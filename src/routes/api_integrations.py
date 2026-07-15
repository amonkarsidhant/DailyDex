"""Integrations endpoints: Notion sync, shorts repurposing, title A/B tests.

State is reached through ``current_app.config["DASH"]`` (the dashboard module)
so the blueprint always talks to the live app instance regardless of how the
module was imported (``dashboard_new`` locally, ``src.dashboard_new`` under
gunicorn, or a re-import in tests).
"""
import json
import time

import os
from flask import Blueprint, current_app, jsonify, request, send_from_directory

integrations_bp = Blueprint("integrations", __name__)


def _db():
    dash = current_app.config.get("DASH")
    return getattr(dash, "intel_db", None)


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


@integrations_bp.route("/api/videos/<filename>", methods=["GET"])
def serve_rendered_video(filename):
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data"))
    videos_dir = os.path.join(data_dir, "videos")
    return send_from_directory(videos_dir, filename)

