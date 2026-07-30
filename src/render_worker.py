#!/usr/bin/env python3
"""Persistent render worker for database-backed factory jobs."""

import json
import os
import time

from data_models import IntelligenceDB
from factory import run_factory


def _load_scored_data():
    path = os.environ.get("SCORED_DATA_FILE", "/app/data/data_scored.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run_once(db):
    job = db.factory_job_claim()
    if not job:
        return False
    try:
        result = run_factory(
            db,
            db.factory_job_payload(job["id"]) or _load_scored_data(),
            limit=1,
            cluster_slug=job["cluster_slug"],
            auto_approve=False,
        )
        error = ""
        if result.get("failed") and not result.get("queued") and not result.get("blocked"):
            error = str(result["failed"][0].get("error") or "factory failed")
        if error and int(job.get("attempts") or 0) < 3:
            db.factory_job_retry(job["id"], error)
        else:
            db.factory_job_finish(job["id"], result=result, error=error)
    except Exception as exc:
        if int(job.get("attempts") or 0) < 3:
            db.factory_job_retry(job["id"], str(exc))
        else:
            db.factory_job_finish(job["id"], error=str(exc))
    return True


def main():
    db = IntelligenceDB(os.environ.get("DB_PATH", "/app/data/intelligence.db"))
    db.factory_jobs_requeue_running()
    poll_seconds = max(1.0, float(os.environ.get("RENDER_WORKER_POLL_SECONDS", "2")))
    while True:
        if not run_once(db):
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
