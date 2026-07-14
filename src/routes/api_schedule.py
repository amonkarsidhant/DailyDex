"""Content calendar endpoints: schedule CRUD + auto-scheduling from the brief.

State is reached through ``current_app.config["DASH"]`` (the dashboard module)
so the blueprint always talks to the live app instance regardless of how the
module was imported (``dashboard_new`` locally, ``src.dashboard_new`` under
gunicorn, or a re-import in tests).
"""
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

schedule_bp = Blueprint("schedule", __name__)


def _dash():
    return current_app.config.get("DASH")


def _db():
    return getattr(_dash(), "intel_db", None)


def _load_creator_profile_safe():
    try:
        import llm_summary
        return llm_summary.load_creator_profile()
    except Exception:
        return {}


def _schedule_item_payload(intel_db, item_id):
    """Denormalized item fields for a calendar cell."""
    if intel_db is None:
        return {}
    try:
        item = intel_db.get_saved_item(int(item_id))
    except (ValueError, TypeError):
        item = None
    if not item:
        return {}
    return {
        "working_title": item.get("working_title") or item.get("title"),
        "topic": item.get("category") or item.get("topic"),
        "format": item.get("format"),
        "creator_score": item.get("creator_score"),
    }


@schedule_bp.route("/api/schedule", methods=["GET"])
def api_schedule_list():
    intel_db = _db()
    if intel_db is None:
        return jsonify([])
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        today = datetime.now()
        start = start or today.strftime("%Y-%m-%d")
        end = end or (today + timedelta(days=6)).strftime("%Y-%m-%d")
    rows = intel_db.get_schedule_range(start, end)
    for row in rows:
        row["item"] = _schedule_item_payload(intel_db, row.get("item_id"))
    return jsonify(rows)


@schedule_bp.route("/api/schedule", methods=["POST"])
def api_schedule_create():
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    body = request.get_json(silent=True) or {}
    if not body.get("item_id") or not body.get("day") or not body.get("kind"):
        return jsonify({"error": "item_id, day, kind required"}), 400
    sched_id = f"sched-{uuid.uuid4().hex[:12]}"
    intel_db.insert_schedule(sched_id, str(body["item_id"]), body["day"],
                             body["kind"], time=body.get("time"))
    row = intel_db.get_schedule_entry(sched_id)
    row["item"] = _schedule_item_payload(intel_db, row.get("item_id"))
    return jsonify(row), 201


@schedule_bp.route("/api/schedule/<sched_id>", methods=["PUT"])
def api_schedule_update(sched_id):
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    body = request.get_json(silent=True) or {}
    ok = intel_db.update_schedule(sched_id, **body)
    if not ok:
        return jsonify({"error": "not found"}), 404
    row = intel_db.get_schedule_entry(sched_id)
    row["item"] = _schedule_item_payload(intel_db, row.get("item_id"))
    return jsonify(row)


@schedule_bp.route("/api/schedule/<sched_id>", methods=["DELETE"])
def api_schedule_delete(sched_id):
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    ok = intel_db.delete_schedule(sched_id)
    return jsonify({"success": ok})


@schedule_bp.route("/api/schedule/<sched_id>/complete", methods=["POST"])
def api_schedule_complete(sched_id):
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    ok = intel_db.update_schedule(sched_id, status="done")
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"success": True})


@schedule_bp.route("/api/schedule/auto", methods=["POST"])
def api_schedule_auto():
    """Drop top brief items into the next available week (simple heuristic)."""
    dash = _dash()
    intel_db = _db()
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    try:
        from creator_intelligence import (
            build_content_opportunities,
            build_creator_brief,
            build_topic_clusters,
        )

        scored_data = dash.load_scored_data()
        clusters = build_topic_clusters(scored_data, intel_db=intel_db)
        opportunities = build_content_opportunities(scored_data, clusters)
        brief = build_creator_brief(opportunities, clusters, intel_db.get_saved_items())
    except Exception as e:
        return jsonify({"error": f"brief unavailable: {e}"}), 500

    profile = _load_creator_profile_safe()
    publish_days = (profile.get("schedule") or {}).get("publish_days", ["Sat", "Sun"])
    record_window = (profile.get("schedule") or {}).get("preferred_record_window", "10:00-12:00")
    record_time = record_window.split("-")[0]

    picks = []
    if brief.get("best_video_idea"):
        picks.append(brief["best_video_idea"])
    picks.extend(brief.get("long_form_candidates", [])[:2])

    created = []
    base = datetime.now()
    day_idx = 0
    for opp in picks:
        item_id = opp.get("id") or opp.get("url") or opp.get("topic")
        # advance to next weekday
        while (base + timedelta(days=day_idx)).weekday() >= 5:
            day_idx += 1
        rec_day = (base + timedelta(days=day_idx)).strftime("%Y-%m-%d")
        sid = f"sched-{uuid.uuid4().hex[:12]}"
        intel_db.insert_schedule(sid, str(item_id), rec_day, "record", time=record_time)
        created.append(sid)
        # publish on next configured publish day
        pub_offset = day_idx + 1
        for _ in range(7):
            cand = base + timedelta(days=pub_offset)
            if cand.strftime("%a") in publish_days:
                break
            pub_offset += 1
        pub_day = (base + timedelta(days=pub_offset)).strftime("%Y-%m-%d")
        psid = f"sched-{uuid.uuid4().hex[:12]}"
        intel_db.insert_schedule(psid, str(item_id), pub_day, "publish", time="10:00")
        created.append(psid)
        day_idx += 1
    return jsonify({"created": created, "count": len(created)})
