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
from creator_intelligence import build_topic_clusters

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
SCORED_DATA_FILE = os.environ.get("SCORED_DATA_FILE", os.path.join(DATA_DIR, "data_scored.json"))
TOP_N = int(os.environ.get("STUDIO_TOP_N", "2"))
DEEP_RESEARCH = os.environ.get("STUDIO_DEEP_RESEARCH", "1") == "1"


def _log(msg: str) -> None:
    print(f"[studio_job {time.strftime('%H:%M:%S')}] {msg}", flush=True)


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


def run(intel_db=None, top_n: int = None) -> Dict:
    top_n = top_n if top_n is not None else TOP_N
    if intel_db is None:
        from data_models import IntelligenceDB
        intel_db = IntelligenceDB()

    avail = cli_registry.available_providers(force=True)  # re-probe fresh each run
    _log(f"providers available: {avail or 'NONE'}")
    if not avail:
        _log("no model CLI available — aborting")
        return {"ok": False, "error": "no_provider", "stories": 0}

    scored = _load_scored()
    clusters = build_topic_clusters(scored, intel_db=intel_db)
    if not clusters:
        _log("no clusters — run a refresh first")
        return {"ok": False, "error": "no_clusters", "stories": 0}

    targets = clusters[:top_n]
    _log(f"generating {len(targets)} stories x {len(studio.FORMAT_ORDER)} formats")
    profile = studio.load_profile()
    made = 0

    for cluster in targets:
        story_key = cluster["slug"]
        topic = cluster["topic"]
        src_url = (cluster.get("related_items") or [{}])[0].get("url", "")
        _log(f"STORY '{topic}' ({story_key})")

        research = _deepen(_base_research(cluster), topic)
        for fmt in studio.FORMAT_ORDER:
            intel_db.studio_set_status(story_key, topic, fmt, "generating",
                                       research=research, source_url=src_url)
            result = studio.generate_format(fmt, research, profile)
            intel_db.studio_save_result(story_key, topic, fmt, result)
            made += 1 if result["ok"] else 0
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
