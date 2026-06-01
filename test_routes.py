from datetime import datetime


def test_saved_routes_and_lifecycle(client, app_env):
    module = app_env["module"]

    first_id = module.intel_db.save_item({
        "title": "First",
        "url": "https://example.com/first",
        "source": "GitHub Trending",
        "source_type": "github",
        "status": "to_read",
        "signal_score": 80,
    })
    second_id = module.intel_db.save_item({
        "title": "Second",
        "url": "https://example.com/second",
        "source": "GitHub Trending",
        "source_type": "github",
        "status": "to_read",
        "signal_score": 70,
    })

    status_response = client.put(f"/api/saved/{first_id}/status", json={"status": "useful"})
    assert status_response.status_code == 200
    items = {item["id"]: item for item in module.intel_db.get_saved_items()}
    assert items[first_id]["status"] == "useful"
    assert items[second_id]["status"] == "to_read"

    notes_response = client.put(f"/api/saved/{first_id}/notes", json={"notes": "important", "tags": ["agent", "pi"]})
    assert notes_response.status_code == 200
    items = {item["id"]: item for item in module.intel_db.get_saved_items()}
    assert items[first_id]["notes"] == "important"
    assert items[first_id]["tags"] == ["agent", "pi"]
    assert items[second_id]["notes"] == ""

    delete_response = client.delete(f"/api/saved/{first_id}")
    assert delete_response.status_code == 200
    remaining_ids = {item["id"] for item in module.intel_db.get_saved_items()}
    assert first_id not in remaining_ids
    assert second_id in remaining_ids


def test_track_routes_and_malformed_routes(client, app_env):
    module = app_env["module"]

    assert client.post("/api/track", json={"topic": "agents", "reason": "keep watching"}).status_code == 200
    assert client.post("/api/track", json={"topic": "local-llm", "reason": "pi testing"}).status_code == 200

    topics = client.get("/api/track").get_json()["topics"]
    tracked = {topic["topic"]: topic["id"] for topic in topics}
    assert "agents" in tracked
    assert "local-llm" in tracked

    delete_response = client.delete(f"/api/track/{tracked['agents']}")
    assert delete_response.status_code == 200

    remaining = {topic["topic"] for topic in client.get("/api/track").get_json()["topics"]}
    assert "agents" not in remaining
    assert "local-llm" in remaining

    assert client.open("/api/saved/", method="DELETE").status_code == 404
    assert client.open("/api/saved//status", method="PUT").status_code == 404
    assert client.open("/api/saved//notes", method="PUT").status_code == 404
    assert client.open("/api/track/", method="DELETE").status_code == 404


def test_save_ignore_and_digest_routes(client, app_env, monkeypatch):
    import llm_summary
    monkeypatch.setattr(llm_summary, "query_llm", lambda *args, **kwargs: "{}")

    save_response = client.post(
        "/api/save",
        json={
            "title": "Saved from API",
            "url": "https://example.com/saved",
            "source": "GitHub Trending",
            "source_type": "github",
            "category": "agents",
            "signal_score": 91,
        },
    )
    assert save_response.status_code == 200
    item_id = save_response.get_json()["id"]

    saved_items = client.get("/api/saved").get_json()["items"]
    assert any(item["id"] == item_id for item in saved_items)

    ignore_response = client.post(
        "/api/ignore",
        json={"url": "https://example.com/ignore", "title": "Ignore Me", "source_type": "blogs"},
    )
    assert ignore_response.status_code == 200
    ignored_items = client.get("/api/ignored").get_json()["items"]
    assert any(item["url"] == "https://example.com/ignore" for item in ignored_items)

    digest_response = client.get("/api/digest")
    assert digest_response.status_code == 200
    payload = digest_response.get_json()
    digest = payload["digest"]
    assert "DailyDex" in digest
    assert payload["path"].endswith(".md")
    digest_path = app_env["digest_dir"] / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    assert digest_path.exists()


def test_refresh_endpoint_success_and_failure_preserves_data(client, app_env, monkeypatch):
    import json
    import fetch_news

    def successful_refresh():
        data_file = app_env["data_dir"] / "data.json"
        data = json.loads(data_file.read_text(encoding="utf-8"))
        data["last_updated"] = datetime.now().isoformat()
        data_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        app_env["module"].intel_db.update_source_health("github", True, item_count=1)

    monkeypatch.setattr(fetch_news, "fetch_all", successful_refresh)
    refresh_response = client.post("/api/refresh")
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.get_json()
    assert refresh_payload["status"] in {"ok", "partial", "failed"}
    assert "source_health" in refresh_payload
    assert "message" in refresh_payload

    original_data = (app_env["data_dir"] / "data.json").read_text(encoding="utf-8")

    def fail_refresh():
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(fetch_news, "fetch_all", fail_refresh)
    failure_response = client.post("/api/refresh")
    failure_payload = failure_response.get_json()
    assert failure_response.status_code == 200
    assert failure_payload["status"] == "failed"
    assert "Existing data preserved" in failure_payload["message"]
    assert (app_env["data_dir"] / "data.json").read_text(encoding="utf-8") == original_data


def test_dashboard_meta_snapshot(client, app_env):
    module = app_env["module"]
    module.intel_db.update_source_health("github", True, item_count=3)

    response = client.get("/api/dashboard-meta")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["snapshot_id"]
    assert "last_updated_display" in payload
    assert "daily_summary" in payload
    assert "counts" in payload


def test_editorial_and_publishing_routes(client, app_env, monkeypatch):
    module = app_env["module"]
    import llm_summary
    monkeypatch.setattr(llm_summary, "query_llm", lambda *args, **kwargs: "Mock Briefing Content")

    # Mock agent runner dispatch to avoid running actual agent worker threads/processes
    if hasattr(module, "agent_runner") and module.agent_runner:
        monkeypatch.setattr(module.agent_runner, "dispatch", lambda *args, **kwargs: "mock-run-id")


    # Mock load_scored_data to return deterministic clusters
    dummy_data = {
        "github": [
            {"title": "Local AI sharding", "url": "https://example.com/sharding", "category": "AI", "signal_score": 90, "creator_score": 90},
            {"title": "Terminal autocomplete", "url": "https://example.com/autocomplete", "category": "Coding", "signal_score": 85, "creator_score": 85}
        ],
        "youtube": [
            {"title": "Local AI sharding deep-dive", "url": "https://example.com/sharding", "category": "AI", "signal_score": 80, "creator_score": 80},
            {"title": "Terminal autocomplete video", "url": "https://example.com/autocomplete", "category": "Coding", "signal_score": 75, "creator_score": 75}
        ]
    }
    monkeypatch.setattr(module, "load_scored_data", lambda *args, **kwargs: dummy_data)

    # 1. Get editorial briefing
    resp = client.get("/api/editorial/briefing")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "briefing" in data
    assert data["status"] == "ready"

    # 2. Force regenerate briefing
    resp_post = client.post("/api/editorial/briefing")
    assert resp_post.status_code == 200
    data_post = resp_post.get_json()
    assert "briefing" in data_post

    # 3. Approve editorial briefing
    approve_resp = client.post("/api/editorial/approve")
    assert approve_resp.status_code == 200
    approve_data = approve_resp.get_json()
    assert approve_data["ok"] is True
    assert approve_data["saved_count"] > 0
    assert "scheduled_days" in approve_data

    # Let's verify that the items were saved to DB
    saved_items = module.intel_db.get_saved_items()
    # Find one of our approved topics
    saved_topic = next((item for item in saved_items if "Local AI" in item.get("title")), None)
    assert saved_topic is not None
    assert saved_topic["pipeline_type"] == "creator"

    # 4. Publish
    publish_resp = client.post("/api/publish", json={
        "item_id": saved_topic["id"],
        "platform": "youtube"
    })
    assert publish_resp.status_code == 200
    assert publish_resp.get_json()["ok"] is True
    assert publish_resp.get_json()["status"] == "publishing"

    # 5. Simulate analytics
    # First, let's manually upsert a 'live' publication in the db to make sure simulate updates it
    module.intel_db.create_or_update_publication(
        item_id=saved_topic["id"],
        platform="youtube",
        views=100,
        impressions=1000,
        ctr=0.1,
        engagement_rate=0.05,
        status="live"
    )

    simulate_resp = client.post("/api/analytics/simulate")
    assert simulate_resp.status_code == 200
    simulate_data = simulate_resp.get_json()
    assert simulate_data["ok"] is True
    assert simulate_data["updated"] > 0

    # Let's verify views went up
    pubs = module.intel_db.get_publication_analytics()
    matching_pub = next((p for p in pubs if p["item_id"] == saved_topic["id"] and p["platform"] == "youtube"), None)
    assert matching_pub is not None
    assert matching_pub["views"] > 100


def test_command_validation_route(client, app_env, monkeypatch):
    module = app_env["module"]
    
    # Mock urllib.request.urlopen
    class MockResponse:
        def __init__(self, status):
            self.status = status
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: MockResponse(200))
    
    item_id = module.intel_db.save_item({
        "title": "Local Docmost setup",
        "url": "https://github.com/docmost/docmost",
        "source": "GitHub Trending",
        "source_type": "github",
        "status": "researching",
        "notes": "To run this project: git clone https://github.com/docmost/docmost.git\ndocker run -d docmost/docmost",
    })
    
    resp = client.post(f"/api/saved/{item_id}/validate")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["item_id"] == item_id
    results = {res["command"]: res for res in data["results"]}
    assert "git clone https://github.com/docmost/docmost.git" in results
    assert results["git clone https://github.com/docmost/docmost.git"]["status"] == "verified"
    assert "docker run -d docmost/docmost" in results
    assert results["docker run -d docmost/docmost"]["status"] == "verified"


def test_analytics_sync_route(client, app_env, monkeypatch):
    module = app_env["module"]
    
    # Mock urllib.request.urlopen to return mock HTML with view count 98765
    class MockResponse:
        def __init__(self, html):
            self.html = html
        def read(self):
            return self.html.encode('utf-8')
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    dummy_html = '<html><head><meta itemprop="interactionCount" content="98765"></head></html>'
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: MockResponse(dummy_html))
    
    # Save item with published_url
    item_id = module.intel_db.save_item({
        "title": "Synced YouTube Video",
        "url": "sync-slug",
        "source": "GitHub Trending",
        "source_type": "github",
        "status": "recording",
        "published_url": "https://www.youtube.com/watch?v=realvideo",
    })
    
    # Create live publication row
    module.intel_db.create_or_update_publication(
        item_id=item_id,
        platform="youtube",
        views=10,
        impressions=100,
        ctr=0.1,
        engagement_rate=0.05,
        status="live"
    )
    
    # Trigger sync/simulate endpoint
    resp = client.post("/api/analytics/simulate")
    assert resp.status_code == 200
    assert resp.get_json()["updated"] == 1
    
    # Verify views synced to scraped count
    pubs = module.intel_db.get_publication_analytics()
    sync_pub = next((p for p in pubs if p["item_id"] == item_id and p["platform"] == "youtube"), None)
    assert sync_pub is not None
    assert sync_pub["views"] == 98765
    assert sync_pub["impressions"] == 98765 * 12
    assert sync_pub["status"] == "completed"


def test_onboarding_flow(client, app_env, monkeypatch, tmp_path):
    import json
    module = app_env["module"]
    
    # Create a dummy profile path
    mock_profile_path = tmp_path / "creator_profile.json"
    mock_profile_path.write_text(json.dumps({"persona": "multi"}), encoding="utf-8")
    monkeypatch.setenv("CREATOR_PROFILE_PATH", str(mock_profile_path))
    
    # Mock settings manager file path to use temporary settings
    import settings_manager
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    
    payload = {
        "identity": {
            "provider": "github",
            "name": "Octocat Dev",
            "email": "octocat@github.com",
            "avatar": "https://avatar.url",
            "channel_id": "UC-Octo"
        },
        "profile": {
            "channel_name": "Testing Channel",
            "niche": "Testing Niche",
            "tone": "Hands-on testing",
            "persona": "shorts"
        },
        "keys": {
            "youtube_api_key": "AIzaSyTestOnboarding",
            "fal_api_key": "fal-test-key",
            "llm_provider": "ollama"
        }
    }
    
    resp = client.post("/api/onboarding/submit", json=payload)
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    
    # Check that settings updated
    assert settings_manager.get("youtube_api_key") == "AIzaSyTestOnboarding"
    assert settings_manager.get("fal_api_key") == "fal-test-key"
    assert settings_manager.get("llm_provider") == "ollama"
    
    # Check that profile json was updated
    with open(mock_profile_path, "r", encoding="utf-8") as f:
        prof_data = json.load(f)
    assert prof_data["channel_name"] == "Testing Channel"
    assert prof_data["niche"] == "Testing Niche"
    assert prof_data["tone"] == "Hands-on testing"
    assert prof_data["persona"] == "shorts"
    assert prof_data["creator_identity"]["name"] == "Octocat Dev"
    assert prof_data["creator_identity"]["onboarding_completed"] is True
    
    # Test Reset Route
    resp_reset = client.post("/api/onboarding/reset")
    assert resp_reset.status_code == 200
    assert resp_reset.get_json()["success"] is True
    
    with open(mock_profile_path, "r", encoding="utf-8") as f:
        prof_data_reset = json.load(f)
    assert "creator_identity" not in prof_data_reset


def test_advanced_creator_integrations(client, app_env):
    module = app_env["module"]

    # 1. Save an item to the DB
    item_id = module.intel_db.save_item({
        "title": "A/B Testing and Repurposing Video",
        "url": "repurpose-slug",
        "source": "GitHub Trending",
        "source_type": "github",
        "status": "published",
        "signal_score": 90,
    })

    # 2. Test Notion Sync
    notion_sync_resp = client.post("/api/integrations/notion/sync", json={"item_id": item_id})
    assert notion_sync_resp.status_code == 200
    notion_data = notion_sync_resp.get_json()
    assert notion_data["success"] is True
    assert "notion.so" in notion_data["notion_url"]

    # Verify inside production_assets database field
    item = module.intel_db.get_saved_item(item_id)
    assets = item.get("production_assets")
    if isinstance(assets, str):
        import json
        assets = json.loads(assets or "{}")
    elif not isinstance(assets, dict):
        assets = {}
    assert assets.get("notion_page_url") == notion_data["notion_url"]

    # 3. Test Repurpose Clips generation (POST)
    repurpose_post_resp = client.post("/api/integrations/repurpose", json={"item_id": item_id})
    assert repurpose_post_resp.status_code == 200
    repurpose_data = repurpose_post_resp.get_json()
    assert repurpose_data["success"] is True
    assert len(repurpose_data["clips"]) == 3
    clip = repurpose_data["clips"][0]
    assert clip["parent_item_id"] == item_id
    assert clip["status"] == "draft"

    # Test listing clips (GET)
    repurpose_get_resp = client.get(f"/api/integrations/repurpose?parent_item_id={item_id}")
    assert repurpose_get_resp.status_code == 200
    clips_list = repurpose_get_resp.get_json()["clips"]
    assert len(clips_list) == 3

    # 4. Test Publishing Clip (POST)
    clip_id = clip["id"]
    publish_clip_resp = client.post(f"/api/integrations/repurpose/{clip_id}/publish")
    assert publish_clip_resp.status_code == 200
    publish_clip_data = publish_clip_resp.get_json()
    assert publish_clip_data["success"] is True
    assert "youtube.com/shorts" in publish_clip_data["published_url"]

    # Verify clip status is live in DB
    updated_clips = module.intel_db.list_repurposed_clips(item_id)
    updated_clip = next((c for c in updated_clips if c["id"] == clip_id), None)
    assert updated_clip is not None
    assert updated_clip["status"] == "live"
    assert updated_clip["published_url"] == publish_clip_data["published_url"]

    # 5. Test A/B Test setup
    ab_resp = client.post("/api/integrations/ab-test", json={
        "item_id": item_id,
        "variant_a_title": "Original Title A",
        "variant_b_title": "Upgraded Title B"
    })
    assert ab_resp.status_code == 200
    ab_data = ab_resp.get_json()
    assert ab_data["success"] is True
    test_id = ab_data["test_id"]

    # Test Active A/B test GET route
    active_resp = client.get(f"/api/integrations/ab-test/active?item_id={item_id}")
    assert active_resp.status_code == 200
    active_test = active_resp.get_json()["test"]
    assert active_test is not None
    assert active_test["id"] == test_id
    assert active_test["status"] == "active"
    assert active_test["variant_b_title"] == "Upgraded Title B"

    # 6. Test A/B Test Analytics Simulation
    sim_resp = client.post("/api/analytics/simulate")
    assert sim_resp.status_code == 200
    assert sim_resp.get_json()["ok"] is True

    # Verify metrics went up in A/B test row
    active_resp_after = client.get(f"/api/integrations/ab-test/active?item_id={item_id}")
    assert active_resp_after.status_code == 200
    active_test_after = active_resp_after.get_json()["test"]
    assert active_test_after["variant_a_views"] > 0
    assert active_test_after["variant_b_views"] > 0




