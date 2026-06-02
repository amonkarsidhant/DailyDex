"""CLI model registry — autonomous provider discovery for Creator Central.

DailyDex's content factory does not assume any one model backend. It probes the
machine for whatever model CLIs / API providers are installed and authenticated
(claude, gemini, opencode, hermes, ollama, NVIDIA NIM, …), caches what works,
and exposes one `generate()` call that routes to the best available provider
with automatic fallback.

Each provider is a small spec: how to detect it, and how to run one headless
text generation. Add a provider by appending to ``_PROVIDERS``.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
PROBE_CACHE = os.path.join(DATA_DIR, "cli_providers.json")
PROBE_TTL_SEC = int(os.environ.get("CLI_PROBE_TTL_SEC", "1800"))  # 30 min
GEN_TIMEOUT = int(os.environ.get("STUDIO_GEN_TIMEOUT", "240"))

def _get_bin(key: str, default: str) -> str:
    try:
        import settings_manager
        return settings_manager.get(key) or default
    except Exception:
        return default

def _get_deployment_mode() -> str:
    try:
        import settings_manager
        return settings_manager.get("deployment_mode") or "cli"
    except Exception:
        return "cli"

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _heal_path() -> None:
    """launchd hands agents a minimal PATH (/usr/bin:/bin). Model CLIs live in
    Homebrew and per-user bin dirs — prepend the usual locations so detection
    and invocation work the same under launchd as in an interactive shell."""
    home = os.path.expanduser("~")
    extra = [
        "/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin",
        os.path.join(home, ".opencode", "bin"),
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".cargo", "bin"),
        os.path.join(home, "bin"),
    ]
    extra += [p for p in os.environ.get("STUDIO_EXTRA_PATH", "").split(":") if p]
    current = os.environ.get("PATH", "").split(":")
    for d in extra:
        if d and os.path.isdir(d) and d not in current:
            current.insert(0, d)
    os.environ["PATH"] = ":".join(current)


_heal_path()


def _strip(text: str) -> str:
    text = _ANSI.sub("", text or "")
    # drop think/reasoning blocks some models emit
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    if "</think>" in text:
        text = text.split("</think>")[-1]
    return text.strip()


def _run(args: List[str], timeout: int, stdin_text: Optional[str] = None) -> Optional[str]:
    try:
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            input=stdin_text,
            stdin=None if stdin_text is not None else subprocess.DEVNULL,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    except Exception:
        return None
    if res.returncode != 0:
        return None
    return _strip(res.stdout) or None


# --------------------------------------------------------------------------- #
# Provider specs
# --------------------------------------------------------------------------- #
@dataclass
class Provider:
    name: str
    label: str
    kind: str                                   # "cli" | "http"
    detect: Callable[[], bool]
    generate: Callable[[str, Optional[str], int], Optional[str]]
    model: str = ""
    priority: int = 50                          # lower = preferred
    notes: str = ""


def _combine(prompt: str, system: Optional[str]) -> str:
    return f"{system}\n\n{prompt}" if system else prompt


def _get_profile_model(provider_name: str, fallback_model: str) -> str:
    """Helper to dynamically fetch model specified in creator_profile.json."""
    prof_data = None
    try:
        import llm_summary
        prof_data = llm_summary.load_creator_profile()
    except Exception:
        pass

    if not prof_data:
        try:
            profile_path = os.environ.get(
                "CREATOR_PROFILE_PATH",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "creator_profile.json")
            )
            if os.path.exists(profile_path):
                with open(profile_path, "r", encoding="utf-8") as f:
                    prof_data = json.load(f)
        except Exception:
            pass

    if prof_data and isinstance(prof_data, dict):
        try:
            cop_cfg = prof_data.get("copilot") or {}
            if cop_cfg.get("provider") == provider_name:
                return cop_cfg.get("model") or fallback_model
        except Exception:
            pass
    return fallback_model


# -- opencode: authed, free models, no API key -- preferred autonomous engine --
_OPENCODE_MODEL = os.environ.get("STUDIO_OPENCODE_MODEL", "opencode/deepseek-v4-flash-free")

def _opencode_detect() -> bool:
    bin_path = _get_bin("opencode_path", "opencode")
    if not shutil.which(bin_path):
        return False
    out = _run([bin_path, "models"], timeout=20)
    return bool(out and "/" in out)

def _opencode_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    bin_path = _get_bin("opencode_path", "opencode")
    model = _get_profile_model("opencode", _OPENCODE_MODEL)
    return _run([bin_path, "run", "-m", model, _combine(prompt, system)], timeout)


# -- claude code CLI: OAuth session, no key --
_CLAUDE_BIN = os.environ.get("CLAUDE_CODE_BIN", os.environ.get("CLAUDE_CODE_EXECPATH", "claude"))
_CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

def _claude_detect() -> bool:
    bin_path = _get_bin("claude_path", _CLAUDE_BIN)
    return bool(shutil.which(bin_path))

def _claude_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    bin_path = _get_bin("claude_path", _CLAUDE_BIN)
    model = _get_profile_model("claude", _CLAUDE_MODEL)
    return _run([bin_path, "-p", _combine(prompt, system), "--model", model], timeout)


# -- hermes: agent CLI with --skills / --yolo --
_HERMES_MODEL = os.environ.get("HERMES_MODEL", "")

def _hermes_detect() -> bool:
    bin_path = _get_bin("hermes_path", "hermes")
    return bool(shutil.which(bin_path))

def _hermes_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    bin_path = _get_bin("hermes_path", "hermes")
    model = _get_profile_model("hermes", _HERMES_MODEL)
    args = [bin_path, "-z", _combine(prompt, system), "--yolo"]
    if model:
        args += ["-m", model]
    return _run(args, timeout)


# -- gemini CLI: needs auth/key --
_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")

def _gemini_detect() -> bool:
    bin_path = _get_bin("gemini_path", "gemini")
    if not shutil.which(bin_path):
        return False
    # gemini fails without an auth method; a fast probe avoids dead routing
    out = _run([bin_path, "-p", "ping"], timeout=25)
    return out is not None

def _gemini_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    bin_path = _get_bin("gemini_path", "gemini")
    model = _get_profile_model("gemini", _GEMINI_MODEL)
    args = [bin_path, "-p", _combine(prompt, system)]
    if model:
        args += ["--model", model]
    return _run(args, timeout)


# -- kilocode: kilo CLI --
def _kilocode_detect() -> bool:
    bin_path = _get_bin("kilocode_path", "kilo")
    if not shutil.which(bin_path):
        if bin_path == "kilo" and shutil.which("kilocode"):
            return True
        return False
    return True

def _kilocode_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    bin_path = _get_bin("kilocode_path", "kilo")
    if not shutil.which(bin_path) and shutil.which("kilocode"):
        bin_path = "kilocode"
    model = _get_profile_model("kilocode", "")
    args = [bin_path, _combine(prompt, system)]
    if model:
        args += ["--model", model]
    return _run(args, timeout)


# -- agy: Google Antigravity CLI --
def _agy_detect() -> bool:
    bin_path = _get_bin("agy_path", "agy")
    if not shutil.which(bin_path):
        return False
    out = _run([bin_path, "help"], timeout=10)
    return out is not None

def _agy_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    bin_path = _get_bin("agy_path", "agy")
    args = [bin_path, "-p", _combine(prompt, system), "--dangerously-skip-permissions"]
    return _run(args, timeout)


# -- ollama: local models --
_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "")

def _ollama_detect() -> bool:
    if not shutil.which("ollama"):
        return False
    out = _run(["ollama", "list"], timeout=15)
    return bool(out and "\n" in out)

def _ollama_model() -> str:
    if _OLLAMA_MODEL:
        return _OLLAMA_MODEL
    out = _run(["ollama", "list"], timeout=15) or ""
    for line in out.splitlines()[1:]:
        name = line.split()[0] if line.split() else ""
        if name:
            return name
    return "llama3.2"

def _ollama_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    model = _get_profile_model("ollama", _ollama_model())
    return _run(["ollama", "run", model, _combine(prompt, system)], timeout)


# -- NVIDIA NIM: OpenAI-compatible HTTP, needs NVIDIA_API_KEY --
def _nvidia_detect() -> bool:
    return bool(os.environ.get("NVIDIA_API_KEY"))

def _nvidia_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    try:
        import llm_summary
        model = _get_profile_model("nvidia", os.environ.get("NVIDIA_MODEL", ""))
        return llm_summary.query_nvidia(prompt, system, model=model)
    except Exception:
        return None


# -- Anthropic API: direct REST, needs ANTHROPIC_API_KEY --
_ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_STUDIO_MODEL", "claude-haiku-4-5-20251001")

def _anthropic_detect() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))

def _anthropic_gen(prompt: str, system: Optional[str], timeout: int) -> Optional[str]:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    try:
        payload: dict = {
            "model": _ANTHROPIC_MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
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
    except Exception:
        return None


_PROVIDERS: List[Provider] = [
    Provider("anthropic", "Anthropic API (claude-haiku)", "http", _anthropic_detect, _anthropic_gen, _ANTHROPIC_MODEL, priority=5),
    Provider("opencode", "opencode (free models)", "cli", _opencode_detect, _opencode_gen, _OPENCODE_MODEL, priority=10),
    Provider("claude", "Claude Code CLI", "cli", _claude_detect, _claude_gen, _CLAUDE_MODEL, priority=20),
    Provider("nvidia", "NVIDIA NIM", "http", _nvidia_detect, _nvidia_gen, os.environ.get("NVIDIA_MODEL", ""), priority=30),
    Provider("hermes", "Hermes agent", "cli", _hermes_detect, _hermes_gen, _HERMES_MODEL, priority=40),
    Provider("kilocode", "Kilocode CLI", "cli", _kilocode_detect, _kilocode_gen, "", priority=45),
    Provider("agy", "Antigravity CLI (agy)", "cli", _agy_detect, _agy_gen, "", priority=48),
    Provider("gemini", "Gemini CLI", "cli", _gemini_detect, _gemini_gen, _GEMINI_MODEL, priority=50),
    Provider("ollama", "Ollama (local)", "cli", _ollama_detect, _ollama_gen, _OLLAMA_MODEL, priority=60),
]

_BY_NAME = {p.name: p for p in _PROVIDERS}


# --------------------------------------------------------------------------- #
# Probing (cached)
# --------------------------------------------------------------------------- #
def _load_cache(mode: str) -> Optional[Dict]:
    try:
        with open(PROBE_CACHE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("deployment_mode") != mode:
            return None
        if time.time() - data.get("probed_at", 0) < PROBE_TTL_SEC:
            return data
    except Exception:
        pass
    return None


def _save_cache(data: Dict) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(PROBE_CACHE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def probe(force: bool = False) -> Dict:
    """Detect available providers. Result cached for PROBE_TTL_SEC.

    Returns {"probed_at", "available": [name...], "providers": [{name,label,kind,model,available,priority}]}.
    """
    mode = _get_deployment_mode()
    if not force:
        cached = _load_cache(mode)
        if cached:
            return cached
    providers = []
    available = []
    for p in sorted(_PROVIDERS, key=lambda x: x.priority):
        if mode == "api" and p.kind == "cli":
            continue
        ok = False
        try:
            ok = bool(p.detect())
        except Exception:
            ok = False
        if ok:
            available.append(p.name)
        providers.append({
            "name": p.name, "label": p.label, "kind": p.kind,
            "model": p.model, "available": ok, "priority": p.priority,
        })
    data = {"probed_at": time.time(), "available": available, "providers": providers, "deployment_mode": mode}
    _save_cache(data)
    return data


def available_providers(force: bool = False) -> List[str]:
    return probe(force=force).get("available", [])


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def generate(prompt: str, system: Optional[str] = None, *,
             prefer: Optional[str] = None, timeout: int = GEN_TIMEOUT,
             log_fn: Optional[Callable[[str], None]] = None) -> Dict:
    """Generate text via the best available provider, with fallback.

    Returns {"text", "provider", "model", "elapsed_ms", "tried"}.
    `text` is None if every available provider failed.
    """
    order: List[str] = []
    if prefer and prefer in _BY_NAME:
        order.append(prefer)
    order += [n for n in available_providers() if n not in order]

    tried = []
    for name in order:
        p = _BY_NAME.get(name)
        if not p:
            continue
        msg = f"Invoking CLI provider: {name} ({p.label})..."
        if log_fn:
            log_fn(msg)
        started = time.time()
        try:
            text = p.generate(prompt, system, timeout)
        except Exception as e:
            text = None
            if log_fn:
                log_fn(f"CLI provider {name} failed: {e}")
        elapsed = int((time.time() - started) * 1000)
        tried.append({"provider": name, "ok": bool(text), "elapsed_ms": elapsed})
        if text:
            msg_ok = f"CLI provider {name} succeeded in {elapsed}ms"
            if log_fn:
                log_fn(msg_ok)
            actual_model = _get_profile_model(name, p.model)
            return {"text": text, "provider": name, "model": actual_model,
                    "elapsed_ms": elapsed, "tried": tried}
        else:
            msg_fail = f"CLI provider {name} returned empty/failed in {elapsed}ms"
            if log_fn:
                log_fn(msg_fail)
    return {"text": None, "provider": None, "model": "", "elapsed_ms": 0, "tried": tried}


if __name__ == "__main__":
    import sys
    info = probe(force=True)
    print("Detected providers:")
    for p in info["providers"]:
        mark = "✓" if p["available"] else "·"
        print(f"  {mark} {p['name']:10} {p['label']}  ({p['model'] or 'auto'})")
    if len(sys.argv) > 1:
        out = generate(sys.argv[1])
        print(f"\nvia {out['provider']} in {out['elapsed_ms']}ms:\n{out['text']}")
