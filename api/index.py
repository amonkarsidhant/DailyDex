"""
api/index.py — Vercel serverless entry point for DailyDex.

Vercel's @vercel/python runtime looks for a callable named `app` in this file.
We import the Flask app from dashboard_new.py and re-export it.

Environment variables expected on Vercel:
  DATABASE_URL          — Supabase Postgres connection string (Transaction pooler URL)
  ANTHROPIC_API_KEY     — for LLM generation
  VERCEL=1              — set automatically by Vercel runtime

Background threads (EnrichmentService) are disabled on Vercel; use Cron Jobs
defined in vercel.json hitting /api/cron/enrich and /api/cron/fetch instead.
"""

import os
import sys

# Make sure the project root is on sys.path so all imports resolve correctly.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# On Vercel, disable the background enrichment thread — it runs via cron instead.
os.environ.setdefault("CREATOR_ENRICHER_PRIMARY", "0")
os.environ.setdefault("VERCEL", "1")

# Import the Flask application object.
from dashboard_new import app  # noqa: F401 — Vercel picks up the `app` name

# Vercel needs the handler to be the WSGI app object exported at module level.
# Nothing else needed.
