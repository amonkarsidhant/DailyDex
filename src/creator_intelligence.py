#!/usr/bin/env python3
"""Creator intelligence helpers for DailyDex."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


SOURCE_LABELS = {
    "github": "GitHub",
    "huggingface": "Hugging Face",
    "youtube": "YouTube",
    "blogs": "Blogs",
    "papers": "arXiv",
    "hackernews": "HackerNews",
    "reddit": "Reddit",
}

CREATOR_STATUS_ORDER = [
    ("idea", "Idea"),
    ("researching", "Researching"),
    ("script_ready", "Script Ready"),
    ("recording", "Recording"),
    ("published", "Published"),
    ("archived", "Archived"),
]

TOPIC_PATTERNS: List[Tuple[str, List[str]]] = [
    ("AI Agents", ["agent", "agentic", "autonomous", "workflow", "mcp"]),
    ("Local AI", ["local", "ollama", "llama.cpp", "raspberry pi", "edge", "self-hosted"]),
    ("Coding AI", ["coding", "code", "coder", "developer", "programming"]),
    ("Open Source Models", ["open source", "huggingface", "llama", "qwen", "mistral", "deepseek"]),
    ("AI Tools", ["tool", "cli", "desktop", "plugin", "extension"]),
    ("Computer Use", ["computer use", "browser", "operator", "screen", "desktop use"]),
    ("Reasoning Models", ["reasoning", "thinking", "chain of thought"]),
    ("Benchmarks", ["benchmark", "eval", "evaluation", "leaderboard"]),
    ("Voice AI", ["voice", "speech", "audio"]),
    ("Vision AI", ["vision", "image", "multimodal", "video generation"]),
    ("AI Infrastructure", ["inference", "deployment", "serving", "api", "infrastructure"]),
]


def _safe_text(value) -> str:
    return str(value or "")


def _combined_text(item: Dict) -> str:
    parts = [
        _safe_text(item.get("title")),
        _safe_text(item.get("description")),
        _safe_text(item.get("abstract")),
        " ".join(item.get("categories") or []),
        " ".join(item.get("tags") or []),
    ]
    return " ".join(parts).lower()


def _clean_topic(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    return cleaned[:80] or "AI Story"


def _fallback_topic(item: Dict) -> str:
    categories = item.get("categories") or []
    if categories:
        return _clean_topic(str(categories[0]).replace("-", " ").title())
    title = _safe_text(item.get("title"))
    words = [word for word in re.findall(r"[A-Za-z0-9+.#-]+", title) if len(word) > 2]
    if words:
        return _clean_topic(" ".join(words[:3]).title())
    return "AI Story"


def extract_topics(item: Dict) -> List[str]:
    """Extract normalized creator topics from an item."""
    text = _combined_text(item)
    matches = []
    for topic, keywords in TOPIC_PATTERNS:
        if any(keyword in text for keyword in keywords):
            matches.append(topic)
    if not matches:
        matches.append(_fallback_topic(item))
    unique = []
    for topic in matches:
        if topic not in unique:
            unique.append(topic)
    return unique[:3]


def primary_topic(item: Dict) -> str:
    return extract_topics(item)[0]


def _is_demoable(item: Dict, source_type: str) -> bool:
    text = _combined_text(item)
    if source_type in {"github", "youtube"}:
        return True
    if item.get("action") == "try":
        return True
    if item.get("is_local_compatible") or item.get("pi_suitability") in {"yes", "partial"}:
        return True
    if item.get("has_code"):
        return True
    return any(keyword in text for keyword in ["demo", "tutorial", "hands-on", "walkthrough", "clone"])


def _story_tension_boost(item: Dict) -> int:
    text = _combined_text(item)
    keywords = [
        "launch", "release", "announced", "breaking", "controversy", "battle",
        "replace", "beats", "vs", "war", "problem", "hype", "killer",
    ]
    return min(40, sum(8 for keyword in keywords if keyword in text))


def _visual_boost(item: Dict, source_type: str) -> int:
    text = _combined_text(item)
    score = 0
    if source_type == "youtube":
        score += 35
    if _is_demoable(item, source_type):
        score += 35
    if any(keyword in text for keyword in ["video", "vision", "browser", "desktop", "screen", "compare"]):
        score += 20
    return min(100, score)


def build_topic_clusters(scored_data: Dict, intel_db=None) -> List[Dict]:
    """Group related items into creator-friendly story clusters.

    When ``intel_db`` is supplied, each cluster also carries the Pulse-screen
    trend fields (``momentum_24h_pct``, ``first_seen_hrs``, ``pulse_24h``,
    ``radar_coords``). Without a DB handle these default to neutral values so
    existing callers keep working unchanged.
    """
    topic_map = {}
    for source_type in ["github", "huggingface", "youtube", "blogs", "papers", "hackernews", "reddit"]:
        for item in scored_data.get(source_type, []) or []:
            for topic in extract_topics(item):
                cluster = topic_map.setdefault(topic, {
                    "topic": topic,
                    "sources": set(),
                    "related_items": [],
                    "raw_items": [],
                    "signal_total": 0,
                    "creator_total": 0,
                    "demoable": False,
                })
                cluster["sources"].add(source_type)
                cluster["related_items"].append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source_type": source_type,
                    "source_label": SOURCE_LABELS.get(source_type, source_type.title()),
                    "signal_score": item.get("signal_score", 0),
                    "creator_score": item.get("creator_score", 0),
                })
                cluster["raw_items"].append((item, source_type))
                cluster["signal_total"] += int(item.get("signal_score") or 0)
                cluster["creator_total"] += int(item.get("creator_score") or 0)
                cluster["demoable"] = cluster["demoable"] or _is_demoable(item, source_type)

    now_hour = int(time.time() // 3600)
    clusters = []
    for topic, cluster in topic_map.items():
        source_count = len(cluster["sources"])
        item_count = len(cluster["related_items"])
        if source_count < 2 or item_count == 0:
            continue
        avg_signal = round(cluster["signal_total"] / item_count, 1)
        avg_creator = round(cluster["creator_total"] / item_count, 1)
        if avg_signal < 50 and not cluster["demoable"]:
            continue
        related_items = sorted(cluster["related_items"], key=lambda row: (row.get("creator_score", 0), row.get("signal_score", 0)), reverse=True)
        best_format = "Comparison video" if source_count >= 3 else "Explainer"
        if cluster["demoable"] and avg_creator >= 70:
            best_format = "Tutorial"

        # Trend time-series fields (Phase 1).
        history = intel_db.read_cluster_history(topic, hours=168) if intel_db else []
        affinity_bonus = 0
        for item, _ in cluster["raw_items"]:
            if item.get("creator_score_breakdown") and isinstance(item.get("creator_score_breakdown"), dict):
                affinity_bonus = max(affinity_bonus, item.get("creator_score_breakdown").get("affinity_bonus", 0))

        cluster_out = {
            "topic": topic,
            "slug": slugify_topic(topic),
            "source_count": source_count,
            "sources": sorted(cluster["sources"]),
            "related_items": related_items[:6],
            "average_signal_score": avg_signal,
            "creator_score": avg_creator,
            "affinity_bonus": affinity_bonus,
            "why_this_is_a_story": f"{topic} is showing up across {source_count} source families, which usually means audience curiosity is already forming.",
            "recommended_angle": "Show what changed, who it matters for, and the fastest concrete demo." if cluster["demoable"] else "Explain the shift, show supporting evidence, and call out what is still uncertain.",
            "best_content_format": best_format,
            "has_demoable_item": cluster["demoable"],
            "momentum_24h_pct": _momentum_pct(history),
            "first_seen_hrs": _first_seen_hrs(history, now_hour),
            "pulse_24h": _pulse_24h(history, now_hour),
            "radar_coords": _radar_coords(cluster["raw_items"], source_count),
        }
        clusters.append(cluster_out)
    clusters.sort(key=lambda row: (row["source_count"], row["creator_score"], row["average_signal_score"]), reverse=True)
    return clusters


# ── Phase 1: trend math ──────────────────────────────────────────────────

def _momentum_pct(history: List[tuple], lookback_hrs: int = 24) -> int:
    """((sum_recent / sum_prior) - 1) * 100, clamped to [-99, +200].

    ``history`` is the list of (hour_bucket, item_count, signal_sum) rows,
    oldest-first, as returned by ``read_cluster_history``.
    """
    if not history:
        return 0
    counts = [row[1] for row in history]
    recent = counts[-lookback_hrs:]
    prior = counts[-2 * lookback_hrs:-lookback_hrs]
    sum_recent = sum(recent)
    sum_prior = sum(prior)
    if sum_prior <= 0:
        return 200 if sum_recent > 0 else 0
    pct = ((sum_recent / sum_prior) - 1.0) * 100.0
    return int(max(-99, min(200, round(pct))))


def _first_seen_hrs(history: List[tuple], now_hour: int) -> int:
    """now_hour - earliest hour with items, or 168+ if absent."""
    for hour_bucket, item_count, _signal in history:
        if item_count > 0:
            return max(0, int(now_hour - hour_bucket))
    return 168


def _pulse_24h(history: List[tuple], now_hour: int) -> List[float]:
    """Length-24 array of item_count, oldest-first, normalized to peak=1.

    Empty hours fill as 0. Returns floats in [0, 1].
    """
    by_hour = {int(hb): int(cnt) for hb, cnt, _s in history}
    raw = [by_hour.get(now_hour - (23 - i), 0) for i in range(24)]
    peak = max(raw) if raw else 0
    if peak <= 0:
        return [0.0] * 24
    return [round(v / peak, 3) for v in raw]


def _radar_coords(raw_items: List[tuple], source_count: int) -> Dict[str, float]:
    """Deterministic {x, y} in [-1, 1]^2 from averaged creator factors.

    X axis: visual (-1) ↔ demo (+1)  -> practical_demo_value vs visual_potential
    Y axis: explainer (-1) ↔ cultural (+1) -> credibility vs story_tension
    """
    if not raw_items:
        return {"x": 0.0, "y": 0.0}
    support = {"source_count": source_count}
    sums = defaultdict(float)
    for item, source_type in raw_items:
        factors = _creator_factors(item, source_type, support)
        for key in ("visual_potential", "practical_demo_value", "credibility", "story_tension"):
            sums[key] += factors[key]
    n = len(raw_items)
    visual = sums["visual_potential"] / n
    demo = sums["practical_demo_value"] / n
    credibility = sums["credibility"] / n
    tension = sums["story_tension"] / n
    # Normalize each opposed pair to a [-1, 1] axis.
    x = (demo - visual) / 100.0
    y = (tension - credibility) / 100.0
    return {"x": round(max(-1.0, min(1.0, x)), 3), "y": round(max(-1.0, min(1.0, y)), 3)}


def snapshot_clusters(scored_data: Dict, intel_db, now_ts: Optional[float] = None) -> int:
    """Group the current scored items by topic; upsert one row per topic into
    cluster_snapshots at the current hour bucket. Returns rows written."""
    if intel_db is None:
        return 0
    now_ts = now_ts or time.time()
    bucket = int(now_ts // 3600)
    by_topic = defaultdict(lambda: {"items": 0, "signal": 0, "sources": set()})
    for source_type in ("github", "huggingface", "youtube", "blogs", "papers", "hackernews", "reddit"):
        for item in scored_data.get(source_type, []) or []:
            topic = primary_topic(item)
            by_topic[topic]["items"] += 1
            by_topic[topic]["signal"] += int(item.get("signal_score") or 0)
            by_topic[topic]["sources"].add(source_type)
    written = 0
    for topic, agg in by_topic.items():
        intel_db.write_cluster_snapshot(
            topic, bucket, agg["items"], agg["signal"],
            json.dumps(sorted(agg["sources"])),
        )
        written += 1
    # Retention trim.
    try:
        retention = int(os.environ.get("CLUSTER_HISTORY_RETENTION_HRS", "336"))
        intel_db.trim_cluster_snapshots(bucket - retention)
    except Exception:
        pass
    return written


def _format_for_item(item: Dict, source_type: str, factors: Dict, support: Dict) -> str:
    if factors["story_tension"] >= 70 and factors["production_effort"] >= 65:
        return "YouTube short"
    if source_type == "github" and factors["practical_demo_value"] >= 70:
        return "Tutorial"
    if source_type == "youtube":
        return "YouTube long-form"
    if support.get("source_count", 1) >= 3:
        return "Comparison video"
    if source_type == "papers":
        return "Explainer"
    if source_type == "blogs":
        return "LinkedIn post"
    if factors["visual_potential"] >= 75 and factors["practical_demo_value"] >= 70:
        return "Livestream demo"
    return "YouTube long-form"


def _production_effort_label(score: int) -> str:
    if score >= 75:
        return "low"
    if score >= 45:
        return "medium"
    return "high"


def _recommended_action(score: int, effort_label: str, support: Dict) -> str:
    if score >= 82 and effort_label in {"low", "medium"}:
        return "Draft script"
    if score >= 72:
        return "Build research pack"
    if score >= 60:
        return "Save as idea"
    if support.get("source_count", 1) >= 2:
        return "Track topic"
    return "Ignore"


def _why_viewers_care(item: Dict, topic: str, support: Dict) -> str:
    if support.get("source_count", 1) >= 3:
        return f"{topic} is appearing across multiple AI source types, so viewers get both urgency and proof that the trend is real."
    if item.get("action") == "try":
        return f"This is not just talk. {topic} can be shown in a concrete demo, which makes the content more useful and more clickable."
    return f"{topic} is moving from abstract discussion to something people can evaluate, compare, or act on right now."


def _demo_idea(item: Dict, topic: str, source_type: str) -> str:
    title = item.get("title", "this item")
    if source_type == "github":
        return f"Clone {title}, run the quickest happy path, and show one result that proves whether the repo is actually usable."
    if source_type == "huggingface":
        return f"Compare {title} against one familiar model on a coding or reasoning prompt and show the difference on screen."
    if source_type == "papers":
        return f"Turn the paper into a practical takeaway: what changed, whether code exists, and what a creator should actually test."
    if source_type == "blogs":
        return f"Pair the announcement with a live product walkthrough, repo, or benchmark so the piece becomes more than a news recap."
    if source_type == "youtube":
        return f"React to the strongest claim in the video, then validate it with your own quick example or counter-example."
    return f"Show one concrete example that proves why {topic} matters beyond the headline."


def _risks_or_caveats(item: Dict, source_type: str) -> str:
    if source_type == "papers" and not item.get("has_code"):
        return "Strong research signal, but production value is lower if you cannot show code or a real demo."
    if source_type == "blogs":
        return "Announcements can outrun real usability, so validate the claims before framing it as a finished breakthrough."
    if source_type == "github" and item.get("stars", "0") in {"0", 0}:
        return "Interesting repo, but traction is still early and there may be missing docs or rough setup."
    return "Avoid overclaiming. Separate what is proven now from what is still hype, roadmap, or speculation."


def _hook_line(topic: str, item: Dict, support: Dict) -> str:
    title = item.get("title", topic)
    if support.get("source_count", 1) >= 3:
        return f"{topic} is showing up everywhere right now, but the real question is whether it is actually useful."
    if item.get("action") == "try":
        return f"I tested {title} so you can decide if it deserves your attention today."
    return f"Everyone is talking about {topic}; here is the part that actually matters."


def _outline_points(topic: str, item: Dict, source_type: str) -> List[str]:
    return [
        f"What happened in {topic} and why it is showing up now.",
        f"What the source evidence says, across {SOURCE_LABELS.get(source_type, source_type.title())} and adjacent signals.",
        f"What people should test, watch, or ignore next.",
    ]


def _short_script(topic: str, item: Dict) -> str:
    return " ".join([
        _hook_line(topic, item, {"source_count": 1}),
        f"The key signal is {item.get('title', topic)}.",
        "The takeaway: this is worth watching if you want useful AI content, not just hype.",
    ])


def _title_ideas(topic: str, item: Dict, fmt: str) -> Dict:
    base = item.get("title", topic).strip()
    short_base = base[:55]
    return {
        "curiosity": f"Why {topic} suddenly matters more than people think",
        "practical": f"What {short_base} means in practice",
        "contrarian": f"The real story behind {topic} is not the hype",
        "tutorial": f"How to use {short_base} quickly" if fmt in {"Tutorial", "Livestream demo"} else f"How to understand {topic} fast",
    }


def _thumbnail_text(topic: str, item: Dict) -> List[str]:
    topic_word = topic.upper().replace(" ", " ")
    candidates = [
        topic_word[:18],
        "HYPE OR USEFUL",
        "MAKE THIS TODAY",
        "WORTH YOUR TIME",
    ]
    trimmed = []
    for text in candidates:
        words = text.split()[:4]
        value = " ".join(words)
        if value not in trimmed:
            trimmed.append(value)
    return trimmed[:3]


def _creator_factors(item: Dict, source_type: str, support: Dict) -> Dict:
    breakdown = item.get("score_breakdown") or {}
    recency = int(breakdown.get("recency") or 50)
    popularity = int(breakdown.get("popularity") or 40)
    relevance = int(breakdown.get("relevance") or 40)
    trust = int(breakdown.get("trust") or 50)
    title_text = _combined_text(item)
    local_bonus = 20 if item.get("pi_suitability") in {"yes", "partial"} or item.get("is_local_compatible") else 0
    code_bonus = 20 if item.get("has_code") or source_type == "github" else 0
    novelty = min(100, 35 + int(recency * 0.7) + _story_tension_boost(item) // 2)
    audience_interest = min(100, int(item.get("signal_score", 0) * 0.45) + support.get("source_count", 1) * 18 + int(popularity * 0.25))
    story_tension = min(100, 25 + _story_tension_boost(item) + (15 if source_type == "blogs" else 0))
    practical_demo_value = min(100, 20 + local_bonus + code_bonus + (25 if _is_demoable(item, source_type) else 0) + (15 if item.get("action") == "try" else 0))
    visual_potential = min(100, 20 + _visual_boost(item, source_type))
    credibility = min(100, int(trust * 0.7) + support.get("source_count", 1) * 10 + (10 if source_type == "papers" else 0))
    shelf_life = 75 if source_type in {"github", "papers"} else 55
    if "tutorial" in title_text or "guide" in title_text:
        shelf_life += 15
    if "breaking" in title_text or "announcement" in title_text:
        shelf_life -= 15
    shelf_life = max(20, min(100, shelf_life))
    effort_base = 80 if item.get("installation_complexity") == "easy" else 60 if item.get("installation_complexity") == "medium" else 35
    if source_type == "papers" and not item.get("has_code"):
        effort_base -= 15
    production_effort = max(20, min(100, effort_base))
    niche_fit = min(100, 20 + local_bonus + int(relevance * 0.5) + (20 if any(keyword in title_text for keyword in ["agent", "coding", "open source", "local"]) else 0))
    differentiation = min(100, 25 + support.get("source_count", 1) * 10 + (15 if _is_demoable(item, source_type) else 0) + (10 if source_type == "github" else 0))
    return {
        "novelty": novelty,
        "audience_interest": audience_interest,
        "story_tension": story_tension,
        "practical_demo_value": practical_demo_value,
        "visual_potential": visual_potential,
        "credibility": credibility,
        "shelf_life": shelf_life,
        "production_effort": production_effort,
        "niche_fit": niche_fit,
        "differentiation": differentiation,
    }


def _creator_score(factors: Dict) -> int:
    return int(round(
        factors["novelty"] * 0.10 +
        factors["audience_interest"] * 0.16 +
        factors["story_tension"] * 0.10 +
        factors["practical_demo_value"] * 0.14 +
        factors["visual_potential"] * 0.10 +
        factors["credibility"] * 0.11 +
        factors["shelf_life"] * 0.08 +
        factors["production_effort"] * 0.09 +
        factors["niche_fit"] * 0.07 +
        factors["differentiation"] * 0.05
    ))


import llm_summary
from creator_enricher import content_hash as _content_hash


def _apply_creator_pack(target: Dict, pack: Dict) -> None:
    """Merge a cached LLM creator pack into an item dict.

    Only overwrites a key when the LLM produced a non-empty value so that
    deterministic fallbacks (titles, thumbnails) remain visible until the
    real pack arrives.
    """
    if not pack:
        return
    string_fields = (
        "opening_hook", "hook_line", "intro_context", "demo_segment",
        "caveats", "closing_takeaway", "call_to_action", "short_script",
        "visual_idea", "cta", "insight",
    )
    list_fields = (
        "three_key_points", "three_beat_structure", "hooks", "tags",
        "thumbnail_text", "broll_list", "on_screen_cues",
    )
    if pack.get("hook"):
        target["opening_hook"] = pack["hook"]
        target["hook_line"] = pack.get("hook_line") or pack["hook"]
    for key in string_fields:
        value = pack.get(key)
        if value:
            target[key] = value
    for key in list_fields:
        value = pack.get(key)
        if value:
            target[key] = value
    titles = pack.get("suggested_titles") or {}
    if any(titles.values()):
        merged = dict(target.get("suggested_titles") or {})
        for k, v in titles.items():
            if v:
                merged[k] = v
        target["suggested_titles"] = merged


def enrich_with_llm_intelligence(item: Dict) -> Dict:
    """Use LLM to generate deep insights, hooks and outlines for high-signal items."""
    # Only enrich if it has high signal or is specifically requested
    if item.get("signal_score", 0) < 70 and item.get("creator_score", 0) < 70:
        return item
        
    import llm_summary
    enrichment = llm_summary.get_item_enrichment(item)
    
    # Update item with LLM intelligence
    item["insight"] = enrichment.get("insight", item.get("insight", ""))
    item["opening_hook"] = enrichment.get("hooks", [item.get("opening_hook", "")])[0] if enrichment.get("hooks") else item.get("opening_hook", "")
    item["hooks"] = enrichment.get("hooks", [])
    item["three_key_points"] = enrichment.get("outline", item.get("three_key_points", []))
    
    # If it's a very high score, set as idea automatically
    if item.get("creator_score", 0) >= 85:
        item["status"] = "idea"
        item["pipeline_type"] = "creator"
        
    return item


def build_topic_performance(intel_db, min_views: int = 10) -> Dict[str, float]:
    """Per-topic audience-performance multipliers from published video analytics.

    Compares each topic's average views against the channel median and maps the
    ratio onto a bounded multiplier so one viral outlier can't hijack scoring:
    >=2x median -> 1.15, >=1.25x -> 1.08, <=0.5x -> 0.92, else 1.0.
    """
    if intel_db is None:
        return {}
    try:
        pubs = intel_db.get_publication_analytics()
    except Exception:
        return {}

    view_rows = [p for p in pubs if (p.get("views") or 0) >= min_views and p.get("title")]
    if len(view_rows) < 2:
        return {}

    all_views = sorted(p["views"] for p in view_rows)
    median_views = all_views[len(all_views) // 2]
    if median_views <= 0:
        return {}

    topic_views: Dict[str, List[int]] = defaultdict(list)
    for pub in view_rows:
        for topic in extract_topics({"title": pub["title"]}):
            topic_views[topic].append(pub["views"])

    multipliers = {}
    for topic, views in topic_views.items():
        ratio = (sum(views) / len(views)) / median_views
        if ratio >= 2.0:
            multipliers[topic] = 1.15
        elif ratio >= 1.25:
            multipliers[topic] = 1.08
        elif ratio <= 0.5:
            multipliers[topic] = 0.92
        else:
            multipliers[topic] = 1.0
    return multipliers


def enrich_scored_data_with_creator_fields(scored_data: Dict, intel_db=None) -> Dict:
    """Add creator metadata to every scored item."""
    support_map = {}
    for cluster in build_topic_clusters(scored_data):
        support_map[cluster["topic"]] = cluster

    top_categories = []
    if intel_db is not None:
        try:
            top_categories = intel_db.get_top_performing_categories(limit=3)
        except Exception:
            pass
    topic_performance = build_topic_performance(intel_db)

    for source_type in ["github", "huggingface", "youtube", "blogs", "papers", "hackernews", "reddit"]:
        enriched_items = []
        for item in scored_data.get(source_type, []) or []:
            topic = primary_topic(item)
            support = support_map.get(topic, {"topic": topic, "source_count": 1, "sources": [source_type], "related_items": []})
            factors = _creator_factors(item, source_type, support)
            creator_score = _creator_score(factors)

            # ROI feedback loop: apply affinity boost if item category matches top performing categories
            affinity_bonus = 0
            item_categories = item.get("categories") or []
            if not isinstance(item_categories, list):
                item_categories = [item_categories]
            if item.get("category"):
                item_categories.append(item.get("category"))

            if any(cat in top_categories for cat in item_categories if cat):
                affinity_bonus = 15
                creator_score = min(100, creator_score + affinity_bonus)

            factors["affinity_bonus"] = affinity_bonus

            # Audience feedback loop: scale by how this topic actually performed
            # on the channel (from publication_analytics views vs channel median).
            audience_multiplier = topic_performance.get(topic, 1.0)
            if audience_multiplier != 1.0:
                creator_score = max(0, min(100, round(creator_score * audience_multiplier)))
            factors["audience_multiplier"] = audience_multiplier
            best_format = _format_for_item(item, source_type, factors, support)
            effort_label = _production_effort_label(factors["production_effort"])
            titles = _title_ideas(topic, item, best_format)
            thumbnails = _thumbnail_text(topic, item)
            hook = _hook_line(topic, item, support)
            source_evidence = support.get("related_items")[:4] or [{
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source_type": source_type,
                "source_label": SOURCE_LABELS.get(source_type, source_type.title()),
                "signal_score": item.get("signal_score", 0),
                "creator_score": creator_score,
            }]
            # Deterministic baseline so the UI always renders something.
            # Real LLM output is layered on top via _apply_creator_pack below.
            sibling_titles = [
                row.get("title", "")
                for row in support.get("related_items", [])
                if row.get("title")
            ][:5]
            hash_ = _content_hash(item)
            enrichment_status = "unenriched"
            enrichment_model = ""
            enrichment_error = ""

            enriched = {
                **item,
                "content_hash": hash_,
                "cluster_sibling_titles": sibling_titles,
                "creator_topic": topic,
                "creator_score": creator_score,
                "creator_score_breakdown": factors,
                "creator_reason": f"High creator potential from {topic.lower()} trend.",
                "recommended_content_format": best_format,
                "production_effort": effort_label,
                "why_viewers_care": _why_viewers_care(item, topic, support),
                "source_evidence": source_evidence,
                "demo_idea": _demo_idea(item, topic, source_type),
                "risks_or_caveats": _risks_or_caveats(item, source_type),
                "recommended_action": _recommended_action(creator_score, effort_label, support),
                "opening_hook": item.get("opening_hook") or hook,
                "hook_line": item.get("hook_line") or hook,
                "intro_context": item.get("intro_context", ""),
                "three_key_points": item.get("three_key_points", []) or _outline_points(topic, item, source_type),
                "three_beat_structure": item.get("three_beat_structure", []),
                "demo_segment": item.get("demo_segment", ""),
                "caveats": item.get("caveats", ""),
                "closing_takeaway": item.get("closing_takeaway", ""),
                "call_to_action": item.get("call_to_action", ""),
                "short_script": item.get("short_script") or _short_script(topic, item),
                "visual_idea": item.get("visual_idea", ""),
                "cta": item.get("cta", ""),
                "suggested_titles": titles,
                "thumbnail_text": thumbnails,
                "broll_list": item.get("broll_list", []),
                "on_screen_cues": item.get("on_screen_cues", []),
            }

            if intel_db is not None:
                try:
                    cached = intel_db.get_creator_asset(hash_)
                except Exception:
                    cached = None
                if cached:
                    status = cached.get("status") or "ready"
                    enrichment_status = status
                    enrichment_model = cached.get("model") or ""
                    enrichment_error = cached.get("error") or ""
                    if status in {"ready", "ready_with_warnings"}:
                        _apply_creator_pack(enriched, cached.get("payload") or {})

            enriched["enrichment_status"] = enrichment_status
            enriched["enrichment_model"] = enrichment_model
            enriched["enrichment_error"] = enrichment_error
            enriched_items.append(enriched)
        scored_data[source_type] = enriched_items
    return scored_data


def build_content_opportunities(scored_data: Dict, clusters: List[Dict], limit: int = 12) -> List[Dict]:
    """Turn scored items into actionable creator cards."""
    cluster_map = {cluster["topic"]: cluster for cluster in clusters}
    opportunities = []
    for source_type in ["github", "huggingface", "youtube", "blogs", "papers", "hackernews", "reddit"]:
        for item in scored_data.get(source_type, []) or []:
            if item.get("signal_score", 0) < 40 and item.get("creator_score", 0) < 55:
                continue
            topic = item.get("creator_topic") or primary_topic(item)
            cluster = cluster_map.get(topic, {"topic": topic, "source_count": 1, "sources": [source_type], "related_items": item.get("source_evidence", [])})
            cluster_slug = cluster.get("slug") or slugify_topic(topic)
            content_hash = item.get("content_hash") or _content_hash(item)
            opportunities.append({
                "id": f"{cluster_slug}:{source_type}:{content_hash[:12]}",
                "content_hash": content_hash,
                "topic": topic,
                "creator_topic": topic,
                "slug": cluster_slug,
                "cluster_slug": cluster_slug,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "source_type": source_type,
                "signal_score": item.get("signal_score", 0),
                "creator_score": item.get("creator_score", 0),
                "creator_score_breakdown": item.get("creator_score_breakdown", {}),
                "creator_reason": item.get("creator_reason", ""),
                "best_format": item.get("recommended_content_format", "YouTube long-form"),
                "hook": item.get("opening_hook", ""),
                "suggested_titles": item.get("suggested_titles", {}),
                "thumbnail_text": item.get("thumbnail_text", []),
                "why_viewers_care": item.get("why_viewers_care", ""),
                "source_evidence": item.get("source_evidence", [])[:4],
                "production_effort": item.get("production_effort", "medium"),
                "demo_idea": item.get("demo_idea", ""),
                "risks_or_caveats": item.get("risks_or_caveats", ""),
                "recommended_action": item.get("recommended_action", "Save as idea"),
                "opening_hook": item.get("opening_hook", ""),
                "intro_context": item.get("intro_context", ""),
                "three_key_points": item.get("three_key_points", []),
                "demo_segment": item.get("demo_segment", ""),
                "caveats": item.get("caveats", ""),
                "closing_takeaway": item.get("closing_takeaway", ""),
                "call_to_action": item.get("call_to_action", ""),
                "hook_line": item.get("hook_line", ""),
                "three_beat_structure": item.get("three_beat_structure", []),
                "short_script": item.get("short_script", ""),
                "visual_idea": item.get("visual_idea", ""),
                "cta": item.get("cta", ""),
                "broll_list": item.get("broll_list", []),
                "on_screen_cues": item.get("on_screen_cues", []),
                "cluster_source_count": cluster.get("source_count", 1),
                "cluster_sources": cluster.get("sources", [source_type]),
                "enrichment_status": item.get("enrichment_status", "unenriched"),
            })
    opportunities.sort(key=lambda row: (row.get("creator_score", 0), row.get("signal_score", 0)), reverse=True)
    return opportunities[:limit]


def build_creator_brief(opportunities: List[Dict], clusters: List[Dict], saved_items: List[Dict]) -> Dict:
    """Build a creator-first planning brief."""
    long_form = [item for item in opportunities if item.get("best_format") != "YouTube short"]
    shorts = [item for item in opportunities if item.get("best_format") == "YouTube short"]
    if len(shorts) < 3:
        shorts = sorted(opportunities, key=lambda row: (row.get("creator_score_breakdown", {}).get("story_tension", 0), row.get("creator_score", 0)), reverse=True)[:5]
    quick_wins = [item for item in opportunities if item.get("production_effort") == "low"]
    if len(quick_wins) < 3:
        quick_wins = sorted(opportunities, key=lambda row: (row.get("production_effort") == "low", row.get("creator_score", 0)), reverse=True)[:4]
    pipeline_items = [item for item in saved_items if item.get("pipeline_type") == "creator"]
    best_video = long_form[0] if long_form else (opportunities[0] if opportunities else None)
    return {
        "best_video_idea": best_video,
        "shorts_ideas": shorts[:5],
        "long_form_candidates": long_form[:3],
        "content_clusters": clusters[:6],
        "quick_wins": quick_wins[:4],
        "pipeline_count": len(pipeline_items),
    }


def build_creator_saved_groups(saved_items: List[Dict]) -> List[Dict]:
    """Group creator items into a production pipeline."""
    creator_items = [item for item in saved_items if item.get("pipeline_type") == "creator"]
    groups = []
    for status_key, label in CREATOR_STATUS_ORDER:
        entries = []
        for item in creator_items:
            if item.get("status") == status_key:
                entries.append(item)
        groups.append({"key": status_key, "label": label, "group_entries": entries})
    return groups


def build_weekly_compilations(scored_data: Dict) -> List[Dict]:
    """Compile scored items into themed listicles for multi-item content delivery."""
    all_items = []
    seen_urls = set()
    for source in ["github", "huggingface", "youtube", "blogs", "papers", "hackernews", "reddit"]:
        for item in scored_data.get(source, []) or []:
            url = item.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                # Ensure we have clean dictionaries with standard fields
                item_copy = dict(item)
                item_copy["source_type"] = source
                all_items.append(item_copy)

    # Sort all items by creator_score first, then signal_score
    all_items.sort(key=lambda x: (x.get("creator_score", 0), x.get("signal_score", 0)), reverse=True)

    # Helper to check keywords in title/description
    def matches_keywords(item, keywords):
        text = ((item.get("title") or "") + " " + (item.get("description") or "") + " " + " ".join(item.get("tags") or [])).lower()
        return any(kw in text for kw in keywords)

    themes = [
        {
            "title": "Top 5 Local AI & Self-Hosted Tools",
            "slug": "top-5-local-ai-self-hosted",
            "theme_description": "Run powerful AI models entirely offline and self-host your own AI infrastructure. These top-trending open-source tools help you ditch the cloud.",
            "keywords": ["local", "self-hosted", "ollama", "llama.cpp", "edge", "offline", "local-first", "host"],
        },
        {
            "title": "Top 5 AI Coding Assistants & Agents",
            "slug": "top-5-ai-coding-agents",
            "theme_description": "AI agents and coding tools are moving at a breakneck pace. Here are the top repositories that automate development and build software autonomously.",
            "keywords": ["agent", "autonomous", "coding", "code", "coder", "developer", "mcp", "programming", "copilot"],
        },
        {
            "title": "Top Notion & Gamma Open-Source Alternatives",
            "slug": "top-notion-gamma-alternatives",
            "theme_description": "Ditch proprietary workspace apps. These developer-first productivity platforms, infinite canvases, and markdown editors are taking over GitHub this week.",
            "keywords": ["notion", "gamma", "editor", "canvas", "wiki", "note", "document", "markdown", "appflowy", "affine", "docmost"],
        },
    ]

    compilations = []

    # 1. Themed listicles
    for t in themes:
        matched = [item for item in all_items if matches_keywords(item, t["keywords"])]
        if len(matched) >= 3:
            comp_items = matched[:5]
            avg_creator = sum(item.get("creator_score", 0) for item in comp_items) / len(comp_items)
            avg_signal = sum(item.get("signal_score", 0) for item in comp_items) / len(comp_items)
            compilations.append({
                "title": t["title"],
                "slug": t["slug"],
                "theme_description": t["theme_description"],
                "items": comp_items,
                "creator_score": int(avg_creator),
                "signal_score": int(avg_signal),
                "recommended_format": "YouTube Listicle (Long-form)",
            })

    # 2. General "Top GitHub Repos of the Week" (always present)
    github_items = [item for item in all_items if item.get("source_type") == "github"]
    if len(github_items) >= 3:
        comp_items = github_items[:5]
        avg_creator = sum(item.get("creator_score", 0) for item in comp_items) / len(comp_items)
        avg_signal = sum(item.get("signal_score", 0) for item in comp_items) / len(comp_items)
        compilations.append({
            "title": "Top 5 Trending GitHub Repos This Week",
            "slug": "top-5-trending-github-repos",
            "theme_description": "The highest-signal open-source repositories and packages trending on GitHub. Perfect for developer show-and-tell reviews.",
            "items": comp_items,
            "creator_score": int(avg_creator),
            "signal_score": int(avg_signal),
            "recommended_format": "YouTube Listicle (Long-form)",
        })

    return compilations





def slugify_topic(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "creator-topic"


def build_research_pack(opportunity: Dict, research_dir: str, date: str | None = None) -> Tuple[str, str]:
    """Generate and save a research pack markdown file."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    topic = opportunity.get("topic") or opportunity.get("creator_topic") or opportunity.get("title") or "creator-topic"
    filename = f"{date}-{slugify_topic(topic)}.md"
    os.makedirs(research_dir, exist_ok=True)
    path = os.path.join(research_dir, filename)

    lines = [
        f"# Research Pack - {topic}",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Core Angle",
        opportunity.get("hook") or opportunity.get("opening_hook") or "No hook generated.",
        "",
        "## Suggested Titles",
    ]
    for key, value in (opportunity.get("suggested_titles") or {}).items():
        lines.append(f"- {key.title()}: {value}")
    lines.extend([
        "",
        "## Thumbnail Ideas",
    ])
    for value in opportunity.get("thumbnail_text") or []:
        lines.append(f"- {value}")
    lines.extend([
        "",
        "## Why Viewers Care",
        opportunity.get("why_viewers_care", ""),
        "",
        "## Source Links",
    ])
    for evidence in opportunity.get("source_evidence") or []:
        lines.append(f"- [{evidence.get('source_label', evidence.get('source_type', 'Source'))}] {evidence.get('title', 'Untitled')} - {evidence.get('url', '')}")
    lines.extend([
        "",
        "## Key Facts",
        f"- Signal score: {opportunity.get('signal_score', 0)}",
        f"- Creator score: {opportunity.get('creator_score', 0)}",
        f"- Best format: {opportunity.get('best_format', '')}",
        f"- Production effort: {opportunity.get('production_effort', '')}",
        "",
        "## Counterpoints and Caveats",
        opportunity.get("risks_or_caveats", ""),
        "",
        "## Suggested Demo",
        opportunity.get("demo_idea", ""),
        "",
        "## Script Outline",
    ])
    for point in opportunity.get("three_key_points") or []:
        lines.append(f"- {point}")
    lines.extend([
        "",
        "## Script Starter",
        f"- Opening hook: {opportunity.get('opening_hook', '')}",
        f"- Intro context: {opportunity.get('intro_context', '')}",
        f"- Demo segment: {opportunity.get('demo_segment', '')}",
        f"- Caveats: {opportunity.get('caveats', '')}",
        f"- Closing takeaway: {opportunity.get('closing_takeaway', '')}",
        f"- CTA: {opportunity.get('call_to_action', '')}",
        "",
    ])

    content = "\n".join(lines).strip() + "\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path, content


def build_creator_digest(brief: Dict, saved_items: List[Dict], date: str | None = None) -> str:
    """Build the creator-mode daily digest."""
    date = date or datetime.now().strftime("%Y-%m-%d")
    lines = [f"# DailyDex Creator Brief - {date}", ""]

    best = brief.get("best_video_idea")
    lines.extend(["## Best Video Idea Today", ""])
    if best:
        lines.append(f"- Title: {best.get('suggested_titles', {}).get('practical') or best.get('title', '')}")
        lines.append(f"- Hook: {best.get('hook', '')}")
        lines.append(f"- Why now: {best.get('why_viewers_care', '')}")
        lines.append("- Sources:")
        for evidence in best.get("source_evidence", [])[:4]:
            lines.append(f"  - {evidence.get('source_label', evidence.get('source_type', 'Source'))}: {evidence.get('title', '')}")
        lines.append("- Outline:")
        for point in best.get("three_key_points", [])[:3]:
            lines.append(f"  - {point}")
    else:
        lines.append("- No creator opportunity available today.")
    lines.append("")

    lines.extend(["## Shorts Ideas", ""])
    for item in brief.get("shorts_ideas", [])[:5]:
        lines.append(f"- {item.get('hook_line', item.get('title', ''))}")
        lines.append(f"  - Script: {item.get('short_script', '')}")
        lines.append(f"  - Visual: {item.get('visual_idea', '')}")
    lines.append("")

    lines.extend(["## Long-form Candidates", ""])
    for item in brief.get("long_form_candidates", [])[:3]:
        lines.append(f"- {item.get('suggested_titles', {}).get('curiosity') or item.get('title', '')}")
        lines.append(f"  - Angle: {item.get('hook', '')}")
        lines.append(f"  - Outline: {' | '.join(item.get('three_key_points', [])[:3])}")
    lines.append("")

    lines.extend(["## Content Clusters", ""])
    for cluster in brief.get("content_clusters", [])[:5]:
        lines.append(f"- {cluster.get('topic', '')} ({cluster.get('source_count', 0)} sources)")
        lines.append(f"  - Angle: {cluster.get('recommended_angle', '')}")
    lines.append("")

    lines.extend(["## Quick Wins", ""])
    for item in brief.get("quick_wins", [])[:4]:
        lines.append(f"- {item.get('title', '')} [{item.get('best_format', '')}] - effort: {item.get('production_effort', '')}")
    lines.append("")

    lines.extend(["## Saved Pipeline", ""])
    creator_items = [item for item in saved_items if item.get("pipeline_type") == "creator"]
    if not creator_items:
        lines.append("- No creator pipeline items yet.")
    else:
        for item in creator_items[:10]:
            lines.append(f"- {item.get('working_title') or item.get('title', '')} - {item.get('status', 'idea')}")
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# Phase 5: thumbnail variant stub generator
# ─────────────────────────────────────────────────────────────────────────

THUMBNAIL_KINDS = ("face-zoom", "before-after", "headline", "vs-hero", "race")

# Hand-tuned per-kind CTR weights (multiplied against visual_potential signal).
_KIND_CTR_WEIGHT = {
    "face-zoom": 1.12,
    "before-after": 1.06,
    "headline": 0.94,
    "vs-hero": 1.0,
    "race": 0.9,
}

_KIND_SUBTEXT = {
    "face-zoom": "I tried it so you don't have to",
    "before-after": "before → after",
    "headline": "what nobody tells you",
    "vs-hero": "head to head",
    "race": "who wins?",
}


def _deterministic_jitter(seed: str) -> float:
    """Stable [-1.5, +1.5] jitter from a seed string."""
    h = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8], 16)
    return ((h % 300) / 100.0) - 1.5


def _ctr_for_kind(visual_potential: int, kind: str, seed: str) -> float:
    """Deterministic CTR prediction (percent) from visual_potential + kind."""
    base = 3.5 + (visual_potential / 100.0) * 7.0  # 3.5%..10.5%
    pred = base * _KIND_CTR_WEIGHT.get(kind, 1.0) + _deterministic_jitter(seed)
    return round(max(1.0, min(14.0, pred)), 1)


def generate_thumbnail_variants(intel_db, content_hash: str, topic: str = None,
                                count: int = 6, base_item: Dict = None) -> List[Dict]:
    """Create `count` thumbnail_variants rows for one item and return them.

    Mirrors the design's FakeThumb fields — no PNG produced. CTR is a
    deterministic function of visual_potential + kind (v1 stub).
    """
    if intel_db is None:
        return []
    visual_potential = 70
    text_lines = None
    if base_item is not None:
        try:
            factors = _creator_factors(base_item, base_item.get("source_type", "github"),
                                       {"source_count": 1})
            visual_potential = factors["visual_potential"]
            text_lines = _thumbnail_text(topic or primary_topic(base_item), base_item)
        except Exception:
            pass
    if not text_lines:
        base = (topic or "AI STORY").upper()
        text_lines = [base, f"{base} EXPLAINED", "YOU'RE NOT READY"]

    now = time.time()
    variants = []
    for i in range(count):
        kind = THUMBNAIL_KINDS[i % len(THUMBNAIL_KINDS)]
        primary = text_lines[i % len(text_lines)]
        seed = f"{content_hash}:{kind}:{i}"
        hue = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[8:12], 16) % 360
        variant = {
            "id": f"tb-{uuid.uuid4().hex[:12]}",
            "content_hash": content_hash,
            "topic": slugify_topic(topic) if topic else None,
            "kind": kind,
            "text_primary": primary,
            "text_secondary": _KIND_SUBTEXT.get(kind, ""),
            "hue": hue,
            "image_path": None,
            "ctr_pred": _ctr_for_kind(visual_potential, kind, seed),
            "picked": 0,
            "generated_by": "stub",
            "created_at": now,
        }
        intel_db.insert_thumbnail_variant(variant)
        variants.append(serialize_thumbnail_variant(variant))
    variants.sort(key=lambda v: v["ctr_pred"], reverse=True)
    return variants


def serialize_thumbnail_variant(row: Dict) -> Dict:
    """DB row -> API shape (MOCK_DATA_REFERENCE thumbnails[])."""
    return {
        "id": row["id"],
        "content_hash": row["content_hash"],
        "topic": row.get("topic"),
        "kind": row["kind"],
        "text": row.get("text_primary"),
        "subtext": row.get("text_secondary"),
        "hue": row.get("hue"),
        "ctr_pred": row.get("ctr_pred"),
        "image_path": row.get("image_path"),
        "picked": bool(row.get("picked")),
    }
