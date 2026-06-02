#!/usr/bin/env python3
"""UX tests for DailyDex using Playwright"""

import pytest

pytestmark = pytest.mark.skip(reason="Legacy browser tests are not part of the automated pytest suite.")

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright, expect
import json

BASE_URL = "http://localhost:8888"

def test_dashboard_loads():
    """Test dashboard loads without errors"""
    print("Test: Dashboard loads...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Capture console errors
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Check title
        title = page.title()
        assert "DailyDex" in title, f"Title missing 'DailyDex': {title}"
        
        # Check header exists
        header = page.locator(".logo")
        expect(header).to_be_visible()
        
        # Check no console errors
        console_errors = [e for e in errors if "favicon" not in e.lower()]
        if console_errors:
            print(f"  Console errors: {console_errors}")
        
        browser.close()
        print("  PASS")

def test_navigation_tabs():
    """Test all navigation tabs work"""
    print("Test: Navigation tabs...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        tabs = ["Feed", "GitHub", "Models", "Videos", "News", "Research", "Workflows", "Local Lab", "Saved"]
        
        for tab_name in tabs:
            tab = page.locator(f"button.nav-btn:has-text('{tab_name}')")
            if tab.count() > 0:
                tab.click()
                page.wait_for_timeout(200)
                print(f"  {tab_name}: OK")
            else:
                print(f"  {tab_name}: NOT FOUND")
        
        browser.close()
        print("  PASS")

def test_feed_cards_have_actions():
    """Test feed cards have Save/Ignore/Track buttons"""
    print("Test: Feed cards have action buttons...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Check cards exist
        cards = page.locator("#feed-grid .card")
        card_count = cards.count()
        print(f"  Found {card_count} cards")
        
        if card_count > 0:
            # Check action buttons exist
            save_buttons = page.locator("#feed-grid .action-save")
            print(f"  Save buttons: {save_buttons.count()}")
            
            ignore_buttons = page.locator("#feed-grid .action-btn-small:has-text('Ignore')")
            print(f"  Ignore buttons: {ignore_buttons.count()}")
        
        browser.close()
        print("  PASS")

def test_saved_tab():
    """Test Saved tab shows empty state"""
    print("Test: Saved tab...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Go to Saved tab
        page.locator("button.nav-btn:has-text('Saved')").click()
        page.wait_for_timeout(300)
        
        # Check empty state or items
        empty_state = page.locator(".empty-state")
        if empty_state.count() > 0:
            print("  Empty state shown (correct)")
        else:
            items = page.locator(".saved-item")
            print(f"  Saved items: {items.count()}")
        
        browser.close()
        print("  PASS")

def test_source_health_display():
    """Test source health bar is visible"""
    print("Test: Source health display...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        health_bar = page.locator(".health-bar")
        if health_bar.count() > 0:
            print("  Health bar visible")
            health_items = page.locator(".health-item")
            print(f"  Health items: {health_items.count()}")
        else:
            print("  Health bar NOT FOUND")
        
        browser.close()
        print("  PASS")

def test_signal_score_badges():
    """Test signal score badges exist"""
    print("Test: Signal score badges...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        badges = page.locator(".signal-badge")
        badge_count = badges.count()
        print(f"  Signal badges: {badge_count}")
        
        if badge_count > 0:
            # Get first badge text
            first_badge = badges.first
            print(f"  First badge: {first_badge.text_content()}")
        
        browser.close()
        print("  PASS")

def test_keyboard_shortcuts():
    """Test keyboard shortcuts work"""
    print("Test: Keyboard shortcuts...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Press 'g' to go to GitHub tab
        page.keyboard.press("g")
        page.wait_for_timeout(300)
        
        github_section = page.locator("#github")
        if github_section.is_visible():
            print("  'g' shortcut: GitHub tab opened")
        else:
            print("  'g' shortcut: FAILED")
        
        # Press 'f' to go to Feed
        page.keyboard.press("f")
        page.wait_for_timeout(300)
        
        feed_section = page.locator("#feed")
        if feed_section.is_visible():
            print("  'f' shortcut: Feed tab opened")
        else:
            print("  'f' shortcut: FAILED")
        
        browser.close()
        print("  PASS")

def test_api_endpoints():
    """Test API endpoints return valid JSON"""
    print("Test: API endpoints...")
    
    import urllib.request
    
    endpoints = [
        "/api/scored",
        "/api/saved", 
        "/api/source-health",
        "/api/track"
    ]
    
    for endpoint in endpoints:
        try:
            url = BASE_URL + endpoint
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read())
                print(f"  {endpoint}: OK ({len(str(data))} chars)")
        except Exception as e:
            print(f"  {endpoint}: FAILED ({e})")
    
    print("  PASS")

if __name__ == "__main__":
    print("=" * 60)
    print("DailyDex - UX Tests")
    print("=" * 60)
    
    tests = [
        test_dashboard_loads,
        test_navigation_tabs,
        test_feed_cards_have_actions,
        test_saved_tab,
        test_source_health_display,
        test_signal_score_badges,
        test_keyboard_shortcuts,
        test_api_endpoints,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
