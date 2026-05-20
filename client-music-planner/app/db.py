import sqlite3
from contextlib import contextmanager
from flask import current_app


def _init_db_pragmas():
    """Set persistent PRAGMAs once at startup. WAL mode survives reconnection."""
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()


@contextmanager
def get_db(immediate=False):
    """Yields a database connection scoped to a single operation.

    Args:
        immediate: If True, starts a write transaction with BEGIN IMMEDIATE.
                   Use for any INSERT/UPDATE/DELETE. Reads leave this False.
    """
    conn = sqlite3.connect(
        current_app.config['DATABASE'],
        timeout=5.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables from schema.sql. Called once at app startup."""
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    with current_app.open_resource('schema.sql') as f:
        conn.executescript(f.read().decode('utf-8'))
    conn.close()


def init_app(app):
    with app.app_context():
        _init_db_pragmas()
        init_db()
