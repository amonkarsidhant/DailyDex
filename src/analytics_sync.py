#!/usr/bin/env python3
"""
analytics_sync.py — YouTube Data API v3 Integration
----------------------------------------------------
Replaces the brittle HTML scraper with official YouTube Data API v3 calls.

Priority:
  1. If YOUTUBE_API_KEY env var or settings_manager key is set → use API
  2. Otherwise → fall back to HTML scraper (legacy, marked as unreliable)

API Key setup:
  console.cloud.google.com → Enable "YouTube Data API v3" → Credentials → API Key
  Free quota: 10,000 units/day. videos.list = 1 unit per call.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any


# ── Key resolution ────────────────────────────────────────────────────────────

def _get_youtube_api_key() -> str:
    """Resolve the YouTube API key: env var > settings file."""
    env_key = os.environ.get("YOUTUBE_API_KEY", "")
    if env_key:
        return env_key
    try:
        from settings_manager import get as settings_get
        return settings_get("youtube_api_key")
    except Exception:
        return ""


# ── YouTube Data API v3 ───────────────────────────────────────────────────────

def _extract_video_id(url: str) -> Optional[str]:
    """Extract a YouTube video ID from various URL formats."""
    if not url:
        return None

    # youtu.be/VIDEO_ID
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)

    # youtube.com/watch?v=VIDEO_ID
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)

    # youtube.com/shorts/VIDEO_ID
    m = re.search(r"/shorts/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)

    # youtube.com/embed/VIDEO_ID
    m = re.search(r"/embed/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)

    return None


def fetch_video_stats_api(video_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch video statistics from YouTube Data API v3.
    Returns a dict with viewCount, likeCount, commentCount, etc.
    Costs 1 quota unit.
    """
    params = urllib.parse.urlencode({
        "part": "statistics,snippet",
        "id": video_id,
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/videos?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "DailyDex/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"[analytics_sync] YouTube API error for {video_id}: {e}")
        return None

    items = data.get("items", [])
    if not items:
        print(f"[analytics_sync] No items returned for video {video_id} — deleted or private?")
        return None

    item = items[0]
    stats = item.get("statistics", {})
    snippet = item.get("snippet", {})

    return {
        "video_id":      video_id,
        "title":         snippet.get("title", ""),
        "channel":       snippet.get("channelTitle", ""),
        "published_at":  snippet.get("publishedAt", ""),
        "view_count":    int(stats.get("viewCount", 0)),
        "like_count":    int(stats.get("likeCount", 0) or 0),
        "comment_count": int(stats.get("commentCount", 0) or 0),
        "thumbnail":     (snippet.get("thumbnails", {}).get("high", {}) or {}).get("url", ""),
    }


# ── Legacy HTML scraper (fallback) ────────────────────────────────────────────

def _scrape_youtube_views_html(url: str) -> Optional[int]:
    """Fallback HTML scraper — fragile, may break on YouTube changes."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/115.0.0.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode("utf-8", errors="ignore")

            m = re.search(r'<meta[^>]*itemprop=["\']interactionCount["\'][^>]*content=["\'](\d+)["\']', html)
            if m:
                return int(m.group(1))

            m = re.search(r'"viewCount":"(\d+)"', html)
            if m:
                return int(m.group(1))

    except Exception as e:
        print(f"[analytics_sync] HTML scrape error for {url}: {e}")
    return None


# ── Main public interface ─────────────────────────────────────────────────────

def get_youtube_views(url: str) -> Optional[int]:
    """
    Get view count for a YouTube URL.
    Uses YouTube Data API v3 if a key is configured, otherwise falls back to HTML scraping.
    """
    if not url:
        return None
    if "youtube.com" not in url and "youtu.be" not in url:
        return None

    api_key = _get_youtube_api_key()

    if api_key:
        video_id = _extract_video_id(url)
        if video_id:
            stats = fetch_video_stats_api(video_id, api_key)
            if stats:
                return stats["view_count"]
        # Fall through to scraper if ID extraction failed
        print(f"[analytics_sync] Could not extract video ID from {url}, trying scraper")

    # Legacy fallback
    print("[analytics_sync] No YouTube API key configured — using HTML scraper (unreliable)")
    return _scrape_youtube_views_html(url)


def get_youtube_full_stats(url: str) -> Optional[Dict[str, Any]]:
    """
    Get full video statistics. Only works with YouTube Data API v3.
    Returns None if no API key is configured.
    """
    api_key = _get_youtube_api_key()
    if not api_key:
        return None

    video_id = _extract_video_id(url)
    if not video_id:
        return None

    return fetch_video_stats_api(video_id, api_key)


def sync_publication_metrics(pub: Dict) -> Optional[Dict]:
    """
    Sync metrics for a publication that has a real YouTube URL.
    Returns updated metrics dict or None.
    """
    url = pub.get("published_url")
    if not url or ("youtube.com" not in url and "youtu.be" not in url):
        return None

    api_key = _get_youtube_api_key()

    if api_key:
        video_id = _extract_video_id(url)
        if video_id:
            stats = fetch_video_stats_api(video_id, api_key)
            if stats:
                views = stats["view_count"]
                likes = stats["like_count"]
                comments = stats["comment_count"]

                # With real data we can compute real engagement
                # Engagement rate = (likes + comments) / views
                engagement_rate = round((likes + comments) / views, 4) if views > 0 else 0.0

                # Impressions are only available via YouTube Studio OAuth (advanced)
                # Use a conservative estimate: impressions ≈ views / typical 8% CTR
                impressions = int(views / 0.08) if views > 0 else 0
                ctr = round(views / impressions, 4) if impressions > 0 else 0.0

                status = "live"
                if views > 25000:
                    status = "completed"

                return {
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "impressions": impressions,
                    "ctr": ctr,
                    "engagement_rate": engagement_rate,
                    "status": status,
                    "source": "youtube_api_v3",
                }

    # Fallback to HTML scraper
    views = _scrape_youtube_views_html(url)
    if views is None:
        return None

    impressions = int(views * 12)
    ctr = round(views / impressions, 4) if impressions > 0 else 0.0
    engagement_rate = 0.055  # placeholder

    status = "live"
    if views > 25000:
        status = "completed"

    return {
        "views": views,
        "impressions": impressions,
        "ctr": ctr,
        "engagement_rate": engagement_rate,
        "status": status,
        "source": "html_scraper",
    }
