#!/usr/bin/env python3
"""Autonomous news-factory orchestrator.

Chains the pieces that already exist into one run:
clusters (creator_intelligence) -> hook/script (clip_generator) ->
guardrails (creator_profile banned phrases + topics.json blocked keywords) ->
vertical short render (video_renderer) -> factory_queue approval row.

Nothing here publishes on its own: every rendered short lands in the
factory_queue as 'pending_review' unless its virality score clears the
profile's auto_forge_score threshold, in which case it is marked 'approved'
(still not published — publish is a separate explicit route).
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional

from creator_intelligence import build_story_candidates, build_topic_clusters

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREATOR_PROFILE_PATH = os.environ.get(
    "CREATOR_PROFILE_PATH", os.path.join(BASE_DIR, "config", "creator_profile.json")
)
TOPICS_CONFIG_PATH = os.environ.get(
    "CONFIG_PATH", os.path.join(BASE_DIR, "config", "topics.json")
)

# Background run state, same pattern as dashboard_new's refresh job.
_factory_lock = threading.Lock()
_factory_state: Dict[str, Any] = {"running": False, "result": None}


def _load_json(path: str) -> Dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# Scripts are machine-written; nobody ran any tests. First-person empirical
# claims are therefore fabrications by construction and must never ship.
_FABRICATION_RE = re.compile(
    r"\b(?:we|i)\s+(?:ran|tested|benchmarked|verified|measured|clocked|deployed|pitted)\b"
    r"|\bour\s+(?:tests?|benchmarks?|measurements?)\b"
    r"|\blink\s+in\s+(?:the\s+)?bio\b",
    re.IGNORECASE,
)


def check_guardrails(text: str,
                     profile: Optional[Dict] = None,
                     topics_config: Optional[Dict] = None) -> List[str]:
    """Return list of guardrail violations found in text (empty = clean)."""
    profile = profile if profile is not None else _load_json(CREATOR_PROFILE_PATH)
    topics_config = topics_config if topics_config is not None else _load_json(TOPICS_CONFIG_PATH)
    lowered = text.lower()
    violations = []
    for phrase in profile.get("banned_phrases", []):
        if phrase.lower() in lowered:
            violations.append(f"banned phrase: {phrase}")
    for keyword in topics_config.get("blocked_keywords", []):
        if keyword.lower() in lowered:
            violations.append(f"blocked keyword: {keyword}")
    for match in set(m.group(0).lower() for m in _FABRICATION_RE.finditer(text)):
        violations.append(f"fabricated claim: '{match}' (no tests were run)")
    return violations


def _cluster_lead_item(cluster: Dict) -> Dict:
    """Best supporting item of a cluster, shaped like a saved item."""
    related = cluster.get("related_items") or []
    lead = max(related, key=lambda r: r.get("signal_score", 0), default={})
    return {
        "id": 0,
        "title": lead.get("title") or cluster.get("topic", ""),
        "url": lead.get("url", ""),
        "source_type": lead.get("source_type", ""),
        # NOTE: not the cluster topic label — that leaked verbatim into
        # generated scripts ("...all 46. General We verified...").
        "description": lead.get("description", ""),
        "signal_score": lead.get("signal_score", 0),
    }


def _shape_item(row: Dict, cluster: Dict) -> Dict:
    """A cluster's related_item shaped like a saved item."""
    return {
        "id": 0,
        "title": row.get("title") or cluster.get("topic", ""),
        "url": row.get("url", ""),
        "source_type": row.get("source_type", ""),
        "description": row.get("description", ""),
        "signal_score": row.get("signal_score", 0),
    }


def _has_evidence(record: Optional[Dict]) -> bool:
    if not record:
        return False
    return bool(record.get("facts") or record.get("quotes")
                or str(record.get("excerpt") or "").strip())


def gather_cluster_evidence(cluster: Dict, lead: Dict, gather_evidence_fn) -> Dict[str, Any]:
    """Evidence for a story, falling back through its corroborating sources.

    Major publishers block automated fetching — Axios and friends answer 403 to
    anything that is not a browser, and harder still from a datacenter IP. A
    story corroborated across three sources should not be unrenderable because
    the single highest-scoring one happens to sit behind a bot wall, so try each
    member in turn and keep the first that yields something citable.
    """
    seen = set()
    attempts = []
    for candidate in [lead] + [_shape_item(row, cluster)
                               for row in (cluster.get("related_items") or [])]:
        url = str(candidate.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            record = gather_evidence_fn(candidate)
        except Exception as exc:
            attempts.append(f"{url}: {exc}")
            continue
        if _has_evidence(record):
            record = dict(record)
            record["evidence_source_url"] = url
            record["evidence_attempts"] = attempts
            return record
        # A fetcher may legitimately return None rather than an error record.
        reason = (record or {}).get("error") or "no citable content"
        attempts.append(f"{url}: {reason}")
    return {"facts": [], "quotes": [], "excerpt": "", "evidence_attempts": attempts,
            "error": "; ".join(attempts[-3:]) or "no source could be retrieved"}


def _cluster_source_urls(cluster: Dict, lead: Optional[Dict] = None, limit: int = 6) -> List[str]:
    """URLs the script was grounded in, lead first, de-duplicated.

    Carried onto the queue row so a published video can credit its sources
    instead of asserting claims with nothing to point at.
    """
    urls: List[str] = []
    candidates = []
    if lead and lead.get("url"):
        candidates.append(lead["url"])
    candidates.extend(item.get("url", "") for item in (cluster.get("related_items") or []))
    for url in candidates:
        url = str(url or "").strip()
        if url and url not in urls and url.lower().startswith(("http://", "https://")):
            urls.append(url)
    return urls[:limit]


def run_factory(intel_db,
                 scored_data: Dict,
                 limit: int = 3,
                 cluster_slug: Optional[str] = None,
                 auto_approve: bool = True,
                render_fn: Optional[Callable] = None,
                generate_clips_fn: Optional[Callable] = None,
                gather_evidence_fn: Optional[Callable] = None,
                use_stories: bool = True) -> Dict[str, Any]:
    """One factory pass: pick top stories, ground, script, gate, render, enqueue.

    render_fn / generate_clips_fn / gather_evidence_fn injectable for tests;
    default to the real video_renderer / clip_generator / evidence modules.

    ``use_stories`` selects story anchors (a real headline) over TOPIC_PATTERNS
    clusters (a category label such as "AI Tools"). Pass False for the legacy
    taxonomy behaviour.
    """
    if render_fn is None:
        from video_renderer import render_short_video as render_fn
    if generate_clips_fn is None:
        from clip_generator import generate_clips as generate_clips_fn
    if gather_evidence_fn is None:
        from evidence import gather_evidence as gather_evidence_fn

    profile = _load_json(CREATOR_PROFILE_PATH)
    topics_config = _load_json(TOPICS_CONFIG_PATH)
    auto_approve_score = profile.get("automation", {}).get("auto_forge_score", 82)

    if use_stories:
        clusters = build_story_candidates(scored_data, intel_db=intel_db, limit=max(limit * 4, 12))
        if not clusters:
            clusters = build_topic_clusters(scored_data, intel_db=intel_db)
    else:
        clusters = build_topic_clusters(scored_data, intel_db=intel_db)
    skip_topics = set(intel_db.factory_active_topics())
    if cluster_slug:
        clusters = [c for c in clusters if c.get("slug") == cluster_slug]
    candidates = [c for c in clusters if c.get("topic") not in skip_topics][:limit]

    results = {"queued": [], "blocked": [], "failed": [], "skipped_topics": sorted(skip_topics)}

    for cluster in candidates:
        topic = cluster.get("topic", "Unknown")
        lead = _cluster_lead_item(cluster)
        source_urls = _cluster_source_urls(cluster, lead)
        try:
            lead_evidence = gather_cluster_evidence(cluster, lead, gather_evidence_fn)
            has_evidence = _has_evidence(lead_evidence)
            if not has_evidence and profile.get("automation", {}).get("block_unevidenced_renders", True):
                detail = str(lead_evidence.get("error") or "")[:300]
                row_id = intel_db.factory_enqueue(
                    topic, lead["title"], status="blocked",
                    error=("No source evidence was available; render blocked by creator "
                           f"safety settings. Tried: {detail}"),
                    source_urls=source_urls,
                )
                results["blocked"].append({
                    "id": row_id,
                    "topic": topic,
                    "violations": ["source evidence required"],
                })
                continue
            clips = generate_clips_fn(lead, num_clips=1, evidence=lead_evidence)
            if not clips:
                results["failed"].append({"topic": topic, "error": "no clip generated"})
                continue
            clip = clips[0]
            title = clip.get("title") or lead["title"]
            hook = clip.get("hook_text", "")
            script = clip.get("script_text", "") or hook
            virality = float(clip.get("virality_score", 0))

            violations = check_guardrails(f"{title} {hook} {script}", profile, topics_config)
            if violations:
                row_id = intel_db.factory_enqueue(
                    topic, title, hook, script,
                    status="blocked", error="; ".join(violations), virality_score=virality,
                    source_urls=source_urls,
                )
                results["blocked"].append({"id": row_id, "topic": topic, "violations": violations})
                continue

            render = render_fn(
                title=title, hook_text=hook, script_text=script,
                clip_id=f"factory-{uuid.uuid4().hex[:12]}",
                virality_score=virality,
                evidence=lead_evidence,
                signal_context={
                    "average_signal_score": cluster.get("average_signal_score", 0),
                    "source_count": cluster.get("source_count", 0),
                    "sources": cluster.get("sources", []),
                },
            )
            if not render.get("success"):
                row_id = intel_db.factory_enqueue(
                    topic, title, hook, script,
                    status="render_failed", error=str(render.get("error", "unknown")),
                    virality_score=virality, source_urls=source_urls,
                )
                results["failed"].append({"id": row_id, "topic": topic, "error": render.get("error")})
                continue

            status = "approved" if auto_approve and virality >= auto_approve_score else "pending_review"
            row_id = intel_db.factory_enqueue(
                topic, title, hook, script,
                video_path=render.get("video_path", ""),
                virality_score=virality, status=status, source_urls=source_urls,
            )
            results["queued"].append({"id": row_id, "topic": topic, "status": status,
                                      "virality": virality, "video_path": render.get("video_path", "")})
        except Exception as exc:
            results["failed"].append({"topic": topic, "error": str(exc)})

    return results


def start_factory_run(intel_db, scored_data: Dict, limit: int = 3) -> bool:
    """Kick off a factory pass in a background thread. False if already running."""
    with _factory_lock:
        if _factory_state["running"]:
            return False
        _factory_state["running"] = True
        _factory_state["result"] = None

    def _job():
        try:
            result = run_factory(intel_db, scored_data, limit=limit)
        except Exception as exc:
            result = {"error": str(exc)}
        with _factory_lock:
            _factory_state["result"] = result
            _factory_state["running"] = False

    threading.Thread(target=_job, daemon=True).start()
    return True


def factory_status() -> Dict[str, Any]:
    with _factory_lock:
        return {"running": _factory_state["running"], "result": _factory_state["result"]}
