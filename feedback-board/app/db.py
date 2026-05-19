import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import current_app


@contextmanager
def get_db(immediate=False):
    """Context manager for DB connections. Auto-commits on success, rollbacks on error.
    Use immediate=True for write operations (BEGIN IMMEDIATE).
    """
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(app):
    """Initialize database from schema.sql. Called once at startup.
    Sets WAL mode (persistent -- only needs to run once)."""
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    db_path = app.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
