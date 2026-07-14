"""Content pipeline routes: enrich, forge, agentic-run, editorial, publish, analytics."""

import json
import os
import random
import threading
import time
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

content_bp = Blueprint("content", __name__)


def _db():
    return current_app.config.get("INTEL_DB")


def _enrichment():
    return current_app.config.get("ENRICHMENT_SERVICE")


def _agent_runner():
    return current_app.config.get("AGENT_RUNNER")


def _load_scored_data():
    dash = _dash()
    return dash.load_scored_data() if dash else {}


def _dash():
    return current_app.config.get("DASH")


# ── Enrichment ───────────────────────────────────────────────────────────────

@content_bp.route("/api/enrich-status", methods=["GET"])
def api_enrich_status():
    enrichment_service = _enrichment()
    if enrichment_service is None:
        return jsonify({"enabled": False})
    payload = enrichment_service.status()
    payload["enabled"] = True
    return jsonify(payload)


@content_bp.route("/api/enrich", methods=["POST"])
def api_enrich():
    """Enqueue a single item for creator-pack enrichment."""
    enrichment_service = _enrichment()
    if enrichment_service is None:
        return jsonify({"error": "enrichment_disabled"}), 503
    item = request.get_json(silent=True) or {}
    if not item.get("url") and not item.get("title"):
        return jsonify({"error": "missing url or title"}), 400
    result = enrichment_service.enqueue(item, force=bool(item.get("force")))
    return jsonify(result)


@content_bp.route("/api/enrich/<content_hash>", methods=["GET"])
def api_enrich_get(content_hash):
    """Return the cached creator pack for a content hash, if any."""
    db = _db()
    if db is None:
        return jsonify({"error": "no_db"}), 503
    cached = db.get_creator_asset(content_hash)
    if not cached:
        return jsonify({"status": "missing"}), 404
    return jsonify({
        "status": cached.get("status"),
        "model": cached.get("model"),
        "error": cached.get("error"),
        "payload": cached.get("payload"),
        "updated_at": cached.get("updated_at"),
    })


# ── Forge ────────────────────────────────────────────────────────────────────

@content_bp.route("/api/forge/<int:item_id>", methods=["POST"])
def api_forge(item_id):
    """Generate Production Forge multi-format assets for a saved item."""
    enrichment_service = _enrichment()
    db = _db()
    if enrichment_service is None or db is None:
        return jsonify({"error": "forge_disabled"}), 503
    item = db.get_saved_item(item_id)
    if not item:
        return jsonify({"error": "not_found"}), 404

    payload_lines = [
        f"Title: {item.get('working_title') or item.get('title') or ''}",
        f"Hook: {item.get('hook') or ''}",
        f"Format: {item.get('format') or ''}",
        f"Notes: {item.get('notes') or ''}",
    ]
    outline = item.get("outline")
    if isinstance(outline, str):
        try:
            outline = json.loads(outline)
        except Exception:
            outline = [outline]
    if isinstance(outline, list) and outline:
        payload_lines.append("Outline:")
        payload_lines.extend([f"- {line}" for line in outline if line])

    content_hash_val = item.get("content_hash")
    if content_hash_val:
        cached = db.get_creator_asset(content_hash_val)
        if cached and cached.get("payload"):
            pack = cached["payload"]
            payload_lines.extend([
                f"Insight: {pack.get('insight', '')}",
                f"Demo segment: {pack.get('demo_segment', '')}",
                f"Caveats: {pack.get('caveats', '')}",
            ])

    research_data = "\n".join(line for line in payload_lines if line.strip())
    result = enrichment_service.forge_saved(item_id, research_data)
    return jsonify(result)


@content_bp.route("/api/agentic-run", methods=["POST"])
def api_agentic_run():
    """Run the full cluster -> enrich -> dive -> save -> forge pipeline."""
    enrichment_service = _enrichment()
    db = _db()
    if enrichment_service is None or db is None:
        return jsonify({"error": "agentic_disabled"}), 503
    try:
        from agentic_researcher import AgenticResearcher
    except Exception as exc:
        return jsonify({"error": f"import_failed:{exc}"}), 500

    payload = request.get_json(silent=True) or {}
    automation_override = payload.get("automation") or {}
    profile = __import__("llm_summary").load_creator_profile()
    automation = {**(profile.get("automation") or {}), **automation_override}

    scored = _load_scored_data()
    researcher = AgenticResearcher(db=db, enrichment_service=enrichment_service)

    def _runner():
        try:
            result = researcher.run_daily_pipeline(scored, automation=automation)
            print(f"[agentic] daily pipeline result: {result}")
        except Exception as exc:
            print(f"[agentic] failed: {exc}")

    thread = threading.Thread(target=_runner, name="agentic-run", daemon=True)
    thread.start()
    return jsonify({"ok": True, "status": "running", "automation": automation})


@content_bp.route("/api/forge-status/<int:item_id>", methods=["GET"])
def api_forge_status(item_id):
    db = _db()
    if db is None:
        return jsonify({"error": "no_db"}), 503
    item = db.get_saved_item(item_id)
    if not item:
        return jsonify({"error": "not_found"}), 404
    assets = item.get("production_assets")
    if isinstance(assets, str):
        try:
            assets = json.loads(assets)
        except Exception:
            assets = {}
    return jsonify({
        "status": item.get("production_status") or "none",
        "assets": assets or {},
        "updated_at": item.get("updated_at"),
    })


# ── Editorial ─────────────────────────────────────────────────────────────────

_EDITORIAL_FALLBACK = (
    "# Daily Production Briefing\n\n"
    "## Plan generation timed out\n\n"
    "No editorial plan was produced. Retry generation or work from the grounded recommendation on Today.\n"
)


@content_bp.route("/api/editorial/briefing", methods=["GET", "POST"])
def api_editorial_briefing():
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

    force = request.method == "POST"
    briefing_timeout = int(os.environ.get("BRIEFING_TIMEOUT_SECONDS", "30"))
    pool = ThreadPoolExecutor(max_workers=1)

    dash = _dash()
    future = pool.submit(dash.generate_editorial_briefing, force)
    try:
        data = future.result(timeout=briefing_timeout)
        pool.shutdown(wait=False)
        return jsonify(data)
    except FutureTimeout:
        pool.shutdown(wait=False, cancel_futures=True)
        return jsonify({
            "briefing": _EDITORIAL_FALLBACK,
            "generated_at": time.time(),
            "status": "fallback",
            "note": f"AI briefing timed out after {briefing_timeout}s; showing a static plan.",
        })
    except Exception as e:
        pool.shutdown(wait=False)
        return jsonify({"error": str(e)}), 500


@content_bp.route("/api/editorial/approve", methods=["POST"])
def api_editorial_approve():
    db = _db()
    if db is None:
        return jsonify({"error": "no_db"}), 503
    try:
        scored_data = _load_scored_data()
        dash = _dash()
        briefing = dash._load_cached_editorial_briefing()
        if not briefing or briefing.get("status") != "ready":
            return jsonify({"error": "A current verified editorial plan is required before approval"}), 409
        current_version = scored_data.get("last_updated") if isinstance(scored_data, dict) else None
        if briefing.get("source_version") != current_version:
            return jsonify({"error": "Source data changed after this plan was generated; regenerate it before approval"}), 409
        clusters = dash._cockpit_clusters(scored_data)
        if not clusters:
            return jsonify({"error": "No clusters available to approve"}), 400
        plan_items = briefing.get("plan_items") or []
        if not plan_items:
            return jsonify({"error": "Editorial plan has no bound production items; regenerate it"}), 409
        clusters_by_slug = {cluster.get("slug"): cluster for cluster in clusters}

        # Mark the plan as approved *before* side effects so a concurrent
        # approval request or a write failure cannot duplicate work.
        marked = dash._mark_editorial_briefing_approved()
        if not marked or marked.get("status") != "approved":
            return jsonify({"error": "Editorial plan was already approved or could not be locked"}), 409

        base = datetime.now()
        rec_day = (base + timedelta(days=1)).strftime("%Y-%m-%d")
        pub_day = (base + timedelta(days=2)).strftime("%Y-%m-%d")

        dispatched_runs = []
        saved_items_count = 0

        agent_runner = _agent_runner()

        for plan_item in plan_items:
            c = clusters_by_slug.get(plan_item.get("cluster_slug"))
            if not c:
                return jsonify({"error": "A planned story is no longer active; regenerate the editorial plan"}), 409

            topic_title = c.get("topic")
            slug = c.get("slug")
            category = c.get("category") or "General"
            content_format = plan_item.get("format") or "YouTube long-form"
            plan_key = int(briefing.get("generated_at") or 0)

            item_id = db.save_item({
                "title": topic_title,
                "working_title": topic_title,
                "url": f"editorial://{plan_key}/{slug}/{content_format.lower().replace(' ', '-')}",
                "category": category,
                "signal_score": c.get("average_signal_score") or 0,
                "creator_score": c.get("creator_score") or 50,
                "pipeline_type": "creator",
                "status": "researching",
                "format": content_format,
                "outline": [c.get("why_this_is_a_story") or ""]
            })
            saved_items_count += 1

            sid_rec = f"sched-{uuid.uuid4().hex[:12]}"
            work_kind = "record" if content_format.startswith("YouTube") else "outline"
            db.insert_schedule(sid_rec, str(item_id), rec_day, work_kind, time="10:00")

            sid_pub = f"sched-{uuid.uuid4().hex[:12]}"
            db.insert_schedule(sid_pub, str(item_id), pub_day, "publish", time="12:00")

            if agent_runner:
                for agent_t in plan_item.get("agent_types") or []:
                    try:
                        run_id = agent_runner.dispatch(
                            agent_t,
                            topic=topic_title,
                            target_id=slug
                        )
                        dispatched_runs.append({"agent": agent_t, "run_id": run_id})
                    except Exception as ae:
                        print(f"[editorial_approve] failed to dispatch {agent_t} for {topic_title}: {ae}")

        return jsonify({
            "ok": True,
            "saved_count": saved_items_count,
            "dispatched": dispatched_runs,
            "scheduled_days": {"record": rec_day, "publish": pub_day}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Publish ──────────────────────────────────────────────────────────────────

@content_bp.route("/api/publish", methods=["POST"])
def api_publish():
    db = _db()
    if db is None:
        return jsonify({"error": "no_db"}), 503
    payload = request.get_json(silent=True) or {}
    item_id = payload.get("item_id")
    platform = payload.get("platform")
    if not item_id or not platform:
        return jsonify({"error": "missing item_id or platform"}), 400

    item = None
    try:
        int_id = int(item_id)
        item = db.get_saved_item(int_id)
    except (ValueError, TypeError):
        pass

    if not item:
        saved_items = db.get_saved_items()
        item = next((i for i in saved_items if i.get("url") == item_id or i.get("title") == item_id or str(i.get("id")) == str(item_id)), None)

    if not item:
        return jsonify({"error": f"item not found: {item_id}"}), 404

    item_id = item["id"]

    db.create_or_update_publication(
        item_id=item_id,
        platform=platform,
        views=0,
        impressions=0,
        ctr=0.0,
        engagement_rate=0.0,
        status="publishing"
    )

    def _publisher_simulator():
        time.sleep(3.0)
        views = random.randint(10, 50)
        impressions = random.randint(150, 400)
        ctr = round(views / impressions, 4) if impressions > 0 else 0.0
        engagement_rate = round(views * 0.08 / impressions, 4) if impressions > 0 else 0.0
        try:
            db.create_or_update_publication(
                item_id=item_id,
                platform=platform,
                views=views,
                impressions=impressions,
                ctr=ctr,
                engagement_rate=engagement_rate,
                status="live"
            )
        except Exception as e:
            print(f"[publish_sim] failed: {e}")

    thread = threading.Thread(target=_publisher_simulator, name=f"publish-{item_id}-{platform}", daemon=True)
    thread.start()

    return jsonify({"ok": True, "status": "publishing"})


# ── Analytics ─────────────────────────────────────────────────────────────────

@content_bp.route("/api/analytics/simulate", methods=["POST"])
def api_analytics_simulate():
    db = _db()
    if db is None:
        return jsonify({"error": "no_db"}), 503

    try:
        publications = db.get_publication_analytics()
        updated_count = 0
        for pub in publications:
            if pub.get("status") == "live":
                from analytics_sync import sync_publication_metrics
                synced = sync_publication_metrics(pub)

                if synced:
                    views = synced["views"]
                    impressions = synced["impressions"]
                    ctr = synced["ctr"]
                    engagement_rate = synced["engagement_rate"]
                    status = synced["status"]
                else:
                    views = pub.get("views", 0) + random.randint(120, 1400)
                    impressions = pub.get("impressions", 0) + random.randint(1800, 12000)
                    ctr = round(views / impressions, 4) if impressions > 0 else 0.0
                    engagement_rate = round(views * 0.07 / impressions, 4) if impressions > 0 else 0.0
                    status = "live"
                    if views > 25000:
                        status = "completed"

                db.create_or_update_publication(
                    item_id=pub.get("item_id"),
                    platform=pub.get("platform"),
                    views=views,
                    impressions=impressions,
                    ctr=ctr,
                    engagement_rate=engagement_rate,
                    status=status
                )
                updated_count += 1

        try:
            active_tests = db.list_all_active_ab_tests()
            for ab in active_tests:
                new_a_views = ab.get("variant_a_views", 0) + random.randint(20, 150)
                new_b_views = ab.get("variant_b_views", 0) + random.randint(20, 150)
                new_a_ctr = round(random.uniform(0.035, 0.070), 4)
                new_b_ctr = round(random.uniform(0.045, 0.090), 4)
                db.update_ab_test_metrics(
                    ab["id"],
                    variant_a_views=new_a_views,
                    variant_b_views=new_b_views,
                    variant_a_ctr=new_a_ctr,
                    variant_b_ctr=new_b_ctr
                )
                updated_count += 1
        except Exception as ab_err:
            print(f"[ab_sim] failed: {ab_err}")

        return jsonify({"ok": True, "updated": updated_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
