"""Authentication helper for standalone Vercel cron applications."""

import hmac
import os

from flask import jsonify, request


def require_cron_secret():
    expected = os.environ.get("CRON_SECRET", "")
    if len(expected) < 32:
        return jsonify({"ok": False, "error": "cron_not_configured"}), 503
    header = request.headers.get("Authorization", "")
    supplied = header[7:] if header.startswith("Bearer ") else ""
    if not supplied or not hmac.compare_digest(
        supplied[:512].encode("utf-8", errors="ignore"),
        expected.encode("utf-8", errors="ignore"),
    ):
        return jsonify({"ok": False, "error": "authentication_required"}), 401
    return None
