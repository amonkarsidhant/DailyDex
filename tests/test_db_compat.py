import importlib
import os
import sys
import sqlite3
from unittest.mock import MagicMock, patch
import pytest

@pytest.fixture(autouse=True)
def reset_db_compat():
    # Store original state
    has_psycopg2 = "psycopg2" in sys.modules
    old_psycopg2 = sys.modules.get("psycopg2")
    has_extras = "psycopg2.extras" in sys.modules
    old_extras = sys.modules.get("psycopg2.extras")
    
    yield
    
    # Teardown: Remove mocks
    if not has_psycopg2 and "psycopg2" in sys.modules:
        del sys.modules["psycopg2"]
    elif has_psycopg2:
        sys.modules["psycopg2"] = old_psycopg2
        
    if not has_extras and "psycopg2.extras" in sys.modules:
        del sys.modules["psycopg2.extras"]
    elif has_extras:
        sys.modules["psycopg2.extras"] = old_extras
        
    # Force reload back to sqlite mode
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]
    
    import db_compat
    importlib.reload(db_compat)

def test_sqlite_branch(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    
    import db_compat
    importlib.reload(db_compat)
    
    assert db_compat.connect == sqlite3.connect
    assert db_compat.Row == sqlite3.Row

def test_postgres_branch_sql_translation(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://mock_db")
    
    mock_psycopg2 = MagicMock()
    mock_extras = MagicMock()
    sys.modules["psycopg2"] = mock_psycopg2
    sys.modules["psycopg2.extras"] = mock_extras
    
    import db_compat
    importlib.reload(db_compat)
    
    assert db_compat.connect.__name__ == "connect"
    
    # Test translations
    sql = "SELECT * FROM users WHERE id = ?"
    assert db_compat._to_pg(sql) == "SELECT * FROM users WHERE id = %s"
    
    sql = "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
    assert db_compat._to_pg(sql) == "CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT)"
    
    sql = "CREATE TABLE users (score REAL)"
    assert db_compat._to_pg(sql) == "CREATE TABLE users (score DOUBLE PRECISION)"
    
    sql = "CREATE TABLE users (created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    assert db_compat._to_pg(sql) == "CREATE TABLE users (created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS'))"
    
    sql = "INSERT OR REPLACE INTO users (id) VALUES (?)"
    assert db_compat._to_pg(sql) == "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING"
    
    sql = "INSERT OR IGNORE INTO users (id) VALUES (?)"
    assert db_compat._to_pg(sql) == "INSERT INTO users (id) VALUES (%s) ON CONFLICT DO NOTHING"

def test_postgres_connection_and_cursor(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://mock_db")
    mock_psycopg2 = MagicMock()
    sys.modules["psycopg2"] = mock_psycopg2
    sys.modules["psycopg2.extras"] = MagicMock()
    
    import db_compat
    importlib.reload(db_compat)
    
    conn = db_compat.connect("ignored.db")
    mock_psycopg2.connect.assert_called_once()
    
    mock_cursor = MagicMock()
    mock_psycopg2.connect().cursor.return_value = mock_cursor
    
    cur = conn.cursor()
    
    # Test execute
    cur.execute("SELECT * FROM test WHERE id = ?", (1,))
    mock_cursor.execute.assert_called_with("SELECT * FROM test WHERE id = %s", (1,))
    
    # Test executemany
    cur.executemany("INSERT INTO test (id) VALUES (?)", [(1,), (2,)])
    mock_cursor.executemany.assert_called_with("INSERT INTO test (id) VALUES (%s)", [(1,), (2,)])
    
    # Test PRAGMA table_info
    mock_cursor.fetchall.return_value = [{"cid": 0, "name": "id"}]
    cur.execute("PRAGMA table_info(test)")
    assert cur.fetchone()["name"] == "id"
    
    # Test commit / close
    conn.commit()
    mock_psycopg2.connect().commit.assert_called()
    conn.close()
    mock_psycopg2.connect().close.assert_called()

def test_postgres_row_dict_access(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://mock_db")
    sys.modules["psycopg2"] = MagicMock()
    sys.modules["psycopg2.extras"] = MagicMock()
    
    import db_compat
    importlib.reload(db_compat)
    
    # psycopg2 RealDictRow acts like a dict, we wrap it in db_compat.Row
    row = db_compat.Row({"id": 1, "name": "foo"})
    
    assert row["id"] == 1
    assert row["name"] == "foo"
    assert row[0] == 1
    assert row[1] == "foo"
    assert list(row.keys()) == ["id", "name"]
