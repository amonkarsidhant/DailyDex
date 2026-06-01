#!/usr/bin/env python3
"""Creator Central — autonomous content factory.

Runs unattended (launchd ``com.dailydex.studio``):

  1. read the latest scored data + build topic clusters
  2. pick the top N stories by creator score
  3. for each story: synthesize a research pack, optionally deepen it with a
     model CLI (autonomous research), then run every format skill
     (shorts / video / podcast / blog), persisting each to ``studio_content``

No manual trigger. Whatever model CLI is available on the machine does the work
(see ``cli_registry``). Re-running regenerates the same stories in place.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from typing import Dict, List

import cli_registry
import studio
from cli_registry import GEN_TIMEOUT
from creator_intelligence import build_topic_clusters

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
SCORED_DATA_FILE = os.environ.get("SCORED_DATA_FILE", os.path.join(DATA_DIR, "data_scored.json"))
TOP_N = int(os.environ.get("STUDIO_TOP_N", "2"))
DEEP_RESEARCH = os.environ.get("STUDIO_DEEP_RESEARCH", "1") == "1"


_log_callback = None


def _log(msg: str) -> None:
    formatted = f"[studio_job {time.strftime('%H:%M:%S')}] {msg}"
    print(formatted, flush=True)
    global _log_callback
    if _log_callback:
        try:
            _log_callback(formatted)
        except Exception:
            pass


def _load_scored() -> Dict:
    try:
        with open(SCORED_DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _base_research(cluster: Dict) -> str:
    """Synthesize a plain research pack from a cluster's fields + sources."""
    lines = [
        f"TOPIC: {cluster['topic']}",
        f"Why it's a story: {cluster.get('why_this_is_a_story', '')}",
        f"Recommended angle: {cluster.get('recommended_angle', '')}",
        f"Across sources: {', '.join(cluster.get('sources', []))}",
        f"Creator score: {cluster.get('creator_score')} · signal {cluster.get('average_signal_score')}",
        "",
        "SOURCE ITEMS:",
    ]
    for it in cluster.get("related_items", [])[:6]:
        lines.append(
            f"- [{it.get('source_type')}] {it.get('title')} "
            f"(signal {it.get('signal_score')}) {it.get('url', '')}".rstrip()
        )
    return "\n".join(lines)


def _deepen(research: str, topic: str) -> str:
    """Optional autonomous research pass: expand the pack via a model CLI."""
    if not DEEP_RESEARCH:
        return research
    try:
        from agentic_researcher import recursive_dive
        _log(f"  initiating two-stage agentic recursive dive on: {topic}...")
        brief = recursive_dive(topic)
        if brief and ("strategic_title" in brief or "leads" in brief):
            lines = [
                f"\n--- DEEP AGENTIC RESEARCH DIVE ---",
                f"### Strategic Title: {brief.get('strategic_title', '')}",
                f"**Fundamentally why it matters:** {brief.get('shift', '')}",
                f"**Unique superpower:** {brief.get('superpower', '')}",
                f"**Munger Inversion (Critical Risk):** {brief.get('inversion', '')}",
                "",
                "**Potential Hooks:**",
                f"- Contrarian perspective: {brief.get('hook_contrarian', '')}",
                f"- Speed-to-value hook: {brief.get('hook_speed', '')}",
                "",
                "**Narrative Beats / Chapters:**"
            ]
            for i, beat in enumerate(brief.get("narrative_beats") or [], 1):
                lines.append(f"{i}. {beat}")
            
            lines.append("\n**Visuals & Thumbnail Angles:**")
            for visual in brief.get("thumbnail_visuals") or []:
                lines.append(f"- {visual}")
                
            lines.append(f"\n**Raw Leads Summary:**\n{brief.get('leads', '')}")
            
            deep_res = "\n".join(lines)
            _log(f"  agentic recursive dive completed successfully.")
            return f"{research}\n{deep_res}"
    except Exception as e:
        _log(f"  warn: agentic recursive dive failed: {e}. Falling back to default deepening...")
        
    system = (
        "You are a research analyst for an AI creator. Expand the notes into a tight "
        "research brief: the core claim, 3-5 concrete facts/benchmarks, who it matters "
        "for, one counterpoint, and one demoable angle. Be specific; no fluff."
    )
    prompt = f"Topic: {topic}\n\nNotes:\n{research}\n\nWrite the research brief."
    res = cli_registry.generate(prompt, system)
    if res["text"]:
        _log(f"  research deepened via {res['provider']} ({res['elapsed_ms']}ms)")
        return f"{research}\n\n--- DEEP RESEARCH ({res['provider']}) ---\n{res['text']}"
    return research



def run(intel_db=None, top_n: int = None, slugs: List[str] = None, log_fn=None) -> Dict:
    global _log_callback
    _log_callback = log_fn
    top_n = top_n if top_n is not None else TOP_N
    if intel_db is None:
        from data_models import IntelligenceDB
        intel_db = IntelligenceDB()

    avail = cli_registry.available_providers(force=True)  # re-probe fresh each run
    _log(f"providers available: {avail or 'NONE'}")
    if not avail:
        _log("no model CLI available — aborting")
        return {"ok": False, "error": "no_provider", "stories": 0}

    scored   = _load_scored()
    clusters = build_topic_clusters(scored, intel_db=intel_db)
    if not clusters:
        _log("no clusters — run a refresh first")
        return {"ok": False, "error": "no_clusters", "stories": 0}

    if slugs:
        targets = [c for c in clusters if c["slug"] in slugs]
        _log(f"generating {len(targets)} specific stories (from slugs: {slugs})")
    else:
        targets = clusters[:top_n]
    _log(f"generating {len(targets)} stories x {len(studio.FORMAT_ORDER)} formats (parallel)")
    profile = studio.load_profile()
    made    = 0

    for cluster in targets:
        story_key = cluster["slug"]
        topic     = cluster["topic"]
        src_url   = (cluster.get("related_items") or [{}])[0].get("url", "")
        _log(f"STORY '{topic}' ({story_key})")

        research = _deepen(_base_research(cluster), topic)

        # Mark all formats as "generating" upfront so the UI shows activity immediately
        for fmt in studio.FORMAT_ORDER:
            try:
                intel_db.studio_set_status(story_key, topic, fmt, "generating",
                                           research=research, source_url=src_url)
            except Exception as e:
                _log(f"  warn: could not set status for {fmt}: {e}")

        # ── Parallel format generation ────────────────────────────────────────
        # Each format runs in its own thread. Results are saved to DB as they
        # complete. Uses the same thread count as there are formats so they all
        # start immediately.
        import concurrent.futures
        import threading

        _db_lock = threading.Lock()  # SQLite is not fully thread-safe for writes

        def _generate_and_save(fmt: str) -> Dict:
            result = studio.generate_format(fmt, research, profile)
            # Save result to DB (guarded by lock)
            with _db_lock:
                try:
                    intel_db.studio_save_result(story_key, topic, fmt, result)
                except Exception as db_err:
                    _log(f"  warn: DB save failed for {fmt}: {db_err}")
            mark = "ok" if result["ok"] else f"FAIL({result.get('error')})"
            _log(f"  {fmt:8} {mark} via {result.get('provider')} {result.get('elapsed_ms')}ms")
            return result

        max_workers = min(len(studio.FORMAT_ORDER), 4)
        results: List[Dict] = []

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_generate_and_save, fmt): fmt for fmt in studio.FORMAT_ORDER}
                for future in concurrent.futures.as_completed(futures):
                    fmt = futures[future]
                    try:
                        res = future.result(timeout=GEN_TIMEOUT + 30)
                        results.append(res)
                        if res["ok"]:
                            made += 1
                    except Exception as exc:
                        _log(f"  {fmt:8} EXCEPTION: {exc}")
                        # Save a failure record so the UI shows an error state
                        with _db_lock:
                            try:
                                intel_db.studio_save_result(
                                    story_key, topic, fmt,
                                    {"format": fmt, "ok": False, "error": str(exc),
                                     "body": "", "provider": None, "model": "", "elapsed_ms": 0}
                                )
                            except Exception:
                                pass
        except Exception as pool_err:
            # Fallback to sequential if threading explodes (shouldn't happen)
            _log(f"  parallel pool failed ({pool_err}) — falling back to sequential")
            for fmt in studio.FORMAT_ORDER:
                result = studio.generate_format(fmt, research, profile)
                intel_db.studio_save_result(story_key, topic, fmt, result)
                if result["ok"]:
                    made += 1
                mark = "ok" if result["ok"] else f"FAIL({result.get('error')})"
                _log(f"  {fmt:8} {mark} via {result.get('provider')} {result.get('elapsed_ms')}ms")

    _log(f"done — {made} assets generated across {len(targets)} stories")
    return {"ok": True, "stories": len(targets), "assets": made}


def main() -> int:
    _log("start")
    try:
        run()
        return 0
    except Exception:
        print("[studio_job] FAILED:\n" + traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
