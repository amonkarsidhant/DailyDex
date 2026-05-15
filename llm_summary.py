#!/usr/bin/env python3
"""LLM-powered summary and creator enrichment.

Default provider: Gemini CLI (works on Raspberry Pi 4 without local model weights).
Fallback: Ollama HTTP (if user opts in via LLM_PROVIDER=ollama).

This module produces a single full creator pack per item in one LLM call.
See `CREATOR_PACK_SCHEMA_VERSION` and `validate_creator_pack` below.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None


PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")
GEMINI_BIN = os.environ.get("GEMINI_BIN", "gemini")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")
GEMINI_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "120"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREATOR_PROFILE_PATH = os.environ.get(
    "CREATOR_PROFILE_PATH",
    os.path.join(BASE_DIR, "config", "creator_profile.json"),
)

CREATOR_PACK_SCHEMA_VERSION = 1

# Required keys in the creator pack returned by the LLM
CREATOR_PACK_REQUIRED_KEYS = [
    "hook",
    "intro_context",
    "three_key_points",
    "three_beat_structure",
    "demo_segment",
    "caveats",
    "closing_takeaway",
    "call_to_action",
    "short_script",
    "visual_idea",
    "cta",
    "suggested_titles",
    "thumbnail_text",
    "broll_list",
    "on_screen_cues",
    "insight",
    "hooks",
    "tags",
]

SUGGESTED_TITLE_KEYS = ["curiosity", "practical", "contrarian", "tutorial"]


# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------

def _gemini_args(prompt: str) -> List[str]:
    args = [GEMINI_BIN]
    if GEMINI_MODEL:
        args += ["--model", GEMINI_MODEL]
    args += ["--prompt", prompt, "--output-format", "json"]
    return args


def query_gemini_cli(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Run the Gemini CLI and return the model's text response.

    The CLI wraps the response in a JSON envelope when called with
    `--output-format json`. We extract the inner text so callers can parse the
    model's payload directly.
    """
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    try:
        result = subprocess.run(
            _gemini_args(full_prompt),
            capture_output=True,
            text=True,
            timeout=GEMINI_TIMEOUT,
        )
    except FileNotFoundError:
        print("Gemini CLI not found. Set GEMINI_BIN or install `gemini`.")
        return None
    except subprocess.TimeoutExpired:
        print(f"Gemini CLI timed out after {GEMINI_TIMEOUT}s")
        return None
    except Exception as exc:  # pragma: no cover
        print(f"Gemini CLI error: {exc}")
        return None

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:400]
        print(f"Gemini CLI exit {result.returncode}: {stderr}")
        return None

    stdout = (result.stdout or "").strip()
    if not stdout:
        return None
    # The CLI sometimes returns the raw model output, sometimes a JSON envelope.
    try:
        envelope = json.loads(stdout)
        if isinstance(envelope, dict):
            for key in ("response", "text", "output", "content"):
                value = envelope.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    except json.JSONDecodeError:
        pass
    return stdout


def query_ollama(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    if requests is None:
        return None
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"max_tokens": 1200, "temperature": 0.3},
        }
        if system_prompt:
            payload["system"] = system_prompt
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        if response.status_code == 200:
            return (response.json().get("response") or "").strip()
    except Exception as exc:
        print(f"Ollama error: {exc}")
    return None


def query_llm(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    if PROVIDER == "ollama":
        return query_ollama(prompt, system_prompt)
    return query_gemini_cli(prompt, system_prompt)


def llm_provider_label() -> str:
    if PROVIDER == "ollama":
        return f"ollama:{OLLAMA_MODEL}"
    return f"gemini:{GEMINI_MODEL or 'default'}"


# ---------------------------------------------------------------------------
# Creator profile loading
# ---------------------------------------------------------------------------

_DEFAULT_PROFILE: Dict[str, Any] = {
    "channel_name": "DailyDex Creator",
    "niche": "Practical AI for indie builders.",
    "audience": "Engineers shipping real demos on commodity hardware.",
    "tone": "Skeptical, hands-on, no hype.",
    "perspective": "First-person builder voice.",
    "banned_phrases": ["game changer", "revolutionary"],
    "preferred_words": ["ship", "test", "demo"],
    "format_rules": {
        "title_min_chars": 38,
        "title_max_chars": 62,
        "hook_max_chars": 140,
        "thumbnail_max_words": 4,
        "short_script_max_seconds": 45,
        "short_script_min_seconds": 25,
    },
    "signature_angles": [],
}


def load_creator_profile(path: str = CREATOR_PROFILE_PATH) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return {**_DEFAULT_PROFILE, **data}
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"Creator profile load error: {exc}")
    return dict(_DEFAULT_PROFILE)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _evidence_block(item: Dict[str, Any]) -> str:
    evidence = item.get("source_evidence") or []
    if not evidence:
        return "(none)"
    lines = []
    for row in evidence[:4]:
        label = row.get("source_label") or row.get("source_type") or "Source"
        title = row.get("title") or ""
        url = row.get("url") or ""
        lines.append(f"- [{label}] {title} ({url})")
    return "\n".join(lines)


def _cluster_block(item: Dict[str, Any]) -> str:
    siblings = item.get("cluster_sibling_titles") or []
    if not siblings:
        return "(item appears in 1 source family)"
    lines = [f"- {title}" for title in siblings[:5]]
    return "Related items in the same topic cluster:\n" + "\n".join(lines)


def build_creator_system_prompt(profile: Dict[str, Any]) -> str:
    rules = profile.get("format_rules", {})
    banned = ", ".join(profile.get("banned_phrases", [])) or "(none)"
    preferred = ", ".join(profile.get("preferred_words", [])) or "(none)"
    angles = "; ".join(profile.get("signature_angles", [])) or "(none)"
    return (
        f"You are the head writer for {profile.get('channel_name', 'a creator channel')}.\n"
        f"Niche: {profile.get('niche', '')}\n"
        f"Audience: {profile.get('audience', '')}\n"
        f"Tone: {profile.get('tone', '')}\n"
        f"Perspective: {profile.get('perspective', '')}\n"
        f"Signature angles you can lean on: {angles}.\n"
        f"Banned phrases (never use): {banned}.\n"
        f"Preferred vocabulary: {preferred}.\n\n"
        "You transform a single high-signal AI item into a complete creator pack.\n"
        "The pack must be specific to the item. Reference the actual title, what it does, and what changed.\n"
        "Never invent benchmarks, dates, or capabilities. If unclear, say so in `caveats`.\n\n"
        "Format constraints:\n"
        f"- title length: {rules.get('title_min_chars', 38)}-{rules.get('title_max_chars', 62)} characters\n"
        f"- hook length: <= {rules.get('hook_max_chars', 140)} characters\n"
        f"- thumbnail_text: 3 strings, each <= {rules.get('thumbnail_max_words', 4)} words, ALL CAPS, no period\n"
        f"- short_script: {rules.get('short_script_min_seconds', 25)}-{rules.get('short_script_max_seconds', 45)} second read, written as plain spoken sentences\n"
        "- three_beat_structure: exactly 3 short beats labelled (hook | payoff | cta)\n"
        "- three_key_points: 3 concrete bullets, not generic\n"
        "- broll_list: 3 concrete visual ideas tied to the item (UI, terminal, diagram, etc.)\n"
        "- on_screen_cues: 3 short on-screen text strings\n\n"
        "Return ONLY a single valid JSON object with these exact keys:\n"
        "hook, intro_context, three_key_points (array of 3 strings), three_beat_structure (array of 3 strings), "
        "demo_segment, caveats, closing_takeaway, call_to_action, short_script, visual_idea, cta, "
        "suggested_titles (object with keys: curiosity, practical, contrarian, tutorial), "
        "thumbnail_text (array of 3 strings), broll_list (array of 3 strings), on_screen_cues (array of 3 strings), "
        "insight, hooks (array of 3 strings), tags (array of 3 strings).\n"
        "Output JSON only. No markdown, no commentary, no code fences."
    )


def build_creator_user_prompt(item: Dict[str, Any]) -> str:
    title = (item.get("title") or "").strip()
    desc = (item.get("description") or item.get("abstract") or "").strip()
    source = (item.get("source") or "").strip()
    source_type = (item.get("source_type") or "").strip()
    url = (item.get("url") or "").strip()
    topic = (item.get("creator_topic") or "").strip()
    cats = item.get("categories") or []
    cats_str = ", ".join(map(str, cats[:6])) if cats else "(none)"
    return (
        f"ITEM TITLE: {title}\n"
        f"SOURCE: {source} ({source_type})\n"
        f"URL: {url}\n"
        f"TOPIC HINT: {topic or '(auto)'}\n"
        f"CATEGORIES: {cats_str}\n"
        f"DESCRIPTION: {desc[:1200]}\n\n"
        f"SOURCE EVIDENCE:\n{_evidence_block(item)}\n\n"
        f"CLUSTER CONTEXT:\n{_cluster_block(item)}\n\n"
        "Produce the creator pack JSON now."
    )


# ---------------------------------------------------------------------------
# JSON extraction + validation
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    # Strip fenced code blocks if present.
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        # Remove a leading language hint like "json\n"
        cleaned = re.sub(r"^[a-zA-Z]*\n", "", cleaned, count=1).strip()
    match = _JSON_BLOCK_RE.search(cleaned)
    if not match:
        return None
    candidate = match.group(0)
    try:
        loaded = json.loads(candidate)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        # Try to repair trailing commas — common Gemini quirk
        repaired = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            loaded = json.loads(repaired)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            return None
    return None


def _coerce_string_list(value: Any, length: int) -> List[str]:
    if isinstance(value, list):
        out = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, str):
        out = [value.strip()] if value.strip() else []
    else:
        out = []
    while len(out) < length:
        out.append("")
    return out[:length]


def _coerce_titles(value: Any) -> Dict[str, str]:
    out = {key: "" for key in SUGGESTED_TITLE_KEYS}
    if isinstance(value, dict):
        for key in SUGGESTED_TITLE_KEYS:
            v = value.get(key)
            if isinstance(v, str):
                out[key] = v.strip()
    return out


def _strip_banned(text: str, banned: List[str]) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text
    for phrase in banned:
        if not phrase:
            continue
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_creator_pack(raw: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Coerce LLM output into the canonical schema. Missing keys become empty."""
    profile = profile or load_creator_profile()
    banned = profile.get("banned_phrases", [])

    def _s(value: Any) -> str:
        return _strip_banned(str(value or "").strip(), banned)

    pack = {
        "hook": _s(raw.get("hook")),
        "intro_context": _s(raw.get("intro_context")),
        "three_key_points": [_s(v) for v in _coerce_string_list(raw.get("three_key_points"), 3)],
        "three_beat_structure": [_s(v) for v in _coerce_string_list(raw.get("three_beat_structure"), 3)],
        "demo_segment": _s(raw.get("demo_segment")),
        "caveats": _s(raw.get("caveats")),
        "closing_takeaway": _s(raw.get("closing_takeaway")),
        "call_to_action": _s(raw.get("call_to_action")),
        "short_script": _s(raw.get("short_script")),
        "visual_idea": _s(raw.get("visual_idea")),
        "cta": _s(raw.get("cta") or raw.get("call_to_action")),
        "suggested_titles": _coerce_titles(raw.get("suggested_titles")),
        "thumbnail_text": [_s(v).upper() for v in _coerce_string_list(raw.get("thumbnail_text"), 3)],
        "broll_list": [_s(v) for v in _coerce_string_list(raw.get("broll_list"), 3)],
        "on_screen_cues": [_s(v) for v in _coerce_string_list(raw.get("on_screen_cues"), 3)],
        "insight": _s(raw.get("insight")),
        "hooks": [_s(v) for v in _coerce_string_list(raw.get("hooks"), 3)],
        "tags": [_s(v) for v in _coerce_string_list(raw.get("tags"), 3)],
        "opening_hook": _s(raw.get("hook")),
        "hook_line": _s(raw.get("hook")),
        "schema_version": CREATOR_PACK_SCHEMA_VERSION,
    }
    return pack


def validate_creator_pack(pack: Dict[str, Any], profile: Optional[Dict[str, Any]] = None) -> List[str]:
    """Return list of validation issues. Empty list = pack is acceptable."""
    profile = profile or load_creator_profile()
    rules = profile.get("format_rules", {})
    issues: List[str] = []

    if not pack.get("hook"):
        issues.append("missing hook")
    if pack.get("hook") and len(pack["hook"]) > rules.get("hook_max_chars", 140):
        issues.append("hook too long")

    titles = pack.get("suggested_titles") or {}
    for key in SUGGESTED_TITLE_KEYS:
        value = titles.get(key, "")
        if not value:
            issues.append(f"missing title.{key}")
            continue
        if len(value) < rules.get("title_min_chars", 30) - 5:
            issues.append(f"title.{key} too short")
        if len(value) > rules.get("title_max_chars", 70) + 5:
            issues.append(f"title.{key} too long")

    thumbs = pack.get("thumbnail_text") or []
    max_words = rules.get("thumbnail_max_words", 4)
    for idx, value in enumerate(thumbs):
        if not value:
            issues.append(f"missing thumbnail_text[{idx}]")
        elif len(value.split()) > max_words:
            issues.append(f"thumbnail_text[{idx}] too long")

    for key in ("three_key_points", "three_beat_structure", "hooks", "broll_list", "on_screen_cues"):
        values = pack.get(key) or []
        if sum(1 for v in values if v) < 2:
            issues.append(f"{key} too sparse")

    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_creator_pack(item: Dict[str, Any], profile: Optional[Dict[str, Any]] = None, retries: int = 1) -> Dict[str, Any]:
    """Generate a full creator pack for one item. Returns a result dict:
        {"ok": bool, "pack": dict, "issues": list[str], "raw": str, "model": str}
    """
    profile = profile or load_creator_profile()
    system = build_creator_system_prompt(profile)
    user = build_creator_user_prompt(item)

    last_raw = ""
    last_issues: List[str] = []
    for attempt in range(retries + 1):
        prompt = user if attempt == 0 else (
            user + "\n\nIMPORTANT: Your previous reply was not valid JSON or violated the schema. "
            "Return ONLY a single JSON object with the required keys. No commentary. No code fences."
        )
        raw = query_llm(prompt, system) or ""
        last_raw = raw
        obj = _extract_json_object(raw)
        if not obj:
            last_issues = ["unparseable LLM response"]
            time.sleep(1)
            continue
        pack = normalize_creator_pack(obj, profile)
        issues = validate_creator_pack(pack, profile)
        if not issues:
            return {"ok": True, "pack": pack, "issues": [], "raw": raw, "model": llm_provider_label()}
        last_issues = issues
        time.sleep(1)

    # Best-effort fallback so caller still has something to render
    fallback = normalize_creator_pack({}, profile)
    fallback["caveats"] = "LLM enrichment failed; this pack is a placeholder."
    return {"ok": False, "pack": fallback, "issues": last_issues or ["empty response"], "raw": last_raw, "model": llm_provider_label()}


def get_item_enrichment(item: Dict[str, Any]) -> Dict[str, Any]:
    """Back-compat wrapper used by older code paths.

    Returns a small subset for callers that only need insight/hooks/outline/tags.
    """
    result = generate_creator_pack(item)
    pack = result.get("pack", {})
    return {
        "insight": pack.get("insight", ""),
        "hooks": pack.get("hooks", []),
        "outline": pack.get("three_key_points", []),
        "tags": pack.get("tags", []),
    }


def get_ollama_summary(data: Dict[str, Any]) -> str:
    """Short 2-sentence daily blurb used by digest pages."""
    github = (data.get("github") or [])[:3]
    blogs = (data.get("blogs") or [])[:3]
    repo_info = "\n".join([f"- {r.get('title', '')}" for r in github])
    news_info = "\n".join([f"- {b.get('title', '')}" for b in blogs])
    prompt = (
        "Write 2 sentences summarising today's AI signal. No hype words.\n"
        f"Trending repos:\n{repo_info}\n\nNews:\n{news_info}\n\nSummary:"
    )
    summary = query_llm(prompt) or ""
    summary = summary.replace("\n", " ").strip()
    if summary:
        if len(summary) > 200:
            summary = summary[:197].rstrip() + "..."
        return summary
    return f"{len(github)} repos | {len(blogs)} stories"


# ---------------------------------------------------------------------------
# Production Forge multi-format generator
# ---------------------------------------------------------------------------

PRODUCTION_REQUIRED_KEYS = [
    "shorts_script",
    "podcast_script",
    "linkedin_post",
    "blog_outline",
    "demo_guide",
]


def generate_production_assets(research_data: str, profile: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Forge a saved creator item into 5 platform-ready formats."""
    profile = profile or load_creator_profile()
    banned = ", ".join(profile.get("banned_phrases", [])) or "(none)"
    tone = profile.get("tone", "")
    audience = profile.get("audience", "")
    system_prompt = (
        f"You are the production team for {profile.get('channel_name', 'a creator channel')}.\n"
        f"Audience: {audience}\nTone: {tone}\nBanned phrases (never use): {banned}.\n\n"
        "Turn one research pack into 5 platform-ready assets. Be technical and concrete.\n"
        "1. shorts_script (60s): Plain spoken sentences with [Visual] and [Audio] cues every few lines.\n"
        "2. podcast_script (~5 min): Host A / Host B technical dialogue, natural chemistry, no filler.\n"
        "3. linkedin_post: <= 1300 chars, hook in first 2 lines before the 'see more' fold, ends with a question.\n"
        "4. blog_outline: H2/H3 structure, bullet points, includes a 'What it actually does' section.\n"
        "5. demo_guide: Numbered steps a viewer can copy-paste, ending in a clear 'success criterion'.\n\n"
        "Return ONLY a JSON object with keys: shorts_script, podcast_script, linkedin_post, blog_outline, demo_guide. "
        "Each value is a string. No markdown fences. No commentary."
    )
    prompt = (
        f"RESEARCH PACK CONTEXT:\n{research_data[:6000]}\n\nForge the production assets now as JSON."
    )
    raw = query_llm(prompt, system_prompt) or ""
    obj = _extract_json_object(raw)
    if not obj:
        return None
    out = {}
    for key in PRODUCTION_REQUIRED_KEYS:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()
        else:
            out[key] = ""
    if not any(out.values()):
        return None
    return out


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.environ.get("DATA_DIR", os.path.join(base_dir, "data"))
    data_path = os.environ.get("DATA_FILE", os.path.join(data_dir, "data.json"))
    if os.path.exists(data_path):
        with open(data_path) as handle:
            data = json.load(handle)
        print("Summary:", get_ollama_summary(data))
