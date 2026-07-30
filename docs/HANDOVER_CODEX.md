# 🤝 Handover Document for Codex — DailyDex

**Project:** DailyDex — Creator Cockpit & AI Signal Cockpit  
**Date:** July 23, 2026  
**Test Suite Status:** **235 Passed, 0 Failed, 35 Skipped**  

---

## 📌 Executive Summary

DailyDex is a local-first AI content strategist and signal cockpit for tech creators and DevRel teams. It aggregates raw developer telemetry (GitHub Trending, HuggingFace, Hacker News, arXiv, YouTube tech channels) into structured video scripts, thumbnail concepts, and multi-platform text assets.

This handover document details the current codebase architecture, recently completed refactoring, and the hardened YouTube publication telemetry and rescue workflow.

---

## 🏗️ Architecture & Key Modules

```
DailyDex/
├── api/                   # Vercel serverless entry points (index.py)
├── config/                # Environment, profile & source configurations
├── docs/                  # Specs & Handover docs
│   ├── ideas/
│   │   └── analytics-virality-feedback-loop.md
│   └── HANDOVER_CODEX.md
├── frontend/              # Standalone React 18 / Vite SPA frontend
├── src/                   # Backend Python Flask application
│   ├── dashboard_new.py   # Primary Flask application entry point
│   ├── rescue_engine.py   # 48-Hour Video Rescue & Telemetry Evaluator
│   ├── youtube_oauth.py   # Google OAuth2 + YouTube Data & Analytics API v3 client
│   ├── llm_summary.py     # Multi-provider LLM query engine (Gemini, Claude, Ollama, OpenAI)
│   ├── factory.py         # Autonomous 3-agent workstation (Researcher, Writer, Thumbnail)
│   ├── analytics_sync.py  # Public & OAuth telemetry sync engine
│   ├── db_compat.py       # SQLite / Supabase database abstraction layer
│   └── routes/            # Modular Flask API blueprints
│       ├── api_auth.py
│       ├── api_billing.py
│       ├── api_compile.py
│       ├── api_factory.py
│       ├── api_integrations.py
│       ├── api_saved.py
│       ├── api_schedule.py
│       ├── api_settings.py
│       └── api_studio.py
├── video-engine/          # Remotion TSX vertical video generator
└── tests/                 # Comprehensive Pytest test suite (30+ test files)
```

---

## ⚡ Recently Completed Features & Refactoring

### 1. Flask Blueprint Modularization
The Flask application in `src/dashboard_new.py` was refactored into domain-isolated blueprints under `src/routes/`:
- `api_auth.py`: Session management, CSRF, login/signup store (`AuthStore`).
- `api_billing.py`: Stripe webhook and subscription state.
- `api_compile.py`: Digest & compilation exporter.
- `api_studio.py`: Autonomous content generation & Rescue Pack endpoints.

### 2. YouTube Publication Telemetry and Rescue Workflow
Implemented a truthful publication telemetry workflow without estimated private metrics:
- **`src/rescue_engine.py`**:
  - `evaluate_performance_status(ctr, views, channel_median_ctr)`: Categorizes video performance into `outlier`, `healthy`, or `low_ctr`.
  - `generate_rescue_pack(title, summary, niche)`: Produces 3 high-CTR replacement title variants and 2 AI visual thumbnail prompts using `query_llm`.
- **`src/youtube_oauth.py`**:
  - Added a CSRF-protected OAuth flow with durable token refresh.
  - Retrieves supported targeted Analytics API metrics: views, likes, comments, average view duration, and average view percentage.
  - Preserves the full mutable snippet before changing a title with `videos.update`.
- **`src/routes/api_studio.py`**:
  - `POST /api/studio/rescue-pack`: Generates rescue packages only for persisted publications with verified low-CTR evidence.
  - `POST /api/studio/rescue-apply`: Derives the YouTube ID from persisted state, propagates remote failures, and audits successful title changes.
- **`src/data_models.py`**:
  - Stores current publication state plus immutable metric samples and sync errors.
- **`src/orchestrator.py`**:
  - Synchronizes live YouTube publications every six hours.

Thumbnail impressions and CTR are not exposed by YouTube's targeted Analytics API. DailyDex therefore never estimates them. Observed YouTube Studio values can be recorded through `POST /api/analytics/observations`; fully automated CTR ingestion requires the asynchronous YouTube Reporting API.

---

## 🧪 Testing & Verification

### Running the Test Suite

Always execute tests using the local virtual environment:

```bash
# Run complete test suite
.venv/bin/python -m pytest -q

# Run specific rescue engine tests
.venv/bin/python -m pytest tests/test_rescue_engine.py -v

# Run studio endpoint tests
.venv/bin/python -m pytest tests/test_studio_jobs.py -v
```

*Current Pass Rate:* **235 passed, 35 skipped, 0 failed.**

---

## 📋 Immediate Next Steps for Codex

1. **YouTube Reporting API**:
   - Add asynchronous bulk-report job creation and download if automatic thumbnail impressions and CTR are required.

2. **Frontend Lint Baseline**:
   - Resolve the migration frontend's existing ESLint backlog and add rescue-modal component tests.

3. **LLM Prompt Weight Tuning**:
   - In `src/factory.py`, expand agent system prompts to read historical high-performing vs low-performing titles from `intelligence.db` to continuously calibrate future hook generation.

---

## 🔒 Security & Environment Notes

- **Database**: SQLite default at `data/intelligence.db` (override via `DB_PATH`).
- **Secrets**: Store Google Client ID / Secret in `.env` or settings manager (`google_client_id`, `google_client_secret`).
- **Local Dev Server**: Run backend with `.venv/bin/python src/dashboard_new.py`.
