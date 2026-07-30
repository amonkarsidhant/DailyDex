"""Creator Signal Miner for DailyDex.

Mines live, empirical audience signals from Hacker News (Algolia API) and Reddit
to discover verified creator topics free from AI filler or hallucination.
"""

import os
import urllib.request
import urllib.parse
import json
import time
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.environ.get("CONFIG_FILE", os.path.join(BASE_DIR, "config.json"))


def _signals_config() -> Dict[str, Any]:
    """Read the `signals` section from config.json (empty dict if missing)."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f).get("signals", {})
    except Exception:
        return {}


def mine_hacker_news_signals(query: str = "AI agent", min_points: int = 50, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch top trending Hacker News discussions matching query via public Algolia API."""
    encoded_q = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={encoded_q}&tags=story&numericFilters=points>{min_points}"

    req = urllib.request.Request(url, headers={"User-Agent": "DailyDex-SignalMiner/1.0"})
    results = []
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            for hit in data.get("hits", [])[:limit]:
                results.append({
                    "source": "Hacker News",
                    "title": hit.get("title", ""),
                    "url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "external_url": hit.get("url", ""),
                    "points": hit.get("points", 0),
                    "num_comments": hit.get("num_comments", 0),
                    "created_at": hit.get("created_at", ""),
                    "signal_score": round((hit.get("points", 0) * 1.0) + (hit.get("num_comments", 0) * 1.5), 1)
                })
    except Exception as e:
        print(f"[creator_signal_miner] HN mining error: {e}")
    return sorted(results, key=lambda x: x["signal_score"], reverse=True)


def mine_reddit_signals(subreddit: str = "LocalLLaMA", limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch top weekly Reddit discussions from technical subreddits via public RSS feed."""
    import feedparser
    url = f"https://www.reddit.com/r/{subreddit}/top/.rss?t=week"
    results = []
    try:
        feed = feedparser.parse(url)
        for idx, entry in enumerate(feed.entries[:limit]):
            results.append({
                "source": f"r/{subreddit}",
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "signal_score": round(500.0 - (idx * 50.0), 1)
            })
    except Exception as e:
        print(f"[creator_signal_miner] Reddit mining error: {e}")
    return results


def research_topic_signals(niche_query: str = "") -> Dict[str, Any]:
    """Execute rigorous multi-source audience signal research for a creator niche.

    Queries and subreddits come from config.json's `signals` section; explicit
    niche_query overrides the configured HN queries.
    """
    cfg = _signals_config()
    hn_queries = [niche_query] if niche_query else cfg.get("hn_queries", ["AI agents local"])
    min_points = cfg.get("hn_min_points", 30)
    subreddits = cfg.get("subreddits", ["LocalLLaMA"])

    all_signals = []
    for query in hn_queries:
        all_signals.extend(mine_hacker_news_signals(query, min_points=min_points, limit=4))
    for sub in subreddits:
        all_signals.extend(mine_reddit_signals(sub, limit=4))

    seen_urls = set()
    deduped = []
    for sig in sorted(all_signals, key=lambda x: x.get("signal_score", 0), reverse=True):
        if sig.get("url") in seen_urls:
            continue
        seen_urls.add(sig.get("url"))
        deduped.append(sig)

    return {
        "query": niche_query or ", ".join(hn_queries),
        "mined_at": time.time(),
        "total_signals": len(deduped),
        "top_signals": deduped,
        "sources": ["Hacker News (Algolia API)", "Reddit RSS"]
    }
