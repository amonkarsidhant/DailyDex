# Changelog

## v0.15 — Dual Deployment Profiles, Onboarding Wizard & Full Screenshot Suite

- added Self-hosted CLI vs Cloud VM API dual deployment mode ("Option B")
- added 4-stage interactive onboarding wizard (OAuth identity, Creator DNA, BYOK keys, engine boot)
- added no-auth YouTube Analytics scraper sync engine (`analytics_sync.py`)
- added terminal setup command verification engine (`command_validator.py`)
- added themed listicles engine for weekly content roundups
- captured high-fidelity Playwright screenshots of all 10+ cockpit views
- rewrote README from scratch: removed obsolete Vite references, corrected setup instructions, added onboarding gallery
- added `test_deployment_modes.py` (5 new tests, 59 total passing)
- updated `settings_manager.py` with deployment mode, custom CLI binary path overrides
- updated `cli_registry.py` with kilocode/agy providers and deployment mode filtering
- updated `llm_summary.py` with dynamic runtime query resolution and API fallbacks

## v0.14 — Notion Sync, Shorts Repurposer & Title A/B Testing

- added Notion sync pipeline with one-click outline export (`✅ Synced ↗`)
- added 9:16 Shorts slicer and auto-repurposer modal in Pipeline view
- added Title A/B Testing Engine with live CTR tracking
- added Copilot Chat view with context-aware LLM strategist
- added Profile view with brand voice customization

## v0.13 — Creator Onboarding & Identity System

- added creator identity onboarding enforcer in App.jsx
- added OAuth simulation popup (Google, GitHub, Microsoft Live)
- added onboarding submit/reset API routes
- added linked identity settings section in SettingsView

## v0.12 — Content Delivery & Themed Listicles

- added themed listicle categorization (Local AI, Coding Agents, Trending Repos)
- added listicle countdown script storyboarder
- added toggle view mode (Single Trends vs Listicle Compilations)

## v0.11 — React Creator Cockpit & Premium Thumbnails

- rebuilt frontend as a full React 18 cockpit with 10 views
- added Babel Standalone in-browser compilation (no build step)
- added premium AI-generated thumbnail mockups per topic cluster
- added live data bridge (`cockpit-live.js`) with SSE agent streaming
- added tweaks panel with theme and persona controls

## v0.10 — Creator Enrichment Pipeline


- replaced templated creator-pack stubs with a real Gemini CLI pipeline that runs asynchronously off the request path
- added a `creator_assets` SQLite table that caches the full creator pack per item, keyed by content hash
- introduced `creator_enricher.EnrichmentService`: in-process worker, dedupe queue, status reporting, and a blocking `ensure_pack` helper for the agentic flow
- rewrote `llm_summary` to return one structured JSON pack per item (hook, beats, script, titles, thumbnails, b-roll, on-screen cues) with schema validation, banned-phrase stripping, and retry on parse failure
- added `config/creator_profile.json` for brand voice, length rules, signature angles, and automation thresholds
- extended `agentic_researcher.recursive_dive` to return a strategic brief and wired it into a cluster-level promotion pipeline (`run_cluster_pipeline`) that saves to the creator pipeline and optionally fires the Production Forge
- new routes: `POST /api/enrich`, `GET /api/enrich-status`, `GET /api/enrich/<hash>`, `POST /api/forge/<id>`, `GET /api/forge-status/<id>`, `POST /api/agentic-run`
- new UI: enrichment badge per opportunity card, header queue pill, Forge button with live tab updates, auto-refreshing badges
- Dockerfile installs `@google/gemini-cli` (skip with `--build-arg DAILYDEX_SKIP_GEMINI=1`) and defaults to a single Gunicorn worker so the enrichment thread isn't duplicated
- removed unused legacy `dashboard.py`
- added `test_creator_enrichment.py` exercising the pipeline with a fake LLM

## v0.9

- added DailyDex Creator as a dedicated creator-intelligence variant
- introduced creator potential scoring, content opportunities, content clusters, research packs, and creator digest flows
- extended saved items to support a creator production pipeline from idea to published
- cleaned up the dashboard layout and restored a stable desktop sidebar
- simplified conflicting CSS and JS created during iterative UI fixes
- kept the multi-variant workflow, saved-item export, bulk actions, and theme controls in the current release
- verified the rendered UI in a browser before release

## v0.7.0-rc1 — DailyDex Product Experience Release Candidate

- renamed and productized the project as DailyDex
- updated product identity across README, UI, Docker, and docs
- preserved the v0.6 modern app-shell dashboard experience
- clarified release-candidate status and product positioning
- retained lightweight Flask + SQLite + JSON + vanilla JS architecture
- prepared the project for public-facing daily-use validation

## v0.6.0 UI Redesign Release Candidate

- redesigned the dashboard around a modern app-shell layout
- added a cleaner overview page with trust state, top signals, and source health
- introduced live dashboard updates using lightweight snapshot polling
- added saved-workflow and trends visualizations driven by live app data
- improved repository structure for public GitHub presentation
- expanded the news/blog source set with more AI-focused feeds
