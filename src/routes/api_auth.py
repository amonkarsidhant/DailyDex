"""Authentication and request security for the shared DailyDex workspace."""

from __future__ import annotations

import hmac
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

import db_compat as sqlite3


auth_bp = Blueprint("auth", __name__)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PUBLIC_ENDPOINTS = {"auth.login", "auth.signup", "health"}


class AuthStore:
    """Small account store kept beside the existing application database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()
        if not sqlite3.DATABASE_URL and db_path and db_path != ":memory:":
            os.chmod(db_path, 0o600)

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_slot INTEGER NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                session_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    def count_users(self) -> int:
        conn = self._connect()
        row = conn.cursor().execute("SELECT COUNT(*) FROM auth_users").fetchone()
        conn.close()
        return int(row[0]) if row else 0

    def get_user(self, email: str):
        conn = self._connect()
        row = conn.cursor().execute(
            """
            SELECT id, email, display_name, password_hash, is_active, session_version
            FROM auth_users WHERE email = ?
            """,
            (email.strip().lower(),),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0],
            "email": row[1],
            "display_name": row[2],
            "password_hash": row[3],
            "is_active": bool(row[4]),
            "session_version": int(row[5]),
        }

    def create_user(self, email: str, display_name: str, password: str) -> bool:
        normalized = email.strip().lower()
        conn = self._connect()
        try:
            conn.cursor().execute(
                """
                INSERT INTO auth_users
                    (workspace_slot, email, display_name, password_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    1,
                    normalized,
                    display_name.strip(),
                    generate_password_hash(password, method="scrypt"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return True
        except Exception:
            if self.get_user(normalized):
                return False
            raise
        finally:
            conn.close()

    def record_login(self, email: str) -> None:
        conn = self._connect()
        conn.cursor().execute(
            "UPDATE auth_users SET last_login_at = ? WHERE email = ?",
            (datetime.now(timezone.utc).isoformat(), email.strip().lower()),
        )
        conn.commit()
        conn.close()


class AuthRateLimiter:
    """Process-local throttle for the single Gunicorn worker deployment."""

    def __init__(self, limit: int = 5, window_seconds: int = 900):
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts = {}
        self._lock = threading.Lock()

    def allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            recent = [
                stamp
                for stamp in self._attempts.get(key, [])
                if now - stamp < self.window_seconds
            ]
            self._attempts[key] = recent
            return len(recent) < self.limit

    def fail(self, key: str) -> None:
        with self._lock:
            self._attempts.setdefault(key, []).append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


def _auth_config():
    return current_app.extensions["dailydex_auth"]


def _csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _valid_csrf() -> bool:
    expected = session.get("csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
    if expected and supplied:
        expected_bytes = expected[:512].encode("utf-8", errors="ignore")
        supplied_bytes = supplied[:512].encode("utf-8", errors="ignore")
        if hmac.compare_digest(expected_bytes, supplied_bytes):
            return True

    origin = request.headers.get("Origin", "")
    if not origin:
        return False
    try:
        parsed = urlsplit(origin)
        expected_origin = urlsplit(request.host_url)
    except ValueError:
        return False
    return parsed.scheme == expected_origin.scheme and parsed.netloc == expected_origin.netloc


def _safe_next(target: str | None) -> str:
    target = (target or "").strip()
    try:
        parsed = urlsplit(target)
    except ValueError:
        return "/"
    if not target.startswith("/") or target.startswith("//"):
        return "/"
    if parsed.scheme or parsed.netloc:
        return "/"
    return target


def _client_key() -> str:
    return request.remote_addr or "unknown"


def _start_session(user) -> None:
    session.clear()
    session.permanent = True
    session["auth_user"] = user["email"]
    session["auth_version"] = user["session_version"]
    session["csrf_token"] = secrets.token_urlsafe(32)


def _session_user():
    email = session.get("auth_user")
    version = session.get("auth_version")
    if not email or version is None:
        return None
    user = _auth_config()["store"].get_user(email)
    if not user or not user["is_active"] or user["session_version"] != version:
        session.clear()
        return None
    return user


def _render_auth(mode: str, error: str = "", status: int = 200):
    config = _auth_config()
    signup_open = config["allow_signup"] and config["store"].count_users() == 0
    return (
        render_template(
            "auth.html",
            mode=mode,
            error=error,
            signup_open=signup_open,
            next_url=_safe_next(request.values.get("next")),
            csrf_token=_csrf_token(),
        ),
        status,
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method != "POST":
        if _session_user():
            return redirect("/")
        return _render_auth("login")

    email = (request.form.get("email") or "").strip().lower()
    key = _client_key()
    limiter = _auth_config()["limiter"]
    if not limiter.allowed(key):
        return _render_auth("login", "Too many attempts. Try again in 15 minutes.", 429)

    user = _auth_config()["store"].get_user(email)
    password_hash = user["password_hash"] if user else _auth_config()["dummy_hash"]
    password_ok = check_password_hash(password_hash, request.form.get("password") or "")
    if not user or not user["is_active"] or not password_ok:
        limiter.fail(key)
        return _render_auth("login", "Invalid email or password.", 401)

    limiter.clear(key)
    _auth_config()["store"].record_login(email)
    _start_session(user)
    return redirect(_safe_next(request.form.get("next")))


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    config = _auth_config()
    signup_open = config["allow_signup"] and config["store"].count_users() == 0
    if not signup_open:
        return _render_auth("signup", "Registration is closed for this workspace.", 403)
    if request.method != "POST":
        return _render_auth("signup")

    key = _client_key()
    limiter = config["limiter"]
    if not limiter.allowed(key):
        return _render_auth("signup", "Too many attempts. Try again in 15 minutes.", 429)

    invite = request.form.get("invite_code") or ""
    if not hmac.compare_digest(
        invite[:512].encode("utf-8", errors="ignore"),
        config["invite_code"].encode("utf-8", errors="ignore"),
    ):
        limiter.fail(key)
        return _render_auth("signup", "Invalid workspace invite code.", 403)

    email = (request.form.get("email") or "").strip().lower()
    display_name = (request.form.get("display_name") or "").strip()
    password = request.form.get("password") or ""
    confirmation = request.form.get("confirm_password") or ""
    if not _EMAIL_RE.match(email):
        return _render_auth("signup", "Enter a valid email address.", 400)
    if not display_name or len(display_name) > 80:
        return _render_auth("signup", "Display name is required and must be under 80 characters.", 400)
    if len(password) < 12 or len(password) > 128:
        return _render_auth("signup", "Password must be between 12 and 128 characters.", 400)
    if password != confirmation:
        return _render_auth("signup", "Passwords do not match.", 400)
    if not config["store"].create_user(email, display_name, password):
        return _render_auth("signup", "Registration is closed for this workspace.", 409)

    limiter.clear(key)
    user = config["store"].get_user(email)
    _start_session(user)
    return redirect("/")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/api/auth/me")
def me():
    user = g.auth_user
    return jsonify(
        {
            "authenticated": True,
            "user": {
                "email": user["email"],
                "display_name": user["display_name"],
            },
            "csrf_token": _csrf_token(),
        }
    )


def init_auth(app, db_path: str) -> None:
    """Install fail-closed authentication and request security on ``app``."""
    raw_enabled = os.environ.get("DAILYDEX_AUTH_ENABLED")
    production = os.environ.get("DAILYDEX_PRODUCTION", "0") == "1"
    if raw_enabled not in {None, "0", "1"}:
        raise RuntimeError("DAILYDEX_AUTH_ENABLED must be either 0 or 1")
    if production and raw_enabled != "1":
        raise RuntimeError("DAILYDEX_AUTH_ENABLED=1 is required in production")
    enabled = raw_enabled == "1"
    app.config["DAILYDEX_AUTH_ENABLED"] = enabled
    if not enabled:
        return

    secret_key = os.environ.get("FLASK_SECRET_KEY", "")
    if len(secret_key) < 32:
        raise RuntimeError("FLASK_SECRET_KEY must be set to at least 32 characters when auth is enabled")

    allow_signup = os.environ.get("AUTH_ALLOW_SIGNUP", "1") == "1"
    invite_code = os.environ.get("AUTH_INVITE_CODE", "")
    if allow_signup and len(invite_code) < 16:
        raise RuntimeError("AUTH_INVITE_CODE must be set to at least 16 characters when signup is enabled")

    secure_cookie = os.environ.get("SESSION_COOKIE_SECURE", "1") == "1"
    app.secret_key = secret_key
    app.config.update(
        SESSION_COOKIE_NAME="__Host-dailydex_session" if secure_cookie else "dailydex_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=secure_cookie,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(
            hours=max(1, int(os.environ.get("AUTH_SESSION_HOURS", "12")))
        ),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    )
    if os.environ.get("AUTH_TRUST_PROXY_HEADERS", "0") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    allowed_hosts = [
        host.strip()
        for host in os.environ.get("DAILYDEX_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    ]
    if allowed_hosts:
        app.config["TRUSTED_HOSTS"] = allowed_hosts + ["localhost", "127.0.0.1"]

    store = AuthStore(os.environ.get("AUTH_DB_PATH", db_path))
    app.extensions["dailydex_auth"] = {
        "store": store,
        "limiter": AuthRateLimiter(),
        "dummy_hash": generate_password_hash(secrets.token_urlsafe(24), method="scrypt"),
        "allow_signup": allow_signup,
        "invite_code": invite_code,
    }
    app.register_blueprint(auth_bp)

    @app.before_request
    def require_authentication():
        endpoint = request.endpoint or ""
        if request.method == "OPTIONS":
            return None
        if endpoint in _PUBLIC_ENDPOINTS:
            if request.method in _UNSAFE_METHODS and not _valid_csrf():
                return jsonify({"error": "csrf_failed"}), 400
            return None

        user = _session_user()
        if not user:
            if request.path.startswith("/api/") or endpoint == "static":
                return jsonify({"error": "authentication_required", "login_url": "/login"}), 401
            next_url = request.full_path.rstrip("?")
            return redirect(url_for("auth.login", next=next_url))

        g.auth_user = user
        if request.method in _UNSAFE_METHODS and not _valid_csrf():
            return jsonify({"error": "csrf_failed"}), 400
        return None

    @app.context_processor
    def inject_auth_context():
        return {
            "auth_csrf_token": _csrf_token(),
            "auth_user": getattr(g, "auth_user", None),
        }

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'",
        )
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        if request.endpoint != "static" and request.path != "/health":
            response.headers.setdefault("Cache-Control", "no-store")
        return response
