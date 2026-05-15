#!/usr/bin/env python3
"""
Agentic Researcher for DailyDex - Recursive Research Edition.
Uses Gemini CLI to perform multi-stage, deep-dive technical investigations.
"""

import os
import json
import sqlite3
import subprocess
from datetime import datetime
from typing import List, Dict, Optional

# Internal imports
from data_models import IntelligenceDB, IntelligenceJSON
import llm_summary
import creator_intelligence

RESEARCH_PACK_DIR = "data/research_packs"
os.makedirs(RESEARCH_PACK_DIR, exist_ok=True)

class AgenticResearcher:
    def __init__(self):
        self.db = IntelligenceDB()
        self.json_store = IntelligenceJSON()
        
    def perform_daily_research(self, top_n: int = 2):
        """Identify top trends and perform Recursive Deep Dives."""
        print(f"[*] Starting Recursive Research session: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        # 1. Identify what's actually trending
        trends = self.db.get_trending_keywords(limit=10)
        if not trends:
            print("[!] No trends found. Falling back to default focus areas.")
            trends = [{"keyword": k} for k in ["Agentic RAG", "Model Context Protocol", "Autonomous Agents"]]
            
        research_targets = [t['keyword'] for t in trends[:top_n]]
        print(f"[*] Top research targets: {', '.join(research_targets)}")
        
        # 2. Perform Recursive Research for each target
        for target in research_targets:
            self.recursive_dive(target)
            
    def recursive_dive(self, topic: str):
        """Perform a multi-stage research dive using Gemini CLI."""
        print(f"\n[🚀] Launching Recursive Dive: {topic}")
        
        # Stage 1: Lead Extraction & Technical Core
        # We use the Gemini CLI's built-in research capabilities here
        print("[1/3] Extracting Technical Leads...")
        leads_prompt = f"""Perform initial research on '{topic}'. 
Identify the 'Recursive Leads': 
1. The primary technical framework/repo.
2. The 'Munger Inversion' (what are the risks or counter-arguments?).
3. The 'Creator Opportunity' (what demo would actually impress people?).
Output a summary of these leads."""

        leads = llm_summary.query_llm(leads_prompt, "You are a PhD-level Research Lead. Be technical and concise.")
        
        # Stage 2: Deep Synthesis & Content Strategy
        print("[2/3] Performing Deep Synthesis via Gemini CLI...")
        synthesis_prompt = f"""Based on these research leads for '{topic}':
{leads}

Generate a 'Gold' Content Brief.
Focus on 'Contextual Sovereignty' and 'The Shift' in AI architecture.

Return a JSON object with:
- strategic_title: High-CTR technical title.
- shift: Why this matters fundamentally.
- superpower: The unique technical edge.
- hook_contrarian: A hook that challenges a common belief.
- hook_speed: A hook about saving time/complexity.
- narrative_beats: 5 logical points for a deep-dive script.
- thumbnail_visuals: 3 visual cues for a high-performing thumbnail.
- inversion: The critical risk or limitation (Munger Inversion).

Output MUST be valid JSON."""

        brief_json_raw = llm_summary.query_llm(synthesis_prompt, "You are a Senior AI Content Strategist.")
        
        # Stage 3: Persistence (Research Pack & DB)
        print("[3/3] Finalizing Research Pack...")
        if brief_json_raw:
            try:
                if "{" in brief_json_raw and "}" in brief_json_raw:
                    json_str = brief_json_raw[brief_json_raw.find("{"):brief_json_raw.rfind("}")+1]
                    brief = json.loads(json_str)
                    
                    # Save Research Pack (Markdown)
                    self._save_research_pack(topic, leads, brief)
                    
                    # Save Brief to Pipeline (DB)
                    self._save_brief_to_pipeline(topic, brief)
                    print(f"[✅] Recursive Dive Complete for {topic}")
            except Exception as e:
                print(f"[!] Recursive Dive Failed for {topic}: {e}")

    def _save_research_pack(self, topic: str, leads: str, brief: Dict):
        """Save a persistent Markdown research pack."""
        date_slug = datetime.now().strftime("%Y-%m-%d")
        file_slug = topic.lower().replace(" ", "-")
        filename = f"{date_slug}-{file_slug}.md"
        path = os.path.join(RESEARCH_PACK_DIR, filename)
        
        content = f"""# Research Pack: {topic}
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Status:** Recursive Synthesis Complete

## 🔍 Initial Leads (Stage 1)
{leads}

## 💡 Strategic Brief (Stage 2)
### The Shift
{brief.get('shift')}

### Technical Superpower
{brief.get('superpower')}

### Munger Inversion (Critical Risk)
{brief.get('inversion')}

## 🎬 Production Strategy
**Strategic Title:** {brief.get('strategic_title')}

**Narrative Beats:**
{chr(10).join([f'- {b}' for b in brief.get('narrative_beats', [])])}

**Hooks:**
- **Contrarian:** {brief.get('hook_contrarian')}
- **Speed-to-Value:** {brief.get('hook_speed')}

**Thumbnail Concepts:**
- {chr(10).join(brief.get('thumbnail_visuals', []))}
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _save_brief_to_pipeline(self, topic: str, brief: Dict):
        """Inject the synthesized brief into the creator pipeline."""
        item = {
            "title": brief.get("strategic_title", f"Recursive Dive: {topic}"),
            "url": f"https://dailydex.internal/research/{topic.lower().replace(' ', '-')}",
            "source": "Recursive Researcher",
            "source_type": "research",
            "category": "Recursive Synthesis",
            "signal_score": 95,
            "creator_score": 98,
            "pipeline_type": "creator",
            "status": "idea",
            "working_title": brief.get("strategic_title"),
            "hook": brief.get("hook_contrarian"),
            "format": "Deep Dive Video",
            "outline": json.dumps(brief.get("narrative_beats", [])),
            "thumbnail_text": ", ".join(brief.get("thumbnail_visuals", [])),
            "notes": f"SHIFT: {brief.get('shift')} | INVERSION: {brief.get('inversion')}",
            "tags": json.dumps(["recursive", topic.lower()]),
            "created_at": datetime.now().isoformat()
        }
        self.db.save_item(item)

if __name__ == "__main__":
    researcher = AgenticResearcher()
    researcher.perform_daily_research()
