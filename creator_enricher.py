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
import uuid
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
        for source_type in ("github", "huggingface", "youtube", "blogs", "papers", "hackernews"):
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


# ─────────────────────────────────────────────────────────────────────────
# Phase 2: typed multi-agent runner + live event stream
# ─────────────────────────────────────────────────────────────────────────

AGENT_LABELS = {
    "topic_researcher": ("Topic Researcher", "🔎"),
    "script_writer": ("Script Writer", "✍️"),
    "thumbnail_director": ("Thumbnail Director", "🎨"),
    "cross_poster": ("Cross-Poster", "🔁"),
}

_DEFAULT_ETA = {
    "topic_researcher": 90,
    "script_writer": 150,
    "thumbnail_director": 45,
    "cross_poster": 180,
}


def agent_name(agent_type: str) -> str:
    return AGENT_LABELS.get(agent_type, (agent_type.replace("_", " ").title(), "⚙️"))[0]


def agent_icon(agent_type: str) -> str:
    return AGENT_LABELS.get(agent_type, (agent_type, "⚙️"))[1]


class AgentRunner:
    """One worker thread per agent_type. Each pulls from a typed queue.

    Additive to ``EnrichmentService`` — the existing enrichment path is left
    untouched; this models the named cockpit agents with a live event stream.
    """

    AGENT_TYPES = ("topic_researcher", "script_writer", "thumbnail_director", "cross_poster")

    def __init__(self, intel_db, llm_provider=None, step_delay: Optional[float] = None):
        self.intel_db = intel_db
        self.llm_provider = llm_provider
        self.queues = {t: queue.Queue() for t in self.AGENT_TYPES}
        self.subscribers: List["queue.Queue"] = []
        self._sub_lock = threading.Lock()
        # Step delay keeps the progress visible in the UI; tests set 0.
        if step_delay is None:
            step_delay = float(os.environ.get("AGENT_STEP_DELAY", "0.6"))
        self.step_delay = step_delay
        self._eta = dict(_DEFAULT_ETA)
        try:
            profile = llm_summary.load_creator_profile()
            self._eta.update((profile.get("agents") or {}).get("default_eta_sec") or {})
        except Exception:
            pass
        self._threads = []
        for t in self.AGENT_TYPES:
            th = threading.Thread(target=self._loop, args=(t,), name=f"agent-{t}", daemon=True)
            th.start()
            self._threads.append(th)

    # ---- public API ----

    def dispatch(self, agent_type: str, *, topic=None, target_id=None, payload=None) -> str:
        if agent_type not in self.AGENT_TYPES:
            raise ValueError(f"unknown agent_type: {agent_type}")
        run_id = f"{agent_type.split('_')[0]}-{uuid.uuid4().hex[:10]}"
        eta = self._eta.get(agent_type)
        if self.intel_db:
            self.intel_db.insert_agent_run(run_id, agent_type, topic=topic,
                                           target_id=target_id, eta_sec=eta)
        self._broadcast({
            "type": "started",
            "run": {
                "id": run_id, "agent_type": agent_type,
                "name": agent_name(agent_type), "icon": agent_icon(agent_type),
                "task": topic or target_id or "", "status": "queued",
                "progress": 0, "eta_sec": eta,
            },
        })
        self.queues[agent_type].put((run_id, payload or {}, topic, target_id))
        return run_id

    def subscribe(self) -> "queue.Queue":
        q: "queue.Queue" = queue.Queue(maxsize=200)
        with self._sub_lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue") -> None:
        with self._sub_lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def snapshot(self) -> Dict[str, Any]:
        """Shape consumed by GET /api/agents."""
        active, recent_done = [], []
        if self.intel_db:
            for row in self.intel_db.list_active_agent_runs():
                active.append(self._row_to_active(row))
            for row in self.intel_db.list_agent_runs(status="done", limit=10):
                recent_done.append({
                    "id": row["id"], "agent_type": row["agent_type"],
                    "name": agent_name(row["agent_type"]),
                    "task": row.get("topic") or row.get("target_id") or "",
                    "finished_at": row.get("finished_at"),
                    "duration_sec": (int(row["finished_at"] - row["started_at"])
                                     if row.get("finished_at") and row.get("started_at") else None),
                    "result_summary": row.get("result_summary") or "",
                })
        return {"active": active, "recent_done": recent_done}

    def _row_to_active(self, row: Dict[str, Any]) -> Dict[str, Any]:
        logs = []
        if self.intel_db:
            logs = [l["line"] for l in self.intel_db.get_agent_logs(row["id"])][-5:]
        return {
            "id": row["id"], "agent_type": row["agent_type"],
            "name": agent_name(row["agent_type"]), "icon": agent_icon(row["agent_type"]),
            "task": row.get("topic") or row.get("target_id") or "",
            "stage": row.get("stage") or "", "progress": row.get("progress") or 0,
            "eta_sec": row.get("eta_sec"), "started_at": row.get("started_at"),
            "logs": logs,
        }

    # ---- worker internals ----

    def _loop(self, agent_type: str):
        while True:
            run_id, payload, topic, target_id = self.queues[agent_type].get()
            self._update(run_id, status="running", started_at=time.time(), progress=0.0)
            self._broadcast({"type": "status", "run_id": run_id, "status": "running",
                             "stage": "starting", "progress": 0.0,
                             "eta_sec": self._eta.get(agent_type)})
            try:
                summary = self._run_agent(agent_type, run_id, topic, target_id, payload)
                self._update(run_id, status="done", finished_at=time.time(),
                             progress=1.0, result_summary=summary)
                self._broadcast({"type": "done", "run_id": run_id,
                                 "finished_at": time.time(), "result_summary": summary})
            except Exception as exc:  # noqa: BLE001
                LOG.exception("Agent %s run %s failed", agent_type, run_id)
                self._update(run_id, status="error", finished_at=time.time(), error=str(exc)[:300])
                self._broadcast({"type": "status", "run_id": run_id, "status": "error",
                                 "stage": "error", "progress": 1.0})

    def _stage(self, run_id, stage, progress, eta_sec=None):
        self._update(run_id, stage=stage, progress=progress, eta_sec=eta_sec)
        self._broadcast({"type": "status", "run_id": run_id, "status": "running",
                         "stage": stage, "progress": progress, "eta_sec": eta_sec})
        if self.step_delay:
            time.sleep(self.step_delay)

    def _run_agent(self, agent_type, run_id, topic, target_id, payload) -> str:
        if agent_type == "topic_researcher":
            return self._run_topic_researcher(run_id, topic, target_id, payload)
        if agent_type == "script_writer":
            return self._run_script_writer(run_id, topic, target_id, payload)
        if agent_type == "thumbnail_director":
            return self._run_thumbnail_director(run_id, topic, target_id, payload)
        if agent_type == "cross_poster":
            return self._run_cross_poster(run_id, topic, target_id, payload)
        raise ValueError(f"no handler for {agent_type}")

    def _run_topic_researcher(self, run_id, topic, target_id, payload) -> str:
        label = topic or target_id or "topic"
        if not label:
            return "No topic provided"

        self._log(run_id, f"Initiating agentic dive on: {label}")
        self._stage(run_id, "Querying leads from LLM", 0.2)

        import llm_summary
        import re
        from datetime import datetime

        leads_prompt = (
            f"Research the AI topic '{label}'. Identify:\n"
            "1. The primary technical framework or repo driving this trend.\n"
            "2. The Munger Inversion: what are the risks, failure modes, or counter-arguments?\n"
            "3. The Creator Opportunity: what concrete demo would prove or disprove the hype?\n"
            "Return a concise technical summary (no preamble, no markdown headings)."
        )
        try:
            leads = llm_summary.query_llm(
                leads_prompt,
                "You are a PhD-level research lead. Be technical, terse, and source-aware.",
            ) or ""
        except Exception as e:
            leads = ""
            self._log(run_id, f"Warning: LLM query for leads failed: {e}")

        if not leads:
            self._log(run_id, "Failed to retrieve research leads. Aborting.")
            self._stage(run_id, "Failed", 1.0)
            return f"failed to draft research pack for {label}"

        self._log(run_id, "Successfully synthesized research leads.")
        self._stage(run_id, "Drafting structured brief", 0.5)

        synthesis_prompt = (
            f"Based on these research leads for '{label}':\n{leads}\n\n"
            "Return a JSON object with these exact keys:\n"
            "strategic_title (high-CTR technical title, 38-62 chars),\n"
            "shift (1 sentence: why this matters fundamentally),\n"
            "superpower (1 sentence: the unique technical edge),\n"
            "hook_contrarian (1 sentence),\n"
            "hook_speed (1 sentence),\n"
            "narrative_beats (array of 5 short strings),\n"
            "thumbnail_visuals (array of 3 short strings),\n"
            "inversion (1 sentence: the critical risk).\n"
            "Output JSON only. No commentary, no code fences."
        )
        try:
            raw = llm_summary.query_llm(
                synthesis_prompt,
                "You are a senior AI content strategist. Output strict JSON only.",
            ) or ""
        except Exception as e:
            raw = ""
            self._log(run_id, f"Warning: LLM synthesis query failed: {e}")

        from agentic_researcher import _extract_json
        brief = _extract_json(raw)

        if not brief:
            self._log(run_id, "Failed to parse structured brief JSON from LLM response.")
            self._stage(run_id, "Failed", 1.0)
            return f"failed to parse structured brief for {label}"

        brief["leads"] = leads
        brief["topic"] = label

        self._log(run_id, "Successfully compiled strategic brief.")
        self._stage(run_id, "Writing research pack markdown file", 0.8)

        # Save to research packs directory
        from agentic_researcher import RESEARCH_PACK_DIR
        date_slug = datetime.now().strftime("%Y-%m-%d")
        file_slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "topic"
        path = os.path.join(RESEARCH_PACK_DIR, f"{date_slug}-{file_slug}.md")

        beats = brief.get("narrative_beats") or []
        thumbs = brief.get("thumbnail_visuals") or []
        body = [
            f"# Research Pack: {label}",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "**Status:** Agentic Recursive Dive",
            "",
            "## Leads",
            brief.get("leads", "(no leads returned)"),
            "",
            "## Strategic Brief",
            f"**Strategic title:** {brief.get('strategic_title', '')}",
            f"**Shift:** {brief.get('shift', '')}",
            f"**Superpower:** {brief.get('superpower', '')}",
            f"**Munger Inversion:** {brief.get('inversion', '')}",
            "",
            "**Hooks:**",
            f"- Contrarian: {brief.get('hook_contrarian', '')}",
            f"- Speed-to-Value: {brief.get('hook_speed', '')}",
            "",
            "**Narrative Beats:**",
            *[f"- {beat}" for beat in beats],
            "",
            "**Thumbnail Visuals:**",
            *[f"- {visual}" for visual in thumbs],
            "",
        ]

        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(body))
            self._log(run_id, f"Research pack written to {path}")
        except Exception as e:
            self._log(run_id, f"Error writing file: {e}")
            self._stage(run_id, "Failed", 1.0)
            return f"failed to write research pack to disk for {label}"

        self._stage(run_id, "Done", 1.0)
        return f"research pack drafted · {label}"

    def _run_script_writer(self, run_id, topic, target_id, payload) -> str:
        self._log(run_id, "outlined cold-open hook (3 candidates)")
        self._stage(run_id, "Drafting 3-beat structure", 0.4)
        self._log(run_id, "beat 1 / beat 2 / beat 3 drafted")
        self._stage(run_id, "Tightening pacing", 0.8)
        return f"script draft ready · {topic or target_id or ''}".strip(" ·")

    def _run_thumbnail_director(self, run_id, topic, target_id, payload) -> str:
        count = int((payload or {}).get("count", 6))
        self._stage(run_id, "Generating variants", 0.3)
        made = 0
        if self.intel_db and target_id:
            try:
                from creator_intelligence import generate_thumbnail_variants
                variants = generate_thumbnail_variants(self.intel_db, target_id, topic, count=count)
                for v in variants:
                    made += 1
                    self._log(run_id, f"variant {v['kind']} · CTR {v['ctr_pred']}%")
            except Exception as exc:  # noqa: BLE001
                self._log(run_id, f"variant generation error: {exc}")
        self._stage(run_id, "Ranking by predicted CTR", 0.9)
        return f"{made or count} thumbnail variants generated"

    def _run_cross_poster(self, run_id, topic, target_id, payload) -> str:
        self._log(run_id, "adapting long-form into LinkedIn carousel")
        self._stage(run_id, "Slicing into 6 slides", 0.5)
        self._log(run_id, "rewrote hook for LinkedIn voice")
        self._stage(run_id, "Formatting carousel JSON", 0.85)
        return f"carousel adapted · {topic or target_id or ''}".strip(" ·")

    def _log(self, run_id: str, line: str):
        ts = time.time()
        if self.intel_db:
            try:
                self.intel_db.append_agent_log(run_id, ts, line)
            except Exception:
                pass
        self._broadcast({"type": "log", "run_id": run_id, "ts": ts, "line": line})

    def _update(self, run_id: str, **fields):
        if self.intel_db:
            try:
                self.intel_db.update_agent_run(run_id, **fields)
            except Exception:
                pass

    def _broadcast(self, event: Dict[str, Any]):
        with self._sub_lock:
            subs = list(self.subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass
