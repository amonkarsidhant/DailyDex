"""
api/cron/enrich.py — Vercel Cron Job: run one enrichment cycle.

Called by Vercel on the schedule defined in vercel.json.
Dequeues pending creator enrichment items and processes them.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("CREATOR_ENRICHER_PRIMARY", "0")
os.environ.setdefault("VERCEL", "1")

from flask import Flask, jsonify

# Minimal Flask app just for this cron endpoint
cron_app = Flask(__name__)

@cron_app.route("/api/cron/enrich", methods=["GET", "POST"])
def run_enrich():
    """Vercel Cron: process one round of creator enrichment."""
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
