import importlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest


REPO_DIR = Path(__file__).resolve().parent


def _sample_raw_data(now_iso: str):
    return {
        "last_updated": now_iso,
        "github": [
            {
                "source": "GitHub Trending",
                "title": "acme/agent-repo",
                "url": "https://github.com/acme/agent-repo",
                "description": "AI coding agent for developers.",
                "stars": "4200",
                "language": "Python",
            }
        ],
        "huggingface": [
            {
                "source": "HuggingFace",
                "title": "acme/coder-model",
                "url": "https://huggingface.co/acme/coder-model",
                "downloads": 12000,
                "likes": 250,
            }
        ],
        "youtube": [
            {
                "source": "YouTube - Test",
                "title": "Agent workflows on Raspberry Pi",
                "url": "https://youtube.com/watch?v=test123",
                "description": "Walkthrough for local agent workflows.",
                "type": "video",
            }
        ],
        "blogs": [
            {
                "source": "Test Blog",
                "title": "Agents are getting practical",
                "url": "https://example.com/agents-practical",
                "published": now_iso,
                "type": "blog",
            }
        ],
        "papers": [
            {
                "source": "ArXiv AI",
                "title": "Practical Agentic Workflows",
                "url": "https://arxiv.org/abs/1234.5678",
                "published": now_iso,
                "arxiv_id": "1234.5678",
                "authors": ["A. Researcher"],
                "abstract": "This paper studies practical agentic workflows for coding tasks.",
                "categories": ["cs.AI"],
                "pdf_url": "https://arxiv.org/pdf/1234.5678.pdf",
            }
        ],
    }


def _sample_scored_data(now_iso: str):
    return {
        "last_updated": now_iso,
        "scored_at": now_iso,
        "executive_brief": {
            "items": [
                {
                    "title": "acme/agent-repo",
                    "signal_score": 88,
                    "action": "try",
                    "categories": ["agents", "developer-tools"],
                    "recommendation": "Try locally this week.",
                    "url": "https://github.com/acme/agent-repo",
                }
            ]
        },
        "github": [
            {
                "source": "GitHub Trending",
                "source_type": "github",
                "title": "acme/agent-repo",
                "url": "https://github.com/acme/agent-repo",
                "description": "AI coding agent for developers.",
                "stars": "4200",
                "language": "Python",
                "license": "MIT",
                "signal_score": 88,
                "score_label": "Hot",
                "score_reason": "Strong developer productivity and agentic relevance.",
                "score_breakdown": {"recency": 15, "popularity": 20, "agentic": 20, "local": 12, "relevance": 12},
                "categories": ["agents", "developer-tools"],
                "action": "try",
                "pi_suitability": "yes",
                "installation_complexity": "medium",
            }
        ],
        "huggingface": [
            {
                "source": "HuggingFace",
                "source_type": "model",
                "title": "acme/coder-model",
                "url": "https://huggingface.co/acme/coder-model",
                "downloads": 12000,
                "likes": 250,
                "signal_score": 72,
                "score_label": "Watch",
                "score_reason": "Strong local coding relevance.",
                "categories": ["model", "coding"],
                "action": "save",
                "is_local": True,
                "is_small": True,
                "is_coding_model": True,
                "is_local_compatible": True,
                "is_agent_ready": True,
                "is_multimodal": False,
                "tool_calling": True,
            }
        ],
        "youtube": [
            {
                "source": "YouTube - Test",
                "source_type": "youtube",
                "title": "Agent workflows on Raspberry Pi",
                "url": "https://youtube.com/watch?v=test123",
                "description": "Walkthrough for local agent workflows.",
                "signal_score": 63,
                "categories": ["agents", "raspberry-pi"],
                "action": "watch",
                "watch_priority": "high",
                "score_breakdown": {"recency": 14, "popularity": 12, "agentic": 18, "local": 10, "relevance": 9},
            }
        ],
        "blogs": [
            {
                "source": "Test Blog",
                "source_type": "blogs",
                "title": "Agents are getting practical",
                "url": "https://example.com/agents-practical",
                "description": "Why agentic workflows are becoming more reliable.",
                "signal_score": 58,
                "categories": ["agents", "news"],
                "action": "read",
                "score_breakdown": {"recency": 15, "popularity": 8, "agentic": 14, "local": 5, "relevance": 10},
            }
        ],
        "papers": [
            {
                "source": "ArXiv AI",
                "source_type": "papers",
                "title": "Practical Agentic Workflows",
                "url": "https://arxiv.org/abs/1234.5678",
                "published": now_iso,
                "signal_score": 69,
                "categories": ["research", "agents"],
                "action": "save",
                "recommendation": "skim",
                "has_code": True,
                "score_breakdown": {"recency": 16, "popularity": 6, "agentic": 16, "local": 8, "relevance": 12},
                "abstract": "This paper studies practical agentic workflows for coding tasks.",
                "authors": ["A. Researcher"],
                "arxiv_id": "1234.5678",
                "pdf_url": "https://arxiv.org/pdf/1234.5678.pdf",
            }
        ],
    }


def _load_app_env(tmp_path, monkeypatch, raw_data, scored_data, selected_variant="default"):
    data_dir = tmp_path / "data"
    cache_dir = data_dir / "cache"
    digest_dir = data_dir / "digests"
    data_dir.mkdir()
    cache_dir.mkdir()
    digest_dir.mkdir()

    config_path = tmp_path / "config.json"
    config_data = json.loads((REPO_DIR / "config.json").read_text(encoding="utf-8"))
    config_data["variant"] = selected_variant
    config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DB_PATH", str(data_dir / "intelligence.db"))
    monkeypatch.setenv("CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("DIGEST_DIR", str(digest_dir))
    monkeypatch.setenv("DATA_FILE", str(data_dir / "data.json"))
    monkeypatch.setenv("SCORED_DATA_FILE", str(data_dir / "data_scored.json"))
    monkeypatch.setenv("CONFIG_FILE", str(config_path))
    monkeypatch.setenv("CONFIG_PATH", str(REPO_DIR / "config" / "topics.json"))

    (data_dir / "data.json").write_text(json.dumps(raw_data, indent=2), encoding="utf-8")
    (data_dir / "data_scored.json").write_text(json.dumps(scored_data, indent=2), encoding="utf-8")

    for module_name in ["data_models", "digest_generator", "fetch_news", "dashboard_new"]:
        sys.modules.pop(module_name, None)

    import dashboard_new

    dashboard_new = importlib.reload(dashboard_new)

    return {
        "module": dashboard_new,
        "data_dir": data_dir,
        "cache_dir": cache_dir,
        "digest_dir": digest_dir,
    }


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    now_iso = datetime.now().isoformat()
    return _load_app_env(tmp_path, monkeypatch, _sample_raw_data(now_iso), _sample_scored_data(now_iso))


@pytest.fixture
def creator_app_env(tmp_path, monkeypatch):
    now_iso = datetime.now().isoformat()
    return _load_app_env(tmp_path, monkeypatch, _sample_raw_data(now_iso), _sample_scored_data(now_iso), selected_variant="creator")


@pytest.fixture
def empty_app_env(tmp_path, monkeypatch):
    now_iso = datetime.now().isoformat()
    empty_raw = {
        "last_updated": now_iso,
        "github": [],
        "huggingface": [],
        "youtube": [],
        "blogs": [],
        "papers": [],
    }
    empty_scored = {
        "last_updated": now_iso,
        "scored_at": now_iso,
        "executive_brief": {"items": []},
        "github": [],
        "huggingface": [],
        "youtube": [],
        "blogs": [],
        "papers": [],
    }
    return _load_app_env(tmp_path, monkeypatch, empty_raw, empty_scored)


@pytest.fixture
def client(app_env):
    return app_env["module"].app.test_client()


@pytest.fixture
def creator_client(creator_app_env):
    return creator_app_env["module"].app.test_client()


@pytest.fixture
def empty_client(empty_app_env):
    return empty_app_env["module"].app.test_client()
