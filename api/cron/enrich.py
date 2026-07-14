"""
api/cron/enrich.py — Vercel Cron Job: run one enrichment cycle.

Called by Vercel on the schedule defined in vercel.json.
Dequeues pending creator enrichment items and processes them.
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

# Minimal Flask app just for this cron endpoint
cron_app = Flask(__name__)

@cron_app.route("/api/cron/enrich", methods=["GET", "POST"])
def run_enrich():
    """Vercel Cron: process one round of creator enrichment."""
    auth_error = require_cron_secret()
    if auth_error:
        return auth_error
    try:
        from data_models import IntelligenceDB
        from creator_enricher import EnrichmentService

        db = IntelligenceDB()
        svc = EnrichmentService(db)
        # Run one synchronous enrichment cycle (not a background thread)
        processed = svc.run_once() if hasattr(svc, "run_once") else 0
        return jsonify({"ok": True, "processed": processed})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Expose the WSGI app for Vercel
app = cron_app
