"""Agent dispatch, status, logs, and SSE stream routes."""

import json
import queue

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

agents_bp = Blueprint("agents", __name__)


def _db():
    return current_app.config.get("INTEL_DB")


def _agent_runner():
    return current_app.config.get("AGENT_RUNNER")


@agents_bp.route("/api/agents/dispatch", methods=["POST"])
def api_agents_dispatch():
    agent_runner = _agent_runner()
    if agent_runner is None:
        return jsonify({"error": "agent runner unavailable"}), 503
    from creator_enricher import AgentRunner

    body = request.get_json(silent=True) or {}
    agent_type = body.get("agent_type")
    if agent_type not in AgentRunner.AGENT_TYPES:
        return jsonify({"error": "invalid agent_type"}), 400
    topic = body.get("topic")
    target_id = body.get("target_id")
    dedup_key = (topic or target_id or "").strip().lower()
    was_in_flight = bool(agent_runner._in_flight.get((agent_type, dedup_key)))
    try:
        run_id = agent_runner.dispatch(
            agent_type,
            topic=topic,
            target_id=target_id,
            payload=body.get("payload"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"run_id": run_id, "deduplicated": was_in_flight})


@agents_bp.route("/api/agents")
def api_agents():
    agent_runner = _agent_runner()
    if agent_runner is None:
        return jsonify({"active": [], "recent_done": []})
    return jsonify(agent_runner.snapshot())


@agents_bp.route("/api/agents/<run_id>/logs")
def api_agent_logs(run_id):
    db = _db()
    if db is None:
        return jsonify({"logs": []})
    return jsonify({"run_id": run_id, "logs": db.get_agent_logs(run_id)})


@agents_bp.route("/api/agents/<run_id>/result")
def api_agent_result(run_id):
    """Return the full generated text for a completed agent run."""
    try:
        from creator_enricher import _AGENT_RESULTS

        text = _AGENT_RESULTS.get(run_id)
        if text:
            return jsonify({"run_id": run_id, "text": text})
    except Exception:
        pass
    db = _db()
    if db:
        try:
            for row in (db.list_agent_runs(limit=200) or []):
                if row.get("id") == run_id:
                    return jsonify({"run_id": run_id, "text": row.get("result_summary") or ""})
        except Exception:
            pass
    return jsonify({"run_id": run_id, "text": ""})


@agents_bp.route("/api/agents/stream")
def api_agents_stream():
    agent_runner = _agent_runner()
    if agent_runner is None:
        return jsonify({"error": "agent runner unavailable"}), 503

    def gen():
        q = agent_runner.subscribe()
        try:
            yield "retry: 5000\n\n"
            while True:
                try:
                    ev = q.get(timeout=15)
                    yield f"data: {json.dumps(ev)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            agent_runner.unsubscribe(q)

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )