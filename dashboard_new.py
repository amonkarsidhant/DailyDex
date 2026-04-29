#!/usr/bin/env python3
"""DailyDex - Flask Dashboard"""

import json
import os
import sys
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
app.url_map.merge_slashes = False

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "intelligence.db"))
CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(DATA_DIR, "cache"))
DIGEST_DIR = os.environ.get("DIGEST_DIR", os.path.join(DATA_DIR, "digests"))
DATA_FILE = os.environ.get("DATA_FILE", os.path.join(DATA_DIR, "data.json"))
CONFIG_FILE = os.environ.get("CONFIG_FILE", os.path.join(BASE_DIR, "config.json"))
SCORED_DATA_FILE = os.environ.get("SCORED_DATA_FILE", os.path.join(DATA_DIR, "data_scored.json"))
CACHE_TTL_SECONDS = 12 * 3600
SOURCE_META = [
    ("github", "GitHub"),
    ("huggingface", "HuggingFace"),
    ("youtube", "YouTube"),
    ("blogs", "Blogs"),
    ("papers", "arXiv"),
]
SAVED_STATUS_ORDER = [
    ("to_read", "To Read"),
    ("to_test", "To Test"),
    ("testing", "Testing"),
    ("useful", "Useful"),
    ("discarded", "Discarded"),
]

# Try importing our modules
try:
    from scoring_engine import SignalScorer
    from data_models import IntelligenceDB, IntelligenceJSON
    HAS_SCORE_ENGINE = True
except Exception as e:
    print(f"Warning: Could not load scoring engine: {e}")
    HAS_SCORE_ENGINE = False

# Initialize data stores
if HAS_SCORE_ENGINE:
    try:
        intel_db = IntelligenceDB()
        intel_json = IntelligenceJSON()
    except Exception as e:
        print(f"Warning: Could not initialize data stores: {e}")
        intel_db = None
        intel_json = None
else:
    intel_db = None
    intel_json = None


def load_data():
    """Load data from JSON file"""
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"github": [], "huggingface": [], "youtube": [], "blogs": [], "papers": []}


def ensure_parent_dir(path: str) -> None:
    """Create a parent directory for a file path when needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def parse_timestamp(value: str):
    """Parse an ISO timestamp when available."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def format_timestamp(value: str) -> str:
    """Format an ISO timestamp for UI display."""
    parsed = parse_timestamp(value)
    if not parsed:
        return "Never"
    return parsed.strftime("%Y-%m-%d %H:%M")


def humanize_seconds(seconds: int) -> str:
    """Render a compact age string."""
    if not seconds:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def humanize_timestamp(value: str) -> str:
    """Render a relative time string for a timestamp."""
    parsed = parse_timestamp(value)
    if not parsed:
        return "Never"
    return humanize_seconds(int((datetime.now() - parsed).total_seconds()))


def generate_scored_data(raw_data=None):
    """Generate and persist scored data from the latest raw fetch."""
    if not HAS_SCORE_ENGINE:
        return load_data()

    data = raw_data or load_data()
    scorer = SignalScorer()
    scored_data = scorer.score_all_items(data)
    scored_data["executive_brief"] = scorer.generate_executive_brief(scored_data)
    ensure_parent_dir(SCORED_DATA_FILE)
    with open(SCORED_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(scored_data, f, indent=2)
    return scored_data


def load_scored_data(force: bool = False):
    """Load scored data, regenerating when raw data changed."""
    raw_data = load_data()
    if not HAS_SCORE_ENGINE:
        return raw_data

    try:
        if not force and os.path.exists(SCORED_DATA_FILE):
            with open(SCORED_DATA_FILE, encoding="utf-8") as f:
                scored = json.load(f)
            if scored.get("last_updated") == raw_data.get("last_updated"):
                return scored
        return generate_scored_data(raw_data)
    except Exception as e:
        print(f"Error generating scored data: {e}")
        return raw_data


def filter_ignored_items(items, ignored_urls):
    """Hide ignored items from dashboard sections."""
    return [item for item in items if item.get("url") not in ignored_urls]


def status_key_for_source(source: dict) -> str:
    """Calculate a user-facing source status."""
    last_success = parse_timestamp(source.get("last_success"))
    using_cache = bool(source.get("using_cache"))
    cache_age_seconds = int(source.get("cache_age_seconds") or 0)

    if using_cache and cache_age_seconds >= CACHE_TTL_SECONDS:
        return "stale"
    if using_cache:
        return "cache"
    if source.get("status") == "failed":
        return "failed"
    if last_success and (datetime.now() - last_success).total_seconds() > CACHE_TTL_SECONDS:
        return "stale"
    if last_success:
        return "ok"
    return "unknown"


def build_source_status_cards(source_health):
    """Build compact status cards for the dashboard."""
    source_map = {row.get("source_name"): row for row in source_health}
    cards = []

    for source_name, label in SOURCE_META:
        row = source_map.get(source_name, {})
        status_key = status_key_for_source(row)
        cache_age_seconds = int(row.get("cache_age_seconds") or 0)
        item_count = int(row.get("item_count") or 0)
        last_success_display = format_timestamp(row.get("last_success"))
        last_attempt_display = format_timestamp(row.get("last_attempt") or row.get("last_failure"))
        cache_age_display = humanize_seconds(cache_age_seconds) if cache_age_seconds else "Live data"

        if status_key == "ok":
            summary = f"Fresh data, {item_count} item{'s' if item_count != 1 else ''}."
        elif status_key == "cache":
            summary = f"Using cached data from {cache_age_display}."
        elif status_key == "stale":
            summary = f"Data is stale. Cache age: {cache_age_display}."
        elif status_key == "failed":
            summary = row.get("failure_reason") or "Latest fetch failed."
        else:
            summary = "No successful fetch recorded yet."

        cards.append({
            "source_name": source_name,
            "label": label,
            "status_key": status_key,
            "status_label": {
                "ok": "OK",
                "cache": "Using Cache",
                "stale": "Stale",
                "failed": "Failed",
                "unknown": "Unknown",
            }[status_key],
            "status_class": f"status-{status_key}",
            "item_count": item_count,
            "last_success": row.get("last_success"),
            "last_attempt": row.get("last_attempt"),
            "last_success_display": last_success_display,
            "last_success_relative": humanize_timestamp(row.get("last_success")),
            "last_attempt_display": last_attempt_display,
            "last_attempt_relative": humanize_timestamp(row.get("last_attempt") or row.get("last_failure")),
            "failure_reason": row.get("failure_reason"),
            "cache_age_display": cache_age_display,
            "using_cache": bool(row.get("using_cache")),
            "summary": summary,
        })

    return cards


def summarize_daily_status(source_cards):
    """Create a single trust summary for the dashboard."""
    failing = [card for card in source_cards if card["status_key"] == "failed"]
    cached = [card for card in source_cards if card["status_key"] == "cache"]
    stale = [card for card in source_cards if card["status_key"] == "stale"]
    healthy = [card for card in source_cards if card["status_key"] == "ok"]
    today = datetime.now().date()

    new_items_today = 0
    for card in source_cards:
        last_success = parse_timestamp(card.get("last_success"))
        if last_success and last_success.date() == today:
            new_items_today += card.get("item_count", 0)

    if failing:
        freshness_message = f"{len(failing)} source{'s are' if len(failing) != 1 else ' is'} failing."
        trust_state = "Attention needed"
    elif stale or cached:
        freshness_message = f"Showing cached or stale data for {len(stale) + len(cached)} source{'s' if len(stale) + len(cached) != 1 else ''}."
        trust_state = "Partial freshness"
    elif healthy:
        freshness_message = "All core sources fetched successfully."
        trust_state = "Fresh data"
    else:
        freshness_message = "Waiting for the first successful refresh."
        trust_state = "No recent data"

    return {
        "new_items_today": new_items_today,
        "trust_state": trust_state,
        "freshness_message": freshness_message,
        "has_failures": bool(failing),
        "has_partial_data": bool(stale or cached),
    }


def why_it_matters_to_me(item: dict) -> str:
    """Generate a short personal relevance note."""
    reasons = []
    categories = [category.lower() for category in item.get("categories", [])]

    if item.get("pi_suitability") in ["yes", "partial"]:
        reasons.append("Runnable in the Raspberry Pi / local lab workflow.")
    if item.get("agentic_relevance", 0) >= 40 or "agent" in categories:
        reasons.append("Useful for coding-agent experimentation.")
    if item.get("source_type") == "github":
        reasons.append("Hands-on repo candidate rather than just background reading.")
    elif item.get("source_type") == "huggingface":
        reasons.append("Worth evaluating for local model workflows.")
    elif item.get("source_type") == "papers":
        reasons.append("Research worth saving before implementation decisions.")

    return " ".join(reasons[:2]) or "Keeps the daily briefing aligned with practical AI work."


def recommended_action_text(item: dict) -> str:
    """Turn the action label into a short decisive recommendation."""
    action = item.get("action", "read")
    if action == "try":
        return "Try this weekend"
    if action == "save":
        return "Save and revisit"
    if action == "read":
        return "Read for context"
    return "Monitor only"


def install_command_for_item(item: dict) -> str:
    """Infer a practical first command when possible."""
    source_type = item.get("source_type")
    url = item.get("url", "")
    if source_type == "github" and url:
        return f"git clone {url}"
    if source_type == "huggingface" and item.get("is_local_compatible"):
        return f"ollama run {item.get('title', '').split('/')[-1]}"
    return "Open the link and follow the setup notes"


def build_top_items(scored_data):
    """Build the decisive top-five briefing cards."""
    top_items = []
    for source_type in ["github", "huggingface", "youtube", "blogs", "papers"]:
        for item in scored_data.get(source_type, []):
            if item.get("signal_score", 0) >= 40:
                enriched = {**item, "source_type": source_type}
                top_items.append(enriched)

    top_items.sort(key=lambda item: item.get("signal_score", 0), reverse=True)
    result = []
    source_labels = dict(SOURCE_META)
    for item in top_items[:5]:
        result.append({
            **item,
            "source_label": source_labels.get(item.get("source_type"), item.get("source_type", "unknown")),
            "why_it_matters": item.get("score_reason", item.get("score_label", "High signal item")),
            "why_it_matters_to_me": why_it_matters_to_me(item),
            "recommended_action": recommended_action_text(item),
        })
    return result


def find_correlations(scored_data):
    """Find topics that appear across multiple sources."""
    topic_sources = {}
    
    keywords_to_track = [
        "agent", "claude", "gpt", "ollama", "llama", "mcp", "cursor", "windsurf",
        "GPT", "AI", "ML", "machine learning", "model", "local", "raspberry", "pi",
        "rag", "embedding", "vector", "fine-tuning", "benchmark", "open weights",
        "reasoning", " Chain", "Function calling", "tool", "computer use", "computer use",
        "multi-modal", "vision", "voice", "speech", "code", "coding", "dev",
        "security", "jailbreak", "safety", "alignment", " RL",
    ]
    
    for source_type, items in scored_data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            title = (item.get("title", "") + " " + item.get("description", "")).lower()
            categories = item.get("categories", [])
            for keyword in keywords_to_track:
                if keyword.lower() in title or keyword.lower() in str(categories).lower():
                    if keyword not in topic_sources:
                        topic_sources[keyword] = []
                    topic_sources[keyword].append({
                        "source": source_type,
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "signal_score": item.get("signal_score", 0)
                    })
    
    correlations = []
    for topic, items in topic_sources.items():
        unique_sources = set(i["source"] for i in items)
        if len(unique_sources) >= 2:
            correlations.append({
                "topic": topic,
                "sources": list(unique_sources),
                "item_list": sorted(items, key=lambda x: x.get("signal_score", 0), reverse=True)[:3]
            })
    
    correlations.sort(key=lambda x: (len(x["sources"]), max(i["signal_score"] for i in x["item_list"])), reverse=True)
    return correlations[:8]


def build_try_this_weekend(scored_data):
    """Pick a small list of practical experiments."""
    candidates = []
    for source_type in ["github", "huggingface"]:
        for item in scored_data.get(source_type, []):
            pi_suitability = item.get("pi_suitability", "partial" if source_type == "github" else "yes")
            if pi_suitability == "no":
                continue
            if item.get("action") == "try" or item.get("local_ai_relevance", 0) >= 35 or item.get("is_local_compatible"):
                candidates.append({**item, "source_type": source_type, "pi_suitability": pi_suitability})

    candidates.sort(
        key=lambda item: (
            item.get("signal_score", 0),
            15 if item.get("source_type") == "github" else 10,
            10 if item.get("action") == "try" else 0,
        ),
        reverse=True,
    )

    weekend = []
    seen_urls = set()
    for item in candidates:
        url = item.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        weekend.append({
            **item,
            "source_label": dict(SOURCE_META).get(item.get("source_type"), item.get("source_type")),
            "why_worth_trying": why_it_matters_to_me(item),
            "setup_difficulty": item.get("installation_complexity", "easy" if item.get("source_type") == "huggingface" else "medium"),
            "install_command": install_command_for_item(item),
        })
        if len(weekend) == 3:
            break

    return weekend


def build_topic_heatmap(scored_data):
    """Build topic frequency heatmap by source."""
    topic_sources = {}
    source_list = ["github", "huggingface", "youtube", "blogs", "papers"]
    
    keywords = [
        "agent", "claude", "gpt", "ollama", "llama", "mcp", "cursor", "windsurf",
        "model", "AI", "ML", "local", "rag", "embedding", "vector",
        "fine-tuning", "benchmark", "reasoning", "function", "tool",
        "computer use", "multi-modal", "vision", "code", "coding",
        "dev", "security", "safety", "alignment", " RL",
    ]
    
    for source_type in source_list:
        source_items = scored_data.get(source_type, [])
        if not isinstance(source_items, list):
            continue
        for keyword in keywords:
            count = 0
            for item in source_items:
                title = (item.get("title", "") + " " + item.get("description", "")).lower()
                if keyword.lower() in title:
                    count += 1
            if count > 0:
                if keyword not in topic_sources:
                    topic_sources[keyword] = {src: 0 for src in source_list}
                topic_sources[keyword][source_type] = count
    
    heatmap_data = []
    for topic, counts in topic_sources.items():
        total = sum(counts.values())
        if total >= 2:
            heatmap_data.append({
                "topic": topic,
                "counts": counts,
                "total": total
            })

    heatmap_data.sort(key=lambda x: x["total"], reverse=True)
    return heatmap_data[:12]


def build_saved_groups(saved_items):
    """Group saved items into a small action board."""
    groups = []
    for status_key, label in SAVED_STATUS_ORDER:
        group_entries = []
        for item in saved_items:
            if item.get("status") == status_key:
                group_entries.append({
                    **item,
                    "created_display": format_timestamp(item.get("created_at")),
                })
        groups.append({"key": status_key, "label": label, "group_entries": group_entries})
    return groups


def build_source_health_response():
    """Return normalized source health cards and a dashboard summary."""
    raw_source_health = []
    if intel_db:
        try:
            raw_source_health = intel_db.get_source_health()
        except Exception:
            raw_source_health = []
    source_cards = build_source_status_cards(raw_source_health)
    return source_cards, summarize_daily_status(source_cards)


def build_status_warning(source_cards):
    """Generate a compact issue warning when something needs attention."""
    for card in source_cards:
        if card["status_key"] == "failed":
            return f"{card['label']} failed. {card['summary']}"
        if card["status_key"] in ["cache", "stale"]:
            return f"{card['label']} is showing cached data from {card['cache_age_display']}."
    return ""


def build_chart_payload(scored_data, saved_items, source_status_cards):
    """Build chart data from live dashboard content instead of mock values."""
    source_labels = [label for _, label in SOURCE_META]
    source_map = {card.get("source_name"): card for card in source_status_cards}
    status_scores = {"ok": 100, "cache": 70, "stale": 40, "failed": 10, "unknown": 0}

    trust_values = []
    new_values = []
    signal_values = []
    avg_signal_values = []

    for source_name, _label in SOURCE_META:
        source_items = scored_data.get(source_name, [])
        source_card = source_map.get(source_name, {})
        trust_values.append(status_scores.get(source_card.get("status_key", "unknown"), 0))
        new_values.append(int(source_card.get("item_count") or len(source_items) or 0))
        high_signal = [item for item in source_items if (item.get("signal_score") or 0) >= 60]
        signal_values.append(len(high_signal))
        if source_items:
            avg_signal = sum(item.get("signal_score", 0) for item in source_items) / max(len(source_items), 1)
            avg_signal_values.append(round(avg_signal, 1))
        else:
            avg_signal_values.append(0)

    saved_status_counts = Counter(item.get("status") or "to_read" for item in saved_items)
    saved_status_labels = [label for _, label in SAVED_STATUS_ORDER]
    saved_status_values = [saved_status_counts.get(key, 0) for key, _ in SAVED_STATUS_ORDER]

    max_items = max(new_values) if new_values else 0
    normalized_volume = [round((value / max_items) * 100, 1) if max_items else 0 for value in new_values]

    category_counts = Counter()
    category_score_totals = defaultdict(int)
    category_score_counts = defaultdict(int)
    for source_name, _label in SOURCE_META:
        for item in scored_data.get(source_name, []):
            categories = item.get("categories") or ["Uncategorized"]
            for raw_category in categories:
                category = (raw_category or "Uncategorized").replace("-", " ").strip().title()
                category_counts[category] += 1
                category_score_totals[category] += int(item.get("signal_score") or 0)
                category_score_counts[category] += 1

    top_categories = category_counts.most_common(6)
    category_labels = [name for name, _count in top_categories]
    category_values = [count for _name, count in top_categories]
    category_scores = [
        round(category_score_totals[name] / max(category_score_counts[name], 1), 1)
        for name, _count in top_categories
    ]

    status_axis = {
        "to_read": 20,
        "to_test": 40,
        "testing": 60,
        "useful": 80,
        "discarded": 100,
    }
    source_bubbles = defaultdict(list)
    for item in saved_items[:30]:
        source_type = item.get("source_type") or "other"
        tags = item.get("tags") or []
        source_bubbles[source_type].append({
            "x": int(item.get("signal_score") or 0),
            "y": status_axis.get(item.get("status") or "to_read", 20),
            "r": min(18, max(6, 6 + len(tags) * 2 + (4 if item.get("notes") else 0))),
            "title": item.get("title", "Saved item"),
            "status": item.get("status", "to_read"),
            "source": item.get("source", source_type),
        })

    source_activity_statuses = [
        source_map.get(source_name, {}).get("status_label", "Unknown")
        for source_name, _label in SOURCE_META
    ]

    return {
        "sparklines": {
            "trust": {"labels": source_labels, "values": trust_values},
            "new": {"labels": source_labels, "values": new_values},
            "signal": {"labels": source_labels, "values": signal_values},
            "saved": {"labels": saved_status_labels, "values": saved_status_values},
        },
        "radar": {
            "labels": source_labels,
            "datasets": [
                {"label": "Average Signal", "values": avg_signal_values},
                {"label": "Relative Volume", "values": normalized_volume},
            ],
        },
        "source_activity": {
            "labels": source_labels,
            "values": new_values,
            "statuses": source_activity_statuses,
        },
        "categories": {
            "labels": category_labels,
            "values": category_values,
            "scores": category_scores,
        },
        "saved_workflow": {
            "datasets": dict(source_bubbles),
            "status_axis": {
                "labels": [label for _key, label in SAVED_STATUS_ORDER],
                "values": [status_axis[key] for key, _label in SAVED_STATUS_ORDER],
            },
        },
    }


def build_dashboard_state(scored_data, daily_summary, source_status_cards, saved_items, trending_keywords, status_warning):
    """Create a compact live state payload for the frontend."""
    live_state = {
        "last_updated_raw": scored_data.get("last_updated") or "",
        "last_updated_display": format_timestamp(scored_data.get("last_updated")) if scored_data.get("last_updated") else "Unknown",
        "live_interval_seconds": 60,
        "daily_summary": daily_summary,
        "status_warning": status_warning,
        "counts": {
            "saved": len(saved_items),
            "top_items": sum(1 for source_name, _label in SOURCE_META for item in scored_data.get(source_name, []) if item.get("signal_score", 0) >= 40),
            "trending": len(trending_keywords),
        },
        "charts": build_chart_payload(scored_data, saved_items, source_status_cards),
    }

    signature_payload = {
        "last_updated_raw": live_state["last_updated_raw"],
        "daily_summary": daily_summary,
        "sources": [
            {
                "source_name": card.get("source_name"),
                "status_key": card.get("status_key"),
                "item_count": card.get("item_count"),
                "cache_age_display": card.get("cache_age_display"),
                "last_success": card.get("last_success"),
            }
            for card in source_status_cards
        ],
        "saved_count": len(saved_items),
        "trends": [
            {"keyword": row.get("keyword"), "count": row.get("count")}
            for row in trending_keywords[:8]
        ],
    }
    live_state["snapshot_id"] = hashlib.sha1(
        json.dumps(signature_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return live_state


def build_dashboard_context():
    """Build the full dashboard context once for HTML and live metadata."""
    scored_data = load_scored_data()

    saved_items = []
    ignored_urls = set()
    new_items = []
    if intel_db:
        try:
            saved_items = intel_db.get_saved_items()
            ignored_urls = {item.get("url") for item in intel_db.get_ignored_items() if item.get("url")}
            
            all_items_for_seen = []
            for source_type, items in scored_data.items():
                if isinstance(items, list):
                    for item in items:
                        all_items_for_seen.append({**item, "source_type": source_type})
            
            new_items = intel_db.get_new_items(all_items_for_seen)
            intel_db.mark_seen_items(all_items_for_seen)
        except Exception as e:
            saved_items = []
            ignored_urls = set()
            new_items = []

    saved_urls = {item.get("url") for item in saved_items if item.get("url")}
    for key, _label in SOURCE_META:
        scored_data[key] = filter_ignored_items(scored_data.get(key, []), ignored_urls)

    source_status_cards, daily_summary = build_source_health_response()
    status_warning = build_status_warning(source_status_cards)

    feed_items = []
    for source_type, items in scored_data.items():
        if source_type in [name for name, _label in SOURCE_META]:
            for item in items:
                if item.get("signal_score", 0) >= 40:
                    feed_items.append({**item, "source_type": source_type})
    feed_items.sort(key=lambda x: x.get("signal_score", 0), reverse=True)

    local_items = [r for r in scored_data.get("github", []) if r.get("pi_suitability") in ["yes", "partial"]]
    local_items.sort(key=lambda x: x.get("signal_score", 0), reverse=True)

    trending_keywords = []
    if intel_db:
        try:
            trending_keywords = intel_db.get_trending_keywords(7)
        except Exception:
            trending_keywords = []

    last_updated = format_timestamp(scored_data.get("last_updated")) if scored_data.get("last_updated") else "Unknown"
    top_items = build_top_items(scored_data)
    weekend_items = build_try_this_weekend(scored_data)
    correlations = find_correlations(scored_data)
    topic_heatmap = build_topic_heatmap(scored_data)
    saved_groups = build_saved_groups(saved_items)
    has_any_data = any(scored_data.get(key) for key, _label in SOURCE_META)
    dashboard_state = build_dashboard_state(
        scored_data,
        daily_summary,
        source_status_cards,
        saved_items,
        trending_keywords,
        status_warning,
    )

    return {
        "github": scored_data.get("github", []),
        "huggingface": scored_data.get("huggingface", []),
        "youtube": scored_data.get("youtube", []),
        "blogs": scored_data.get("blogs", []),
        "papers": scored_data.get("papers", []),
        "correlations": correlations,
        "topic_heatmap": topic_heatmap,
        "feed_items": feed_items[:30],
        "local_items": local_items[:6],
        "saved_items": saved_items,
        "last_updated": last_updated,
        "trending_keywords": trending_keywords,
        "source_status_cards": source_status_cards,
        "daily_summary": daily_summary,
        "status_warning": status_warning,
        "top_items": top_items,
        "weekend_items": weekend_items,
        "saved_groups": saved_groups,
        "saved_urls": saved_urls,
        "new_items": new_items,
        "digest_dir": DIGEST_DIR,
        "today_date": datetime.now().strftime("%Y-%m-%d"),
        "has_any_data": has_any_data,
        "dashboard_state": dashboard_state,
    }




@app.route("/")
def home():
    """Main dashboard page"""
    return render_template("dashboard.html", **build_dashboard_context())


@app.route("/health")
def health():
    """Health check endpoint for Docker"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/api/data")
def api_data():
    """API endpoint for raw data"""
    return jsonify(load_data())


@app.route("/api/scored")
def api_scored():
    """API endpoint for scored data"""
    return jsonify(load_scored_data())


@app.route("/api/save", methods=["POST"])
def api_save():
    """Save an item"""
    if not intel_db:
        return jsonify({"success": False, "error": "Database not available"})
    
    data = request.json
    existing = None
    item_url = data.get("url", "")
    if item_url:
        existing = next((item for item in intel_db.get_saved_items() if item.get("url") == item_url), None)
    item_id = intel_db.save_item({
        "title": data.get("title", ""),
        "url": data.get("url", ""),
        "source": data.get("source", ""),
        "source_type": data.get("source_type", ""),
        "category": data.get("category", ""),
        "signal_score": data.get("signal_score", 0)
    })
    created = existing is None
    return jsonify({
        "success": True,
        "id": item_id,
        "created": created,
        "message": "Saved to your board." if created else "Already saved, updated timestamp.",
    })


@app.route("/api/saved/<int:item_id>", methods=["DELETE"])
def api_delete_saved(item_id):
    """Delete a saved item"""
    if not intel_db:
        return jsonify({"success": False, "error": "Database not available"})
    
    intel_db.delete_item(item_id)
    return jsonify({"success": True, "message": "Saved item removed."})


@app.route("/api/saved/<int:item_id>/status", methods=["PUT"])
def api_update_status(item_id):
    """Update saved item status"""
    if not intel_db:
        return jsonify({"success": False, "error": "Database not available"})
    
    data = request.json
    status = data.get("status", "to_read")
    intel_db.update_status(item_id, status)
    return jsonify({"success": True, "message": f"Status updated to {status}."})


@app.route("/api/saved/<int:item_id>/notes", methods=["PUT"])
def api_update_notes(item_id):
    """Update saved item notes and tags"""
    if not intel_db:
        return jsonify({"success": False, "error": "Database not available"})
    
    data = request.json
    notes = data.get("notes", "")
    tags = data.get("tags", [])
    intel_db.update_notes(item_id, notes, tags)
    return jsonify({"success": True, "message": "Notes and tags updated."})


@app.route("/api/saved")
def api_get_saved():
    """Get all saved items"""
    if not intel_db:
        return jsonify({"items": []})
    
    return jsonify({"items": intel_db.get_saved_items()})


@app.route("/api/ignore", methods=["POST"])
def api_ignore():
    """Ignore/hide an item"""
    if not intel_db:
        return jsonify({"success": False, "error": "Database not available"})
    
    data = request.json
    url = data.get("url", "")
    title = data.get("title", "")
    source_type = data.get("source_type", "")
    
    intel_db.ignore_item(url, title, source_type)
    return jsonify({"success": True, "message": "Item ignored and hidden."})


@app.route("/api/ignored")
def api_get_ignored():
    """Get all ignored items"""
    if not intel_db:
        return jsonify({"items": []})
    
    return jsonify({"items": intel_db.get_ignored_items()})


@app.route("/api/track", methods=["POST"])
def api_track():
    """Add a topic to track"""
    if not intel_db:
        return jsonify({"success": False, "error": "Database not available"})
    
    data = request.json
    topic = data.get("topic", "")
    reason = data.get("reason", "")
    
    if topic:
        existing_topics = {item.get("topic") for item in intel_db.get_tracked_topics()}
        intel_db.add_tracked_topic(topic, reason)
        return jsonify({
            "success": True,
            "created": topic not in existing_topics,
            "message": "Tracking topic." if topic not in existing_topics else "Topic already tracked.",
        })
    
    return jsonify({"success": False, "error": "No topic provided"})


@app.route("/api/track", methods=["GET"])
def api_get_tracked():
    """Get all tracked topics"""
    if not intel_db:
        return jsonify({"topics": []})
    
    return jsonify({"topics": intel_db.get_tracked_topics()})


@app.route("/api/track/<int:topic_id>", methods=["DELETE"])
def api_delete_track(topic_id):
    """Remove a tracked topic"""
    if not intel_db:
        return jsonify({"success": False})
    
    intel_db.remove_tracked_topic(topic_id)
    return jsonify({"success": True, "message": "Tracked topic removed."})


@app.route("/api/source-health")
def api_source_health():
    """Get source health status"""
    source_cards, daily_summary = build_source_health_response()
    return jsonify({"sources": source_cards, "summary": daily_summary})


@app.route("/api/dashboard-meta")
def api_dashboard_meta():
    """Return a lightweight snapshot for live dashboard refresh checks."""
    state = build_dashboard_context()["dashboard_state"]
    return jsonify({
        "snapshot_id": state["snapshot_id"],
        "last_updated_raw": state["last_updated_raw"],
        "last_updated_display": state["last_updated_display"],
        "live_interval_seconds": state["live_interval_seconds"],
        "daily_summary": state["daily_summary"],
        "status_warning": state["status_warning"],
        "counts": state["counts"],
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Run a manual refresh without wiping existing data on failure."""
    previous_data = load_data()
    try:
        from fetch_news import fetch_all

        fetch_all()
        scored_data = load_scored_data(force=True)
        source_cards, daily_summary = build_source_health_response()
        status = "ok"
        if any(card["status_key"] == "failed" for card in source_cards):
            status = "failed"
        elif any(card["status_key"] in ["cache", "stale"] for card in source_cards):
            status = "partial"

        return jsonify({
            "status": status,
            "last_updated": format_timestamp(scored_data.get("last_updated")),
            "source_health": source_cards,
            "summary": daily_summary,
            "message": daily_summary["freshness_message"],
        })
    except Exception as exc:
        source_cards, daily_summary = build_source_health_response()
        ensure_parent_dir(DATA_FILE)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(previous_data, f, indent=2)
        return jsonify({
            "status": "failed",
            "last_updated": format_timestamp(previous_data.get("last_updated")),
            "source_health": source_cards,
            "summary": daily_summary,
            "message": f"Refresh failed. Existing data preserved. {exc}",
        })


@app.route("/api/llm-summarize", methods=["POST"])
def api_llm_summarize():
    """Summarize an item using Ollama"""
    data = request.json
    text = data.get("text", "")
    item_type = data.get("type", "general")
    
    ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "minimax-m2.5:cloud")
    
    prompt = f"""Analyze this AI {item_type} and return JSON:
{{
  "summary": "2-3 sentence summary",
  "why_matters": "why this is important",
  "category": "one word category",
  "signal_score": 0-100,
  "action": "read|try|save|ignore",
  "pi_suitable": "yes|partial|no"
}}
Content: {text[:500]}
"""
    
    try:
        import requests as req
        resp = req.post(f"{ollama_url}/api/generate", json={"model": model, "prompt": prompt, "format": "json"}, timeout=30)
        if resp.status_code == 200:
            result = resp.json()
            return jsonify({"success": True, "summary": json.loads(result.get("response", "{}"))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
    return jsonify({"success": False, "error": "Ollama not available"})


@app.route("/api/digest")
def api_digest():
    """Generate and return daily digest"""
    if not HAS_SCORE_ENGINE:
        return jsonify({"error": "Scoring engine not available"}), 500

    try:
        from digest_generator import DailyDigestGenerator

        generator = DailyDigestGenerator()
        data = load_data()
        digest = generator.generate_digest(data)
        digest_path = os.path.join(DIGEST_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.md")
        return jsonify({
            "digest": digest,
            "path": digest_path,
            "message": f"Digest saved to {digest_path}.",
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=True)
