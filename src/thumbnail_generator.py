#!/usr/bin/env python3
"""
thumbnail_generator.py — Real Image Generation via fal.ai (Flux)
-----------------------------------------------------------------
Replaces text-description-only output with actual JPEG/PNG URLs
from Flux Schnell via fal.ai.

Cost: ~$0.003 per image (Flux Schnell). A creator making 10 thumbnails/week
spends ~$1.50/month.

Key setup:
  Sign up at https://fal.ai → Dashboard → API Keys → Create key
  Set via Settings UI or FAL_API_KEY env var.

Providers supported:
  - fal.ai (recommended, cheapest, no waitlist)
  - Replicate (fallback if FAL_API_KEY not set)

Style presets built for tech YouTube thumbnails:
  - dark_tech    : dark background, glowing UI, dramatic lighting
  - clean_white  : white background, bold typography feel
  - dramatic     : high contrast, split composition
  - minimal      : clean, modern, lots of space
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, List


# ── Key resolution ─────────────────────────────────────────────────────────────

def _get_fal_key() -> str:
    """Resolve fal.ai API key: env var > settings file."""
    env_key = os.environ.get("FAL_API_KEY", "")
    if env_key:
        return env_key
    try:
        from settings_manager import get as settings_get
        return settings_get("fal_api_key")
    except Exception:
        return ""


# ── Style presets ─────────────────────────────────────────────────────────────

STYLE_PRESETS = {
    "dark_tech": (
        "cinematic dark background, glowing neon blue and cyan accents, "
        "high-tech UI elements, dramatic lighting, sharp focus, "
        "professional YouTube thumbnail style, 4k quality"
    ),
    "clean_white": (
        "clean white background, bold colorful accents, "
        "modern minimalist design, professional photography style, "
        "YouTube thumbnail composition, high contrast, sharp"
    ),
    "dramatic": (
        "dramatic high contrast lighting, split composition, "
        "bold colors, cinematic grade, strong visual hierarchy, "
        "YouTube thumbnail style, striking visual impact"
    ),
    "minimal": (
        "minimal clean design, subtle gradient background, "
        "modern typography aesthetic, lots of negative space, "
        "professional and sophisticated, YouTube thumbnail"
    ),
    "explosion": (
        "bold explosive energy, vibrant orange and electric blue, "
        "dynamic composition, wow factor, high energy, "
        "tech creator YouTube thumbnail, eye-catching, viral aesthetic"
    ),
}


# ── fal.ai Flux API ───────────────────────────────────────────────────────────

FAL_FLUX_SCHNELL_URL = "https://fal.run/fal-ai/flux/schnell"
FAL_FLUX_DEV_URL     = "https://fal.run/fal-ai/flux/dev"


def generate_with_fal(
    prompt: str,
    api_key: str,
    style: str = "dark_tech",
    width: int = 1280,
    height: int = 720,
    num_images: int = 1,
    model: str = "schnell",
) -> Optional[Dict[str, Any]]:
    """
    Generate an image using Flux via fal.ai.

    Returns:
        {
          "url": "https://...",
          "width": 1280,
          "height": 720,
          "content_type": "image/jpeg",
          "model": "flux-schnell",
          "cost_estimate": "~$0.003"
        }
    or None on failure.
    """
    style_suffix = STYLE_PRESETS.get(style, STYLE_PRESETS["dark_tech"])
    full_prompt = f"{prompt}, {style_suffix}"

    endpoint = FAL_FLUX_DEV_URL if model == "dev" else FAL_FLUX_SCHNELL_URL

    payload = {
        "prompt": full_prompt,
        "image_size": {
            "width": width,
            "height": height,
        },
        "num_inference_steps": 4 if model == "schnell" else 28,
        "num_images": num_images,
        "enable_safety_checker": True,
        "output_format": "jpeg",
    }

    req = urllib.request.Request(
        endpoint,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "DailyDex/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:300]
        print(f"[thumbnail_gen] fal.ai HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"[thumbnail_gen] fal.ai error: {e}")
        return None

    images = data.get("images", [])
    if not images:
        print("[thumbnail_gen] fal.ai returned no images")
        return None

    img = images[0]
    return {
        "url":           img.get("url", ""),
        "width":         img.get("width", width),
        "height":        img.get("height", height),
        "content_type":  img.get("content_type", "image/jpeg"),
        "model":         f"flux-{model}",
        "provider":      "fal.ai",
        "cost_estimate": "~$0.003" if model == "schnell" else "~$0.025",
        "prompt_used":   full_prompt,
    }


# ── Replicate fallback ────────────────────────────────────────────────────────

def generate_with_replicate(
    prompt: str,
    api_key: str,
    style: str = "dark_tech",
) -> Optional[Dict[str, Any]]:
    """Fallback: generate via Replicate's Flux Schnell endpoint."""
    style_suffix = STYLE_PRESETS.get(style, STYLE_PRESETS["dark_tech"])
    full_prompt = f"{prompt}, {style_suffix}"

    create_payload = {
        "version": "5f24084160c9089501c1b3545d9be3c27883ae2239b6f412990e82d4a6210f8f",  # flux-schnell
        "input": {
            "prompt": full_prompt,
            "width": 1280,
            "height": 720,
            "num_outputs": 1,
            "output_format": "jpg",
        },
    }

    # Step 1: create prediction
    req = urllib.request.Request(
        "https://api.replicate.com/v1/predictions",
        method="POST",
        data=json.dumps(create_payload).encode(),
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "DailyDex/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            pred = json.loads(resp.read().decode())
    except Exception as e:
        print(f"[thumbnail_gen] Replicate create error: {e}")
        return None

    poll_url = pred.get("urls", {}).get("get")
    if not poll_url:
        return None

    # Step 2: poll for completion (max 60s)
    auth_header = {"Authorization": f"Token {api_key}", "User-Agent": "DailyDex/1.0"}
    for _ in range(30):
        time.sleep(2)
        poll_req = urllib.request.Request(poll_url, headers=auth_header)
        try:
            with urllib.request.urlopen(poll_req, timeout=10) as r:
                result = json.loads(r.read().decode())
        except Exception:
            continue

        status = result.get("status")
        if status == "succeeded":
            outputs = result.get("output", [])
            if outputs:
                return {
                    "url":           outputs[0],
                    "width":         1280,
                    "height":        720,
                    "content_type":  "image/jpeg",
                    "model":         "flux-schnell",
                    "provider":      "replicate",
                    "cost_estimate": "~$0.003",
                    "prompt_used":   full_prompt,
                }
        elif status in ("failed", "canceled"):
            print(f"[thumbnail_gen] Replicate prediction {status}")
            return None

    print("[thumbnail_gen] Replicate timed out")
    return None


# ── Main public interface ─────────────────────────────────────────────────────

def generate_thumbnail(
    topic: str,
    style: str = "dark_tech",
    extra_context: Optional[str] = None,
    num_variants: int = 1,
) -> List[Dict[str, Any]]:
    """
    Generate thumbnail image(s) for a given topic.

    Builds a creator-optimised prompt, then calls fal.ai (or Replicate if no
    fal key).

    Returns a list of result dicts (each with a .url field). Empty list on failure.
    """
    fal_key = _get_fal_key()

    # Build a thumbnail-optimised prompt
    base_prompt = _build_thumbnail_prompt(topic, extra_context)

    results = []

    if fal_key:
        for i in range(num_variants):
            style_to_use = style if i == 0 else list(STYLE_PRESETS.keys())[i % len(STYLE_PRESETS)]
            result = generate_with_fal(base_prompt, fal_key, style=style_to_use)
            if result:
                result["variant_index"] = i
                result["style"] = style_to_use
                results.append(result)
    else:
        # Check for Replicate key
        replicate_key = os.environ.get("REPLICATE_API_KEY", "")
        if replicate_key:
            result = generate_with_replicate(base_prompt, replicate_key, style=style)
            if result:
                results.append(result)
        else:
            print("[thumbnail_gen] No image generation key found. Set FAL_API_KEY or REPLICATE_API_KEY.")
            # Return a text-only fallback so the UI still has something
            results.append({
                "url": None,
                "prompt_used": f"{base_prompt}, {STYLE_PRESETS.get(style, '')}",
                "provider": "none",
                "error": "No API key. Add your fal.ai key in Settings → Image Generation.",
            })

    return results


def _build_thumbnail_prompt(topic: str, extra_context: Optional[str] = None) -> str:
    """
    Build a YouTube-thumbnail-optimised image prompt for a tech topic.
    No text overlays (those are added in editing tools like Canva/Photoshop).
    """
    # Clean up the topic string
    topic = topic.strip().rstrip(".")
    context_suffix = f", context: {extra_context}" if extra_context else ""

    return (
        f"YouTube thumbnail image concept for the topic: {topic}{context_suffix}. "
        f"No text or words in the image. Tech-focused, modern design, "
        f"visually represents the concept of {topic}. "
        f"High quality, sharp focus, studio-grade composition"
    )


def thumbnail_preview_html(result: Dict[str, Any]) -> str:
    """Return a simple HTML img tag or error message for embedding in the cockpit."""
    if result.get("url"):
        return f'<img src="{result["url"]}" alt="Generated thumbnail" style="max-width:100%;border-radius:8px;">'
    return f'<div style="color:#ff6b6b;font-size:12px;">{result.get("error", "Generation failed")}</div>'
