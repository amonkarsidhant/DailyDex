"""Focused tests for LLM provider configuration."""

from unittest.mock import MagicMock

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
