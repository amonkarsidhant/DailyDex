"""Studio routes: autonomous content factory, SSE log stream, format regeneration."""

import json
import queue
import threading
from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

studio_bp = Blueprint("studio", __name__)

# ── module-level state (single-process; fine for local/dev) ──────────────────
_studio_run_state: dict = {"running": False, "started_at": None, "last": None}
_studio_logs: list[str] = []
_studio_subscribers: list[queue.Queue] = []
_studio_sub_lock = threading.Lock()


def _db():
    return current_app.config.get("INTEL_DB")


def add_studio_log(msg: str) -> None:
    _studio_logs.append(msg)
    if len(_studio_logs) > 500:
        _studio_logs.pop(0)
    with _studio_sub_lock:
        for q in _studio_subscribers:
            q.put(msg)


def _cockpit_studio() -> dict:
    """Creator Central: autonomously generated content + provider status."""
    db = _db()
    stories = []
    if db:
        try:
            stories = db.studio_list_stories(limit=30)
        except Exception:
            stories = []
    providers = []
    try:
        import cli_registry

        providers = cli_registry.probe().get("providers", [])
    except Exception:
        providers = []
    try:
        import studio as _studio

        skills = [
            {"format": f, "label": _studio.SKILLS[f]["label"], "icon": _studio.SKILLS[f]["icon"]}
            for f in _studio.FORMAT_ORDER
        ]
    except Exception:
        skills = []
    return {"stories": stories, "providers": providers, "skills": skills}


@studio_bp.route("/api/studio")
def api_studio():
    """List autonomously generated content + detected providers + skills."""
    return jsonify(_cockpit_studio() | {"run": _studio_run_state})


@studio_bp.route("/api/studio/run", methods=["POST"])
def api_studio_run():
    """Kick the autonomous content factory in the background."""
    if _studio_run_state["running"]:
        return jsonify({"status": "already_running"}), 409
    body = request.get_json(silent=True) or {}
    top_n = int(body.get("top_n", 0)) or None
    slugs = body.get("slugs") or None
    intel_db = _db()
    _studio_run_state.update(running=True, started_at=datetime.now().isoformat())

    def _runner():
        global _studio_logs
        with _studio_sub_lock:
            _studio_logs.clear()
        add_studio_log("Factory run started.")
        try:
            import studio_job

            _studio_run_state["last"] = studio_job.run(
                intel_db=intel_db, top_n=top_n, slugs=slugs, log_fn=add_studio_log
            )
            add_studio_log("Factory run completed.")
        except Exception as exc:
            _studio_run_state["last"] = {"ok": False, "error": str(exc)}
            add_studio_log(f"Factory run failed: {exc}")
        finally:
            _studio_run_state["running"] = False

    threading.Thread(target=_runner, name="studio-run", daemon=True).start()
    return jsonify({"status": "started"})


@studio_bp.route("/api/studio/stream")
def api_studio_stream():
    """SSE stream for real-time factory logs."""

    def gen():
        q: queue.Queue = queue.Queue()
        with _studio_sub_lock:
            _studio_subscribers.append(q)
        try:
            current_logs = []
            with _studio_sub_lock:
                current_logs = list(_studio_logs)
            for log in current_logs:
                yield f"data: {json.dumps({'text': log})}\n\n"
            yield "retry: 2000\n\n"
            while True:
                try:
                    log = q.get(timeout=10)
                    yield f"data: {json.dumps({'text': log})}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _studio_sub_lock:
                if q in _studio_subscribers:
                    _studio_subscribers.remove(q)

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@studio_bp.route("/api/studio/<story_key>/<fmt>/regenerate", methods=["POST"])
def api_studio_regenerate(story_key, fmt):
    """Regenerate one format for one story, reusing its stored research."""
    db = _db()
    if db is None:
        return jsonify({"error": "no_db"}), 503
    rows = db.studio_get_story(story_key)
    row = next((r for r in rows if r["fmt"] == fmt), None)
    if not row:
        return jsonify({"error": "not_found"}), 404
    import studio

    prefer = (request.get_json(silent=True) or {}).get("provider")
    db.studio_set_status(story_key, row["topic"], fmt, "generating")
    result = studio.generate_format(fmt, row.get("research") or "", prefer=prefer)
    db.studio_save_result(story_key, row["topic"], fmt, result)
    return jsonify(
        {
            "ok": result["ok"],
            "format": fmt,
            "provider": result.get("provider"),
            "body": result.get("body", ""),
        }
    )
