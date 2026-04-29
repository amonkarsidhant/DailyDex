#!/usr/bin/env python3
"""Signal Scoring Engine for DailyDex"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Focus areas configuration
DEFAULT_FOCUS_AREAS = [
    "agentic AI", "coding agents", "open-source LLMs", "local LLMs", 
    "Ollama", "Raspberry Pi AI", "lightweight models", "AI engineering tools",
    "model evaluation", "RAG", "AI infrastructure", "developer productivity",
    "self-hosted AI", "code generation", "code review", "agent workflows",
    "tool calling", "multi-agent", "autonomous agents", "browser automation",
    "CLI agents", "sandboxing", "evals", "benchmarking"
]

# Blocked keywords
BLOCKED_KEYWORDS = [
    "nsfw", "porn", "sex", "成人", "casino", "spam", "scam", "crypto scam",
    "download crypto", "free bitcoin", "buy followers", "fake reviews"
]

# Category keywords mapping
CATEGORY_KEYWORDS = {
    "model": ["model", "LLM", "GPT", "Claude", "Gemini", "Mistral", "Qwen", "DeepSeek", "Llama", "Phi"],
    "agent": ["agent", "autonomous", "agentic", "workflow", "tool calling", "function calling", "mcp"],
    "open-source": ["open source", "opensource", "apache", "MIT", "GPL", "huggingface", "github"],
    "research": ["paper", "arxiv", "research", "benchmark", "evaluation", "paper with code"],
    "regulation": ["regulation", "government", "EU AI Act", "policy", "law", "compliance"],
    "product": ["product", "launch", "release", "announce", "new feature", "beta"],
    "infrastructure": ["infrastructure", "API", "cloud", "deployment", "serving", "optimization", "inference"],
    "safety": ["safety", "alignment", "jailbreak", "red team", "security", "guardrail"],
    "coding": ["coding", "code", "developer", "programming", "repository", "repo"],
    "local": ["local", "raspberry pi", "ollama", "lm studio", "llama.cpp", "self-hosted", "edge"]
}

# Signal scoring weights
SCORING_WEIGHTS = {
    "recency_days_max": 7,
    "star_growth_weight": 0.25,
    "popularity_weight": 0.15,
    "recency_weight": 0.20,
    "agentic_relevance_weight": 0.15,
    "local_relevance_weight": 0.10,
    "developer_productivity_weight": 0.10,
    "pi_suitability_weight": 0.05
}


class SignalScorer:
    def __init__(self, config: Optional[Dict] = None, variant_info: Optional[Dict] = None):
        self.config = config or {}
        self.variant_info = variant_info or {}
        
        variant_keywords = self.variant_info.get("focus_keywords", [])
        if variant_keywords:
            self.focus_areas = variant_keywords
        else:
            self.focus_areas = self.config.get("focus_areas", DEFAULT_FOCUS_AREAS)
        
        self.blocked_keywords = self.config.get("blocked_keywords", BLOCKED_KEYWORDS)
        self.scoring_weights = self.config.get("scoring_weights", SCORING_WEIGHTS)
        
    def is_blocked(self, text: str) -> bool:
        """Check if content contains blocked keywords"""
        text_lower = text.lower()
        return any(blocked in text_lower for blocked in self.blocked_keywords)
    
    def calculate_recency_score(self, date_str: str) -> float:
        """Calculate recency score (0-100) based on date"""
        try:
            # Try parsing various date formats
            date = None
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d %b %Y", "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    date = datetime.strptime(date_str.replace("Z", "+00:00")[:19], fmt)
                    break
                except:
                    continue
            
            if not date:
                return 50  # Default middle score
            
            days_ago = (datetime.now() - date).days
            max_days = self.scoring_weights["recency_days_max"]
            
            if days_ago <= 1:
                return 100
            elif days_ago <= 3:
                return 90
            elif days_ago <= 7:
                return 70
            elif days_ago <= 14:
                return 50
            elif days_ago <= 30:
                return 30
            else:
                return 10
        except:
            return 50
    
    def calculate_popularity_score(self, stars: str) -> float:
        """Calculate popularity score from star count"""
        try:
            stars_clean = stars.replace(",", "").replace("K", "000").replace("M", "000000")
            stars_int = int(stars_clean)
            
            if stars_int >= 50000:
                return 100
            elif stars_int >= 10000:
                return 80
            elif stars_int >= 5000:
                return 60
            elif stars_int >= 1000:
                return 40
            elif stars_int >= 100:
                return 20
            else:
                return 10
        except:
            return 30
    
    def calculate_keyword_match_score(self, text: str) -> float:
        """Calculate score based on focus area keywords"""
        text_lower = text.lower()
        matches = 0
        
        # Check exact matches
        for area in self.focus_areas:
            if area.lower() in text_lower:
                matches += 1
        
        # Also check partial matches and related terms
        related_terms = ["ai", "llm", "gpt", "model", "agent", "code", "open", "local", "raspberry", "pi", "docker", "cli", "tool", "automation", "eval", "benchmark", "rag", "embedding", "inference", "serving", "api"]
        for term in related_terms:
            if term in text_lower:
                matches += 0.5
        
        # Normalize to 0-100 - more generous
        return min(100, matches * 8)
    
    def detect_category(self, text: str) -> List[str]:
        """Detect categories based on keywords"""
        text_lower = text.lower()
        categories = []
        
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(kw.lower() in text_lower for kw in keywords):
                categories.append(category)
        
        return categories[:3] if categories else ["general"]
    
    def calculate_agentic_relevance(self, text: str, tags: List[str]) -> float:
        """Calculate agentic workflow relevance (0-100)"""
        text_lower = (text + " " + " ".join(tags)).lower()
        
        agentic_keywords = [
            "agent", "autonomous", "tool", "function", "mcp", "workflow",
            "automation", "cli", "browser", "sandbox", "eval", "benchmark",
            "code execution", "shell", "terminal", "api call", "web scraping"
        ]
        
        matches = sum(1 for kw in agentic_keywords if kw in text_lower)
        return min(100, matches * 15)
    
    def calculate_local_relevance(self, text: str, tags: List[str]) -> float:
        """Calculate local/Raspberry Pi suitability (0-100)"""
        text_lower = (text + " " + " ".join(tags)).lower()
        
        local_keywords = [
            "raspberry pi", "ollama", "llama.cpp", "lm studio", "local",
            "self-hosted", "edge", "docker", "lightweight", "small model",
            "3b", "7b", "8b", "quantized", "arm64", "aarch64"
        ]
        
        matches = sum(1 for kw in local_keywords if kw in text_lower)
        return min(100, matches * 15)
    
    def calculate_pi_suitability(self, text: str, tags: List[str]) -> str:
        """Determine Raspberry Pi suitability"""
        text_lower = (text + " " + " ".join(tags)).lower()
        
        if any(kw in text_lower for kw in ["raspberry pi", "ollama", "arm64", "aarch64", "docker"]):
            return "yes"
        elif any(kw in text_lower for kw in ["3b", "7b", "1b", "2b", "small", "lightweight", "quantized"]):
            return "partial"
        else:
            return "no"
    
    def calculate_installation_complexity(self, text: str, description: str) -> str:
        """Estimate installation complexity"""
        combined = (text + " " + description).lower()
        
        if any(kw in combined for kw in ["pip install", "npm install", "docker run", "one command", "one-click"]):
            return "easy"
        elif any(kw in combined for kw in ["docker compose", "kubernetes", "complex setup", "multiple steps"]):
            return "hard"
        else:
            return "medium"
    
    def score_github_repo(self, repo: Dict) -> Dict:
        """Score a GitHub repository"""
        if self.is_blocked(repo.get("title", "") + " " + repo.get("description", "")):
            return {**repo, "signal_score": 0, "action": "ignore", "categories": []}
        
        title = repo.get("title", "")
        description = repo.get("description", "")
        stars = repo.get("stars", "0")
        
        # Calculate component scores
        recency_score = self.calculate_recency_score(repo.get("published", ""))
        popularity_score = self.calculate_popularity_score(stars)
        keyword_score = self.calculate_keyword_match_score(title + " " + description)
        agentic_score = self.calculate_agentic_relevance(description, repo.get("tags", []))
        local_score = self.calculate_local_relevance(description, repo.get("tags", []))
        
        # Calculate final weighted score with bonus for general AI relevance
        base_score = (
            recency_score * self.scoring_weights["recency_weight"] +
            popularity_score * self.scoring_weights["popularity_weight"] +
            keyword_score * 0.3 +
            agentic_score * self.scoring_weights["agentic_relevance_weight"] +
            local_score * self.scoring_weights["local_relevance_weight"]
        )
        
        # Boost for AI-related keywords
        ai_boost = 0
        text_lower = (title + " " + description).lower()
        ai_terms = ["ai", "llm", "gpt", "model", "agent", "gemma", "qwen", "llama", "mistral", "claude", "openai", "anthropic", "deepseek"]
        for term in ai_terms:
            if term in text_lower:
                ai_boost += 10
        
        signal_score = min(100, int(base_score + ai_boost))
        
        # Determine action and label based on score
        if signal_score >= 80:
            action = "try"
            score_label = "Hot"
        elif signal_score >= 60:
            action = "save"
            score_label = "Worth Watching"
        elif signal_score >= 40:
            action = "read"
            score_label = "Interesting"
        else:
            action = "ignore"
            score_label = "Low Priority"
        
        # Detect categories
        categories = self.detect_category(title + " " + description)
        
        # Calculate Pi suitability
        pi_suitability = self.calculate_pi_suitability(description, repo.get("tags", []))
        installation = self.calculate_installation_complexity(title, description)
        
        return {
            **repo,
            "signal_score": signal_score,
            "score_label": score_label,
            "score_reason": self._generate_why(recency_score, popularity_score, agentic_score, local_score, keyword_score, ai_boost),
            "action": action,
            "categories": categories,
            "agentic_relevance": agentic_score,
            "local_ai_relevance": local_score,
            "pi_suitability": pi_suitability,
            "installation_complexity": installation,
            "score_breakdown": {
                "recency": recency_score,
                "popularity": popularity_score,
                "growth": min(100, int((popularity_score + agentic_score) / 2)),
                "agentic": agentic_score,
                "local": local_score,
                "relevance": keyword_score,
                "pi_suitability": 50 if pi_suitability in ["yes", "partial"] else 20,
                "developer_productivity": min(100, int((agentic_score + keyword_score) / 2)),
                "trust": 80 if repo.get("stars", "0") != "0" else 40
            }
        }
    
    def _generate_why(self, recency, popularity, agentic, local, relevance, boost) -> str:
        """Generate human-readable explanation of score"""
        reasons = []
        if recency >= 80:
            reasons.append("recent")
        if popularity >= 60:
            reasons.append("popular")
        if agentic >= 40:
            reasons.append("agentic")
        if local >= 40:
            reasons.append("local runnable")
        if relevance >= 50:
            reasons.append("relevant")
        if boost > 0:
            reasons.append("AI boost")
        
        return "+".join(reasons[:4]) if reasons else "baseline"
    
    def _get_score_label(self, score: int) -> str:
        """Get score label based on signal score"""
        if score >= 80:
            return "Hot"
        elif score >= 60:
            return "Worth Watching"
        elif score >= 40:
            return "Interesting"
        return "Low Priority"

    def score_model(self, model: Dict) -> Dict:
        """Score a HuggingFace model"""
        title = model.get("title", "")
        
        if self.is_blocked(title):
            return {**model, "signal_score": 0, "action": "ignore", "categories": []}
        
        downloads = model.get("downloads", 0)
        
        # Popularity based on downloads
        if downloads > 100000000:
            popularity_score = 100
        elif downloads > 10000000:
            popularity_score = 80
        elif downloads > 1000000:
            popularity_score = 60
        elif downloads > 100000:
            popularity_score = 40
        else:
            popularity_score = 20
        
        keyword_score = self.calculate_keyword_match_score(title)
        agentic_score = 20 if any(kw in title.lower() for kw in ["agent", "tool", "function", "mcp"]) else 10
        
        # Check for local/ollama compatibility
        is_local = "ollama" in title.lower() or "llama.cpp" in title.lower() or "lmstudio" in title.lower()
        
        # Check for coding capability
        is_coding = any(kw in title.lower() for kw in ["code", "coder", "codex", "deepseek-coder"])
        
        # Check size
        is_small = any(size in title.lower() for size in ["1b", "2b", "3b", "7b", "8b"])
        
        signal_score = int(popularity_score * 0.4 + keyword_score * 0.4 + (is_local * 20) + (is_coding * 10))
        signal_score = min(100, signal_score)
        
        if signal_score >= 80:
            action = "try"
        elif signal_score >= 60:
            action = "save"
        else:
            action = "read"
        
        categories = self.detect_category(title)
        
        return {
            **model,
            "signal_score": signal_score,
            "score_label": self._get_score_label(signal_score),
            "action": action,
            "categories": categories,
            "is_local_compatible": is_local,
            "is_coding_model": is_coding,
            "is_small": is_small,
            "score_breakdown": {
                "recency": 50,
                "popularity": min(100, int(downloads / 1000000)),
                "growth": min(100, int(downloads / 100000)),
                "agentic": agentic_score,
                "local": 100 if is_local else 0,
                "relevance": keyword_score,
                "pi_suitability": 80 if is_local else 20,
                "developer_productivity": 80 if is_coding else 50,
                "trust": 80
            },
            "score_reason": f"Popular model with {downloads:,} downloads" if downloads > 100000 else "Emerging model"
        }
    
    def score_video(self, video: Dict) -> Dict:
        """Score a YouTube video"""
        title = video.get("title", "")
        description = video.get("description", "")
        
        if self.is_blocked(title):
            return {**video, "signal_score": 0, "action": "ignore", "categories": []}
        
        keyword_score = self.calculate_keyword_match_score(title + " " + description)
        agentic_score = self.calculate_agentic_relevance(description, video.get("tags", []))
        
        # Watch priority based on keywords
        watch_priority = "high"
        if any(kw in (title + description).lower() for kw in ["tutorial", "demo", "hands-on", "review"]):
            watch_priority = "high"
        elif any(kw in (title + description).lower() for kw in ["news", "announcement", "launch"]):
            watch_priority = "medium"
        else:
            watch_priority = "low"
        
        signal_score = int(keyword_score * 0.5 + agentic_score * 0.3 + (watch_priority == "high" and 30 or 0))
        signal_score = min(100, signal_score)
        
        if signal_score >= 80:
            action = "save"
        elif signal_score >= 60:
            action = "read"
        else:
            action = "ignore"
        
        return {
            **video,
            "signal_score": signal_score,
            "score_label": self._get_score_label(signal_score),
            "action": action,
            "watch_priority": watch_priority,
            "categories": self.detect_category(title + " " + description),
            "score_breakdown": {
                "recency": 50,
                "popularity": 50,
                "growth": 50,
                "agentic": agentic_score,
                "local": 0,
                "relevance": keyword_score,
                "pi_suitability": 0,
                "developer_productivity": 30,
                "trust": 80
            },
            "score_reason": f"{watch_priority} priority video on relevant topic"
        }
    
    def score_news(self, news: Dict) -> Dict:
        """Score a news article"""
        title = news.get("title", "")
        description = news.get("description", "")
        
        if self.is_blocked(title):
            return {**news, "signal_score": 0, "action": "ignore", "categories": []}
        
        keyword_score = self.calculate_keyword_match_score(title + " " + description)
        
        # Impact level estimation
        impact = "medium"
        if any(kw in title.lower() for kw in ["breaking", "major", "launch", "announcement", "gpt-5", "claude 4"]):
            impact = "critical"
        elif any(kw in title.lower() for kw in ["update", "release", "new feature", "research"]):
            impact = "high"
        
        signal_score = int(keyword_score * 0.6 + (impact == "critical" and 40 or impact == "high" and 20 or 0))
        signal_score = min(100, signal_score)
        
        if signal_score >= 70:
            action = "read"
        elif signal_score >= 40:
            action = "save"
        else:
            action = "ignore"
        
        return {
            **news,
            "signal_score": signal_score,
            "score_label": self._get_score_label(signal_score),
            "action": action,
            "impact": impact,
            "categories": self.detect_category(title),
            "score_breakdown": {
                "recency": 50,
                "popularity": 50,
                "growth": 50,
                "agentic": 20,
                "local": 0,
                "relevance": keyword_score,
                "pi_suitability": 0,
                "developer_productivity": 30,
                "trust": 70
            },
            "score_reason": f"{impact} impact news on AI topic"
        }
    
    def score_paper(self, paper: Dict) -> Dict:
        """Score an arXiv paper"""
        title = paper.get("title", "")
        
        if self.is_blocked(title):
            return {**paper, "signal_score": 0, "action": "ignore", "categories": []}
        
        keyword_score = self.calculate_keyword_match_score(title)
        
        # Check for code availability in title, abstract, and links
        abstract = paper.get("abstract", "")
        pdf_url = paper.get("pdf_url", "")
        text_to_check = f"{title} {abstract} {pdf_url}".lower()
        has_code = any(kw in text_to_check for kw in ["github", "code", "implementation", "codebase", "repository"])
        
        # Estimate reproducibility
        reproducibility = "high" if has_code else "medium" if abstract and len(abstract) > 200 else "low"
        
        # Estimate practical usefulness
        usefulness_keywords = ["agent", "tool", "framework", "library", "benchmark", "dataset", "model", "system", "deployment"]
        practical_usefulness = "high" if any(kw in text_to_check for kw in usefulness_keywords) else "medium"
        
        signal_score = int(keyword_score * 0.7 + (has_code and 30 or 0))
        signal_score = min(100, signal_score)
        
        if signal_score >= 80:
            action = "read"
            recommendation = "read deeply"
        elif signal_score >= 50:
            action = "save"
            recommendation = "skim"
        else:
            action = "ignore"
            recommendation = "ignore"
        
        return {
            **paper,
            "signal_score": signal_score,
            "score_label": self._get_score_label(signal_score),
            "action": action,
            "recommendation": recommendation,
            "has_code": has_code,
            "practical_usefulness": practical_usefulness,
            "reproducibility_estimate": reproducibility,
            "categories": self.detect_category(title),
            "score_breakdown": {
                "recency": 50,
                "popularity": 30,
                "growth": 30,
                "agentic": 20,
                "local": 0,
                "relevance": keyword_score,
                "pi_suitability": 0,
                "developer_productivity": 30 if has_code else 10,
                "trust": 80
            },
            "score_reason": f"{recommendation} - {'Has code' if has_code else 'No code'} - {practical_usefulness} usefulness"
        }
    
    def score_all_items(self, data: Dict) -> Dict:
        """Score all items in the data dictionary"""
        scored_data = {
            "last_updated": data.get("last_updated"),
            "scored_at": datetime.now().isoformat()
        }
        
        # Score each category
        if "github" in data:
            scored_data["github"] = [self.score_github_repo(repo) for repo in data["github"]]
        
        if "huggingface" in data:
            scored_data["huggingface"] = [self.score_model(model) for model in data["huggingface"]]
        
        if "youtube" in data:
            scored_data["youtube"] = [self.score_video(video) for video in data["youtube"]]
        
        if "blogs" in data:
            scored_data["blogs"] = [self.score_news(blog) for blog in data["blogs"]]
        
        if "papers" in data:
            scored_data["papers"] = [self.score_paper(paper) for paper in data["papers"]]
        
        return scored_data
    
    def generate_executive_brief(self, scored_data: Dict) -> Dict:
        """Generate the daily executive brief"""
        all_items = []
        
        # Collect all scored items
        for category, items in scored_data.items():
            if category in ["github", "huggingface", "youtube", "blogs", "papers"]:
                for item in items:
                    all_items.append({**item, "source_type": category})
        
        # Filter to high-signal items (lowered from 60 to 40 for more items)
        high_signal = [item for item in all_items if item.get("signal_score", 0) >= 40]
        high_signal.sort(key=lambda x: x.get("signal_score", 0), reverse=True)
        
        # Take top 5
        top_5 = high_signal[:5]
        
        brief_items = []
        for item in top_5:
            # Generate one-liner summary
            title = item.get("title", "")
            score = item.get("signal_score", 0)
            action = item.get("action", "read")
            categories = item.get("categories", [])
            
            # Generate action recommendation
            if action == "try":
                recommendation = "Try this weekend - test locally"
            elif action == "save":
                recommendation = "Save for research later"
            elif action == "read":
                recommendation = "Read for context"
            else:
                recommendation = "Monitor"
            
            brief_items.append({
                "title": title[:100],
                "signal_score": score,
                "action": action,
                "categories": categories,
                "recommendation": recommendation,
                "source": item.get("source_type", "unknown"),
                "url": item.get("url", "")
            })
        
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat(),
            "items": brief_items,
            "total_high_signal": len(high_signal)
        }


def load_config(config_path: str = None) -> Dict:
    """Load configuration from file or use defaults"""
    if config_path and os.path.exists(config_path):
        with open(config_path) as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    # Test the scorer
    scorer = SignalScorer()
    
    # Test with sample data
    sample_github = {
        "title": "OpenClaw/awesome-coding-agents",
        "description": "A curated list of awesome coding agents and autonomous AI tools",
        "stars": "15,000",
        "language": "Python",
        "url": "https://github.com/example/repo"
    }
    
    scored = scorer.score_github_repo(sample_github)
    print("Sample GitHub repo scored:", scored.get("signal_score"))
    print("Action:", scored.get("action"))
    print("Categories:", scored.get("categories"))