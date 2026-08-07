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


# ── topic words must not corroborate ──────────────────────────────────────

def test_generic_ai_vocabulary_does_not_fuse_unrelated_stories():
    """Regression: "artificial"+"intelligence" fused a power-systems paper with
    an OpenAI gadget story, a rogue-agent story, and an AI-religion story."""
    scored = {
        "papers": [
            {"title": "Bridging Artificial Intelligence and Power Systems Education Framework",
             "signal_score": 95, "url": "https://arxiv.org/abs/2501.1"},
        ],
        "blogs": [
            {"title": "Jony Ive's first OpenAI gadget is reportedly a hockey puck",
             "signal_score": 80, "url": "https://example.com/1"},
            {"title": "Artificial intelligence bots started a religion",
             "signal_score": 78, "url": "https://example.com/2"},
            {"title": "Intelligence is Free, Now What? Data Systems for Everyone",
             "signal_score": 76, "url": "https://example.com/3"},
        ],
    }
    stories = ci.build_story_candidates(scored)

    # None of these items are about the same thing, so nothing may corroborate.
    for story in stories:
        assert story["source_count"] == 1, (
            f"{story['topic'][:40]!r} wrongly absorbed "
            f"{[r['title'][:30] for r in story['related_items'][1:]]}")


def test_an_uncommon_word_is_not_a_name():
    """"insane" and "problem" are rare-ish English, not subjects.

    Treating them as names grouped an "INSANE Week" roundup with "INSANE
    prompts", and "Stupidity is the problem" with "The Problem with pandas".
    """
    for token in ("insane", "problem", "stupidity", "entropy", "compression"):
        assert ci._is_strong_name(token) is False, f"{token} must not link alone"
    for token in ("gpt-5.6", "lfm2.5-2.6b", "llama.cpp", "minimax-h3"):
        assert ci._is_strong_name(token) is True, f"{token} should link alone"


def test_a_bare_version_is_not_a_name():
    for token in ("2.0", "10x", "26m", "100"):
        assert ci._is_strong_name(token) is False


def test_a_shared_name_links_even_when_widely_mentioned():
    """A dozen articles naming gpt-5.6 are probably about GPT-5.6."""
    scored = {"blogs": [
        {"title": f"Coverage number {n} of the GPT-5.6 launch",
         "signal_score": 80 - n, "url": f"https://example.com/{n}"}
        for n in range(6)
    ]}
    stories = ci.build_story_candidates(scored)

    assert len(stories) == 1, "one subject should yield one story"
    assert len(stories[0]["related_items"]) > 1


def test_topic_words_are_dropped_before_they_can_corroborate():
    """Stopwording happens in _story_tokens, upstream of the specificity test."""
    tokens = ci._story_tokens({
        "title": "Artificial Intelligence Systems: A Framework for Benchmark Evaluation",
        "url": "https://example.com/x",
    })
    for word in ("artificial", "intelligence", "systems", "framework", "benchmark"):
        assert word not in tokens, f"{word} survived as a linking token"

    named = ci._story_tokens({"title": "OmniRoute and llama.cpp ship GPT-5.6 support",
                              "url": "https://example.com/y"})
    assert {"omniroute", "llama.cpp", "gpt-5.6"} <= named


def test_distinctiveness_does_not_loosen_as_the_corpus_grows():
    """common_max scaling with corpus size made clustering looser with more data."""
    def common_max(corpus):
        return min(8, max(3, corpus // 120))

    assert common_max(200) <= common_max(1000) <= 8
    # The production corpus (851) previously yielded 85.
    assert common_max(851) <= 8


# ── anchor-source weighting ───────────────────────────────────────────────

def _paper_vs_incident(paper_score=90, incident_score=90):
    """A paper and an incident with matched signal and matched corroboration."""
    # Each distinctive name appears in exactly two documents, which is what
    # corroboration means; a name in most of a tiny corpus is not distinctive.
    # Both stories therefore get one corroborator — only the anchor differs.
    return {
        "papers": [
            {"title": "Desbordante-2.1: discovering order dependencies at scale",
             "signal_score": paper_score, "url": "https://arxiv.org/abs/2501.1"},
        ],
        "hackernews": [
            {"title": "OmniRoute agents hacked a second account during testing",
             "signal_score": incident_score, "url": "https://news.ycombinator.com/item?id=9"},
            {"title": "Desbordante-2.1 discussion thread",
             "signal_score": 70, "url": "https://news.ycombinator.com/item?id=1"},
        ],
        "blogs": [
            {"title": "OmniRoute incident: a reconstructed timeline",
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
