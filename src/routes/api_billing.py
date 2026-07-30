"""Stripe billing, local no-card trials, and workspace entitlements."""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request

import db_compat as sqlite3


billing_bp = Blueprint("billing", __name__)
_ACCESS_STATUSES = {"active", "trialing"}
_BILLING_ENDPOINTS = {
    "billing.page", "billing.status", "billing.checkout", "billing.portal", "billing.webhook"
}


def _now():
    return datetime.now(timezone.utc)


def _parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _iso_from_unix(value):
    if not value:
        return None
    return datetime.fromtimestamp(int(value), timezone.utc).isoformat()


class BillingStore:
    def __init__(self, db_path, trial_days=14):
        self.db_path = db_path
        self.trial_days = trial_days
        self._init_schema()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auth_user_id INTEGER NOT NULL UNIQUE,
                email TEXT NOT NULL,
                plan TEXT,
                trial_started_at TEXT NOT NULL,
                trial_ends_at TEXT NOT NULL,
                stripe_customer_id TEXT UNIQUE,
                stripe_subscription_id TEXT UNIQUE,
                subscription_status TEXT,
                current_period_end TEXT,
                cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                latest_event_created INTEGER NOT NULL DEFAULT 0,
                latest_event_priority INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stripe_webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stripe_event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                event_created INTEGER NOT NULL,
                processed_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS billing_checkout_locks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auth_user_id INTEGER NOT NULL UNIQUE,
                plan TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def ensure_account(self, user):
        existing = self.get_account(user["id"])
        if existing:
            return existing
        now = _now()
        conn = self._connect()
        try:
            conn.cursor().execute("""
                INSERT INTO billing_accounts
                    (auth_user_id, email, trial_started_at, trial_ends_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user["id"], user["email"], now.isoformat(),
                (now + timedelta(days=self.trial_days)).isoformat(),
                now.isoformat(), now.isoformat(),
            ))
            conn.commit()
        except Exception:
            conn.close()
            existing = self.get_account(user["id"])
            if existing:
                return existing
            raise
        conn.close()
        return self.get_account(user["id"])

    def get_account(self, user_id):
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        row = conn.cursor().execute(
            "SELECT * FROM billing_accounts WHERE auth_user_id = ?", (user_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_by_customer(self, customer_id):
        if not customer_id:
            return None
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        row = conn.cursor().execute(
            "SELECT * FROM billing_accounts WHERE stripe_customer_id = ?", (customer_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def apply_event(self, event_id, event_type, event_created, auth_user_id=None,
                    customer_id=None, subscription_id=None, plan=None,
                    subscription_status=None, current_period_end=None,
                    cancel_at_period_end=None, event_priority=0):
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO stripe_webhook_events
                    (stripe_event_id, event_type, event_created, processed_at)
                VALUES (?, ?, ?, ?)
            """, (event_id, event_type, int(event_created or 0), _now().isoformat()))
        except Exception:
            try:
                conn.rollback()
                duplicate = cursor.execute(
                    "SELECT 1 FROM stripe_webhook_events WHERE stripe_event_id = ?",
                    (event_id,),
                ).fetchone()
            except Exception:
                conn.close()
                raise
            if duplicate:
                conn.close()
                return False
            conn.close()
            raise

        where, identity = ("auth_user_id", auth_user_id) if auth_user_id else ("stripe_customer_id", customer_id)
        if identity is not None:
            cursor.execute(f"""
                UPDATE billing_accounts SET
                    stripe_customer_id = COALESCE(?, stripe_customer_id),
                    stripe_subscription_id = COALESCE(?, stripe_subscription_id),
                    plan = COALESCE(?, plan),
                    subscription_status = COALESCE(?, subscription_status),
                    current_period_end = COALESCE(?, current_period_end),
                    cancel_at_period_end = COALESCE(?, cancel_at_period_end),
                    latest_event_created = ?, latest_event_priority = ?, updated_at = ?
                WHERE {where} = ? AND (
                    latest_event_created < ? OR
                    (latest_event_created = ? AND latest_event_priority < ?)
                )
            """, (
                customer_id, subscription_id, plan, subscription_status,
                current_period_end,
                None if cancel_at_period_end is None else int(bool(cancel_at_period_end)),
                int(event_created or 0), int(event_priority or 0),
                _now().isoformat(), identity, int(event_created or 0),
                int(event_created or 0), int(event_priority or 0),
            ))
        conn.commit()
        conn.close()
        return True

    def acquire_checkout_lock(self, auth_user_id, plan, ttl_seconds=1800):
        now = int(_now().timestamp())
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM billing_checkout_locks WHERE auth_user_id = ? AND created_at < ?",
            (auth_user_id, now - ttl_seconds),
        )
        try:
            cursor.execute(
                "INSERT INTO billing_checkout_locks (auth_user_id, plan, created_at) VALUES (?, ?, ?)",
                (auth_user_id, plan, now),
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            conn.rollback()
            existing = cursor.execute(
                "SELECT 1 FROM billing_checkout_locks WHERE auth_user_id = ?",
                (auth_user_id,),
            ).fetchone()
            conn.close()
            if existing:
                return False
            raise

    def release_checkout_lock(self, auth_user_id):
        if not auth_user_id:
            return
        conn = self._connect()
        conn.cursor().execute(
            "DELETE FROM billing_checkout_locks WHERE auth_user_id = ?", (auth_user_id,)
        )
        conn.commit()
        conn.close()


def _extension():
    return current_app.extensions["dailydex_billing"]


def _stripe():
    import stripe
    stripe.api_key = _extension()["secret_key"]
    return stripe


def _base_url():
    configured = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if configured:
        parsed = urlsplit(configured)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return configured
    return request.host_url.rstrip("/")


def _status_for(user):
    extension = _extension()
    if not extension["enabled"]:
        return {"enabled": False, "access": True, "status": "disabled"}
    account = extension["store"].ensure_account(user)
    trial_end = _parse_time(account["trial_ends_at"])
    now = _now()
    stripe_status = account.get("subscription_status") or ""
    trial_access = bool(trial_end and now < trial_end and not stripe_status)
    paid_access = stripe_status in _ACCESS_STATUSES
    status = stripe_status or ("trialing" if trial_access else "expired")
    seconds_left = max(0, (trial_end - now).total_seconds()) if trial_end else 0
    return {
        "enabled": True,
        "access": paid_access or trial_access,
        "status": status,
        "plan": account.get("plan"),
        "trial_ends_at": account.get("trial_ends_at"),
        "trial_days_left": int(math.ceil(seconds_left / 86400)) if trial_access else 0,
        "current_period_end": account.get("current_period_end"),
        "cancel_at_period_end": bool(account.get("cancel_at_period_end")),
        "has_customer": bool(account.get("stripe_customer_id")),
        "can_checkout": not account.get("stripe_subscription_id") or stripe_status in {
            "canceled", "unpaid", "incomplete_expired"
        },
        "plans": extension["plans"],
    }


@billing_bp.route("/billing")
def page():
    return render_template("billing.html")


@billing_bp.route("/api/billing/status")
def status():
    if not _extension()["enabled"]:
        return jsonify({"enabled": False, "access": True, "status": "disabled"})
    return jsonify(_status_for(g.auth_user))


@billing_bp.route("/api/billing/checkout", methods=["POST"])
def checkout():
    extension = _extension()
    if not extension["enabled"]:
        return jsonify({"error": "billing_disabled"}), 404
    if not extension["secret_key"]:
        return jsonify({"error": "billing_not_configured"}), 503
    plan = str((request.get_json(silent=True) or {}).get("plan") or "")
    plan_config = extension["plans"].get(plan)
    if not plan_config or not plan_config.get("price_id"):
        return jsonify({"error": "plan_unavailable"}), 503
    account = extension["store"].ensure_account(g.auth_user)
    if (account.get("stripe_subscription_id")
            and account.get("subscription_status") not in {"canceled", "unpaid", "incomplete_expired"}):
        return jsonify({"error": "manage_existing_subscription", "portal_url": "/billing"}), 409
    if not extension["store"].acquire_checkout_lock(g.auth_user["id"], plan):
        return jsonify({"error": "checkout_in_progress"}), 409
    kwargs = {
        "mode": "subscription",
        "line_items": [{"price": plan_config["price_id"], "quantity": 1}],
        "success_url": f"{_base_url()}/billing?checkout=success",
        "cancel_url": f"{_base_url()}/billing?checkout=canceled",
        "client_reference_id": str(g.auth_user["id"]),
        "metadata": {"auth_user_id": str(g.auth_user["id"]), "plan": plan},
        "subscription_data": {"metadata": {"auth_user_id": str(g.auth_user["id"]), "plan": plan}},
        "allow_promotion_codes": True,
        "expires_at": int(_now().timestamp()) + 1800,
    }
    trial_end = _parse_time(account.get("trial_ends_at"))
    if (not account.get("subscription_status") and trial_end
            and trial_end - _now() >= timedelta(hours=48)):
        kwargs["subscription_data"]["trial_end"] = int(trial_end.timestamp())
    if account.get("stripe_customer_id"):
        kwargs["customer"] = account["stripe_customer_id"]
    else:
        kwargs["customer_email"] = account["email"]
    try:
        checkout_session = _stripe().checkout.Session.create(**kwargs)
    except Exception:
        extension["store"].release_checkout_lock(g.auth_user["id"])
        raise
    return jsonify({"url": checkout_session.url})


@billing_bp.route("/api/billing/portal", methods=["POST"])
def portal():
    extension = _extension()
    if not extension["enabled"]:
        return jsonify({"error": "billing_disabled"}), 404
    if not extension["secret_key"]:
        return jsonify({"error": "billing_not_configured"}), 503
    account = extension["store"].ensure_account(g.auth_user)
    if not account.get("stripe_customer_id"):
        return jsonify({"error": "stripe_customer_required"}), 400
    portal_session = _stripe().billing_portal.Session.create(
        customer=account["stripe_customer_id"], return_url=f"{_base_url()}/billing"
    )
    return jsonify({"url": portal_session.url})


def _object_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@billing_bp.route("/api/billing/webhook", methods=["POST"])
def webhook():
    extension = _extension()
    if not extension["enabled"] or not extension["webhook_secret"]:
        return jsonify({"error": "webhook_unavailable"}), 503
    try:
        event = _stripe().Webhook.construct_event(
            request.get_data(), request.headers.get("Stripe-Signature", ""),
            extension["webhook_secret"],
        )
    except Exception:
        return jsonify({"error": "invalid_signature"}), 400

    event_id = _object_value(event, "id", "")
    event_type = _object_value(event, "type", "")
    event_created = int(_object_value(event, "created", 0) or 0)
    data = _object_value(_object_value(event, "data", {}), "object", {})
    metadata = _object_value(data, "metadata", {}) or {}
    auth_user_id = _object_value(metadata, "auth_user_id")
    plan = _object_value(metadata, "plan")
    customer_id = _object_value(data, "customer")
    subscription_id = _object_value(data, "subscription")
    subscription_status = None
    period_end = None
    cancel_at_period_end = None
    event_priority = {
        "checkout.session.completed": 20,
        "customer.subscription.created": 30,
        "customer.subscription.updated": 40,
        "customer.subscription.deleted": 50,
    }.get(event_type, 10)

    if event_type.startswith("customer.subscription."):
        subscription_id = _object_value(data, "id")
        subscription_status = _object_value(data, "status")
        period_end = _iso_from_unix(_object_value(data, "current_period_end"))
        cancel_at_period_end = bool(_object_value(data, "cancel_at_period_end", False))
    elif event_type == "checkout.session.completed":
        subscription_status = "active"
    elif event_type in {"invoice.payment_failed", "invoice.paid"}:
        # Subscription events carry the authoritative entitlement status.
        return jsonify({"received": True})

    if event_type in {
        "checkout.session.completed", "customer.subscription.created",
        "customer.subscription.updated", "customer.subscription.deleted",
        "checkout.session.expired",
    }:
        if event_type == "checkout.session.expired":
            if auth_user_id:
                extension["store"].release_checkout_lock(int(auth_user_id))
            return jsonify({"received": True})
        try:
            extension["store"].apply_event(
                event_id, event_type, event_created,
                auth_user_id=int(auth_user_id) if auth_user_id else None,
                customer_id=customer_id, subscription_id=subscription_id, plan=plan,
                subscription_status=subscription_status, current_period_end=period_end,
                cancel_at_period_end=cancel_at_period_end, event_priority=event_priority,
            )
        except Exception:
            return jsonify({"error": "webhook_processing_failed"}), 500
        if event_type == "checkout.session.completed" and auth_user_id:
            extension["store"].release_checkout_lock(int(auth_user_id))
    return jsonify({"received": True})


def init_billing(app):
    enabled = os.environ.get("DAILYDEX_BILLING_ENABLED", "0") == "1"
    if enabled and not app.config.get("DAILYDEX_AUTH_ENABLED"):
        raise RuntimeError("DailyDex billing requires authentication")
    auth_extension = app.extensions.get("dailydex_auth")
    db_path = auth_extension["store"].db_path if auth_extension else app.config.get("DB_PATH", "data/intelligence.db")
    plans = {
        "creator": {
            "name": "Creator", "amount": 12.99, "currency": "USD",
            "price_id": os.environ.get("STRIPE_CREATOR_PRICE_ID", ""),
        },
        "studio": {
            "name": "Studio", "amount": 33.99, "currency": "USD",
            "price_id": os.environ.get("STRIPE_STUDIO_PRICE_ID", ""),
        },
    }
    app.extensions["dailydex_billing"] = {
        "enabled": enabled,
        "store": BillingStore(db_path, max(1, int(os.environ.get("BILLING_TRIAL_DAYS", "14")))) if enabled else None,
        "secret_key": os.environ.get("STRIPE_SECRET_KEY", ""),
        "webhook_secret": os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
        "plans": plans,
    }
    app.register_blueprint(billing_bp)

    @app.before_request
    def require_subscription():
        if not enabled or request.method == "OPTIONS" or request.routing_exception is not None:
            return None
        endpoint = request.endpoint or ""
        if endpoint in _BILLING_ENDPOINTS or endpoint in {"auth.login", "auth.signup", "auth.logout", "auth.me", "health", "static"}:
            return None
        user = getattr(g, "auth_user", None)
        if not user:
            return None
        billing_status = _status_for(user)
        if billing_status["access"]:
            return None
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "subscription_required", "billing_url": "/billing",
                "billing": billing_status,
            }), 402
        return redirect("/billing")
