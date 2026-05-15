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

    def wait_for_cache(self, hash_: str, timeout_seconds: int = 180, poll: float = 2.0) -> Optional[Dict[str, Any]]:
        """Block until the asset is ready (or fails). Used by the agentic pipeline."""
        if not self.db:
            return None
        deadline = time.time() + max(5, int(timeout_seconds))
        while time.time() < deadline:
            row = self.db.get_creator_asset(hash_)
            if row and row.get("status") in {"ready", "ready_with_warnings"}:
                return row
            if row and row.get("status") == "failed":
                return row
            time.sleep(poll)
        return self.db.get_creator_asset(hash_)

    def ensure_pack(self, item: Dict[str, Any], timeout_seconds: int = 180) -> Optional[Dict[str, Any]]:
        """Enqueue (if needed) and wait for the creator pack to land in cache."""
        if not self.db:
            return None
        hash_ = content_hash(item)
        existing = self.db.get_creator_asset(hash_)
        if existing and existing.get("status") in {"ready", "ready_with_warnings"}:
            return existing
        self.enqueue(item)
        return self.wait_for_cache(hash_, timeout_seconds=timeout_seconds)

    def run_cluster_pipeline(
        self,
        clusters: List[Dict[str, Any]],
        scored_data: Dict[str, Any],
        automation: Dict[str, Any],
        recursive_dive_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Walk clusters through enrich -> recursive dive -> save -> forge.

        Caller decides whether to invoke this synchronously (cron) or fire it
        from a background thread (manual button press). The function itself
        does not spawn threads.
        """
        if not self.db:
            return {"ok": False, "error": "no_db"}

        min_sources = int(automation.get("min_cluster_sources", 3))
        research_threshold = int(automation.get("auto_research_cluster_score", 75))
        script_threshold = int(automation.get("auto_script_ready_score", 85))
        forge_threshold = int(automation.get("auto_forge_score", 90))
        max_promotions = int(automation.get("max_auto_promotions_per_day", 3))
        timeout_seconds = int(automation.get("enrichment_wait_seconds", 180))

        item_lookup: Dict[str, Dict[str, Any]] = {}
        for source_type in ("github", "huggingface", "youtube", "blogs", "papers"):
            for raw_item in scored_data.get(source_type, []) or []:
                url = raw_item.get("url")
                if url:
                    item_lookup[url] = raw_item

        promoted: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        for cluster in clusters:
            if len(promoted) >= max_promotions:
                skipped.append({"topic": cluster.get("topic"), "reason": "daily_cap"})
                continue
            if cluster.get("source_count", 0) < min_sources:
                skipped.append({"topic": cluster.get("topic"), "reason": "few_sources"})
                continue
            score = float(cluster.get("creator_score") or 0)
            if score < research_threshold:
                skipped.append({"topic": cluster.get("topic"), "reason": "low_score"})
                continue

            related = cluster.get("related_items") or []
            seed = next(
                (item_lookup.get(row.get("url")) for row in related if item_lookup.get(row.get("url"))),
                None,
            )
            if not seed:
                skipped.append({"topic": cluster.get("topic"), "reason": "no_seed_item"})
                continue

            try:
                cached = self.ensure_pack(seed, timeout_seconds=timeout_seconds)
            except Exception as exc:
                LOG.exception("ensure_pack failed for %s", cluster.get("topic"))
                skipped.append({"topic": cluster.get("topic"), "reason": f"enrich_error:{exc}"})
                continue
            pack = (cached or {}).get("payload") or {}

            dive_result: Dict[str, Any] = {}
            if recursive_dive_fn:
                try:
                    dive_result = recursive_dive_fn(cluster.get("topic", "")) or {}
                except Exception as exc:
                    LOG.exception("recursive_dive failed for %s", cluster.get("topic"))
                    dive_result = {"error": str(exc)[:300]}

            target_status = "idea"
            if score >= script_threshold:
                target_status = "script_ready"

            saved_id = self._save_cluster_item(cluster, seed, pack, dive_result, target_status)
            promotion = {
                "topic": cluster.get("topic"),
                "saved_id": saved_id,
                "status": target_status,
                "creator_score": score,
            }

            if saved_id and score >= forge_threshold:
                research_blob = self._build_forge_blob(cluster, seed, pack, dive_result)
                forge_result = self.forge_saved(saved_id, research_blob)
                promotion["forge"] = forge_result.get("status") or "started"

            promoted.append(promotion)

        LOG.info("Cluster pipeline complete: %d promoted, %d skipped", len(promoted), len(skipped))
        return {"ok": True, "promoted": promoted, "skipped": skipped}

    def _save_cluster_item(
        self,
        cluster: Dict[str, Any],
        seed: Dict[str, Any],
        pack: Dict[str, Any],
        dive: Dict[str, Any],
        status: str,
    ) -> Optional[int]:
        titles = pack.get("suggested_titles") or {}
        working_title = (
            titles.get("practical")
            or dive.get("strategic_title")
            or cluster.get("topic")
            or seed.get("title")
            or "Untitled"
        )
        hook = pack.get("hook") or dive.get("hook_contrarian") or seed.get("title", "")
        outline = pack.get("three_key_points") or dive.get("narrative_beats") or []
        thumbnails = pack.get("thumbnail_text") or []
        notes_lines = [
            f"Topic: {cluster.get('topic')}",
            f"Cluster score: {cluster.get('creator_score')}",
            f"Sources: {', '.join(cluster.get('sources', []))}",
        ]
        if dive.get("shift"):
            notes_lines.append(f"Shift: {dive.get('shift')}")
        if dive.get("inversion"):
            notes_lines.append(f"Inversion: {dive.get('inversion')}")
        if pack.get("caveats"):
            notes_lines.append(f"Caveats: {pack.get('caveats')}")

        item = {
            "title": working_title,
            "url": seed.get("url"),
            "source": "Agentic Researcher",
            "source_type": seed.get("source_type") or "research",
            "category": cluster.get("topic"),
            "signal_score": int(seed.get("signal_score") or 0),
            "creator_score": int(cluster.get("creator_score") or 0),
            "pipeline_type": "creator",
            "status": status,
            "working_title": working_title,
            "hook": hook,
            "format": cluster.get("best_content_format") or pack.get("visual_idea") or "Deep Dive",
            "outline": outline,
            "sources": [row.get("url") for row in cluster.get("related_items", []) if row.get("url")],
            "thumbnail_text": ", ".join(thumbnails) if thumbnails else "",
            "notes": "\n".join(notes_lines),
            "tags": ["agentic", cluster.get("topic", "").lower().replace(" ", "-")],
            "priority": "high" if status == "script_ready" else "medium",
        }
        try:
            return self.db.save_item(item)
        except Exception as exc:
            LOG.exception("save_item failed for %s", cluster.get("topic"))
            return None

    def _build_forge_blob(
        self,
        cluster: Dict[str, Any],
        seed: Dict[str, Any],
        pack: Dict[str, Any],
        dive: Dict[str, Any],
    ) -> str:
        lines = [
            f"TOPIC: {cluster.get('topic')}",
            f"SEED TITLE: {seed.get('title', '')}",
            f"SEED URL: {seed.get('url', '')}",
            f"CLUSTER SCORE: {cluster.get('creator_score')} | SOURCES: {', '.join(cluster.get('sources', []))}",
            "",
            "CREATOR PACK:",
            f"- Hook: {pack.get('hook', '')}",
            f"- Insight: {pack.get('insight', '')}",
            f"- Demo: {pack.get('demo_segment', '')}",
            f"- Caveats: {pack.get('caveats', '')}",
            f"- Three key points: {' | '.join(pack.get('three_key_points', []) or [])}",
            "",
            "RECURSIVE DIVE:",
            f"- Strategic title: {dive.get('strategic_title', '')}",
            f"- Shift: {dive.get('shift', '')}",
            f"- Superpower: {dive.get('superpower', '')}",
            f"- Inversion: {dive.get('inversion', '')}",
            f"- Narrative beats: {' | '.join(dive.get('narrative_beats', []) or [])}",
            "",
            "RELATED EVIDENCE:",
        ]
        for row in (cluster.get("related_items") or [])[:6]:
            lines.append(f"- {row.get('source_label') or row.get('source_type')}: {row.get('title', '')} ({row.get('url', '')})")
        return "\n".join(line for line in lines if line is not None)

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
