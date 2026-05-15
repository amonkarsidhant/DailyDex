#!/usr/bin/env python3
"""LLM-powered summary and enrichment using Ollama or Gemini CLI."""

import json
import requests
import os
import subprocess

# Configuration
PROVIDER = os.environ.get("LLM_PROVIDER", "gemini") # Default to gemini
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "minimax-m2.5:cloud")

def query_gemini_cli(prompt, system_prompt=None):
    """Query the Gemini CLI tool for high-quality synthesis."""
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
    try:
        # Use headless mode with JSON output
        result = subprocess.run(
            ["gemini", "--prompt", full_prompt, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=180
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"Gemini CLI Error: {e}")
    return None

def query_ollama(prompt, system_prompt=None):
    """Generic helper to query Ollama"""
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"max_tokens": 500, "temperature": 0.3},
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "").strip()
    except Exception as e:
        print(f"Ollama Error: {e}")
    return None

def query_llm(prompt, system_prompt=None):
    """Route to the configured provider."""
    if PROVIDER == "gemini":
        return query_gemini_cli(prompt, system_prompt)
    return query_ollama(prompt, system_prompt)

def get_ollama_summary(data):
    """Generate global summary for the daily brief."""
    github = data.get("github", [])[:3]
    blogs = data.get("blogs", [])[:3]

    repo_info = "\n".join([f"- {r['title']}" for r in github])
    news_info = "\n".join([f"- {b['title']}" for b in blogs])

    prompt = f"""Write 2 sentences about today's AI news:
Trending: {repo_info}
News: {news_info}
Brief summary:"""

    summary = query_llm(prompt)
    if summary:
        summary = summary.replace("\n", " ").strip()
        if len(summary) > 160:
            summary = summary[:160] + "..."
        return summary

    return f"{len(github)} repos • {len(blogs)} stories"

def get_item_enrichment(item):
    """Generate high-quality strategic synthesis for a content creator."""
    title = item.get("title", "")
    description = item.get("description", item.get("abstract", ""))
    source = item.get("source", "")
    
    system_prompt = """You are a Senior AI Content Strategist for a top-tier tech channel. 
Your job is to transform raw technical data into a 'Content Goldmine'. 
Avoid generic 'AI' fluff. Be specific, technical, and slightly opinionated.

Analyze the provided item and return a JSON object with:
- the_shift: (1 sentence) What is fundamentally changing because of this? Why does it matter *now*?
- the_edge: (1 sentence) What is the unique technical 'superpower' here? 
- hooks: 3 high-retention hooks:
    1. 'The Contrarian' (Challenges common belief)
    2. 'The Speed-to-Value' (How it saves time)
    3. 'The Visionary' (The 1-year future impact)
- narrative_beats: A list of 4 logical beats for a video or thread.
- tags: 3 specific, low-noise tags.

Output MUST be valid JSON."""

    prompt = f"SOURCE: {source}\nTITLE: {title}\nDESC: {description}\n\nSynthesize the 'Signal':"
    
    response_text = query_llm(prompt, system_prompt)
    if response_text:
        try:
            if "{" in response_text and "}" in response_text:
                json_str = response_text[response_text.find("{"):response_text.rfind("}")+1]
                data = json.loads(json_str)
                return {
                    "insight": f"{data.get('the_shift')} {data.get('the_edge')}",
                    "hooks": data.get("hooks", []),
                    "outline": data.get("narrative_beats", []),
                    "tags": data.get("tags", [])
                }
        except:
            pass
    
    return {
        "insight": "High-signal development identified in the AI landscape.",
        "hooks": [f"Why {title} is a game changer.", "The technical edge you missed.", "Where this is going."],
        "outline": ["The Problem", "The Solution", "The Practical Test", "The Verdict"],
        "tags": ["AI", source]
    }

def generate_production_assets(research_data: str):
    """Synthesize multi-format content assets from research context."""
    system_prompt = """You are an Elite Content Production House. 
Your goal is to repurpose a single technical 'Research Pack' into 5 high-impact formats.

For each format, be technical, creative, and optimized for the platform:
1. YouTube Shorts (60s): Use [Visual] and [Audio] cues. High retention.
2. Podcast Script (5 min): A 'Host A' and 'Host B' technical dialogue. Natural chemistry.
3. LinkedIn Post: Professional, technical, bullet-pointed, with a clear takeaway.
4. Technical Blog: A 'How-to' or 'State of the Art' structured outline.
5. The Demo Guide: Step-by-step visual walkthrough to show the tool in action.

Output MUST be a JSON object with keys: shorts_script, podcast_script, linkedin_post, blog_outline, demo_guide."""

    prompt = f"RESEARCH PACK CONTEXT:\n{research_data}\n\nForge the production assets:"
    
    response = query_llm(prompt, system_prompt)
    if response:
        try:
            if "{" in response and "}" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
                return json.loads(json_str)
        except:
            pass
    return None

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.environ.get("DATA_DIR", os.path.join(base_dir, "data"))
    data_path = os.environ.get("DATA_FILE", os.path.join(data_dir, "data.json"))
    
    if os.path.exists(data_path):
        with open(data_path) as f:
            data = json.load(f)
        summary = get_ollama_summary(data)
        print("Summary:", summary)
