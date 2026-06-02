#!/usr/bin/env python3
"""Agentic Researcher for DailyDex.

This module is the "strategy brain" that sits on top of the
``EnrichmentService`` worker. The worker handles per-item creator packs.
The researcher handles whole *topics* (clusters): it pulls leads from the
LLM, asks for a structured brief, and feeds both into the shared cluster
pipeline so the worker can save + forge them.

Public entry points:

* ``recursive_dive(topic)`` — pure function that returns a dive dict; safe
  to pass as the ``recursive_dive_fn`` argument of
  ``EnrichmentService.run_cluster_pipeline``.
* ``AgenticResearcher.run_daily_pipeline`` — convenience runner used by the
  ``/api/agentic-run`` route and the legacy CLI entry point.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import creator_intelligence
import llm_summary
from data_models import IntelligenceDB

RESEARCH_PACK_DIR = os.environ.get(
    "RESEARCH_PACK_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "research_packs"),
)
os.makedirs(RESEARCH_PACK_DIR, exist_ok=True)


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> Dict[str, Any]:
    """Best-effort JSON object extractor (the Gemini CLI sometimes wraps with prose)."""
    if not text:
        return {}
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return {}
    candidate = match.group(0)
    try:
        loaded = json.loads(candidate)
        return loaded if isinstance(loaded, dict) else {}
    except json.JSONDecodeError:
        repaired = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            loaded = json.loads(repaired)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}


def recursive_dive(topic: str) -> Dict[str, Any]:
    """Two-stage Gemini dive that returns a strategic brief for ``topic``.

    Stage 1 (leads) is a free-form synthesis; Stage 2 turns those leads into
    a structured brief that the cluster pipeline can store on the saved item
    and feed into the Production Forge.
    """
    if not topic:
        return {}

    leads_prompt = (
        f"Research the AI topic '{topic}'. Identify:\n"
        "1. The primary technical framework or repo driving this trend.\n"
        "2. The Munger Inversion: what are the risks, failure modes, or counter-arguments?\n"
        "3. The Creator Opportunity: what concrete demo would prove or disprove the hype?\n"
        "Return a concise technical summary (no preamble, no markdown headings)."
    )
    leads = llm_summary.query_llm(
        leads_prompt,
        "You are a PhD-level research lead. Be technical, terse, and source-aware.",
    ) or ""

    synthesis_prompt = (
        f"Based on these research leads for '{topic}':\n{leads}\n\n"
        "Return a JSON object with these exact keys:\n"
        "strategic_title (high-CTR technical title, 38-62 chars),\n"
        "shift (1 sentence: why this matters fundamentally),\n"
        "superpower (1 sentence: the unique technical edge),\n"
        "hook_contrarian (1 sentence),\n"
        "hook_speed (1 sentence),\n"
        "narrative_beats (array of 5 short strings),\n"
        "thumbnail_visuals (array of 3 short strings),\n"
        "inversion (1 sentence: the critical risk).\n"
        "Output JSON only. No commentary, no code fences."
    )
    raw = llm_summary.query_llm(
        synthesis_prompt,
        "You are a senior AI content strategist. Output strict JSON only.",
    ) or ""
    brief = _extract_json(raw)

    if brief:
        brief.setdefault("leads", leads)
        brief.setdefault("topic", topic)
    elif leads:
        brief = {"topic": topic, "leads": leads}
    return brief


class AgenticResearcher:
    """Glue layer between scored data, clusters, and the EnrichmentService."""

    def __init__(self, db: Optional[IntelligenceDB] = None, enrichment_service: Any = None):
        self.db = db or IntelligenceDB()
        self.enrichment_service = enrichment_service

    # -- public entry points ---------------------------------------------------

    def run_daily_pipeline(
        self,
        scored_data: Dict[str, Any],
        automation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build clusters from scored data and promote qualifying ones."""
        profile = llm_summary.load_creator_profile()
        automation = automation or profile.get("automation", {})
        clusters = creator_intelligence.build_topic_clusters(scored_data)
        if not self.enrichment_service:
            return {"ok": False, "error": "no_enrichment_service", "clusters_considered": len(clusters)}

        result = self.enrichment_service.run_cluster_pipeline(
            clusters=clusters,
            scored_data=scored_data,
            automation=automation,
            recursive_dive_fn=recursive_dive,
        )
        # Persist a markdown research pack for each successful promotion so
        # the existing research-packs tab continues to work as a paper trail.
        for promotion in result.get("promoted", []):
            topic = promotion.get("topic")
            if not topic:
                continue
            self._write_research_pack(topic)
        result["clusters_considered"] = len(clusters)
        return result

    # -- legacy CLI-style API --------------------------------------------------

    def perform_daily_research(self, top_n: int = 2) -> List[Dict[str, Any]]:
        """Legacy keyword-driven runner used by the CLI entry point."""
        trends = self.db.get_trending_keywords(limit=10) or []
        targets = [t["keyword"] for t in trends[:top_n]] or [
            "Agentic RAG", "Model Context Protocol", "Autonomous Agents",
        ]
        briefs = []
        for topic in targets:
            brief = recursive_dive(topic)
            if brief:
                briefs.append(brief)
                self._save_cli_brief(topic, brief)
        return briefs

    # -- internals -------------------------------------------------------------

    def _write_research_pack(self, topic: str) -> Optional[str]:
        brief = recursive_dive(topic)
        if not brief:
            return None
        return self._save_cli_brief(topic, brief)

    def _save_cli_brief(self, topic: str, brief: Dict[str, Any]) -> str:
        date_slug = datetime.now().strftime("%Y-%m-%d")
        file_slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") or "topic"
        path = os.path.join(RESEARCH_PACK_DIR, f"{date_slug}-{file_slug}.md")
        beats = brief.get("narrative_beats") or []
        thumbs = brief.get("thumbnail_visuals") or []
        body = [
            f"# Research Pack: {topic}",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "**Status:** Agentic Recursive Dive",
            "",
            "## Leads",
            brief.get("leads", "(no leads returned)"),
            "",
            "## Strategic Brief",
            f"**Strategic title:** {brief.get('strategic_title', '')}",
            f"**Shift:** {brief.get('shift', '')}",
            f"**Superpower:** {brief.get('superpower', '')}",
            f"**Munger Inversion:** {brief.get('inversion', '')}",
            "",
            "**Hooks:**",
            f"- Contrarian: {brief.get('hook_contrarian', '')}",
            f"- Speed-to-Value: {brief.get('hook_speed', '')}",
            "",
            "**Narrative Beats:**",
            *[f"- {beat}" for beat in beats],
            "",
            "**Thumbnail Visuals:**",
            *[f"- {visual}" for visual in thumbs],
            "",
        ]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(body))
        return path


if __name__ == "__main__":
    AgenticResearcher().perform_daily_research()
