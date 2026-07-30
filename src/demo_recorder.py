#!/usr/bin/env python3
"""Record REAL terminal demos with VHS (charmbracelet) for factory shorts.

Generates a .tape script whose commands actually execute at record time
(live curl against the GitHub / HN APIs), records them to an mp4, and hands
the file to the Remotion composition, which plays it inside the terminal
card instead of the synthetic typed-text simulation.

VHS is an optional dependency: when the `vhs` binary is missing (or the
source kind has no good command story) record_demo returns None and the
renderer falls back to the evidence-driven synthetic card.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

_RECORD_TIMEOUT = 120

_TAPE_HEADER = """Output "{output}"
Set FontSize 22
Set Width 960
Set Height 470
Set Padding 16
Set WindowBar Rings
Set Theme "Catppuccin Mocha"
"""


def vhs_available() -> bool:
    return shutil.which("vhs") is not None


def _tape_commands(evidence: Dict[str, Any]) -> List[str]:
    """Real, fast, non-destructive commands appropriate to the source."""
    kind = evidence.get("source_kind") or ""
    url = evidence.get("url") or ""
    excerpt = evidence.get("excerpt") or ""

    if kind == "github":
        m = re.search(r"github\.com/([\w.-]+/[\w.-]+)", url)
        if not m:
            return []
        repo = m.group(1)
        cmds = [
            f"curl -s https://api.github.com/repos/{repo} | jq '{{stars: .stargazers_count, forks: .forks_count, language: .language, license: .license.spdx_id}}'",
        ]
        pkg = re.search(r"\bnpm (?:i|install)\s+([@\w./-]+)", excerpt)
        if pkg:
            cmds.append(f"npm view {pkg.group(1)} name version description 2>/dev/null | head -6")
        return cmds

    if kind == "hackernews":
        m = re.search(r"id=(\d+)", url)
        if not m:
            return []
        return [
            f"curl -s https://hn.algolia.com/api/v1/items/{m.group(1)} | jq '{{title: .title, points: .points, comments: (.children | length)}}'",
        ]

    return []


def build_tape(evidence: Dict[str, Any], output_path: str) -> Optional[str]:
    commands = _tape_commands(evidence)
    if not commands:
        return None
    lines = [_TAPE_HEADER.format(output=output_path)]
    for cmd in commands:
        escaped = cmd.replace('"', '\\"')
        lines.append(f'Type "{escaped}"')
        lines.append("Sleep 500ms")
        lines.append("Enter")
        lines.append("Sleep 4s")
    lines.append("Sleep 2s")
    return "\n".join(lines) + "\n"


def record_demo(evidence: Dict[str, Any], output_path: str) -> Optional[str]:
    """Record a real terminal demo mp4 for this evidence. None on any failure."""
    if not vhs_available():
        return None
    tape = build_tape(evidence, output_path)
    if not tape:
        return None

    with tempfile.NamedTemporaryFile("w", suffix=".tape", delete=False) as f:
        f.write(tape)
        tape_path = f.name
    try:
        subprocess.run(
            ["vhs", tape_path],
            check=True, capture_output=True, timeout=_RECORD_TIMEOUT,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
        return None
    except Exception as e:
        print(f"[demo_recorder] vhs recording failed: {e}")
        return None
    finally:
        os.unlink(tape_path)
