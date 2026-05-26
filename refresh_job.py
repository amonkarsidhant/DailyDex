#!/usr/bin/env python3
"""Standalone hourly refresh for the DailyDex Cockpit.

Runs the same pipeline as POST /api/refresh — fetch_all() → re-score →
cluster snapshot — directly against the data files and SQLite DB, so the
content stays populated whether or not the web server is running.

Invoked by the launchd job com.dailydex.refresh (every 60 min).
"""
import sys
import time
import traceback

import dashboard_new as dd
from fetch_news import fetch_all
from creator_intelligence import snapshot_clusters


def main() -> int:
    started = time.time()
    print(f"[refresh_job] start {time.strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        fetch_all()
        scored = dd.load_scored_data(force=True)
        if dd.intel_db is not None:
            snapshot_clusters(scored, dd.intel_db)
            print("[refresh_job] cluster snapshot written")
        n = sum(len(scored.get(k, []) or []) for k in
                ("github", "huggingface", "youtube", "blogs", "papers"))
        print(f"[refresh_job] done — {n} scored items in {time.time() - started:.1f}s")
        return 0
    except Exception:
        print("[refresh_job] FAILED:\n" + traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
