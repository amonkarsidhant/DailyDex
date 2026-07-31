#!/usr/bin/env python3
"""AI-powered clip generation for Shorts repurposing.

Replaces the mock clip stubs in ``api_integrations.py`` with real
LLM-driven segment picking and hook writing.

LLM call path: reuses ``llm_summary.query_llm`` (multi-provider dispatcher)
so the user's configured provider (Gemini CLI, Claude, NVIDIA NIM, Ollama,
OpenAI, Anthropic, etc.) is honoured automatically.

Fallback: if the LLM is unreachable the module falls back to rule-based
extraction — splitting content into segments by topic boundaries and ranking
them by keyword density + structural heuristics.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Project imports — same layer, same patterns as llm_summary.py
# ---------------------------------------------------------------------------

from llm_summary import (
    _extract_json_object,
    load_creator_profile,
    query_llm,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREATOR_PROFILE_PATH = os.environ.get(
    "CREATOR_PROFILE_PATH",
    os.path.join(BASE_DIR, "config", "creator_profile.json"),
)

# Emotional / high-engagement trigger words used by score_clip_virality
_EMOTION_WORDS: set[str] = {
    "secret", "mistake", "actually", "nobody", "everyone", "wrong",
    "surprising", "shocking", "unexpected", "hidden", "truth", "myth",
    "hack", "trick", "banned", "free", "fastest", "easiest", "worst",
    "best", "only", "never", "always", "stop", "warning", "avoid",
    "finally", "proof", "exactly", "real", "honest", "ugly", "brutal",
    "painful", "insane", "ridiculous",
}

# Paragraph / section boundary heuristics
_SECTION_BREAK_RE = re.compile(
    r"(?:\n\s*\n)"           # double newline
    r"|(?:^#{1,4}\s)",       # markdown heading
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Virality scoring — deterministic heuristics, no LLM needed
# ---------------------------------------------------------------------------

def score_clip_virality(hook: str, title: str) -> float:
    """Score a clip's viral potential 0–100 using structural heuristics.

    Factors considered:
        - Hook length (sweet spot 8–15 words)
        - Emotional / power-word density
        - Starts with a question or number
        - Contains a pattern interrupt cue ("but", "except", "however")
        - Title conciseness (< 60 chars preferred)
    """
    score = 50.0  # neutral baseline

    # --- Hook analysis ---
    hook_lower = hook.lower().strip()
    hook_words = hook_lower.split()
    hook_word_count = len(hook_words)

    # Length sweet spot: 8–15 words → +15, outside that → penalty
    if 8 <= hook_word_count <= 15:
        score += 15
    elif hook_word_count < 5:
        score -= 10
    elif hook_word_count > 20:
        score -= 8

    # Emotion / power words
    emotion_hits = sum(1 for w in hook_words if w.strip(".,!?\"'") in _EMOTION_WORDS)
    score += min(emotion_hits * 6, 18)  # cap contribution

    # Starts with a question
    if hook_lower.endswith("?") or hook_lower.startswith(("why ", "how ", "what ", "did you", "have you", "is it")):
        score += 10

    # Starts with a number / stat
    if hook_words and re.match(r"^\d", hook_words[0]):
        score += 8

    # Pattern interrupt words
    interrupt_words = {"but", "except", "however", "yet", "actually", "turns out", "plot twist"}
    if any(iw in hook_lower for iw in interrupt_words):
        score += 7

    # --- Title analysis ---
    title_len = len(title)
    if 25 <= title_len <= 60:
        score += 5
    elif title_len > 80:
        score -= 5

    # Clamp to [0, 100]
    return round(max(0.0, min(100.0, score)), 1)


# ---------------------------------------------------------------------------
# Rule-based fallback — no LLM required
# ---------------------------------------------------------------------------

def _split_into_segments(text: str, max_segments: int = 10) -> List[Dict[str, Any]]:
    """Split long-form text into topical segments by paragraph/heading breaks."""
    if not text or not text.strip():
        return []

    raw_parts = _SECTION_BREAK_RE.split(text.strip())
    # Merge very short fragments (< 40 chars) with the next segment
    merged: list[str] = []
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        if merged and len(merged[-1]) < 40:
            merged[-1] = merged[-1] + " " + part
        else:
            merged.append(part)

    segments: list[dict[str, Any]] = []
    for idx, block in enumerate(merged[:max_segments]):
        sentences = re.split(r"(?<=[.!?])\s+", block.strip())
        first_sentence = sentences[0] if sentences else block[:120]
        # Estimate read duration: ~2.5 words/sec for spoken delivery
        word_count = len(block.split())
        duration_sec = word_count / 2.5
        segments.append({
            "index": idx,
            "text": block,
            "first_sentence": first_sentence,
            "word_count": word_count,
            "duration_sec": round(duration_sec, 1),
        })
    return segments


def _keyword_density(text: str) -> float:
    """Return a 0–1 density score based on how many engagement keywords appear."""
    words = text.lower().split()
    if not words:
        return 0.0
    hits = sum(1 for w in words if w.strip(".,!?\"'") in _EMOTION_WORDS)
    return min(hits / max(len(words), 1), 1.0)


def _build_full_script_text(clip_title: str, hook: str, item: Dict[str, Any], idx: int = 1,
                            evidence: Optional[Dict[str, Any]] = None) -> str:
    """Build an honest fallback script from real item data only.

    Every sentence must be traceable to the item or fetched evidence — no
    invented benchmarks, no first-person test claims. When we have little
    real material, a short truthful script beats a long fabricated one.
    """
    parts = [hook]

    desc = (item.get("description") or item.get("abstract") or "").strip()
    if desc:
        parts.append(desc[:280].rstrip(".") + ".")

    for fact in (evidence or {}).get("facts", [])[:3]:
        parts.append(str(fact).strip().rstrip(".") + ".")

    quotes = (evidence or {}).get("quotes") or []
    if quotes:
        parts.append(f'One commenter put it plainly: "{str(quotes[0]).strip()[:160]}".')

    # Real engagement metadata only — numbers we actually have.
    stars = str(item.get("stars") or "").strip()
    points = item.get("score") or item.get("points")
    comments = item.get("comments") or item.get("num_comments")
    if stars and stars not in {"0", ""}:
        parts.append(f"The repo is at {stars} stars and climbing.")
    elif points:
        engagement = f"{points} points"
        if comments:
            engagement += f" and {comments} comments"
        parts.append(f"The thread hit {engagement} — engineers clearly have opinions on this one.")

    parts.append("Source is linked below — read it before you form a take.")
    return " ".join(parts)


def _rule_based_clips(item: Dict[str, Any], num_clips: int = 3,
                      evidence: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fallback clip generator when LLM is unavailable.

    Strategy:
        1. Extract the best available text from the item (production_assets
           scripts, description, title).
        2. Split into segments by topic / paragraph boundaries.
        3. Rank segments by keyword density and pick the top N.
        4. Generate hooks from each segment's first sentence.
    """
    item_id = item.get("id", "unknown")
    title = (item.get("title") or item.get("working_title") or "Content").strip()

    # Gather all available text
    text_parts: list[str] = []

    # Production assets (scripts, LinkedIn post, blog outline, etc.)
    assets = item.get("production_assets")
    if isinstance(assets, str):
        try:
            assets = json.loads(assets)
        except (json.JSONDecodeError, TypeError):
            assets = {}
    if isinstance(assets, dict):
        for key in ("shorts_script", "podcast_script", "linkedin_post", "blog_outline", "demo_guide"):
            val = assets.get(key)
            if isinstance(val, str) and val.strip():
                text_parts.append(val.strip())

    # Creator pack fields
    pack = item.get("creator_pack") or item.get("enrichment") or {}
    if isinstance(pack, str):
        try:
            pack = json.loads(pack)
        except (json.JSONDecodeError, TypeError):
            pack = {}
    if isinstance(pack, dict):
        for key in ("short_script", "insight", "hook", "demo_segment", "closing_takeaway"):
            val = pack.get(key)
            if isinstance(val, str) and val.strip():
                text_parts.append(val.strip())

    # Description / abstract
    desc = item.get("description") or item.get("abstract") or ""
    if isinstance(desc, str) and desc.strip():
        text_parts.append(desc.strip())

    full_text = "\n\n".join(text_parts) if text_parts else title

    # Split and rank
    segments = _split_into_segments(full_text)
    if not segments:
        # Ultra-fallback: one clip from the title itself
        hook = f"Here's something about {title} you need to know."
        return [{
            "parent_item_id": item_id,
            "title": f"Quick take: {title}"[:80],
            "start_time": "00:00",
            "end_time": "00:45",
            "hook_text": hook,
            "script_text": _build_full_script_text(f"Quick take: {title}", hook, item, 1, evidence=evidence),
            "virality_score": score_clip_virality(hook, title),
            "status": "draft",
        }]

    # Filter to segments that fit the 30–60 second spoken window
    viable = [s for s in segments if 15.0 <= s["duration_sec"] <= 90.0]
    if len(viable) < num_clips:
        viable = segments  # relax filter

    # Sort by keyword density (descending)
    viable.sort(key=lambda s: _keyword_density(s["text"]), reverse=True)

    clips: list[dict[str, Any]] = []
    cumulative_sec = 0.0
    for seg in viable[:num_clips]:
        start_min, start_sec_part = divmod(int(cumulative_sec), 60)
        end_total = cumulative_sec + min(seg["duration_sec"], 60.0)
        end_min, end_sec_part = divmod(int(end_total), 60)

        hook = seg["first_sentence"][:140]
        clip_title = f"{title} — Part {seg['index'] + 1}"[:80]

        clips.append({
            "parent_item_id": item_id,
            "title": clip_title,
            "start_time": f"{start_min:02d}:{start_sec_part:02d}",
            "end_time": f"{end_min:02d}:{end_sec_part:02d}",
            "hook_text": hook,
            "script_text": _build_full_script_text(clip_title, hook, item, seg["index"] + 1, evidence=evidence),
            "virality_score": score_clip_virality(hook, clip_title),
            "status": "draft",
        })
        cumulative_sec = end_total + 2.0  # 2 s gap between clips

    return clips


# ---------------------------------------------------------------------------
# LLM prompt construction
# ---------------------------------------------------------------------------

def _build_clip_system_prompt(profile: Dict[str, Any]) -> str:
    """System prompt that steers the LLM towards Shorts-optimised clips."""
    banned = ", ".join(profile.get("banned_phrases", [])) or "(none)"
    tone = profile.get("tone", "")
    audience = profile.get("audience", "")
    preferred = ", ".join(profile.get("preferred_words", [])) or "(none)"
    angles = "; ".join(profile.get("signature_angles", [])) or "(none)"

    return (
        f"You are a viral Shorts editor for {profile.get('channel_name', 'a creator channel')}.\n"
        f"Audience: {audience}\n"
        f"Tone: {tone}\n"
        f"Preferred vocabulary: {preferred}\n"
        f"Signature angles: {angles}\n"
        f"Banned phrases (never use): {banned}\n\n"
        "Your job: given a saved content item (title, description, scripts, etc.), "
        "extract the N best vertical-video clip ideas.\n\n"
        "Each clip MUST:\n"
        "- Have a strong hook in the first 3 seconds that stops the scroll.\n"
        "- Be a self-contained story — it must make sense without the original context.\n"
        "- Target 30–60 seconds of spoken content (ideal for YouTube Shorts, TikTok, Reels).\n"
        "- Include a pattern interrupt or unexpected insight somewhere in the middle.\n"
        "- End on a micro-CTA or open loop that drives comments/shares.\n\n"
        "GROUNDING RULES (non-negotiable):\n"
        "- Every factual claim, number, and quote in hook_text and script_text must come "
        "from the ITEM or EVIDENCE blocks in the user message. Nothing else.\n"
        "- Never invent benchmarks, statistics, or test results. Never claim 'we ran', "
        "'we tested', 'we benchmarked', or 'we verified' anything — no tests were run.\n"
        "- Any example content in this prompt or the creator profile is a STYLE reference "
        "only; never reuse its facts, numbers, or product names.\n"
        "- If the source material is thin, write a shorter honest script instead of padding "
        "it with invented specifics.\n\n"
        "For each clip return:\n"
        "- title: a compelling, concise clip title (≤ 60 chars)\n"
        "- start_time: approximate start in MM:SS format\n"
        "- end_time: approximate end in MM:SS format\n"
        "- hook_text: the exact spoken opening line (≤ 140 chars, must hook in < 3 seconds)\n"
        "- script_text: the FULL spoken narration (60-140 words), starting with hook_text, "
        "grounded entirely in the provided material\n"
        "- virality_score: your honest estimate 0–100 of how likely this clip goes viral\n\n"
        "Return ONLY a JSON object: {\"clips\": [<clip>, ...]}. "
        "No markdown, no code fences, no commentary."
    )


def _build_clip_user_prompt(item: Dict[str, Any], num_clips: int,
                            evidence: Optional[Dict[str, Any]] = None) -> str:
    """User prompt with the item's content for the LLM to mine."""
    title = (item.get("title") or item.get("working_title") or "").strip()
    url = (item.get("url") or "").strip()
    desc = (item.get("description") or item.get("abstract") or "").strip()

    # Gather script / asset text
    content_parts: list[str] = []

    assets = item.get("production_assets")
    if isinstance(assets, str):
        try:
            assets = json.loads(assets)
        except (json.JSONDecodeError, TypeError):
            assets = {}
    if isinstance(assets, dict):
        for key in ("shorts_script", "podcast_script", "linkedin_post", "blog_outline", "demo_guide"):
            val = assets.get(key)
            if isinstance(val, str) and val.strip():
                content_parts.append(f"[{key}]\n{val.strip()[:1500]}")

    pack = item.get("creator_pack") or item.get("enrichment") or {}
    if isinstance(pack, str):
        try:
            pack = json.loads(pack)
        except (json.JSONDecodeError, TypeError):
            pack = {}
    if isinstance(pack, dict):
        for key in ("short_script", "insight", "hook", "demo_segment", "three_key_points"):
            val = pack.get(key)
            if isinstance(val, str) and val.strip():
                content_parts.append(f"[{key}]\n{val.strip()[:800]}")
            elif isinstance(val, list):
                content_parts.append(f"[{key}]\n" + "\n".join(str(v) for v in val))

    content_block = "\n\n".join(content_parts) if content_parts else desc[:2000]

    evidence_block = ""
    if evidence and (evidence.get("facts") or evidence.get("quotes") or evidence.get("excerpt")):
        lines = []
        for fact in evidence.get("facts", [])[:8]:
            lines.append(f"- {fact}")
        for quote in evidence.get("quotes", [])[:4]:
            lines.append(f'- Quote: "{quote}"')
        excerpt = (evidence.get("excerpt") or "").strip()
        if excerpt:
            lines.append(f"Source excerpt:\n{excerpt[:1800]}")
        evidence_block = (
            f"\n\nEVIDENCE (fetched from {evidence.get('url', url)} — "
            "the ONLY permitted source of facts, numbers, and quotes):\n" + "\n".join(lines)
        )

    return (
        f"ITEM TITLE: {title}\n"
        f"URL: {url}\n"
        f"DESCRIPTION: {desc[:600]}\n\n"
        f"CONTENT / SCRIPTS:\n{content_block}"
        f"{evidence_block}\n\n"
        f"Generate exactly {num_clips} clip ideas as JSON now."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_clips(item: Dict[str, Any], num_clips: int = 3,
                   evidence: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Generate AI-powered clip suggestions for a saved item.

    Uses the configured LLM provider via ``llm_summary.query_llm`` to
    analyse the item's content and produce ``num_clips`` clip dicts,
    each matching the repurposed_clips schema.

    Falls back to rule-based extraction if the LLM is unavailable or
    returns unparseable output.

    Args:
        item: A saved-item dict (must have at least ``id`` and ``title``).
        num_clips: Number of clip suggestions to generate (default 3).

    Returns:
        A list of clip dicts, each containing:
            parent_item_id, title, start_time, end_time,
            hook_text, virality_score, status.
    """
    item_id = item.get("id", "unknown")
    profile = load_creator_profile(CREATOR_PROFILE_PATH)

    # --- Try LLM path ---
    system = _build_clip_system_prompt(profile)
    user = _build_clip_user_prompt(item, num_clips, evidence=evidence)

    raw = query_llm(user, system)
    if raw:
        obj = _extract_json_object(raw)
        if obj and isinstance(obj.get("clips"), list):
            clips: list[dict[str, Any]] = []
            for raw_clip in obj["clips"][:num_clips]:
                hook = str(raw_clip.get("hook_text") or raw_clip.get("hook") or "")[:140]
                clip_title = str(raw_clip.get("title") or "")[:80]

                heuristic_score = score_clip_virality(hook, clip_title)

                # Use LLM's virality_score if plausible, otherwise compute ours.
                # Default must be None, not 0: float(0) passes the range check,
                # so a *missing* field would score 0 and drag the blend down to
                # 0.3x the heuristic — penalising clips the LLM simply didn't
                # self-rate.
                try:
                    raw_score = raw_clip.get("virality_score")
                    if raw_score is None:
                        raise ValueError
                    llm_score = float(raw_score)
                    if not (0 <= llm_score <= 100):
                        raise ValueError
                except (TypeError, ValueError):
                    llm_score = heuristic_score

                # Blend: 70 % LLM + 30 % heuristic for robustness
                blended = round(0.7 * llm_score + 0.3 * heuristic_score, 1)

                clips.append({
                    "parent_item_id": item_id,
                    "title": clip_title or f"Clip from {item.get('title', 'content')}"[:80],
                    "start_time": str(raw_clip.get("start_time", "00:00")),
                    "end_time": str(raw_clip.get("end_time", "00:45")),
                    "hook_text": hook,
                    "script_text": str(raw_clip.get("script_text") or _build_full_script_text(clip_title, hook, item, len(clips)+1, evidence=evidence)),
                    "virality_score": blended,
                    "status": "draft",
                })
            if clips:
                return clips

    # --- Fallback: rule-based extraction ---
    print("[clip_generator] LLM unavailable or returned bad output — using rule-based fallback")
    return _rule_based_clips(item, num_clips, evidence=evidence)


# ---------------------------------------------------------------------------
# CLI quick-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_item: Dict[str, Any] = {
        "id": 999,
        "title": "Llamafile 0.9 ships single-binary distribution for tiny LLMs",
        "description": (
            "Mozilla's Llamafile project releases a single binary that bundles "
            "model weights + runtime, runnable on CPU-only hardware including "
            "Raspberry Pi."
        ),
        "production_assets": {
            "shorts_script": (
                "Llamafile 0.9 just dropped and it actually runs on my Pi 4. "
                "One binary. No CUDA. I clocked six tokens a second on a 3B model "
                "and the setup took four minutes. The catch is memory pressure "
                "climbs over 3.7 gigs once context fills. Worth testing tonight."
            ),
        },
    }

    print("=== Generating clips ===")
    results = generate_clips(sample_item, num_clips=3)
    for i, clip in enumerate(results, 1):
        print(f"\n--- Clip {i} ---")
        for k, v in clip.items():
            print(f"  {k}: {v}")

    print("\n=== Virality score test ===")
    test_hooks = [
        ("One file. No GPU. Real tokens on a Pi 4.", "Single-binary LLM on a Pi 4"),
        ("Why is nobody talking about this?", "The hidden feature in Llamafile"),
        ("Step 1 of the tutorial", "How to install Llamafile"),
    ]
    for hook, title in test_hooks:
        score = score_clip_virality(hook, title)
        print(f"  {score:5.1f}  |  hook={hook!r}")
