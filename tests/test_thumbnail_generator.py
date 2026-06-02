import json
from unittest.mock import MagicMock, patch
import urllib.error

import pytest

import thumbnail_generator

def test_get_fal_key(monkeypatch):
    monkeypatch.setenv("FAL_API_KEY", "env_key")
    assert thumbnail_generator._get_fal_key() == "env_key"

    monkeypatch.delenv("FAL_API_KEY", raising=False)
    with patch("settings_manager.get") as mock_get:
        mock_get.return_value = "settings_key"
        assert thumbnail_generator._get_fal_key() == "settings_key"

        mock_get.side_effect = Exception("No settings")
        assert thumbnail_generator._get_fal_key() == ""

@patch("urllib.request.urlopen")
def test_generate_with_fal(mock_urlopen):
    mock_res = MagicMock()
    mock_res.read.return_value = json.dumps({"images": [{"url": "http://img", "width": 100, "height": 100}]}).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_res
    
    res = thumbnail_generator.generate_with_fal("prompt", "key")
    assert res is not None
    assert res["url"] == "http://img"

    # Empty images
    mock_res.read.return_value = json.dumps({"images": []}).encode()
    assert thumbnail_generator.generate_with_fal("prompt", "key") is None

    # HTTP Error
    err = urllib.error.HTTPError("url", 400, "Bad Request", {}, None)
    err.read = lambda: b"error body"
    mock_urlopen.side_effect = err
    assert thumbnail_generator.generate_with_fal("prompt", "key") is None

    # General Error
    mock_urlopen.side_effect = Exception("General Error")
    assert thumbnail_generator.generate_with_fal("prompt", "key") is None

@patch("urllib.request.urlopen")
@patch("time.sleep")
def test_generate_with_replicate(mock_sleep, mock_urlopen):
    # Success
    mock_create = MagicMock()
    mock_create.read.return_value = json.dumps({"urls": {"get": "http://poll"}}).encode()
    
    mock_poll = MagicMock()
    mock_poll.read.return_value = json.dumps({"status": "succeeded", "output": ["http://img2"]}).encode()
    
    mock_urlopen.side_effect = [MagicMock(__enter__=lambda _: mock_create), MagicMock(__enter__=lambda _: mock_poll)]
    
    res = thumbnail_generator.generate_with_replicate("prompt", "key")
    assert res is not None
    assert res["url"] == "http://img2"

    # Creation failed
    mock_urlopen.side_effect = Exception("Create fail")
    assert thumbnail_generator.generate_with_replicate("p", "k") is None

    # Poll failed status
    mock_poll_fail = MagicMock()
    mock_poll_fail.read.return_value = json.dumps({"status": "failed"}).encode()
    mock_urlopen.side_effect = [MagicMock(__enter__=lambda _: mock_create), MagicMock(__enter__=lambda _: mock_poll_fail)]
    assert thumbnail_generator.generate_with_replicate("p", "k") is None

    # Timeout
    mock_poll_processing = MagicMock()
    mock_poll_processing.read.return_value = json.dumps({"status": "processing"}).encode()
    mock_urlopen.side_effect = [MagicMock(__enter__=lambda _: mock_create)] + [MagicMock(__enter__=lambda _: mock_poll_processing)] * 30
    assert thumbnail_generator.generate_with_replicate("p", "k") is None

@patch("thumbnail_generator.generate_with_fal")
@patch("thumbnail_generator.generate_with_replicate")
@patch("thumbnail_generator._get_fal_key")
def test_generate_thumbnail(mock_get_fal, mock_rep, mock_fal, monkeypatch):
    monkeypatch.delenv("REPLICATE_API_KEY", raising=False)
    
    # Fal key exists
    mock_get_fal.return_value = "fal_key"
    mock_fal.side_effect = [{"url": "f"}, {"url": "f"}]
    res = thumbnail_generator.generate_thumbnail("topic", num_variants=2)
    assert len(res) == 2
    assert res[0]["url"] == "f"
    assert res[0]["variant_index"] == 0

    # No fal key, Replicate key exists
    mock_get_fal.return_value = ""
    monkeypatch.setenv("REPLICATE_API_KEY", "rep_key")
    mock_rep.return_value = {"url": "r"}
    res2 = thumbnail_generator.generate_thumbnail("topic")
    assert len(res2) == 1
    assert res2[0]["url"] == "r"

    # No keys
    monkeypatch.delenv("REPLICATE_API_KEY", raising=False)
    res3 = thumbnail_generator.generate_thumbnail("topic")
    assert len(res3) == 1
    assert res3[0]["url"] is None
    assert res3[0]["provider"] == "none"

def test_build_thumbnail_prompt():
    p = thumbnail_generator._build_thumbnail_prompt("Test Topic", "Context")
    assert "Test Topic" in p
    assert "Context" in p

def test_thumbnail_preview_html():
    h = thumbnail_generator.thumbnail_preview_html({"url": "http://img"})
    assert '<img src="http://img"' in h

    h2 = thumbnail_generator.thumbnail_preview_html({"error": "Failed"})
    assert "Failed" in h2
