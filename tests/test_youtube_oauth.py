import os
from urllib.parse import parse_qs, urlsplit

import settings_manager
import youtube_oauth


def test_google_oauth_settings_persist_but_tokens_stay_hidden(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_manager, "SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(settings_manager, "SETTINGS_FILE", tmp_path / "settings.json")
    settings_manager.update({
        "google_client_id": "client-id",
        "google_client_secret": "client-secret",
        "google_access_token": "access-token",
        "google_refresh_token": "refresh-token",
        "google_token_expiry": "123456",
    })

    assert settings_manager.get("google_refresh_token") == "refresh-token"
    api_payload = settings_manager.get_for_api()
    assert "google_client_id" in api_payload["schema"]
    assert "google_access_token" not in api_payload["schema"]
    assert oct(os.stat(settings_manager.SETTINGS_FILE).st_mode & 0o777) == "0o600"


def test_auth_url_uses_state_redirect_and_required_scope(monkeypatch):
    monkeypatch.setattr(youtube_oauth, "_get_setting", lambda key: "client-id" if key == "google_client_id" else "")
    url = youtube_oauth.get_auth_url(
        redirect_uri="https://dailydex.example/api/integrations/youtube/callback",
        state="csrf-state",
    )
    query = parse_qs(urlsplit(url).query)
    assert query["state"] == ["csrf-state"]
    assert query["redirect_uri"] == ["https://dailydex.example/api/integrations/youtube/callback"]
    assert "https://www.googleapis.com/auth/youtube.force-ssl" in query["scope"][0]


def test_exchange_code_persists_tokens_atomically(monkeypatch):
    monkeypatch.setattr(youtube_oauth, "_get_setting", lambda _key: "configured")
    monkeypatch.setattr(youtube_oauth, "_form_post", lambda *_args, **_kwargs: {
        "ok": True,
        "data": {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600},
    })
    persisted = []
    monkeypatch.setattr(settings_manager, "update", lambda values: persisted.append(values))

    result = youtube_oauth.exchange_code("code", redirect_uri="https://example.test/callback")
    assert result["access_token"] == "access"
    assert len(persisted) == 1
    assert persisted[0]["google_refresh_token"] == "refresh"


def test_targeted_analytics_uses_only_supported_metrics(monkeypatch):
    monkeypatch.setattr(youtube_oauth, "_ensure_valid_token", lambda _token=None: {
        "ok": True, "access_token": "token",
    })
    requested = {}

    def fake_request(url, _token):
        requested["url"] = url
        return {
            "ok": True,
            "data": {
                "columnHeaders": [{"name": "video"}, {"name": "views"}],
                "rows": [["1234567890a", 42]],
            },
        }

    monkeypatch.setattr(youtube_oauth, "_authed_request", fake_request)
    result = youtube_oauth.get_video_analytics(None, "1234567890a")
    metrics = parse_qs(urlsplit(requested["url"]).query)["metrics"][0]
    assert "impressionClickThroughRate" not in metrics
    assert result["views"] == 42
    assert result["ctr"] is None


def test_title_update_preserves_existing_snippet(monkeypatch):
    monkeypatch.setattr(youtube_oauth, "_ensure_valid_token", lambda _token=None: {
        "ok": True, "access_token": "token",
    })
    monkeypatch.setattr(youtube_oauth, "_authed_request", lambda *_args, **_kwargs: {
        "ok": True,
        "data": {"items": [{"snippet": {
            "title": "Old",
            "description": "Keep this",
            "categoryId": "28",
            "tags": ["ai", "testing"],
            "defaultLanguage": "en",
        }}]},
    })
    sent = {}

    def fake_http(_url, **kwargs):
        import json
        sent.update(json.loads(kwargs["data"]))
        return {"ok": True, "data": {"id": "1234567890a", "snippet": sent["snippet"]}}

    monkeypatch.setattr(youtube_oauth, "_http_request", fake_http)
    result = youtube_oauth.update_video_title(None, "1234567890a", "New title")
    assert result["ok"] is True
    assert sent["snippet"]["description"] == "Keep this"
    assert sent["snippet"]["categoryId"] == "28"
    assert sent["snippet"]["tags"] == ["ai", "testing"]


def test_oauth_routes_validate_state(client, monkeypatch):
    monkeypatch.setattr(youtube_oauth, "_get_setting", lambda key: "client-id" if key == "google_client_id" else "")
    start = client.get("/api/integrations/youtube/connect")
    assert start.status_code == 302
    query = parse_qs(urlsplit(start.headers["Location"]).query)
    assert query.get("state")

    invalid = client.get("/api/integrations/youtube/callback?code=code&state=wrong")
    assert invalid.status_code == 400

    with client.session_transaction() as session:
        session["youtube_oauth_state"] = "expected"
    monkeypatch.setattr(youtube_oauth, "exchange_code", lambda *_args, **_kwargs: {"access_token": "ok"})
    valid = client.get("/api/integrations/youtube/callback?code=code&state=expected")
    assert valid.status_code == 302
