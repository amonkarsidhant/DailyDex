"""Source-health metadata and asynchronous refresh endpoints."""

import json
import threading

from flask import Blueprint, current_app, jsonify

refresh_bp = Blueprint("refresh", __name__)


def _dash():
    return current_app.config["DASH"]


def _state():
    return current_app.extensions["dailydex_refresh"]


@refresh_bp.route("/api/source-health")
def api_source_health():
    """Get source health status."""
    source_cards, daily_summary = _dash().build_source_health_response()
    return jsonify({"sources": source_cards, "summary": daily_summary})


@refresh_bp.route("/api/dashboard-meta")
def api_dashboard_meta():
    """Return a lightweight snapshot for live dashboard refresh checks."""
    state = _dash().build_dashboard_context()["dashboard_state"]
    return jsonify({
        "snapshot_id": state["snapshot_id"],
        "last_updated_raw": state["last_updated_raw"],
        "last_updated_display": state["last_updated_display"],
        "live_interval_seconds": state["live_interval_seconds"],
        "daily_summary": state["daily_summary"],
        "status_warning": state["status_warning"],
        "counts": state["counts"],
    })


def _run_refresh_job(dash, refresh_state):
    previous_data = dash.load_data()
    try:
        from fetch_news import fetch_all

        fetch_all()
        scored_data = dash.load_scored_data(force=True)
        source_cards, daily_summary = dash.build_source_health_response()
        status = "ok"
        if any(card["status_key"] == "failed" for card in source_cards):
            status = "failed"
        elif any(card["status_key"] in ["cache", "stale"] for card in source_cards):
            status = "partial"
        result = {
            "status": status,
            "last_updated": dash.format_timestamp(scored_data.get("last_updated")),
            "source_health": source_cards,
            "summary": daily_summary,
            "message": daily_summary["freshness_message"],
        }
    except Exception as exc:
        source_cards, daily_summary = dash.build_source_health_response()
        try:
            dash.ensure_parent_dir(dash.DATA_FILE)
            with open(dash.DATA_FILE, "w", encoding="utf-8") as handle:
                json.dump(previous_data, handle, indent=2)
        except Exception:
            pass
        result = {
            "status": "failed",
            "last_updated": dash.format_timestamp(previous_data.get("last_updated")),
            "source_health": source_cards,
            "summary": daily_summary,
            "message": f"Refresh failed. Existing data preserved. {exc}",
        }
    with refresh_state["lock"]:
        refresh_state["result"] = result
        refresh_state["running"] = False


@refresh_bp.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Start a manual refresh in the background; poll /api/refresh/status."""
    state = _state()
    with state["lock"]:
        if state["running"]:
            return jsonify({"status": "running", "started": False})
        state["running"] = True
        state["result"] = None
    thread = threading.Thread(target=_run_refresh_job, args=(_dash(), state), daemon=True)
    thread.start()
    return jsonify({"status": "running", "started": True})


@refresh_bp.route("/api/refresh/status", methods=["GET"])
def api_refresh_status():
    """Report background refresh progress; returns the result once finished."""
    state = _state()
    with state["lock"]:
        running = state["running"]
        result = state["result"]
    if running:
        return jsonify({"running": True})
    if result is None:
        source_cards, daily_summary = _dash().build_source_health_response()
        return jsonify({
            "running": False,
            "status": "idle",
            "source_health": source_cards,
            "summary": daily_summary,
            "message": daily_summary.get("freshness_message", ""),
        })
    payload = dict(result)
    payload["running"] = False
    return jsonify(payload)


def init_refresh(app):
    """Register refresh routes with state isolated to this Flask app."""
    app.extensions["dailydex_refresh"] = {
        "lock": threading.Lock(),
        "running": False,
        "result": None,
    }
    app.register_blueprint(refresh_bp)
