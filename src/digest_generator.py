#!/usr/bin/env python3
"""Daily Digest Generator for DailyDex"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any
from scoring_engine import SignalScorer
from data_models import IntelligenceJSON, IntelligenceDB
import creator_intelligence

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DATA_FILE = os.environ.get("DATA_FILE", os.path.join(DATA_DIR, "data.json"))
CONFIG_TOPICS_FILE = os.environ.get("CONFIG_PATH", os.path.join(BASE_DIR, "config", "topics.json"))


class DailyDigestGenerator:
    """Generate daily markdown digests"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = CONFIG_TOPICS_FILE
        self.config_path = config_path
        self.scorer = self._load_scorer()
        self.json_store = IntelligenceJSON()
        self.db = IntelligenceDB()
    
    def _load_scorer(self) -> SignalScorer:
        """Load scoring configuration"""
        try:
            with open(self.config_path) as f:
                config = json.load(f)
            return SignalScorer(config)
        except Exception:
            return SignalScorer()
    
    def generate_digest(self, data: Dict, date: str = None) -> str:
        """Generate the daily markdown digest"""
        date = date or datetime.now().strftime("%Y-%m-%d")
        
        # 1. Score all items
        scored_data = self.scorer.score_all_items(data)
        
        # 2. Enrich with Creator Intelligence
        scored_data = creator_intelligence.enrich_scored_data_with_creator_fields(scored_data)
        
        # 3. LLM Enrichment for high-signal items
        for source_type, items in scored_data.items():
            if source_type in ["github", "huggingface", "youtube", "blogs", "papers", "hackernews"]:
                for i in range(len(items)):
                    # Only enrich top 3 items per source to save tokens/time
                    if i < 3 and (items[i].get("signal_score", 0) >= 60 or items[i].get("creator_score", 0) >= 60):
                        items[i] = creator_intelligence.enrich_with_llm_intelligence(items[i])
                        # Save to database if it's high signal
                        self.db.save_item({**items[i], "source_type": source_type})
        
        # 4. Generate executive brief
        brief = self.scorer.generate_executive_brief(scored_data)
        
        # 5. Build markdown
        digest = self._build_markdown(date, scored_data, brief)
        
        # 6. Save digest
        self.json_store.save_daily_digest(date, digest)
        
        return digest
    
    def _build_markdown(self, date: str, scored_data: Dict, brief: Dict) -> str:
        """Build the markdown content"""
        lines = []
        
        # Header
        lines.append(f"# DailyDex Daily Brief - {date}")
        lines.append("")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")
        
        # Executive Brief
        lines.append("## Today's Brief")
        lines.append("")
        
        for i, item in enumerate(brief.get("items", []), 1):
            score_emoji = "🔥" if item["signal_score"] >= 80 else "⭐" if item["signal_score"] >= 60 else "📌"
            lines.append(f"{i}. **{item['title']}** {score_emoji}")
            lines.append(f"   - Signal: {item['signal_score']}/100 | Action: {item['action']}")
            lines.append(f"   - Categories: {', '.join(item['categories'])}")
            lines.append(f"   - Recommendation: {item['recommendation']}")
            lines.append(f"   - [Source]({item['url']})")
            lines.append("")
        
        # High Signal Items
        lines.append("## High Signal Items")
        lines.append("")
        
        all_items = []
        for source_type, items in scored_data.items():
            if source_type in ["github", "huggingface", "youtube", "blogs", "papers", "hackernews"]:
                for item in items:
                    if item.get("signal_score", 0) >= 70:
                        all_items.append({**item, "source": source_type})
        
        all_items.sort(key=lambda x: x.get("signal_score", 0), reverse=True)
        
        for item in all_items[:10]:
            emoji = self._get_source_emoji(item["source"])
            lines.append(f"- {emoji} **{item.get('title', 'Untitled')[:60]}...** (Score: {item.get('signal_score', 0)})")
            lines.append(f"  - Action: {item.get('action', 'read')} | Categories: {', '.join(item.get('categories', []))}")
            if item.get("url"):
                lines.append(f"  - {item['url']}")
            lines.append("")
        
        # GitHub Trending
        lines.append("## GitHub Trending")
        lines.append("")
        
        github_items = scored_data.get("github", [])[:5]
        for repo in github_items:
            stars = repo.get("stars", "0")
            lines.append(f"- **{repo.get('title', '')}** ({stars} stars)")
            lines.append(f"  - {repo.get('description', '')[:100]}...")
            if repo.get("url"):
                lines.append(f"  - [Link]({repo['url']})")
            lines.append("")
        
        # Top Models
        lines.append("## Top Models")
        lines.append("")
        
        models = scored_data.get("huggingface", [])[:5]
        for model in models:
            downloads = model.get("downloads", 0)
            lines.append(f"- **{model.get('title', '')}**")
            lines.append(f"  - Downloads: {downloads:,} | Score: {model.get('signal_score', 0)}")
            lines.append("")
        
        # Videos to Watch
        lines.append("## Videos to Watch")
        lines.append("")
        
        videos = [v for v in scored_data.get("youtube", []) if v.get("signal_score", 0) >= 60][:3]
        for video in videos:
            lines.append(f"- **{video.get('title', '')}**")
            lines.append(f"  - Priority: {video.get('watch_priority', 'medium')} | Channel: {video.get('source', '')}")
            if video.get("url"):
                lines.append(f"  - [Watch]({video['url']})")
            lines.append("")
        
        # Research Papers
        lines.append("## Research Radar")
        lines.append("")
        
        papers = scored_data.get("papers", [])[:5]
        for paper in papers:
            lines.append(f"- **{paper.get('title', '')}**")
            lines.append(f"  - Recommendation: {paper.get('recommendation', 'skim')} | Has Code: {paper.get('has_code', False)}")
            if paper.get("url"):
                lines.append(f"  - [arXiv]({paper['url']})")
            lines.append("")
        
        # Things to Try This Weekend
        lines.append("## Things to Try This Weekend")
        lines.append("")
        
        try_items = [item for item in all_items if item.get("action") == "try" and item.get("pi_suitability") != "no"]
        for item in try_items[:3]:
            emoji = self._get_source_emoji(item["source"])
            lines.append(f"{emoji} **{item.get('title', '')[:60]}**")
            lines.append(f"   - Pi Suitability: {item.get('pi_suitability', 'unknown')}")
            lines.append(f"   - Setup: {item.get('installation_complexity', 'medium')}")
            if item.get("url"):
                lines.append(f"   - {item['url']}")
            lines.append("")
        
        # Strategic Takeaway
        lines.append("## Strategic Takeaway")
        lines.append("")
        
        if brief.get("items"):
            top_item = brief["items"][0]
            lines.append(f"Today: *{top_item.get('title', 'No major updates')[:80]}*")
            lines.append(f"Focus: {top_item.get('recommendation', 'Continue monitoring')}")
        else:
            lines.append("Today: No major high-signal updates. Continue regular monitoring.")
        
        lines.append("")
        lines.append("---")
        lines.append("*End of Daily Brief*")
        
        return "\n".join(lines)
    
    def _get_source_emoji(self, source: str) -> str:
        """Get emoji for source type"""
        mapping = {
            "github": "🔧",
            "huggingface": "🤗",
            "youtube": "📺",
            "blogs": "📰",
            "papers": "📄",
            "hackernews": "🧡"
        }
        return mapping.get(source, "📌")
    
    def get_digest(self, date: str) -> str:
        """Get a specific digest"""
        return self.json_store.get_daily_digest(date)
    
    def list_digests(self) -> List[str]:
        """List available digests"""
        return self.json_store.list_digests()


def generate_daily_digest(data_path: str = None):
    """Main function to generate daily digest"""
    if data_path is None:
        data_path = DATA_FILE
    with open(data_path) as f:
        data = json.load(f)
    
    # Generate digest
    generator = DailyDigestGenerator()
    digest = generator.generate_digest(data)
    
    return digest


if __name__ == "__main__":
    digest = generate_daily_digest()
    print(digest[:500] + "...")
