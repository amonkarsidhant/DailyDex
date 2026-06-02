import json
import os
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from creator_lab import bp, _AB_SCHEDULE

@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(bp)
    app.testing = True
    return app.test_client()

@patch("cli_registry.generate")
def test_title_tournament(mock_generate, client):
    mock_generate.return_value = {"text": '{"results":[{"title":"Test Title","overall":90}]}'}
    res = client.post("/api/lab/title-tournament", json={"titles": ["Title 1"], "topic": "AI"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["winner"]["title"] == "Test Title"

    res_err = client.post("/api/lab/title-tournament", json={})
    assert res_err.status_code == 400

@patch("cli_registry.generate")
def test_retention_sim(mock_generate, client):
    mock_generate.return_value = {"text": '{"retention_score":85}'}
    res = client.post("/api/lab/retention-sim", json={"script": "Hey guys welcome back"})
    assert res.status_code == 200
    assert res.get_json()["retention_score"] == 85

    assert client.post("/api/lab/retention-sim", json={}).status_code == 400

@patch("cli_registry.generate")
def test_cpm_safety(mock_generate, client):
    mock_generate.return_value = {"text": '{"cpm_tier":"high"}'}
    res = client.post("/api/lab/cpm-safety", json={"script": "finance stuff"})
    assert res.status_code == 200
    assert res.get_json()["cpm_tier"] == "high"

    assert client.post("/api/lab/cpm-safety", json={}).status_code == 400

@patch("cli_registry.generate")
def test_virality_forecast(mock_generate, client):
    mock_generate.return_value = {"text": '{"confidence":99}'}
    res = client.post("/api/lab/virality-forecast", json={"topic": "AGI soon"})
    assert res.status_code == 200
    assert res.get_json()["confidence"] == 99

    assert client.post("/api/lab/virality-forecast", json={}).status_code == 400

@patch("cli_registry.generate")
def test_thumb_ctr(mock_generate, client):
    mock_generate.return_value = {"text": '{"results":[{"id":"t1","overall":90}]}'}
    res = client.post("/api/lab/thumb-ctr", json={"thumbs": [{"id": "t1", "caption": "woah"}]})
    assert res.status_code == 200
    assert res.get_json()["ranked"][0]["id"] == "t1"

    assert client.post("/api/lab/thumb-ctr", json={}).status_code == 400

@patch("cli_registry.generate")
def test_longform_to_shorts(mock_generate, client):
    mock_generate.return_value = {"text": '{"clips":[{"hook_score":100}]}'}
    # With string transcript
    res = client.post("/api/lab/longform-to-shorts", json={"transcript": "Hello. World."})
    assert res.status_code == 200
    assert len(res.get_json()["clips"]) == 1

    # With list transcript
    res2 = client.post("/api/lab/longform-to-shorts", json={"transcript": [{"text": "Hello", "start": 0, "end": 1}]})
    assert res2.status_code == 200

    assert client.post("/api/lab/longform-to-shorts", json={}).status_code == 400

@patch("urllib.request.urlopen")
def test_competitor_pulse(mock_urlopen, client, monkeypatch):
    # Without API key
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    monkeypatch.delenv("YT_API_KEY", raising=False)
    res = client.post("/api/lab/competitor-pulse", json={"channel_ids": ["UC123"]})
    assert res.status_code == 200
    assert res.get_json()["available"] is False

    assert client.post("/api/lab/competitor-pulse", json={}).status_code == 400

    # With API key
    monkeypatch.setenv("YOUTUBE_API_KEY", "dummy")
    
    # Needs two yt_get calls per channel (channels, playlistItems)
    mock_res_channel = MagicMock()
    mock_res_channel.read.return_value = json.dumps({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "PL123"}}, "snippet": {"title": "Test"}, "statistics": {"subscriberCount": "100"}}]}).encode()
    
    mock_res_playlist = MagicMock()
    mock_res_playlist.read.return_value = json.dumps({"items": [{"snippet": {"resourceId": {"videoId": "vid1"}, "title": "Vid Title"}}]}).encode()
    
    mock_urlopen.side_effect = [MagicMock(__enter__=lambda _: mock_res_channel), MagicMock(__enter__=lambda _: mock_res_playlist)]

    res2 = client.post("/api/lab/competitor-pulse", json={"channel_ids": ["UC123"]})
    assert res2.status_code == 200
    data = res2.get_json()
    assert data["available"] is True
    assert data["channels"][0]["videos"][0]["video_id"] == "vid1"

@patch("urllib.request.urlopen")
def test_audience_overlap(mock_urlopen, client, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "dummy")
    
    mock_channel = MagicMock()
    mock_channel.read.return_value = json.dumps({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "PL123"}}}]}).encode()
    
    mock_playlist = MagicMock()
    mock_playlist.read.return_value = json.dumps({"items": [{"snippet": {"title": "query"}}]}).encode()
    
    mock_search = MagicMock()
    mock_search.read.return_value = json.dumps({"items": [{"snippet": {"channelId": "UC456", "channelTitle": "Other"}}]}).encode()
    
    mock_urlopen.side_effect = [MagicMock(__enter__=lambda _: mock_channel), MagicMock(__enter__=lambda _: mock_playlist), MagicMock(__enter__=lambda _: mock_search)]
    
    res = client.post("/api/lab/audience-overlap", json={"channel_id": "UC123"})
    assert res.status_code == 200
    assert res.get_json()["neighbors"][0]["channel_id"] == "UC456"

    assert client.post("/api/lab/audience-overlap", json={}).status_code == 400

def test_ab_thumb_swap(client):
    _AB_SCHEDULE.clear()
    res = client.post("/api/lab/ab-thumb-swap", json={"video_id": "v1", "thumb_a": "a.jpg", "thumb_b": "b.jpg"})
    assert res.status_code == 200
    assert "v1" in _AB_SCHEDULE

    assert client.post("/api/lab/ab-thumb-swap", json={}).status_code == 400

    res2 = client.get("/api/lab/ab-thumb-swap")
    assert res2.status_code == 200
    assert len(res2.get_json()["schedules"]) == 1

def test_kanban(client, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pf = data_dir / "pipeline.json"
    pf.write_text(json.dumps([{"stage": "script", "stage_entered_at": "2020-01-01T00:00:00Z"}]))
    
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    
    res = client.get("/api/lab/kanban")
    assert res.status_code == 200
    data = res.get_json()
    assert len(data["by_stage"]["script"]) == 1
    assert data["by_stage"]["script"][0]["sla_breached"] is True

@patch("cli_registry.generate")
@patch("cli_registry.probe")
def test_ship_it(mock_probe, mock_generate, client):
    mock_probe.return_value = {"available": ["mock"]}
    mock_generate.return_value = {"text": '{"titles":["T1"], "thumbs":[{"prompt":"P1"}]}'}
    
    res = client.post("/api/lab/ship-it", json={"topic": "Agents"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["topic"] == "Agents"
    assert "title_candidates" in data

    assert client.post("/api/lab/ship-it", json={}).status_code == 400

@patch("cli_registry.probe")
def test_status(mock_probe, client):
    mock_probe.return_value = {"available": ["mock"]}
    res = client.get("/api/lab/status")
    assert res.status_code == 200
    assert "llm_providers" in res.get_json()
    assert res.get_json()["features"]["kanban"]["ready"] is True
