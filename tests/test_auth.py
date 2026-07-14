"""Security regression tests for the shared-workspace authentication layer."""

import re
import sys
import types
from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask, jsonify

from routes.api_auth import init_auth


REPO_DIR = Path(__file__).resolve().parent.parent
HTTPS = "https://dailydex.test"


def _csrf(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match
    return match.group(1)


@pytest.fixture
def auth_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILYDEX_AUTH_ENABLED", "1")
    monkeypatch.setenv("FLASK_SECRET_KEY", "s" * 64)
    monkeypatch.setenv("AUTH_INVITE_CODE", "invite-code-with-32-safe-characters")
    monkeypatch.setenv("AUTH_ALLOW_SIGNUP", "1")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")

    app = Flask(
        __name__,
        template_folder=str(REPO_DIR / "src" / "templates"),
        static_folder=str(REPO_DIR / "src" / "static"),
    )
    app.config["TESTING"] = True

    @app.route("/")
    def home():
        return "private"

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/private", methods=["GET", "POST"])
    def private_api():
        return jsonify({"ok": True})

    init_auth(app, str(tmp_path / "auth.db"))
    return app


def _register(client):
    page = client.get("/signup", base_url=HTTPS)
    token = _csrf(page.get_data(as_text=True))
    return client.post(
        "/signup",
        base_url=HTTPS,
        data={
            "csrf_token": token,
            "invite_code": "invite-code-with-32-safe-characters",
            "display_name": "DailyDex Owner",
            "email": "owner@example.com",
            "password": "correct horse battery staple",
            "confirm_password": "correct horse battery staple",
        },
    )


def test_anonymous_requests_are_denied_but_health_is_public(auth_app):
    client = auth_app.test_client()

    page = client.get("/", base_url=HTTPS)
    assert page.status_code == 302
    assert page.headers["Location"].startswith("/login?next=")

    api = client.get("/api/private", base_url=HTTPS)
    assert api.status_code == 401
    assert api.get_json()["error"] == "authentication_required"

    static = client.get("/static/auth-client.js", base_url=HTTPS)
    assert static.status_code == 401
    assert client.get("/health", base_url=HTTPS).status_code == 200


def test_invite_signup_hashes_password_and_closes_registration(auth_app):
    client = auth_app.test_client()
    response = _register(client)

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=Lax" in cookie

    user = auth_app.extensions["dailydex_auth"]["store"].get_user("owner@example.com")
    assert user["password_hash"] != "correct horse battery staple"
    assert user["password_hash"].startswith("scrypt:")

    second_client = auth_app.test_client()
    closed = second_client.get("/signup", base_url=HTTPS)
    assert closed.status_code == 403
    assert "Registration is closed" in closed.get_data(as_text=True)


def test_bad_invite_and_weak_password_are_rejected(auth_app):
    client = auth_app.test_client()
    token = _csrf(client.get("/signup", base_url=HTTPS).get_data(as_text=True))
    bad_invite = client.post(
        "/signup",
        base_url=HTTPS,
        data={"csrf_token": token, "invite_code": "wrong"},
    )
    assert bad_invite.status_code == 403

    token = _csrf(client.get("/signup", base_url=HTTPS).get_data(as_text=True))
    weak = client.post(
        "/signup",
        base_url=HTTPS,
        data={
            "csrf_token": token,
            "invite_code": "invite-code-with-32-safe-characters",
            "display_name": "Owner",
            "email": "owner@example.com",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert weak.status_code == 400
    assert auth_app.extensions["dailydex_auth"]["store"].count_users() == 0


def test_authenticated_mutations_require_csrf_and_logout_clears_session(auth_app):
    client = auth_app.test_client()
    _register(client)

    assert client.get("/api/private", base_url=HTTPS).status_code == 200
    assert client.post("/api/private", base_url=HTTPS).status_code == 400

    token = client.get("/api/auth/me", base_url=HTTPS).get_json()["csrf_token"]
    allowed = client.post(
        "/api/private",
        base_url=HTTPS,
        headers={"X-CSRF-Token": token},
    )
    assert allowed.status_code == 200

    same_origin = client.post(
        "/api/private",
        base_url=HTTPS,
        headers={"Origin": HTTPS},
    )
    assert same_origin.status_code == 200

    logout = client.post(
        "/logout",
        base_url=HTTPS,
        headers={"X-CSRF-Token": token},
    )
    assert logout.status_code == 302
    assert client.get("/api/private", base_url=HTTPS).status_code == 401


def test_login_uses_generic_errors_and_blocks_open_redirects(auth_app):
    client = auth_app.test_client()
    _register(client)
    token = client.get("/api/auth/me", base_url=HTTPS).get_json()["csrf_token"]
    client.post("/logout", base_url=HTTPS, headers={"X-CSRF-Token": token})

    login_page = client.get("/login", base_url=HTTPS)
    token = _csrf(login_page.get_data(as_text=True))
    bad = client.post(
        "/login",
        base_url=HTTPS,
        data={"csrf_token": token, "email": "owner@example.com", "password": "wrong"},
    )
    assert bad.status_code == 401
    assert "Invalid email or password" in bad.get_data(as_text=True)

    token = _csrf(client.get("/login", base_url=HTTPS).get_data(as_text=True))
    good = client.post(
        "/login",
        base_url=HTTPS,
        data={
            "csrf_token": token,
            "email": "owner@example.com",
            "password": "correct horse battery staple",
            "next": "https://evil.example/steal",
        },
    )
    assert good.status_code == 302
    assert good.headers["Location"] == "/"


def test_security_headers_are_added(auth_app):
    response = auth_app.test_client().get("/login", base_url=HTTPS)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
    assert response.headers["Cache-Control"] == "no-store"


def test_auth_configuration_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILYDEX_AUTH_ENABLED", "1")
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    monkeypatch.setenv("AUTH_INVITE_CODE", "invite-code-with-32-safe-characters")

    with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
        init_auth(Flask(__name__), str(tmp_path / "auth.db"))


def test_production_cannot_silently_disable_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILYDEX_PRODUCTION", "1")
    monkeypatch.delenv("DAILYDEX_AUTH_ENABLED", raising=False)

    with pytest.raises(RuntimeError, match="required in production"):
        init_auth(Flask(__name__), str(tmp_path / "auth.db"))


def test_head_and_malformed_inputs_cannot_mutate_or_crash(auth_app):
    client = auth_app.test_client()
    assert client.head("/login", base_url=HTTPS).status_code == 200
    assert client.head("/signup", base_url=HTTPS).status_code == 200
    assert auth_app.extensions["dailydex_auth"]["store"].count_users() == 0

    login = client.get("/login?next=http://[", base_url=HTTPS)
    assert login.status_code == 200

    token = _csrf(client.get("/signup", base_url=HTTPS).get_data(as_text=True))
    invite = client.post(
        "/signup",
        base_url=HTTPS,
        data={"csrf_token": token, "invite_code": "not-ascii-\N{SNOWMAN}"},
    )
    assert invite.status_code == 403


def test_cron_endpoint_requires_bearer_secret(monkeypatch):
    cron_secret = "cron-secret-value-with-at-least-32-chars"
    monkeypatch.setenv("CRON_SECRET", cron_secret)
    from api.cron import enrich

    client = enrich.app.test_client()
    assert client.post("/api/cron/enrich").status_code == 401
    assert client.post(
        "/api/cron/enrich",
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 401

    fake_db = types.SimpleNamespace(IntelligenceDB=lambda: object())

    class FakeService:
        def __init__(self, db):
            self.db = db

        def run_once(self):
            return 2

    monkeypatch.setitem(sys.modules, "data_models", fake_db)
    monkeypatch.setitem(
        sys.modules,
        "creator_enricher",
        types.SimpleNamespace(EnrichmentService=FakeService),
    )
    response = client.post(
        "/api/cron/enrich",
        headers={"Authorization": f"Bearer {cron_secret}"},
    )
    assert response.status_code == 200
    assert response.get_json()["processed"] == 2


def test_main_dashboard_app_is_guarded_when_auth_enabled(tmp_path, monkeypatch):
    from conftest import _load_app_env, _sample_raw_data, _sample_scored_data

    monkeypatch.setenv("DAILYDEX_AUTH_ENABLED", "1")
    monkeypatch.setenv("FLASK_SECRET_KEY", "s" * 64)
    monkeypatch.setenv("AUTH_INVITE_CODE", "invite-code-with-32-safe-characters")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("CREATOR_ENRICHER_PRIMARY", "0")
    now_iso = datetime.now().isoformat()
    app_env = _load_app_env(
        tmp_path,
        monkeypatch,
        _sample_raw_data(now_iso),
        _sample_scored_data(now_iso),
    )
    client = app_env["module"].app.test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 302
    assert client.get("/api/benchmarks").status_code == 401
    assert client.post("/api/refresh").status_code == 401
    assert client.get("/login").status_code == 200
