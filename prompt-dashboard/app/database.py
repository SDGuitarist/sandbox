import os
import sqlite3
from flask import g, current_app


def _connect(db_path):
    """Open a connection with correct PRAGMAs."""
    conn = sqlite3.connect(db_path, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA synchronous=NORMAL')
    result = conn.execute('PRAGMA journal_mode=WAL').fetchone()
    assert result[0] == 'wal', f'WAL mode failed: got {result[0]}'
    return conn


def get_db():
    """Get per-request database connection. NOT a context manager."""
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE', 'prompting.db')
        g.db = _connect(db_path)
    return g.db


def close_db(e=None):
    """Teardown: close per-request connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Initialize database schema. Uses raw sqlite3.connect(), NOT get_db().
    executescript() issues implicit COMMIT that would break context manager."""
    db_path = app.config.get('DATABASE', 'prompting.db')
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.close()
