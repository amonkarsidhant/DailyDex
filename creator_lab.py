#!/usr/bin/env python3
"""creator_lab.py — DailyDex Creator Lab features.

Ten endpoints inspired by MrBeast-style creator-economy obsessions. All routes
live under ``/api/lab/*``. LLM-driven scoring routes through ``cli_registry``
(which respects ``LLM_PROVIDER``, defaulting to NVIDIA NIM in this deploy).

Endpoints
---------
POST /api/lab/title-tournament   — score & rank candidate titles
POST /api/lab/retention-sim       — critique first 30s of a script
POST /api/lab/cpm-safety          — brand-safety + CPM tier estimate
POST /api/lab/virality-forecast   — predicted 7d views w/ confidence
POST /api/lab/thumb-ctr           — score thumbnails (vision LLM if available)
POST /api/lab/longform-to-shorts  — pick best N short-form clips from transcript
POST /api/lab/competitor-pulse    — competitor channel latest-uploads digest
POST /api/lab/audience-overlap    — audience overlap candidates (YT-driven)
POST /api/lab/ab-thumb-swap       — schedule live thumb A/B (stub w/o YT OAuth)
GET  /api/lab/kanban              — pipeline kanban w/ SLA timers
POST /api/lab/ship-it             — one-button: research → brief → script → thumbs
GET  /api/lab/status              — feature-flag matrix
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

import cli_registry

bp = Blueprint("creator_lab", __name__, url_prefix="/api/lab")

# ──────────────────────────────────────────────────────────────────────────── #
# Helpers
# ──────────────────────────────────────────────────────────────────────────── #
def _json_request() -> Dict[str, Any]:
    if not request.is_json:
        return {}
    try:
        return request.get_json(silent=True) or {}
    except Exception:
        return {}


def _llm_json(prompt: str, system: Optional[str] = None,
              timeout: int = 60, fallback: Any = None) -> Any:
    """Call LLM, extract first JSON object from response."""
    res = cli_registry.generate(prompt=prompt, system=system, timeout=timeout)
    text = (res.get("text") or "").strip()
    if not text:
        return fallback
    # Strip code fences
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    # Find first {...} or [...] block
    m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
    if not m:
        return fallback
    try:
        return json.loads(m.group(1))
    except Exception:
        return fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _yt_api_key() -> str:
    return os.environ.get("YOUTUBE_API_KEY", "") or os.environ.get("YT_API_KEY", "")


def _yt_get(path: str, params: Dict[str, str], timeout: int = 15) -> Dict[str, Any]:
    key = _yt_api_key()
    if not key:
        return {}
    params = {**params, "key": key}
    url = f"https://www.googleapis.com/youtube/v3/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)}


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 1: Title Tournament
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/title-tournament", methods=["POST"])
def title_tournament():
    payload = _json_request()
    titles: List[str] = [t for t in (payload.get("titles") or []) if isinstance(t, str) and t.strip()]
    topic: str = (payload.get("topic") or "").strip()
    niche: str = (payload.get("niche") or "AI / developer tools").strip()
    if not titles:
        return jsonify({"error": "Provide 'titles': [str, ...]"}), 400

    rubric = (
        "Score each YouTube title 0-100 across five axes (curiosity, specificity, "
        "emotional_charge, length_fit, niche_resonance). Compute a weighted "
        "overall = 0.30*curiosity + 0.20*specificity + 0.20*emotional_charge + "
        "0.10*length_fit + 0.20*niche_resonance. Return strict JSON: "
        '{"results":[{"title":str,"axes":{...},"overall":int,"why":str,"rewrite":str}]}.'
        " 'rewrite' is a punchier variant. No prose outside JSON."
    )
    prompt = (
        f"Niche: {niche}\nTopic: {topic or '(unspecified)'}\nTitles:\n"
        + "\n".join(f"- {t}" for t in titles[:20])
        + "\n\nReturn JSON only."
    )
    data = _llm_json(prompt, system=rubric, timeout=90,
                     fallback={"results": [{"title": t, "overall": 50,
                                           "why": "LLM unavailable", "rewrite": t}
                                          for t in titles]})
    results = sorted((data or {}).get("results", []),
                     key=lambda r: r.get("overall", 0), reverse=True)
    return jsonify({"ranked": results, "winner": results[0] if results else None,
                    "scored_at": _now_iso()})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 2: First-30s Retention Simulator
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/retention-sim", methods=["POST"])
def retention_sim():
    payload = _json_request()
    script: str = (payload.get("script") or "").strip()
    target_audience: str = (payload.get("audience") or "technical builders, AI/developer tools").strip()
    if not script:
        return jsonify({"error": "Provide 'script': str (full or first 30s)"}), 400

    rubric = (
        "You are a YouTube retention coach. Read the opening of a script (first ~30 "
        "seconds of spoken delivery, ≈75 words). Score on a 0-100 retention probability "
        "(viewer still watching at the 30s mark). Identify the *exact phrase* that risks "
        "a swipe-away, and propose a pattern-interrupt rewrite that opens with a concrete "
        "claim or number. Return JSON: "
        '{"retention_score":int,"first_hook":str,"swipe_risk_phrase":str,'
        '"diagnosis":str,"rewrite":str,"pattern_interrupt_used":str}.'
    )
    prompt = f"Audience: {target_audience}\nScript opening:\n{script[:2000]}\n\nReturn JSON only."
    data = _llm_json(prompt, system=rubric, timeout=90,
                     fallback={"retention_score": 50, "diagnosis": "LLM unavailable",
                               "rewrite": script[:200]})
    return jsonify({**(data or {}), "scored_at": _now_iso()})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 3: CPM / Brand-Safety Pre-Score
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/cpm-safety", methods=["POST"])
def cpm_safety():
    payload = _json_request()
    script: str = (payload.get("script") or payload.get("text") or "").strip()
    title: str = (payload.get("title") or "").strip()
    if not script and not title:
        return jsonify({"error": "Provide 'script' or 'title'"}), 400

    rubric = (
        "Rate this YouTube content's monetization profile. Return JSON: "
        '{"cpm_tier":"low|mid|high","cpm_usd_estimate":[lo,hi],'
        '"demonetization_risk":int(0-100),"flagged_topics":[str],'
        '"brand_categories":[str],"safer_rewrites":[{"of":str,"to":str}],'
        '"summary":str}. '
        "Tiers anchor at: low=$1-3 CPM, mid=$5-15, high=$20-50 (US, 2026). "
        "Flag NSFW, violence, controversial politics, medical claims, etc."
    )
    prompt = f"Title: {title}\n\nScript:\n{script[:3500]}\n\nReturn JSON only."
    data = _llm_json(prompt, system=rubric, timeout=90,
                     fallback={"cpm_tier": "mid", "demonetization_risk": 20,
                               "summary": "LLM unavailable"})
    return jsonify({**(data or {}), "scored_at": _now_iso()})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 4: Virality Forecast
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/virality-forecast", methods=["POST"])
def virality_forecast():
    payload = _json_request()
    topic: str = (payload.get("topic") or "").strip()
    title: str = (payload.get("title") or "").strip()
    channel_size: int = int(payload.get("channel_subs") or 0)
    niche: str = (payload.get("niche") or "AI / developer tools").strip()
    posted_at: str = payload.get("planned_post_time") or _now_iso()
    if not topic and not title:
        return jsonify({"error": "Provide 'topic' or 'title'"}), 400

    rubric = (
        "Forecast 7-day YouTube views for a video. Use heuristics: niche size, topic "
        "freshness/timeliness, title CTR estimate, channel subscriber base, day-of-week "
        "effect. Return JSON: "
        '{"forecast_views_7d":{"p10":int,"p50":int,"p90":int},'
        '"confidence":int(0-100),"drivers":[str],"risks":[str],"comparables":[str]}. '
        "Be honest about uncertainty for unknown channels."
    )
    prompt = (
        f"Niche: {niche}\nTopic: {topic}\nTitle: {title}\nChannel subs: {channel_size}\n"
        f"Planned post: {posted_at}\n\nReturn JSON only."
    )
    data = _llm_json(prompt, system=rubric, timeout=90,
                     fallback={"forecast_views_7d": {"p10": 100, "p50": 1000, "p90": 10000},
                               "confidence": 20, "drivers": ["LLM unavailable"]})
    return jsonify({**(data or {}), "scored_at": _now_iso()})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 5: Thumbnail CTR Predictor
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/thumb-ctr", methods=["POST"])
def thumb_ctr():
    """Accepts {"thumbs":[{"id":str,"url":str|"caption":str|"prompt":str}]}.

    If a vision LLM is configured (NVIDIA_VLM_MODEL or fal.ai), uses the image.
    Otherwise scores from caption/prompt text only (still useful as a comparator).
    """
    payload = _json_request()
    thumbs = payload.get("thumbs") or []
    niche: str = (payload.get("niche") or "AI / developer tools").strip()
    topic: str = (payload.get("topic") or "").strip()
    if not isinstance(thumbs, list) or not thumbs:
        return jsonify({"error": "Provide 'thumbs': [{id,url|caption|prompt}, ...]"}), 400

    # Build description per thumb. Vision-LLM path is opt-in via NVIDIA_VLM_MODEL.
    vlm_model = os.environ.get("NVIDIA_VLM_MODEL", "").strip()
    desc_lines = []
    for t in thumbs[:12]:
        tid = t.get("id") or f"thumb_{len(desc_lines)+1}"
        cap = t.get("caption") or t.get("prompt") or t.get("description") or ""
        url = t.get("url") or ""
        desc_lines.append(f"[{tid}] url={url or '(no-url)'} caption=\"{cap[:180]}\"")

    rubric = (
        "Score YouTube thumbnails 0-100 on click-through likelihood. Five axes: "
        "focal_clarity, face_or_subject_strength, color_contrast, curiosity_cue, "
        "text_legibility. Overall = mean. Return strict JSON: "
        '{"results":[{"id":str,"overall":int,"axes":{...},"why":str,"upgrade":str}],'
        '"top3":[id,id,id]}. '
        "Be brutal — most thumbnails are mediocre."
    )
    prompt = (
        f"Niche: {niche}\nTopic: {topic or '(unspecified)'}\n"
        f"Thumbnails to score (textual descriptions only):\n"
        + "\n".join(desc_lines)
        + ("\n\n(Vision LLM not configured — score using caption/prompt text only.)"
           if not vlm_model else "")
        + "\n\nReturn JSON only."
    )
    data = _llm_json(prompt, system=rubric, timeout=120,
                     fallback={"results": [{"id": t.get("id", f"t{i}"), "overall": 50,
                                           "why": "LLM unavailable"}
                                          for i, t in enumerate(thumbs)]})
    results = sorted((data or {}).get("results", []),
                     key=lambda r: r.get("overall", 0), reverse=True)
    return jsonify({"ranked": results,
                    "top3": [r.get("id") for r in results[:3]],
                    "vision_mode": bool(vlm_model),
                    "scored_at": _now_iso()})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 6: Longform → Shorts auto-cutter
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/longform-to-shorts", methods=["POST"])
def longform_to_shorts():
    """Picks N highest-hook ~30s segments from a transcript.

    Input: {"transcript":[{"start":sec,"end":sec,"text":str}], "n":15}.
    If 'transcript' is a string, naive sentence splitting is used.

    NOTE: STT (whisper) and ffmpeg cutting are not done here — caller must do
    that separately. This endpoint is the *picker*. Wire whisper.cpp/ffmpeg in
    a downstream worker when binaries are available.
    """
    payload = _json_request()
    transcript = payload.get("transcript")
    n: int = int(payload.get("n") or 15)
    niche: str = (payload.get("niche") or "AI / developer tools").strip()

    if not transcript:
        return jsonify({"error": "Provide 'transcript' (list of segments or full text)"}), 400

    # Normalize to list of segments
    if isinstance(transcript, str):
        sentences = re.split(r"(?<=[.!?])\s+", transcript.strip())
        segs = []
        t = 0.0
        for s in sentences:
            dur = max(2.5, min(8.0, len(s.split()) * 0.35))
            segs.append({"start": round(t, 2), "end": round(t + dur, 2), "text": s})
            t += dur
        transcript = segs

    transcript = transcript[:400]  # cap for prompt size
    lines = []
    for i, s in enumerate(transcript):
        lines.append(f"[{i}] t={s.get('start', 0):.1f}-{s.get('end', 0):.1f}s: {s.get('text', '')[:160]}")

    rubric = (
        "Pick the N most hook-worthy 25-45 second clips from this transcript. "
        "Each clip should start on a strong statement (number, claim, twist) and end "
        "before the next idea starts. Return JSON: "
        '{"clips":[{"start_idx":int,"end_idx":int,"start_sec":float,"end_sec":float,'
        '"hook_score":int(0-100),"hook_line":str,"caption":str,"vertical_crop_hint":str}],'
        '"strategy":str}. '
        "'vertical_crop_hint' = 'center', 'left-face', 'right-face', 'top', 'bottom' "
        "based on where the speaker likely is. caption ≤ 80 chars."
    )
    prompt = f"N={n}\nNiche: {niche}\nTranscript segments:\n" + "\n".join(lines) + "\n\nReturn JSON only."
    data = _llm_json(prompt, system=rubric, timeout=120,
                     fallback={"clips": [], "strategy": "LLM unavailable"})
    return jsonify({**(data or {}),
                    "binaries": {
                        "whisper": _have("whisper") or _have("whisper-cli") or _have("whisper.cpp"),
                        "ffmpeg": _have("ffmpeg"),
                    },
                    "todo": ("Wire whisper STT + ffmpeg vertical-crop pipeline. "
                             "Use 'binaries' to gate auto-cut worker."),
                    "scored_at": _now_iso()})


def _have(cmd: str) -> bool:
    import shutil
    return bool(shutil.which(cmd))


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 7: Competitor War Room
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/competitor-pulse", methods=["POST"])
def competitor_pulse():
    """Latest uploads from competitor channels + post-time analytics.

    Input: {"channel_ids":[str], "max_per_channel":5}
    Uses YouTube Data API v3 if YOUTUBE_API_KEY env var set; otherwise returns
    a structured stub.
    """
    payload = _json_request()
    channel_ids: List[str] = [c for c in (payload.get("channel_ids") or []) if isinstance(c, str)]
    max_per: int = int(payload.get("max_per_channel") or 5)
    if not channel_ids:
        return jsonify({"error": "Provide 'channel_ids': [yt_channel_id, ...]"}), 400

    if not _yt_api_key():
        return jsonify({
            "available": False,
            "reason": "Set YOUTUBE_API_KEY env var to enable competitor pulse.",
            "stub": [{"channel_id": c, "videos": []} for c in channel_ids],
        }), 200

    results = []
    for cid in channel_ids[:20]:
        ch = _yt_get("channels", {"part": "snippet,statistics,contentDetails", "id": cid})
        uploads_pl = (((ch.get("items") or [{}])[0].get("contentDetails") or {})
                      .get("relatedPlaylists") or {}).get("uploads")
        if not uploads_pl:
            results.append({"channel_id": cid, "error": "no_uploads_playlist"})
            continue
        pl = _yt_get("playlistItems",
                     {"part": "snippet,contentDetails", "playlistId": uploads_pl,
                      "maxResults": str(min(max_per, 50))})
        videos = []
        for it in pl.get("items", []):
            sn = it.get("snippet", {})
            videos.append({
                "video_id": sn.get("resourceId", {}).get("videoId"),
                "title": sn.get("title"),
                "published_at": sn.get("publishedAt"),
                "thumb": (sn.get("thumbnails", {}).get("medium") or {}).get("url"),
            })
        snip = ((ch.get("items") or [{}])[0].get("snippet") or {})
        stats = ((ch.get("items") or [{}])[0].get("statistics") or {})
        results.append({
            "channel_id": cid,
            "title": snip.get("title"),
            "subs": stats.get("subscriberCount"),
            "view_count": stats.get("viewCount"),
            "videos": videos,
        })
    return jsonify({"available": True, "channels": results, "fetched_at": _now_iso()})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 8: Audience Overlap Miner
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/audience-overlap", methods=["POST"])
def audience_overlap():
    """Surface adjacent channels via YT recommendation graph proxies.

    True overlap data needs YT Analytics (channel-owner OAuth). For now, infers
    adjacency by fetching 'related' search results from a seed channel's recent
    videos and aggregating co-mentioned channel IDs.
    """
    payload = _json_request()
    seed_channel: str = (payload.get("channel_id") or "").strip()
    if not seed_channel:
        return jsonify({"error": "Provide 'channel_id'"}), 400
    if not _yt_api_key():
        return jsonify({
            "available": False,
            "reason": "Set YOUTUBE_API_KEY env var to enable overlap mining.",
            "stub": {"channel_id": seed_channel, "neighbors": []},
        })

    # Get latest 5 videos from seed, then run search for each title; aggregate channel IDs.
    ch = _yt_get("channels", {"part": "contentDetails", "id": seed_channel})
    up_pl = (((ch.get("items") or [{}])[0].get("contentDetails") or {})
             .get("relatedPlaylists") or {}).get("uploads")
    titles: List[str] = []
    if up_pl:
        pl = _yt_get("playlistItems",
                     {"part": "snippet", "playlistId": up_pl, "maxResults": "5"})
        titles = [it["snippet"]["title"] for it in pl.get("items", []) if it.get("snippet")]
    counts: Dict[str, Dict[str, Any]] = {}
    for q in titles:
        s = _yt_get("search", {"part": "snippet", "q": q, "type": "video", "maxResults": "10"})
        for it in s.get("items", []):
            cid = (it.get("snippet") or {}).get("channelId")
            cname = (it.get("snippet") or {}).get("channelTitle")
            if not cid or cid == seed_channel:
                continue
            row = counts.setdefault(cid, {"channel_id": cid, "name": cname, "co_mentions": 0})
            row["co_mentions"] += 1
    neighbors = sorted(counts.values(), key=lambda r: r["co_mentions"], reverse=True)[:20]
    return jsonify({"available": True, "seed": seed_channel,
                    "neighbors": neighbors, "fetched_at": _now_iso(),
                    "note": ("Inferred from co-mentioned channels in search results. "
                             "True overlap needs YT Analytics OAuth.")})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 9: Live A/B Thumb Swap (scheduler)
# ──────────────────────────────────────────────────────────────────────────── #
_AB_SCHEDULE: Dict[str, Dict[str, Any]] = {}


@bp.route("/ab-thumb-swap", methods=["POST"])
def ab_thumb_swap():
    """Schedule a thumbnail A/B test.

    Input: {"video_id":str,"thumb_a":url,"thumb_b":url,
            "swap_after_minutes":int,"ctr_floor":float}.
    Real execution needs YT Data API v3 + channel OAuth + a worker that polls
    analytics. This endpoint records intent.
    """
    payload = _json_request()
    vid = (payload.get("video_id") or "").strip()
    a = (payload.get("thumb_a") or "").strip()
    b = (payload.get("thumb_b") or "").strip()
    if not vid or not a or not b:
        return jsonify({"error": "Provide 'video_id','thumb_a','thumb_b'"}), 400
    rec = {
        "video_id": vid,
        "thumb_a": a,
        "thumb_b": b,
        "swap_after_minutes": int(payload.get("swap_after_minutes") or 360),
        "ctr_floor": float(payload.get("ctr_floor") or 0.04),
        "scheduled_at": _now_iso(),
        "status": "scheduled",
    }
    _AB_SCHEDULE[vid] = rec
    return jsonify({
        "ok": True,
        "schedule": rec,
        "available": False,
        "reason": ("YT OAuth not wired. Implement worker that polls "
                   "youtube.analytics impressions/CTR and calls youtube.thumbnails.set."),
    })


@bp.route("/ab-thumb-swap", methods=["GET"])
def ab_thumb_swap_list():
    return jsonify({"schedules": list(_AB_SCHEDULE.values())})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 10: Pipeline Kanban with SLA timers
# ──────────────────────────────────────────────────────────────────────────── #
PIPELINE_STAGES = ["idea", "research", "script", "thumbs", "edit", "scheduled", "published"]
PIPELINE_SLA_HOURS = {"idea": 4, "research": 6, "script": 8, "thumbs": 4,
                      "edit": 24, "scheduled": 24, "published": 0}


@bp.route("/kanban", methods=["GET"])
def kanban():
    """Return current pipeline grouped by stage w/ SLA breach flags.

    Reads from data/pipeline.json if present, else returns empty stages.
    """
    base = os.path.dirname(os.path.abspath(__file__))
    pf = os.path.join(os.environ.get("DATA_DIR", os.path.join(base, "data")),
                      "pipeline.json")
    items: List[Dict[str, Any]] = []
    if os.path.exists(pf):
        try:
            with open(pf, encoding="utf-8") as f:
                raw = json.load(f)
                items = raw if isinstance(raw, list) else raw.get("items", [])
        except Exception:
            items = []

    now = datetime.now(timezone.utc)
    grouped: Dict[str, List[Dict[str, Any]]] = {s: [] for s in PIPELINE_STAGES}
    for it in items:
        stage = it.get("stage") or "idea"
        if stage not in grouped:
            grouped[stage] = []
        entered = it.get("stage_entered_at")
        breached = False
        age_hours = None
        if entered:
            try:
                dt = datetime.fromisoformat(entered.replace("Z", "+00:00"))
                age_hours = (now - dt).total_seconds() / 3600
                breached = age_hours > PIPELINE_SLA_HOURS.get(stage, 24)
            except Exception:
                pass
        it = {**it, "age_hours": age_hours, "sla_breached": breached}
        grouped[stage].append(it)
    return jsonify({"stages": PIPELINE_STAGES, "sla_hours": PIPELINE_SLA_HOURS,
                    "by_stage": grouped, "now": _now_iso()})


# ──────────────────────────────────────────────────────────────────────────── #
# Feature 11 (bonus): Ship It — one-button research→brief→script→thumbs
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/ship-it", methods=["POST"])
def ship_it():
    """Synchronous mini-pipeline: takes a topic, returns full asset bundle.

    Heavy version should run async via studio_job, but this gives a working demo.
    """
    payload = _json_request()
    topic: str = (payload.get("topic") or "").strip()
    niche: str = (payload.get("niche") or "AI / developer tools").strip()
    if not topic:
        return jsonify({"error": "Provide 'topic'"}), 400

    started = time.time()
    out: Dict[str, Any] = {"topic": topic, "niche": niche, "stages": []}

    def _step(name, prompt, system=None, parse_json=False, timeout=90):
        t0 = time.time()
        if parse_json:
            data = _llm_json(prompt, system=system, timeout=timeout)
        else:
            res = cli_registry.generate(prompt=prompt, system=system, timeout=timeout)
            data = res.get("text")
        out["stages"].append({"name": name, "elapsed_ms": int((time.time() - t0) * 1000),
                              "ok": bool(data)})
        return data

    # 1) Research summary
    research = _step("research",
                     f"Write a tight research brief (~250 words) on: {topic}. "
                     f"Audience: {niche}. Include 3 concrete data points or examples.",
                     timeout=120)
    out["research"] = research

    # 2) Titles
    titles_data = _step("titles",
                        f"Generate 10 punchy YouTube titles for a video on: {topic}. "
                        f"Niche: {niche}. Return JSON: {{\"titles\":[str]}}.",
                        parse_json=True, timeout=60)
    out["title_candidates"] = (titles_data or {}).get("titles", [])

    # 3) Script (first 60s)
    script = _step("script",
                   f"Write the opening 60 seconds of a YouTube script on: {topic}. "
                   f"Audience: {niche}. Strong hook in first 5 seconds. "
                   f"Plain prose, no stage directions.",
                   timeout=120)
    out["script_opener"] = script

    # 4) Thumb prompts
    thumb_prompts = _step("thumbs",
                          f"Generate 4 distinct YouTube thumbnail prompts (for an image "
                          f"generator) for a video on: {topic}. Niche: {niche}. "
                          f"Return JSON: {{\"thumbs\":[{{\"id\":str,\"prompt\":str,"
                          f"\"caption\":str}}]}}.",
                          parse_json=True, timeout=60)
    out["thumb_candidates"] = (thumb_prompts or {}).get("thumbs", [])

    out["elapsed_ms"] = int((time.time() - started) * 1000)
    out["provider"] = cli_registry.probe().get("available", [])
    out["finished_at"] = _now_iso()
    return jsonify(out)


# ──────────────────────────────────────────────────────────────────────────── #
# Status / feature-flag matrix
# ──────────────────────────────────────────────────────────────────────────── #
@bp.route("/status", methods=["GET"])
def status():
    providers = cli_registry.probe()
    return jsonify({
        "features": {
            "title_tournament": {"ready": True, "needs": []},
            "retention_sim":    {"ready": True, "needs": []},
            "cpm_safety":       {"ready": True, "needs": []},
            "virality_forecast":{"ready": True, "needs": []},
            "thumb_ctr":        {"ready": True, "needs": ["NVIDIA_VLM_MODEL (optional, for image-based scoring)"]},
            "longform_to_shorts": {
                "ready": True,
                "needs": ["whisper binary (for STT)", "ffmpeg binary (for cuts)"],
                "binaries": {"whisper": _have("whisper") or _have("whisper-cli"),
                             "ffmpeg": _have("ffmpeg")},
            },
            "competitor_pulse": {"ready": bool(_yt_api_key()),
                                 "needs": ["YOUTUBE_API_KEY env var"]},
            "audience_overlap": {"ready": bool(_yt_api_key()),
                                 "needs": ["YOUTUBE_API_KEY env var"]},
            "ab_thumb_swap":    {"ready": False,
                                 "needs": ["YouTube OAuth (channel-owner)", "background worker"]},
            "kanban":           {"ready": True, "needs": []},
            "ship_it":          {"ready": True, "needs": []},
        },
        "llm_providers": providers,
        "now": _now_iso(),
    })
