from pathlib import Path


def test_creator_variant_exists_and_creator_ui_renders(creator_client):
    variant_payload = creator_client.get("/api/variant").get_json()
    keys = {variant["key"] for variant in variant_payload["variants"]}
    assert variant_payload["current"] == "creator"
    assert "creator" in keys

    html = creator_client.get("/").get_data(as_text=True)
    assert "Creator Brief" in html
    assert "Video Ideas" in html
    assert "Shorts" in html
    assert "Research Packs" in html
    assert "Content Pipeline" in html


def test_creator_fields_are_generated_for_scored_items(creator_client):
    payload = creator_client.get("/api/scored").get_json()
    item = payload["github"][0]

    assert isinstance(item.get("creator_score"), int)
    assert item["creator_score"] >= 0
    assert "creator_score_breakdown" in item
    assert "novelty" in item["creator_score_breakdown"]
    assert "audience_interest" in item["creator_score_breakdown"]
    assert "story_tension" in item["creator_score_breakdown"]
    assert "production_effort" in item["creator_score_breakdown"]
    assert item.get("creator_reason")
    assert item.get("recommended_content_format")
    assert item.get("opening_hook")
    assert item.get("three_key_points")
    assert item.get("short_script")
    assert item.get("suggested_titles")
    assert item.get("thumbnail_text")


def test_creator_brief_opportunities_and_clusters_are_built(creator_app_env):
    module = creator_app_env["module"]
    context = module.build_dashboard_context()

    assert context["creator_mode"] is True
    assert context["creator_opportunities"]
    assert context["creator_brief"]["best_video_idea"]
    assert context["creator_brief"]["shorts_ideas"]
    assert context["creator_brief"]["long_form_candidates"]
    assert context["creator_clusters"]

    cluster = context["creator_clusters"][0]
    assert cluster["source_count"] >= 2
    assert cluster["related_items"]
    assert cluster["why_this_is_a_story"]
    assert cluster["recommended_angle"]
    assert cluster["best_content_format"]


def test_research_pack_route_creates_markdown_file(creator_client):
    context = creator_client.get("/api/scored").get_json()
    item = context["github"][0]
    payload = {
        "topic": item["creator_topic"],
        "title": item["title"],
        "signal_score": item["signal_score"],
        "creator_score": item["creator_score"],
        "hook": item["opening_hook"],
        "suggested_titles": item["suggested_titles"],
        "thumbnail_text": item["thumbnail_text"],
        "why_viewers_care": item["why_viewers_care"],
        "source_evidence": item["source_evidence"],
        "production_effort": item["production_effort"],
        "demo_idea": item["demo_idea"],
        "risks_or_caveats": item["risks_or_caveats"],
        "three_key_points": item["three_key_points"],
        "opening_hook": item["opening_hook"],
        "intro_context": item["intro_context"],
        "demo_segment": item["demo_segment"],
        "caveats": item["caveats"],
        "closing_takeaway": item["closing_takeaway"],
        "call_to_action": item["call_to_action"],
        "best_format": item["recommended_content_format"],
    }
    response = creator_client.post("/api/research-pack", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert Path(data["path"]).exists()
    assert data["path"].endswith(".md")
    assert "Research Pack" in data["content"]


def test_creator_digest_is_generated(creator_client):
    response = creator_client.get("/api/creator-digest")
    assert response.status_code == 200
    payload = response.get_json()
    digest = payload["digest"]
    assert "DailyDex Creator Brief" in digest
    assert "## Best Video Idea Today" in digest
    assert "## Shorts Ideas" in digest
    assert "## Long-form Candidates" in digest
    assert "## Content Clusters" in digest
    assert payload["path"].endswith(".md")
    assert Path(payload["path"]).exists()


def test_creator_pipeline_statuses_and_fields_are_supported(creator_client, creator_app_env):
    save_response = creator_client.post(
        "/api/save",
        json={
            "title": "Agent demo opportunity",
            "url": "https://example.com/creator-opportunity",
            "source": "GitHub Trending",
            "source_type": "github",
            "signal_score": 88,
            "creator_score": 91,
            "pipeline_type": "creator",
            "status": "idea",
            "working_title": "I tested this agent repo",
            "hook": "This repo looks useful, but does it actually work?",
            "format": "Tutorial",
            "outline": ["What happened", "Live demo", "Verdict"],
            "sources": [{"title": "Evidence", "url": "https://example.com/creator-opportunity"}],
            "thumbnail_text": ["USEFUL OR HYPE"],
            "priority": "high",
        },
    )
    assert save_response.status_code == 200
    item_id = save_response.get_json()["id"]

    update_response = creator_client.put(
        f"/api/saved/{item_id}/notes",
        json={
            "notes": "Need a tighter intro.",
            "tags": ["creator"],
            "working_title": "I tested this open-source agent",
            "hook": "The claim is big. The setup is surprisingly short.",
            "format": "YouTube long-form",
            "outline": ["Story", "Demo", "Caveats"],
            "thumbnail_text": "HYPE OR USEFUL",
            "priority": "high",
            "published_url": "https://youtube.com/watch?v=published",
            "pipeline_type": "creator",
        },
    )
    assert update_response.status_code == 200

    creator_items = creator_client.get("/api/saved?pipeline_type=creator").get_json()["items"]
    item = next(entry for entry in creator_items if entry["id"] == item_id)
    assert item["status"] == "idea"
    assert item["pipeline_type"] == "creator"
    assert item["working_title"] == "I tested this open-source agent"
    assert item["hook"]
    assert item["format"] == "YouTube long-form"
    assert item["outline"] == ["Story", "Demo", "Caveats"]
    assert item["published_url"] == "https://youtube.com/watch?v=published"

    creator_client.put(f"/api/saved/{item_id}/status", json={"status": "script_ready"})
    grouped = creator_app_env["module"].build_dashboard_context()["creator_saved_groups"]
    assert any(group["key"] == "script_ready" for group in grouped)


def test_normal_mode_still_works(client):
    html = client.get("/").get_data(as_text=True)
    assert "Overview" in html
    assert "High Signal Feed" in html
    assert "Creator Brief" not in html
