#!/usr/bin/env python3
"""DailyDex Orchestrator — 24/7 autonomous pipeline daemon.

Runs on a VM (via docker-compose sidecar or systemd timer) and executes the
full content pipeline on a schedule:

  1. FETCH   — pull fresh signals from 7 sources (every 2 hours)
  2. SCORE   — re-score all items → data_scored.json
  3. ENRICH  — run LLM enrichment on top items (after each fetch)
  4. STUDIO  — generate scripts/assets for top clusters (every 6 hours)
  5. SYNC    — push new saved items to Notion (after each studio run)

Usage:
    python src/orchestrator.py              # run one full cycle and exit
    python src/orchestrator.py --daemon      # run forever on schedule
    python src/orchestrator.py --step fetch  # run a single step

Environment variables:
    ORCH_FETCH_INTERVAL    — seconds between fetch cycles (default: 7200 = 2h)
    ORCH_STUDIO_INTERVAL   — seconds between studio runs (default: 21600 = 6h)
    ORCH_TOP_N             — top N clusters to generate content for (default: 3)
    ORCH_NOTION_SYNC       — "1" to enable Notion sync (default: "0")
    NOTION_API_TOKEN       — Notion integration token
    NOTION_DATABASE_ID     — Notion database ID
    LLM_PROVIDER           — nvidia, openai, anthropic, ollama, gemini, etc.
    NVIDIA_API_KEY         — if using NVIDIA NIM
"""

from __future__ import annotations

import os
import sys
import time
import json
import signal
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional

# Ensure src/ is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FETCH_INTERVAL = int(os.environ.get("ORCH_FETCH_INTERVAL", "7200"))
STUDIO_INTERVAL = int(os.environ.get("ORCH_STUDIO_INTERVAL", "21600"))
TOP_N = int(os.environ.get("ORCH_TOP_N", "3"))
NOTION_SYNC = os.environ.get("ORCH_NOTION_SYNC", "0") == "1"
RUNNING = True


def _log(msg: str) -> None:
    print(f"[orchestrator {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def step_fetch() -> Dict[str, Any]:
    """Fetch fresh signals from all 7 sources + re-score."""
    _log("STEP: fetch — pulling signals from all sources")
    from fetch_news import fetch_all

    last_updated = fetch_all()
    _log(f"  fetch complete: last_updated={last_updated}")

    # Re-score immediately after fetch
    import dashboard_new as dd
    scored = dd.load_scored_data(force=True)
    n = sum(len(scored.get(k, []) or []) for k in
            ("github", "huggingface", "youtube", "blogs", "papers", "hackernews", "reddit"))
    _log(f"  scored: {n} items across all sources")

    # Snapshot clusters for trend tracking
    try:
        from creator_intelligence import snapshot_clusters
        if dd.intel_db is not None:
            snapshot_clusters(scored, dd.intel_db)
            _log("  cluster snapshot written")
    except Exception as exc:
        _log(f"  WARNING: cluster snapshot failed: {exc}")

    benchmark_count = 0
    try:
        from data.fetch_benchmarks import fetch_benchmarks
        if dd.intel_db is not None:
            benchmark_count = fetch_benchmarks(db=dd.intel_db)
            _log(f"  benchmarks refreshed: {benchmark_count} models")
    except Exception as exc:
        _log(f"  WARNING: benchmark refresh failed: {exc}")

    return {
        "last_updated": last_updated,
        "scored_items": n,
        "benchmarks": benchmark_count,
    }


def step_enrich() -> Dict[str, Any]:
    """Enqueue top items for enrichment and process them synchronously."""
    _log("STEP: enrich — queuing top items for LLM enrichment")
    import dashboard_new as dd
    from creator_enricher import EnrichmentService

    if dd.intel_db is None:
        return {"error": "no_db"}

    svc = EnrichmentService(dd.intel_db)
    scored = dd.load_scored_data()

    # Pick top items for enrichment (same logic as dashboard_new)
    from dashboard_new import _top_items_for_enrichment
    top = _top_items_for_enrichment(scored, limit=20)
    queued = svc.enqueue_batch(top, limit=20)
    _log(f"  queued {queued} items for enrichment")

    # Process synchronously
    processed = svc.run_once(timeout=300)
    _log(f"  enriched {processed} items")
    return {"queued": queued, "processed": processed}


def step_studio() -> Dict[str, Any]:
    """Generate scripts/assets for top clusters."""
    _log(f"STEP: studio — generating content for top {TOP_N} clusters")
    import dashboard_new as dd
    import studio_job

    if dd.intel_db is None:
        return {"error": "no_db"}

    result = studio_job.run(intel_db=dd.intel_db, top_n=TOP_N, log_fn=_log)
    _log(f"  studio done: ok={result.get('ok')} stories={result.get('stories', 0)}")
    return result


def step_sync_notion() -> Dict[str, Any]:
    """Sync unsaved items to Notion (if enabled)."""
    if not NOTION_SYNC:
        return {"skipped": True}

    token = os.environ.get("NOTION_API_TOKEN", "")
    db_id = os.environ.get("NOTION_DATABASE_ID", "")
    if not token or not db_id:
        _log("STEP: notion-sync — SKIPPED (missing NOTION_API_TOKEN or NOTION_DATABASE_ID)")
        return {"skipped": True, "reason": "missing_config"}

    _log("STEP: notion-sync — syncing saved items to Notion")
    import dashboard_new as dd
    from notion_client import sync_to_notion

    if dd.intel_db is None:
        return {"error": "no_db"}

    items = dd.intel_db.get_saved_items()
    synced = 0
    errors = 0
    for item in items:
        # Skip if already has a notion_page_url in production_assets
        assets = item.get("production_assets")
        if isinstance(assets, str):
            try:
                assets = json.loads(assets)
            except Exception:
                assets = {}
        if isinstance(assets, dict) and assets.get("notion_page_url"):
            continue

        result = sync_to_notion(item)
        if result.get("success"):
            synced += 1
            # Save the URL back to production_assets
            try:
                assets = assets or {}
                assets["notion_page_url"] = result["notion_url"]
                dd.intel_db.set_production_assets(item["id"], assets)
            except Exception:
                pass
        else:
            errors += 1
            _log(f"  notion sync error for item {item.get('id')}: {result.get('error', '?')[:80]}")

    _log(f"  notion sync: {synced} synced, {errors} errors")
    return {"synced": synced, "errors": errors}


# ---------------------------------------------------------------------------
# Cycle orchestration
# ---------------------------------------------------------------------------

STEPS = {
    "fetch": step_fetch,
    "enrich": step_enrich,
    "studio": step_studio,
    "notion-sync": step_sync_notion,
}


def run_full_cycle() -> Dict[str, Any]:
    """Run the full pipeline: fetch → enrich → studio → notion-sync."""
    _log("=" * 60)
    _log("FULL CYCLE START")
    _log("=" * 60)
    results = {}
    for step_name in ("fetch", "enrich", "studio", "notion-sync"):
        try:
            results[step_name] = STEPS[step_name]()
        except Exception as exc:
            _log(f"  STEP {step_name} FAILED: {exc}")
            _log(traceback.format_exc())
            results[step_name] = {"error": str(exc)}
    _log("=" * 60)
    _log("FULL CYCLE COMPLETE")
    _log("=" * 60)
    return results


def run_daemon():
    """Run forever: fetch every FETCH_INTERVAL, studio every STUDIO_INTERVAL."""
    global RUNNING

    def _shutdown(signum, frame):
        global RUNNING
        _log(f"Received signal {signum} — shutting down gracefully...")
        RUNNING = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    last_studio = 0.0
    _log(f"Daemon started — fetch every {FETCH_INTERVAL}s, studio every {STUDIO_INTERVAL}s")

    while RUNNING:
        try:
            # Always fetch + enrich
            step_fetch()
            step_enrich()

            # Studio on its own longer interval
            now = time.time()
            if now - last_studio >= STUDIO_INTERVAL:
                step_studio()
                step_sync_notion()
                last_studio = now

        except Exception as exc:
            _log(f"Cycle failed: {exc}")
            _log(traceback.format_exc())

        # Sleep until next fetch cycle
        if RUNNING:
            _log(f"Sleeping {FETCH_INTERVAL}s until next cycle...")
            try:
                time.sleep(FETCH_INTERVAL)
            except KeyboardInterrupt:
                break

    _log("Daemon stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--daemon" in args:
        run_daemon()
    elif "--step" in args:
        idx = args.index("--step")
        step_name = args[idx + 1] if idx + 1 < len(args) else "fetch"
        if step_name in STEPS:
            result = STEPS[step_name]()
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Unknown step: {step_name}. Available: {list(STEPS.keys())}")
            sys.exit(1)
    else:
        # Single full cycle
        result = run_full_cycle()
        print(json.dumps(result, indent=2, default=str))
