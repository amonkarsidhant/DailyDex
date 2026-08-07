"""Tests for story-level topic selection.

build_topic_clusters groups by TOPIC_PATTERNS and yields category labels
("AI Tools", "General"). build_story_candidates anchors on the item that
actually happened, so the factory names a video after an event.
"""

import creator_intelligence as ci


def _scored():
    return {
        "hackernews": [
            {"title": "GPT-5.6 vs. Claude Fable 5 for Physical AI, which performs best?",
             "signal_score": 92, "url": "https://example.com/hn/1"},
            {"title": "We're frozen out (for good?)", "signal_score": 90,
             "url": "https://example.com/hn/2"},
        ],
        "blogs": [
            {"title": "Advancing the price-performance frontier with GPT-5.6 | JuliaHub",
             "signal_score": 80, "url": "https://example.com/blog/1"},
            {"title": "Master NotebookLM 2.0 (2026 Edition)", "signal_score": 70,
             "url": "https://example.com/blog/2"},
        ],
        "youtube": [
            {"title": "LG AI Research releases K-EXAONE 2.0", "signal_score": 68,
             "url": "https://example.com/yt/1"},
        ],
        "github": [
            {"title": "diegosouzapw/OmniRoute", "signal_score": 88,
             "description": "Free MIT AI gateway. One endpoint, 290+ providers.",
             "url": "https://github.com/diegosouzapw/OmniRoute", "has_code": True},
        ],
    }


def test_anchor_is_a_headline_not_a_taxonomy_label():
    stories = ci.build_story_candidates(_scored())
    topics = [s["topic"] for s in stories]

    assert any("GPT-5.6" in t for t in topics)
    # None of the TOPIC_PATTERNS bucket names should appear as a story.
    for label in ("AI Tools", "Coding AI", "General", "Model"):
        assert label not in topics


def test_vague_titles_do_not_anchor_a_story():
    """"We're frozen out (for good?)" names nothing researchable."""
    stories = ci.build_story_candidates(_scored())
    assert not any("frozen out" in s["topic"].lower() for s in stories)


def test_github_slug_becomes_a_readable_headline():
    stories = ci.build_story_candidates(_scored())
    omni = next(s for s in stories if "OmniRoute" in s["topic"])

    assert omni["topic"].startswith("OmniRoute:")
    assert "diegosouzapw/" not in omni["topic"]
    # The lead item the factory reads must carry the same headline.
    assert omni["related_items"][0]["title"] == omni["topic"]


def test_feed_titles_lose_their_publication_suffix():
    assert ci._normalize_headline("Real headline about models | JuliaHub") == \
        "Real headline about models"
    # Too short to be a headline on its own, so the split is not applied.
    assert "|" in ci._normalize_headline("Kimi K3 | JuliaHub")


def test_bare_version_numbers_do_not_fuse_unrelated_stories():
    """"NotebookLM 2.0" and "K-EXAONE 2.0" share "2.0" and nothing else."""
    stories = ci.build_story_candidates(_scored())
    notebook = [s for s in stories if "NotebookLM" in s["topic"]]
    if notebook:
        titles = " ".join(r["title"] for r in notebook[0]["related_items"])
        assert "EXAONE" not in titles


def test_shared_product_name_corroborates_across_sources():
    stories = ci.build_story_candidates(_scored())
    gpt = next(s for s in stories if "GPT-5.6" in s["topic"])

    assert gpt["corroborated"] is True
    assert "blogs" in gpt["sources"] and "hackernews" in gpt["sources"]


def test_generic_english_words_are_not_specific():
    for token in ("out", "good", "part", "2.0", "10x"):
        assert ci._is_specific(token) is False
    for token in ("gpt-5.6", "omniroute", "cross-entropy", "minimax"):
        assert ci._is_specific(token) is True


def test_opaque_identifiers_are_dropped_from_tokens():
    tokens = ci._story_tokens({
        "title": "Some real headline about agents",
        "url": "https://youtube.com/watch?v=61dz7fh0ozg",
    })
    assert "61dz7fh0ozg" not in tokens
    # The host must not survive, or every YouTube item corroborates every other.
    assert "youtube.com" not in tokens


# ── anchor-source weighting ───────────────────────────────────────────────

def _paper_vs_incident(paper_score=90, incident_score=90):
    """A paper and an incident with matched signal and matched corroboration."""
    return {
        "papers": [
            {"title": "Bridging Artificial Intelligence and Power Systems Education Framework",
             "signal_score": paper_score, "url": "https://arxiv.org/abs/2501.1"},
        ],
        "hackernews": [
            {"title": "OpenAI agents hacked a second account during model testing",
             "signal_score": incident_score, "url": "https://news.ycombinator.com/item?id=9"},
            {"title": "Power Systems Education Framework discussion",
             "signal_score": 70, "url": "https://news.ycombinator.com/item?id=1"},
        ],
        "blogs": [
            {"title": "Notes on the Power Systems Education Framework paper",
             "signal_score": 70, "url": "https://example.com/p"},
            {"title": "OpenAI agents hacked a second account: timeline",
             "signal_score": 70, "url": "https://example.com/h"},
        ],
    }


def _rank_of(stories, source):
    for index, story in enumerate(stories):
        if story["anchor_source"] == source:
            return index
    return None


def test_a_paper_does_not_outrank_an_incident_at_equal_signal():
    """Papers corroborate easily, which floated them above real events."""
    stories = ci.build_story_candidates(_paper_vs_incident())

    assert _rank_of(stories, "hackernews") < _rank_of(stories, "papers")


def test_a_clearly_bigger_paper_still_surfaces():
    """The weighting is a thumb on the scale, not a ban on papers."""
    stories = ci.build_story_candidates(_paper_vs_incident(paper_score=99, incident_score=40))

    assert _rank_of(stories, "papers") == 0


def test_weighting_keys_on_the_anchor_not_the_corroborating_sources():
    """A paper corroborated by HN must not collect HN's bonus."""
    stories = ci.build_story_candidates(_paper_vs_incident())
    paper = next(s for s in stories if s["anchor_source"] == "papers")

    assert "hackernews" in paper["sources"], "fixture should have HN corroboration"
    # Anchor weight is the paper's, so the penalty applies despite HN support.
    assert paper["story_score"] < paper["average_signal_score"] + 12 * (paper["source_count"] - 1) + 10


def test_empty_input_returns_no_stories():
    assert ci.build_story_candidates({}) == []
    assert ci.build_story_candidates({"github": []}) == []
