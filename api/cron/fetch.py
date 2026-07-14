"""
api/cron/fetch.py — Vercel Cron Job: refresh intelligence feed.

Fetches fresh RSS/YouTube items, scores them, and writes to the database.
Runs on the schedule defined in vercel.json (e.g. every 2 hours).
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
os.environ.setdefault("CREATOR_ENRICHER_PRIMARY", "0")
os.environ.setdefault("VERCEL", "1")

from flask import Flask, jsonify
from cron_security import require_cron_secret

cron_app = Flask(__name__)

@cron_app.route("/api/cron/fetch", methods=["GET", "POST"])
def run_fetch():
    """Vercel Cron: fetch + score latest intelligence items."""
    auth_error = require_cron_secret()
    if auth_error:
        return auth_error
    try:
        # Import the refresh logic from the main app
        from dashboard_new import run_refresh
        result = run_refresh()
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

app = cron_app
