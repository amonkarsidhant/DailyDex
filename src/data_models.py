#!/usr/bin/env python3
"""Data models for DailyDex - SQLite + PostgreSQL storage"""

# db_compat provides a transparent sqlite3-compatible interface that
# automatically routes to Postgres when DATABASE_URL is set, or falls
# back to plain sqlite3 for local development.
import db_compat as sqlite3

if not sqlite3.DATABASE_URL:
    # SQLite-only: apply WAL mode and increased timeout for concurrency.
    _orig_sq3_connect = sqlite3.connect
    def custom_connect(*args, **kwargs):
        import sqlite3 as _sq3
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30.0
        conn = _orig_sq3_connect(*args, **kwargs)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        return conn
    sqlite3.connect = custom_connect

import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DEFAULT_DB_PATH = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "intelligence.db"))
DEFAULT_DIGEST_DIR = os.environ.get("DIGEST_DIR", os.path.join(DATA_DIR, "digests"))


class IntelligenceDB:
    """SQLite database for saved intelligence"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        if db_path != ":memory:" and db_path:
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Saved items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT,
                source TEXT,
                source_type TEXT,
                category TEXT,
                notes TEXT,
                tags TEXT,
                status TEXT DEFAULT 'to_read',
                signal_score INTEGER,
                creator_score INTEGER,
                pipeline_type TEXT DEFAULT 'intel',
                working_title TEXT,
                hook TEXT,
                format TEXT,
                outline TEXT,
                sources TEXT,
                thumbnail_text TEXT,
                priority TEXT,
                published_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("PRAGMA table_info(saved_items)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        creator_columns = {
            "creator_score": "INTEGER",
            "pipeline_type": "TEXT DEFAULT 'intel'",
            "working_title": "TEXT",
            "hook": "TEXT",
            "format": "TEXT",
            "outline": "TEXT",
            "sources": "TEXT",
            "thumbnail_text": "TEXT",
            "priority": "TEXT",
            "published_url": "TEXT",
            "production_assets": "TEXT",
            "production_status": "TEXT DEFAULT 'none'",
            "content_hash": "TEXT",
        }
        for column, definition in creator_columns.items():
            if column not in existing_columns:
                cursor.execute(f"ALTER TABLE saved_items ADD COLUMN {column} {definition}")
        
        # Trend history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trend_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                source TEXT,
                count INTEGER DEFAULT 1,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Intelligence clusters table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS intelligence_clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_name TEXT NOT NULL,
                items_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Ignored items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ignored_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                title TEXT,
                source_type TEXT,
                reason TEXT DEFAULT 'user_ignored',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tracked topics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracked_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL UNIQUE,
                reason TEXT,
                notify BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Source health table (extended)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL UNIQUE,
                last_success TEXT,
                last_failure TEXT,
                failure_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'unknown',
                failure_reason TEXT,
                item_count INTEGER DEFAULT 0,
                using_cache INTEGER DEFAULT 0,
                cache_age_seconds INTEGER DEFAULT 0,
                last_attempt TEXT
            )
        """)

        # Seen items table (for tracking what's new since last check)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                source_type TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Unique index on seen_items.url
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_seen_items_url ON seen_items(url)")

        # Unique index on saved_items.url for deduplication
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_items_url ON saved_items(url)")

        # Telegram subscribers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL UNIQUE,
                name TEXT,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Friend votes table — one vote per user per item
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_url TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                voter_name TEXT,
                voted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(item_url, chat_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_item_votes_url ON item_votes(item_url)")

        # Cached LLM creator enrichment, keyed by content hash
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creator_assets (
                content_hash TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                model TEXT,
                schema_version INTEGER DEFAULT 1,
                status TEXT DEFAULT 'ready',
                error TEXT,
                source_title TEXT,
                source_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_creator_assets_status ON creator_assets(status)")

        # ── Creator Cockpit tables (Phases 1-5) ──────────────────────────
        # P1: per-(topic, hour) cluster snapshots for trend time-series.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cluster_snapshots (
                topic         TEXT NOT NULL,
                hour_bucket   INTEGER NOT NULL,
                item_count    INTEGER NOT NULL,
                signal_sum    INTEGER NOT NULL,
                sources_json  TEXT NOT NULL,
                PRIMARY KEY (topic, hour_bucket)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cluster_snapshots_topic_bucket
                ON cluster_snapshots(topic, hour_bucket DESC)
        """)

        # P2: multi-agent runner state + per-run log lines.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_runs (
                id           TEXT PRIMARY KEY,
                agent_type   TEXT NOT NULL,
                topic        TEXT,
                target_id    TEXT,
                status       TEXT NOT NULL,
                stage        TEXT,
                progress     REAL DEFAULT 0,
                eta_sec      INTEGER,
                started_at   REAL,
                finished_at  REAL,
                result_summary TEXT,
                error        TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_runs_status_started
                ON agent_runs(status, started_at DESC)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_logs (
                run_id  TEXT NOT NULL,
                ts      REAL NOT NULL,
                line    TEXT NOT NULL,
                PRIMARY KEY (run_id, ts)
            )
        """)

        # P3: publishing/production calendar.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id          TEXT PRIMARY KEY,
                item_id     TEXT NOT NULL,
                day         TEXT NOT NULL,
                time        TEXT,
                kind        TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'planned',
                created_at  REAL NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_day ON schedule(day)")

        # P5: thumbnail variant store.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thumbnail_variants (
                id             TEXT PRIMARY KEY,
                content_hash   TEXT NOT NULL,
                topic          TEXT,
                kind           TEXT NOT NULL,
                text_primary   TEXT,
                text_secondary TEXT,
                hue            INTEGER,
                image_path     TEXT,
                ctr_pred       REAL,
                picked         INTEGER DEFAULT 0,
                generated_by   TEXT,
                created_at     REAL NOT NULL
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_thumbnail_variants_hash
                ON thumbnail_variants(content_hash, ctr_pred DESC)
        """)

        # Creator Central — autonomously generated content, one row per
        # (story, format). Regeneration overwrites in place.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS studio_content (
                story_key   TEXT NOT NULL,
                topic       TEXT,
                fmt         TEXT NOT NULL,
                body        TEXT,
                provider    TEXT,
                model       TEXT,
                status      TEXT NOT NULL DEFAULT 'queued',
                error       TEXT,
                research    TEXT,
                source_url  TEXT,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL,
                PRIMARY KEY (story_key, fmt)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_studio_content_story
                ON studio_content(story_key, fmt)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_studio_content_updated
                ON studio_content(updated_at DESC)
        """)

        # CEO closed-loop: publication analytics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS publication_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                published_at TEXT DEFAULT CURRENT_TIMESTAMP,
                views INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                ctr REAL DEFAULT 0.0,
                engagement_rate REAL DEFAULT 0.0,
                status TEXT DEFAULT 'live',
                FOREIGN KEY (item_id) REFERENCES saved_items(id)
            )
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_analytics_item_platform 
                ON publication_analytics(item_id, platform)
        """)

        # 9:16 Shorts / Repurposed clips table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repurposed_clips (
                id TEXT PRIMARY KEY,
                parent_item_id INTEGER NOT NULL,
                title TEXT,
                start_time TEXT,
                end_time TEXT,
                hook_text TEXT,
                virality_score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'draft',
                published_url TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY (parent_item_id) REFERENCES saved_items(id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_repurposed_clips_parent 
                ON repurposed_clips(parent_item_id)
        """)

        # Title & Thumbnail A/B Tests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ab_tests (
                id TEXT PRIMARY KEY,
                item_id INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                variant_a_title TEXT,
                variant_a_image TEXT,
                variant_b_title TEXT,
                variant_b_image TEXT,
                variant_a_ctr REAL DEFAULT 0.0,
                variant_b_ctr REAL DEFAULT 0.0,
                variant_a_views INTEGER DEFAULT 0,
                variant_b_views INTEGER DEFAULT 0,
                started_at REAL NOT NULL,
                ended_at REAL,
                FOREIGN KEY (item_id) REFERENCES saved_items(id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ab_tests_item 
                ON ab_tests(item_id)
        """)

        conn.commit()
        conn.close()

    # ---- studio_content helpers (Creator Central) ----

    def studio_set_status(self, story_key: str, topic: str, fmt: str,
                          status: str, *, research: str = None, source_url: str = None) -> None:
        """Upsert a content row to a status (queued/generating), preserving body."""
        now = time.time()
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO studio_content
                (story_key, topic, fmt, status, research, source_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(story_key, fmt) DO UPDATE SET
                status=excluded.status, topic=excluded.topic,
                research=COALESCE(excluded.research, studio_content.research),
                source_url=COALESCE(excluded.source_url, studio_content.source_url),
                updated_at=excluded.updated_at
        """, (story_key, topic, fmt, status, research, source_url, now, now))
        conn.commit()
        conn.close()

    def studio_save_result(self, story_key: str, topic: str, fmt: str, result: Dict) -> None:
        """Persist a finished generation (body + provider + status)."""
        now = time.time()
        status = "ready" if result.get("ok") else "failed"
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO studio_content
                (story_key, topic, fmt, body, provider, model, status, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(story_key, fmt) DO UPDATE SET
                body=excluded.body, provider=excluded.provider, model=excluded.model,
                status=excluded.status, error=excluded.error, topic=excluded.topic,
                updated_at=excluded.updated_at
        """, (story_key, topic, fmt, result.get("body", ""), result.get("provider"),
              result.get("model"), status, result.get("error"), now, now))
        conn.commit()
        conn.close()

    def studio_get_story(self, story_key: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM studio_content WHERE story_key = ? ORDER BY fmt", (story_key,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def studio_list_stories(self, limit: int = 30) -> List[Dict]:
        """Group content by story, newest story first; each carries its formats."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM studio_content ORDER BY updated_at DESC"
        ).fetchall()
        conn.close()
        stories: Dict[str, Dict] = {}
        for r in rows:
            d = dict(r)
            s = stories.setdefault(d["story_key"], {
                "story_key": d["story_key"], "topic": d["topic"],
                "source_url": d["source_url"], "updated_at": d["updated_at"],
                "formats": {},
            })
            s["formats"][d["fmt"]] = {
                "format": d["fmt"], "body": d["body"], "provider": d["provider"],
                "model": d["model"], "status": d["status"], "error": d["error"],
                "updated_at": d["updated_at"],
            }
            s["updated_at"] = max(s["updated_at"], d["updated_at"])
        ordered = sorted(stories.values(), key=lambda x: x["updated_at"], reverse=True)
        return ordered[:limit]

    # ---- creator_assets helpers ----

    def get_creator_asset(self, content_hash: str) -> Optional[Dict]:
        if not content_hash:
            return None
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM creator_assets WHERE content_hash = ?", (content_hash,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        out = dict(row)
        try:
            out["payload"] = json.loads(out.get("payload_json") or "{}")
        except Exception:
            out["payload"] = {}
        return out

    def upsert_creator_asset(self, content_hash: str, payload: Dict, model: str = "", status: str = "ready", error: str = "", source_title: str = "", source_url: str = "", schema_version: int = 1) -> None:
        if not content_hash:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO creator_assets (content_hash, payload_json, model, schema_version, status, error, source_title, source_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(content_hash) DO UPDATE SET
                payload_json = excluded.payload_json,
                model = excluded.model,
                schema_version = excluded.schema_version,
                status = excluded.status,
                error = excluded.error,
                source_title = excluded.source_title,
                source_url = excluded.source_url,
                updated_at = excluded.updated_at
        """, (content_hash, json.dumps(payload or {}), model, schema_version, status, error, source_title, source_url, now, now))
        conn.commit()
        conn.close()

    def mark_creator_asset_status(self, content_hash: str, status: str, error: str = "") -> None:
        if not content_hash:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO creator_assets (content_hash, payload_json, status, error, updated_at)
            VALUES (?, '{}', ?, ?, ?)
            ON CONFLICT(content_hash) DO UPDATE SET
                status = excluded.status,
                error = excluded.error,
                updated_at = excluded.updated_at
        """, (content_hash, status, error, now))
        conn.commit()
        conn.close()

    def creator_assets_stats(self) -> Dict[str, int]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) FROM creator_assets GROUP BY status")
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return counts

    def set_production_assets(self, item_id: int, assets: Dict, status: str = "ready", error: str = "") -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE saved_items SET production_assets = ?, production_status = ?, updated_at = ? WHERE id = ?",
            (json.dumps(assets or {}), status, datetime.now().isoformat(), item_id),
        )
        conn.commit()
        conn.close()
        return True

    def _deserialize_row(self, row) -> Dict:
        """Map Row to dict and deserialize structured columns."""
        item = dict(row)
        for key in ["tags", "sources", "outline", "three_beat_structure", "thumbnail_text"]:
            if item.get(key):
                try:
                    item[key] = json.loads(item[key])
                except Exception:
                    if key == "tags" and isinstance(item[key], str) and "," in item[key]:
                        item[key] = [t.strip() for t in item[key].split(",")]
                    else:
                        item[key] = [item[key]] if item[key] is not None else []
            else:
                item[key] = []
                
        if item.get("production_assets"):
            try:
                item["production_assets"] = json.loads(item["production_assets"])
            except Exception:
                item["production_assets"] = {}
        else:
            item["production_assets"] = {}
        return item

    def get_saved_item(self, item_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self._deserialize_row(row)

    def _serialize_value(self, key: str, value):
        """Serialize structured values for SQLite storage."""
        if key in {"tags", "sources", "outline", "thumbnail_text", "three_beat_structure"}:
            if value is None:
                return json.dumps([])
            if isinstance(value, str):
                return value
            return json.dumps(value)
        return value

    def _default_pipeline_type(self, item: Dict) -> str:
        status = item.get("status", "")
        if item.get("pipeline_type"):
            return item.get("pipeline_type")
        if status in {"idea", "researching", "script_ready", "recording", "published", "archived"}:
            return "creator"
        return "intel"
    
    def save_item(self, item: Dict) -> int:
        """Save an item to the database - updates if URL already exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        url = item.get("url")
        pipeline_type = self._default_pipeline_type(item)
        tags = self._serialize_value("tags", item.get("tags", []))
        sources = self._serialize_value("sources", item.get("sources", []))
        outline = self._serialize_value("outline", item.get("outline", []))
        thumbnail_text = self._serialize_value("thumbnail_text", item.get("thumbnail_text", []))
        
        # Check if item with this URL already exists
        if url:
            cursor.execute("SELECT id FROM saved_items WHERE url = ?", (url,))
            existing = cursor.fetchone()
            if existing:
                # Update existing item instead of inserting
                cursor.execute("""
                    UPDATE saved_items SET 
                        title = ?, source = ?, source_type = ?, category = ?,
                        notes = ?, tags = ?, status = ?, signal_score = ?, creator_score = ?,
                        pipeline_type = ?, working_title = ?, hook = ?, format = ?,
                        outline = ?, sources = ?, thumbnail_text = ?, priority = ?, published_url = ?,
                        updated_at = ?
                    WHERE url = ?
                """, (
                    item.get("title"),
                    item.get("source"),
                    item.get("source_type"),
                    item.get("category"),
                    item.get("notes", ""),
                    tags,
                    item.get("status", "to_read"),
                    item.get("signal_score"),
                    item.get("creator_score"),
                    pipeline_type,
                    item.get("working_title"),
                    item.get("hook"),
                    item.get("format"),
                    outline,
                    sources,
                    thumbnail_text,
                    item.get("priority"),
                    item.get("published_url"),
                    datetime.now().isoformat(),
                    url
                ))
                conn.commit()
                conn.close()
                return existing[0]
        
        cursor.execute("""
            INSERT INTO saved_items (
                title, url, source, source_type, category, notes, tags, status, signal_score,
                creator_score, pipeline_type, working_title, hook, format, outline, sources,
                thumbnail_text, priority, published_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.get("title"),
            url,
            item.get("source"),
            item.get("source_type"),
            item.get("category"),
            item.get("notes", ""),
            tags,
            item.get("status", "to_read"),
            item.get("signal_score"),
            item.get("creator_score"),
            pipeline_type,
            item.get("working_title"),
            item.get("hook"),
            item.get("format"),
            outline,
            sources,
            thumbnail_text,
            item.get("priority"),
            item.get("published_url")
        ))
        
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return item_id
    
    def update_item(self, item_id: int, updates: Dict) -> bool:
        """Update a saved item"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        set_clauses = []
        values = []
        
        for key in [
            "notes", "tags", "status", "pipeline_type", "creator_score",
            "working_title", "hook", "format", "outline", "sources",
            "thumbnail_text", "priority", "published_url",
        ]:
            if key in updates:
                set_clauses.append(f"{key} = ?")
                values.append(self._serialize_value(key, updates[key]))
        
        if set_clauses:
            set_clauses.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(item_id)
            
            cursor.execute(f"""
                UPDATE saved_items 
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """, values)
            
            conn.commit()
        
        conn.close()
        return True
    
    def delete_item(self, item_id: int) -> bool:
        """Delete a saved item"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_items WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        return True
    
    def update_status(self, item_id: int, status: str) -> bool:
        """Update status of a saved item"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE saved_items SET status = ?, updated_at = ? WHERE id = ?", (status, datetime.now().isoformat(), item_id))
        conn.commit()
        conn.close()
        return True
    
    def update_notes(self, item_id: int, notes: str, tags: List[str]) -> bool:
        """Update notes and tags of a saved item"""
        return self.update_item(item_id, {"notes": notes, "tags": tags})
    
    def get_saved_items(self, status: Optional[str] = None, pipeline_type: Optional[str] = None) -> List[Dict]:
        """Get all saved items, optionally filtered by status"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = []
        values = []
        if status:
            conditions.append("status = ?")
            values.append(status)
        if pipeline_type:
            conditions.append("pipeline_type = ?")
            values.append(pipeline_type)

        query = "SELECT * FROM saved_items"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        cursor.execute(query, tuple(values))
        
        rows = cursor.fetchall()
        conn.close()
        
        items = []
        for row in rows:
            items.append(self._deserialize_row(row))
        return items
    
    def record_keyword(self, keyword: str, source: str) -> None:
        """Record a keyword occurrence for trend tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if keyword exists
        cursor.execute("SELECT * FROM trend_history WHERE keyword = ?", (keyword,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("""
                UPDATE trend_history 
                SET count = count + 1, last_seen = ?
                WHERE keyword = ?
            """, (datetime.now().isoformat(), keyword))
        else:
            cursor.execute("""
                INSERT INTO trend_history (keyword, source, count)
                VALUES (?, ?, 1)
            """, (keyword, source))
        
        conn.commit()
        conn.close()
    
    def get_trending_keywords(self, limit: int = 10) -> List[Dict]:
        """Get trending keywords"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM trend_history 
            ORDER BY count DESC, last_seen DESC 
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ===== Ignored Items =====
    def ignore_item(self, url: str, title: str = "", source_type: str = "", reason: str = "user_ignored") -> int:
        """Add an item to the ignore list"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO ignored_items (url, title, source_type, reason)
            VALUES (?, ?, ?, ?)
        """, (url, title, source_type, reason))
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return item_id
    
    def is_ignored(self, url: str) -> bool:
        """Check if URL is in ignore list"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM ignored_items WHERE url = ?", (url,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def get_ignored_items(self) -> List[Dict]:
        """Get all ignored items"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ignored_items ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ===== Tracked Topics =====
    def add_tracked_topic(self, topic: str, reason: str = "") -> int:
        """Add a topic to track"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO tracked_topics (topic, reason)
            VALUES (?, ?)
        """, (topic, reason))
        topic_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return topic_id
    
    def remove_tracked_topic(self, topic_id: int) -> bool:
        """Remove a tracked topic"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tracked_topics WHERE id = ?", (topic_id,))
        conn.commit()
        conn.close()
        return True
    
    def get_tracked_topics(self) -> List[Dict]:
        """Get all tracked topics"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracked_topics ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ===== Source Health =====
    def update_source_health(self, source_name: str, success: bool, item_count: int = 0, 
                             failure_reason: str = None, using_cache: bool = False, 
                             cache_age_seconds: int = 0) -> None:
        """Update source health status with extended fields"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        if success:
            cursor.execute("""
                INSERT OR REPLACE INTO source_health 
                (source_name, last_success, failure_count, status, item_count, failure_reason, using_cache, cache_age_seconds, last_attempt)
                VALUES (?, ?, 0, 'ok', ?, NULL, ?, 0, ?)
            """, (source_name, now, item_count, 1 if using_cache else 0, now))
        else:
            status = "using_cache" if using_cache else "failed"
            cursor.execute("""
                INSERT INTO source_health 
                (source_name, last_failure, failure_count, status, failure_reason, item_count, last_attempt, using_cache, cache_age_seconds)
                VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    last_failure = excluded.last_failure,
                    failure_count = failure_count + 1,
                    status = excluded.status,
                    failure_reason = excluded.failure_reason,
                    item_count = excluded.item_count,
                    last_attempt = excluded.last_attempt,
                    using_cache = excluded.using_cache,
                    cache_age_seconds = excluded.cache_age_seconds
            """, (source_name, now, status, failure_reason or "Unknown error", item_count, now, 1 if using_cache else 0, cache_age_seconds))
        
        conn.commit()
        conn.close()
    
    def get_source_health(self) -> List[Dict]:
        """Get health status of all sources"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM source_health ORDER BY source_name")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ===== Seen Items (What's New) =====
    def mark_seen_items(self, items: List[Dict]) -> None:
        """Mark items as seen, update last_seen for existing items"""
        if not items:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        for item in items:
            url = item.get("url")
            if not url:
                continue
            cursor.execute("""
                INSERT INTO seen_items (url, title, source_type, last_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title = excluded.title,
                    source_type = excluded.source_type,
                    last_seen = excluded.last_seen
            """, (url, item.get("title", ""), item.get("source_type", ""), now))
        
        conn.commit()
        conn.close()
    
    def get_new_items(self, items: List[Dict]) -> List[Dict]:
        """Return items that are new today (first_seen today)"""
        if not items:
            return []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        new_today_urls = set()
        
        cursor.execute("SELECT url FROM seen_items WHERE first_seen LIKE ?", (f'{today}%',))
        for row in cursor.fetchall():
            new_today_urls.add(row[0])
        
        new_items = []
        for item in items:
            url = item.get("url")
            if url in new_today_urls:
                new_items.append(item)
        
        conn.close()
        return new_items
    
    def get_new_item_count(self) -> int:
        """Get count of new items seen today"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM seen_items WHERE first_seen LIKE ?", (f'{today}%',))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    # ---- P1: cluster_snapshots helpers ----

    def write_cluster_snapshot(self, topic: str, hour_bucket: int, item_count: int,
                               signal_sum: int, sources: str) -> None:
        """Idempotent upsert — re-running the snapshotter in the same hour is safe."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO cluster_snapshots (topic, hour_bucket, item_count, signal_sum, sources_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(topic, hour_bucket) DO UPDATE SET
                item_count=excluded.item_count,
                signal_sum=excluded.signal_sum,
                sources_json=excluded.sources_json
            """,
            (topic, int(hour_bucket), int(item_count), int(signal_sum), sources),
        )
        conn.commit()
        conn.close()

    # ===== Telegram Subscribers =====

    def add_subscriber(self, chat_id: int, name: str = "") -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO telegram_subscribers (chat_id, name) VALUES (?, ?)",
            (chat_id, name),
        )
        conn.commit()
        conn.close()

    def read_cluster_history(self, topic: str, hours: int = 168) -> List[tuple]:
        """Returns list of (hour_bucket, item_count, signal_sum), newest-last."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT hour_bucket, item_count, signal_sum
            FROM cluster_snapshots
            WHERE topic = ?
            ORDER BY hour_bucket DESC
            LIMIT ?
            """,
            (topic, int(hours)),
        )
        rows = cursor.fetchall()
        conn.close()
        return list(reversed(rows))

    def first_seen_hour(self, topic: str) -> Optional[int]:
        """Earliest hour_bucket where item_count > 0, or None."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MIN(hour_bucket) FROM cluster_snapshots WHERE topic = ? AND item_count > 0",
            (topic,),
        )
        row = cursor.fetchone()
        conn.close()
        return int(row[0]) if row and row[0] is not None else None

    def trim_cluster_snapshots(self, older_than_hour: int) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cluster_snapshots WHERE hour_bucket < ?", (int(older_than_hour),))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    # ---- P2: agent_runs / agent_logs helpers ----

    def insert_agent_run(self, run_id: str, agent_type: str, topic: str = None,
                         target_id: str = None, eta_sec: int = None) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO agent_runs (id, agent_type, topic, target_id, status, progress, eta_sec)
            VALUES (?, ?, ?, ?, 'queued', 0, ?)
            """,
            (run_id, agent_type, topic, target_id, eta_sec),
        )
        conn.commit()
        conn.close()

    def update_agent_run(self, run_id: str, **fields) -> None:
        allowed = {"status", "stage", "progress", "eta_sec", "started_at",
                   "finished_at", "result_summary", "error", "topic", "target_id"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return
        cols = ", ".join(f"{k} = ?" for k in sets)
        conn = sqlite3.connect(self.db_path)
        conn.execute(f"UPDATE agent_runs SET {cols} WHERE id = ?", (*sets.values(), run_id))
        conn.commit()
        conn.close()

    def get_agent_run(self, run_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_agent_runs(self, status: str = None, limit: int = 50) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if status:
            cursor.execute(
                "SELECT * FROM agent_runs WHERE status = ? ORDER BY started_at DESC LIMIT ?",
                (status, int(limit)),
            )
        else:
            cursor.execute(
                "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT ?", (int(limit),)
            )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def list_active_agent_runs(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM agent_runs WHERE status IN ('queued','running') ORDER BY started_at DESC"
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def append_agent_log(self, run_id: str, ts: float, line: str) -> None:
        conn = sqlite3.connect(self.db_path)
        # ts is PK with run_id; nudge on collision so rapid logs don't drop
        try:
            conn.execute("INSERT INTO agent_logs (run_id, ts, line) VALUES (?, ?, ?)",
                         (run_id, float(ts), line))
        except sqlite3.IntegrityError:
            conn.execute("INSERT INTO agent_logs (run_id, ts, line) VALUES (?, ?, ?)",
                         (run_id, float(ts) + 1e-4, line))
        conn.commit()
        conn.close()

    def get_agent_logs(self, run_id: str, limit: int = 200) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ts, line FROM agent_logs WHERE run_id = ? ORDER BY ts ASC LIMIT ?",
            (run_id, int(limit)),
        )
        rows = [{"ts": r[0], "line": r[1]} for r in cursor.fetchall()]
        conn.close()
        return rows

    def trim_agent_logs(self, older_than_ts: float) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM agent_logs WHERE ts < ?", (float(older_than_ts),))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    # ---- P3: schedule helpers ----

    def insert_schedule(self, sched_id: str, item_id: str, day: str, kind: str,
                        time: str = None, status: str = "planned", created_at: float = None) -> None:
        import time as _time
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO schedule (id, item_id, day, time, kind, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sched_id, str(item_id), day, time, kind, status, created_at or _time.time()),
        )
        conn.commit()
        conn.close()

    def get_schedule_range(self, start: str, end: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM schedule WHERE day >= ? AND day <= ? ORDER BY day ASC, time ASC",
            (start, end),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def get_schedule_entry(self, sched_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schedule WHERE id = ?", (sched_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_schedule(self, sched_id: str, **fields) -> bool:
        allowed = {"item_id", "day", "time", "kind", "status"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return False
        cols = ", ".join(f"{k} = ?" for k in sets)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE schedule SET {cols} WHERE id = ?", (*sets.values(), sched_id))
        changed = cursor.rowcount
        conn.commit()
        conn.close()
        return changed > 0

    def delete_schedule(self, sched_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedule WHERE id = ?", (sched_id,))
        changed = cursor.rowcount
        conn.commit()
        conn.close()
        return changed > 0

    # ---- P5: thumbnail_variants helpers ----

    def insert_thumbnail_variant(self, variant: Dict) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO thumbnail_variants
                (id, content_hash, topic, kind, text_primary, text_secondary,
                 hue, image_path, ctr_pred, picked, generated_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                variant["id"], variant["content_hash"], variant.get("topic"),
                variant["kind"], variant.get("text_primary"), variant.get("text_secondary"),
                variant.get("hue"), variant.get("image_path"), variant.get("ctr_pred"),
                int(variant.get("picked", 0)), variant.get("generated_by", "stub"),
                variant["created_at"],
            ),
        )
        conn.commit()
        conn.close()

    def get_thumbnail_variants(self, content_hash: str) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM thumbnail_variants WHERE content_hash = ? ORDER BY ctr_pred DESC",
            (content_hash,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def get_thumbnail_variant(self, variant_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM thumbnail_variants WHERE id = ?", (variant_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def update_thumbnail_variant(self, variant_id: str, **fields) -> bool:
        allowed = {"text_primary", "text_secondary", "hue", "kind", "ctr_pred", "image_path", "picked"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return False
        cols = ", ".join(f"{k} = ?" for k in sets)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE thumbnail_variants SET {cols} WHERE id = ?", (*sets.values(), variant_id))
        changed = cursor.rowcount
        conn.commit()
        conn.close()
        return changed > 0

    def delete_thumbnail_variant(self, variant_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM thumbnail_variants WHERE id = ?", (variant_id,))
        changed = cursor.rowcount
        conn.commit()
        conn.close()
        return changed > 0

    def pick_thumbnail_variant(self, variant_id: str) -> bool:
        """Mark one variant picked; clear the rest for the same content_hash."""
        variant = self.get_thumbnail_variant(variant_id)
        if not variant:
            return False
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE thumbnail_variants SET picked = 0 WHERE content_hash = ?",
                       (variant["content_hash"],))
        cursor.execute("UPDATE thumbnail_variants SET picked = 1 WHERE id = ?", (variant_id,))
        conn.commit()
        conn.close()
        return True

    def remove_subscriber(self, chat_id: int) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM telegram_subscribers WHERE chat_id = ?", (chat_id,))
        conn.commit()
        conn.close()

    def get_subscribers(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM telegram_subscribers ORDER BY joined_at")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ===== Friend Votes =====

    def vote_item(self, item_url: str, chat_id: int, voter_name: str = "") -> bool:
        """Record a vote. Returns True if this is a new vote, False if already voted."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO item_votes (item_url, chat_id, voter_name) VALUES (?, ?, ?)",
                (item_url, chat_id, voter_name),
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def get_vote_count(self, item_url: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM item_votes WHERE item_url = ?", (item_url,))
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_all_votes(self) -> Dict[str, int]:
        """Return {item_url: vote_count} for all items with at least one vote."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT item_url, COUNT(*) as cnt FROM item_votes GROUP BY item_url"
        )
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}

    def create_or_update_publication(self, item_id: int, platform: str, views: int = 0,
                                     impressions: int = 0, ctr: float = 0.0,
                                     engagement_rate: float = 0.0, status: str = 'live') -> None:
        """Upsert a publication record for a saved item and platform"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO publication_analytics (item_id, platform, views, impressions, ctr, engagement_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id, platform) DO UPDATE SET
                views=excluded.views,
                impressions=excluded.impressions,
                ctr=excluded.ctr,
                engagement_rate=excluded.engagement_rate,
                status=excluded.status
        """, (item_id, platform, views, impressions, ctr, engagement_rate, status))
        conn.commit()
        conn.close()

    def get_publication_analytics(self) -> List[Dict]:
        """Get all publication analytics with details from the saved item"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, s.title, s.category, s.format, s.published_url
            FROM publication_analytics p
            JOIN saved_items s ON p.item_id = s.id
            ORDER BY p.published_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "item_id": r["item_id"],
                "platform": r["platform"],
                "published_at": r["published_at"],
                "views": r["views"],
                "impressions": r["impressions"],
                "ctr": r["ctr"],
                "engagement_rate": r["engagement_rate"],
                "status": r["status"],
                "title": r["title"],
                "category": r["category"],
                "format": r["format"],
                "published_url": r["published_url"],
            })
        return results


    def get_top_performing_categories(self, limit: int = 3) -> List[str]:
        """Get top categories based on views from published items"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.category, SUM(p.views) as total_views
            FROM publication_analytics p
            JOIN saved_items s ON p.item_id = s.id
            WHERE s.category IS NOT NULL AND s.category != ''
            GROUP BY s.category
            ORDER BY total_views DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows if r[0]]

    # ── repurposed_clips database helpers ──
    def insert_repurposed_clip(self, clip: Dict) -> str:
        import uuid
        import time
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        clip_id = clip.get("id") or f"clip-{uuid.uuid4().hex[:12]}"
        cursor.execute("""
            INSERT INTO repurposed_clips (id, parent_item_id, title, start_time, end_time, hook_text, virality_score, status, published_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clip_id,
            clip.get("parent_item_id"),
            clip.get("title", ""),
            clip.get("start_time", ""),
            clip.get("end_time", ""),
            clip.get("hook_text", ""),
            clip.get("virality_score", 0.0),
            clip.get("status", "draft"),
            clip.get("published_url", ""),
            clip.get("created_at") or time.time()
        ))
        conn.commit()
        conn.close()
        return clip_id

    def list_repurposed_clips(self, parent_item_id: int) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM repurposed_clips WHERE parent_item_id = ? ORDER BY created_at DESC", (parent_item_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_repurposed_clip(self, clip_id: str, **fields) -> bool:
        if not fields:
            return False
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        keys = []
        values = []
        for k, v in fields.items():
            keys.append(f"{k} = ?")
            values.append(v)
        values.append(clip_id)
        cursor.execute(f"UPDATE repurposed_clips SET {', '.join(keys)} WHERE id = ?", values)
        ok = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return ok

    # ── ab_tests database helpers ──
    def insert_ab_test(self, test: Dict) -> str:
        import uuid
        import time
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        test_id = test.get("id") or f"test-{uuid.uuid4().hex[:12]}"
        cursor.execute("""
            INSERT INTO ab_tests (id, item_id, status, variant_a_title, variant_a_image, variant_b_title, variant_b_image, variant_a_ctr, variant_b_ctr, variant_a_views, variant_b_views, started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_id,
            test.get("item_id"),
            test.get("status", "active"),
            test.get("variant_a_title", ""),
            test.get("variant_a_image", ""),
            test.get("variant_b_title", ""),
            test.get("variant_b_image", ""),
            test.get("variant_a_ctr", 0.0),
            test.get("variant_b_ctr", 0.0),
            test.get("variant_a_views", 0),
            test.get("variant_b_views", 0),
            test.get("started_at") or time.time()
        ))
        conn.commit()
        conn.close()
        return test_id

    def get_active_ab_test(self, item_id: int) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ab_tests WHERE item_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1", (item_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_ab_tests(self, item_id: int) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ab_tests WHERE item_id = ? ORDER BY started_at DESC", (item_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_ab_test_metrics(self, test_id: str, **fields) -> bool:
        if not fields:
            return False
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        keys = []
        values = []
        for k, v in fields.items():
            keys.append(f"{k} = ?")
            values.append(v)
        values.append(test_id)
        cursor.execute(f"UPDATE ab_tests SET {', '.join(keys)} WHERE id = ?", values)
        ok = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return ok

    def list_all_active_ab_tests(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ab_tests WHERE status = 'active'")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class IntelligenceJSON:
    """JSON-based storage for daily digests and cache"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = DATA_DIR
        self.data_dir = data_dir
        self.digests_dir = os.environ.get("DIGEST_DIR", DEFAULT_DIGEST_DIR)
        os.makedirs(self.digests_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
    
    def save_daily_digest(self, date: str, content: str) -> str:
        """Save daily digest markdown"""
        filename = f"{date}.md"
        filepath = os.path.join(self.digests_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return filepath
    
    def get_daily_digest(self, date: str) -> Optional[str]:
        """Get daily digest for a specific date"""
        filepath = os.path.join(self.digests_dir, f"{date}.md")
        
        if os.path.exists(filepath):
            with open(filepath, encoding="utf-8") as f:
                return f.read()
        return None
    
    def list_digests(self) -> List[str]:
        """List all available digests"""
        digests = []
        for filename in os.listdir(self.digests_dir):
            if filename.endswith(".md"):
                digests.append(filename.replace(".md", ""))
        return sorted(digests, reverse=True)
    
    def save_cache(self, name: str, data: Any) -> None:
        """Save cached data"""
        filepath = os.path.join(self.data_dir, f"{name}.cache.json")
        
        with open(filepath, "w") as f:
            json.dump({
                "data": data,
                "cached_at": datetime.now().isoformat()
            }, f, indent=2)
    
    def load_cache(self, name: str, max_age_seconds: int = 3600) -> Optional[Any]:
        """Load cached data if fresh enough"""
        filepath = os.path.join(self.data_dir, f"{name}.cache.json")
        
        if os.path.exists(filepath):
            with open(filepath) as f:
                cache = json.load(f)
                
            cached_at = datetime.fromisoformat(cache["cached_at"])
            age = (datetime.now() - cached_at).total_seconds()
            
            if age < max_age_seconds:
                return cache["data"]
        
        return None


# Initialize databases
def init_data_stores():
    """Initialize all data stores"""
    db = IntelligenceDB()
    json_store = IntelligenceJSON()
    return db, json_store


if __name__ == "__main__":
    # Test the database
    db, json_store = init_data_stores()
    
    # Test saving an item
    test_item = {
        "title": "Test Awesome Repo",
        "url": "https://github.com/test/repo",
        "source": "GitHub Trending",
        "source_type": "github",
        "category": "coding-agent",
        "signal_score": 85,
        "status": "to_test"
    }
    
    item_id = db.save_item(test_item)
    print(f"Saved item with ID: {item_id}")
    
    # Get saved items
    items = db.get_saved_items()
    print(f"Total saved items: {len(items)}")
