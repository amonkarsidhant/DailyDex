"""Tests for the Creator Cockpit backend (Phases 1-5)."""

import json
import time

import pytest

import creator_intelligence as ci
from data_models import IntelligenceDB


# ── Phase 1: cluster time-series + radar ──────────────────────────────────

def _db(tmp_path):
    return IntelligenceDB(str(tmp_path / "intel.db"))


def _scored():
    return {
        "github": [
            {"title": "browser-use agent ships vision policy", "signal_score": 91,
             "description": "agent browser computer use demo", "has_code": True},
        ],
        "youtube": [
            {"title": "I gave an AI agent my Mac", "signal_score": 80,
             "description": "agent demo computer use"},
        ],
        "blogs": [
            {"title": "Agentic workflows go mainstream", "signal_score": 70,
             "description": "agent autonomous workflow"},
        ],
    }


def test_snapshot_idempotent_same_hour(tmp_path):
    db = _db(tmp_path)
    base = 1000 * 3600
    ci.snapshot_clusters(_scored(), db, now_ts=base)
    ci.snapshot_clusters(_scored(), db, now_ts=base + 120)  # same hour
    history = db.read_cluster_history("AI Agents")
    # Exactly one row for that hour.
    buckets = [row[0] for row in history]
    assert buckets.count(1000) == 1


def test_snapshot_two_hours_pulse_vector(tmp_path):
    db = _db(tmp_path)
    base = 1000 * 3600
    ci.snapshot_clusters(_scored(), db, now_ts=base)
    ci.snapshot_clusters(_scored(), db, now_ts=base + 3600)
    history = db.read_cluster_history("AI Agents")
    assert len(history) == 2
    pulse = ci._pulse_24h(history, now_hour=1001)
    assert len(pulse) == 24
    assert all(0.0 <= v <= 1.0 for v in pulse)
    # The two most recent hours carry signal.
    assert pulse[-1] > 0 and pulse[-2] > 0


def test_radar_coords_deterministic(tmp_path):
    raw = [(item, "github") for item in _scored()["github"]]
    a = ci._radar_coords(raw, source_count=3)
    b = ci._radar_coords(raw, source_count=3)
    assert a == b
    assert -1.0 <= a["x"] <= 1.0 and -1.0 <= a["y"] <= 1.0


def test_clusters_carry_phase1_fields(tmp_path):
    db = _db(tmp_path)
    ci.snapshot_clusters(_scored(), db, now_ts=time.time())
    clusters = ci.build_topic_clusters(_scored(), intel_db=db)
    assert clusters
    for c in clusters:
        assert "momentum_24h_pct" in c
        assert "first_seen_hrs" in c
        assert len(c["pulse_24h"]) == 24
        assert set(c["radar_coords"]) == {"x", "y"}
        assert "slug" in c


def test_api_clusters_endpoint(client):
    resp = client.get("/api/clusters")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "clusters" in data


# ── Phase 2: agent runner + SSE ───────────────────────────────────────────

def test_agent_dispatch_and_complete(app_env):
    module = app_env["module"]
    module.agent_runner.step_delay = 0
    client = module.app.test_client()
    resp = client.post("/api/agents/dispatch",
                       json={"agent_type": "topic_researcher", "topic": "Computer Use"})
    assert resp.status_code == 200
    run_id = resp.get_json()["run_id"]
    # Wait for completion.
    for _ in range(50):
        run = module.intel_db.get_agent_run(run_id)
        if run and run["status"] == "done":
            break
        time.sleep(0.05)
    run = module.intel_db.get_agent_run(run_id)
    assert run["status"] == "done"
    logs = module.intel_db.get_agent_logs(run_id)
    assert len(logs) >= 1


def test_agent_dispatch_invalid_type(client):
    resp = client.post("/api/agents/dispatch", json={"agent_type": "nope"})
    assert resp.status_code == 400


def test_agents_snapshot_shape(client):
    data = client.get("/api/agents").get_json()
    assert "active" in data and "recent_done" in data


def test_agent_runner_concurrency_different_types(app_env):
    """Different agent types run on independent worker threads."""
    runner = app_env["module"].agent_runner
    runner.step_delay = 0
    ids = [
        runner.dispatch("topic_researcher", topic="A"),
        runner.dispatch("script_writer", topic="B"),
        runner.dispatch("cross_poster", topic="C"),
    ]
    db = app_env["module"].intel_db
    for _ in range(100):
        if all(db.get_agent_run(i)["status"] == "done" for i in ids):
            break
        time.sleep(0.05)
    assert all(db.get_agent_run(i)["status"] == "done" for i in ids)


# ── Phase 3: schedule ─────────────────────────────────────────────────────

def test_schedule_crud(client):
    created = client.post("/api/schedule",
                          json={"item_id": "p3", "day": "2026-05-26",
                                "kind": "record", "time": "10:00"})
    assert created.status_code == 201
    sid = created.get_json()["id"]

    listing = client.get("/api/schedule?start=2026-05-25&end=2026-05-31").get_json()
    assert any(row["id"] == sid for row in listing)
    assert all("item" in row for row in listing)

    assert client.post(f"/api/schedule/{sid}/complete").status_code == 200
    listing = client.get("/api/schedule?start=2026-05-25&end=2026-05-31").get_json()
    row = next(r for r in listing if r["id"] == sid)
    assert row["status"] == "done"

    assert client.delete(f"/api/schedule/{sid}").get_json()["success"] is True


def test_schedule_create_requires_fields(client):
    assert client.post("/api/schedule", json={"item_id": "p3"}).status_code == 400


# ── Phase 4: copilot ──────────────────────────────────────────────────────

def test_copilot_mocked_llm(app_env, monkeypatch):
    import llm_summary
    monkeypatch.setattr(llm_summary, "query_llm", lambda q, system_prompt=None: "Demo first.")
    monkeypatch.setattr(app_env["module"], "_load_creator_profile_safe",
                        lambda: {"copilot": {"provider": "gemini", "max_tokens": 200}})
    client = app_env["module"].app.test_client()
    resp = client.post("/api/copilot",
                       json={"view": "pulse", "context": {}, "question": "rank clusters"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["answer"] == "Demo first."
    assert "elapsed_ms" in data


def test_copilot_requires_question(client):
    assert client.post("/api/copilot", json={"view": "pulse"}).status_code == 400


def test_copilot_nvidia_provider(app_env, monkeypatch):
    """When copilot config provider=nvidia, the NIM path is used."""
    module = app_env["module"]
    import llm_summary
    captured = {}

    def fake_nvidia(prompt, system_prompt=None, model=None, max_tokens=1024, api_key=None):
        captured["model"] = model
        captured["max_tokens"] = max_tokens
        return "Coding AI wins."

    monkeypatch.setattr(llm_summary, "query_nvidia", fake_nvidia)
    monkeypatch.setattr(module, "_load_creator_profile_safe",
                        lambda: {"copilot": {"provider": "nvidia",
                                             "model": "minimaxai/minimax-m2.7",
                                             "max_tokens": 200}})
    client = module.app.test_client()
    resp = client.post("/api/copilot", json={"view": "clusters", "question": "best demo?"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["answer"] == "Coding AI wins."
    assert data["model"] == "minimaxai/minimax-m2.7"
    assert captured["model"] == "minimaxai/minimax-m2.7"
    assert captured["max_tokens"] >= 1024  # reasoning headroom


def test_query_nvidia_no_key_returns_none(monkeypatch):
    import llm_summary
    monkeypatch.setattr(llm_summary, "NVIDIA_API_KEY", "")
    assert llm_summary.query_nvidia("hi", api_key="") is None


# ── Phase 5: thumbnails ───────────────────────────────────────────────────

def test_generate_six_distinct_variants(tmp_path):
    db = _db(tmp_path)
    variants = ci.generate_thumbnail_variants(db, "hash123", topic="Computer Use", count=6)
    assert len(variants) == 6
    kinds = {v["kind"] for v in variants}
    assert len(kinds) == len(ci.THUMBNAIL_KINDS)  # all 5 kinds present
    assert all(1.0 <= v["ctr_pred"] <= 14.0 for v in variants)
    # Sorted by ctr desc.
    ctrs = [v["ctr_pred"] for v in variants]
    assert ctrs == sorted(ctrs, reverse=True)


def test_thumbnail_endpoints_and_pick(client):
    gen = client.post("/api/thumbnails/generate",
                      json={"content_hash": "hashABC", "topic": "Voice AI", "count": 6})
    assert gen.status_code == 201
    variants = client.get("/api/thumbnails/hashABC").get_json()
    assert len(variants) == 6
    vid = variants[0]["id"]
    assert client.post(f"/api/thumbnails/{vid}/pick").status_code == 200
    after = client.get("/api/thumbnails/hashABC").get_json()
    picked = [v for v in after if v["picked"]]
    assert len(picked) == 1 and picked[0]["id"] == vid
    # Edit + delete.
    assert client.put(f"/api/thumbnails/{vid}", json={"text": "NEW HOOK"}).status_code == 200
    assert client.delete(f"/api/thumbnails/{vid}").get_json()["success"] is True
