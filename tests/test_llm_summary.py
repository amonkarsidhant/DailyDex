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
