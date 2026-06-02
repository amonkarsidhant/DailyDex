#!/usr/bin/env python3
"""
DailyDex Settings Manager — BYOK (Bring Your Own Keys)
-------------------------------------------------------
Persists creator-supplied API keys and LLM provider config to a local
JSON file (~/.dailydex/settings.json by default).

Keys stored:
  - youtube_api_key        : YouTube Data API v3 key (Google Cloud Console)
  - fal_api_key            : fal.ai API key for Flux image generation
  - llm_provider           : "gemini" | "claude" | "ollama" | "nvidia" | "openai" | "anthropic"
  - llm_model              : provider-specific model name
  - llm_api_key            : API key (for openai / anthropic / nvidia)
  - llm_base_url           : Custom OpenAI-compatible base URL (for self-hosted)
  - ollama_url             : Ollama server URL (default: http://localhost:11434)
  - ollama_model           : Ollama model name (default: phi3:mini)

Design principles:
  - Keys live on disk, never in the DB or on any server.
  - The .env file can still override anything via env vars (env wins).
  - Sensitive values are masked in the API response.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

# ── Storage path ─────────────────────────────────────────────────────────────

_DEFAULT_SETTINGS_DIR = Path.home() / ".dailydex"
SETTINGS_DIR = Path(os.environ.get("DAILYDEX_SETTINGS_DIR", str(_DEFAULT_SETTINGS_DIR)))
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# ── Key schema ────────────────────────────────────────────────────────────────

SCHEMA: Dict[str, Dict[str, Any]] = {
    # YouTube
    "youtube_api_key": {
        "label": "YouTube Data API v3 Key",
        "group": "youtube",
        "secret": True,
        "help": "Get it from console.cloud.google.com → APIs & Services → YouTube Data API v3 → Credentials",
        "placeholder": "AIza...",
    },
    # fal.ai / Flux
    "fal_api_key": {
        "label": "fal.ai API Key (Flux Image Gen)",
        "group": "image_gen",
        "secret": True,
        "help": "Sign up at fal.ai — free $1 credit on signup. Flux Schnell costs ~$0.003/image.",
        "placeholder": "fal-...",
    },
    # LLM
    "deployment_mode": {
        "label": "Deployment Mode",
        "group": "llm",
        "secret": False,
        "help": "Choose between Self-hosted (Local CLI) and Cloud VM (Remote API) environments.",
        "placeholder": "cli",
        "options": ["cli", "api"],
    },
    "llm_provider": {
        "label": "LLM Provider",
        "group": "llm",
        "secret": False,
        "help": "Which LLM powers the creator agents. Options: gemini, claude, ollama, nvidia, openai, anthropic, opencode, hermes, kilocode, agy",
        "placeholder": "gemini",
        "options": ["gemini", "claude", "ollama", "nvidia", "openai", "anthropic", "opencode", "hermes", "kilocode", "agy"],
    },
    "llm_model": {
        "label": "LLM Model",
        "group": "llm",
        "secret": False,
        "help": "Model name for the chosen provider (e.g. gpt-4o, claude-opus-4-5, phi3:mini)",
        "placeholder": "",
    },
    "llm_api_key": {
        "label": "LLM API Key",
        "group": "llm",
        "secret": True,
        "help": "API key for OpenAI, Anthropic, or NVIDIA NIM. Leave blank for local CLIs or Ollama.",
        "placeholder": "sk-...",
    },
    "llm_base_url": {
        "label": "LLM Base URL (OpenAI-compatible)",
        "group": "llm",
        "secret": False,
        "help": "Custom base URL for self-hosted or OpenAI-compatible endpoints (e.g. http://localhost:1234/v1)",
        "placeholder": "",
    },
    "ollama_url": {
        "label": "Ollama Server URL",
        "group": "llm",
        "secret": False,
        "help": "URL of your local Ollama instance",
        "placeholder": "http://localhost:11434",
    },
    "ollama_model": {
        "label": "Ollama Model",
        "group": "llm",
        "secret": False,
        "help": "Model pulled in Ollama (e.g. phi3:mini, llama3, mistral)",
        "placeholder": "phi3:mini",
    },
    "gemini_path": {
        "label": "Gemini CLI Path",
        "group": "llm",
        "secret": False,
        "help": "Path to your local gemini binary (default: gemini)",
        "placeholder": "gemini",
    },
    "claude_path": {
        "label": "Claude CLI Path",
        "group": "llm",
        "secret": False,
        "help": "Path to your local claude binary (default: claude)",
        "placeholder": "claude",
    },
    "opencode_path": {
        "label": "OpenCode CLI Path",
        "group": "llm",
        "secret": False,
        "help": "Path to your local opencode binary (default: opencode)",
        "placeholder": "opencode",
    },
    "hermes_path": {
        "label": "Hermes CLI Path",
        "group": "llm",
        "secret": False,
        "help": "Path to your local hermes binary (default: hermes)",
        "placeholder": "hermes",
    },
    "kilocode_path": {
        "label": "Kilocode CLI Path",
        "group": "llm",
        "secret": False,
        "help": "Path to your local kilo binary (default: kilo)",
        "placeholder": "kilo",
    },
    "agy_path": {
        "label": "Antigravity CLI Path",
        "group": "llm",
        "secret": False,
        "help": "Path to your local agy binary (default: agy)",
        "placeholder": "agy",
    },
    # Cloudflare
    "cloudflare_account_id": {
        "label": "Cloudflare Account ID",
        "group": "cloudflare",
        "secret": False,
        "help": "Cloudflare Account ID from your dashboard overview page",
        "placeholder": "",
    },
    "cloudflare_api_token": {
        "label": "Cloudflare API Token",
        "group": "cloudflare",
        "secret": True,
        "help": "Cloudflare API token with DNS:Edit permissions",
        "placeholder": "cfat_...",
    },
}

# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_raw() -> Dict[str, str]:
    """Load raw settings dict from disk (empty dict if not found)."""
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[settings] Warning: could not read {SETTINGS_FILE}: {e}")
    return {}


def _save_raw(data: Dict[str, str]) -> None:
    """Persist raw settings dict to disk."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _mask(value: str) -> str:
    """Mask a secret value for API responses — show last 4 chars only."""
    if not value or len(value) < 8:
        return "****"
    return "****" + value[-4:]


# ── Public API ────────────────────────────────────────────────────────────────

def get_all() -> Dict[str, str]:
    """
    Return resolved settings: env vars > settings file > empty string.
    Includes all schema keys.
    """
    stored = _load_raw()
    result: Dict[str, str] = {}

    # Env var mapping for each key
    _env_map = {
        "youtube_api_key": "YOUTUBE_API_KEY",
        "fal_api_key":     "FAL_API_KEY",
        "llm_provider":    "LLM_PROVIDER",
        "llm_model":       "LLM_MODEL",
        "llm_api_key":     "LLM_API_KEY",
        "llm_base_url":    "LLM_BASE_URL",
        "ollama_url":      "OLLAMA_URL",
        "ollama_model":    "OLLAMA_MODEL",
        "cloudflare_account_id": "CLOUDFLARE_ACCOUNT_ID",
        "cloudflare_api_token":  "CLOUDFLARE_API_TOKEN",
        "deployment_mode": "DEPLOYMENT_MODE",
        "kilocode_path": "KILOCODE_PATH",
        "agy_path": "AGY_PATH",
        "gemini_path": "GEMINI_PATH",
        "claude_path": "CLAUDE_PATH",
        "opencode_path": "OPENCODE_PATH",
        "hermes_path": "HERMES_PATH",
    }

    for key in SCHEMA:
        env_val = os.environ.get(_env_map.get(key, ""), "")
        result[key] = env_val or stored.get(key, "")

    return result


def get(key: str) -> str:
    """Get a single resolved setting value."""
    return get_all().get(key, "")


def update(updates: Dict[str, str]) -> Dict[str, str]:
    """
    Merge updates into the settings file.
    Returns the new full settings dict (unmasked — used internally).
    """
    stored = _load_raw()
    for key, value in updates.items():
        if key in SCHEMA:
            stored[key] = (value or "").strip()
    _save_raw(stored)
    return get_all()


def delete(key: str) -> None:
    """Remove a key from the settings file."""
    stored = _load_raw()
    stored.pop(key, None)
    _save_raw(stored)


def get_for_api() -> Dict[str, Any]:
    """
    Return settings formatted for the frontend:
    - secret values are masked
    - schema metadata included per key
    - env_override flag tells UI to show a lock icon
    """
    raw = get_all()
    _env_map = {
        "youtube_api_key": "YOUTUBE_API_KEY",
        "fal_api_key":     "FAL_API_KEY",
        "llm_provider":    "LLM_PROVIDER",
        "llm_model":       "LLM_MODEL",
        "llm_api_key":     "LLM_API_KEY",
        "llm_base_url":    "LLM_BASE_URL",
        "ollama_url":      "OLLAMA_URL",
        "ollama_model":    "OLLAMA_MODEL",
        "cloudflare_account_id": "CLOUDFLARE_ACCOUNT_ID",
        "cloudflare_api_token":  "CLOUDFLARE_API_TOKEN",
        "deployment_mode": "DEPLOYMENT_MODE",
        "kilocode_path": "KILOCODE_PATH",
        "agy_path": "AGY_PATH",
        "gemini_path": "GEMINI_PATH",
        "claude_path": "CLAUDE_PATH",
        "opencode_path": "OPENCODE_PATH",
        "hermes_path": "HERMES_PATH",
    }

    result = {"schema": SCHEMA, "values": {}}
    for key, meta in SCHEMA.items():
        value = raw.get(key, "")
        env_override = bool(os.environ.get(_env_map.get(key, ""), ""))
        result["values"][key] = {
            "value": _mask(value) if meta["secret"] and value else value,
            "has_value": bool(value),
            "env_override": env_override,
        }
    return result


def validate_youtube_key(api_key: str) -> Dict[str, Any]:
    """
    Validate a YouTube API key by calling the cheap /videoCategories endpoint.
    Returns {"ok": True} or {"ok": False, "error": "..."}
    """
    try:
        import urllib.request
        import urllib.parse
        url = (
            "https://www.googleapis.com/youtube/v3/videoCategories"
            f"?part=snippet&regionCode=US&key={urllib.parse.quote(api_key)}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "DailyDex/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            if data.get("items"):
                return {"ok": True, "quota_info": "Key valid — 10,000 units/day free"}
            return {"ok": False, "error": "Key returned empty response"}
    except Exception as e:
        err = str(e)
        if "403" in err or "keyInvalid" in err:
            return {"ok": False, "error": "Invalid API key or YouTube Data API v3 not enabled"}
        if "400" in err:
            return {"ok": False, "error": "Bad request — check the key format"}
        return {"ok": False, "error": f"Connection error: {err}"}


def validate_fal_key(api_key: str) -> Dict[str, Any]:
    """
    Validate a fal.ai key by probing the queue endpoint.
    Returns {"ok": True} or {"ok": False, "error": "..."}

    HTTP status meanings:
      200 / 202 : Key valid, generation started (costs credits)
      400 / 422 : Key valid, but request payload issue — fine for validation
      401       : Invalid key
      403 + "Exhausted balance" : Key valid but no credits — still saves the key
      403 other : Key invalid or account issue
    """
    import urllib.error

    req = urllib.request.Request(
        "https://queue.fal.run/fal-ai/flux/schnell",
        method="POST",
        data=json.dumps({"prompt": "test", "num_images": 1}).encode(),
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "DailyDex/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            # 200/202 — key valid, job queued (would cost credits if real prompt)
            return {"ok": True, "quota_info": "Key valid — ~$0.003/image (Flux Schnell)"}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass

        if e.code == 401:
            return {"ok": False, "error": "Invalid fal.ai API key — check Dashboard → API Keys"}
        if e.code == 403:
            if "balance" in body.lower() or "exhausted" in body.lower() or "locked" in body.lower():
                # Key is real — just no credits
                return {
                    "ok": True,
                    "quota_info": "Key valid ✓ — balance exhausted. Top up at fal.ai/dashboard/billing",
                    "no_credits": True,
                }
            return {"ok": False, "error": f"Access denied: {body[:120]}"}
        if e.code in (400, 422):
            # Bad payload but key was accepted — valid key
            return {"ok": True, "quota_info": "Key valid — ~$0.003/image (Flux Schnell)"}
        return {"ok": False, "error": f"HTTP {e.code}: {body[:120]}"}
    except Exception as e:
        return {"ok": False, "error": f"Connection error: {str(e)}"}
