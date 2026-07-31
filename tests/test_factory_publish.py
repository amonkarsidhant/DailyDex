"""Tests for the factory -> YouTube publish path.

The upload itself is a network call, so youtube_oauth is patched; what matters
here is that a successful upload lands in the analytics tables the rescue
engine reads, and that a failed one leaves the row recoverable.
"""

from unittest.mock import patch

import pytest


def _approved_row(db, **kwargs):
    row_id = db.factory_enqueue(
        kwargs.pop("topic", "AI Agents"),
        kwargs.pop("title", "Agent write access incident"),
        hook=kwargs.pop("hook", "An agent got write access it should never have had."),
        script=kwargs.pop("script", "An agent got write access it should never have had. "
                                    "Two independent timelines landed within a day."),
        video_path=kwargs.pop("video_path", "/videos/factory-abc.mp4"),
        virality_score=kwargs.pop("virality_score", 77),
    )
    db.factory_update_status(row_id, "approved")
    return row_id


@pytest.fixture
def ok_token():
    with patch("youtube_oauth._ensure_valid_token",
               return_value={"ok": True, "access_token": "tok"}):
        yield


def test_publish_registers_a_publication_for_analytics(client, app_env, ok_token):
    """A published short must be visible to analytics_sync and rescue_engine."""
    db = app_env["module"].intel_db
    row_id = _approved_row(db)

    with patch("youtube_oauth.upload_video",
               return_value={"video_id": "vid123", "url": "https://youtu.be/vid123"}):
        resp = client.post(f"/api/factory/{row_id}/publish")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "published"
    assert body["video_id"] == "vid123"
    assert db.factory_get(row_id)["status"] == "published"

    publications = db.get_publication_analytics()
    assert any(p.get("video_id") == "vid123" for p in publications), \
        "upload did not produce a publication row; rescue engine cannot see it"


def test_publish_is_idempotent_on_repeat(client, app_env, ok_token):
    """Re-publishing the same video must not accumulate duplicate rows."""
    db = app_env["module"].intel_db
    upload = {"video_id": "vid777", "url": "https://youtu.be/vid777"}

    for _ in range(2):
        row_id = _approved_row(db, video_path="/videos/factory-dup.mp4")
        with patch("youtube_oauth.upload_video", return_value=upload):
            client.post(f"/api/factory/{row_id}/publish")

    matching = [p for p in db.get_publication_analytics() if p.get("video_id") == "vid777"]
    assert len(matching) == 1


def test_publish_passes_privacy_through(client, app_env, ok_token):
    db = app_env["module"].intel_db
    row_id = _approved_row(db)

    with patch("youtube_oauth.upload_video",
               return_value={"video_id": "v", "url": "https://youtu.be/v"}) as upload:
        resp = client.post(f"/api/factory/{row_id}/publish", json={"privacy": "private"})

    assert resp.status_code == 200
    assert upload.call_args.kwargs["privacy"] == "private"
    assert upload.call_args.kwargs["is_short"] is True


def test_publish_defaults_to_unlisted(client, app_env, ok_token):
    db = app_env["module"].intel_db
    row_id = _approved_row(db)

    with patch("youtube_oauth.upload_video",
               return_value={"video_id": "v", "url": "https://youtu.be/v"}) as upload:
        client.post(f"/api/factory/{row_id}/publish")

    assert upload.call_args.kwargs["privacy"] == "unlisted"


def test_publish_rejects_unknown_privacy(client, app_env):
    db = app_env["module"].intel_db
    row_id = _approved_row(db)

    resp = client.post(f"/api/factory/{row_id}/publish", json={"privacy": "everyone"})
    assert resp.status_code == 400
    assert "privacy" in resp.get_json()["error"]


def test_failed_upload_leaves_row_approved_for_retry(client, app_env, ok_token):
    db = app_env["module"].intel_db
    row_id = _approved_row(db)

    with patch("youtube_oauth.upload_video", return_value={"error": "quotaExceeded"}):
        resp = client.post(f"/api/factory/{row_id}/publish")

    assert resp.status_code == 502
    row = db.factory_get(row_id)
    assert row["status"] == "approved", "a failed upload must stay retryable"
    assert "quota" in row["error"].lower()


def test_description_does_not_repeat_the_hook(app_env):
    from routes.api_factory import _publication_description

    text = _publication_description({
        "hook": "An agent got write access.",
        "script": "An agent got write access. Then the timelines landed.",
    })
    assert text.count("An agent got write access.") == 1

    both = _publication_description({"hook": "Standalone hook.", "script": "Different body."})
    assert "Standalone hook." in both and "Different body." in both


# ── source attribution ────────────────────────────────────────────────────

def test_description_cites_sources(app_env):
    from routes.api_factory import _publication_description

    text = _publication_description({
        "hook": "A claim.",
        "script": "A claim with detail.",
        "source_urls": ["https://github.com/org/repo", "https://news.ycombinator.com/item?id=1"],
    })
    assert "Sources:" in text
    assert "- https://github.com/org/repo" in text
    assert "- https://news.ycombinator.com/item?id=1" in text


def test_description_accepts_sources_still_encoded_as_json(app_env):
    """Rows read outside the decoding helpers still carry a JSON string."""
    from routes.api_factory import _publication_description

    text = _publication_description({
        "hook": "A claim.",
        "source_urls": '["https://example.com/a"]',
    })
    assert "- https://example.com/a" in text


def test_description_drops_non_http_and_duplicate_sources(app_env):
    from routes.api_factory import _publication_description

    text = _publication_description({
        "hook": "A claim.",
        "source_urls": ["https://example.com/a", "https://example.com/a",
                        "javascript:alert(1)", "dailydex://internal", ""],
    })
    assert text.count("https://example.com/a") == 1
    assert "javascript:" not in text
    assert "dailydex://" not in text


def test_description_omits_the_section_without_sources(app_env):
    from routes.api_factory import _publication_description

    assert "Sources:" not in _publication_description({"hook": "A claim.", "source_urls": []})


def test_published_description_reaches_youtube_with_sources(client, app_env, ok_token):
    db = app_env["module"].intel_db
    row_id = db.factory_enqueue(
        "AI Agents", "Incident short", hook="A claim.", script="A claim with detail.",
        video_path="/videos/f.mp4",
        source_urls=["https://github.com/org/repo"],
    )
    db.factory_update_status(row_id, "approved")

    with patch("youtube_oauth.upload_video",
               return_value={"video_id": "v", "url": "https://youtu.be/v"}) as upload:
        client.post(f"/api/factory/{row_id}/publish")

    assert "https://github.com/org/repo" in upload.call_args.kwargs["description"]
