import time
from concurrent.futures import ThreadPoolExecutor

from data_models import IntelligenceDB


def test_duplicate_save_updates_existing_row(tmp_path):
    db = IntelligenceDB(db_path=str(tmp_path / "test.db"))

    item = {
        "title": "Original",
        "url": "https://example.com/duplicate",
        "source": "GitHub Trending",
        "source_type": "github",
        "status": "to_read",
        "signal_score": 70,
    }
    item_id = db.save_item(item)
    first_row = db.get_saved_items()[0]
    time.sleep(0.02)

    updated_id = db.save_item({**item, "title": "Updated", "status": "useful", "signal_score": 95})
    rows = db.get_saved_items()

    assert updated_id == item_id
    assert len(rows) == 1
    assert rows[0]["title"] == "Updated"
    assert rows[0]["status"] == "useful"
    assert rows[0]["updated_at"] != first_row["updated_at"]


def test_saved_item_update_delete_ignore_and_track_lifecycle(tmp_path):
    db = IntelligenceDB(db_path=str(tmp_path / "test.db"))
    item_id = db.save_item({
        "title": "Trackable Repo",
        "url": "https://example.com/repo",
        "source": "GitHub Trending",
        "source_type": "github",
        "status": "to_read",
        "signal_score": 88,
    })

    assert db.update_status(item_id, "testing") is True
    assert db.update_notes(item_id, "needs benchmarking", ["agent", "pi"]) is True

    item = db.get_saved_items()[0]
    assert item["status"] == "testing"
    assert item["notes"] == "needs benchmarking"
    assert item["tags"] == ["agent", "pi"]

    db.ignore_item("https://example.com/ignore", "Ignore", "blogs")
    assert db.is_ignored("https://example.com/ignore") is True
    assert len(db.get_ignored_items()) == 1

    topic_id = db.add_tracked_topic("agents", "watch this")
    assert any(topic["topic"] == "agents" for topic in db.get_tracked_topics())
    assert db.remove_tracked_topic(topic_id) is True
    assert not any(topic["topic"] == "agents" for topic in db.get_tracked_topics())

    assert db.delete_item(item_id) is True
    assert db.get_saved_items() == []


def test_concurrent_duplicate_saves_are_atomic(tmp_path):
    db = IntelligenceDB(db_path=str(tmp_path / "test.db"))
    item = {
        "title": "Concurrent story",
        "url": "https://example.com/concurrent",
        "source": "Research desk",
        "source_type": "article",
        "status": "idea",
        "signal_score": 80,
    }
    with ThreadPoolExecutor(max_workers=8) as executor:
        ids = list(executor.map(lambda _: db.save_item(item), range(16)))

    assert len(set(ids)) == 1
    assert len(db.get_saved_items()) == 1


def test_publication_metrics_keep_samples_and_delete_cleanly(tmp_path):
    from data_models import IntelligenceDB

    db = IntelligenceDB(str(tmp_path / "analytics.db"))
    item_id = db.save_item({
        "title": "Published video",
        "url": "dailydex://published-video",
        "status": "published",
        "published_url": "https://youtube.com/watch?v=1234567890a",
    })
    db.create_or_update_publication(item_id, "youtube", video_id="1234567890a")
    publication = db.get_publication_for_item(item_id)
    db.record_publication_metrics(publication["id"], {
        "views": 100,
        "impressions": 2000,
        "ctr": 0.05,
        "source": "test",
        "synced_at": "2026-07-21T00:00:00+00:00",
    })
    db.record_publication_metrics(publication["id"], {
        "views": 250,
        "source": "test",
        "synced_at": "2026-07-22T00:00:00+00:00",
    })

    current = db.get_publication_for_item(item_id)
    assert current["views"] == 250
    assert current["impressions"] == 2000
    samples = db.get_publication_samples(publication["id"])
    assert [sample["views"] for sample in samples] == [100, 250]

    db.delete_item(item_id)
    assert db.get_publication_samples(publication["id"]) == []


def test_existing_publication_schema_is_migrated(tmp_path):
    import sqlite3

    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE publication_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            published_at TEXT DEFAULT CURRENT_TIMESTAMP,
            views INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            ctr REAL DEFAULT 0.0,
            engagement_rate REAL DEFAULT 0.0,
            status TEXT DEFAULT 'live'
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX idx_publication_analytics_item_platform "
        "ON publication_analytics(item_id, platform)"
    )
    conn.commit()
    conn.close()

    IntelligenceDB(str(path))
    conn = sqlite3.connect(path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(publication_analytics)")}
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"video_id", "last_synced_at", "sync_error", "rescue_status"} <= columns
    assert "publication_analytics_samples" in tables
