"""Competitor Channel Analysis Engine (DailyDex Phase 2 - Gap 6).

Analyzes competitor YouTube channels via public RSS feeds and YouTube Data API v3
to extract posting frequency, format mix, top performers, and outlier videos.
"""

import urllib.request
import xml.etree.ElementTree as ET
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

try:
    from settings_manager import get_setting
except ImportError:
    def get_setting(key, default=None):
        return default


def fetch_channel_rss_videos(channel_id: str) -> List[Dict[str, Any]]:
    """Fetch latest public videos for a channel using YouTube atom RSS feed (free, no API key required)."""
    clean_id = channel_id.strip()
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={clean_id}"
    videos = []
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 DailyDex/1.0"
        })
        with urllib.request.urlopen(req, timeout=6) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            # Namespace map
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "yt": "http://www.youtube.com/xml/schemas/2015",
                "media": "http://search.yahoo.com/mrss/"
            }
            for entry in root.findall("atom:entry", ns):
                video_id_elem = entry.find("yt:videoId", ns)
                title_elem = entry.find("atom:title", ns)
                published_elem = entry.find("atom:published", ns)

                video_id = video_id_elem.text if video_id_elem is not None else ""
                title = title_elem.text if title_elem is not None else "Untitled"
                published_str = published_elem.text if published_elem is not None else ""

                # Try media group for views/description
                views = 0
                media_group = entry.find("media:group", ns)
                if media_group is not None:
                    stats_elem = media_group.find("media:community/media:statistics", ns)
                    if stats_elem is not None:
                        views = int(stats_elem.attrib.get("views", 0))

                is_short = ("#shorts" in title.lower() or "#short" in title.lower())

                videos.append({
                    "video_id": video_id,
                    "title": title,
                    "url": f"https://youtube.com/watch?v={video_id}",
                    "published_at": published_str,
                    "views": views,
                    "is_short": is_short
                })
    except Exception as e:
        print(f"[competitor_analyzer] RSS fetch error for {channel_id}: {e}")
    return videos


def analyze_channel(channel_id: str, channel_name: Optional[str] = None) -> Dict[str, Any]:
    """Run comprehensive analysis on a competitor channel."""
    videos = fetch_channel_rss_videos(channel_id)

    if not videos:
        return {
            "channel_id": channel_id,
            "channel_name": channel_name or channel_id,
            "error": "Could not fetch public feed. Ensure valid YouTube channel ID starting with UC...",
            "video_count": 0
        }

    # Calculate posting frequency
    now = datetime.utcnow()
    timestamps = []
    for v in videos:
        try:
            pub_dt = datetime.fromisoformat(v["published_at"].replace("Z", "+00:00")).replace(tzinfo=None)
            timestamps.append(pub_dt)
        except Exception:
            pass

    posting_freq_weekly = 1.0
    if len(timestamps) >= 2:
        timestamps.sort()
        span_days = max(1, (timestamps[-1] - timestamps[0]).days)
        posting_freq_weekly = round((len(timestamps) / span_days) * 7.0, 1)

    shorts_count = sum(1 for v in videos if v["is_short"])
    longform_count = len(videos) - shorts_count

    # Calculate outlier score for videos with view counts
    avg_views = 0
    views_list = [v["views"] for v in videos if v["views"] > 0]
    if views_list:
        avg_views = sum(views_list) // len(views_list)

    for v in videos:
        if avg_views > 0 and v["views"] > 0:
            outlier_ratio = round(v["views"] / max(1, avg_views), 2)
            v["outlier_ratio"] = outlier_ratio
            v["is_outlier"] = outlier_ratio >= 1.5
        else:
            v["outlier_ratio"] = 1.0
            v["is_outlier"] = False

    return {
        "channel_id": channel_id,
        "channel_name": channel_name or channel_id,
        "video_count": len(videos),
        "posting_frequency_weekly": posting_freq_weekly,
        "format_mix": {
            "shorts": shorts_count,
            "longform": longform_count
        },
        "avg_views": avg_views,
        "latest_videos": videos[:15]
    }
