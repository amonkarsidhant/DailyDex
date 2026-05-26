#!/usr/bin/env python3
"""DailyDex - Flask Dashboard"""

import json
import os
import sys
import time
import uuid
import queue
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, Response, stream_with_context

from creator_intelligence import (
    CREATOR_STATUS_ORDER,
    build_content_opportunities,
    build_creator_brief,
    build_creator_digest,
    build_creator_saved_groups,
    build_research_pack,
    build_topic_clusters,
    enrich_scored_data_with_creator_fields,
    snapshot_clusters,
    slugify_topic as _ci_slug,
)

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
RESEARCH_PACK_DIR = os.environ.get("RESEARCH_PACK_DIR", os.path.join(DATA_DIR, "research_packs"))
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

try:
    from creator_enricher import EnrichmentService, content_hash as creator_content_hash
    enrichment_service = EnrichmentService(intel_db)
    # Multi-worker deployments (e.g. gunicorn -w N>1) must designate one worker
    # as primary to avoid spawning N independent enricher threads that all try
    # to dequeue the same hash and run duplicate Gemini subprocesses.
    if os.environ.get("CREATOR_ENRICHER_PRIMARY", "1") == "1":
        enrichment_service.start()
    else:
        print("Creator enrichment worker is in standby mode (CREATOR_ENRICHER_PRIMARY=0).")
except Exception as e:
    print(f"Warning: Could not start creator enrichment worker: {e}")
    enrichment_service = None
    creator_content_hash = None

# Phase 2: typed multi-agent runner with live SSE event stream.
try:
    from creator_enricher import AgentRunner
    agent_runner = AgentRunner(intel_db) if intel_db is not None else None
except Exception as e:
    print(f"Warning: Could not start agent runner: {e}")
    agent_runner = None


def _top_items_for_enrichment(scored_data, limit: int = 20):
    """Pick the highest-signal items across sources for background enrichment."""
    pool = []
    for source_type in ("github", "huggingface", "youtube", "blogs", "papers"):
        for item in scored_data.get(source_type, []) or []:
            score = max(
                int(item.get("signal_score") or 0),
                int(item.get("creator_score") or 0),
            )
            if score < 40:
                continue
            pool.append((score, item))
    pool.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in pool[:limit]]


def load_data():
    """Load data from JSON file"""
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"github": [], "huggingface": [], "youtube": [], "blogs": [], "papers": []}


def load_config():
    """Load configuration including variant settings"""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def get_variant_info():
    """Get current variant info from config"""
    config = load_config()
    variant_key = config.get("variant", "default")
    variants = config.get("variants", {})
    variant = variants.get(variant_key, variants.get("default", {
        "name": "DailyDex",
        "title": "AI Signal Cockpit",
        "focus_keywords": ["agent", "claude", "gpt", "ollama", "llama", "mcp"],
        "description": "General AI news"
    }))
    return {
        "key": variant_key,
        "name": variant.get("name", "DailyDex"),
        "title": variant.get("title", "AI Signal Cockpit"),
        "focus_keywords": variant.get("focus_keywords", []),
        "description": variant.get("description", ""),
        "available_variants": list(variants.keys())
    }


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
    variant_info = get_variant_info()
    scorer = SignalScorer(variant_info=variant_info)
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
                enriched = enrich_scored_data_with_creator_fields(scored, intel_db=intel_db)
                _maybe_enqueue_enrichment(enriched)
                return enriched
        enriched = enrich_scored_data_with_creator_fields(generate_scored_data(raw_data), intel_db=intel_db)
        _maybe_enqueue_enrichment(enriched)
        return enriched
    except Exception as e:
        print(f"Error generating scored data: {e}")
        return raw_data


_enrichment_last_version = {"value": None}


def _maybe_enqueue_enrichment(scored_data):
    """Schedule top items for background LLM enrichment, if worker is running.

    Throttled per scored-data version: avoids re-enqueueing on every page load
    when the underlying source data hasn't changed.
    """
    if enrichment_service is None:
        return
    version = scored_data.get("last_updated") if isinstance(scored_data, dict) else None
    if version and _enrichment_last_version["value"] == version:
        return
    try:
        top = _top_items_for_enrichment(scored_data, limit=20)
        enrichment_service.enqueue_batch(top, limit=20)
        _enrichment_last_version["value"] = version
    except Exception as exc:
        print(f"Enrichment enqueue skipped: {exc}")


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


def build_creator_pipeline_groups(saved_items):
    """Group creator items into a production board."""
    groups = []
    for group in build_creator_saved_groups(saved_items):
        entries = []
        for item in group.get("group_entries", []):
            entries.append({
                **item,
                "created_display": format_timestamp(item.get("created_at")),
            })
        groups.append({**group, "group_entries": entries})
    return groups


def list_research_packs(limit: int = 12):
    """Load recent research packs for Creator Mode."""
    if not os.path.isdir(RESEARCH_PACK_DIR):
        return []
    packs = []
    for filename in sorted(os.listdir(RESEARCH_PACK_DIR), reverse=True):
        if not filename.endswith(".md"):
            continue
        path = os.path.join(RESEARCH_PACK_DIR, filename)
        try:
            with open(path, encoding="utf-8") as handle:
                content = handle.read().strip()
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            packs.append({
                "filename": filename,
                "path": path,
                "title": lines[0].lstrip("# ") if lines else filename,
                "excerpt": lines[1][:180] if len(lines) > 1 else "",
                "updated_at": format_timestamp(datetime.fromtimestamp(os.path.getmtime(path)).isoformat()),
            })
        except Exception:
            continue
        if len(packs) >= limit:
            break
    return packs


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


COCKPIT_SOURCES = {
    "github":      {"key": "github",      "label": "GitHub",       "color": "#7DDE5B", "abbr": "GH"},
    "huggingface": {"key": "huggingface", "label": "Hugging Face", "color": "#FFD021", "abbr": "HF"},
    "youtube":     {"key": "youtube",     "label": "YouTube",      "color": "#FF5A5A", "abbr": "YT"},
    "blogs":       {"key": "blogs",       "label": "Blogs / News", "color": "#62A8FF", "abbr": "BL"},
    "papers":      {"key": "papers",      "label": "arXiv",        "color": "#B084F2", "abbr": "AX"},
}

COCKPIT_PERSONAS = {
    "multi": {"label": "Multi-format", "sub": "YouTube · LinkedIn · Newsletter",
              "hero_title": "What to make today",
              "hero_sub": "Across long-form, shorts, and a LinkedIn carousel — one signal, three surfaces.",
              "cta": "Open today's brief", "kpi_label": "Cross-format opportunities"},
    "shorts": {"label": "Shorts-first", "sub": "TikTok · Reels · YT Shorts",
               "hero_title": "Shorts to film this hour",
               "hero_sub": "Five hooks ranked by tension. Vertical thumbnails ready. Script under 90 words.",
               "cta": "Pick a hook", "kpi_label": "Hooks with > 70 tension score"},
    "newsletter": {"label": "Newsletter writer", "sub": "Substack · Beehiiv · personal blog",
                   "hero_title": "This week's lead story",
                   "hero_sub": "One angle worth 1,200 words, with sourcing and counterpoints already pulled.",
                   "cta": "Open story brief", "kpi_label": "Stories with cross-source proof"},
    "educator": {"label": "Educator", "sub": "Course · workshop · cohort",
                 "hero_title": "Today's teachable moment",
                 "hero_sub": "An idea with shelf-life > 90 days, a demo your students can rebuild, and a clean explainer arc.",
                 "cta": "Open lesson brief", "kpi_label": "Evergreen lessons forming"},
}

_COCKPIT_PIPELINE_LANES = ["idea", "researching", "script_ready", "recording", "published"]


def _cockpit_clusters(scored_data):
    """build_topic_clusters output mapped to the prototype's DD_DATA.clusters shape."""
    clusters = build_topic_clusters(scored_data, intel_db=intel_db)
    out = []
    for c in clusters:
        radar = c.get("radar_coords") or {"x": 0, "y": 0}
        out.append({
            "topic": c["topic"],
            "slug": c.get("slug") or "",
            "source_count": c.get("source_count", 0),
            "sources": c.get("sources", []),
            "average_signal_score": c.get("average_signal_score", 0),
            "creator_score": c.get("creator_score", 0),
            "momentum": c.get("momentum_24h_pct", 0),
            "first_seen_hrs": c.get("first_seen_hrs", 0),
            "angle_x": radar.get("x", 0),
            "angle_y": radar.get("y", 0),
            "pulse": c.get("pulse_24h", [0] * 24),
            "recommended_angle": c.get("recommended_angle", ""),
            "best_content_format": c.get("best_content_format", ""),
            "has_demoable_item": c.get("has_demoable_item", False),
            "why_this_is_a_story": c.get("why_this_is_a_story", ""),
            "related_items": c.get("related_items", []),
        })
    return out


def _synth_titles(cluster):
    """Deterministic title fallback when no opportunity titles exist."""
    topic = cluster.get("topic", "this story")
    return {
        "curiosity": f"What's really happening with {topic}",
        "practical": f"I tested {topic} so you don't have to",
        "contrarian": f"{topic} is not what you think",
        "tutorial": f"Get started with {topic} in 30 minutes",
    }


def _cockpit_title_sets(clusters, opp_by_slug):
    """Title sets keyed by cluster slug so every visible cluster has titles."""
    sets = {}
    for c in clusters[:8]:
        slug = c.get("slug")
        if not slug:
            continue
        opp = opp_by_slug.get(slug)
        titles = (opp or {}).get("suggested_titles") or {}
        if not any(titles.values()):
            titles = _synth_titles(c)
        sets[slug] = {
            "curiosity": titles.get("curiosity", ""),
            "practical": titles.get("practical", ""),
            "contrarian": titles.get("contrarian", ""),
            "tutorial": titles.get("tutorial", ""),
        }
    return sets


def _cockpit_source_health():
    rows = {}
    if intel_db:
        try:
            for r in intel_db.get_source_health():
                rows[r.get("source_name")] = r
        except Exception:
            rows = {}
    out = {}
    for key in COCKPIT_SOURCES:
        r = rows.get(key) or {}
        status = r.get("status", "unknown")
        last_min = None
        stamp = r.get("last_attempt") or r.get("last_success")
        if stamp:
            try:
                dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                last_min = max(0, int((datetime.now() - dt).total_seconds() // 60))
            except Exception:
                last_min = None
        out[key] = {
            "fresh": status == "ok" and (last_min is None or last_min < 30),
            "last_fetch_min": last_min if last_min is not None else 99,
            "items_24h": r.get("item_count", 0),
            "delta": 0,
            "error": r.get("failure_reason") if status in ("failed", "stale", "cache") else None,
        }
    return out


def _cockpit_pipeline(saved_items):
    lanes = {k: [] for k in _COCKPIT_PIPELINE_LANES}
    for item in saved_items:
        status = item.get("status")
        if status not in lanes:
            continue
        lanes[status].append({
            "id": str(item.get("id")),
            "topic": item.get("category") or item.get("topic") or "",
            "working_title": item.get("working_title") or item.get("title") or "",
            "format": item.get("format") or "",
            "effort": item.get("priority") or "medium",
            "creator_score": item.get("creator_score") or item.get("signal_score") or 0,
            "due": item.get("due") or "—",
            "research_pct": item.get("research_pct"),
            "published_at": item.get("published_at"),
            "views": item.get("views"),
            "retention": item.get("retention"),
        })
    return lanes


def _cockpit_calendar():
    """Next 7 days of schedule grouped into the prototype's calendar shape."""
    out = []
    if intel_db is None:
        return out
    today = datetime.now()
    start = today.strftime("%Y-%m-%d")
    end = (today + timedelta(days=6)).strftime("%Y-%m-%d")
    try:
        rows = intel_db.get_schedule_range(start, end)
    except Exception:
        rows = []
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append({"ref": str(r.get("item_id")), "time": r.get("time") or "—",
                                  "kind": r.get("kind")})
    for offset in range(7):
        d = today + timedelta(days=offset)
        key = d.strftime("%Y-%m-%d")
        out.append({"day": d.strftime("%a"), "date": d.day, "items": by_day.get(key, [])})
    return out


def _cockpit_agents():
    if agent_runner is None:
        return []
    snap = agent_runner.snapshot()
    return [{
        "id": a["id"], "name": a["name"], "task": a.get("task", ""),
        "stage": a.get("stage", ""), "progress": a.get("progress", 0),
        "icon": a.get("icon", "⚙️"), "eta_sec": a.get("eta_sec"),
        "logs": a.get("logs", []),
    } for a in snap.get("active", [])]


def _cockpit_thumbnails(clusters, opp_by_slug):
    """Variants for the top clusters (keyed by cluster slug), generated on demand."""
    import hashlib
    from creator_intelligence import generate_thumbnail_variants, serialize_thumbnail_variant
    if intel_db is None:
        return []
    out = []
    for c in clusters[:4]:
        slug = c.get("slug")
        if not slug:
            continue
        opp = opp_by_slug.get(slug)
        if opp and creator_content_hash is not None:
            chash = creator_content_hash(opp)
        else:
            chash = hashlib.sha1(slug.encode("utf-8")).hexdigest()
        existing = intel_db.get_thumbnail_variants(chash)
        if not existing:
            generate_thumbnail_variants(intel_db, chash, topic=c.get("topic"),
                                        count=6, base_item=opp)
            existing = intel_db.get_thumbnail_variants(chash)
        for r in existing:
            v = serialize_thumbnail_variant(r)
            out.append({"id": v["id"], "topic": slug, "text": v["text"],
                        "subtext": v["subtext"], "hue": v["hue"],
                        "ctr": v["ctr_pred"], "kind": v["kind"],
                        "content_hash": chash, "picked": v["picked"]})
    return out


def build_cockpit_data():
    """Server-side DD_DATA payload matching prototype/src/data.js shape."""
    scored_data = load_scored_data()
    if intel_db:
        try:
            snapshot_clusters(scored_data, intel_db)
        except Exception:
            pass
    clusters_raw = build_topic_clusters(scored_data, intel_db=intel_db)
    opportunities = build_content_opportunities(scored_data, clusters_raw)
    opp_by_slug = {}
    for opp in opportunities:
        slug = opp.get("slug") or _ci_slug(opp.get("topic", ""))
        opp_by_slug.setdefault(slug, opp)
    clusters = _cockpit_clusters(scored_data)
    saved_items = intel_db.get_saved_items(pipeline_type="creator") if intel_db else []
    profile = _load_creator_profile_safe()
    persona = profile.get("persona", "multi")
    cop_cfg = profile.get("copilot") or {}
    return {
        "SOURCES": COCKPIT_SOURCES,
        "personas": COCKPIT_PERSONAS,
        "persona": persona if persona in COCKPIT_PERSONAS else "multi",
        "copilotModel": cop_cfg.get("model", ""),
        "clusters": clusters,
        "titleSets": _cockpit_title_sets(clusters, opp_by_slug),
        "sourceHealth": _cockpit_source_health(),
        "agents": _cockpit_agents(),
        "pipeline": _cockpit_pipeline(saved_items),
        "calendar": _cockpit_calendar(),
        "thumbnails": _cockpit_thumbnails(clusters, opp_by_slug),
        "studio": _cockpit_studio(),
    }


def _cockpit_studio():
    """Creator Central: autonomously generated content + provider status."""
    stories = []
    if intel_db:
        try:
            stories = intel_db.studio_list_stories(limit=30)
        except Exception:
            stories = []
    providers = []
    try:
        import cli_registry
        providers = cli_registry.probe().get("providers", [])
    except Exception:
        providers = []
    try:
        import studio as _studio
        skills = [{"format": f, "label": _studio.SKILLS[f]["label"],
                   "icon": _studio.SKILLS[f]["icon"]} for f in _studio.FORMAT_ORDER]
    except Exception:
        skills = []
    return {"stories": stories, "providers": providers, "skills": skills}


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
    variant_info = get_variant_info()
    creator_mode = variant_info.get("key") == "creator"

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
                    feed_items.append({
                        **item,
                        "source_type": source_type,
                        "score_breakdown": item.get("score_breakdown", {}),
                        "why": item.get("why", ""),
                        "score_label": item.get("score_label", "Interesting")
                    })
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
    if intel_db:
        try:
            snapshot_clusters(scored_data, intel_db)
        except Exception as e:
            print(f"Warning: cluster snapshot failed: {e}")
    creator_clusters = build_topic_clusters(scored_data, intel_db=intel_db)
    creator_opportunities = build_content_opportunities(scored_data, creator_clusters)
    creator_brief = build_creator_brief(creator_opportunities, creator_clusters, saved_items)
    creator_saved_groups = build_creator_pipeline_groups(saved_items)
    research_packs = list_research_packs()
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
        "creator_saved_groups": creator_saved_groups,
        "saved_urls": saved_urls,
        "new_items": new_items,
        "digest_dir": DIGEST_DIR,
        "research_pack_dir": RESEARCH_PACK_DIR,
        "today_date": datetime.now().strftime("%Y-%m-%d"),
        "has_any_data": has_any_data,
        "dashboard_state": dashboard_state,
        "variant_info": variant_info,
        "creator_mode": creator_mode,
        "creator_clusters": creator_clusters,
        "creator_opportunities": creator_opportunities,
        "creator_brief": creator_brief,
        "research_packs": research_packs,
    }


@app.route("/api/variant", methods=["GET", "POST"])
def api_variant():
    """Get or set the current variant"""
    config = load_config()
    variants = config.get("variants", {})
    
    if request.method == "POST":
        data = request.get_json()
        variant_key = data.get("variant")
        if variant_key in variants:
            config["variant"] = variant_key
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            return jsonify({"success": True, "variant": variant_key})
        return jsonify({"success": False, "error": "Invalid variant"}), 400
    
    current = config.get("variant", "default")
    return jsonify({
        "current": current,
        "variants": [{"key": k, "name": v.get("name"), "description": v.get("description")} for k, v in variants.items()]
    })




@app.route("/")
@app.route("/cockpit")
def home():
    """Creator Cockpit — the homepage. New React UI mounted via CDN, hydrated
    server-side from the same data pipeline the classic dashboard uses."""
    try:
        dd_data = build_cockpit_data()
    except Exception as e:
        print(f"Warning: cockpit data build failed: {e}")
        dd_data = {"SOURCES": COCKPIT_SOURCES, "personas": COCKPIT_PERSONAS,
                   "persona": "multi", "clusters": [], "titleSets": {},
                   "sourceHealth": {}, "agents": [], "pipeline": {},
                   "calendar": [], "thumbnails": []}
    return render_template("cockpit.html", dd_data=dd_data)


@app.route("/classic")
def classic_dashboard():
    """The original DailyDex dashboard, kept for reference."""
    return render_template("dashboard.html", **build_dashboard_context())


@app.route("/api/cockpit-data")
def api_cockpit_data():
    """JSON DD_DATA payload — lets the UI refresh without a full reload."""
    return jsonify(build_cockpit_data())


# ── Creator Central (Studio) ─────────────────────────────────────────────
_studio_run_state = {"running": False, "started_at": None, "last": None}


@app.route("/api/studio")
def api_studio():
    """List autonomously generated content + detected providers + skills."""
    return jsonify(_cockpit_studio() | {"run": _studio_run_state})


@app.route("/api/studio/run", methods=["POST"])
def api_studio_run():
    """Kick the autonomous content factory in the background."""
    if _studio_run_state["running"]:
        return jsonify({"status": "already_running"}), 409
    top_n = int((request.get_json(silent=True) or {}).get("top_n", 0)) or None

    def _runner():
        _studio_run_state.update(running=True, started_at=datetime.now().isoformat())
        try:
            import studio_job
            _studio_run_state["last"] = studio_job.run(intel_db=intel_db, top_n=top_n)
        except Exception as exc:  # noqa: BLE001
            _studio_run_state["last"] = {"ok": False, "error": str(exc)}
        finally:
            _studio_run_state["running"] = False

    threading.Thread(target=_runner, name="studio-run", daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/studio/<story_key>/<fmt>/regenerate", methods=["POST"])
def api_studio_regenerate(story_key, fmt):
    """Regenerate one format for one story, reusing its stored research."""
    if intel_db is None:
        return jsonify({"error": "no_db"}), 503
    rows = intel_db.studio_get_story(story_key)
    row = next((r for r in rows if r["fmt"] == fmt), None)
    if not row:
        return jsonify({"error": "not_found"}), 404
    import studio
    prefer = (request.get_json(silent=True) or {}).get("provider")
    intel_db.studio_set_status(story_key, row["topic"], fmt, "generating")
    result = studio.generate_format(fmt, row.get("research") or "", prefer=prefer)
    intel_db.studio_save_result(story_key, row["topic"], fmt, result)
    return jsonify({"ok": result["ok"], "format": fmt, "provider": result.get("provider"),
                    "body": result.get("body", "")})


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


@app.route("/api/clusters")
def api_clusters():
    """Creator-cockpit clusters with Phase-1 trend fields (pulse/momentum/radar)."""
    scored_data = load_scored_data()
    if intel_db:
        try:
            snapshot_clusters(scored_data, intel_db)
        except Exception as e:
            print(f"Warning: cluster snapshot failed: {e}")
    clusters = build_topic_clusters(scored_data, intel_db=intel_db)
    return jsonify({"clusters": clusters})


# ── Phase 2: agents ──────────────────────────────────────────────────────

@app.route("/api/agents/dispatch", methods=["POST"])
def api_agents_dispatch():
    if agent_runner is None:
        return jsonify({"error": "agent runner unavailable"}), 503
    body = request.get_json(silent=True) or {}
    agent_type = body.get("agent_type")
    if agent_type not in AgentRunner.AGENT_TYPES:
        return jsonify({"error": "invalid agent_type"}), 400
    try:
        run_id = agent_runner.dispatch(
            agent_type,
            topic=body.get("topic"),
            target_id=body.get("target_id"),
            payload=body.get("payload"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"run_id": run_id})


@app.route("/api/agents")
def api_agents():
    if agent_runner is None:
        return jsonify({"active": [], "recent_done": []})
    return jsonify(agent_runner.snapshot())


@app.route("/api/agents/<run_id>/logs")
def api_agent_logs(run_id):
    if intel_db is None:
        return jsonify({"logs": []})
    return jsonify({"run_id": run_id, "logs": intel_db.get_agent_logs(run_id)})


@app.route("/api/agents/stream")
def api_agents_stream():
    if agent_runner is None:
        return jsonify({"error": "agent runner unavailable"}), 503

    def gen():
        q = agent_runner.subscribe()
        try:
            yield "retry: 5000\n\n"
            while True:
                try:
                    ev = q.get(timeout=15)
                    yield f"data: {json.dumps(ev)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            agent_runner.unsubscribe(q)

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Phase 3: schedule ────────────────────────────────────────────────────

def _schedule_item_payload(item_id):
    """Denormalized item fields for a calendar cell."""
    if intel_db is None:
        return {}
    try:
        item = intel_db.get_saved_item(int(item_id))
    except (ValueError, TypeError):
        item = None
    if not item:
        return {}
    return {
        "working_title": item.get("working_title") or item.get("title"),
        "topic": item.get("category") or item.get("topic"),
        "format": item.get("format"),
        "creator_score": item.get("creator_score"),
    }


@app.route("/api/schedule", methods=["GET"])
def api_schedule_list():
    if intel_db is None:
        return jsonify([])
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        today = datetime.now()
        start = start or today.strftime("%Y-%m-%d")
        end = end or (today + timedelta(days=6)).strftime("%Y-%m-%d")
    rows = intel_db.get_schedule_range(start, end)
    for row in rows:
        row["item"] = _schedule_item_payload(row.get("item_id"))
    return jsonify(rows)


@app.route("/api/schedule", methods=["POST"])
def api_schedule_create():
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    body = request.get_json(silent=True) or {}
    if not body.get("item_id") or not body.get("day") or not body.get("kind"):
        return jsonify({"error": "item_id, day, kind required"}), 400
    sched_id = f"sched-{uuid.uuid4().hex[:12]}"
    intel_db.insert_schedule(sched_id, str(body["item_id"]), body["day"],
                             body["kind"], time=body.get("time"))
    row = intel_db.get_schedule_entry(sched_id)
    row["item"] = _schedule_item_payload(row.get("item_id"))
    return jsonify(row), 201


@app.route("/api/schedule/<sched_id>", methods=["PUT"])
def api_schedule_update(sched_id):
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    body = request.get_json(silent=True) or {}
    ok = intel_db.update_schedule(sched_id, **body)
    if not ok:
        return jsonify({"error": "not found"}), 404
    row = intel_db.get_schedule_entry(sched_id)
    row["item"] = _schedule_item_payload(row.get("item_id"))
    return jsonify(row)


@app.route("/api/schedule/<sched_id>", methods=["DELETE"])
def api_schedule_delete(sched_id):
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    ok = intel_db.delete_schedule(sched_id)
    return jsonify({"success": ok})


@app.route("/api/schedule/<sched_id>/complete", methods=["POST"])
def api_schedule_complete(sched_id):
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    ok = intel_db.update_schedule(sched_id, status="done")
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"success": True})


@app.route("/api/schedule/auto", methods=["POST"])
def api_schedule_auto():
    """Drop top brief items into the next available week (simple heuristic)."""
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    try:
        scored_data = load_scored_data()
        clusters = build_topic_clusters(scored_data, intel_db=intel_db)
        opportunities = build_content_opportunities(scored_data, clusters)
        brief = build_creator_brief(opportunities, clusters, intel_db.get_saved_items())
    except Exception as e:
        return jsonify({"error": f"brief unavailable: {e}"}), 500

    profile = _load_creator_profile_safe()
    publish_days = (profile.get("schedule") or {}).get("publish_days", ["Sat", "Sun"])
    record_window = (profile.get("schedule") or {}).get("preferred_record_window", "10:00-12:00")
    record_time = record_window.split("-")[0]

    picks = []
    if brief.get("best_video_idea"):
        picks.append(brief["best_video_idea"])
    picks.extend(brief.get("long_form_candidates", [])[:2])

    created = []
    base = datetime.now()
    day_idx = 0
    for opp in picks:
        item_id = opp.get("id") or opp.get("url") or opp.get("topic")
        # advance to next weekday
        while (base + timedelta(days=day_idx)).weekday() >= 5:
            day_idx += 1
        rec_day = (base + timedelta(days=day_idx)).strftime("%Y-%m-%d")
        sid = f"sched-{uuid.uuid4().hex[:12]}"
        intel_db.insert_schedule(sid, str(item_id), rec_day, "record", time=record_time)
        created.append(sid)
        # publish on next configured publish day
        pub_offset = day_idx + 1
        for _ in range(7):
            cand = base + timedelta(days=pub_offset)
            if cand.strftime("%a") in publish_days:
                break
            pub_offset += 1
        pub_day = (base + timedelta(days=pub_offset)).strftime("%Y-%m-%d")
        psid = f"sched-{uuid.uuid4().hex[:12]}"
        intel_db.insert_schedule(psid, str(item_id), pub_day, "publish", time="10:00")
        created.append(psid)
        day_idx += 1
    return jsonify({"created": created, "count": len(created)})


# ── Phase 4: copilot ─────────────────────────────────────────────────────

_COPILOT_HITS = defaultdict(list)


def _load_creator_profile_safe():
    try:
        import llm_summary
        return llm_summary.load_creator_profile()
    except Exception:
        return {}


def _copilot_live_context(max_clusters=8, max_items=3):
    """Compact snapshot of what DailyDex actually fetched, for the copilot."""
    try:
        scored = load_scored_data()
    except Exception:
        scored = {}
    ctx = {"generated_at": datetime.now().isoformat(timespec="minutes")}

    # Per-source freshness + 24h counts.
    sources = {}
    for key in ("github", "huggingface", "youtube", "blogs", "papers"):
        items = scored.get(key, []) or []
        sources[key] = len(items)
    ctx["items_by_source"] = sources

    # Top clusters with the signal the user reasons about.
    try:
        clusters = build_topic_clusters(scored, intel_db=intel_db)
    except Exception:
        clusters = []
    ctx["clusters"] = [{
        "topic": c.get("topic"),
        "creator_score": c.get("creator_score"),
        "signal": c.get("average_signal_score"),
        "momentum_24h_pct": c.get("momentum_24h_pct"),
        "first_seen_hrs": c.get("first_seen_hrs"),
        "sources": c.get("sources"),
        "best_format": c.get("best_content_format"),
        "why": (c.get("why_this_is_a_story") or "")[:160],
        "top_items": [
            {"title": (it.get("title") or "")[:110], "source": it.get("source_type"),
             "signal": it.get("signal_score")}
            for it in (c.get("related_items") or [])[:max_items]
        ],
    } for c in clusters[:max_clusters]]
    return ctx


@app.route("/api/copilot", methods=["POST"])
def api_copilot():
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    view = body.get("view") or "pulse"
    context = body.get("context") or {}
    if not question:
        return jsonify({"error": "question required"}), 400

    # Ground the answer in what DailyDex actually fetched.
    context = {"client": context, "dailydex": _copilot_live_context()}

    # Per-IP rate limit.
    limit = int(os.environ.get("COPILOT_RATE_LIMIT_PER_MIN", "12"))
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "local").split(",")[0].strip()
    now = time.time()
    hits = [t for t in _COPILOT_HITS[ip] if now - t < 60]
    if len(hits) >= limit:
        return jsonify({"error": "rate limited"}), 429
    hits.append(now)
    _COPILOT_HITS[ip] = hits

    profile = _load_creator_profile_safe()
    cop_cfg = profile.get("copilot") or {}
    system = (
        "You are DailyDex's creator copilot. DailyDex is a trend-intelligence dashboard that "
        "fetches AI news from GitHub, Hugging Face, YouTube, blogs, and arXiv, then groups it into "
        "cross-source story clusters with creator/signal scores and 24h momentum.\n"
        f"The user is on the \"{view}\" screen. Answer ONLY from the live DailyDex data below — "
        "reference real topics, scores, sources, and items. Never say you lack access to history or "
        "data; the data is right here. If the question can't be answered from it, say what IS trending instead.\n"
        f"LIVE DATA (JSON):\n{json.dumps(context)[:6000]}\n"
        "Output ONLY the final answer — no reasoning, no planning, no 'Okay, the user wants'. "
        "1-3 punchy, opinionated sentences. Cite specific topics/numbers. No preamble."
    )
    started = time.time()
    answer = None
    model = "unknown"
    max_tokens = int(cop_cfg.get("max_tokens", 200))
    provider = cop_cfg.get("provider") or os.environ.get("LLM_PROVIDER", "gemini")
    try:
        import llm_summary
        if provider == "nvidia":
            model = cop_cfg.get("model") or llm_summary.NVIDIA_MODEL
            # Reasoning models (e.g. minimax) spend tokens thinking — give headroom
            # so the final answer isn't truncated; the display cap below trims it.
            gen_tokens = max(max_tokens, int(cop_cfg.get("nvidia_max_tokens", 2048)))
            answer = llm_summary.query_nvidia(question, system_prompt=system,
                                              model=model, max_tokens=gen_tokens)
        else:
            model = llm_summary.llm_provider_label()
            answer = llm_summary.query_llm(question, system_prompt=system)
    except Exception as e:
        print(f"Copilot LLM error: {e}")
    if not answer:
        answer = "Copilot is offline right now — check the LLM provider config."
    # Cap length defensively (~max_tokens proxy).
    max_chars = int(cop_cfg.get("max_tokens", 200)) * 6
    answer = answer.strip()[:max_chars]
    return jsonify({
        "answer": answer,
        "model": model,
        "elapsed_ms": int((time.time() - started) * 1000),
    })


# ── Phase 5: thumbnails ──────────────────────────────────────────────────

@app.route("/api/thumbnails/generate", methods=["POST"])
def api_thumbnails_generate():
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    from creator_intelligence import generate_thumbnail_variants
    body = request.get_json(silent=True) or {}
    content_hash = body.get("content_hash")
    if not content_hash:
        return jsonify({"error": "content_hash required"}), 400
    count = int(body.get("count", 6))
    variants = generate_thumbnail_variants(
        intel_db, content_hash, topic=body.get("topic"),
        count=count, base_item=body.get("item"),
    )
    return jsonify(variants), 201


@app.route("/api/thumbnails/<content_hash>")
def api_thumbnails_get(content_hash):
    if intel_db is None:
        return jsonify([])
    from creator_intelligence import serialize_thumbnail_variant
    rows = intel_db.get_thumbnail_variants(content_hash)
    return jsonify([serialize_thumbnail_variant(r) for r in rows])


@app.route("/api/thumbnails/<variant_id>", methods=["PUT"])
def api_thumbnails_update(variant_id):
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    from creator_intelligence import serialize_thumbnail_variant
    body = request.get_json(silent=True) or {}
    fields = {}
    if "text" in body:
        fields["text_primary"] = body["text"]
    if "subtext" in body:
        fields["text_secondary"] = body["subtext"]
    for k in ("hue", "kind", "ctr_pred"):
        if k in body:
            fields[k] = body[k]
    ok = intel_db.update_thumbnail_variant(variant_id, **fields)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify(serialize_thumbnail_variant(intel_db.get_thumbnail_variant(variant_id)))


@app.route("/api/thumbnails/<variant_id>", methods=["DELETE"])
def api_thumbnails_delete(variant_id):
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    return jsonify({"success": intel_db.delete_thumbnail_variant(variant_id)})


@app.route("/api/thumbnails/<variant_id>/pick", methods=["POST"])
def api_thumbnails_pick(variant_id):
    if intel_db is None:
        return jsonify({"error": "db unavailable"}), 503
    ok = intel_db.pick_thumbnail_variant(variant_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"success": True})


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
        "signal_score": data.get("signal_score", 0),
        "creator_score": data.get("creator_score"),
        "pipeline_type": data.get("pipeline_type"),
        "status": data.get("status", "to_read"),
        "working_title": data.get("working_title"),
        "hook": data.get("hook"),
        "format": data.get("format") or data.get("recommended_content_format") or data.get("best_format"),
        "outline": data.get("outline") or data.get("three_key_points") or [],
        "sources": data.get("sources") or data.get("source_evidence") or [],
        "thumbnail_text": ", ".join(data.get("thumbnail_text", [])) if isinstance(data.get("thumbnail_text"), list) else data.get("thumbnail_text"),
        "notes": data.get("notes", ""),
        "tags": data.get("tags", []),
        "priority": data.get("priority"),
        "published_url": data.get("published_url"),
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
    updates = {}
    for key, default in [("notes", ""), ("tags", [])]:
        if key in data:
            updates[key] = data.get(key, default)
    for key in ["working_title", "hook", "format", "outline", "sources", "thumbnail_text", "priority", "published_url", "pipeline_type"]:
        if key in data:
            updates[key] = data.get(key)
    intel_db.update_item(item_id, updates)
    return jsonify({"success": True, "message": "Notes and tags updated."})


@app.route("/api/saved")
def api_get_saved():
    """Get all saved items"""
    if not intel_db:
        return jsonify({"items": []})
    
    status_filter = request.args.get("status")
    pipeline_type = request.args.get("pipeline_type")
    items = intel_db.get_saved_items(pipeline_type=pipeline_type)
    
    if status_filter and status_filter != "all":
        items = [i for i in items if i.get("status") == status_filter]
    
    return jsonify({"items": items})


@app.route("/api/saved/export", methods=["GET"])
def api_export_saved():
    """Export saved items as JSON or markdown"""
    if not intel_db:
        return jsonify({"items": []})
    
    fmt = request.args.get("format", "json")
    status_filter = request.args.get("status")
    pipeline_type = request.args.get("pipeline_type")
    items = intel_db.get_saved_items(pipeline_type=pipeline_type)
    
    if status_filter and status_filter != "all":
        items = [i for i in items if i.get("status") == status_filter]
    
    if fmt == "markdown" or fmt == "md":
        md = "# Saved Intelligence\n\n"
        for item in items:
            status_emoji = {"to_read": "📖", "to_test": "🧪", "testing": "⚙️", "useful": "✅", "discarded": "❌"}.get(item.get("status", ""), "📌")
            md += f"## {status_emoji} {item.get('title', 'Untitled')}\n\n"
            md += f"- URL: {item.get('url', 'N/A')}\n"
            md += f"- Status: {item.get('status', 'unknown')}\n"
            if item.get("notes"):
                md += f"- Notes: {item['notes']}\n"
            if item.get("tags"):
                md += f"- Tags: {', '.join(item['tags'])}\n"
            md += "\n"
        return md, 200, {"Content-Type": "text/markdown"}
    
    return jsonify({"items": items})


@app.route("/api/research-pack", methods=["POST"])
def api_build_research_pack():
    """Build and save a creator research pack."""
    payload = request.get_json() or {}
    path, content = build_research_pack(payload, RESEARCH_PACK_DIR)
    return jsonify({
        "success": True,
        "path": path,
        "content": content,
        "message": f"Research pack saved to {path}.",
    })


@app.route("/api/research-packs")
def api_list_research_packs():
    """List saved research packs."""
    return jsonify({"packs": list_research_packs()})


@app.route("/api/research-pack/<path:filename>", methods=["GET"])
def api_get_research_pack(filename):
    """Return the raw markdown content of a research pack."""
    path = os.path.join(RESEARCH_PACK_DIR, os.path.basename(filename))
    if not os.path.isfile(path):
        return jsonify({"error": "Not found"}), 404
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return jsonify({"filename": filename, "content": content})


@app.route("/api/research-pack/<path:filename>", methods=["PUT"])
def api_update_research_pack(filename):
    """Save edited markdown content back to a research pack file."""
    path = os.path.join(RESEARCH_PACK_DIR, os.path.basename(filename))
    if not os.path.isfile(path):
        return jsonify({"error": "Not found"}), 404
    data = request.get_json() or {}
    content = data.get("content", "")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return jsonify({"success": True})


@app.route("/api/research-pack/<path:filename>/send-to-pipeline", methods=["POST"])
def api_research_pack_to_pipeline(filename):
    """Create a content pipeline item from a research pack."""
    if not intel_db:
        return jsonify({"success": False, "error": "Database not available"})
    path = os.path.join(RESEARCH_PACK_DIR, os.path.basename(filename))
    if not os.path.isfile(path):
        return jsonify({"error": "Not found"}), 404
    with open(path, encoding="utf-8") as f:
        content = f.read()
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    title = lines[0].lstrip("# ") if lines else filename
    excerpt = lines[1][:300] if len(lines) > 1 else ""
    data = request.get_json() or {}
    item_id = intel_db.save_item({
        "title": title,
        "url": f"research-pack://{filename}",
        "source": "research-pack",
        "source_type": "research-pack",
        "category": data.get("category", "Research"),
        "signal_score": 0,
        "status": "researching",
        "working_title": title,
        "hook": excerpt,
        "notes": content,
        "pipeline_type": "creator",
    })
    return jsonify({"success": True, "id": item_id, "message": "Added to Content Pipeline."})



_PRACTICUM_AGENTS = {
    "youtube": {
        "name": "YouTube — The Practicum",
        "system_prompt": (
            "You are a YouTube content strategist for AI Practicum, a channel run by two "
            "engineering managers who build agentic AI systems and AI-augmented SDLC workflows. "
            "Generate: 1) 3 title options (SEO optimised, punchy), 2) Full video description "
            "with timestamps placeholder, 3) 5 tags, 4) Thumbnail concept description, "
            "5) Full video outline with sections and talking points."
        ),
    },
    "shorts": {
        "name": "Shorts — The Practicum",
        "system_prompt": (
            "You are a scriptwriter for AI Practicum. Generate content based on the selected "
            "format: For YouTube Short: a 60-second vertical video script with hook, 3 key "
            "points, CTA. For Podcast Episode: intro, 4 talking segments with questions for "
            "two hosts, outro. For Demo Script: step-by-step narration script for a live "
            "technical demo, with cues for what to show on screen."
        ),
    },
    "demo": {
        "name": "Demo — The Practicum",
        "system_prompt": (
            "You are a technical demo producer for AI Practicum. Generate: 1) A step-by-step "
            "demo guide with exact actions to perform, 2) A GIF storyboard (list of 6-8 frames "
            "with descriptions of what to capture), 3) Key callout annotations to overlay on "
            "screenshots, 4) A one-paragraph intro to read before the demo starts."
        ),
    },
}


@app.route("/api/agent-run", methods=["POST"])
def api_agent_run():
    """Run one of the Practicum content agents via the LLM."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id", "")
    agent = _PRACTICUM_AGENTS.get(agent_id)
    if not agent:
        return jsonify({"success": False, "error": f"Unknown agent: {agent_id}"}), 400

    inputs = data.get("inputs", {})
    user_prompt = "\n".join(f"{k}: {v}" for k, v in inputs.items() if v)

    from llm_summary import query_claude_code_cli
    result = query_claude_code_cli(user_prompt, system_prompt=agent["system_prompt"])
    if result is None:
        return jsonify({"success": False, "error": "LLM returned no response. Check LLM_PROVIDER and credentials."}), 500
    return jsonify({"success": True, "output": result, "agent": agent["name"]})


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

    if request.args.get("mode") == "creator" or get_variant_info().get("key") == "creator":
        return api_creator_digest()

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


@app.route("/api/creator-digest")
def api_creator_digest():
    """Generate and return a creator-focused digest."""
    try:
        context = build_dashboard_context()
        digest = build_creator_digest(context["creator_brief"], context["saved_items"], context["today_date"])
        digest_path = os.path.join(DIGEST_DIR, f"creator-{datetime.now().strftime('%Y-%m-%d')}.md")
        ensure_parent_dir(digest_path)
        with open(digest_path, "w", encoding="utf-8") as handle:
            handle.write(digest)
        return jsonify({
            "digest": digest,
            "path": digest_path,
            "message": f"Creator digest saved to {digest_path}.",
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/markets")
def api_markets():
    try:
        from fetch_markets import load_markets
        return jsonify(load_markets())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/markets/refresh", methods=["POST"])
def api_markets_refresh():
    try:
        from fetch_markets import fetch_markets
        return jsonify(fetch_markets())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/votes")
def api_votes():
    """Return vote counts for all items: {url: count}"""
    try:
        db = IntelligenceDB()
        return jsonify(db.get_all_votes())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/bot/send", methods=["POST"])
def api_bot_send():
    """Trigger a broadcast of the daily digest to all Telegram subscribers."""
    import asyncio
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN not set"}), 400
    try:
        from telegram_bot import build_application, broadcast_digest
        application = build_application()

        async def _run():
            async with application:
                return await broadcast_digest(application)

        sent = asyncio.run(_run())
        return jsonify({"sent": sent})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/enrich-status", methods=["GET"])
def api_enrich_status():
    if enrichment_service is None:
        return jsonify({"enabled": False})
    payload = enrichment_service.status()
    payload["enabled"] = True
    return jsonify(payload)


@app.route("/api/enrich", methods=["POST"])
def api_enrich():
    """Enqueue a single item for creator-pack enrichment."""
    if enrichment_service is None:
        return jsonify({"error": "enrichment_disabled"}), 503
    item = request.get_json(silent=True) or {}
    if not item.get("url") and not item.get("title"):
        return jsonify({"error": "missing url or title"}), 400
    result = enrichment_service.enqueue(item, force=bool(item.get("force")))
    return jsonify(result)


@app.route("/api/enrich/<content_hash>", methods=["GET"])
def api_enrich_get(content_hash):
    """Return the cached creator pack for a content hash, if any."""
    if intel_db is None:
        return jsonify({"error": "no_db"}), 503
    cached = intel_db.get_creator_asset(content_hash)
    if not cached:
        return jsonify({"status": "missing"}), 404
    return jsonify({
        "status": cached.get("status"),
        "model": cached.get("model"),
        "error": cached.get("error"),
        "payload": cached.get("payload"),
        "updated_at": cached.get("updated_at"),
    })


@app.route("/api/forge/<int:item_id>", methods=["POST"])
def api_forge(item_id):
    """Generate Production Forge multi-format assets for a saved item."""
    if enrichment_service is None or intel_db is None:
        return jsonify({"error": "forge_disabled"}), 503
    item = intel_db.get_saved_item(item_id)
    if not item:
        return jsonify({"error": "not_found"}), 404

    payload_lines = [
        f"Title: {item.get('working_title') or item.get('title') or ''}",
        f"Hook: {item.get('hook') or ''}",
        f"Format: {item.get('format') or ''}",
        f"Notes: {item.get('notes') or ''}",
    ]
    outline = item.get("outline")
    if isinstance(outline, str):
        try:
            outline = json.loads(outline)
        except Exception:
            outline = [outline]
    if isinstance(outline, list) and outline:
        payload_lines.append("Outline:")
        payload_lines.extend([f"- {line}" for line in outline if line])

    content_hash_val = item.get("content_hash")
    if content_hash_val:
        cached = intel_db.get_creator_asset(content_hash_val)
        if cached and cached.get("payload"):
            pack = cached["payload"]
            payload_lines.extend([
                f"Insight: {pack.get('insight', '')}",
                f"Demo segment: {pack.get('demo_segment', '')}",
                f"Caveats: {pack.get('caveats', '')}",
            ])

    research_data = "\n".join(line for line in payload_lines if line.strip())
    result = enrichment_service.forge_saved(item_id, research_data)
    return jsonify(result)


@app.route("/api/agentic-run", methods=["POST"])
def api_agentic_run():
    """Run the full cluster -> enrich -> dive -> save -> forge pipeline."""
    if enrichment_service is None or intel_db is None:
        return jsonify({"error": "agentic_disabled"}), 503
    try:
        from agentic_researcher import AgenticResearcher
    except Exception as exc:
        return jsonify({"error": f"import_failed:{exc}"}), 500

    payload = request.get_json(silent=True) or {}
    automation_override = payload.get("automation") or {}
    profile = __import__("llm_summary").load_creator_profile()
    automation = {**(profile.get("automation") or {}), **automation_override}

    scored = load_scored_data()
    researcher = AgenticResearcher(db=intel_db, enrichment_service=enrichment_service)

    import threading

    def _runner():
        try:
            result = researcher.run_daily_pipeline(scored, automation=automation)
            print(f"[agentic] daily pipeline result: {result}")
        except Exception as exc:
            print(f"[agentic] failed: {exc}")

    thread = threading.Thread(target=_runner, name="agentic-run", daemon=True)
    thread.start()
    return jsonify({"ok": True, "status": "running", "automation": automation})


@app.route("/api/forge-status/<int:item_id>", methods=["GET"])
def api_forge_status(item_id):
    if intel_db is None:
        return jsonify({"error": "no_db"}), 503
    item = intel_db.get_saved_item(item_id)
    if not item:
        return jsonify({"error": "not_found"}), 404
    assets = item.get("production_assets")
    if isinstance(assets, str):
        try:
            assets = json.loads(assets)
        except Exception:
            assets = {}
    return jsonify({
        "status": item.get("production_status") or "none",
        "assets": assets or {},
        "updated_at": item.get("updated_at"),
    })


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8888"))
    debug = os.environ.get("DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, threaded=True)
