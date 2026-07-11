import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import fetch_news

def test_fingerprint_and_duplicate():
    fetch_news._seen_fingerprints.clear()
    
    item1 = {"title": "Test Title", "url": "https://example.com/path", "source": "News Source"}
    item2 = {"title": "Test Title", "url": "http://example.com/path/", "source": "News Source"}
    item3 = {"title": "Different Title", "url": "https://example.com/path", "source": "News Source"}

    # They should have identical fingerprints if normalized correctly
    fp1 = fetch_news.get_fingerprint(item1)
    fp2 = fetch_news.get_fingerprint(item2)
    assert fp1 == fp2
    
    assert not fetch_news.is_duplicate(item1)
    assert fetch_news.is_duplicate(item2)
    assert not fetch_news.is_duplicate(item3)

def test_cache_operations(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(fetch_news, "CACHE_DIR", str(cache_dir))
    
    items = [{"title": "cached item", "url": "https://example.com/cached"}]
    fetch_news.save_source_cache("test_source", items)
    
    # Should exist
    assert (cache_dir / "test_source.json").exists()
    
    # Age should be 0 seconds
    age = fetch_news.get_cache_age_seconds("test_source")
    assert age >= 0 and age < 5
    
    loaded_items, is_fresh = fetch_news.load_source_cache("test_source")
    assert loaded_items == items
    assert is_fresh is True
    
    # Age of non-existent cache should be 0
    assert fetch_news.get_cache_age_seconds("does_not_exist") == 0
    loaded_none, is_fresh_none = fetch_news.load_source_cache("does_not_exist")
    assert loaded_none == []
    assert is_fresh_none is False

def test_config_operations(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(fetch_news, "CONFIG_FILE", str(config_file))
    
    assert fetch_news.load_config() == {}
    
    cfg = {"github": {"limit": 10}}
    fetch_news.save_config(cfg)
    
    assert fetch_news.load_config() == cfg

def test_merge_weekly_data():
    now = datetime.now()
    two_days_ago = (now - timedelta(days=2)).isoformat() + "Z"
    eight_days_ago = (now - timedelta(days=8)).isoformat() + "Z"
    
    history = {
        "github": [
            {"title": "Old Valid", "published": two_days_ago},
            {"title": "Too Old", "published": eight_days_ago}
        ]
    }
    new_data = {
        "github": [
            {"title": "New", "published": now.isoformat() + "Z"}
        ]
    }
    
    combined = fetch_news.merge_weekly_data(history, new_data)
    titles = [i["title"] for i in combined["github"]]
    assert "New" in titles
    assert "Old Valid" in titles
    assert "Too Old" not in titles

@patch("yt_dlp.YoutubeDL")
def test_get_youtube_feeds(mock_ydl_class, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"youtube": {"channels": [{"name": "Test", "url": "https://youtube.com/@test"}]}}))
    monkeypatch.setattr(fetch_news, "CONFIG_FILE", str(config_file))
    
    mock_ydl = MagicMock()
    mock_ydl_class.return_value.__enter__.return_value = mock_ydl
    mock_ydl.extract_info.return_value = {
        "entries": [{"id": "vid1", "title": "Vid Title", "description": "Vid Desc"}]
    }
    
    results = fetch_news.get_youtube_feeds()
    assert len(results) == 1
    assert results[0]["title"] == "Vid Title"
    assert results[0]["url"] == "https://youtube.com/watch?v=vid1"

@patch("requests.get")
def test_get_github_trending(mock_get, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"github": {"limit": 1}}))
    monkeypatch.setattr(fetch_news, "CONFIG_FILE", str(config_file))
    
    mock_res = MagicMock()
    mock_res.text = '<article class="Box-row"><h2><a class="Link" href="/acme/repo">acme/repo</a></h2><p>AI repo</p><a class="Link--muted">123 stars today</a><span itemprop="programmingLanguage">Python</span></article>'
    mock_get.return_value = mock_res
    
    results = fetch_news.get_github_trending()
    assert len(results) == 1
    assert results[0]["title"] == "acme/repo"

@patch("requests.get")
def test_get_huggingface(mock_get, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"huggingface": {"limit": 1}}))
    monkeypatch.setattr(fetch_news, "CONFIG_FILE", str(config_file))
    
    mock_res = MagicMock()
    mock_res.json.return_value = [{"id": "model1", "downloads": 100, "likes": 10}]
    mock_get.return_value = mock_res
    
    results = fetch_news.get_huggingface()
    assert len(results) == 1
    assert results[0]["title"] == "model1"

@patch("feedparser.parse")
def test_get_blogs(mock_parse, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"blogs": [{"name": "Test", "url": "https://test"}]}))
    monkeypatch.setattr(fetch_news, "CONFIG_FILE", str(config_file))
    
    mock_feed = MagicMock()
    mock_entry = MagicMock()
    mock_entry.title = "Blog Post"
    mock_entry.link = "https://example.com"
    mock_entry.get.return_value = "2026-01-01"
    mock_feed.entries = [mock_entry]
    mock_parse.return_value = mock_feed
    
    results = fetch_news.get_blogs()
    assert len(results) == 1
    assert results[0]["title"] == "Blog Post"

@patch("feedparser.parse")
def test_get_arxiv(mock_parse, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"arxiv": {"limit": 1}}))
    monkeypatch.setattr(fetch_news, "CONFIG_FILE", str(config_file))
    
    mock_feed = MagicMock()
    mock_entry = MagicMock()
    mock_entry.title = "Paper Title"
    mock_entry.link = "https://arxiv.org/abs/1234"
    mock_entry.published = "2026-01-01"
    mock_entry.get.return_value = []
    mock_feed.entries = [mock_entry]
    mock_parse.return_value = mock_feed
    
    results = fetch_news.get_arxiv()
    assert len(results) == 1
    assert results[0]["title"] == "Paper Title"

@patch("requests.get")
def test_get_hackernews(mock_get, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({}))
    monkeypatch.setattr(fetch_news, "CONFIG_FILE", str(config_file))
    
    # Mock topstories
    mock_top = MagicMock()
    mock_top.json.return_value = [1]
    
    # Mock item
    mock_item = MagicMock()
    mock_item.status_code = 200
    mock_item.json.return_value = {"type": "story", "title": "New AI Agent Released", "url": "https://example", "score": 100}
    
    mock_get.side_effect = [mock_top, mock_item]
    
    results = fetch_news.get_hackernews()
    assert len(results) == 1
    assert results[0]["title"] == "New AI Agent Released"

@patch.object(fetch_news, "update_source_health")
@patch.object(fetch_news, "get_reddit")
@patch.object(fetch_news, "get_hackernews")
@patch.object(fetch_news, "get_arxiv")
@patch.object(fetch_news, "get_blogs")
@patch.object(fetch_news, "get_huggingface")
@patch.object(fetch_news, "get_github_trending")
@patch.object(fetch_news, "get_youtube_feeds")
def test_fetch_all(m_yt, m_gh, m_hf, m_bl, m_ar, m_hn, m_rd, m_update_health, tmp_path, monkeypatch):
    data_file = tmp_path / "data.json"
    monkeypatch.setattr(fetch_news, "DATA_FILE", str(data_file))
    
    m_yt.return_value = [{"title": "yt"}]
    m_gh.return_value = [{"title": "gh"}]
    m_hf.return_value = [{"title": "hf"}]
    m_bl.return_value = [{"title": "bl"}]
    m_ar.return_value = [{"title": "ar"}]
    m_hn.return_value = [{"title": "hn"}]
    m_rd.return_value = [{"title": "rd"}]
    
    # Fetch all
    last_updated = fetch_news.fetch_all()
    
    # Verify file saved
    assert data_file.exists()
    saved_data = json.loads(data_file.read_text())
    
    assert len(saved_data["youtube"]) == 1
    assert saved_data["last_updated"] == last_updated
    assert m_update_health.call_count == 7
    assert "reddit" in saved_data
    assert len(saved_data["reddit"]) == 1


@patch("requests.get")
def test_get_reddit(mock_get, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "reddit": {"subreddits": ["LocalLLaMA"], "limit_per_subreddit": 3}
    }))
    monkeypatch.setattr(fetch_news, "CONFIG_FILE", str(config_file))

    mock_res = MagicMock()
    mock_res.json.return_value = {
        "data": {
            "children": [
                {"data": {"title": "New local LLM runs on Pi", "score": 200, "num_comments": 50, "permalink": "/r/LocalLLaMA/comments/abc/new_llm", "created_utc": 1700000000}},
                {"data": {"title": "Off-topic post about cooking", "score": 10, "num_comments": 2, "permalink": "/r/LocalLLaMA/comments/def/cooking", "created_utc": 1700000000}},
            ]
        }
    }
    mock_get.return_value = mock_res

    results = fetch_news.get_reddit()
    assert len(results) == 1
    assert results[0]["title"] == "New local LLM runs on Pi"
    assert results[0]["source"] == "Reddit r/LocalLLaMA"
    assert results[0]["url"] == "https://www.reddit.com/r/LocalLLaMA/comments/abc/new_llm"
    assert results[0]["score"] == 200

@patch("fetch_news.get_intel_db")
def test_update_source_health_exception(mock_db):
    # Test that exception in update_source_health is swallowed
    mock_db.side_effect = Exception("DB Error")
    
    # Should not raise
    fetch_news.update_source_health("test", True)
