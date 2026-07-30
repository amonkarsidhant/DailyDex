"""
rescue_engine.py — 48-Hour Video Rescue & Telemetry Calibration Engine
----------------------------------------------------------------------
Evaluates performance metrics for published items, detects low-CTR videos,
and generates 1-click "Rescue Packs" (alternative titles & visual thumbnail prompts).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from llm_summary import query_llm

logger = logging.getLogger(__name__)

DEFAULT_MEDIAN_CTR = 0.045  # Ratio: 4.5%


def evaluate_performance_status(
    ctr: Optional[float],
    views: int,
    channel_median_ctr: float = DEFAULT_MEDIAN_CTR,
    *,
    impressions: Optional[int] = None,
    published_at: Optional[str] = None,
    now: Optional[datetime] = None,
    threshold_factor: float = 0.75,
    min_age_hours: int = 48,
    min_impressions: int = 100,
) -> Dict[str, Any]:
    """
    Evaluate performance status based on CTR and view count.

    Status Categories:
    - 'outlier': CTR > 1.5x median CTR and views > 1000
    - 'healthy': CTR >= 0.75x median CTR
    - 'low_ctr': CTR < 0.75x median CTR (triggers Rescue Pack)
    """
    if ctr is None or ctr <= 0 or not impressions or impressions < min_impressions:
        return {
            "status": "pending",
            "reason": "insufficient_ctr_evidence",
            "ctr": ctr,
            "views": views,
            "needs_rescue": False,
        }

    if published_at:
        try:
            published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            current = now or datetime.now(timezone.utc)
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            age_hours = (current - published).total_seconds() / 3600
            if age_hours < min_age_hours:
                return {
                    "status": "pending",
                    "reason": "awaiting_48h_window",
                    "ctr": ctr,
                    "views": views,
                    "needs_rescue": False,
                    "age_hours": round(max(0, age_hours), 1),
                }
        except (TypeError, ValueError):
            return {
                "status": "pending",
                "reason": "unknown_publication_age",
                "ctr": ctr,
                "views": views,
                "needs_rescue": False,
            }

    threshold = channel_median_ctr * min(0.95, max(0.5, threshold_factor))
    outlier_threshold = channel_median_ctr * 1.5

    if ctr >= outlier_threshold and views >= 1000:
        status = "outlier"
        needs_rescue = False
    elif ctr >= threshold:
        status = "healthy"
        needs_rescue = False
    else:
        status = "low_ctr"
        needs_rescue = True

    return {
        "status": status,
        "ctr": ctr,
        "views": views,
        "needs_rescue": needs_rescue,
        "threshold_ctr": threshold,
    }


def generate_rescue_pack(
    title: str,
    summary: str = "",
    niche: str = "software engineering",
) -> Dict[str, Any]:
    """
    Generate a 1-click Rescue Pack (3 punchy replacement titles + 2 thumbnail prompts)
    for an underperforming video.
    """
    if not isinstance(title, str) or not title.strip():
        return {"error": "Original title is required."}
    title = title.strip()[:100]
    summary = summary.strip()[:2000] if isinstance(summary, str) else ""
    niche = niche.strip()[:100] if isinstance(niche, str) and niche.strip() else "software engineering"

    prompt = (
        f"You are a YouTube viral strategist specializing in {niche}.\n"
        f"An existing video with the title '{title}' is underperforming with a low Click-Through Rate (CTR).\n"
        f"Context/Summary: {summary or 'Tech tutorial/analysis video.'}\n\n"
        f"Generate a Rescue Pack in JSON format with:\n"
        f"1. 'titles': array of 3 distinct, high-CTR replacement titles under 70 characters.\n"
        f"   - Title 1: Curiosity gap / Contrarian angle\n"
        f"   - Title 2: Urgency / Problem-solution angle\n"
        f"   - Title 3: High-energy outcome / Result angle\n"
        f"2. 'thumbnail_prompts': array of 2 visual concepts for AI image generation (e.g. Flux/fal.ai).\n"
        f"   - High contrast, bold subjects, maximum 3 words of text.\n\n"
        f"Return ONLY valid JSON with keys 'titles' and 'thumbnail_prompts'."
    )

    try:
        raw_res = query_llm(prompt) or ""
        # Attempt to parse JSON from LLM response
        clean_res = raw_res.strip()
        if "```json" in clean_res:
            clean_res = clean_res.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_res:
            clean_res = clean_res.split("```")[1].split("```")[0].strip()

        parsed = json.loads(clean_res)
        if not isinstance(parsed, dict):
            raise ValueError("rescue response must be an object")
        titles = parsed.get("titles", [])
        prompts = parsed.get("thumbnail_prompts", [])
        if not isinstance(titles, list) or not isinstance(prompts, list):
            raise ValueError("rescue titles and prompts must be arrays")
        titles = [value.strip()[:70] for value in titles if isinstance(value, str) and value.strip()]
        prompts = [value.strip()[:500] for value in prompts if isinstance(value, str) and value.strip()]

        if len(titles) < 3:
            titles = [
                f"Why {title} is Changing Everything",
                f"The Truth About {title}",
                f"Stop Doing {title} Wrong",
            ]
        if len(prompts) < 2:
            prompts = [
                f"High-contrast minimalist tech diagram about {title[:30]}",
                f"Neon glowing terminal window with warning text for {title[:30]}",
            ]

        return {
            "ok": True,
            "original_title": title,
            "titles": [value[:70] for value in titles[:3]],
            "thumbnail_prompts": prompts[:2],
        }

    except Exception as e:
        logger.warning(f"Rescue pack generation fell back to heuristic variants: {e}")
        # Fallback heuristic variants if LLM parsing fails
        return {
            "ok": True,
            "original_title": title,
            "titles": [
                f"Why 99% of Devs Get {title[:35]} Wrong"[:70],
                f"The Ultimate Guide to {title[:35]} in 2026"[:70],
                f"I Replaced My Stack With {title[:35]}"[:70],
            ],
            "thumbnail_prompts": [
                f"Bold neon typography of {title[:20]} with split code window",
                f"Minimalist futuristic icon of {title[:20]} on dark gradient background",
            ],
        }
