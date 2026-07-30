"""Live research compile stream and cache tests."""

import json
from copy import deepcopy

import data_models
import compile_engine
import routes.api_compile as compile_route
from compile_engine import (
    _gather_one, build_compile_prompts, is_grounded_record, parse_compile_result,
    source_version,
)


def _events(response):
    events = []
    for frame in response.get_data(as_text=True).split("\n\n"):
        for line in frame.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def _valid_result():
    return {
        "story_title": "The agent workflow developers can finally inspect",
        "story_title_evidence_ids": ["E1"],
        "editorial_thesis": "The useful story is not another agent launch. It is that builders can now inspect the workflow before trusting it.",
        "editorial_thesis_evidence_ids": ["E1"],
        "audience_payoff": "Builders learn how to verify an agent workflow before adopting it.",
        "audience_payoff_evidence_ids": ["E1"],
        "hook": "The interesting part of this agent is not what it automates.",
        "hook_evidence_ids": ["E1"],
        "angles": [
            {"name": "Inspectability", "take": "Show the observable workflow.", "evidence_ids": ["E1"]},
            {"name": "Local test", "take": "Test the smallest useful path.", "evidence_ids": ["E1"]},
            {"name": "Trade-off", "take": "Contrast speed with control.", "evidence_ids": ["E1"]},
        ],
        "recommended_format": "Technical demo",
        "format_reason": "The source describes a workflow that can be shown directly.",
        "format_reason_evidence_ids": ["E1"],
        "demo_idea": "Open the repository and trace one agent run from input to tool call.",
        "demo_evidence_ids": ["E1"],
        "titles": [
            "The AI agent workflow you can actually inspect",
            "Before you trust an AI agent, inspect this",
            "A practical test for inspectable AI agents",
        ],
        "titles_evidence_ids": ["E1"],
        "key_facts": [
            {"claim": "The source describes an agent workflow.", "evidence_ids": ["E1"]},
            {"claim": "The implementation is available in a repository.", "evidence_ids": ["E1"]},
            {"claim": "The signal is relevant to developers.", "evidence_ids": ["E1"]},
        ],
        "caveats": ["Performance was not independently benchmarked."],
        "caveats_evidence_ids": ["E1"],
    }


def test_compile_streams_grounded_result_and_replays_cache(client, app_env, monkeypatch):
    cluster = client.get("/api/cockpit-data").get_json()["clusters"][0]
    evidence_calls = []
    llm_calls = []

    def fake_evidence(selected, scored):
        evidence_calls.append(selected["slug"])
        yield {
            "id": "E1", "title": "Source repo", "url": "https://example.com/repo",
            "source_type": "github", "facts": ["Repository describes an agent workflow"],
            "quotes": [], "excerpt": "The workflow exposes each tool call.", "signal_score": 88,
        }

    raw = json.dumps(_valid_result())

    def fake_llm(prompt, system, profile):
        llm_calls.append(prompt)
        for token in (raw[:80], raw[80:]):
            yield {"token": token, "model": "test:model"}

    monkeypatch.setattr(compile_route, "iter_cluster_evidence", fake_evidence)
    monkeypatch.setattr(compile_route, "stream_llm_tokens", fake_llm)

    first = client.post("/api/compile", json={"cluster_slug": cluster["slug"]})
    assert first.status_code == 200
    assert first.mimetype == "text/event-stream"
    first_events = _events(first)
    assert [event["type"] for event in first_events][-2:] == ["result", "done"]
    assert any(event["type"] == "token" for event in first_events)
    result_event = next(event for event in first_events if event["type"] == "result")
    assert result_event["cache_hit"] is False
    assert result_event["result"]["editorial_thesis"].startswith("The useful story")

    second = client.post("/api/compile", json={"cluster_slug": cluster["slug"]})
    second_events = _events(second)
    cached_result = next(event for event in second_events if event["type"] == "result")
    assert cached_result["cache_hit"] is True
    assert len(evidence_calls) == 1
    assert len(llm_calls) == 1


def test_compile_instruction_gets_independent_cache_entry(client, app_env, monkeypatch):
    cluster = client.get("/api/cockpit-data").get_json()["clusters"][0]
    monkeypatch.setattr(compile_route, "iter_cluster_evidence", lambda cluster, scored: iter([{
        "id": "E1", "title": "Source", "url": "https://example.com",
        "source_type": "article", "facts": ["Supported fact"], "quotes": [],
        "excerpt": "Evidence text", "signal_score": 70,
    }]))
    calls = []
    raw = json.dumps(_valid_result())

    def fake_llm(prompt, system, profile):
        calls.append(prompt)
        yield {"token": raw, "model": "test:model"}

    monkeypatch.setattr(compile_route, "stream_llm_tokens", fake_llm)
    for instruction in ("Focus on developer trust", "Focus on cost"):
        response = client.post("/api/compile", json={
            "cluster_slug": cluster["slug"], "instruction": instruction,
        })
        assert next(event for event in _events(response) if event["type"] == "result")["cache_hit"] is False
    assert len(calls) == 2


def test_compile_blocks_empty_evidence(client, app_env, monkeypatch):
    cluster = client.get("/api/cockpit-data").get_json()["clusters"][0]
    monkeypatch.setattr(compile_route, "iter_cluster_evidence", lambda cluster, scored: iter([{
        "id": "E1", "title": "Unavailable", "url": "", "source_type": "article",
        "facts": [], "quotes": [], "excerpt": "", "signal_score": 0,
    }]))
    monkeypatch.setattr(
        compile_route, "stream_llm_tokens",
        lambda *args: (_ for _ in ()).throw(AssertionError("LLM must not run")),
    )
    response = client.post("/api/compile", json={"cluster_slug": cluster["slug"]})
    events = _events(response)
    assert any(event.get("code") == "evidence_unavailable" for event in events)
    assert events[-1]["type"] == "done"


def test_compile_rejects_unknown_cluster(client, app_env):
    response = client.post("/api/compile", json={"cluster_slug": "does-not-exist"})
    assert response.status_code == 404
    assert response.get_json()["error"] == "unknown_cluster"


def test_compile_validator_rejects_render_unsafe_values_and_failed_citations():
    unsafe = _valid_result()
    unsafe["titles"][0] = {"text": "React cannot render this object"}
    result, issues = parse_compile_result(json.dumps(unsafe), ["E1"])
    assert result is None
    assert "titles entries must be non-empty strings" in issues

    failed_citation = _valid_result()
    failed_citation["editorial_thesis_evidence_ids"] = ["E2"]
    result, issues = parse_compile_result(json.dumps(failed_citation), ["E1"])
    assert result is None
    assert "editorial_thesis_evidence_ids cites unknown evidence" in issues


def test_compile_prompt_excludes_failed_evidence_records():
    profile = {"channel_name": "Test creator"}
    cluster = {"topic": "Inspectable agents", "sources": ["github"]}
    records = [
        {
            "id": "E1", "title": "Grounded", "url": "https://example.com/one",
            "source_type": "github", "facts": ["A fact"], "quotes": [], "excerpt": "",
        },
        {
            "id": "E2", "title": "Failed private source", "url": "http://127.0.0.1/private",
            "source_type": "article", "facts": [], "quotes": [], "excerpt": "", "error": "blocked",
        },
    ]
    _, prompt = build_compile_prompts(profile, cluster, records, "Check the claim")
    assert '"id": "E1"' in prompt
    assert '"id": "E2"' not in prompt
    assert "Failed private source" not in prompt


def test_failed_fetch_does_not_promote_feed_description_to_evidence(monkeypatch):
    monkeypatch.setattr(
        "compile_engine.evidence_fetcher.gather_evidence",
        lambda item: {
            "url": "", "source_kind": "", "facts": [], "quotes": [], "excerpt": "",
            "error": "Private or reserved evidence hosts are not allowed",
        },
    )
    record = _gather_one(0, {
        "title": "Untrusted signal", "url": "http://127.0.0.1/private",
        "source_type": "blogs", "description": "A feed-supplied claim that was never fetched",
    })
    assert record["excerpt"] == ""
    assert record["error"]
    assert is_grounded_record(record) is False


def test_compile_cache_is_invalidated_when_sources_change(client, app_env, monkeypatch):
    cluster = client.get("/api/cockpit-data").get_json()["clusters"][0]
    versions = iter(["source-v1", "source-v2"])
    monkeypatch.setattr(compile_route, "source_version", lambda scored, selected: next(versions))
    monkeypatch.setattr(compile_route, "iter_cluster_evidence", lambda selected, scored: iter([{
        "id": "E1", "title": "Source", "url": "https://example.com",
        "source_type": "article", "facts": ["Supported fact"], "quotes": [],
        "excerpt": "Evidence text", "signal_score": 70,
    }]))
    calls = []
    raw = json.dumps(_valid_result())

    def fake_llm(prompt, system, profile):
        calls.append(prompt)
        yield {"token": raw, "model": "test:model"}

    monkeypatch.setattr(compile_route, "stream_llm_tokens", fake_llm)
    first = _events(client.post("/api/compile", json={"cluster_slug": cluster["slug"]}))
    second = _events(client.post("/api/compile", json={"cluster_slug": cluster["slug"]}))
    assert next(event for event in first if event["type"] == "result")["cache_hit"] is False
    assert next(event for event in second if event["type"] == "result")["cache_hit"] is False
    assert len(calls) == 2


def test_compile_lease_can_only_be_released_by_its_owner(client):
    db = client.application.config["INTEL_DB"]
    assert db.compile_lock_acquire("story:key", "owner-one") is True
    db.compile_lock_release("story:key", "owner-two")
    assert db.compile_lock_acquire("story:key", "owner-two") is False
    assert db.compile_lock_refresh("story:key", "owner-two") is False
    db.compile_lock_release("story:key", "owner-one")
    assert db.compile_lock_acquire("story:key", "owner-two") is True
    assert db.compile_cache_set_if_lock_owner(
        "story", "hash", "instruction", "source", [], {}, "test:model", 4,
        "story:key", "owner-one",
    ) is False
    assert db.compile_cache_set_if_lock_owner(
        "story", "hash", "instruction", "source", [], {}, "test:model", 4,
        "story:key", "owner-two",
    ) is True
    db.compile_lock_release("story:key", "owner-two")


def test_compile_attempt_limit_counts_atomically(client):
    db = client.application.config["INTEL_DB"]
    assert db.compile_attempt_allow(2) is True
    assert db.compile_attempt_allow(2) is True
    assert db.compile_attempt_allow(2) is False


def test_compile_rate_cleanup_does_not_delete_newer_bucket(client, monkeypatch):
    db = client.application.config["INTEL_DB"]
    monkeypatch.setattr(data_models.time, "time", lambda: 7201)
    assert db.compile_attempt_allow(1) is True
    monkeypatch.setattr(data_models.time, "time", lambda: 3599)
    assert db.compile_attempt_allow(1) is True
    monkeypatch.setattr(data_models.time, "time", lambda: 7201)
    assert db.compile_attempt_allow(1) is False


def test_source_version_tracks_prompt_metrics_and_source_content():
    scored = {
        "last_updated": "2026-07-17T10:00:00Z",
        "github": [{
            "source_type": "github", "title": "acme/repo", "url": "https://github.com/acme/repo",
            "description": "First description", "signal_score": 80,
        }],
    }
    cluster = {
        "slug": "acme-repo", "topic": "Acme repo", "sources": ["github"],
        "average_signal_score": 80, "creator_score": 75, "momentum_24h_pct": 10,
        "related_items": [{
            "source_type": "github", "title": "acme/repo", "url": "https://github.com/acme/repo",
        }],
    }
    baseline = source_version(scored, cluster)
    changed_metric = deepcopy(cluster)
    changed_metric["creator_score"] = 90
    assert source_version(scored, changed_metric) != baseline
    changed_source = deepcopy(scored)
    changed_source["github"][0]["description"] = "Materially updated description"
    assert source_version(changed_source, cluster) != baseline
    changed_engagement = deepcopy(scored)
    changed_engagement["github"][0]["comments"] = 42
    assert source_version(changed_engagement, cluster) != baseline


def test_nvidia_compile_uses_structured_output_model(monkeypatch):
    selected_models = []

    def fake_stream(prompt, system, provider, model):
        selected_models.append(model)
        yield '{"status":"ok"}'

    monkeypatch.delenv("COMPILE_MODEL", raising=False)
    monkeypatch.setattr(compile_engine, "_openai_stream", fake_stream)
    chunks = list(compile_engine.stream_llm_tokens(
        "prompt", "system",
        {"copilot": {"provider": "nvidia", "model": "stepfun-ai/step-3.5-flash"}},
    ))
    assert selected_models == ["meta/llama-3.3-70b-instruct"]
    assert chunks[0]["token"] == '{"status":"ok"}'
