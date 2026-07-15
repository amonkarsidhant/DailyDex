"""Studio-Grade Animated Motion Graphics & Live Demo Video Renderer.

Generates 1080x1920 vertical Shorts with:
1. ElevenLabs AI Voiceover (Charlie - Deep, Confident, Energetic)
2. Live-typing macOS Terminal Demo window (commands + streaming logs), rendered
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
from typing import Dict, Any, Optional, List

VIDEO_ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video-engine")
FPS = 30

# Inside Docker, the video engine lives at /engine (built from Dockerfile.video).
# Locally, it's the video-engine/ directory next to src/.
_RENDER_CMD = None
def _resolve_render_command():
    """Pick the right way to invoke Remotion: direct npx, or docker compose run."""
    global _RENDER_CMD
    if _RENDER_CMD is not None:
        return _RENDER_CMD
    engine_dir = os.environ.get("VIDEO_ENGINE_DIR", VIDEO_ENGINE_DIR)
    has_npx = shutil.which("npx") is not None
    has_engine = os.path.isdir(os.path.join(engine_dir, "src"))
    if has_npx and has_engine:
        _RENDER_CMD = ("npx",)
    else:
        _RENDER_CMD = ("docker", "compose", "run", "--rm", "-T", "video")
    return _RENDER_CMD


def _generate_elevenlabs_audio(text: str, api_key: str, output_path: str) -> bool:
    url = "https://api.elevenlabs.io/v1/text-to-speech/IKne3meq5aSn9XLyUdCD"
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
    except Exception as e:
        print(f"[video_renderer] ElevenLabs API error: {e}")
        return False


def _pick_demo_content(title: str, hook_text: str):
    """Return (demo_cmd, demo_logs, metric_label, metric_val, metric_unit) for the topic."""
    t_lower = (title + " " + hook_text).lower()
    if "hit piece" in t_lower or "rogue" in t_lower or "published" in t_lower:
        return (
            "tail -f /var/log/autonomous_agent.log",
            [
                "[AUDIT] Step 41: Recursion threshold reached",
                "[ALERT] Prompt drift -> Context window saturated",
                "[EXEC] tool_call -> blog_publish('Hit Piece...')",
                "[LIVE] Post published • 14,200 impressions",
                "[RULE] Sand-box write tools with human review"
            ],
            "Unchecked Tool Escalation Rate", 4120.0, "calls / hr"
        )
    if "bankrupt" in t_lower or "billing" in t_lower or "dn42" in t_lower or "saas" in t_lower or "$4,800" in t_lower:
        return (
            "curl -s https://api.openai.com/v1/usage",
            [
                "[ACCT] ID: org-daily-dex-prod | Status: ACTIVE",
                "[SPIKE] 03:14 AM -> 89,412 loop retries logged",
                "[CHARGE] 148.2M input tokens billed @ $15/M",
                "[INVOICE] Total balance reached: $4,842.19 USD",
                "[FIX] Added local circuit breaker + 3B fallback"
            ],
            "Cloud Runaway Cost Burn Rate", 142.5, "$ USD / min"
        )
    if "opencode" in t_lower or "coding" in t_lower or "offline" in t_lower or "3b" in t_lower:
        return (
            "opencode --refactor ./src/engine.py",
            [
                "[MODEL] OpenCode-7B-Instruct (Q4_K_M) loaded",
                "[PARSE] AST generated across 24 source files",
                "[DIFF] +142 / -89 lines modified in 1.4s pass",
                "[TEST] pytest passed • 48 tests • 0 errors",
                "[PRIVACY] Zero telemetry • 100% Offline execution"
            ],
            "Local Refactor Pass Accuracy", 94.8, "% Score"
        )
    if "pi 4" in t_lower or "raspberry" in t_lower or "llamafile" in t_lower:
        return (
            "./llamafile --model 3b-instruct.gguf",
            [
                "[INFO] CPU Arch: ARM64 Cortex-A72 | RAM: 8.0 GB",
                "[LOAD] mmap weights 1.86 GB ... READY (0.42s)",
                "[TEST] Prompt: 'Extract key metrics from JSON'",
                "[BENCH] Generation speed: 6.42 tokens/sec local",
                "[SUCCESS] Zero cloud calls • Zero API latency"
            ],
            "Local Pi 4 Inference Speed", 6.4, "tok / sec"
        )
    return (
        "python3 -m dailydex.creator_labs --topic",
        [
            "[MINER] Connected to Hacker News & Reddit feeds",
            "[SIGNAL] Found 4 breakout audience debates",
            "[SCRIPT] Synthesized contrarian hook structure",
            "[STUDIO] Rendered kinetic subtitles & voiceover",
            "[READY] Prepared Shorts distribution queue"
        ],
        "Audience Engagement Signal", 91.5, "% Virality"
    )


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
    evidence: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Render a full animated motion graphics + live terminal demo Short via Remotion."""
    import settings_manager
    elevenlabs_key = settings_manager.get("elevenlabs_api_key")

    if not clip_id:
        clip_id = f"clip-{uuid.uuid4().hex[:8]}"

    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "videos")
    os.makedirs(base_dir, exist_ok=True)

    render_tmp_dir = os.path.join(VIDEO_ENGINE_DIR, "public", "render_tmp", clip_id)
    os.makedirs(render_tmp_dir, exist_ok=True)

    if not output_path:
        output_path = os.path.join(base_dir, f"{clip_id}.mp4")

    narration = (script_text or f"{hook_text}. {title}.").strip()

    # Step 1: Generate human voiceover using ElevenLabs API
    used_elevenlabs = False
    audio_path = os.path.join(render_tmp_dir, "voice.mp3")
    if elevenlabs_key:
        used_elevenlabs = _generate_elevenlabs_audio(narration, elevenlabs_key, audio_path)

    if not used_elevenlabs:
        audio_path = os.path.join(render_tmp_dir, "voice.wav")
        subprocess.run(
            ["say", "-o", audio_path, "--data-format=LEF32@22050", narration],
            check=True, timeout=15
        )

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
        demo_cmd, demo_logs, metric_label, metric_val, metric_unit = _pick_demo_content(title, hook_text)

    # Real recorded terminal demo (VHS) when available; synthetic card otherwise.
    demo_video_rel = ""
    if evidence:
        try:
            import demo_recorder

            demo_mp4 = os.path.join(render_tmp_dir, "demo.mp4")
            if demo_recorder.record_demo(evidence, demo_mp4):
                demo_video_rel = f"render_tmp/{clip_id}/demo.mp4"
        except Exception as e:
            print(f"[video_renderer] demo recording skipped: {e}")

    words = narration.split()
    duration_in_frames = max(1, int(round(duration_sec * FPS)))
    voice_rel_path = f"render_tmp/{clip_id}/{os.path.basename(audio_path)}"

    props = {
        "brandLabel": "HACKER NEWS • BREAKOUT REPORT",
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

    engine_dir = os.environ.get("VIDEO_ENGINE_DIR", VIDEO_ENGINE_DIR)
    render_cmd = _resolve_render_command()

    try:
        if render_cmd[0] == "npx":
            # Local: npx remotion render BreakoutShort <output> --props=<path>
            cmd = list(render_cmd) + [
                "remotion", "render", "BreakoutShort",
                output_path,
                f"--props={props_path}",
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=180, cwd=engine_dir)
        else:
            # Docker: the video container shares /app/data via the volume.
            # Write props + audio into the shared data dir so the container
            # can read them, then invoke `docker compose run --rm video`.
            data_dir = os.environ.get("DATA_DIR", "/app/data")
            shared_render_dir = os.path.join(data_dir, "render_tmp", clip_id)
            os.makedirs(shared_render_dir, exist_ok=True)

            # Copy props and audio to the shared location
            shared_props = os.path.join(shared_render_dir, "props.json")
            shutil.copy2(props_path, shared_props)

            # Copy audio if it exists
            shared_audio = os.path.join(shared_render_dir, os.path.basename(audio_path))
            shutil.copy2(audio_path, shared_audio)

            # Copy demo video if recorded
            if demo_video_rel:
                demo_src = os.path.join(render_tmp_dir, "demo.mp4")
                if os.path.exists(demo_src):
                    shutil.copy2(demo_src, os.path.join(shared_render_dir, "demo.mp4"))

            shared_output = os.path.join(data_dir, "videos", f"{clip_id}.mp4")
            os.makedirs(os.path.dirname(shared_output), exist_ok=True)

            # The video container's public/ is mounted to /app/data/render_tmp/{clip_id}
            # via the shared volume, so Remotion can find the audio/props there.
            # We pass a relative props path from the container's perspective.
            container_props_path = f"/app/data/render_tmp/{clip_id}/props.json"
            container_output_path = f"/app/data/videos/{clip_id}.mp4"

            cmd = list(render_cmd) + [
                "npx", "remotion", "render", "BreakoutShort",
                container_output_path,
                f"--props={container_props_path}",
                "--browser-executable=/usr/bin/chromium",
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=300, cwd=engine_dir)
            output_path = shared_output
        file_size = os.path.getsize(output_path)
        return {
            "success": True,
            "clip_id": clip_id,
            "video_path": output_path,
            "voice_engine": "ElevenLabs (Charlie)" if used_elevenlabs else "System TTS",
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
