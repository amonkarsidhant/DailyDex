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
import statistics
import urllib.request
import urllib.parse
from datetime import datetime, timezone
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
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/", 1)[0]
        return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else None
    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        return None
    if parsed.path == "/watch":
        candidate = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
    else:
        match = re.fullmatch(r"/(?:shorts|embed)/([A-Za-z0-9_-]{11})/?", parsed.path)
        candidate = match.group(1) if match else ""
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        return candidate

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
    video_id = _extract_video_id(url)
    if not video_id:
        return None
    safe_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        req = urllib.request.Request(
            safe_url,
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
    video_id = _extract_video_id(url)
    if not video_id:
        return None

    api_key = _get_youtube_api_key()

    if api_key:
        stats = fetch_video_stats_api(video_id, api_key)
        if stats:
            return stats["view_count"]

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
    video_id = pub.get("video_id") or _extract_video_id(url)
    if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(video_id)):
        return None

    # Owner analytics are preferred because they provide retention and watch
    # duration. Thumbnail CTR is not available from this targeted API.
    try:
        import youtube_oauth

        analytics = youtube_oauth.get_video_analytics(None, str(video_id))
    except Exception:
        analytics = {"error": "OAuth analytics unavailable"}
    if not analytics.get("error"):
        views = int(analytics.get("views") or 0)
        likes = int(analytics.get("likes") or 0)
        comments = int(analytics.get("comments") or 0)
        return {
            "video_id": str(video_id),
            "views": views,
            "likes": likes,
            "comments": comments,
            "impressions": pub.get("impressions") or None,
            "ctr": pub.get("ctr") or None,
            "engagement_rate": round((likes + comments) / views, 4) if views else 0.0,
            "average_view_duration_seconds": analytics.get("average_view_duration_seconds"),
            "average_view_percentage": analytics.get("average_view_percentage"),
            "status": "live",
            "source": "youtube_analytics_api",
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    api_key = _get_youtube_api_key()

    if api_key:
        stats = fetch_video_stats_api(str(video_id), api_key)
        if stats:
            views = stats["view_count"]
            likes = stats["like_count"]
            comments = stats["comment_count"]
            engagement_rate = round((likes + comments) / views, 4) if views > 0 else 0.0

            return {
                "video_id": str(video_id),
                "views": views,
                "likes": likes,
                "comments": comments,
                "impressions": pub.get("impressions") or None,
                "ctr": pub.get("ctr") or None,
                "engagement_rate": engagement_rate,
                "average_view_duration_seconds": None,
                "average_view_percentage": None,
                "status": "live",
                "source": "youtube_api_v3",
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }

    # Fallback to HTML scraper
    views = _scrape_youtube_views_html(url)
    if views is None:
        return None

    return {
        "video_id": str(video_id),
        "views": views,
        "likes": None,
        "comments": None,
        "impressions": pub.get("impressions") or None,
        "ctr": pub.get("ctr") or None,
        "engagement_rate": pub.get("engagement_rate") or None,
        "average_view_duration_seconds": None,
        "average_view_percentage": None,
        "status": "live",
        "source": "html_scraper",
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


def sync_all_publications(db) -> Dict[str, int]:
    """Synchronize every live YouTube publication without fabricating data."""
    counts = {"updated": 0, "failed": 0, "skipped": 0}
    publications = db.get_publication_analytics()
    observed_ctrs = [float(row["ctr"]) for row in publications if row.get("ctr") and row.get("impressions")]
    from rescue_engine import DEFAULT_MEDIAN_CTR, evaluate_performance_status
    channel_median = statistics.median(observed_ctrs) if len(observed_ctrs) >= 3 else DEFAULT_MEDIAN_CTR
    try:
        from settings_manager import get as settings_get
        sensitivity = abs(float(settings_get("rescue_ctr_sensitivity") or -25)) / 100
    except (TypeError, ValueError):
        sensitivity = 0.25
    threshold_factor = 1 - min(0.5, max(0.05, sensitivity))

    for publication in publications:
        if publication.get("platform", "").lower() != "youtube" or publication.get("status") != "live":
            counts["skipped"] += 1
            continue
        metrics = sync_publication_metrics(publication)
        if not metrics:
            db.mark_publication_sync_error(publication["id"], "YouTube metrics were unavailable")
            counts["failed"] += 1
            continue
        assessment = evaluate_performance_status(
            metrics.get("ctr") or publication.get("ctr"),
            metrics.get("views") or publication.get("views") or 0,
            channel_median,
            impressions=metrics.get("impressions") or publication.get("impressions"),
            published_at=publication.get("published_at"),
            threshold_factor=threshold_factor,
        )
        metrics["rescue_status"] = assessment["status"]
        db.record_publication_metrics(publication["id"], metrics)
        counts["updated"] += 1
    return counts
