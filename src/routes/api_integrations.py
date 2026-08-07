"""Integrations endpoints: Notion sync, shorts repurposing, title A/B tests.

State is reached through ``current_app.config["DASH"]`` (the dashboard module)
so the blueprint always talks to the live app instance regardless of how the
module was imported (``dashboard_new`` locally, ``src.dashboard_new`` under
gunicorn, or a re-import in tests).
"""
import json
import hmac
import secrets
import time

import os
from flask import Blueprint, current_app, jsonify, redirect, request, send_from_directory, session, url_for

integrations_bp = Blueprint("integrations", __name__)


def _db():
    dash = current_app.config.get("DASH")
    return getattr(dash, "intel_db", None)


@integrations_bp.route("/api/integrations/youtube/connect", methods=["GET"])
def api_youtube_connect():
    """Start a CSRF-protected Google OAuth flow for the creator channel."""
    import youtube_oauth

    state = secrets.token_urlsafe(32)
    session["youtube_oauth_state"] = state
    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI") or url_for(
        "integrations.api_youtube_callback", _external=True
    )
    auth_url = youtube_oauth.get_auth_url(redirect_uri=redirect_uri, state=state)
    if auth_url.startswith("error:"):
        return jsonify({"error": auth_url.removeprefix("error: ")}), 400
    return redirect(auth_url)


@integrations_bp.route("/api/integrations/youtube/callback", methods=["GET"])
def api_youtube_callback():
    """Validate Google OAuth state and persist the resulting refresh token."""
    expected = session.pop("youtube_oauth_state", "")
    received = request.args.get("state", "")
    if not expected or not received or not hmac.compare_digest(expected, received):
        return jsonify({"error": "Invalid or expired OAuth state."}), 400
    if request.args.get("error"):
        return jsonify({"error": f"Google authorization failed: {request.args['error']}"}), 400

    code = request.args.get("code", "")
    if not code:
        return jsonify({"error": "Google did not return an authorization code."}), 400

    import youtube_oauth

    redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI") or url_for(
        "integrations.api_youtube_callback", _external=True
    )
    result = youtube_oauth.exchange_code(code, redirect_uri=redirect_uri)
    if result.get("error"):
        return jsonify({"error": result["error"]}), 502
    return redirect("/cockpit?youtube=connected")


@integrations_bp.route("/api/integrations/youtube/status", methods=["GET"])
def api_youtube_status():
    from settings_manager import get as settings_get

    return jsonify({
        "connected": bool(settings_get("google_refresh_token") or settings_get("google_access_token")),
        "client_configured": bool(settings_get("google_client_id") and settings_get("google_client_secret")),
    })


@integrations_bp.route("/api/integrations/youtube/disconnect", methods=["DELETE"])
def api_youtube_disconnect():
    from settings_manager import update as settings_update

    settings_update({
        "google_access_token": "",
        "google_refresh_token": "",
        "google_token_expiry": "",
    })
    return jsonify({"ok": True, "connected": False})


@integrations_bp.route("/api/integrations/notion/sync", methods=["POST"])
def api_integrations_notion_sync():
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "no_db"}), 503
    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    if not item_id:
        return jsonify({"error": "item_id required"}), 400

    try:
        int_id = int(item_id)
        item = intel_db.get_saved_item(int_id)
    except (ValueError, TypeError, Exception):
        item = None

    if not item:
        try:
            saved_items = intel_db.get_saved_items()
            item = next((i for i in saved_items if str(i.get("id")) == str(item_id) or i.get("url") == item_id or i.get("title") == item_id or i.get("working_title") == item_id), None)
        except Exception:
            item = None

    if not item:
        return jsonify({"error": f"Item not found: {item_id}"}), 404

    # Use real Notion API integration
    try:
        from notion_client import sync_to_notion
        result = sync_to_notion(item)
    except ImportError:
        return jsonify({"error": "Notion integration module not available"}), 500
    except Exception as e:
        return jsonify({"error": f"Notion sync failed: {e}"}), 500

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    notion_url = result.get("notion_url", "")

    # Save the real Notion URL to production_assets
    if notion_url:
        try:
            assets = item.get("production_assets")
            if isinstance(assets, str):
                assets = json.loads(assets or "{}")
            elif not isinstance(assets, dict):
                assets = {}
            assets["notion_page_url"] = notion_url
            assets["notion_page_id"] = result.get("page_id", "")
            intel_db.set_production_assets(item["id"], assets)
        except Exception as e:
            # Page was created but metadata save failed — still return success
            print(f"[notion_sync] Warning: page created but failed to save metadata: {e}")

    return jsonify({"success": True, "notion_url": notion_url})


# ── Repurpose Clips Endpoint (Shorts clipping) ──
@integrations_bp.route("/api/integrations/repurpose", methods=["GET", "POST"])
def api_integrations_repurpose():
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "no_db"}), 503

    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        item_id = body.get("item_id")
        if not item_id:
            return jsonify({"error": "item_id required"}), 400

        # Check existing clips
        existing = intel_db.list_repurposed_clips(item_id)
        if existing:
            return jsonify({"success": True, "clips": existing})

        # Generate real clips using AI-powered clip analysis
        try:
            item = intel_db.get_saved_item(int(item_id))
        except Exception:
            item = None

        if not item:
            return jsonify({"error": f"Item not found: {item_id}"}), 404

        try:
            from clip_generator import generate_clips
            ai_clips = generate_clips(item, num_clips=3)
        except ImportError:
            return jsonify({"error": "Clip generator module not available"}), 500
        except Exception as e:
            print(f"[repurpose] Clip generation failed: {e}")
            return jsonify({"error": f"Clip generation failed: {e}"}), 500

        saved_clips = []
        for c in ai_clips:
            clip_id = intel_db.insert_repurposed_clip(c)
            c["id"] = clip_id
            try:
                from video_renderer import render_short_video
                v_res = render_short_video(
                    title=c.get("title", ""),
                    hook_text=c.get("hook_text", ""),
                    script_text=c.get("script_text", ""),
                    clip_id=clip_id,
                    virality_score=float(c.get("virality_score", 78.0))
                )
                if v_res.get("success"):
                    c["video_url"] = f"/api/videos/{clip_id}.mp4"
            except Exception as ve:
                print(f"[repurpose] video rendering warning: {ve}")
            saved_clips.append(c)

        return jsonify({"success": True, "clips": saved_clips})

    else:  # GET
        parent_id = request.args.get("parent_item_id")
        if not parent_id:
            return jsonify({"error": "parent_item_id query param required"}), 400
        clips = intel_db.list_repurposed_clips(int(parent_id))
        return jsonify({"success": True, "clips": clips})


@integrations_bp.route("/api/integrations/repurpose/<clip_id>/publish", methods=["POST"])
def api_integrations_repurpose_publish(clip_id):
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "no_db"}), 503

    # Attempt real YouTube Shorts upload if OAuth is available
    published_url = None
    try:
        from youtube_oauth import _ensure_valid_token
        token = _ensure_valid_token()
        if token:
            # Real YouTube upload would go here when video file is available
            # For now, mark as ready — actual upload requires a rendered video file
            print(f"[clip_publish] YouTube OAuth available for clip {clip_id}")
            published_url = None  # Set when actual video upload is implemented
    except ImportError:
        pass
    except Exception as e:
        print(f"[clip_publish] OAuth check failed: {e}")

    if published_url:
        ok = intel_db.update_repurposed_clip(clip_id, status="live", published_url=published_url)
        status_label = "live"
    else:
        # No real upload — mark as ready_to_publish instead of faking a URL
        ok = intel_db.update_repurposed_clip(clip_id, status="ready_to_publish")
        status_label = "ready_to_publish"

    if not ok:
        return jsonify({"error": "Clip not found"}), 404

    return jsonify({
        "success": True,
        "status": status_label,
        "published_url": published_url or "",
        "message": "Clip marked as ready. Connect YouTube OAuth and provide a video file to upload." if not published_url else "Published successfully."
    })


# ── Title & Thumbnail A/B Testing Endpoint ──
@integrations_bp.route("/api/integrations/ab-test", methods=["POST"])
def api_integrations_ab_test():
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "no_db"}), 503
    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    variant_a_title = body.get("variant_a_title", "")
    variant_b_title = body.get("variant_b_title", "")

    if not item_id or not variant_a_title or not variant_b_title:
        return jsonify({"error": "item_id, variant_a_title, and variant_b_title required"}), 400

    # End any active tests for this item first
    active_test = intel_db.get_active_ab_test(item_id)
    if active_test:
        intel_db.update_ab_test_metrics(active_test["id"], status="completed", ended_at=time.time())

    test_id = intel_db.insert_ab_test({
        "item_id": item_id,
        "variant_a_title": variant_a_title,
        "variant_b_title": variant_b_title,
        "variant_a_image": body.get("variant_a_image", ""),
        "variant_b_image": body.get("variant_b_image", ""),
        "status": "active"
    })

    return jsonify({"success": True, "test_id": test_id})


@integrations_bp.route("/api/integrations/ab-test/active", methods=["GET"])
def api_integrations_ab_test_active():
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "no_db"}), 503
    item_id = request.args.get("item_id")
    if not item_id:
        return jsonify({"error": "item_id required"}), 400
    test = intel_db.get_active_ab_test(int(item_id))
    return jsonify({"success": True, "test": test})


@integrations_bp.route("/api/integrations/linkedin/carousel", methods=["POST"])
def api_linkedin_carousel():
    """Render carousel copy to the PDF LinkedIn accepts for a document post.

    Accepts either ``slides`` (a list) or ``text`` (generated copy to parse).
    Rendering only — publishing stays a separate, explicit step.
    """
    import carousel_renderer

    payload = request.get_json(silent=True) or {}
    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        slides = carousel_renderer.parse_slides(str(payload.get("text") or ""))
    slides = [str(s).strip() for s in slides if str(s).strip()]
    if not slides:
        return jsonify({"error": "no slides supplied"}), 400

    import llm_summary
    profile = llm_summary.load_creator_profile()
    result = carousel_renderer.render_carousel_pdf(
        slides,
        brand_label=(payload.get("brand_label") or profile.get("brand_label")
                     or profile.get("channel_name") or "DAILYDEX • AI REPORT"),
        handle=payload.get("handle") or profile.get("linkedin_handle", ""),
        accent_color=profile.get("video_accent_color") or "#F0B72F",
        topic=str(payload.get("topic") or "")[:40],
    )
    if not result.get("success"):
        return jsonify({"error": result.get("error", "render failed")}), 502
    result["download_url"] = f"/api/carousels/{os.path.basename(result['pdf_path'])}"
    return jsonify(result)


@integrations_bp.route("/api/integrations/linkedin/status", methods=["GET"])
def api_linkedin_status():
    """Whether a usable LinkedIn token is configured, without exposing it."""
    import linkedin_client

    if not linkedin_client._token():
        return jsonify({"connected": False, "reason": "LINKEDIN_ACCESS_TOKEN is not set"})
    who = linkedin_client.get_author_urn()
    if not who.get("ok"):
        return jsonify({"connected": False, "reason": who.get("error")})
    return jsonify({"connected": True, "author_urn": who["urn"], "name": who.get("name", "")})


@integrations_bp.route("/api/integrations/linkedin/post", methods=["POST"])
def api_linkedin_post():
    """Publish a rendered carousel PDF as a LinkedIn document post.

    Deliberately not reachable from the orchestrator or the factory: this
    publishes public content under the creator's own name, so it stays an
    explicit request. ``confirm: true`` is required so a stray call cannot post.
    """
    import linkedin_client

    payload = request.get_json(silent=True) or {}
    if payload.get("confirm") is not True:
        return jsonify({"error": "confirmation_required",
                        "detail": "pass confirm=true to publish publicly"}), 400

    pdf_path = str(payload.get("pdf_path") or "").strip()
    if not pdf_path:
        return jsonify({"error": "pdf_path required"}), 400

    # Confine reads to the carousel output directory; the caller must not be
    # able to hand this route an arbitrary path on the host.
    data_dir = os.environ.get("DATA_DIR", os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data"))
    carousels = os.path.realpath(os.path.join(data_dir, "carousels"))
    resolved = os.path.realpath(pdf_path if os.path.isabs(pdf_path)
                                else os.path.join(carousels, pdf_path))
    if not (resolved == carousels or resolved.startswith(carousels + os.sep)):
        return jsonify({"error": "pdf_path must be inside the carousels directory"}), 400

    result = linkedin_client.publish_document_post(
        pdf_path=resolved,
        commentary=str(payload.get("commentary") or ""),
        title=str(payload.get("title") or ""),
        # Least public default: an explicit visibility is required to hit the feed.
        visibility=str(payload.get("visibility") or "CONNECTIONS").upper(),
    )
    if not result.get("ok"):
        return jsonify({"error": result.get("error"), "stage": result.get("stage")}), 502
    return jsonify(result)


@integrations_bp.route("/api/carousels/<filename>", methods=["GET"])
def serve_rendered_carousel(filename):
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data"))
    return send_from_directory(os.path.join(data_dir, "carousels"), filename)


@integrations_bp.route("/api/videos/<filename>", methods=["GET"])
def serve_rendered_video(filename):
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data"))
    videos_dir = os.path.join(data_dir, "videos")
    return send_from_directory(videos_dir, filename)
