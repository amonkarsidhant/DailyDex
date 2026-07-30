"""CTR Prediction & Pre-Publish Scoring Engine (DailyDex Phase 2 - Gap 7).

Evaluates video titles and thumbnail metadata to predict CTR performance (0-100)
and generate actionable improvement recommendations before publishing.
"""

import re
from typing import Dict, List, Any, Optional

POWER_WORDS = {
    "why", "secret", "truth", "nobody", "tested", "vs", "actual", "revealed",
    "mistake", "warning", "stopped", "insane", "banned", "ultimate", "how to",
    "dead", "real", "honest", "review", "finally", "never", "always"
}


def predict_ctr_score(title: str, thumbnail_has_face: bool = True, thumbnail_text_words: int = 3) -> Dict[str, Any]:
    """Score title + thumbnail combination for expected click-through rate (CTR)."""
    clean_title = title.strip()
    score = 50  # Base score
    positives = []
    suggestions = []

    # 1. Title Length evaluation
    t_len = len(clean_title)
    if 35 <= t_len <= 65:
        score += 12
        positives.append("Title length is optimal (35-65 chars) for mobile truncation")
    elif t_len < 25:
        score -= 8
        suggestions.append("Title is too short (<25 chars); add specificity or emotional intrigue")
    elif t_len > 75:
        score -= 10
        suggestions.append("Title exceeds 75 chars and will get cut off on mobile devices")

    # 2. Power words evaluation
    title_lower = clean_title.lower()
    found_power = [w for w in POWER_WORDS if w in title_lower]
    if found_power:
        score += min(15, len(found_power) * 7)
        positives.append(f"Contains high-CTR power words: {', '.join(found_power[:3])}")
    else:
        suggestions.append("Add a curiosity or power word (e.g. 'Why', 'Truth', 'Tested', 'Actual')")

    # 3. Numbers / Statistics check
    if re.search(r'\b\d+\b', clean_title) or re.search(r'\b(one|two|three|five|ten|hundred|thousand)\b', title_lower):
        score += 8
        positives.append("Includes concrete numbers or statistics")
    else:
        suggestions.append("Consider adding a number or timeframe (e.g. '7 Days', '3 Mistakes', '10X')")

    # 4. Parentheses / Brackets boost
    if re.search(r'[\(\[].*?[\)\]]', clean_title):
        score += 7
        positives.append("Uses brackets or parentheses to highlight value proposition")
    else:
        suggestions.append("Try adding parenthetical emphasis like '(Real Benchmark)' or '[Not Clickbait]'")

    # 5. Thumbnail synergy
    if thumbnail_has_face:
        score += 8
        positives.append("Thumbnail includes human face / eye contact")
    if 1 <= thumbnail_text_words <= 4:
        score += 5
        positives.append("Thumbnail text is concise (1-4 words)")
    elif thumbnail_text_words > 6:
        score -= 8
        suggestions.append("Thumbnail has too much text (>6 words); reduce to punchy 2-4 word hook")

    final_score = max(5, min(98, score))
    grade = "A+" if final_score >= 85 else ("A" if final_score >= 75 else ("B" if final_score >= 60 else "C"))

    return {
        "title": clean_title,
        "predicted_ctr_score": final_score,
        "grade": grade,
        "positive_signals": positives,
        "improvement_suggestions": suggestions
    }
