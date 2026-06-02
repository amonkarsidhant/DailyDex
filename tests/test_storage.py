import time

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
