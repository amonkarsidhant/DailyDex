#!/usr/bin/env python3
"""Fetch AI news from multiple sources."""

import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "intelligence.db"))
CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(DATA_DIR, "cache"))
DATA_FILE = os.environ.get("DATA_FILE", os.path.join(DATA_DIR, "data.json"))
CONFIG_FILE = os.environ.get("CONFIG_FILE", os.path.join(BASE_DIR, "config.json"))
CACHE_TTL_HOURS = 12

# Deduplication cache
_seen_fingerprints = set()

def get_fingerprint(item):
    """Create stable fingerprint for deduplication"""
    title = item.get("title", "").lower().strip()
    url = item.get("url", "").lower().strip()
    # Normalize: remove http(s)://, trailing slashes
    if url:
        url = url.rstrip('/').replace('https://','').replace('http://','')
    # Extract domain for news items
    domain = ''
    if 'blogs' in item.get('source', '').lower() or 'news' in item.get('source', '').lower():
        parts = url.split('/')
        domain = parts[0] if parts else ''
    return f"{title}|{domain}"


def is_duplicate(item):
    """Check if item is duplicate"""
    fp = get_fingerprint(item)
    if fp in _seen_fingerprints:
        return True
    _seen_fingerprints.add(fp)
    return False


def load_source_cache(source_name: str):
    """Load cached data for a source"""
    cache_file = os.path.join(CACHE_DIR, f"{source_name}.json")
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data.get("cached_at", "2020-01-01"))
        age_hours = (datetime.now() - cached_at).total_seconds() / 3600
        if age_hours < CACHE_TTL_HOURS:
            return data.get("items", []), True  # Cache is fresh
        return data.get("items", []), False  # Cache is stale
    return [], False


def get_cache_age_seconds(source_name: str) -> int:
    """Get cache age for a source in seconds."""
    cache_file = os.path.join(CACHE_DIR, f"{source_name}.json")
    if not os.path.exists(cache_file):
        return 0
    return int((datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file)).replace(tzinfo=None)).total_seconds())


def save_source_cache(source_name: str, items: list):
    """Save data to source cache"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{source_name}.json")
    with open(cache_file, "w") as f:
        json.dump({"items": items, "cached_at": datetime.now().isoformat()}, f)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_youtube_feeds():
    import yt_dlp
    import re

    config = load_config()
    channels = config.get("youtube", {}).get("channels", [])

    def clean_desc(desc):
        if not desc:
            return ""
        lines = desc.split("\n")
        clean = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.match(r"^[\U0001F300-\U0001F9FF]", line):
                continue
            if any(
                x in line.lower()
                for x in [
                    "subscribe",
                    " patreon",
                    "affiliate",
                    "sign up",
                    "http",
                    "discord",
                ]
            ):
                continue
            if len(line) > 3:
                clean.append(line)
        return " ".join(clean[:2])[:150]

    results = []
    channel_error = None
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "js_runtime": "node"}
    for ch in channels:
        name, url = ch.get("name", ""), ch.get("url", "")
        if not url:
            continue
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                for video in info.get("entries", [])[:3]:
                    results.append(
                        {
                            "source": f"YouTube - {name}",
                            "title": video.get("title", ""),
                            "url": f"https://youtube.com/watch?v={video.get('id', '')}",
                            "description": clean_desc(video.get("description", "")),
                            "type": "video",
                        }
                    )
        except Exception as e:
            channel_error = e
            print(f"  YT-{name}: ERROR: {e}")
    if channels and not results and channel_error is not None:
        raise RuntimeError(f"YouTube fetch failed: {channel_error}")
    return results
def get_github_trending():
    import requests
    from bs4 import BeautifulSoup

    config = load_config()
    url = config.get("github", {}).get(
        "url", "https://github.com/trending?since=weekly"
    )
    limit = config.get("github", {}).get("limit", 15)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    repos = []
    for article in soup.select("article.Box-row")[:limit]:
        title_elem = article.select_one("h2 a.Link")
        if title_elem:
            href = title_elem.get("href", "")
            repos.append(
                {
                    "source": "GitHub Trending",
                    "title": href.lstrip("/")
                    if href
                    else title_elem.get_text(strip=True),
                    "url": "https://github.com" + href,
                    "description": article.select_one("p").text.strip()
                    if article.select_one("p")
                    else "",
                    "stars": article.select_one("a.Link--muted")
                    .text.strip()
                    .split()[0]
                    if article.select_one("a.Link--muted")
                    else "0",
                    "language": article.select_one("span[itemprop]").text.strip()
                    if article.select_one("span[itemprop]")
                    else "",
                }
            )
    return repos


def get_huggingface():
    import requests

    config = load_config()
    limit = config.get("huggingface", {}).get("limit", 15)
    r = requests.get(
        f"https://huggingface.co/api/models?sort=downloads&direction=-1&limit={limit}",
        timeout=10,
    )
    r.raise_for_status()
    models = r.json()
    return [
        {
            "source": "HuggingFace",
            "title": m["id"],
            "url": f"https://huggingface.co/{m['id']}",
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
        }
        for m in models
    ]


def get_blogs():
    import feedparser

    config = load_config()
    feeds = config.get("blogs", [])

    blogs = []
    blog_error = None
    for feed in feeds:
        name, url = feed.get("name", ""), feed.get("url", "")
        if not url:
            continue
        try:
            f = feedparser.parse(url)
            for entry in f.entries[:5]:
                blogs.append(
                    {
                        "source": name,
                        "title": entry.title,
                        "url": entry.link,
                        "published": entry.get("published", ""),
                        "type": "blog",
                    }
                )
        except Exception as e:
            blog_error = e
            print(f"  Blog-{name}: {e}")
    if feeds and not blogs and blog_error is not None:
        raise RuntimeError(f"Blog fetch failed: {blog_error}")
    return blogs


def get_arxiv():
    import feedparser

    config = load_config()
    limit = config.get("arxiv", {}).get("limit", 15)
    feed = feedparser.parse(
        f"http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
    )
    papers = []
    for e in feed.entries:
        # Extract arXiv ID from URL
        arxiv_id = e.link.split("/")[-1] if e.link else ""
        
        # Extract authors
        authors = [a.name for a in e.get("authors", [])]
        
        # Get categories
        categories = [tag.term for tag in e.get("tags", [])]
        
        # Abstract (summary)
        abstract = e.get("summary", "")[:500]
        
        # PDF URL
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        papers.append({
            "source": "ArXiv AI",
            "title": e.title.replace("\n", " "),
            "url": e.link,
            "published": e.published,
            "arxiv_id": arxiv_id,
            "authors": authors[:5],  # Limit to 5 authors
            "abstract": abstract,
            "categories": categories,
            "pdf_url": pdf_url,
        })
    return papers


def get_hackernews():
    import requests
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Get top stories
    try:
        r = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
        r.raise_for_status()
        story_ids = r.json()
    except Exception as e:
        print(f"  HN: Failed to fetch top stories list: {e}")
        return []

    # Limit to top 150 stories to inspect
    story_ids = story_ids[:150]

    config = load_config()
    variant_key = config.get("variant", "default")
    variant_config = config.get("variants", {}).get(variant_key, {})
    
    # AI/ML filter keywords
    focus_kws = {kw.lower() for kw in variant_config.get("focus_keywords", [])}
    base_kws = {
        "ai", "ml", "llm", "gpt", "claude", "llama", "mcp", "agent", 
        "openai", "anthropic", "gemini", "deepmind", "reasoning model",
        "open-source model", "neural", "deep learning", "machine learning",
        "stable diffusion", "midjourney", "huggingface", "vector db", 
        "rag", "copilot", "cursor", "ollama", "vlm", "lmm"
    }
    keywords = base_kws.union(focus_kws)

    results = []

    def fetch_item(story_id):
        try:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            item_res = requests.get(item_url, timeout=5)
            if item_res.status_code == 200:
                item_data = item_res.json()
                if item_data and item_data.get("type") == "story":
                    title = item_data.get("title", "")
                    title_lower = title.lower()
                    
                    if any(kw in title_lower for kw in keywords):
                        pub_time = item_data.get("time", int(time.time()))
                        published_str = datetime.fromtimestamp(pub_time).isoformat()
                        return {
                            "source": "HackerNews",
                            "title": title,
                            "url": item_data.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                            "score": item_data.get("score", 0),
                            "comments": item_data.get("descendants", 0),
                            "published": published_str,
                            "type": "news"
                        }
        except Exception:
            pass
        return None

    # Fetch concurrently with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_item, s_id) for s_id in story_ids]
        for future in as_completed(futures):
            item = future.result()
            if item:
                results.append(item)

    # Sort by score descending
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def fetch_all():
    print(f"[{datetime.now().strftime('%H:%M')}] Fetching AI news...")

    # Load existing data for weekly retention
    history = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            history = json.load(f)

    # Get new data with cache fallback
    new_data = {"last_updated": datetime.now().isoformat()}
    
    # YouTube
    try:
        new_data["youtube"] = get_youtube_feeds()
        save_source_cache("youtube", new_data["youtube"])
        update_source_health("youtube", True, len(new_data["youtube"]))
        print(f"  YouTube: {len(new_data['youtube'])} items")
    except Exception as e:
        print(f"  YouTube failed: {e}")
        cached, is_fresh = load_source_cache("youtube")
        new_data["youtube"] = cached
        cache_age = get_cache_age_seconds("youtube")
        update_source_health("youtube", False, len(cached), str(e), cache_age_seconds=cache_age)
        print(f"  Using cache: {len(cached)} items" + (" (stale)" if cached and not is_fresh else ""))
    
    # GitHub
    try:
        new_data["github"] = get_github_trending()
        save_source_cache("github", new_data["github"])
        update_source_health("github", True, len(new_data["github"]))
        print(f"  GitHub: {len(new_data['github'])} repos")
    except Exception as e:
        print(f"  GitHub failed: {e}")
        cached, is_fresh = load_source_cache("github")
        new_data["github"] = cached
        cache_age = get_cache_age_seconds("github")
        update_source_health("github", False, len(cached), str(e), cache_age_seconds=cache_age)
        print(f"  Using cache: {len(cached)} repos" + (" (stale)" if cached and not is_fresh else ""))

    # HuggingFace
    try:
        new_data["huggingface"] = get_huggingface()
        save_source_cache("huggingface", new_data["huggingface"])
        update_source_health("huggingface", True, len(new_data["huggingface"]))
        print(f"  HuggingFace: {len(new_data['huggingface'])} models")
    except Exception as e:
        print(f"  HuggingFace failed: {e}")
        cached, is_fresh = load_source_cache("huggingface")
        new_data["huggingface"] = cached
        cache_age = get_cache_age_seconds("huggingface")
        update_source_health("huggingface", False, len(cached), str(e), cache_age_seconds=cache_age)
        print(f"  Using cache: {len(cached)} models" + (" (stale)" if cached and not is_fresh else ""))

    # Blogs
    try:
        new_data["blogs"] = get_blogs()
        save_source_cache("blogs", new_data["blogs"])
        update_source_health("blogs", True, len(new_data["blogs"]))
        print(f"  Blogs: {len(new_data['blogs'])} items")
    except Exception as e:
        print(f"  Blogs failed: {e}")
        cached, is_fresh = load_source_cache("blogs")
        new_data["blogs"] = cached
        cache_age = get_cache_age_seconds("blogs")
        update_source_health("blogs", False, len(cached), str(e), cache_age_seconds=cache_age)
        print(f"  Using cache: {len(cached)} items" + (" (stale)" if cached and not is_fresh else ""))

    # Papers
    try:
        new_data["papers"] = get_arxiv()
        save_source_cache("papers", new_data["papers"])
        update_source_health("papers", True, len(new_data["papers"]))
        print(f"  Papers: {len(new_data['papers'])} items")
    except Exception as e:
        print(f"  Papers failed: {e}")
        cached, is_fresh = load_source_cache("papers")
        new_data["papers"] = cached
        cache_age = get_cache_age_seconds("papers")
        update_source_health("papers", False, len(cached), str(e), cache_age_seconds=cache_age)
        print(f"  Using cache: {len(cached)} papers" + (" (stale)" if cached and not is_fresh else ""))

    # HackerNews
    try:
        new_data["hackernews"] = get_hackernews()
        save_source_cache("hackernews", new_data["hackernews"])
        update_source_health("hackernews", True, len(new_data["hackernews"]))
        print(f"  HackerNews: {len(new_data['hackernews'])} items")
    except Exception as e:
        print(f"  HackerNews failed: {e}")
        cached, is_fresh = load_source_cache("hackernews")
        new_data["hackernews"] = cached
        cache_age = get_cache_age_seconds("hackernews")
        update_source_health("hackernews", False, len(cached), str(e), cache_age_seconds=cache_age)
        print(f"  Using cache: {len(cached)} items" + (" (stale)" if cached and not is_fresh else ""))

    # Deduplicate
    global _seen_fingerprints
    _seen_fingerprints = set()
    for key in ["youtube", "github", "huggingface", "blogs", "papers", "hackernews"]:
        items = new_data.get(key, [])
        deduplicated = [item for item in items if not is_duplicate(item)]
        new_data[key] = deduplicated
        print(f"  {key}: {len(deduplicated)} after dedup")

    # Merge with 7-day retention
    combined = merge_weekly_data(history, new_data)

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(combined, f, indent=2)

    print(
        f"Done: YT:{len(combined['youtube'])} GH:{len(combined['github'])} HF:{len(combined['huggingface'])} Blogs:{len(combined['blogs'])} Papers:{len(combined['papers'])} HN:{len(combined.get('hackernews', []))}"
    )
    return combined["last_updated"]


def merge_weekly_data(history, new_data):
    """Keep only items from last 7 days, merge with new fetch"""
    from datetime import timedelta

    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)

    # Combined data starts with new fetch
    combined = new_data.copy()

    # Merge historical items that are within 7 days
    for key in ["youtube", "github", "huggingface", "blogs", "papers", "hackernews"]:
        if key not in combined:
            combined[key] = []

        old_items = history.get(key, [])
        for item in old_items:
            # Check if item is from last 7 days
            published = item.get("published", "")
            if published:
                try:
                    # Parse ISO date
                    item_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if item_date.tzinfo:
                        item_date = item_date.replace(tzinfo=None)
                    if item_date >= seven_days_ago:
                        # Check for duplicates (same title/url)
                        if not any(
                            existing.get("title") == item.get("title")
                            for existing in combined[key]
                        ):
                            combined[key].append(item)
                except:
                    pass

    return combined


# Import IntelligenceDB for unified source health (avoid duplicate schema)
def get_intel_db():
    """Get IntelligenceDB instance"""
    from data_models import IntelligenceDB
    return IntelligenceDB(DB_PATH)


def update_source_health(source_name: str, success: bool, item_count: int = 0, 
                         failure_reason: str = None, cache_age_seconds: int = 0):
    """Update source health using IntelligenceDB (unified schema)"""
    try:
        db = get_intel_db()
        using_cache = not success and item_count > 0
        db.update_source_health(source_name, success, item_count, failure_reason, using_cache, cache_age_seconds)
    except Exception as e:
        print(f"  Warning: Could not update source health: {e}")


if __name__ == "__main__":
    fetch_all()
