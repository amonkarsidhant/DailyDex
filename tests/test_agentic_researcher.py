import json

import agentic_researcher


def test_recursive_dive_requests_operational_reality_check(monkeypatch):
    prompts = []
    responses = iter([
        "The repository exposes tool activity but has no documented recovery path.",
        json.dumps({
            "strategic_title": "The agent failure path nobody demonstrates",
            "shift": "Operability now matters more than another feature list.",
            "superpower": "Tool activity is observable.",
            "hook_contrarian": "The demo is the easy part.",
            "hook_speed": "Find the failure boundary in five minutes.",
            "narrative_beats": ["claim", "setup", "failure", "recovery", "decision"],
            "thumbnail_visuals": ["failure trace", "recovery gap", "decision matrix"],
            "operational_reality": (
                "The workflow fails when tool output is unavailable. Detection depends on trace visibility, "
                "and the sources do not document automatic recovery or an enterprise runbook."
            ),
        }),
    ])

    def fake_query(prompt, system):
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(agentic_researcher.llm_summary, "query_llm", fake_query)
    brief = agentic_researcher.recursive_dive("Inspectable agents")

    assert "Operational Reality Check" in prompts[0]
    assert "failure boundary" in prompts[1]
    assert brief["operational_reality"].startswith("The workflow fails")
