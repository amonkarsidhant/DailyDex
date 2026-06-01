-- ============================================================
-- DailyDex — Supabase / PostgreSQL schema
-- Run this once against your Supabase project via:
--   psql $DATABASE_URL -f supabase_schema.sql
-- or paste into the Supabase SQL editor.
-- ============================================================

-- ── saved_items ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saved_items (
    id                SERIAL PRIMARY KEY,
    title             TEXT NOT NULL,
    url               TEXT,
    source            TEXT,
    source_type       TEXT,
    category          TEXT,
    notes             TEXT,
    tags              TEXT,
    status            TEXT DEFAULT 'to_read',
    signal_score      INTEGER,
    creator_score     INTEGER,
    pipeline_type     TEXT DEFAULT 'intel',
    working_title     TEXT,
    hook              TEXT,
    format            TEXT,
    outline           TEXT,
    sources           TEXT,
    thumbnail_text    TEXT,
    priority          TEXT,
    published_url     TEXT,
    production_assets TEXT,
    production_status TEXT DEFAULT 'none',
    content_hash      TEXT,
    created_at        TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS'),
    updated_at        TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_items_url ON saved_items(url);

-- ── trend_history ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trend_history (
    id         SERIAL PRIMARY KEY,
    keyword    TEXT NOT NULL,
    source     TEXT,
    count      INTEGER DEFAULT 1,
    first_seen TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS'),
    last_seen  TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
);

-- ── intelligence_clusters ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS intelligence_clusters (
    id           SERIAL PRIMARY KEY,
    cluster_name TEXT NOT NULL,
    items_json   TEXT,
    created_at   TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
);

-- ── ignored_items ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ignored_items (
    id          SERIAL PRIMARY KEY,
    url         TEXT NOT NULL,
    title       TEXT,
    source_type TEXT,
    reason      TEXT DEFAULT 'user_ignored',
    created_at  TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ignored_items_url ON ignored_items(url);

-- ── tracked_topics ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tracked_topics (
    id         SERIAL PRIMARY KEY,
    topic      TEXT NOT NULL UNIQUE,
    reason     TEXT,
    notify     BOOLEAN DEFAULT TRUE,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
);

-- ── source_health ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS source_health (
    id                SERIAL PRIMARY KEY,
    source_name       TEXT NOT NULL UNIQUE,
    last_success      TEXT,
    last_failure      TEXT,
    failure_count     INTEGER DEFAULT 0,
    status            TEXT DEFAULT 'unknown',
    failure_reason    TEXT,
    item_count        INTEGER DEFAULT 0,
    using_cache       INTEGER DEFAULT 0,
    cache_age_seconds INTEGER DEFAULT 0,
    last_attempt      TEXT
);

-- ── seen_items ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS seen_items (
    id          SERIAL PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,
    title       TEXT,
    source_type TEXT,
    first_seen  TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS'),
    last_seen   TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_seen_items_url ON seen_items(url);

-- ── telegram_subscribers ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS telegram_subscribers (
    id        SERIAL PRIMARY KEY,
    chat_id   BIGINT NOT NULL UNIQUE,
    name      TEXT,
    joined_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
);

-- ── item_votes ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS item_votes (
    id         SERIAL PRIMARY KEY,
    item_url   TEXT NOT NULL,
    chat_id    BIGINT NOT NULL,
    voter_name TEXT,
    voted_at   TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS'),
    UNIQUE(item_url, chat_id)
);
CREATE INDEX IF NOT EXISTS idx_item_votes_url ON item_votes(item_url);

-- ── creator_assets ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS creator_assets (
    content_hash   TEXT PRIMARY KEY,
    payload_json   TEXT NOT NULL,
    model          TEXT,
    schema_version INTEGER DEFAULT 1,
    status         TEXT DEFAULT 'ready',
    error          TEXT,
    source_title   TEXT,
    source_url     TEXT,
    created_at     TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS'),
    updated_at     TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
);
CREATE INDEX IF NOT EXISTS idx_creator_assets_status ON creator_assets(status);

-- ── cluster_snapshots ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cluster_snapshots (
    topic        TEXT NOT NULL,
    hour_bucket  BIGINT NOT NULL,
    item_count   INTEGER NOT NULL,
    signal_sum   INTEGER NOT NULL,
    sources_json TEXT NOT NULL,
    PRIMARY KEY (topic, hour_bucket)
);
CREATE INDEX IF NOT EXISTS idx_cluster_snapshots_topic_bucket
    ON cluster_snapshots(topic, hour_bucket DESC);

-- ── agent_runs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_runs (
    id             TEXT PRIMARY KEY,
    agent_type     TEXT NOT NULL,
    topic          TEXT,
    target_id      TEXT,
    status         TEXT NOT NULL,
    stage          TEXT,
    progress       DOUBLE PRECISION DEFAULT 0,
    eta_sec        INTEGER,
    started_at     DOUBLE PRECISION,
    finished_at    DOUBLE PRECISION,
    result_summary TEXT,
    error          TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status_started
    ON agent_runs(status, started_at DESC);

-- ── agent_logs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_logs (
    run_id TEXT NOT NULL,
    ts     DOUBLE PRECISION NOT NULL,
    line   TEXT NOT NULL,
    PRIMARY KEY (run_id, ts)
);

-- ── schedule ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schedule (
    id         TEXT PRIMARY KEY,
    item_id    TEXT NOT NULL,
    day        TEXT NOT NULL,
    time       TEXT,
    kind       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'planned',
    created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_schedule_day ON schedule(day);

-- ── thumbnail_variants ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS thumbnail_variants (
    id             TEXT PRIMARY KEY,
    content_hash   TEXT NOT NULL,
    topic          TEXT,
    kind           TEXT NOT NULL,
    text_primary   TEXT,
    text_secondary TEXT,
    hue            INTEGER,
    image_path     TEXT,
    ctr_pred       DOUBLE PRECISION,
    picked         INTEGER DEFAULT 0,
    generated_by   TEXT,
    created_at     DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_thumbnail_variants_hash
    ON thumbnail_variants(content_hash, ctr_pred DESC);

-- ── studio_content ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS studio_content (
    story_key  TEXT NOT NULL,
    topic      TEXT,
    fmt        TEXT NOT NULL,
    body       TEXT,
    provider   TEXT,
    model      TEXT,
    status     TEXT NOT NULL DEFAULT 'queued',
    error      TEXT,
    research   TEXT,
    source_url TEXT,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (story_key, fmt)
);
CREATE INDEX IF NOT EXISTS idx_studio_content_story   ON studio_content(story_key, fmt);
CREATE INDEX IF NOT EXISTS idx_studio_content_updated ON studio_content(updated_at DESC);

-- ── publication_analytics ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS publication_analytics (
    id              SERIAL PRIMARY KEY,
    item_id         INTEGER NOT NULL,
    platform        TEXT NOT NULL,
    published_at    TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS'),
    views           INTEGER DEFAULT 0,
    impressions     INTEGER DEFAULT 0,
    ctr             DOUBLE PRECISION DEFAULT 0.0,
    engagement_rate DOUBLE PRECISION DEFAULT 0.0,
    status          TEXT DEFAULT 'live',
    FOREIGN KEY (item_id) REFERENCES saved_items(id),
    UNIQUE(item_id, platform)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_analytics_item_platform ON publication_analytics(item_id, platform);

-- ── repurposed_clips ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS repurposed_clips (
    id             TEXT PRIMARY KEY,
    parent_item_id INTEGER NOT NULL,
    title          TEXT,
    start_time     TEXT,
    end_time       TEXT,
    hook_text      TEXT,
    virality_score DOUBLE PRECISION DEFAULT 0.0,
    status         TEXT DEFAULT 'draft',
    published_url  TEXT,
    created_at     DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (parent_item_id) REFERENCES saved_items(id)
);
CREATE INDEX IF NOT EXISTS idx_repurposed_clips_parent ON repurposed_clips(parent_item_id);

-- ── ab_tests ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ab_tests (
    id              TEXT PRIMARY KEY,
    item_id         INTEGER NOT NULL,
    status          TEXT DEFAULT 'active',
    variant_a_title TEXT,
    variant_a_image TEXT,
    variant_b_title TEXT,
    variant_b_image TEXT,
    variant_a_ctr   DOUBLE PRECISION DEFAULT 0.0,
    variant_b_ctr   DOUBLE PRECISION DEFAULT 0.0,
    variant_a_views INTEGER DEFAULT 0,
    variant_b_views INTEGER DEFAULT 0,
    started_at      DOUBLE PRECISION NOT NULL,
    ended_at        DOUBLE PRECISION,
    FOREIGN KEY (item_id) REFERENCES saved_items(id)
);
CREATE INDEX IF NOT EXISTS idx_ab_tests_item ON ab_tests(item_id);
