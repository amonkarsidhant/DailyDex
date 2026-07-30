"""Network-boundary tests for live evidence retrieval."""

import urllib.parse

import pytest

import evidence


def test_evidence_get_rejects_local_and_credentialed_urls():
    with pytest.raises(ValueError, match="Private or reserved"):
        evidence._get("http://127.0.0.1:8080/admin")
    with pytest.raises(ValueError, match="Credentialed"):
        evidence._get("https://user:password@example.com/private")


def test_evidence_validation_rejects_private_redirect_target():
    with pytest.raises(ValueError, match="Private or reserved"):
        evidence._validate_public_url("http://[::1]/secret")


def test_evidence_get_bounds_response_size(monkeypatch):
    class OversizedResponse:
        status = 200

        def read(self, size):
            return b"x" * size

        def getheader(self, name):
            return None

    class FakeConnection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return OversizedResponse()

        def close(self):
            pass

    monkeypatch.setattr(
        evidence, "_validate_public_url",
        lambda url: (urllib.parse.urlparse(url), "93.184.216.34"),
    )
    monkeypatch.setattr(evidence, "_PinnedHTTPSConnection", FakeConnection)
    with pytest.raises(ValueError, match="size limit"):
        evidence._get("https://example.com/large")


def test_evidence_connection_uses_the_validated_ip(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def read(self, size):
            return b"grounded response"

        def getheader(self, name):
            return None

    class FakeConnection:
        def __init__(self, host, pinned_ip, **kwargs):
            captured.update(host=host, pinned_ip=pinned_ip)

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(
        evidence.socket, "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    monkeypatch.setattr(evidence, "_PinnedHTTPSConnection", FakeConnection)
    assert evidence._get("https://example.com/story") == "grounded response"
    assert captured == {"host": "example.com", "pinned_ip": "93.184.216.34"}


def test_github_evidence_falls_back_to_public_repo_page(monkeypatch):
    def fake_get(url, headers=None):
        if "api.github.com" in url:
            raise ValueError("GitHub API quota exhausted")
        return "<html><body><h1>acme/repo</h1><p>" + ("Inspectable agent workflow. " * 20) + "</p></body></html>"

    monkeypatch.setattr(evidence, "_get", fake_get)
    result = evidence._github_evidence("https://github.com/acme/repo")
    assert result["error"] == ""
    assert "Inspectable agent workflow" in result["excerpt"]


def test_youtube_evidence_reads_embedded_video_metadata(monkeypatch):
    monkeypatch.setattr(evidence, "_get", lambda url: (
        '{"title":"A practical model test","ownerChannelName":"Builder Channel",'
        '"shortDescription":"A source-backed walkthrough of the model trade-offs.",'
        '"viewCount":"12345"}'
    ))
    result = evidence._youtube_evidence("https://youtube.com/watch?v=test")
    assert result["error"] == ""
    assert "Published by: Builder Channel" in result["facts"]
    assert "12,345 YouTube views at fetch time" in result["facts"]
    assert result["excerpt"].startswith("A source-backed walkthrough")
