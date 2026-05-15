"""Tests for the creator enrichment pipeline + agentic cluster runner.

These exercise the orchestration without touching the Gemini CLI: the
``llm_summary.query_llm`` helper is monkey-patched to return canned JSON so
each test runs in well under a second.
"""

from __future__ import annotations

import json
import time

import pytest


CANNED_PACK = {
    "hook": "Does it actually run on a Pi 4 without melting the SD card?",
    "intro_context": "Quick context for why this matters today.",
    "three_key_points": ["benchmark", "trade-off", "what to test"],
    "three_beat_structure": ["hook", "payoff", "cta"],
    "demo_segment": "Clone, run, measure.",
    "caveats": "Alpha quality; expect rough edges.",
    "closing_takeaway": "Worth testing locally tonight.",
    "call_to_action": "Star the repo if it works for you.",
    "short_script": "Today we test the smallest agent that can plan a route. Here is what changed and what broke. Try it tonight.",
    "visual_idea": "Split screen: terminal vs. live result.",
    "cta": "Star the repo.",
    "suggested_titles": {
        "curiosity": "The agent that fits inside a Raspberry Pi 4 budget",
        "practical": "Smallest local agent worth testing on a Pi 4 tonight",
        "contrarian": "Why this tiny agent beats the bloated competition",
        "tutorial": "How to ship a local agent on a Pi 4 in one evening",
    },
    "thumbnail_text": ["PI READY", "REAL DEMO", "NO HYPE"],
    "broll_list": ["terminal output", "pi 4 board shot", "latency chart"],
    "on_screen_cues": ["1.2GB RAM", "8 tok/s", "ship it"],
    "insight": "Lean models are catching up where it counts.",
    "hooks": ["Tiny model, real demo.", "It fits on a Pi.", "Stop waiting for GPT-5."],
    "tags": ["agents", "local-ai", "pi"],
}

CANNED_DIVE = {
    "strategic_title": "Smallest local agent worth testing on a Pi 4 tonight",
    "shift": "Lean models close the gap on edge hardware.",
    "superpower": "Latency stays under 1s without a GPU.",
    "hook_contrarian": "You do not need a 70B model to ship a useful agent.",
    "hook_speed": "Five minutes from clone to working demo.",
    "narrative_beats": ["state of edge AI", "the model", "the benchmark", "the demo", "the trap"],
    "thumbnail_visuals": ["pi 4 board", "latency dial", "before/after"],
    "inversion": "Memory pressure under load is the real failure mode.",
}


def _fake_query_llm_factory():
    """Returns a fake query_llm that switches output based on the system prompt."""

    def fake(prompt, system_prompt=None):
        text = (system_prompt or "") + (prompt or "")
        if "production team" in text.lower() or "Forge the production assets" in text:
            return json.dumps({
                "shorts_script": "[Visual] Pi 4 boots. [Audio] We test the agent.",
                "podcast_script": "Host A: We tried it. Host B: Here is what broke.",
                "linkedin_post": "We tested a small local agent. Here is what we learned.",
                "blog_outline": "## What it does\n## How it works\n## Where it fails",
                "demo_guide": "1. Clone repo. 2. Run script. 3. Verify output.",
            })
        if "JSON object with these exact keys" in text and "strategic_title" in text:
            return json.dumps(CANNED_DIVE)
        if "creator pack JSON now" in text or "JSON object with these exact keys" in text:
            return json.dumps(CANNED_PACK)
        # Leads stage: a freeform string is fine.
        return "Leads: framework=foo, risk=memory, demo=run-on-pi."

    return fake


@pytest.fixture
def stub_llm(monkeypatch):
    import llm_summary
    monkeypatch.setattr(llm_summary, "query_llm", _fake_query_llm_factory())
    return llm_summary


def _wait_until(predicate, timeout=4.0, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_creator_pack_round_trip_through_db(stub_llm, tmp_path):
    from data_models import IntelligenceDB
    from creator_enricher import EnrichmentService, content_hash

    db = IntelligenceDB(str(tmp_path / "test.db"))
    service = EnrichmentService(db)
    service.start()
    try:
        item = {
            "url": "https://example.com/repo",
            "title": "Tiny agent for Pi",
            "description": "An agent that runs on a Raspberry Pi 4.",
            "source_type": "github",
            "signal_score": 88,
        }
        result = service.enqueue(item)
        assert result["queued"] is True

        hash_ = content_hash(item)
        ok = _wait_until(
            lambda: (db.get_creator_asset(hash_) or {}).get("status") in {"ready", "ready_with_warnings"},
            timeout=5,
        )
        assert ok, "enrichment never reached ready state"

        cached = db.get_creator_asset(hash_)
        assert cached["status"] in {"ready", "ready_with_warnings"}
        assert cached["payload"]["hook"].startswith("Does it actually run")
        assert cached["payload"]["thumbnail_text"][0] == "PI READY"
    finally:
        service.stop()


def test_cluster_pipeline_promotes_and_gates_forge(stub_llm, tmp_path):
    from data_models import IntelligenceDB
    from creator_enricher import EnrichmentService, content_hash

    db = IntelligenceDB(str(tmp_path / "test.db"))
    service = EnrichmentService(db)
    # Pre-seed the cache so the pipeline does not wait on the worker thread.
    seed = {
        "url": "https://example.com/agent",
        "title": "Tiny agent for Pi",
        "description": "Runs on Pi 4.",
        "source_type": "github",
        "signal_score": 90,
    }
    db.upsert_creator_asset(content_hash(seed), CANNED_PACK, model="test", status="ready")

    cluster = {
        "topic": "Local Agents",
        "source_count": 3,
        "sources": ["github", "papers", "blogs"],
        "creator_score": 92,
        "best_content_format": "Tutorial",
        "related_items": [
            {"url": seed["url"], "title": seed["title"], "source_type": "github", "source_label": "GitHub"},
        ],
    }
    automation = {
        "min_cluster_sources": 3,
        "auto_research_cluster_score": 75,
        "auto_script_ready_score": 85,
        "auto_forge_score": 999,  # gate: forge should NOT fire
        "max_auto_promotions_per_day": 3,
        "enrichment_wait_seconds": 5,
    }

    from agentic_researcher import recursive_dive
    result = service.run_cluster_pipeline(
        clusters=[cluster],
        scored_data={"github": [seed]},
        automation=automation,
        recursive_dive_fn=recursive_dive,
    )
    assert result["ok"]
    assert len(result["promoted"]) == 1
    promo = result["promoted"][0]
    assert promo["status"] == "script_ready"
    assert "forge" not in promo

    saved = db.get_saved_items(pipeline_type="creator")
    assert len(saved) == 1
    assert saved[0]["working_title"] == CANNED_PACK["suggested_titles"]["practical"]


def test_cluster_pipeline_auto_forges_above_threshold(stub_llm, tmp_path):
    from data_models import IntelligenceDB
    from creator_enricher import EnrichmentService, content_hash

    db = IntelligenceDB(str(tmp_path / "test.db"))
    service = EnrichmentService(db)
    seed = {
        "url": "https://example.com/super",
        "title": "Super agent",
        "description": "Edge agent.",
        "source_type": "github",
        "signal_score": 95,
    }
    db.upsert_creator_asset(content_hash(seed), CANNED_PACK, model="test", status="ready")
    cluster = {
        "topic": "Edge AI",
        "source_count": 3,
        "sources": ["github", "papers", "blogs"],
        "creator_score": 95,
        "best_content_format": "Tutorial",
        "related_items": [
            {"url": seed["url"], "title": seed["title"], "source_type": "github", "source_label": "GitHub"},
        ],
    }
    automation = {
        "min_cluster_sources": 3,
        "auto_research_cluster_score": 75,
        "auto_script_ready_score": 85,
        "auto_forge_score": 90,  # gate: forge SHOULD fire
        "max_auto_promotions_per_day": 3,
        "enrichment_wait_seconds": 5,
    }
    from agentic_researcher import recursive_dive
    result = service.run_cluster_pipeline(
        clusters=[cluster],
        scored_data={"github": [seed]},
        automation=automation,
        recursive_dive_fn=recursive_dive,
    )
    promo = result["promoted"][0]
    assert promo["forge"] in {"queued", "started"} or "forge" in promo

    saved_id = promo["saved_id"]
    ok = _wait_until(
        lambda: (db.get_saved_item(saved_id) or {}).get("production_status") == "ready",
        timeout=5,
    )
    assert ok, "production assets never marked ready"
    saved = db.get_saved_item(saved_id)
    assets = saved.get("production_assets")
    if isinstance(assets, str):
        assets = json.loads(assets)
    assert "shorts_script" in assets
    assert "Pi 4" in assets["shorts_script"]


def test_agentic_run_route_kicks_off_pipeline(stub_llm, creator_client, monkeypatch):
    response = creator_client.post("/api/agentic-run", json={"automation": {"max_auto_promotions_per_day": 1}})
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["automation"]["max_auto_promotions_per_day"] == 1


def test_enrich_status_route_reports_provider(stub_llm, creator_client):
    response = creator_client.get("/api/enrich-status")
    assert response.status_code == 200
    body = response.get_json()
    assert body["enabled"] is True
    assert "provider" in body
    assert "cache_counts" in body
