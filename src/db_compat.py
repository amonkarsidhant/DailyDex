"""
db_compat.py — Transparent SQLite ↔ PostgreSQL adapter for DailyDex.

When DATABASE_URL is set in the environment, all connections go to Postgres
via psycopg2 and SQLite-specific SQL is translated on the fly.
When DATABASE_URL is absent, this module is a thin pass-through to stdlib
sqlite3 — zero performance impact for local dev.

Translations performed for Postgres mode:
  - ?  →  %s  (placeholder style)
  - INTEGER PRIMARY KEY AUTOINCREMENT  →  SERIAL PRIMARY KEY
  - REAL  →  DOUBLE PRECISION
  - INSERT OR REPLACE INTO  →  INSERT INTO … ON CONFLICT DO NOTHING
  - INSERT OR IGNORE  INTO  →  INSERT INTO … ON CONFLICT DO NOTHING
  - PRAGMA journal_mode=WAL  →  (silently skipped)
  - PRAGMA table_info(tbl)   →  information_schema.columns query
  - TEXT DEFAULT CURRENT_TIMESTAMP  →  TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')
  - conn.row_factory = sqlite3.Row  →  RealDictCursor (automatic)
"""

import os
import re
import sqlite3 as _sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# ─────────────────────────────────────────────────────────────────────────────
# SQLite path — just expose stdlib sqlite3 unchanged
# ─────────────────────────────────────────────────────────────────────────────

if not DATABASE_URL:
    connect = _sqlite3.connect
    Row = _sqlite3.Row

# ─────────────────────────────────────────────────────────────────────────────
# Postgres path
# ─────────────────────────────────────────────────────────────────────────────
else:
    import psycopg2
    import psycopg2.extras

    # ── SQL Translation ───────────────────────────────────────────────────────

    _PH         = re.compile(r'\?')
    _AUTOINCR   = re.compile(r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', re.I)
    _REAL_COL   = re.compile(r'\bREAL\b')
    _TEXT_TS    = re.compile(r'\bTEXT\s+DEFAULT\s+CURRENT_TIMESTAMP\b', re.I)
    _INS_REPL   = re.compile(r'\bINSERT\s+OR\s+REPLACE\s+INTO\b', re.I)
    _INS_IGN    = re.compile(r'\bINSERT\s+OR\s+IGNORE\s+INTO\b', re.I)
    _INS_PLAIN  = re.compile(r'\bINSERT\s+INTO\b', re.I)
    _PRAGMA     = re.compile(r'^\s*PRAGMA\b', re.I)
    _PRAGMA_TI  = re.compile(r'PRAGMA\s+table_info\s*\(\s*(\w+)\s*\)', re.I)

    def _to_pg(sql: str) -> str:
        sql = _PH.sub('%s', sql)
        sql = _AUTOINCR.sub('SERIAL PRIMARY KEY', sql)
        sql = _REAL_COL.sub('DOUBLE PRECISION', sql)
        sql = _TEXT_TS.sub("TEXT DEFAULT to_char(now(),'YYYY-MM-DD HH24:MI:SS')", sql)
        # INSERT OR REPLACE / INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
        if _INS_REPL.search(sql):
            sql = _INS_REPL.sub('INSERT INTO', sql)
            sql = sql.rstrip('; \n\t\r') + ' ON CONFLICT DO NOTHING'
        elif _INS_IGN.search(sql):
            sql = _INS_IGN.sub('INSERT INTO', sql)
            sql = sql.rstrip('; \n\t\r') + ' ON CONFLICT DO NOTHING'
        return sql

    # ── Row compat ────────────────────────────────────────────────────────────

    class Row(dict):
        """
        Behaves like sqlite3.Row:
          - dict-style access:  row['col']
          - index access:       row[0]   (by column position)
          - .keys()
        psycopg2's RealDictRow already provides dict access; we just add [int].
        """
        def __getitem__(self, key):
            if isinstance(key, int):
                return list(self.values())[key]
            return super().__getitem__(key)

        def keys(self):
            return list(super().keys())

    # ── Cursor ────────────────────────────────────────────────────────────────

    class _Cursor:
        def __init__(self, pg_cur, row_factory=None):
            self._c       = pg_cur
            self._rf      = row_factory
            self.lastrowid = None
            self.rowcount  = 0
            self._pragma_rows = None  # for PRAGMA emulation

        # ── Internal ──────────────────────────────────────────────────────────

        def _wrap_row(self, raw):
            if raw is None:
                return None
            if self._rf:
                return self._rf(self._c, raw)
            return Row(raw) if isinstance(raw, dict) else raw

        def _exec_pg(self, sql: str, params=None):
            """Execute translated SQL; handle lastrowid for INSERTs."""
            adapted = _to_pg(sql)
            is_insert = bool(re.match(r'\s*INSERT\b', adapted, re.I))
            if is_insert and 'RETURNING' not in adapted.upper():
                try:
                    self._c.execute(adapted + ' RETURNING id', params or ())
                    row = self._c.fetchone()
                    self.lastrowid = row['id'] if row and 'id' in row else (
                        list(row.values())[0] if row else None)
                except Exception:
                    # RETURNING id might fail if table has no 'id' column (composite PK)
                    try:
                        self._c.execute(adapted, params or ())
                        self.lastrowid = None
                    except Exception:
                        raise
            else:
                self._c.execute(adapted, params or ())
                self.lastrowid = None
            self.rowcount = self._c.rowcount

        # ── PRAGMA emulation ─────────────────────────────────────────────────

        def _handle_pragma(self, sql: str) -> bool:
            """
            Returns True if sql was a PRAGMA and was handled internally.
            Sets self._pragma_rows for fetchall/fetchone.
            """
            if not _PRAGMA.match(sql):
                return False
            m = _PRAGMA_TI.search(sql)
            if m:
                table = m.group(1)
                self._c.execute("""
                    SELECT
                        ordinal_position - 1 AS cid,
                        column_name          AS name,
                        data_type            AS type,
                        0                    AS notnull,
                        NULL                 AS dflt_value,
                        0                    AS pk
                    FROM information_schema.columns
                    WHERE table_name = %s
                      AND table_schema = 'public'
                    ORDER BY ordinal_position
                """, (table,))
                # rows come from RealDictCursor — wrap them
                self._pragma_rows = [Row(r) for r in self._c.fetchall()]
            else:
                # Other PRAGMAs (journal_mode etc.) — silently no-op
                self._pragma_rows = []
            return True

        # ── Public API ────────────────────────────────────────────────────────

        def execute(self, sql, params=None):
            self._pragma_rows = None
            if self._handle_pragma(sql):
                return self
            self._exec_pg(sql, params)
            return self

        def executemany(self, sql, seq):
            adapted = _to_pg(sql)
            self._c.executemany(adapted, seq)
            self.rowcount = self._c.rowcount

        def fetchone(self):
            if self._pragma_rows is not None:
                return self._pragma_rows.pop(0) if self._pragma_rows else None
            raw = self._c.fetchone()
            return self._wrap_row(raw)

        def fetchall(self):
            if self._pragma_rows is not None:
                rows, self._pragma_rows = self._pragma_rows, None
                return rows
            return [self._wrap_row(r) for r in self._c.fetchall()]

        def __iter__(self):
            if self._pragma_rows is not None:
                rows, self._pragma_rows = self._pragma_rows, None
                return iter(rows)
            return (self._wrap_row(r) for r in self._c.fetchall())

    # ── Connection ────────────────────────────────────────────────────────────

    class _Connection:
        def __init__(self, dsn: str):
            self._conn = psycopg2.connect(
                dsn,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            # Postgres default is autocommit=False; keep it that way.
            self.row_factory = None   # set by callers, mimics sqlite3.Connection

        def cursor(self):
            return _Cursor(self._conn.cursor(), row_factory=self.row_factory)

        def execute(self, sql, params=None):
            c = self.cursor()
            c.execute(sql, params)
            return c

        def executemany(self, sql, seq):
            c = self.cursor()
            c.executemany(sql, seq)

        def commit(self):
            self._conn.commit()

        def close(self):
            try:
                self._conn.commit()
                self._conn.close()
            except Exception:
                pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc_type:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
            else:
                try:
                    self._conn.commit()
                except Exception:
                    pass
            self.close()

    # ── Public connect() ─────────────────────────────────────────────────────

    def connect(path_or_dsn=None, **kwargs):  # noqa: F811
        """
        Drop-in replacement for sqlite3.connect().
        Ignores path_or_dsn (and all sqlite3 kwargs) and routes to DATABASE_URL.
        """
        return _Connection(DATABASE_URL)

    # ── Expose Row so callers can do:  conn.row_factory = sqlite3.Row ────────
    # (Row is defined above in the postgres branch)
