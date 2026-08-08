"""Tests for LinkedIn document posting.

The three-step upload is mocked at the HTTP boundary — this has never been run
against the live API, so these pin the request shapes and the guard rails, not
LinkedIn's actual acceptance.
"""

import json
import os
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

import linkedin_client as li


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "carousel.pdf"
    path.write_bytes(b"%PDF-1.4 fake document body")
    return str(path)


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "test-token")


def _ok(data=None, headers=None):
    return {"ok": True, "data": data or {}, "status": 200, "headers": headers or {}}


def _happy_path():
    """userinfo -> initializeUpload -> PUT bytes -> create post."""
    return [
        _ok({"sub": "abc123", "name": "Sidhant"}),
        _ok({"value": {"uploadUrl": "https://upload.example/put",
                       "document": "urn:li:document:D123"}}),
        _ok({}),
        _ok({}, {"x-restli-id": "urn:li:share:S456"}),
    ]


def test_publishes_and_returns_the_post_url(pdf):
    with patch.object(li, "_request", side_effect=_happy_path()) as req:
        result = li.publish_document_post(pdf, "Here is what broke in production.")

    assert result["ok"] is True
    assert result["post_urn"] == "urn:li:share:S456"
    assert result["url"].endswith("urn:li:share:S456")
    assert result["document_urn"] == "urn:li:document:D123"
    assert req.call_count == 4


def test_the_post_body_carries_the_document_and_commentary(pdf):
    with patch.object(li, "_request", side_effect=_happy_path()) as req:
        li.publish_document_post(pdf, "Commentary text", title="Incident report")

    body = json.loads(req.call_args_list[3].kwargs["data"].decode())
    assert body["author"] == "urn:li:person:abc123"
    assert body["commentary"] == "Commentary text"
    assert body["content"]["media"]["id"] == "urn:li:document:D123"
    assert body["content"]["media"]["title"] == "Incident report"
    assert body["lifecycleState"] == "PUBLISHED"


def test_the_version_header_is_sent(pdf):
    with patch.object(li, "_request", side_effect=_happy_path()) as req:
        li.publish_document_post(pdf, "text")

    headers = req.call_args_list[3].kwargs["headers"]
    assert headers["LinkedIn-Version"] == li.API_VERSION
    assert headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert headers["Authorization"] == "Bearer test-token"


def test_a_missing_token_fails_before_any_request(monkeypatch, pdf):
    monkeypatch.delenv("LINKEDIN_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(li, "_token", lambda: "")

    with patch.object(li, "_request") as req:
        result = li.publish_document_post(pdf, "text")

    assert result["ok"] is False and result["stage"] == "auth"
    req.assert_not_called()


@pytest.mark.parametrize("commentary,expected", [("", "commentary"), ("   ", "commentary")])
def test_commentary_is_required(pdf, commentary, expected):
    result = li.publish_document_post(pdf, commentary)
    assert result["ok"] is False and expected in result["error"]


def test_a_missing_pdf_is_rejected():
    result = li.publish_document_post("/nonexistent/x.pdf", "text")
    assert result["ok"] is False and result["stage"] == "validate"


def test_an_oversized_pdf_is_rejected(tmp_path, monkeypatch):
    big = tmp_path / "big.pdf"
    big.write_bytes(b"x" * 100)
    monkeypatch.setattr(li, "MAX_PDF_BYTES", 10)

    result = li.publish_document_post(str(big), "text")
    assert result["ok"] is False and "limit" in result["error"]


def test_an_unknown_visibility_is_rejected(pdf):
    result = li.publish_document_post(pdf, "text", visibility="EVERYONE")
    assert result["ok"] is False and "visibility" in result["error"]


def test_commentary_is_truncated_to_the_platform_limit(pdf):
    with patch.object(li, "_request", side_effect=_happy_path()) as req:
        li.publish_document_post(pdf, "x" * 5000)

    body = json.loads(req.call_args_list[3].kwargs["data"].decode())
    assert len(body["commentary"]) == li.MAX_COMMENTARY_CHARS


def test_a_failure_names_the_stage_it_failed_at(pdf):
    """A partial run can leave an uploaded document with no post attached."""
    responses = _happy_path()
    responses[3] = {"ok": False, "error": {"message": "ACCESS_DENIED"}, "status": 403}

    with patch.object(li, "_request", side_effect=responses):
        result = li.publish_document_post(pdf, "text")

    assert result["ok"] is False
    assert result["stage"] == "create_post"
    assert result["document_urn"] == "urn:li:document:D123"


def test_a_token_without_openid_scope_is_reported_clearly():
    with patch.object(li, "_request", side_effect=[_ok({"name": "no sub here"})]):
        result = li.get_author_urn("tok")

    assert result["ok"] is False and "openid" in result["error"]


def test_an_unexpected_initialize_response_is_not_treated_as_success(pdf):
    responses = _happy_path()
    responses[1] = _ok({"value": {}})

    with patch.object(li, "_request", side_effect=responses):
        result = li.publish_document_post(pdf, "text")

    assert result["ok"] is False and result["stage"] == "initialize_upload"


# ── route guards ──────────────────────────────────────────────────────────

def test_route_refuses_without_explicit_confirmation(client, app_env):
    resp = client.post("/api/integrations/linkedin/post",
                       json={"pdf_path": "x.pdf", "commentary": "hi"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "confirmation_required"


def test_route_rejects_paths_outside_the_carousel_directory(client, app_env):
    """The route takes a caller-supplied path; it must not read arbitrary files."""
    for attempt in ("/etc/passwd", "../../../etc/passwd", "../.env"):
        resp = client.post("/api/integrations/linkedin/post",
                           json={"confirm": True, "pdf_path": attempt, "commentary": "hi"})
        assert resp.status_code == 400, f"{attempt} was not rejected"
        assert "carousels" in resp.get_json()["error"]


def test_route_defaults_to_the_least_public_visibility(client, app_env, tmp_path, monkeypatch):
    import linkedin_client

    data_dir = os.environ["DATA_DIR"]
    carousels = Path(data_dir) / "carousels"
    carousels.mkdir(parents=True, exist_ok=True)
    pdf = carousels / "deck.pdf"
    pdf.write_bytes(b"%PDF-1.4 body")

    seen = {}

    def fake_publish(**kwargs):
        seen.update(kwargs)
        return {"ok": True, "post_urn": "urn:li:share:1", "url": "https://x", "bytes": 1}

    monkeypatch.setattr(linkedin_client, "publish_document_post", fake_publish)
    resp = client.post("/api/integrations/linkedin/post",
                       json={"confirm": True, "pdf_path": "deck.pdf", "commentary": "hi"})

    assert resp.status_code == 200
    assert seen["visibility"] == "CONNECTIONS", "must not default to the public feed"


# ── review fixes ──────────────────────────────────────────────────────────

def test_visibility_defaults_to_connections_not_public(pdf):
    """The module default must match the route's; a caller reaching the public
    feed should have to ask for it."""
    with patch.object(li, "_request", side_effect=_happy_path()) as req:
        li.publish_document_post(pdf, "text")

    body = json.loads(req.call_args_list[3].kwargs["data"].decode())
    assert body["visibility"] == "CONNECTIONS"


def test_the_bearer_token_is_dropped_when_a_redirect_leaves_the_host():
    """urllib replays headers on redirect; the upload PUT carries the token."""
    handler = li._StripAuthOnHostChange()
    req = urllib.request.Request("https://api.linkedin.com/rest/documents",
                                 headers={"Authorization": "Bearer secret"})

    offsite = handler.redirect_request(req, None, 302, "Found", {},
                                       "https://evil.example/upload")
    assert "Authorization" not in dict(offsite.headers)
    assert "authorization" not in {k.lower() for k in offsite.headers}

    samehost = handler.redirect_request(req, None, 302, "Found", {},
                                        "https://api.linkedin.com/elsewhere")
    assert "Bearer secret" in dict(samehost.headers).get("Authorization", "")


def test_the_document_title_is_not_a_uuid(tmp_path):
    """path.stem is "carousel-<hex>" and viewers see it on the document."""
    deck = tmp_path / "carousel-8e68a848cee3.pdf"
    deck.write_bytes(b"%PDF-1.4 body")

    with patch.object(li, "_request", side_effect=_happy_path()) as req:
        li.publish_document_post(str(deck), "An agent got write access it should not have")

    title = json.loads(req.call_args_list[3].kwargs["data"].decode())["content"]["media"]["title"]
    assert "carousel-" not in title
    assert title.startswith("An agent got write access")


def test_route_refuses_to_post_the_same_deck_twice(client, app_env, monkeypatch):
    """Publishing is irreversible; a retry or double-click must not post twice."""
    import linkedin_client
    from routes import api_integrations

    carousels = Path(os.environ["DATA_DIR"]) / "carousels"
    carousels.mkdir(parents=True, exist_ok=True)
    (carousels / "deck.pdf").write_bytes(b"%PDF-1.4 identical body")

    calls = []
    monkeypatch.setattr(linkedin_client, "publish_document_post",
                        lambda **kw: calls.append(kw) or
                        {"ok": True, "post_urn": "urn:li:share:1", "url": "https://x"})
    api_integrations._linkedin_posted.clear()

    body = {"confirm": True, "pdf_path": "deck.pdf", "commentary": "hi"}
    first = client.post("/api/integrations/linkedin/post", json=body)
    second = client.post("/api/integrations/linkedin/post", json=body)

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.get_json()["error"] == "duplicate_post"
    assert len(calls) == 1, "the deck was published twice"


def test_a_different_deck_is_not_blocked_by_the_guard(client, app_env, monkeypatch):
    import linkedin_client
    from routes import api_integrations

    carousels = Path(os.environ["DATA_DIR"]) / "carousels"
    carousels.mkdir(parents=True, exist_ok=True)
    (carousels / "a.pdf").write_bytes(b"%PDF-1.4 deck one")
    (carousels / "b.pdf").write_bytes(b"%PDF-1.4 deck two")

    monkeypatch.setattr(linkedin_client, "publish_document_post",
                        lambda **kw: {"ok": True, "post_urn": "u", "url": "https://x"})
    api_integrations._linkedin_posted.clear()

    for name in ("a.pdf", "b.pdf"):
        resp = client.post("/api/integrations/linkedin/post",
                           json={"confirm": True, "pdf_path": name, "commentary": "hi"})
        assert resp.status_code == 200, name


def test_a_failed_publish_is_not_remembered(client, app_env, monkeypatch):
    """A 502 must stay retryable, or a transient failure blocks the deck."""
    import linkedin_client
    from routes import api_integrations

    carousels = Path(os.environ["DATA_DIR"]) / "carousels"
    carousels.mkdir(parents=True, exist_ok=True)
    (carousels / "c.pdf").write_bytes(b"%PDF-1.4 deck three")

    monkeypatch.setattr(linkedin_client, "publish_document_post",
                        lambda **kw: {"ok": False, "error": "boom", "stage": "upload"})
    api_integrations._linkedin_posted.clear()

    body = {"confirm": True, "pdf_path": "c.pdf", "commentary": "hi"}
    assert client.post("/api/integrations/linkedin/post", json=body).status_code == 502
    assert client.post("/api/integrations/linkedin/post", json=body).status_code == 502
