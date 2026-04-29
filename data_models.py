#!/usr/bin/env python3
"""Data models for DailyDex - SQLite + JSON storage"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
        
        conn.commit()
        conn.close()

    def _serialize_value(self, key: str, value):
        """Serialize structured values for SQLite storage."""
        if key in {"tags", "sources", "outline"}:
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
                    item.get("thumbnail_text"),
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
            item.get("thumbnail_text"),
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
            item = dict(row)
            if item.get("tags"):
                item["tags"] = json.loads(item["tags"])
            else:
                item["tags"] = []
            if item.get("sources"):
                try:
                    item["sources"] = json.loads(item["sources"])
                except Exception:
                    item["sources"] = [item["sources"]]
            else:
                item["sources"] = []
            if item.get("outline"):
                try:
                    item["outline"] = json.loads(item["outline"])
                except Exception:
                    item["outline"] = [item["outline"]]
            else:
                item["outline"] = []
            items.append(item)
        
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
