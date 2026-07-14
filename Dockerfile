FROM python:3.12-slim

# curl for healthcheck, git for any pip installs from git
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY src ./src
COPY config.json ./
COPY config ./config
ENV PYTHONPATH=/app/src

# Data directories (mounted as volume in production)
RUN mkdir -p /app/data/cache /app/data/digests /app/data/research_packs /app/data/settings

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

# Single Gunicorn worker: the creator-enrichment background thread
# is per-process. The orchestrator (orchestrator.py) runs as a sidecar
# container via docker-compose, not inside gunicorn.
ENV GUNICORN_WORKERS=1
ENV GUNICORN_TIMEOUT=180
ENV CREATOR_ENRICHER_PRIMARY=1

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:8888 -w ${GUNICORN_WORKERS:-2} --timeout ${GUNICORN_TIMEOUT:-180} --worker-class gthread --threads 4 src.dashboard_new:app"]