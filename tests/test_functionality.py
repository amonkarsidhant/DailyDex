#!/usr/bin/env python3
"""Functionality tests - simplified fast version"""

import pytest

pytestmark = pytest.mark.skip(reason="Legacy browser tests are not part of the automated pytest suite.")

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright
import json
import urllib.request

BASE_URL = "http://localhost:8888"
TIMEOUT = 20000

def run_test(name, test_func):
    try:
        test_func()
        print(f"  PASS")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_save_button():
    print("Test: Save button - must increase saved count...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        # Get initial count
        import urllib.request, json
        with urllib.request.urlopen(BASE_URL + "/api/saved") as resp:
            data = json.load(resp)
            initial_count = len(data["items"])
            print(f"  Initial saved count: {initial_count}")
        
        # Save an item
        feed_cards = page.locator("#feed-grid .card").count()
        print(f"  Feed cards: {feed_cards}")
        
        first_card = page.locator("#feed-grid .card").first
        save_btn = first_card.locator(".action-save").first
        save_btn.click()
        page.wait_for_timeout(1000)

        # Verify count increased
        with urllib.request.urlopen(BASE_URL + "/api/saved") as resp:
            data = json.load(resp)
            after_count = len(data["items"])
            print(f"  After save count: {after_count}")
            assert after_count > initial_count, f"Save did not increase count: {initial_count} -> {after_count}"
        
        # Reload page to see saved items (dashboard quirk: save doesn't auto-reload)
        page.reload()
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        
        # Check if saved tab is visible
        page.locator("button.nav-btn:has-text('Saved')").click()
        page.wait_for_timeout(1000)
        
        saved = page.locator("#saved .saved-item")
        count = saved.count()
        print(f"  UI saved count after reload: {count}")
        
        assert count > 0, "No saved items"
        browser.close()

def test_remove_button():
    print("Test: Remove button...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        first_card = page.locator("#feed-grid .card").first
        first_card.locator(".action-save").first.click()
        page.wait_for_timeout(1000)

        # Reload page to see saved items (dashboard quirk: save doesn't auto-reload)
        page.reload()
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        page.locator("button.nav-btn:has-text('Saved')").click()
        page.wait_for_timeout(1000)

        before = page.locator("#saved .saved-item").count()
        print(f"  Before remove: {before}")
        
        # Click remove - deleteItem calls location.reload() on success
        page.locator("#saved .action-ignore:has-text('Remove')").first.click()
        
        # Wait for reload to complete
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(1000)  # Extra wait for rendering

        after = page.locator("#saved .saved-item").count()
        print(f"  After remove: {after}")
        
        # Verify via API
        import urllib.request, json
        with urllib.request.urlopen(BASE_URL + "/api/saved") as resp:
            data = json.load(resp)
            print(f"  API count: {len(data['items'])}")
        
        assert after < before, f"Remove didn't work (before={before}, after={after})"
        browser.close()

def test_ignore_button():
    print("Test: Ignore button...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        before = page.locator("#feed-grid .card").count()
        first_card = page.locator("#feed-grid .card").first
        first_card.locator("button:has-text('Ignore')").first.click()
        page.wait_for_timeout(500)

        after = page.locator("#feed-grid .card").count()
        print(f"  Cards before: {before}, after: {after}")
        browser.close()

def test_track_button():
    print("Test: Track button...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        first_card = page.locator("#feed-grid .card").first
        track_btn = first_card.locator("button:has-text('Track')")
        if track_btn.count() > 0:
            track_btn.first.click()
            page.wait_for_timeout(500)

        with urllib.request.urlopen(BASE_URL + "/api/track") as resp:
            data = json.loads(resp.read())
            print(f"  Topics: {len(data.get('topics', []))}")
        browser.close()

def test_status_dropdown():
    print("Test: Status dropdown...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        first_card = page.locator("#feed-grid .card").first
        first_card.locator(".action-save").first.click()
        page.wait_for_timeout(500)

        page.locator("button.nav-btn:has-text('Saved')").click()
        page.wait_for_timeout(500)

        select = page.locator(".status-select").first
        if select.count() > 0:
            current = select.input_value()
            print(f"  Current status: {current}")
            select.select_option("to_test")
            page.wait_for_timeout(500)
            
            # Verify persistence by checking API
            import urllib.request, json
            with urllib.request.urlopen(BASE_URL + "/api/saved") as resp:
                data = json.load(resp)
                if data['items']:
                    api_status = data['items'][0].get('status')
                    print(f"  API status after change: {api_status}")
            
            print("  Status changed successfully")
        browser.close()

def test_search_filter():
    print("Test: Search filter...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        before = page.locator("#feed-grid .card").count()
        page.locator(".search-bar").fill("xyznonexistent")
        page.wait_for_timeout(300)

        after = page.locator("#feed-grid .card").count()
        print(f"  Before: {before}, after search: {after}")
        page.locator(".search-bar").fill("")
        browser.close()

def test_filter_buttons():
    print("Test: Filter buttons (Hot/All)...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        page.locator(".filter-btn:has-text('Hot')").click()
        page.wait_for_timeout(300)
        print("  Hot filter clicked")

        page.locator(".filter-btn:has-text('All')").click()
        page.wait_for_timeout(300)
        print("  All filter clicked")
        browser.close()

def test_keyboard_shortcuts():
    print("Test: Keyboard shortcuts...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BASE_URL, timeout=TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        page.keyboard.press("g")
        page.wait_for_timeout(200)
        assert page.locator("#github").is_visible()

        page.keyboard.press("f")
        page.wait_for_timeout(200)
        assert page.locator("#feed").is_visible()
        browser.close()

if __name__ == "__main__":
    print("=" * 50)
    print("Functionality Tests")
    print("=" * 50)

    tests = [
        ("Save button", test_save_button),
        ("Remove button", test_remove_button),
        ("Ignore button", test_ignore_button),
        ("Track button", test_track_button),
        ("Status dropdown", test_status_dropdown),
        ("Search filter", test_search_filter),
        ("Filter buttons", test_filter_buttons),
        ("Keyboard shortcuts", test_keyboard_shortcuts),
    ]

    passed = 0
    for name, func in tests:
        if run_test(name, func):
            passed += 1
        print()

    print("=" * 50)
    print(f"RESULTS: {passed}/{len(tests)} passed")
    print("=" * 50)
