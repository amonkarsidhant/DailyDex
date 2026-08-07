"""Focused tests for LLM provider configuration."""

from unittest.mock import MagicMock

import cli_registry
import llm_summary


def test_query_nvidia_prefers_provider_specific_model(monkeypatch):
    monkeypatch.setenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
    monkeypatch.setenv("LLM_MODEL", "legacy-model")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [{"message": {"content": "working"}}]
    }
    post = MagicMock(return_value=response)
    monkeypatch.setattr(llm_summary.requests, "post", post)

    result = llm_summary.query_nvidia("hello", api_key="test-key")

    assert result == "working"
    assert post.call_args.kwargs["json"]["model"] == "meta/llama-3.3-70b-instruct"


def test_studio_nvidia_prefers_environment_model_over_profile(monkeypatch):
    monkeypatch.setenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
    monkeypatch.setattr(
        llm_summary,
        "load_creator_profile",
        lambda: {
            "copilot": {
                "provider": "nvidia",
                "model": "stepfun-ai/step-3.5-flash",
            }
        },
    )
    query = MagicMock(return_value="working")
    monkeypatch.setattr(llm_summary, "query_nvidia", query)

    result = cli_registry.generate(
        "hello", "system", prefer="nvidia", timeout=30
    )

    assert result["text"] == "working"
    assert result["model"] == "meta/llama-3.3-70b-instruct"
    assert query.call_args.kwargs["model"] == "meta/llama-3.3-70b-instruct"


def test_the_prompt_states_the_title_length_the_validator_enforces():
    """Every enriched pack was flagged "title.* too short" because the schema
    block never told the model the length the validator demands."""
    import llm_summary

    profile = llm_summary.load_creator_profile()
    prompt = llm_summary.build_creator_system_prompt(profile)
    rules = profile.get("format_rules") or {}
    low = rules.get("title_min_chars", 30)
    high = rules.get("title_max_chars", 70)

    assert "suggested_titles" in prompt
    assert f"{low}-{high} characters" in prompt, \
        "the title length constraint must reach the model, not just the validator"


def test_titles_at_the_stated_length_pass_validation():
    import llm_summary

    profile = llm_summary.load_creator_profile()
    rules = profile.get("format_rules") or {}
    good = "How one rogue agent quietly rewrote production config"
    assert len(good) >= rules.get("title_min_chars", 30) - 5

    pack = {key: "x" for key in llm_summary.CREATOR_PACK_REQUIRED_KEYS}
    pack["suggested_titles"] = {k: good for k in llm_summary.SUGGESTED_TITLE_KEYS}
    issues = llm_summary.validate_creator_pack(pack, profile)

    assert not [i for i in issues if "title." in i and "short" in i]
