import json
from unittest.mock import MagicMock, patch

import pytest

import studio_job

def test_load_scored(tmp_path, monkeypatch):
    data_file = tmp_path / "scored.json"
    data_file.write_text(json.dumps({"test": "data"}))
    monkeypatch.setattr(studio_job, "SCORED_DATA_FILE", str(data_file))
    
    assert studio_job._load_scored() == {"test": "data"}
    
    monkeypatch.setattr(studio_job, "SCORED_DATA_FILE", str(tmp_path / "missing.json"))
    assert studio_job._load_scored() == {}

def test_base_research():
    cluster = {
        "topic": "Agents",
        "why_this_is_a_story": "Because",
        "recommended_angle": "Angle",
        "sources": ["github", "blogs"],
        "creator_score": 99,
        "average_signal_score": 50,
        "related_items": [
            {"source_type": "github", "title": "AutoGPT", "signal_score": 90, "url": "http"}
        ]
    }
    res = studio_job._base_research(cluster)
    assert "TOPIC: Agents" in res
    assert "AutoGPT" in res

@patch("agentic_researcher.recursive_dive")
@patch("cli_registry.generate")
def test_deepen(mock_generate, mock_dive, monkeypatch):
    # Agentic success
    monkeypatch.setattr(studio_job, "DEEP_RESEARCH", True)
    mock_dive.return_value = {"strategic_title": "T", "shift": "S", "superpower": "SP", "inversion": "I"}
    
    res1 = studio_job._deepen("base", "topic")
    assert "DEEP AGENTIC RESEARCH DIVE" in res1
    assert "base" in res1
    assert "T" in res1
    
    # Agentic failure, fallback to cli
    mock_dive.side_effect = Exception("Dive failed")
    mock_generate.return_value = {"text": "fallback text", "provider": "mock", "elapsed_ms": 10}
    res2 = studio_job._deepen("base", "topic")
    assert "DEEP RESEARCH (mock)" in res2
    assert "fallback text" in res2

    # DEEP_RESEARCH off
    monkeypatch.setattr(studio_job, "DEEP_RESEARCH", False)
    assert studio_job._deepen("base", "topic") == "base"

@patch("studio_job.build_topic_clusters")
@patch("studio.load_profile")
@patch("studio.generate_format")
@patch("cli_registry.available_providers")
def test_run_success(mock_avail, mock_gen_fmt, mock_profile, mock_clusters, monkeypatch):
    mock_avail.return_value = ["mock_provider"]
    mock_clusters.return_value = [{"slug": "s1", "topic": "T1"}]
    mock_profile.return_value = {}
    
    mock_gen_fmt.return_value = {"ok": True, "provider": "mock", "elapsed_ms": 100}
    
    mock_db = MagicMock()
    
    res = studio_job.run(intel_db=mock_db, top_n=1)
    
    assert res["ok"] is True
    assert res["stories"] == 1
    # Check that formats were generated
    assert mock_gen_fmt.called
    assert mock_db.studio_save_result.called

@patch("cli_registry.available_providers")
def test_run_no_providers(mock_avail):
    mock_avail.return_value = []
    res = studio_job.run(intel_db=MagicMock())
    assert res["ok"] is False
    assert res["error"] == "no_provider"

@patch("cli_registry.available_providers")
@patch("studio_job.build_topic_clusters")
def test_run_no_clusters(mock_clusters, mock_avail):
    mock_avail.return_value = ["mock"]
    mock_clusters.return_value = []
    res = studio_job.run(intel_db=MagicMock())
    assert res["ok"] is False
    assert res["error"] == "no_clusters"

@patch("studio_job.run")
def test_main(mock_run, capsys):
    assert studio_job.main() == 0
    mock_run.assert_called_once()
    
    mock_run.side_effect = Exception("Crash")
    assert studio_job.main() == 1
    assert "FAILED" in capsys.readouterr().out
