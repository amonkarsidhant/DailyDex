"""Studio-Grade Animated Motion Graphics & Live Demo Video Renderer.

Generates 1080x1920 vertical Shorts with:
1. ElevenLabs AI Voiceover with deterministic creator-configured voice rotation
2. Live-typing Terminal Demo window (commands + streaming logs), rendered
   by the Remotion composition in video-engine/src/BreakoutShort.tsx
3. Animated visual benchmark metrics & progress indicators
4. Synchronized kinetic highlighted subtitles (word-by-word)

Frame compositing/rendering is delegated to Remotion (video-engine/), which
replaced the previous PIL-per-frame + ffmpeg-mux pipeline. This module still
owns: ElevenLabs narration synthesis, audio duration probing, and picking the
topic-specific demo content (command/logs/metric) shown in the terminal card.
"""

import os
import shutil
import subprocess
import uuid
import urllib.request
import urllib.error
import json
import hashlib
from typing import Dict, Any, Optional, List

VIDEO_ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video-engine")
FPS = 30
DEFAULT_ELEVENLABS_VOICES = [
    "IKne3meq5aSn9XLyUdCD",
    "pNInz6obpgDQGcFmaJgB",
    "ErXwobaYiNj19HyfgpX6",
    "TxGEqnHWrfWFTfGW9XjX",
]

# Inside Docker, the video engine lives at /engine.
# Locally, it's the video-engine/ directory next to src/.
_RENDER_CMD = None
_ELEVENLABS_VOICE_CACHE: Optional[List[str]] = None
def _resolve_render_command():
    """Resolve the local Remotion executable used by the render worker."""
    global _RENDER_CMD
    if _RENDER_CMD is not None:
        return _RENDER_CMD
    engine_dir = os.environ.get("VIDEO_ENGINE_DIR", VIDEO_ENGINE_DIR)
    has_npx = shutil.which("npx") is not None
    has_engine = os.path.isdir(os.path.join(engine_dir, "src"))
    if not (has_npx and has_engine):
        raise RuntimeError("Remotion is unavailable; run rendering in the video-worker service")
    _RENDER_CMD = ("npx",)
    return _RENDER_CMD


def _generate_elevenlabs_audio(text: str, api_key: str, output_path: str, voice_id: str) -> bool:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.2,
            "use_speaker_boost": True
        }
    }
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())
        return True
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")[:300]
        print(f"[video_renderer] ElevenLabs API error ({e.code}): {detail}")
        return False
    except Exception as e:
        print(f"[video_renderer] ElevenLabs API error: {e}")
        return False


def _available_elevenlabs_voice_ids(api_key: str) -> List[str]:
    """Return voices visible to this ElevenLabs account, cached per worker."""
    global _ELEVENLABS_VOICE_CACHE
    if _ELEVENLABS_VOICE_CACHE is not None:
        return _ELEVENLABS_VOICE_CACHE
    try:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v2/voices?page_size=100",
            headers={"xi-api-key": api_key, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        _ELEVENLABS_VOICE_CACHE = [
            str(voice.get("voice_id"))
            for voice in payload.get("voices", [])
            if voice.get("voice_id")
        ]
    except Exception as exc:
        print(f"[video_renderer] ElevenLabs voice catalog unavailable: {exc}")
        _ELEVENLABS_VOICE_CACHE = []
    return _ELEVENLABS_VOICE_CACHE


def _signal_demo_content(signal_context: Optional[Dict[str, Any]] = None):
    """Build a fallback card using only observed DailyDex scoring data."""
    context = signal_context or {}
    score = float(context.get("average_signal_score") or 0)
    source_count = int(context.get("source_count") or 0)
    sources = [str(value) for value in context.get("sources", []) if value]
    logs = [f"[SOURCE] {source}" for source in sources[:3]]
    logs.extend([
        f"[SIGNAL] DailyDex score: {score:.1f} / 100",
        f"[COVERAGE] {source_count} source families observed",
    ])
    return (
        "dailydex inspect --evidence",
        logs[:5],
        "DailyDex Signal Score",
        score,
        "/ 100",
    )


def _load_creator_profile() -> Dict[str, Any]:
    profile_path = os.environ.get(
        "CREATOR_PROFILE_PATH",
        os.path.join(os.path.dirname(VIDEO_ENGINE_DIR), "config", "creator_profile.json"),
    )
    try:
        with open(profile_path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _system_tts(text: str, output_dir: str) -> tuple[str, str]:
    if shutil.which("say"):
        output_path = os.path.join(output_dir, "voice.wav")
        subprocess.run(
            ["say", "-o", output_path, "--data-format=LEF32@22050", text],
            check=True, timeout=30,
        )
        return output_path, "macOS system voice"
    if shutil.which("espeak-ng"):
        output_path = os.path.join(output_dir, "voice.wav")
        subprocess.run(
            ["espeak-ng", "-w", output_path, "-s", "160", "-p", "40", text],
            check=True, timeout=30,
        )
        return output_path, "espeak-ng"
    raise RuntimeError("No TTS engine is available")


def _demo_from_evidence(evidence: Dict[str, Any]) -> Optional[tuple]:
    """Build the terminal card from REAL fetched evidence instead of canned
    keyword buckets. Returns (cmd, logs, metric_label, metric_val, metric_unit)
    or None when evidence is too thin to carry the card."""
    import re as _re

    facts = evidence.get("facts") or []
    quotes = evidence.get("quotes") or []
    excerpt = evidence.get("excerpt") or ""
    kind = evidence.get("source_kind") or ""
    url = evidence.get("url") or ""
    if not (facts or quotes):
        return None

    def _log(prefix: str, text: str) -> str:
        return f"[{prefix}] {text[:44]}"

    logs = []
    metric_label, metric_val, metric_unit = "", 0.0, ""

    if kind == "github":
        m = _re.search(r"github\.com/([\w.-]+/[\w.-]+)", url)
        repo = m.group(1) if m else "the repo"
        install = _re.search(r"\b((?:npm (?:i|install)|npx|pip install|brew install|cargo install)\s+[@\w./-]+)", excerpt)
        cmd = install.group(1) if install else f"git clone https://github.com/{repo}"
        for fact in facts:
            fact = str(fact)
            if "stars" in fact:
                stars = _re.search(r"([\d,]+)", fact)
                if stars:
                    metric_label = "GitHub Stars (live API)"
                    metric_val = float(stars.group(1).replace(",", ""))
                    metric_unit = "stars"
                logs.append(_log("REPO", fact))
            elif fact.startswith("Repo description:"):
                logs.append(_log("DESC", fact.replace("Repo description: ", "")))
            else:
                logs.append(_log("META", fact))
        forks = _re.search(r"([\d,]+(?:\.\d+)?[kK]?)\+?\s+forks", excerpt)
        if forks:
            logs.append(_log("META", f"{forks.group(1)} forks"))
    elif kind == "hackernews":
        story = _re.search(r"id=(\d+)", url)
        cmd = f"curl hn.algolia.com/api/v1/items/{story.group(1)}" if story else "curl hn.algolia.com/api/v1/search"
        for fact in facts:
            fact = str(fact)
            if "points" in fact:
                pts = _re.search(r"(\d+)", fact)
                if pts:
                    metric_label = "Hacker News Points (live)"
                    metric_val = float(pts.group(1))
                    metric_unit = "points"
                logs.append(_log("HN", fact))
            else:
                logs.append(_log("HN", fact))
        for quote in quotes[:2]:
            logs.append(_log("REPLY", f'"{str(quote)}"'))
    else:
        cmd = f"curl -sL {url[:40]}" if url else "open source article"
        logs = [_log("SRC", str(f)) for f in facts[:4]]
        for quote in quotes[:2]:
            logs.append(_log("QUOTE", f'"{str(quote)}"'))

    if not logs:
        return None
    if not metric_label:
        metric_label, metric_val, metric_unit = "Source Signals Cited", float(len(logs)), "facts"
    # The metric card renders val.toFixed(1); scale big counts to K/M so
    # 228236 stars reads "228.2 K stars", not "228236.0 stars".
    if metric_val >= 1_000_000:
        metric_val, metric_unit = metric_val / 1_000_000, f"M {metric_unit}"
    elif metric_val >= 10_000:
        metric_val, metric_unit = metric_val / 1_000, f"K {metric_unit}"
    return cmd[:48], logs[:5], metric_label, metric_val, metric_unit


def render_short_video(
    title: str,
    hook_text: str,
    script_text: Optional[str] = None,
    output_path: Optional[str] = None,
    clip_id: Optional[str] = None,
    virality_score: float = 85.0,
    evidence: Optional[Dict[str, Any]] = None,
    signal_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Render a full animated motion graphics + live terminal demo Short via Remotion."""
    import settings_manager
    elevenlabs_key = settings_manager.get("elevenlabs_api_key")
    profile = _load_creator_profile()

    if not clip_id:
        clip_id = f"clip-{uuid.uuid4().hex[:8]}"

    base_dir = os.path.join(os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__))), "videos")
    os.makedirs(base_dir, exist_ok=True)

    engine_dir = os.environ.get("VIDEO_ENGINE_DIR", VIDEO_ENGINE_DIR)
    render_asset_root = "render_jobs"
    render_tmp_dir = os.path.join(engine_dir, "public", render_asset_root, clip_id)
    os.makedirs(render_tmp_dir, exist_ok=True)

    if not output_path:
        output_path = os.path.join(base_dir, f"{clip_id}.mp4")

    narration = (script_text or f"{hook_text}. {title}.").strip()

    # Step 1: Generate human voiceover using ElevenLabs API
    used_elevenlabs = False
    voice_id = ""
    voice_engine = ""
    audio_path = os.path.join(render_tmp_dir, "voice.mp3")
    if elevenlabs_key:
        available_voices = _available_elevenlabs_voice_ids(elevenlabs_key)
        preferred_voices = profile.get("elevenlabs_voices") or DEFAULT_ELEVENLABS_VOICES
        voices = [voice for voice in preferred_voices if voice in available_voices]
        voices = voices or available_voices[:4] or preferred_voices
        voice_id = voices[int(hashlib.sha256(title.encode("utf-8")).hexdigest(), 16) % len(voices)]
        used_elevenlabs = _generate_elevenlabs_audio(
            narration, elevenlabs_key, audio_path, voice_id
        )

    if not used_elevenlabs:
        audio_path, voice_engine = _system_tts(narration, render_tmp_dir)
    else:
        voice_engine = "ElevenLabs"

    # Get duration
    duration_sec = 10.0
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=5
        )
        if probe.stdout.strip():
            duration_sec = max(4.0, float(probe.stdout.strip()))
    except Exception:
        duration_sec = 10.0

    demo = _demo_from_evidence(evidence) if evidence else None
    if demo:
        demo_cmd, demo_logs, metric_label, metric_val, metric_unit = demo
    else:
        demo_cmd, demo_logs, metric_label, metric_val, metric_unit = _signal_demo_content(signal_context)

    # Real recorded terminal demo (VHS) when available; synthetic card otherwise.
    demo_video_rel = ""
    if evidence:
        try:
            import demo_recorder

            demo_mp4 = os.path.join(render_tmp_dir, "demo.mp4")
            if demo_recorder.record_demo(evidence, demo_mp4):
                demo_video_rel = f"{render_asset_root}/{clip_id}/demo.mp4"
        except Exception as e:
            print(f"[video_renderer] demo recording skipped: {e}")

    words = narration.split()
    duration_in_frames = max(1, int(round(duration_sec * FPS)))
    voice_rel_path = f"{render_asset_root}/{clip_id}/{os.path.basename(audio_path)}"

    props = {
        "brandLabel": profile.get("brand_label") or profile.get("channel_name") or "DAILYDEX • AI REPORT",
        "accentColor": profile.get("video_accent_color") or "#F0B72F",
        "ctaLabel": profile.get("video_cta") or "FOLLOW FOR MORE AI REPORTS",
        "demoMode": "source_backed" if demo else "illustrative",
        "title": title,
        "demoCmd": demo_cmd,
        "demoLogs": demo_logs,
        "metricLabel": metric_label,
        "metricVal": metric_val,
        "metricUnit": metric_unit,
        "words": words,
        "voiceSrc": voice_rel_path,
        "bgMusicSrc": "bg_music.wav",
        "demoVideoSrc": demo_video_rel,
        "durationInFrames": duration_in_frames,
        "fps": FPS,
    }

    props_path = os.path.join(render_tmp_dir, "props.json")
    with open(props_path, "w") as f:
        json.dump(props, f)

    render_cmd = _resolve_render_command()

    try:
        cmd = list(render_cmd) + [
            "remotion", "render", "BreakoutShort", output_path,
            f"--props={props_path}",
        ]
        browser = os.environ.get("REMOTION_BROWSER_EXECUTABLE")
        if browser:
            cmd.append(f"--browser-executable={browser}")
        subprocess.run(cmd, check=True, capture_output=True, timeout=300, cwd=engine_dir)
        file_size = os.path.getsize(output_path)
        return {
            "success": True,
            "clip_id": clip_id,
            "video_path": output_path,
            "voice_engine": voice_engine,
            "voice_id": voice_id,
            "demo_mode": props["demoMode"],
            "has_animated_demo": True,
            "duration_sec": round(duration_sec, 2),
            "file_size_bytes": file_size
        }
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode("utf-8", errors="ignore")[:500]
        print(f"[video_renderer] Remotion render error: {err_msg}")
        return {"error": f"Video rendering failed: {err_msg}"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        shutil.rmtree(render_tmp_dir, ignore_errors=True)
