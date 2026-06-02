import json
from unittest.mock import MagicMock, patch

import pytest

import analytics_sync

def test_get_youtube_api_key(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "env_key")
    assert analytics_sync._get_youtube_api_key() == "env_key"

    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with patch("settings_manager.get") as mock_get:
        mock_get.return_value = "set_key"
        assert analytics_sync._get_youtube_api_key() == "set_key"

        mock_get.side_effect = Exception("No")
        assert analytics_sync._get_youtube_api_key() == ""

def test_extract_video_id():
    assert analytics_sync._extract_video_id("https://youtu.be/1234567890a") == "1234567890a"
    assert analytics_sync._extract_video_id("https://youtube.com/watch?v=1234567890a") == "1234567890a"
    assert analytics_sync._extract_video_id("https://youtube.com/shorts/1234567890a") == "1234567890a"
    assert analytics_sync._extract_video_id("https://youtube.com/embed/1234567890a") == "1234567890a"
    assert analytics_sync._extract_video_id("https://other.com") is None
    assert analytics_sync._extract_video_id("") is None

@patch("urllib.request.urlopen")
def test_fetch_video_stats_api(mock_urlopen):
    # Success
    mock_res = MagicMock()
    mock_res.read.return_value = json.dumps({
        "items": [{
            "snippet": {"title": "Test Title", "channelTitle": "Ch", "publishedAt": "2024", "thumbnails": {"high": {"url": "img"}}},
            "statistics": {"viewCount": "100", "likeCount": "10", "commentCount": "5"}
        }]
    }).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_res
    
    stats = analytics_sync.fetch_video_stats_api("vid", "key")
    assert stats["view_count"] == 100
    assert stats["title"] == "Test Title"

    # Empty items
    mock_res.read.return_value = json.dumps({"items": []}).encode()
    assert analytics_sync.fetch_video_stats_api("vid", "key") is None

    # Error
    mock_urlopen.side_effect = Exception("HTTP")
    assert analytics_sync.fetch_video_stats_api("vid", "key") is None

@patch("urllib.request.urlopen")
def test_scrape_youtube_views_html(mock_urlopen):
    # Success itemprop
    mock_res = MagicMock()
    mock_res.read.return_value = b'<meta itemprop="interactionCount" content="500">'
    mock_urlopen.return_value.__enter__.return_value = mock_res
    assert analytics_sync._scrape_youtube_views_html("http://url") == 500

    # Success viewCount json
    mock_res.read.return_value = b'"viewCount":"600"'
    assert analytics_sync._scrape_youtube_views_html("http://url") == 600

    # Error
    mock_urlopen.side_effect = Exception("Fail")
    assert analytics_sync._scrape_youtube_views_html("http://url") is None

@patch("analytics_sync.fetch_video_stats_api")
@patch("analytics_sync._scrape_youtube_views_html")
@patch("analytics_sync._get_youtube_api_key")
def test_get_youtube_views(mock_get_key, mock_scrape, mock_fetch):
    # Invalid url
    assert analytics_sync.get_youtube_views("") is None
    assert analytics_sync.get_youtube_views("http://google.com") is None

    # With API key
    mock_get_key.return_value = "key"
    mock_fetch.return_value = {"view_count": 1000}
    assert analytics_sync.get_youtube_views("https://youtu.be/1234567890a") == 1000

    # API key but fetch fails -> fallback to scraper (wait, logic says it falls back if ID extract fails)
    # Actually if fetch fails it returns None, get_youtube_views returns None
    mock_fetch.return_value = None
    mock_scrape.return_value = 50
    assert analytics_sync.get_youtube_views("https://youtube.com/invalid_id") == 50

    # No API key -> fallback
    mock_get_key.return_value = ""
    mock_scrape.return_value = 500
    assert analytics_sync.get_youtube_views("https://youtu.be/1234567890a") == 500

@patch("analytics_sync.fetch_video_stats_api")
@patch("analytics_sync._get_youtube_api_key")
def test_get_youtube_full_stats(mock_get_key, mock_fetch):
    # No key
    mock_get_key.return_value = ""
    assert analytics_sync.get_youtube_full_stats("https://youtu.be/vid") is None
    
    # Invalid url
    mock_get_key.return_value = "k"
    assert analytics_sync.get_youtube_full_stats("not_yt") is None

    # Success
    mock_fetch.return_value = {"view_count": 10}
    assert analytics_sync.get_youtube_full_stats("https://youtu.be/1234567890a") == {"view_count": 10}

@patch("analytics_sync.fetch_video_stats_api")
@patch("analytics_sync._scrape_youtube_views_html")
@patch("analytics_sync._get_youtube_api_key")
def test_sync_publication_metrics(mock_get_key, mock_scrape, mock_fetch):
    # No url
    assert analytics_sync.sync_publication_metrics({}) is None
    
    # API success
    mock_get_key.return_value = "key"
    mock_fetch.return_value = {"view_count": 30000, "like_count": 100, "comment_count": 50}
    res = analytics_sync.sync_publication_metrics({"published_url": "https://youtu.be/1234567890a"})
    assert res["views"] == 30000
    assert res["status"] == "completed"
    assert res["source"] == "youtube_api_v3"
    
    # Scraper fallback
    mock_get_key.return_value = ""
    mock_scrape.return_value = 5000
    res2 = analytics_sync.sync_publication_metrics({"published_url": "https://youtu.be/1234567890a"})
    assert res2["views"] == 5000
    assert res2["status"] == "live"
    assert res2["source"] == "html_scraper"
    
    # Scraper fails
    mock_scrape.return_value = None
    assert analytics_sync.sync_publication_metrics({"published_url": "https://youtu.be/1234567890a"}) is None
