"""Tests for the autonomous news-factory orchestrator + approval queue."""

import json

import pytest

import factory as factory_mod
from data_models import IntelligenceDB


def _db(tmp_path):
    return IntelligenceDB(str(tmp_path / "intel.db"))


def _scored():
    return {
        "github": [
            {"title": "browser-use agent ships vision policy", "signal_score": 91,
             "description": "agent browser computer use demo", "url": "https://example.com/a", "has_code": True},
            {"title": "ollama local runtime update", "signal_score": 88,
             "description": "local self-hosted inference", "url": "https://example.com/b"},
        ],
        "youtube": [
            {"title": "I gave an AI agent my Mac", "signal_score": 80,
             "description": "agent demo computer use", "url": "https://example.com/c"},
        ],
        "blogs": [
            {"title": "Local llama.cpp on raspberry pi", "signal_score": 76,
             "description": "local edge inference", "url": "https://example.com/d"},
        ],
    }


def _fake_clips(item, num_clips=1, evidence=None):
    return [{
        "parent_item_id": item.get("id", 0),
        "title": f"Short: {item['title'][:40]}",
        "hook_text": "This broke production in eighteen minutes.",
        "script_text": "Full script body with technical evidence.",
        "virality_score": 90.0,
        "status": "draft",
    }]


def _fake_render(**kwargs):
    return {"success": True, "video_path": f"/videos/{kwargs['clip_id']}.mp4"}


# ── guardrails ────────────────────────────────────────────────────────────

def test_guardrails_flag_banned_and_blocked():
    profile = {"banned_phrases": ["game changer"]}
    topics = {"blocked_keywords": ["casino"]}
    violations = factory_mod.check_guardrails(
        "This GAME CHANGER casino tool", profile, topics)
    assert len(violations) == 2

    assert factory_mod.check_guardrails("clean technical text", profile, topics) == []


def test_guardrails_block_fabricated_claims():
    profile = {"banned_phrases": []}
    topics = {"blocked_keywords": []}
    fabricated = ("We ran fifty complex function calling benchmarks. "
                  "Our tests show 91 percent accuracy. Link in the bio.")
    violations = factory_mod.check_guardrails(fabricated, profile, topics)
    assert any("we ran" in v for v in violations)
    assert any("our tests" in v for v in violations)
    assert any("link in" in v for v in violations)

    honest = ("The repo README documents 6.4 tokens per second on a Pi 4. "
              "The thread hit 400 points. Source is linked below.")
    assert factory_mod.check_guardrails(honest, profile, topics) == []


# ── run_factory ───────────────────────────────────────────────────────────

def test_run_factory_queues_and_auto_approves(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 82, "block_unevidenced_renders": False}, "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    # Exercises queue/auto-approve mechanics against the taxonomy selector this
    # test was written for; story selection has its own coverage below.
    result = factory_mod.run_factory(
        db, _scored(), limit=2, use_stories=False,
        render_fn=_fake_render, generate_clips_fn=_fake_clips)

    assert len(result["queued"]) == 2
    assert not result["failed"] and not result["blocked"]
    # virality 90 >= 82 -> auto-approved
    assert all(q["status"] == "approved" for q in result["queued"])
    rows = db.factory_list()
    assert len(rows) == 2
    assert all(r["video_path"].startswith("/videos/factory-") for r in rows)


def test_run_factory_blocks_guardrail_violations(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 82, "block_unevidenced_renders": False}, "banned_phrases": ["broke production"]}
        if "profile" in p else {"blocked_keywords": []}
    ))
    result = factory_mod.run_factory(
        db, _scored(), limit=1,
        render_fn=_fake_render, generate_clips_fn=_fake_clips)

    assert len(result["blocked"]) == 1
    assert not result["queued"]
    rows = db.factory_list(status="blocked")
    assert len(rows) == 1
    assert "banned phrase" in rows[0]["error"]


def test_run_factory_skips_already_queued_topics(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 95, "block_unevidenced_renders": False}, "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    first = factory_mod.run_factory(db, _scored(), limit=1,
                                    render_fn=_fake_render, generate_clips_fn=_fake_clips)
    assert len(first["queued"]) == 1
    first_topic = first["queued"][0]["topic"]

    second = factory_mod.run_factory(db, _scored(), limit=1,
                                     render_fn=_fake_render, generate_clips_fn=_fake_clips)
    assert first_topic in second["skipped_topics"]
    assert all(q["topic"] != first_topic for q in second["queued"])


def test_run_factory_records_render_failure(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 95, "block_unevidenced_renders": False}, "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))

    def broken_render(**kwargs):
        return {"error": "ffmpeg exploded"}

    result = factory_mod.run_factory(db, _scored(), limit=1,
                                     render_fn=broken_render, generate_clips_fn=_fake_clips)
    assert len(result["failed"]) == 1
    rows = db.factory_list(status="render_failed")
    assert len(rows) == 1 and "ffmpeg exploded" in rows[0]["error"]


def test_run_factory_passes_evidence_to_clip_generator(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 95}, "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    seen = {}

    def spy_clips(item, num_clips=1, evidence=None):
        seen["evidence"] = evidence
        return _fake_clips(item, num_clips)

    fake_evidence = {"url": "https://example.com/a", "source_kind": "github",
                     "facts": ["1200 GitHub stars"], "quotes": [], "excerpt": "Real README text."}
    result = factory_mod.run_factory(
        db, _scored(), limit=1,
        render_fn=_fake_render, generate_clips_fn=spy_clips,
        gather_evidence_fn=lambda item: fake_evidence)
    assert len(result["queued"]) == 1
    assert seen["evidence"] == fake_evidence


def test_run_factory_targets_selected_cluster(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 95}, "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    from creator_intelligence import build_topic_clusters
    clusters = build_topic_clusters(_scored(), intel_db=db)
    selected = clusters[-1]
    result = factory_mod.run_factory(
        db, _scored(), limit=1, cluster_slug=selected["slug"], use_stories=False,
        render_fn=_fake_render, generate_clips_fn=_fake_clips,
        gather_evidence_fn=lambda item: {"facts": ["source fact"], "url": item["url"]},
    )
    assert result["queued"][0]["topic"] == selected["topic"]


def test_run_factory_defaults_to_story_topics(tmp_path, monkeypatch):
    """The default run must name a video after an event, not a category."""
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 95, "block_unevidenced_renders": False},
         "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    result = factory_mod.run_factory(
        db, _scored(), limit=2,
        render_fn=_fake_render, generate_clips_fn=_fake_clips)

    topics = [q["topic"] for q in result["queued"]]
    assert topics, "story selection produced no candidates"
    for label in ("AI Agents", "Local AI", "Coding AI", "AI Tools", "General"):
        assert label not in topics


def test_run_factory_falls_back_to_clusters_without_stories(tmp_path, monkeypatch):
    """Titles too vague to anchor must not leave the factory with nothing."""
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 95, "block_unevidenced_renders": False},
         "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    vague = {
        "github": [{"title": "we are so back", "signal_score": 90,
                    "description": "agent demo", "url": "https://example.com/x",
                    "has_code": True}],
        "youtube": [{"title": "it is over", "signal_score": 88,
                     "description": "agent demo", "url": "https://example.com/y"}],
    }
    result = factory_mod.run_factory(
        db, vague, limit=1,
        render_fn=_fake_render, generate_clips_fn=_fake_clips)

    assert not result["failed"]


def test_run_factory_blocks_missing_evidence_when_configured(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 95, "block_unevidenced_renders": True}, "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    result = factory_mod.run_factory(
        db, _scored(), limit=1, render_fn=_fake_render,
        generate_clips_fn=_fake_clips, gather_evidence_fn=lambda item: None,
    )
    assert result["blocked"]
    assert not result["queued"]


def test_run_factory_blocks_empty_evidence_object(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"block_unevidenced_renders": True}, "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    empty = {"url": "", "source_kind": "", "facts": [], "quotes": [], "excerpt": ""}
    result = factory_mod.run_factory(
        db, _scored(), limit=1, render_fn=_fake_render,
        generate_clips_fn=_fake_clips, gather_evidence_fn=lambda item: empty,
    )
    assert len(result["blocked"]) == 1


def test_factory_job_queue_is_durable(tmp_path):
    db = _db(tmp_path)
    snapshot = {"last_updated": "snapshot", "github": [{"title": "selected"}]}
    db.factory_job_enqueue("job-1", "selected-story", scored_data=snapshot)
    assert db.factory_job_payload("job-1") == snapshot
    claimed = db.factory_job_claim()
    assert claimed["id"] == "job-1"
    assert claimed["status"] == "running"
    db.factory_job_finish("job-1", result={"queued": [{"id": 1}]})
    finished = db.factory_job_get("job-1")
    assert finished["status"] == "succeeded"
    assert finished["result"]["queued"][0]["id"] == 1


def test_factory_job_recovery_fails_exhausted_attempt(tmp_path):
    db = _db(tmp_path)
    db.factory_job_enqueue("job-3", "selected-story")
    assert db.factory_job_claim()["attempts"] == 1
    db.factory_job_retry("job-3", "first failure")
    assert db.factory_job_claim()["attempts"] == 2
    db.factory_job_retry("job-3", "second failure")
    assert db.factory_job_claim()["attempts"] == 3
    db.factory_jobs_requeue_running()
    recovered = db.factory_job_get("job-3")
    assert recovered["status"] == "failed"
    assert "final attempt" in recovered["error"]


def test_signal_demo_uses_observed_context_only():
    import video_renderer as vr
    demo = vr._signal_demo_content({
        "average_signal_score": 73.5, "source_count": 3,
        "sources": ["github", "hackernews", "youtube"],
    })
    assert demo[2:] == ("DailyDex Signal Score", 73.5, "/ 100")
    assert "3 source families" in " ".join(demo[1])


# ── queue state machine (DB level) ───────────────────────────────────────

def test_factory_queue_transitions(tmp_path):
    db = _db(tmp_path)
    row_id = db.factory_enqueue("AI Agents", "Test short", hook="h", script="s",
                                video_path="/v.mp4", virality_score=70)
    row = db.factory_get(row_id)
    assert row["status"] == "pending_review"

    assert db.factory_update_status(row_id, "approved")
    assert db.factory_get(row_id)["status"] == "approved"

    assert db.factory_update_status(row_id, "published", published_url="https://youtu.be/x")
    row = db.factory_get(row_id)
    assert row["status"] == "published"
    assert row["published_url"] == "https://youtu.be/x"

    assert db.factory_active_topics() == ["AI Agents"]
    assert not db.factory_update_status(99999, "approved")


# ── routes ────────────────────────────────────────────────────────────────

def test_factory_routes(client, app_env):
    module = app_env["module"]
    db = module.intel_db

    row_id = db.factory_enqueue("Local AI", "Pi cluster short", hook="hook",
                                script="script", video_path="/videos/x.mp4",
                                virality_score=75)

    queue = client.get("/api/factory/queue").get_json()
    assert any(item["id"] == row_id for item in queue["items"])

    # publish before approval must fail
    resp = client.post(f"/api/factory/{row_id}/publish")
    assert resp.status_code == 400

    resp = client.post(f"/api/factory/{row_id}/approve")
    assert resp.status_code == 200
    assert db.factory_get(row_id)["status"] == "approved"

    # double-approve rejected by state machine
    assert client.post(f"/api/factory/{row_id}/approve").status_code == 400

    resp = client.post(f"/api/factory/{row_id}/reject")
    assert resp.status_code == 200
    assert db.factory_get(row_id)["status"] == "rejected"

    assert client.post("/api/factory/99999/approve").status_code == 404


def test_factory_publish_without_oauth_fails_cleanly(client, app_env):
    db = app_env["module"].intel_db
    row_id = db.factory_enqueue("AI Tools", "Tool short", video_path="/videos/y.mp4")
    db.factory_update_status(row_id, "approved")

    resp = client.post(f"/api/factory/{row_id}/publish")
    # No Google OAuth configured in test env -> 400 with clear error
    assert resp.status_code == 400
    assert "OAuth" in resp.get_json()["error"] or "token" in resp.get_json()["error"].lower()


# ── source attribution ────────────────────────────────────────────────────

def test_factory_row_round_trips_source_urls(tmp_path):
    db = _db(tmp_path)
    row_id = db.factory_enqueue("AI Agents", "Short", source_urls=[
        "https://github.com/org/repo", "https://news.ycombinator.com/item?id=1"])

    row = db.factory_get(row_id)
    assert row["source_urls"] == [
        "https://github.com/org/repo", "https://news.ycombinator.com/item?id=1"]
    assert db.factory_list()[0]["source_urls"] == row["source_urls"]


def test_factory_row_without_sources_reads_as_empty_list(tmp_path):
    db = _db(tmp_path)
    row_id = db.factory_enqueue("AI Agents", "Short")
    assert db.factory_get(row_id)["source_urls"] == []


def test_source_urls_column_is_added_to_an_existing_database(tmp_path):
    """A pre-existing factory_queue must gain the column, not error."""
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE factory_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            title TEXT NOT NULL,
            hook TEXT DEFAULT '',
            script TEXT DEFAULT '',
            video_path TEXT DEFAULT '',
            virality_score REAL DEFAULT 0,
            status TEXT DEFAULT 'pending_review',
            error TEXT DEFAULT '',
            published_url TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO factory_queue (topic, title) VALUES ('Old', 'Pre-existing row')")
    conn.commit()
    conn.close()

    db = IntelligenceDB(str(db_path))
    rows = db.factory_list()
    assert any(r["title"] == "Pre-existing row" for r in rows)
    assert all(r["source_urls"] == [] for r in rows)
    # And the migrated table accepts new writes.
    new_id = db.factory_enqueue("New", "Fresh row", source_urls=["https://example.com/a"])
    assert db.factory_get(new_id)["source_urls"] == ["https://example.com/a"]


def test_run_factory_records_the_sources_it_grounded_in(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(factory_mod, "_load_json", lambda p: (
        {"automation": {"auto_forge_score": 95, "block_unevidenced_renders": False},
         "banned_phrases": []}
        if "profile" in p else {"blocked_keywords": []}
    ))
    result = factory_mod.run_factory(
        db, _scored(), limit=1,
        render_fn=_fake_render, generate_clips_fn=_fake_clips)

    assert result["queued"], "no rows queued"
    row = db.factory_get(result["queued"][0]["id"])
    assert row["source_urls"], "queued row carries no source attribution"
    assert all(u.startswith("http") for u in row["source_urls"])


def test_cluster_source_urls_dedupes_and_filters(tmp_path):
    urls = factory_mod._cluster_source_urls(
        {"related_items": [
            {"url": "https://example.com/a"},
            {"url": "https://example.com/a"},
            {"url": "dailydex://internal"},
            {"url": ""},
            {"url": "https://example.com/b"},
        ]},
        lead={"url": "https://example.com/lead"},
    )
    assert urls[0] == "https://example.com/lead"
    assert urls == ["https://example.com/lead", "https://example.com/a", "https://example.com/b"]


# ── evidence → video demo card ────────────────────────────────────────────

def test_demo_from_evidence_github():
    import video_renderer as vr
    ev = {
        "url": "https://github.com/acme/tool",
        "source_kind": "github",
        "facts": ["Repo description: An agent harness", "228236 GitHub stars", "Primary language: TypeScript"],
        "quotes": [],
        "excerpt": "Install with npm install ecc-universal and enjoy. 32k+ forks",
    }
    cmd, logs, label, val, unit = vr._demo_from_evidence(ev)
    assert cmd.startswith("npm install ecc-universal")
    assert any("228236 GitHub stars" in l or "228236" in l for l in logs)
    assert label == "GitHub Stars (live API)"
    assert (val, unit) == (228.236, "K stars")


def test_demo_from_evidence_hn_and_empty():
    import video_renderer as vr
    ev = {
        "url": "https://news.ycombinator.com/item?id=123",
        "source_kind": "hackernews",
        "facts": ["2346 points on Hacker News", "176 top-level comments"],
        "quotes": ["Real commenter text here that is long enough to matter."],
        "excerpt": "",
    }
    cmd, logs, label, val, unit = vr._demo_from_evidence(ev)
    assert "curl hn.algolia.com/api/v1/items/123" == cmd
    assert label == "Hacker News Points (live)"
    assert val == 2346.0 and unit == "points"
    assert any(l.startswith("[REPLY]") for l in logs)

    assert vr._demo_from_evidence({"facts": [], "quotes": [], "excerpt": "", "source_kind": "", "url": ""}) is None
