"""Billing trial, checkout, webhook, and entitlement tests."""

import re
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from flask import Flask, jsonify

from routes.api_auth import init_auth
from routes.api_billing import init_billing


REPO_DIR = Path(__file__).resolve().parent.parent
HTTPS = "https://dailydex.test"


def _csrf(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.fixture
def billing_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DAILYDEX_AUTH_ENABLED", "1")
    monkeypatch.setenv("FLASK_SECRET_KEY", "s" * 64)
    monkeypatch.setenv("AUTH_INVITE_CODE", "invite-code-with-32-safe-characters")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("DAILYDEX_BILLING_ENABLED", "1")
    monkeypatch.setenv("BILLING_TRIAL_DAYS", "14")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_placeholder")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")
    monkeypatch.setenv("STRIPE_CREATOR_PRICE_ID", "price_creator")
    monkeypatch.setenv("STRIPE_STUDIO_PRICE_ID", "price_studio")
    monkeypatch.setenv("PUBLIC_BASE_URL", HTTPS)

    app = Flask(
        __name__, template_folder=str(REPO_DIR / "src" / "templates"),
        static_folder=str(REPO_DIR / "src" / "static"),
    )
    app.config["TESTING"] = True

    @app.route("/")
    def home():
        return "private"

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/private")
    def private_api():
        return jsonify({"ok": True})

    db_path = str(tmp_path / "auth.db")
    init_auth(app, db_path)
    init_billing(app)
    return app


def _register(client):
    token = _csrf(client.get("/signup", base_url=HTTPS).get_data(as_text=True))
    return client.post("/signup", base_url=HTTPS, data={
        "csrf_token": token,
        "invite_code": "invite-code-with-32-safe-characters",
        "display_name": "Owner", "email": "owner@example.com",
        "password": "correct horse battery staple",
        "confirm_password": "correct horse battery staple",
    })


def test_signup_starts_no_card_trial_and_allows_access(billing_app):
    client = billing_app.test_client()
    assert _register(client).status_code == 302
    status = client.get("/api/billing/status", base_url=HTTPS).get_json()
    assert status["status"] == "trialing"
    assert status["trial_days_left"] == 14
    assert status["access"] is True
    assert status["has_customer"] is False
    assert client.get("/api/private", base_url=HTTPS).status_code == 200


def test_expired_trial_returns_402_for_api_and_redirects_pages(billing_app):
    client = billing_app.test_client()
    _register(client)
    store = billing_app.extensions["dailydex_billing"]["store"]
    conn = store._connect()
    conn.cursor().execute(
        "UPDATE billing_accounts SET trial_ends_at = ?",
        ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),),
    )
    conn.commit()
    conn.close()

    denied = client.get("/api/private", base_url=HTTPS)
    assert denied.status_code == 402
    assert denied.get_json()["error"] == "subscription_required"
    assert client.get("/", base_url=HTTPS).headers["Location"] == "/billing"
    assert client.get("/billing", base_url=HTTPS).status_code == 200


def test_checkout_uses_selected_price_without_creating_trial_card(billing_app, monkeypatch):
    client = billing_app.test_client()
    _register(client)
    calls = []
    fake_stripe = types.SimpleNamespace(
        api_key=None,
        checkout=types.SimpleNamespace(Session=types.SimpleNamespace(
            create=lambda **kwargs: calls.append(kwargs) or types.SimpleNamespace(url="https://checkout.test/session")
        )),
        billing_portal=types.SimpleNamespace(Session=types.SimpleNamespace(create=lambda **kwargs: None)),
        Webhook=types.SimpleNamespace(construct_event=lambda *args: None),
    )
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)
    token = client.get("/api/auth/me", base_url=HTTPS).get_json()["csrf_token"]
    response = client.post(
        "/api/billing/checkout", base_url=HTTPS,
        headers={"X-CSRF-Token": token, "Content-Type": "application/json"},
        json={"plan": "creator"},
    )
    assert response.status_code == 200
    assert response.get_json()["url"] == "https://checkout.test/session"
    assert calls[0]["line_items"][0]["price"] == "price_creator"
    assert "trial_period_days" not in calls[0]["subscription_data"]
    assert calls[0]["subscription_data"]["trial_end"] > int(datetime.now(timezone.utc).timestamp())
    assert "customer_email" in calls[0]
    second = client.post(
        "/api/billing/checkout", base_url=HTTPS,
        headers={"X-CSRF-Token": token}, json={"plan": "creator"},
    )
    assert second.status_code == 409
    assert second.get_json()["error"] == "checkout_in_progress"
    assert len(calls) == 1


def test_checkout_blocks_second_active_subscription(billing_app, monkeypatch):
    client = billing_app.test_client()
    _register(client)
    store = billing_app.extensions["dailydex_billing"]["store"]
    conn = store._connect()
    conn.cursor().execute(
        "UPDATE billing_accounts SET stripe_customer_id = ?, stripe_subscription_id = ?, subscription_status = ?",
        ("cus_existing", "sub_existing", "active"),
    )
    conn.commit()
    conn.close()
    token = client.get("/api/auth/me", base_url=HTTPS).get_json()["csrf_token"]
    response = client.post(
        "/api/billing/checkout", base_url=HTTPS,
        headers={"X-CSRF-Token": token}, json={"plan": "studio"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "manage_existing_subscription"


def test_signed_webhook_is_csrf_exempt_and_idempotent(billing_app, monkeypatch):
    client = billing_app.test_client()
    _register(client)
    user = billing_app.extensions["dailydex_auth"]["store"].get_user("owner@example.com")
    event = {
        "id": "evt_1", "type": "checkout.session.completed", "created": 123,
        "data": {"object": {
            "customer": "cus_1", "subscription": "sub_1",
            "metadata": {"auth_user_id": str(user["id"]), "plan": "studio"},
        }},
    }
    fake_stripe = types.SimpleNamespace(
        api_key=None,
        Webhook=types.SimpleNamespace(construct_event=lambda *args: event),
    )
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)
    store = billing_app.extensions["dailydex_billing"]["store"]
    assert store.acquire_checkout_lock(user["id"], "studio") is True
    response = client.post(
        "/api/billing/webhook", base_url=HTTPS,
        headers={"Stripe-Signature": "valid"}, data=b"{}",
    )
    assert response.status_code == 200
    assert client.post(
        "/api/billing/webhook", base_url=HTTPS,
        headers={"Stripe-Signature": "valid"}, data=b"{}",
    ).status_code == 200
    account = store.get_account(user["id"])
    assert account["plan"] == "studio"
    assert account["subscription_status"] == "active"
    assert account["stripe_customer_id"] == "cus_1"
    assert store.acquire_checkout_lock(user["id"], "creator") is True


def test_webhook_processing_failure_requests_retry(billing_app, monkeypatch):
    client = billing_app.test_client()
    _register(client)
    event = {
        "id": "evt_failure", "type": "checkout.session.completed", "created": 124,
        "data": {"object": {"customer": "cus_2", "metadata": {"auth_user_id": "1"}}},
    }
    fake_stripe = types.SimpleNamespace(
        api_key=None, Webhook=types.SimpleNamespace(construct_event=lambda *args: event),
    )
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)
    store = billing_app.extensions["dailydex_billing"]["store"]
    monkeypatch.setattr(store, "apply_event", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db locked")))
    response = client.post(
        "/api/billing/webhook", base_url=HTTPS,
        headers={"Stripe-Signature": "valid"}, data=b"{}",
    )
    assert response.status_code == 500
