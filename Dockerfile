FROM python:3.11-slim

# Curl for the healthcheck; nodejs+npm so the Gemini CLI can run inside the
# container the same way it runs on a Raspberry Pi 4. Set DAILYDEX_SKIP_GEMINI=1
# at build time to skip the CLI install (useful for CI or Ollama-only setups).
ARG DAILYDEX_SKIP_GEMINI=0
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && if [ "$DAILYDEX_SKIP_GEMINI" = "0" ]; then \
         curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
         && apt-get install -y --no-install-recommends nodejs \
         && npm install -g @google/gemini-cli ; \
       fi \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application modules. Keep this list in sync with imports referenced by
# dashboard_new.py / agentic_researcher.py.
COPY fetch_news.py dashboard_new.py scoring_engine.py data_models.py \
     digest_generator.py creator_intelligence.py creator_enricher.py \
     llm_summary.py agentic_researcher.py config.json \
     cli_registry.py settings_manager.py creator_lab.py \
     thumbnail_generator.py db_compat.py analytics_sync.py \
     command_validator.py telegram_bot.py studio.py studio_job.py \
     refresh_job.py ./
COPY v0.1 ./v0.1
COPY config ./config
COPY templates ./templates
COPY static ./static

RUN mkdir -p /app/data/cache /app/data/digests /app/data/research_packs

EXPOSE 8888

ENV DATA_DIR=/app/data
ENV DIGEST_DIR=/app/data/digests
ENV DATA_FILE=/app/data/data.json
ENV SCORED_DATA_FILE=/app/data/data_scored.json
ENV CACHE_DIR=/app/data/cache
ENV DB_PATH=/app/data/intelligence.db
ENV RESEARCH_PACK_DIR=/app/data/research_packs
ENV DAILYDEX_SETTINGS_DIR=/app/data/settings
ENV CREATOR_PROFILE_PATH=/app/data/creator_profile.json
# Single Gunicorn worker by default: the creator-enrichment background thread
# is per-process, so multiple workers would mean multiple queues and duplicate
# Gemini subprocess calls. Override GUNICORN_WORKERS only if you also disable
# the enricher in the extra workers (CREATOR_ENRICHER_PRIMARY=0).
ENV GUNICORN_WORKERS=1
ENV GUNICORN_TIMEOUT=180
ENV CREATOR_ENRICHER_PRIMARY=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:8888 -w ${GUNICORN_WORKERS:-1} --timeout ${GUNICORN_TIMEOUT:-180} dashboard_new:app"]
