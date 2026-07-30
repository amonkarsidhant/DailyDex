"""Retention & Hook Analysis Engine (DailyDex Phase 2 - Gap 8).

Analyzes video opening hooks and scripts to identify retention drop-off risks,
categorizes hook strategy, and suggests high-retention structural improvements.
"""

import re
from typing import Dict, List, Any


def analyze_hook(hook_text: str) -> Dict[str, Any]:
    """Analyze opening hook (first 15-30 seconds of script/Short) for retention strength."""
    clean = hook_text.strip()
    words = clean.split()
    word_count = len(words)

    score = 60
    hook_type = "Standard Declarative"
    strengths = []
    risks = []

    # Detect hook pattern
    lower = clean.lower()
    if "?" in clean or lower.startswith(("why ", "what if ", "did you know ", "how ")):
        hook_type = "Curiosity Question"
        score += 15
        strengths.append("Opens with a curiosity question that creates an open loop")
    elif any(w in lower for w in ("never ", "stop ", "don't ", "mistake", "warning")):
        hook_type = "Contrarian / Warning"
        score += 18
        strengths.append("Uses loss aversion / contrarian hook to command immediate attention")
    elif any(w in lower for w in ("i spent ", "i tested ", "for 30 days", "i built ")):
        hook_type = "Personal Experiment / Story"
        score += 16
        strengths.append("Establishes authentic first-person stakes and empirical proof")
    elif re.search(r'\b\d+%\b|\$\d+', clean):
        hook_type = "Surprising Statistic"
        score += 14
        strengths.append("Leads with hard data / numbers to ground the premise")

    # Word count check (ideally under 25 words for the first hook sentence)
    first_sentence = clean.split(".")[0]
    first_sentence_words = len(first_sentence.split())
    if first_sentence_words <= 18:
        score += 10
        strengths.append("Opening sentence is punchy and fast-paced (<=18 words)")
    elif first_sentence_words > 28:
        score -= 12
        risks.append("Opening sentence is overly long (>28 words); viewers drop off during rambling intros")

    # Fluff detection ("Hey guys", "Welcome back", "In today's video")
    fluff_phrases = ["hey guys", "welcome back", "in today's video", "without further ado", "don't forget to subscribe"]
    found_fluff = [f for f in fluff_phrases if f in lower]
    if found_fluff:
        score -= 25
        risks.append(f"Contains slow YouTube intro fluff: '{found_fluff[0]}'. Cut directly to the hook!")

    final_score = max(10, min(99, score))

    return {
        "hook_text": clean,
        "hook_type": hook_type,
        "retention_score": final_score,
        "strengths": strengths,
        "risks": risks
    }
