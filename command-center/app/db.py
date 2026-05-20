import sqlite3
from contextlib import contextmanager
from flask import g, current_app

DATABASE = None  # Set by init_app


def init_app(app):
    global DATABASE
    DATABASE = app.config['DATABASE']
    app.teardown_appcontext(close_db)


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_raw_connection():
    """Get a raw sqlite3 connection. Caller manages lifecycle."""
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def get_db(immediate=False):
    """Context manager for database access. Always use with `with` syntax.

    Usage:
        with get_db() as db:
            rows = db.execute("SELECT * FROM contact").fetchall()

        with get_db(immediate=True) as db:
            db.execute("INSERT INTO contact ...")
            db.execute("INSERT INTO activity_log ...")
            # Auto-commits on exit, rolls back on exception
    """
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        if immediate:
            conn.commit()
    except Exception:
        if immediate:
            conn.rollback()
        raise
    finally:
        conn.close()


def init_db(app):
    """Initialize database schema. Call once at startup."""
    conn = None
    try:
        conn = sqlite3.connect(app.config['DATABASE'], timeout=10)
        result = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        assert result[0] == 'wal', f"WAL mode failed: {result[0]}"
        with open(app.config['SCHEMA_PATH']) as f:
            conn.executescript(f.read())
    finally:
        if conn:
            conn.close()
