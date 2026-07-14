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

def test_agent_dispatch_and_complete(app_env, monkeypatch):
    import cli_registry
    def mock_generate(prompt, system=None, *, prefer=None, timeout=240, **kwargs):
        if "synthesis" in prompt.lower() or "Based on these research leads" in prompt or "Return a JSON object" in prompt:
            return {
                "text": '{"strategic_title": "Mock Title", "shift": "Mock Shift", "superpower": "Mock Superpower", "hook_contrarian": "Mock hook contrarian", "hook_speed": "Mock hook speed", "narrative_beats": ["Beat 1", "Beat 2", "Beat 3", "Beat 4", "Beat 5"], "thumbnail_visuals": ["Concept 1", "Concept 2", "Concept 3"], "inversion": "Mock Inversion"}',
                "provider": "mock", "model": "mock", "elapsed_ms": 1, "tried": []
            }
        return {"text": "Mock research leads", "provider": "mock", "model": "mock", "elapsed_ms": 1, "tried": []}
    monkeypatch.setattr(cli_registry, "generate", mock_generate)

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


def test_agent_runner_concurrency_different_types(app_env, monkeypatch):
    """Different agent types run on independent worker threads."""
    import cli_registry
    def mock_generate(prompt, system=None, *, prefer=None, timeout=240, **kwargs):
        if "synthesis" in prompt.lower() or "Based on these research leads" in prompt or "Return a JSON object" in prompt:
            return {
                "text": '{"strategic_title": "Mock Title", "shift": "Mock Shift", "superpower": "Mock Superpower", "hook_contrarian": "Mock hook contrarian", "hook_speed": "Mock hook speed", "narrative_beats": ["Beat 1", "Beat 2", "Beat 3", "Beat 4", "Beat 5"], "thumbnail_visuals": ["Concept 1", "Concept 2", "Concept 3"], "inversion": "Mock Inversion"}',
                "provider": "mock", "model": "mock", "elapsed_ms": 1, "tried": []
            }
        return {"text": "Mock output content", "provider": "mock", "model": "mock", "elapsed_ms": 1, "tried": []}
    monkeypatch.setattr(cli_registry, "generate", mock_generate)

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
    import cli_registry
    monkeypatch.setattr(cli_registry, "generate", lambda prompt, system=None, **kwargs: {
        "text": "Demo first.", "provider": "gemini", "model": "mock-model", "elapsed_ms": 10, "tried": []
    })
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
    monkeypatch.setattr(llm_summary, "load_creator_profile",
                        lambda *args, **kwargs: {"copilot": {"provider": "nvidia",
                                                             "model": "minimaxai/minimax-m2.7",
                                                             "max_tokens": 200}})
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


def test_ignore_topic_endpoint(client):
    resp = client.post("/api/ignore-topic", json={
        "topic": "AI Agents",
        "items": [
            {"url": "https://example.com/item1", "title": "Item 1", "source_type": "github"},
            {"url": "https://example.com/item2", "title": "Item 2", "source_type": "youtube"},
        ]
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "ignored" in data["message"]


# ── Audience feedback loop: topic performance multipliers ────────────────

def _seed_publication(db, title, views):
    slug = title.lower().replace(" ", "-")
    item_id = db.save_item({
        "title": title,
        "url": f"https://example.com/{slug}",
        "source": "GitHub Trending",
        "source_type": "github",
        "status": "published",
        "signal_score": 80,
    })
    db.create_or_update_publication(item_id, "youtube", views=views)
    return item_id


def test_topic_performance_multipliers(tmp_path):
    db = _db(tmp_path)
    # "AI Agents" videos massively outperform; "Voice AI" underperforms.
    _seed_publication(db, "My agent workflow automation video", 40000)
    _seed_publication(db, "Autonomous agent demo gone wrong", 30000)
    _seed_publication(db, "Voice AI speech assistant test", 1000)
    _seed_publication(db, "A generic tech recap video xyz", 8000)
    _seed_publication(db, "Another generic tech recap qrs", 8000)

    perf = ci.build_topic_performance(db)
    assert perf.get("AI Agents") == 1.15
    assert perf.get("Voice AI") == 0.92


def test_topic_performance_empty_without_data(tmp_path):
    db = _db(tmp_path)
    assert ci.build_topic_performance(db) == {}
    assert ci.build_topic_performance(None) == {}


def test_enrich_applies_audience_multiplier(tmp_path):
    db = _db(tmp_path)
    _seed_publication(db, "My agent workflow automation video", 40000)
    _seed_publication(db, "Autonomous agent demo gone wrong", 30000)
    _seed_publication(db, "Voice AI speech assistant test", 1000)
    _seed_publication(db, "A generic tech recap video xyz", 8000)
    _seed_publication(db, "Another generic tech recap qrs", 8000)

    enriched = ci.enrich_scored_data_with_creator_fields(_scored(), intel_db=db)
    agent_item = enriched["github"][0]
    assert agent_item["creator_topic"] == "AI Agents"
    assert agent_item["creator_score_breakdown"]["audience_multiplier"] == 1.15

    baseline = ci.enrich_scored_data_with_creator_fields(_scored(), intel_db=None)
    baseline_item = baseline["github"][0]
    assert baseline_item["creator_score_breakdown"]["audience_multiplier"] == 1.0
    assert agent_item["creator_score"] >= baseline_item["creator_score"]


# ── Today cockpit payload contracts ──────────────────────────────────────

def test_opportunities_carry_canonical_cluster_identity():
    scored = ci.enrich_scored_data_with_creator_fields(_scored())
    clusters = ci.build_topic_clusters(scored)
    opportunities = ci.build_content_opportunities(scored, clusters)

    assert opportunities
    assert len({opportunity["id"] for opportunity in opportunities}) == len(opportunities)
    for opportunity in opportunities:
        assert opportunity["id"].endswith(opportunity["content_hash"][:12])
        assert opportunity["creator_topic"] == opportunity["topic"]
        assert opportunity["slug"]
        assert opportunity["cluster_slug"] == opportunity["slug"]


def test_cockpit_payload_exposes_truthful_today_state(app_env):
    payload = app_env["module"].build_cockpit_data()

    assert payload["meta"]["last_updated"] == payload["last_updated"]
    assert payload["stats"]["avg_lead_time_days"] is None
    assert payload["stats"]["tracked_topics_count"] == 0
    assert payload["factory_queue"] == []
    assert "editorial_briefing" in payload
    assert payload["opportunities"]
    assert all(row["cluster_slug"] for row in payload["opportunities"])
    assert all(health["count_label"] in {"latest fetch", "cached snapshot", "not fetched"} for health in payload["sourceHealth"].values())
    assert all(health["delta"] is None for health in payload["sourceHealth"].values())


def test_cockpit_thumbnail_reads_use_original_content_hash(app_env):
    module = app_env["module"]
    initial = module.build_cockpit_data()
    opportunity = initial["opportunities"][0]
    ci.generate_thumbnail_variants(
        module.intel_db,
        opportunity["content_hash"],
        topic=opportunity["topic"],
        count=1,
    )

    payload = module.build_cockpit_data()
    assert any(row["content_hash"] == opportunity["content_hash"] for row in payload["thumbnails"])


def test_cockpit_thumbnail_reads_legacy_slug_key(app_env):
    module = app_env["module"]
    initial = module.build_cockpit_data()
    cluster = initial["clusters"][0]
    ci.generate_thumbnail_variants(module.intel_db, cluster["slug"], topic=cluster["topic"], count=1)

    payload = module.build_cockpit_data()
    assert any(row["content_hash"] == cluster["slug"] for row in payload["thumbnails"])


def test_cockpit_factory_queue_reports_full_approval_count(app_env):
    module = app_env["module"]
    for index in range(6):
        module.intel_db.factory_enqueue(
            topic=f"Topic {index}",
            title=f"Short {index}",
            status="pending_review",
        )

    payload = module.build_cockpit_data()
    assert len(payload["factory_queue"]) == 5
    assert payload["stats"]["approval_count"] == 6


def test_cached_editorial_briefing_expires(app_env):
    module = app_env["module"]
    path = app_env["data_dir"] / "editorial_briefing.json"
    path.write_text(json.dumps({
        "briefing": "Old plan",
        "generated_at": time.time() - 3601,
        "status": "ready",
    }), encoding="utf-8")

    assert module._load_cached_editorial_briefing() is None


def test_editorial_approval_requires_current_verified_plan(client):
    response = client.post("/api/editorial/approve")
    assert response.status_code == 409
    assert "verified editorial plan" in response.get_json()["error"]


def test_editorial_approval_rejects_changed_source_version(app_env):
    module = app_env["module"]
    payload = module.build_cockpit_data()
    cluster = payload["clusters"][0]
    path = app_env["data_dir"] / "editorial_briefing.json"
    path.write_text(json.dumps({
        "briefing": "Verified plan",
        "generated_at": time.time(),
        "status": "ready",
        "source_version": "older-version",
        "plan_items": [{
            "format": "YouTube long-form",
            "cluster_slug": cluster["slug"],
            "topic": cluster["topic"],
            "agent_types": [],
        }],
    }), encoding="utf-8")

    response = module.app.test_client().post("/api/editorial/approve")
    assert response.status_code == 409
    assert "Source data changed" in response.get_json()["error"]
