"""Opt-in Playwright acceptance tests for the production cockpit UI.

Run against a local app with:
RUN_BROWSER_TESTS=1 .venv/bin/python -m pytest tests/test_live_desk_browser.py -q
"""

import json
import os
import re
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BROWSER_TESTS") != "1",
    reason="Set RUN_BROWSER_TESTS=1 against a running local DailyDex app.",
)

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright


BASE_URL = os.environ.get("DAILYDEX_BROWSER_BASE_URL", "http://127.0.0.1:8888")
ARTIFACT_DIR = Path(os.environ.get(
    "DAILYDEX_BROWSER_ARTIFACT_DIR",
    "/var/folders/49/4936ct353qz9545544kx7d6r0000gn/T/opencode/dailydex-browser",
))


def _result():
    evidence_ids = ["E1"]
    return {
        "story_title": "The inspectable agent stack worth testing",
        "story_title_evidence_ids": evidence_ids,
        "editorial_thesis": "The useful shift is inspectability, not another agent launch.",
        "editorial_thesis_evidence_ids": evidence_ids,
        "audience_payoff": "Builders get a concrete verification workflow.",
        "audience_payoff_evidence_ids": evidence_ids,
        "hook": "This agent matters because you can inspect what it does.",
        "hook_evidence_ids": evidence_ids,
        "angles": [
            {"name": "Inspect it", "take": "Trace one tool call.", "evidence_ids": evidence_ids},
            {"name": "Test it", "take": "Run the smallest useful task.", "evidence_ids": evidence_ids},
            {"name": "Stress it", "take": "Show the failure boundary.", "evidence_ids": evidence_ids},
        ],
        "recommended_format": "Technical demo",
        "format_reason": "The workflow can be demonstrated directly.",
        "format_reason_evidence_ids": evidence_ids,
        "demo_idea": "Trace one request from prompt to tool result.",
        "demo_evidence_ids": evidence_ids,
        "titles": [
            "The AI agent workflow you can inspect",
            "Test this before trusting an AI agent",
            "A practical inspectability test for agents",
        ],
        "titles_evidence_ids": evidence_ids,
        "key_facts": [
            {"claim": "The source documents an agent workflow.", "evidence_ids": evidence_ids},
            {"claim": "The implementation exposes tool activity.", "evidence_ids": evidence_ids},
            {"claim": "The project targets builders.", "evidence_ids": evidence_ids},
        ],
        "caveats": ["Performance has not been independently benchmarked."],
        "caveats_evidence_ids": evidence_ids,
    }


def _sse_success():
    record = {
        "id": "E1", "title": "Source repository", "url": "https://example.com/source",
        "source_type": "github", "facts": ["The repository documents the workflow"],
        "quotes": [], "excerpt": "The tool activity is inspectable.", "signal_score": 88,
    }
    events = [
        {"type": "meta", "cache_hit": False},
        {"type": "status", "phase": "evidence", "message": "Reading live sources."},
        {"type": "evidence", "record": record},
        {"type": "token", "token": '{"story_title":"draft"}'},
        {"type": "result", "result": _result(), "model": "test:structured", "cache_hit": False,
         "generated_at": 1_750_000_000, "locked_until": 1_750_086_400},
        {"type": "done"},
    ]
    return "retry: 3000\n\n" + "".join(
        f"data: {json.dumps(event)}\n\n" for event in events
    )


@pytest.fixture(scope="module")
def browser():
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as runner:
        instance = runner.chromium.launch(headless=True)
        yield instance
        instance.close()


def _page(browser, viewport=None):
    context = browser.new_context(viewport=viewport or {"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    failed_requests = []
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("requestfailed", lambda request: failed_requests.append(
        f"{request.method} {request.url}: {request.failure}"
    ))
    return context, page, errors, failed_requests


def _assert_clean(errors, failed_requests):
    ignored = ("favicon", "ERR_ABORTED")
    relevant_errors = [value for value in errors if not any(token in value for token in ignored)]
    relevant_failures = [value for value in failed_requests if not any(token in value for token in ignored)]
    assert relevant_errors == []
    assert relevant_failures == []


def test_desktop_live_desk_success(browser):
    context, page, errors, failed_requests = _page(browser)
    compile_requests = []
    page.route("**/api/compile", lambda route, request: (
        compile_requests.append(request.post_data_json),
        route.fulfill(status=200, content_type="text/event-stream", body=_sse_success()),
    )[-1])

    page.goto(BASE_URL, wait_until="networkidle")
    expect(page).to_have_title(re.compile("DailyDex"))
    expect(page.get_by_role("heading", name="Choose a signal. Get a fresh desk brief.")).to_be_visible()
    expect(page.get_by_text("Nothing compiles until you choose")).to_be_visible()
    assert compile_requests == []
    assert not re.search(r"\b\d{4,}m\b", page.locator(".topbar-sources").inner_text())

    signals = page.locator(".signal-row")
    assert signals.count() >= 3
    signals.first.click()
    expect(page.locator(".desk-brief")).to_be_visible(timeout=10_000)
    expect(page.get_by_role("heading", name=re.compile("inspectable agent stack"))).to_be_visible()
    expect(page.locator(".desk-evidence-ledger")).to_contain_text("Source repository")
    assert len(compile_requests) == 1
    assert compile_requests[0]["cluster_slug"]
    assert page.locator(".desk-citations a").count() >= 8

    unnamed_buttons = page.locator("button").evaluate_all(
        "buttons => buttons.filter(button => !button.innerText.trim() && !button.getAttribute('aria-label')).length"
    )
    assert unnamed_buttons == 0
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.screenshot(path=str(ARTIFACT_DIR / "desktop-live-desk.png"), full_page=True)
    _assert_clean(errors, failed_requests)
    context.close()


def test_interrupted_compile_surfaces_recoverable_error(browser):
    context, page, errors, failed_requests = _page(browser)
    incomplete = "data: " + json.dumps({"type": "status", "phase": "compiling", "message": "Working"}) + "\n\n"
    page.route("**/api/compile", lambda route: route.fulfill(
        status=200, content_type="text/event-stream", body=incomplete,
    ))
    page.goto(BASE_URL, wait_until="networkidle")
    page.locator(".signal-row").first.click()
    expect(page.locator(".desk-error")).to_contain_text(
        "stream ended before the desk returned a result", timeout=10_000,
    )
    expect(page.get_by_role("button", name="Try again")).to_be_visible()
    _assert_clean(errors, failed_requests)
    context.close()


def test_navigation_and_profile_editor(browser):
    context, page, errors, failed_requests = _page(browser)
    saved_profiles = []

    def profile_route(route, request):
        if request.method == "POST":
            saved_profiles.append(request.post_data_json)
            route.fulfill(
                status=200, content_type="application/json",
                body=json.dumps({"ok": True, "profile": request.post_data_json}),
            )
        else:
            route.continue_()

    page.route("**/api/profile", profile_route)
    page.goto(BASE_URL, wait_until="networkidle")
    for label in ("Discover", "Produce", "Publish", "Insights", "Research", "Thumb Lab", "Settings"):
        page.get_by_role("button", name=re.compile(f"^{label}")).click()
        expect(page.locator(".main-scroll")).not_to_be_empty()
        expect(page.get_by_text("Something broke rendering this view")).to_have_count(0)
        if label == "Research":
            assert "Munger" not in page.locator(".main-scroll").inner_text()

    page.get_by_role("button", name=re.compile("^Discover")).click()
    cluster_toggle = page.locator('[role="button"][aria-expanded]').first
    initial_expanded = cluster_toggle.get_attribute("aria-expanded")
    cluster_toggle.focus()
    page.keyboard.press("Enter")
    expect(cluster_toggle).to_have_attribute(
        "aria-expanded", "false" if initial_expanded == "true" else "true",
    )
    page.get_by_role("button", name=re.compile("^Settings")).click()

    page.get_by_role("button", name="Edit brand profile").click()
    expect(page.get_by_role("heading", name="Brand Identity & Profile")).to_be_visible()
    channel_input = page.get_by_label("Channel Name")
    expect(channel_input).to_have_value("Sidhant Amonkar")
    channel_input.fill("Sidhant Amonkar Test")
    expect(channel_input).to_have_value("Sidhant Amonkar Test")
    expect(page.get_by_label("Research Desk Model")).to_have_value("meta/llama-3.3-70b-instruct")
    page.get_by_role("button", name=re.compile("Save Brand Profile")).click()
    expect(page.get_by_text("Brand profile updated and saved successfully")).to_be_visible()
    assert saved_profiles[0]["channel_name"] == "Sidhant Amonkar Test"
    assert saved_profiles[0]["copilot"]["compile_model"] == "meta/llama-3.3-70b-instruct"
    page.screenshot(path=str(ARTIFACT_DIR / "profile-editor.png"), full_page=True)
    _assert_clean(errors, failed_requests)
    context.close()


def test_mobile_navigation_and_signal_selection(browser):
    context, page, errors, failed_requests = _page(browser, {"width": 390, "height": 844})
    page.route("**/api/compile", lambda route: route.fulfill(
        status=200, content_type="text/event-stream", body=_sse_success(),
    ))
    page.goto(BASE_URL, wait_until="networkidle")
    expect(page.get_by_role("button", name="Open navigation")).to_be_visible()
    page.get_by_role("button", name="Open navigation").click()
    expect(page.locator("#primary-navigation")).to_be_visible()
    expect(page.locator(".nav-mobile-close")).to_be_focused()
    page.get_by_role("button", name=re.compile("^Today")).click()
    expect(page.locator(".nav-backdrop")).to_have_count(0)

    page.locator(".signal-row").nth(1).click()
    expect(page.locator(".desk-brief")).to_be_visible(timeout=10_000)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.screenshot(path=str(ARTIFACT_DIR / "mobile-live-desk.png"), full_page=True)
    _assert_clean(errors, failed_requests)
    context.close()


@pytest.mark.parametrize("width", [320, 768])
def test_viewport_extremes_have_no_page_overflow(browser, width):
    context, page, errors, failed_requests = _page(browser, {"width": width, "height": 780})
    page.goto(BASE_URL, wait_until="networkidle")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.get_by_role("button", name="Open navigation").click()
    page.keyboard.press("Escape")
    expect(page.locator(".nav-backdrop")).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    _assert_clean(errors, failed_requests)
    context.close()
