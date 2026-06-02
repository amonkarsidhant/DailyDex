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
IS_VERCEL = os.environ.get("VERCEL") == "1"
GEMINI_BIN = os.environ.get("GEMINI_BIN", "gemini")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")
GEMINI_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "600"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")

# Claude Code CLI — uses the existing OAuth session, no API key needed.
_CLAUDE_CODE_BIN = os.environ.get(
    "CLAUDE_CODE_BIN",
    os.environ.get("CLAUDE_CODE_EXECPATH", "claude"),
)
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "120"))

# NVIDIA NIM — OpenAI-compatible endpoint (build.nvidia.com).
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "minimaxai/minimax-m2.7")

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

def get_llm_setting(key: str, default: str = "") -> str:
    env_val = os.environ.get(key)
    if env_val:
        return env_val
    try:
        import settings_manager
        return settings_manager.get(key.lower())
    except Exception:
        return default


def _gemini_args(prompt: str) -> List[str]:
    gemini_bin = get_llm_setting("GEMINI_PATH", "gemini")
    gemini_model = get_llm_setting("LLM_MODEL", "")
    args = [gemini_bin]
    if gemini_model:
        args += ["--model", gemini_model]
    # Headless Automation Mode: Use --prompt and --output-format json.
    # --approval-mode yolo allows the agent to use its research tools (search, etc.) autonomously.
    args += [
        "--prompt", prompt,
        "--output-format", "json",
        "--approval-mode", "yolo",
        "--accept-raw-output-risk"
    ]
    return args


def query_gemini_cli(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Run the Gemini CLI in headless mode and return the model's text response.
    """
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    gemini_timeout = int(get_llm_setting("GEMINI_TIMEOUT", "600"))
    gemini_bin = get_llm_setting("GEMINI_PATH", "gemini")
    try:
        # Pass DEVNULL to stdin to ensure non-interactive behavior
        result = subprocess.run(
            _gemini_args(full_prompt),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=gemini_timeout,
        )
    except FileNotFoundError:
        print(f"Gemini CLI not found at {gemini_bin}. Set GEMINI_BIN or install `gemini`.")
        return None
    except subprocess.TimeoutExpired:
        print(f"Gemini CLI timed out after {gemini_timeout}s")
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
    url = get_llm_setting("OLLAMA_URL", "http://localhost:11434")
    if not url.endswith("/api/generate"):
        url = f"{url.rstrip('/')}/api/generate"
    model = get_llm_setting("OLLAMA_MODEL", "phi3:mini")
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"max_tokens": 1200, "temperature": 0.3},
        }
        if system_prompt:
            payload["system"] = system_prompt
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            return (response.json().get("response") or "").strip()
    except Exception as exc:
        print(f"Ollama error: {exc}")
    return None


def query_claude_code_cli(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Call Claude via the claude CLI using the existing OAuth session."""
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    claude_bin = get_llm_setting("CLAUDE_PATH", "claude")
    claude_model = get_llm_setting("LLM_MODEL", "claude-sonnet-4-6")
    claude_timeout = int(get_llm_setting("CLAUDE_TIMEOUT", "120"))
    args = [
        claude_bin,
        "-p", full_prompt,
        "--model", claude_model,
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=claude_timeout,
        )
    except FileNotFoundError:
        print(f"Claude CLI not found at {claude_bin}. Set CLAUDE_CODE_BIN.")
        return None
    except subprocess.TimeoutExpired:
        print(f"Claude CLI timed out after {claude_timeout}s")
        return None
    except Exception as exc:
        print(f"Claude CLI error: {exc}")
        return None

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:400]
        print(f"Claude CLI exit {result.returncode}: {stderr}")
        return None

    return (result.stdout or "").strip() or None


def query_opencode_cli(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    """Call opencode CLI in headless mode and return response."""
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    bin_path = get_llm_setting("OPENCODE_PATH", "opencode")
    model = get_llm_setting("LLM_MODEL", "opencode/deepseek-v4-flash-free")
    try:
        profile_path = os.path.join(BASE_DIR, "config", "creator_profile.json")
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                prof_data = json.load(f)
                cop_cfg = prof_data.get("copilot") or {}
                if cop_cfg.get("provider") == "opencode":
                    model = cop_cfg.get("model") or model
    except Exception:
        pass
    
    args = [bin_path, "run", "-m", model, full_prompt]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=120,
        )
    except FileNotFoundError:
        print(f"opencode CLI not found at {bin_path}. Install it or set it up.")
        return None
    except subprocess.TimeoutExpired:
        print("opencode CLI timed out.")
        return None
    except Exception as exc:
        print(f"opencode CLI error: {exc}")
        return None

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()[:400]
        print(f"opencode CLI exit {result.returncode}: {stderr}")
        return None

    stdout = (result.stdout or "").strip()
    import re as _re
    stdout = _re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", stdout)
    stdout = _re.sub(r"<think>.*?</think>", "", stdout, flags=_re.S)
    if "</think>" in stdout:
        stdout = stdout.split("</think>")[-1]
    return stdout.strip() or None


def query_kilocode_cli(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    bin_path = get_llm_setting("KILOCODE_PATH", "kilo")
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    model = get_llm_setting("LLM_MODEL", "")
    args = [bin_path, full_prompt]
    if model:
        args += ["--model", model]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=120,
        )
        if result.returncode == 0:
            return (result.stdout or "").strip() or None
    except Exception as e:
        print(f"Kilocode CLI error: {e}")
    return None


def query_agy_cli(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    bin_path = get_llm_setting("AGY_PATH", "agy")
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    args = [bin_path, "-p", full_prompt, "--dangerously-skip-permissions"]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=180,
        )
        if result.returncode == 0:
            return (result.stdout or "").strip() or None
    except Exception as e:
        print(f"Antigravity CLI error: {e}")
    return None


def query_nvidia(prompt: str, system_prompt: Optional[str] = None,
                 model: Optional[str] = None, max_tokens: int = 1024,
                 api_key: Optional[str] = None) -> Optional[str]:
    """Call an NVIDIA NIM OpenAI-compatible chat endpoint."""
    if requests is None:
        return None
    key = api_key or get_llm_setting("LLM_API_KEY", "") or os.environ.get("NVIDIA_API_KEY", "")
    if not key:
        print("NVIDIA NIM: no API key set")
        return None
    url = get_llm_setting("LLM_BASE_URL", "") or "https://integrate.api.nvidia.com/v1"
    resolved_model = model or get_llm_setting("LLM_MODEL", "minimaxai/minimax-m2.7")
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": resolved_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.4,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"NVIDIA NIM error {resp.status_code}: {resp.text[:200]}")
            return None
        choices = resp.json().get("choices") or []
        if choices:
            msg = choices[0].get("message", {}) or {}
            text = (msg.get("content") or "").strip()
            # Some NIM reasoning models (step, minimax) place the answer in
            # reasoning_content and leave content empty when token budget is tight.
            if not text:
                text = (msg.get("reasoning_content") or "").strip()
            return _strip_think(text) or None
    except Exception as exc:
        print(f"NVIDIA NIM error: {exc}")
    return None


def query_openai(prompt: str, system_prompt: Optional[str] = None,
                 model: Optional[str] = None, max_tokens: int = 4096) -> Optional[str]:
    """Call an OpenAI or custom OpenAI-compatible API endpoint."""
    if requests is None:
        return None
    key = get_llm_setting("LLM_API_KEY", "")
    url = get_llm_setting("LLM_BASE_URL", "") or "https://api.openai.com/v1"
    resolved_model = model or get_llm_setting("LLM_MODEL", "gpt-4o-mini")
    if not key and "openai.com" in url:
        print("OpenAI API: no API key set")
        return None
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"} if key else {"Content-Type": "application/json"},
            json={
                "model": resolved_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.4,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"OpenAI compatible API error {resp.status_code}: {resp.text[:200]}")
            return None
        choices = resp.json().get("choices") or []
        if choices:
            msg = choices[0].get("message", {}) or {}
            return (msg.get("content") or "").strip() or None
    except Exception as exc:
        print(f"OpenAI compatible API error: {exc}")
    return None


def query_anthropic(prompt: str, system_prompt: Optional[str] = None,
                    model: Optional[str] = None, timeout: int = 60) -> Optional[str]:
    key = get_llm_setting("LLM_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("Anthropic API: no API key set")
        return None
    resolved_model = model or get_llm_setting("LLM_MODEL", "claude-3-5-sonnet-latest")
    try:
        payload: dict = {
            "model": resolved_model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            blocks = result.get("content", [])
            return "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip() or None
    except Exception as e:
        print(f"Anthropic API error: {e}")
        return None


def _strip_think(text: str) -> str:
    """Remove <think>...</think> reasoning blocks; if only an unclosed think
    block exists, keep what's after the last tag."""
    if not text:
        return text
    import re as _re
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.S).strip()
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    if text.startswith("<think>"):
        text = text[len("<think>"):].strip()
    return text

_last_used_provider_label: Optional[str] = None


def query_llm(prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
    global _last_used_provider_label
    
    provider = get_llm_setting("LLM_PROVIDER", "gemini")
    deployment_mode = get_llm_setting("DEPLOYMENT_MODE", "cli")

    if IS_VERCEL or deployment_mode == "api":
        if provider not in ("nvidia", "openai", "anthropic", "ollama"):
            provider = "nvidia" if (get_llm_setting("LLM_API_KEY") or get_llm_setting("NVIDIA_API_KEY")) else "anthropic"

    strategies = {
        "nvidia": (query_nvidia, "LLM_MODEL", "minimaxai/minimax-m2.7"),
        "openai": (query_openai, "LLM_MODEL", "gpt-4o-mini"),
        "anthropic": (query_anthropic, "LLM_MODEL", "claude-3-5-sonnet-latest"),
        "ollama": (query_ollama, "OLLAMA_MODEL", "phi3:mini"),
        "claude": (query_claude_code_cli, "LLM_MODEL", "claude-sonnet-4-6"),
        "opencode": (query_opencode_cli, "LLM_MODEL", "deepseek-v4-flash-free"),
        "kilocode": (query_kilocode_cli, "LLM_MODEL", "default"),
        "agy": (query_agy_cli, "LLM_MODEL", "default"),
        "gemini": (query_gemini_cli, "LLM_MODEL", "default"),
    }
    
    handler_info = strategies.get(provider, strategies["gemini"])
    func, model_key, default_model = handler_info
    
    try:
        model = get_llm_setting(model_key, default_model)
        if func in (query_nvidia, query_openai, query_anthropic):
            res = func(prompt, system_prompt, model=model)
        else:
            res = func(prompt, system_prompt)
            
        if res and res.strip():
            _last_used_provider_label = f"{provider}:{model}"
            return res
    except Exception as e:
        print(f"Provider {provider} failed: {e}")

    # Fallback to dynamic CLI registry discovery
    try:
        import cli_registry as _cr
        probe_res = _cr.generate(prompt, system_prompt, timeout=60)
        if probe_res.get("text"):
            _last_used_provider_label = f"{probe_res.get('provider', 'unknown')}:{probe_res.get('model', '')}"
            return probe_res["text"]
    except Exception:
        pass
        
    return None


def llm_provider_label() -> str:
    if _last_used_provider_label:
        return _last_used_provider_label
    provider = get_llm_setting("LLM_PROVIDER", "gemini")
    model = get_llm_setting("LLM_MODEL", "")
    if provider == "ollama":
        return f"ollama:{get_llm_setting('OLLAMA_MODEL', 'phi3:mini')}"
    if provider == "claude":
        return f"claude:{model or 'claude-sonnet-4-6'}"
    if provider == "opencode":
        return f"opencode:{model or 'deepseek-v4-flash-free'}"
    if provider == "nvidia":
        return f"nvidia:{model or 'minimaxai/minimax-m2.7'}"
    if provider == "openai":
        return f"openai:{model or 'gpt-4o-mini'}"
    if provider == "anthropic":
        return f"anthropic:{model or 'claude-3-5-sonnet-latest'}"
    return f"{provider}:{model or 'default'}"


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


def _examples_block(profile: Dict[str, Any], limit: int = 2) -> str:
    """Render a few-shot block of validated past packs.

    The examples teach voice + structure better than any amount of rule
    enumeration. Keep `limit` small so we do not blow the prompt budget.
    """
    examples = profile.get("examples") or []
    if not examples:
        return ""
    blocks = ["Past creator packs that hit the bar — use this voice, density, and structure (do not copy text verbatim):"]
    for example in examples[:limit]:
        title = example.get("input_title") or "(untitled item)"
        desc = example.get("input_description") or ""
        pack = example.get("pack") or {}
        blocks.append("---")
        blocks.append(f"INPUT TITLE: {title}")
        if desc:
            blocks.append(f"INPUT DESCRIPTION: {desc}")
        blocks.append("OUTPUT PACK:")
        try:
            blocks.append(json.dumps(pack, ensure_ascii=False))
        except Exception:
            continue
    blocks.append("---")
    return "\n".join(blocks)


def build_creator_system_prompt(profile: Dict[str, Any]) -> str:
    rules = profile.get("format_rules", {})
    banned = ", ".join(profile.get("banned_phrases", [])) or "(none)"
    preferred = ", ".join(profile.get("preferred_words", [])) or "(none)"
    angles = "; ".join(profile.get("signature_angles", [])) or "(none)"
    examples = _examples_block(profile)
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
        + (f"\n\n{examples}" if examples else "")
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
    """Remove banned phrases. Also catches hyphenated / inflected variants.

    We escape the phrase, then loosen any internal space/hyphen so
    "game changer" also matches "game-changer". A trailing optional
    ``(?:s|ed|ing)`` catches the most common inflections without dragging in a
    real stemmer.
    """
    if not isinstance(text, str):
        return ""
    cleaned = text
    for phrase in banned:
        if not phrase:
            continue
        # Tokenize on whitespace/hyphen, escape each token, rejoin with
        # ``[\s\-]+`` so "game changer" also matches "game-changer". Trailing
        # ``\w*`` sweeps up inflections (-ed, -er, -ing, -s).
        tokens = [t for t in re.split(r"[\s\-]+", phrase.strip()) if t]
        if not tokens:
            continue

        def _token_pattern(token: str) -> str:
            escaped = re.escape(token)
            # English drops trailing ``e`` before consonant suffixes
            # ("supercharge" -> "supercharging"). Make the final ``e`` optional
            # so the suffix-absorbing ``\w*`` still catches inflected forms.
            if token.lower().endswith("e") and len(token) > 2:
                escaped = escaped[:-1] + "e?"
            return escaped

        pattern = r"\b" + r"[\s\-]+".join(_token_pattern(tok) for tok in tokens) + r"\w*"
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    # Collapse double whitespace and leftover punctuation islands.
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -,;:")
    return cleaned


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
