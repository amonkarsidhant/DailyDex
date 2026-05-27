#!/usr/bin/env python3
"""Smart summarizer using rules - works without heavy ML."""

import json
import re


def clean_text(text):
    """Clean and normalize text."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return text[:200]


def analyze_repo(item):
    """Generate a summary for a repo."""
    title = item.get("title", "")
    desc = item.get("description", "")
    stars = item.get("stars", "0")

    # Extract key info
    owner = title.split("/")[0] if "/" in title else ""
    repo = title.split("/")[-1] if "/" in title else title
    lang = item.get("language", "")

    # Generate smart summary
    summary_parts = [f"⭐ {stars} stars"]
    if lang:
        summary_parts.append(f"Built with {lang}")

    # Add description snippet
    if desc:
        snip = desc.split(".")[0] if "." in desc else desc
        summary_parts.append(clean_text(snip)[:80])

    return f"{owner}/{repo}: " + " • ".join(summary_parts)


def analyze_video(item):
    """Generate a summary for a video."""
    title = item.get("title", "Untitled")
    source = item.get("source", "").replace("YouTube - ", "")

    # Detect topics in title
    topics = []
    title_lower = title.lower()
    if any(w in title_lower for w in ["review", "tutorial", "guide"]):
        topics.append("How-to")
    if any(w in title_lower for w in ["announce", "release", "launch", "new"]):
        topics.append("News")
    if any(w in title_lower for w in ["vs", "comparison", "vs.", "better"]):
        topics.append("Comparison")
    if any(w in title_lower for w in ["explain", "what is", "how does"]):
        topics.append("Explainer")

    topic_str = f" [{', '.join(topics)}]" if topics else ""
    return f"📺 {source}: {title[:45]}{topic_str}"


def analyze_news(item):
    """Generate a summary for news."""
    title = item.get("title", "Untitled")
    source = item.get("source", "")

    # Detect sentiment/category
    title_lower = title.lower()
    if any(w in title_lower for w in ["launch", "release", "announce", "new"]):
        cat = "🚀"
    elif any(w in title_lower for w in ["raise", "funding", "acquire", "valuation"]):
        cat = "💰"
    elif any(w in title_lower for w in ["warning", "risk", "concern", "danger"]):
        cat = "⚠️"
    elif any(w in title_lower for w in ["research", "paper", "study"]):
        cat = "📄"
    else:
        cat = "📰"

    return f"{cat} {source}: {title[:55]}"


def generate_smart_summary(data):
    """Generate intelligent summary using rules."""
    github = data.get("github", [])[:3]
    youtube = data.get("youtube", [])[:2]
    blogs = data.get("blogs", [])[:3]
    papers = data.get("papers", [])[:1]

    # Build summary
    lines = []
    lines.append(
        "📊 " + f"{len(github)} repos • {len(blogs)} stories • {len(youtube)} videos"
    )
    lines.append("")

    # Top repo highlight
    if github:
        top = analyze_repo(github[0])
        lines.append("🔥 " + top)

    # News highlights
    if blogs:
        lines.append("")
        for b in blogs:
            lines.append(analyze_news(b))

    # Videos worth watching
    if youtube:
        lines.append("")
        for v in youtube:
            lines.append(analyze_video(v))

    return "\n".join(lines)


# Test it
if __name__ == "__main__":
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.environ.get("DATA_DIR", os.path.join(base_dir, "data"))
    data_path = os.environ.get("DATA_FILE", os.path.join(data_dir, "data.json"))
    with open(data_path) as f:
        data = json.load(f)

    summary = generate_smart_summary(data)
    print(summary)
    print("\n" + "=" * 50)
    print("Sample output ready for email!")
