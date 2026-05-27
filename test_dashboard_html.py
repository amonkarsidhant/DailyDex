def test_dashboard_contains_real_action_wiring(client, app_env):
    module = app_env["module"]
    module.intel_db.update_source_health("github", True, item_count=7)
    module.intel_db.update_source_health("huggingface", False, item_count=4, failure_reason="timeout", using_cache=True, cache_age_seconds=3600)
    module.intel_db.update_source_health("youtube", False, item_count=2, failure_reason="api error", using_cache=True, cache_age_seconds=13 * 3600)
    module.intel_db.update_source_health("blogs", False, item_count=0, failure_reason="feed offline", using_cache=False, cache_age_seconds=0)
    module.intel_db.update_source_health("papers", True, item_count=5)

    module.intel_db.save_item(
        {
            "title": "Saved Item",
            "url": "https://example.com/saved-item",
            "source": "GitHub Trending",
            "source_type": "github",
            "status": "to_read",
            "signal_score": 84,
            "notes": "keep this",
            "tags": ["agent"],
        }
    )
    module.intel_db.save_item(
        {
            "title": "Useful Item",
            "url": "https://example.com/useful-item",
            "source": "HuggingFace",
            "source_type": "huggingface",
            "status": "useful",
            "signal_score": 77,
        }
    )

    html = client.get("/classic").get_data(as_text=True)

    assert "<script src=\"/static/app.js\"></script>" in html
    assert "Daily Trust" in html
    assert "Refresh Now" in html
    assert "Open Today" not in html and "DailyDex Digest" in html
    assert "nav-btn" in html
    assert "search-target" in html
    assert "action-save" in html or "action-save" in html
    assert "btn btn-small action-ignore" in html
    assert "status-select" in html
    assert "kanban-board" in html
    assert "To Read" in html
    assert "Useful" in html
    assert "toast-container" in html
    assert 'id="live-status"' in html
    assert 'id="dashboard-state"' in html


def test_empty_state_is_helpful(empty_client):
    html = empty_client.get("/classic").get_data(as_text=True)

    assert "Overview" in html
    assert "Refresh Now" in html
