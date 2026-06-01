import sqlite3
import os
from contextlib import contextmanager
from flask import g, current_app

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts.db')

@contextmanager
def get_db():
    """Context manager for database connections.
    Usage:
        with get_db() as conn:
            rows = conn.execute('SELECT ...').fetchall()
    """
    if 'db' not in g:
        # isolation_level left as default ("") — DO NOT use isolation_level=None,
        # which makes conn.commit() a no-op (3-build recurrence: runs 054, 056, 057)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # WAL mode persists on the DB file — set only in init_db(), not per-connection
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=5000')
        g.db = conn
    try:
        yield g.db
    finally:
        pass  # Connection closed in teardown

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database schema.
    Uses raw sqlite3.connect(), NOT get_db() — executescript() issues
    implicit COMMIT that breaks context manager contract (brainstorm refinement #1).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    result = conn.execute('PRAGMA journal_mode').fetchone()
    assert result[0] == 'wal', f'WAL mode failed: got {result[0]}'
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
