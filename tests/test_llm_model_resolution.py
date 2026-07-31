"""Model resolution for the NVIDIA provider.

query_llm passes the resolved model to query_nvidia explicitly, and that
argument wins over everything query_nvidia would otherwise consult. Keying it
on the generic LLM_MODEL therefore made NVIDIA_MODEL unreachable and pinned
every call to the strategy table's default.
"""

import llm_summary


def _resolve(monkeypatch, env):
    """Resolve the model exactly as query_llm's strategy table does."""
    for key in ("LLM_MODEL", "NVIDIA_MODEL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(llm_summary, "get_llm_setting",
                        lambda k, d="": __import__("os").environ.get(k) or d)
    return llm_summary.get_llm_setting("NVIDIA_MODEL", llm_summary.NVIDIA_DEFAULT_MODEL)


def test_nvidia_model_env_var_is_honoured(monkeypatch):
    assert _resolve(monkeypatch, {"NVIDIA_MODEL": "meta/llama-3.3-70b-instruct"}) == \
        "meta/llama-3.3-70b-instruct"


def test_falls_back_to_default_when_unset(monkeypatch):
    assert _resolve(monkeypatch, {}) == llm_summary.NVIDIA_DEFAULT_MODEL


def test_nvidia_strategy_keys_off_nvidia_model(monkeypatch):
    """Regression: the strategy table used to read LLM_MODEL for nvidia."""
    import inspect

    source = inspect.getsource(llm_summary.query_llm)
    nvidia_line = next(l for l in source.splitlines() if '"nvidia": (query_nvidia' in l)
    assert "NVIDIA_MODEL" in nvidia_line, nvidia_line
    assert "LLM_MODEL" not in nvidia_line, nvidia_line


def test_no_end_of_life_model_is_hardcoded():
    """minimaxai/minimax-m2.7 reached EOL 2026-07-27 and returns HTTP 410."""
    source = open(llm_summary.__file__, encoding="utf-8").read()
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
    assert "minimaxai/minimax-m2.7" not in code


def test_default_model_is_a_served_model():
    assert llm_summary.NVIDIA_DEFAULT_MODEL == "meta/llama-3.3-70b-instruct"
