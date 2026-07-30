"""Static contracts for the production legacy live research desk."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_today_is_live_desk_not_static_recommendation():
    source = (ROOT / "src/static/cockpit/src/PulseView.jsx").read_text(encoding="utf-8")
    assert "Live research desk" in source
    assert "window.DDX.compile" in source
    assert "why_this_is_a_story" not in source
    assert "recommended_angle" not in source
    assert "Render short" not in source
    assert "const [activeSlug, setActiveSlug] = useState(null)" in source
    assert "Nothing compiles until you choose" in source


def test_floating_copilot_is_not_mounted():
    source = (ROOT / "src/static/cockpit/src/App.jsx").read_text(encoding="utf-8")
    assert "<CopilotDock" not in source
    assert "copilot:  CopilotChatView" not in source


def test_compile_bridge_parses_streamed_post_events():
    source = (ROOT / "src/static/cockpit/cockpit-live.js").read_text(encoding="utf-8")
    assert 'fetch("/api/compile"' in source
    assert "response.body.getReader()" in source
    assert 'method: "POST"' in source
    assert "if (!sawTerminal)" in source


def test_live_desk_has_explicit_mobile_layout():
    css = (ROOT / "src/static/cockpit/cockpit.css").read_text(encoding="utf-8")
    assert ".live-desk-layout" in css
    assert ".signal-queue__list { display: flex" in css
    assert ".desk-prompt__input { grid-template-columns: minmax(0, 1fr); }" in css


def test_research_uses_operational_reality_not_finance_branding():
    source = (ROOT / "src/static/cockpit/src/ResearchView.jsx").read_text(encoding="utf-8")
    assert 'title="Operational Reality Check"' in source
    assert 'src="Failure-boundary analysis"' in source
    assert "Counterpoints & Munger" not in source
    assert "## Munger Inversion" not in source
