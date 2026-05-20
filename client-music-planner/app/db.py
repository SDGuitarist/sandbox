import sqlite3
from contextlib import contextmanager
from flask import current_app, g


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


def get_request_db():
    """Return a request-scoped read-only connection stored on g.
    Used by decorators to avoid opening a second connection when the route
    will open its own. Closed in teardown_appcontext."""
    if '_db' not in g:
        g._db = sqlite3.connect(
            current_app.config['DATABASE'],
            timeout=5.0,
        )
        g._db.row_factory = sqlite3.Row
        g._db.execute("PRAGMA foreign_keys = ON")
        g._db.execute("PRAGMA synchronous = NORMAL")
    return g._db


def close_request_db(exc=None):
    """Close the request-scoped connection if it was opened."""
    db = g.pop('_db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables from schema.sql. Called once at app startup."""
    conn = sqlite3.connect(current_app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    with current_app.open_resource('schema.sql') as f:
        conn.executescript(f.read().decode('utf-8'))
    conn.close()


def init_app(app):
    app.teardown_appcontext(close_request_db)
    with app.app_context():
        _init_db_pragmas()
        init_db()
