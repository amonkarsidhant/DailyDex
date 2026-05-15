#!/usr/bin/env python3
"""Background creator-pack enrichment worker.

Why this exists
---------------
The Gemini CLI is slow (a few seconds per call) and runs as a subprocess. Doing
it inline on a Flask request would freeze the dashboard on a Raspberry Pi 4.
This module owns a tiny in-process queue, a single worker thread, and a
content-hash cache so each high-signal item is enriched at most once.

Public surface
--------------
- ``content_hash(item)``: stable identifier used as cache key.
- ``EnrichmentService.enqueue(item)``: schedule one item.
- ``EnrichmentService.enqueue_batch(items, limit)``: bulk schedule.
- ``EnrichmentService.status()``: queue depth, last error, model.
- ``EnrichmentService.forge_saved(item_id, research_data)``: produce
  multi-format production assets and persist them on the saved item.
"""

from __future__ import annotations

import hashlib
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

import llm_summary

LOG = logging.getLogger("dailydex.creator_enricher")
if not LOG.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(os.environ.get("DAILYDEX_LOG_LEVEL", "INFO"))


def content_hash(item: Dict[str, Any]) -> str:
    """Stable hash for an item. Uses URL + title + truncated description."""
    parts = [
        str(item.get("url") or ""),
        str(item.get("title") or ""),
        str((item.get("description") or item.get("abstract") or ""))[:400],
    ]
    raw = "||".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()


@dataclass
class _Job:
    content_hash: str
    item: Dict[str, Any]
    callback: Optional[Callable[[str, Dict[str, Any]], None]] = None


@dataclass
class _State:
    queued: int = 0
    in_flight: int = 0
    enriched_today: int = 0
    failed_today: int = 0
    last_error: str = ""
    last_run_at: str = ""
    last_completed_at: str = ""
    in_flight_hashes: List[str] = field(default_factory=list)
    queued_hashes: List[str] = field(default_factory=list)


class EnrichmentService:
    def __init__(self, intel_db, max_queue: int = 200):
        self.db = intel_db
        self._queue: "queue.Queue[_Job]" = queue.Queue(maxsize=max_queue)
        self._state = _State()
        self._state_lock = threading.Lock()
        self._enqueued: set[str] = set()
        self._enqueued_lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.profile = llm_summary.load_creator_profile()
        self.daily_limit = int(os.environ.get("CREATOR_ENRICH_DAILY_LIMIT", "60"))

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop.clear()
        self._worker = threading.Thread(target=self._run, name="creator-enricher", daemon=True)
        self._worker.start()
        LOG.info("Enrichment worker started (provider=%s)", llm_summary.llm_provider_label())

    def stop(self) -> None:
        self._stop.set()

    # -- public API ----------------------------------------------------

    def is_cached(self, hash_: str) -> bool:
        if not self.db:
            return False
        row = self.db.get_creator_asset(hash_)
        return bool(row and row.get("status") == "ready")

    def enqueue(self, item: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
        if not self.db:
            return {"queued": False, "reason": "no_db"}
        hash_ = content_hash(item)
        if not force and self.is_cached(hash_):
            return {"queued": False, "reason": "cached", "content_hash": hash_}
        with self._enqueued_lock:
            if hash_ in self._enqueued:
                return {"queued": False, "reason": "already_queued", "content_hash": hash_}
            self._enqueued.add(hash_)
        # Mark pending so the UI can show a "queued" badge immediately.
        try:
            self.db.mark_creator_asset_status(hash_, "queued")
        except Exception as exc:
            LOG.warning("Failed to mark queued for %s: %s", hash_, exc)
        try:
            self._queue.put_nowait(_Job(content_hash=hash_, item=item))
        except queue.Full:
            with self._enqueued_lock:
                self._enqueued.discard(hash_)
            return {"queued": False, "reason": "queue_full", "content_hash": hash_}
        with self._state_lock:
            self._state.queued = self._queue.qsize()
            self._state.queued_hashes = list(self._enqueued)[:20]
        return {"queued": True, "content_hash": hash_}

    def enqueue_batch(self, items: Iterable[Dict[str, Any]], limit: int = 20) -> int:
        count = 0
        for item in items:
            if count >= limit:
                break
            result = self.enqueue(item)
            if result.get("queued"):
                count += 1
        if count:
            LOG.info("Enqueued %d items for enrichment", count)
        return count

    def status(self) -> Dict[str, Any]:
        stats: Dict[str, int] = {}
        if self.db:
            try:
                stats = self.db.creator_assets_stats()
            except Exception as exc:
                LOG.warning("creator_assets_stats failed: %s", exc)
        with self._state_lock:
            return {
                "provider": llm_summary.llm_provider_label(),
                "queued": self._queue.qsize(),
                "in_flight": self._state.in_flight,
                "in_flight_hashes": list(self._state.in_flight_hashes),
                "queued_hashes": list(self._state.queued_hashes),
                "enriched_today": self._state.enriched_today,
                "failed_today": self._state.failed_today,
                "last_error": self._state.last_error,
                "last_run_at": self._state.last_run_at,
                "last_completed_at": self._state.last_completed_at,
                "cache_counts": stats,
                "daily_limit": self.daily_limit,
            }

    def forge_saved(self, item_id: int, research_data: str) -> Dict[str, Any]:
        if not self.db:
            return {"ok": False, "error": "no_db"}
        try:
            self.db.set_production_assets(item_id, {}, status="queued")
        except Exception as exc:
            LOG.warning("forge status update failed: %s", exc)
        thread = threading.Thread(
            target=self._forge_worker,
            args=(item_id, research_data),
            name=f"forge-{item_id}",
            daemon=True,
        )
        thread.start()
        return {"ok": True, "status": "queued"}

    # -- internals -----------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            self._process_job(job)
            self._queue.task_done()

    def _process_job(self, job: _Job) -> None:
        with self._state_lock:
            self._state.in_flight = 1
            self._state.in_flight_hashes = [job.content_hash]
            self._state.last_run_at = datetime.now().isoformat()
        start = time.time()
        try:
            result = llm_summary.generate_creator_pack(job.item, profile=self.profile, retries=1)
            pack = result.get("pack") or {}
            ok = bool(result.get("ok"))
            issues = result.get("issues") or []
            status = "ready" if ok else "ready_with_warnings" if pack else "failed"
            error = ", ".join(issues) if issues else ""
            self.db.upsert_creator_asset(
                content_hash=job.content_hash,
                payload=pack,
                model=result.get("model", ""),
                status=status,
                error=error,
                source_title=job.item.get("title", ""),
                source_url=job.item.get("url", ""),
                schema_version=int(pack.get("schema_version") or llm_summary.CREATOR_PACK_SCHEMA_VERSION),
            )
            with self._state_lock:
                if ok:
                    self._state.enriched_today += 1
                else:
                    self._state.failed_today += 1
                    self._state.last_error = error
                self._state.last_completed_at = datetime.now().isoformat()
            LOG.info(
                "Enriched %s in %.1fs status=%s issues=%s",
                job.content_hash[:8],
                time.time() - start,
                status,
                error or "-",
            )
        except Exception as exc:
            LOG.exception("Enrichment job %s failed", job.content_hash[:8])
            try:
                self.db.mark_creator_asset_status(job.content_hash, "failed", str(exc)[:300])
            except Exception:
                pass
            with self._state_lock:
                self._state.failed_today += 1
                self._state.last_error = str(exc)[:300]
        finally:
            with self._enqueued_lock:
                self._enqueued.discard(job.content_hash)
            with self._state_lock:
                self._state.in_flight = 0
                self._state.in_flight_hashes = []
                self._state.queued = self._queue.qsize()
                self._state.queued_hashes = list(self._enqueued)[:20]

    def _forge_worker(self, item_id: int, research_data: str) -> None:
        try:
            assets = llm_summary.generate_production_assets(research_data, profile=self.profile)
            if not assets:
                self.db.set_production_assets(item_id, {}, status="failed", error="empty_response")
                LOG.warning("Forge %s produced no assets", item_id)
                return
            self.db.set_production_assets(item_id, assets, status="ready")
            LOG.info("Forge %s ready", item_id)
        except Exception as exc:
            LOG.exception("Forge %s failed", item_id)
            try:
                self.db.set_production_assets(item_id, {}, status="failed", error=str(exc)[:300])
            except Exception:
                pass
