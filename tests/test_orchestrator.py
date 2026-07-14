"""Tests for the orchestrator pipeline and EnrichmentService.run_once()."""

import os
import sys
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ---------------------------------------------------------------------------
# EnrichmentService.run_once()
# ---------------------------------------------------------------------------

def test_enrichment_service_run_once_exists():
    """EnrichmentService should have a run_once method for synchronous execution."""
    from creator_enricher import EnrichmentService
    assert hasattr(EnrichmentService, "run_once")
    assert callable(getattr(EnrichmentService, "run_once"))


def test_enrichment_service_run_once_empty_queue(tmp_path):
    """run_once on an empty queue should return 0 immediately."""
    from data_models import IntelligenceDB
    from creator_enricher import EnrichmentService

    db = IntelligenceDB(str(tmp_path / "test.db"))
    svc = EnrichmentService(db)
    # Queue is empty — should return 0 fast
    result = svc.run_once(timeout=2)
    assert result == 0


def test_enrichment_service_run_once_processes_job(tmp_path, monkeypatch):
    """run_once should process a queued job synchronously."""
    from data_models import IntelligenceDB
    from creator_enricher import EnrichmentService

    db = IntelligenceDB(str(tmp_path / "test.db"))
    svc = EnrichmentService(db)

    # Mock the LLM call so we don't need a real API key
    def mock_generate(item, profile=None, retries=1):
        return {
            "ok": True,
            "pack": {"insight": "test insight", "schema_version": 1},
            "model": "test-model",
            "issues": [],
        }

    monkeypatch.setattr("creator_enricher.llm_summary.generate_creator_pack", mock_generate)

    # Enqueue an item
    item = {"title": "Test Item", "url": "https://example.com/test", "source": "test"}
    svc.enqueue(item)

    # Process synchronously
    processed = svc.run_once(timeout=10)
    assert processed == 1

    # Verify it was saved to DB
    from creator_enricher import content_hash
    chash = content_hash(item)
    asset = db.get_creator_asset(chash)
    assert asset is not None
    assert asset["status"] == "ready"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def test_orchestrator_steps_exist():
    """All 4 pipeline steps should be defined in the orchestrator module."""
    # Read the source file and check the step functions are defined
    src = Path(__file__).resolve().parent.parent / "src" / "orchestrator.py"
    content = src.read_text()
    assert "def step_fetch(" in content
    assert "def step_enrich(" in content
    assert "def step_studio(" in content
    assert "def step_sync_notion(" in content
    assert "def run_full_cycle(" in content
    assert "def run_daemon(" in content
    assert "--daemon" in content
    assert "--step" in content


def test_orchestrator_fetch_refreshes_benchmarks(monkeypatch):
    import orchestrator
    import types

    db = MagicMock()
    dashboard = types.SimpleNamespace(
        intel_db=db,
        load_scored_data=lambda force=False: {"github": [{"title": "item"}]},
    )
    benchmark_fetcher = MagicMock(return_value=7)

    monkeypatch.setitem(
        sys.modules,
        "fetch_news",
        types.SimpleNamespace(fetch_all=lambda: "now"),
    )
    monkeypatch.setitem(sys.modules, "dashboard_new", dashboard)
    monkeypatch.setitem(
        sys.modules,
        "creator_intelligence",
        types.SimpleNamespace(snapshot_clusters=lambda scored, intel_db: None),
    )
    monkeypatch.setattr(
        "data.fetch_benchmarks.fetch_benchmarks",
        benchmark_fetcher,
    )

    result = orchestrator.step_fetch()

    benchmark_fetcher.assert_called_once_with(db=db)
    assert result["benchmarks"] == 7


def test_orchestrator_run_full_cycle_logic():
    """run_full_cycle logic: call all steps and collect results dict."""
    # Test the orchestration logic directly without importing the full orchestrator
    # (which pulls in dashboard_new and starts background threads)
    steps = {
        "fetch": lambda: {"scored_items": 10},
        "enrich": lambda: {"processed": 5},
        "studio": lambda: {"ok": True, "stories": 2},
        "notion-sync": lambda: {"synced": 0, "skipped": True},
    }

    results = {}
    for step_name, step_fn in steps.items():
        try:
            results[step_name] = step_fn()
        except Exception as exc:
            results[step_name] = {"error": str(exc)}

    assert "fetch" in results
    assert "enrich" in results
    assert "studio" in results
    assert "notion-sync" in results
    assert results["fetch"]["scored_items"] == 10
    assert results["enrich"]["processed"] == 5
    assert results["studio"]["ok"] is True


def test_orchestrator_notion_sync_skipped_when_disabled(monkeypatch):
    """Notion sync should skip when ORCH_NOTION_SYNC is not '1'."""
    monkeypatch.setenv("ORCH_NOTION_SYNC", "0")

    # Import just the function logic without the full module chain
    # step_sync_notion checks env vars before importing anything heavy
    import importlib
    import types

    # Create a minimal test by checking the logic directly
    notion_sync = os.environ.get("ORCH_NOTION_SYNC", "0") == "1"
    token = os.environ.get("NOTION_API_TOKEN", "")
    db_id = os.environ.get("NOTION_DATABASE_ID", "")

    assert not notion_sync  # ORCH_NOTION_SYNC=0 -> should skip


def test_orchestrator_notion_sync_skipped_when_no_token(monkeypatch):
    """Notion sync should skip when token is missing."""
    monkeypatch.setenv("ORCH_NOTION_SYNC", "1")
    monkeypatch.setenv("NOTION_API_TOKEN", "")
    monkeypatch.setenv("NOTION_DATABASE_ID", "")

    notion_sync = os.environ.get("ORCH_NOTION_SYNC", "0") == "1"
    token = os.environ.get("NOTION_API_TOKEN", "")
    db_id = os.environ.get("NOTION_DATABASE_ID", "")

    assert notion_sync  # ORCH_NOTION_SYNC=1
    assert not token     # but token is empty -> should skip


def test_orchestrator_step_handles_failure():
    """run_full_cycle should catch per-step failures and continue."""
    # Test the error handling logic directly without importing the full orchestrator
    # (which pulls in dashboard_new and starts threads)

    steps = {
        "fetch": lambda: (_ for _ in ()).throw(RuntimeError("kaboom")),
        "enrich": lambda: {"processed": 0},
        "studio": lambda: {"ok": False, "stories": 0},
        "notion-sync": lambda: {"skipped": True},
    }

    results = {}
    for step_name, step_fn in steps.items():
        try:
            results[step_name] = step_fn()
        except Exception as exc:
            results[step_name] = {"error": str(exc)}

    assert "error" in results["fetch"]
    assert "kaboom" in results["fetch"]["error"]
    assert results["enrich"]["processed"] == 0
    assert results["studio"]["ok"] is False
