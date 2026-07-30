"""On-demand streamed research compilation for a selected signal cluster."""

from __future__ import annotations

import json
import os
import secrets
import time
from typing import Any, Dict

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from compile_engine import (
    COMPILE_SCHEMA_VERSION,
    build_compile_prompts,
    compile_key,
    grounded_evidence_ids,
    has_grounding,
    iter_cluster_evidence,
    normalize_instruction,
    parse_compile_result,
    source_version,
    stream_llm_tokens,
)
from creator_intelligence import build_topic_clusters
from llm_summary import load_creator_profile


compile_bp = Blueprint("compile", __name__)


def _db():
    return current_app.config.get("INTEL_DB")


def _scored_data():
    loader = current_app.config.get("SCORED_DATA_LOADER")
    return loader() if loader else {}


def _event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@compile_bp.route("/api/compile", methods=["POST"])
def api_compile():
    body = request.get_json(silent=True) or {}
    cluster_slug = str(body.get("cluster_slug") or "").strip()
    if not cluster_slug or len(cluster_slug) > 160:
        return jsonify({"error": "valid cluster_slug required"}), 400
    instruction = normalize_instruction(str(body.get("instruction") or ""))

    db = _db()
    if db is None:
        return jsonify({"error": "compile store unavailable"}), 503
    scored_data = _scored_data()
    clusters = build_topic_clusters(scored_data, intel_db=db)
    cluster = next((item for item in clusters if item.get("slug") == cluster_slug), None)
    if not cluster:
        return jsonify({"error": "unknown_cluster"}), 404

    profile = load_creator_profile()
    instruction_hash = compile_key(instruction, profile)
    version = source_version(scored_data, cluster)
    max_age = max(3600, int(os.environ.get("COMPILE_CACHE_SECONDS", "86400")))
    lock_key = f"{cluster_slug}:{instruction_hash}"
    lease_token = secrets.token_urlsafe(24)

    def cache_is_current(cached):
        return bool(
            cached
            and int(cached.get("schema_version") or 0) == COMPILE_SCHEMA_VERSION
            and cached.get("source_version") == version
        )

    def replay(cached):
        yield _event({
            "type": "cache", "cache_hit": True,
            "generated_at": cached["generated_at"],
            "locked_until": cached["generated_at"] + max_age,
            "model": cached.get("model", ""),
        })
        for record in cached.get("evidence", []):
            yield _event({"type": "evidence", "record": record, "cache_hit": True})
        yield _event({
            "type": "result", "result": cached["result"],
            "model": cached.get("model", ""), "cache_hit": True,
            "generated_at": cached["generated_at"],
            "locked_until": cached["generated_at"] + max_age,
        })
        yield _event({"type": "done"})

    def compile_fresh():
        if not db.compile_lock_refresh(lock_key, lease_token):
            yield _event({"type": "error", "code": "compile_lease_lost", "message": "The desk compile lease expired. Try again."})
            yield _event({"type": "done"})
            return
        last_lease_refresh = time.monotonic()
        hourly_limit = max(1, int(os.environ.get("COMPILE_MAX_UNIQUE_PER_HOUR", "30")))
        if not db.compile_attempt_allow(hourly_limit):
            yield _event({
                "type": "error", "code": "compile_rate_limited",
                "message": "The live desk has reached its hourly compile limit. Cached briefs remain available.",
            })
            yield _event({"type": "done"})
            return

        yield _event({
            "type": "status", "phase": "evidence",
            "message": f"Reading {len(cluster.get('related_items', []))} live sources for {cluster.get('topic', 'this story')}.",
        })
        evidence_records = []
        for record in iter_cluster_evidence(cluster, scored_data):
            evidence_records.append(record)
            yield _event({"type": "evidence", "record": record, "cache_hit": False})

        evidence_records.sort(key=lambda value: int(value["id"][1:]))
        valid_ids = grounded_evidence_ids(evidence_records)
        if not has_grounding(evidence_records):
            yield _event({
                "type": "error", "code": "evidence_unavailable",
                "message": "The research desk could not retrieve enough source evidence to compile safely.",
            })
            yield _event({"type": "done"})
            return

        system, prompt = build_compile_prompts(profile, cluster, evidence_records, instruction)
        model = ""
        result = None
        issues = []
        for attempt in range(2):
            if not db.compile_lock_refresh(lock_key, lease_token):
                yield _event({"type": "error", "code": "compile_lease_lost", "message": "The desk compile lease expired. Try again."})
                yield _event({"type": "done"})
                return
            last_lease_refresh = time.monotonic()
            if attempt:
                yield _event({
                    "type": "status", "phase": "repairing",
                    "message": "The desk is checking citations and repairing the brief.",
                })
                yield _event({"type": "draft_reset"})
                repair = (
                    "\n\nYour previous response failed validation: " + "; ".join(issues[:8])
                    + ". Return a corrected JSON object only, with valid evidence IDs."
                )
            else:
                yield _event({
                    "type": "status", "phase": "compiling",
                    "message": "The research desk is writing a creator-specific editorial brief.",
                })
                repair = ""
            raw = ""
            last_stream_heartbeat = time.monotonic()
            try:
                for chunk in stream_llm_tokens(prompt + repair, system, profile):
                    if time.monotonic() - last_lease_refresh >= 30:
                        if not db.compile_lock_refresh(lock_key, lease_token):
                            raise RuntimeError("compile lease expired")
                        last_lease_refresh = time.monotonic()
                    token = chunk.get("token", "")
                    if token:
                        raw += token
                        if len(raw) > 60000:
                            raise RuntimeError("compile response exceeded safety limit")
                        yield _event({"type": "token", "token": token})
                    elif chunk.get("heartbeat") and time.monotonic() - last_stream_heartbeat >= 5:
                        yield _event({
                            "type": "status", "phase": "compiling",
                            "message": "The research desk is checking the evidence and shaping the brief.",
                        })
                        last_stream_heartbeat = time.monotonic()
                    model = chunk.get("model") or model
            except Exception as exc:
                yield _event({"type": "error", "code": "llm_unavailable", "message": str(exc)[:500]})
                yield _event({"type": "done"})
                return
            result, issues = parse_compile_result(raw, valid_ids)
            if result:
                break

        if not result:
            yield _event({
                "type": "error", "code": "invalid_compile",
                "message": "The research desk returned an invalid cited brief.",
                "issues": issues[:10],
            })
            yield _event({"type": "done"})
            return

        generated_at = time.time()
        db.compile_cache_trim(generated_at - (7 * 86400))
        stored = db.compile_cache_set_if_lock_owner(
            cluster_slug, instruction_hash, instruction, version,
            evidence_records, result, model,
            schema_version=COMPILE_SCHEMA_VERSION,
            lock_key=lock_key, owner_token=lease_token,
        )
        if not stored:
            yield _event({
                "type": "error", "code": "compile_lease_lost",
                "message": "The desk compile lease expired before the brief could be stored. Try again.",
            })
            yield _event({"type": "done"})
            return
        yield _event({
            "type": "result", "result": result, "model": model,
            "cache_hit": False, "generated_at": generated_at,
            "locked_until": generated_at + max_age,
        })
        yield _event({"type": "done"})

    def stream():
        yield "retry: 3000\n\n"
        yield _event({
            "type": "meta", "cluster_slug": cluster_slug,
            "topic": cluster.get("topic", ""), "source_version": version,
            "instruction": instruction, "cache_hit": False,
        })

        cached = db.compile_cache_get(cluster_slug, instruction_hash, max_age_seconds=max_age)
        if cache_is_current(cached):
            yield from replay(cached)
            return

        owns_lease = db.compile_lock_acquire(lock_key, lease_token)
        if not owns_lease:
            yield _event({"type": "status", "phase": "waiting", "message": "Another desk compile is finishing."})
            for _ in range(90):
                time.sleep(1)
                cached = db.compile_cache_get(cluster_slug, instruction_hash, max_age_seconds=max_age)
                if cache_is_current(cached):
                    yield from replay(cached)
                    return
                owns_lease = db.compile_lock_acquire(lock_key, lease_token)
                if owns_lease:
                    break
                if _ and _ % 10 == 0:
                    yield _event({"type": "status", "phase": "waiting", "message": "The other desk compile is still running."})
        if not owns_lease:
            yield _event({
                "type": "error", "code": "compile_busy",
                "message": "Another compile is still running. Try this signal again shortly.",
            })
            yield _event({"type": "done"})
            return

        try:
            cached = db.compile_cache_get(cluster_slug, instruction_hash, max_age_seconds=max_age)
            if cache_is_current(cached):
                yield from replay(cached)
                return
            yield from compile_fresh()
        finally:
            db.compile_lock_release(lock_key, lease_token)

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
