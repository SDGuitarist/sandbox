import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = "dashboard.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def get_db(path=None, immediate=False):
    db_path = path or DB_PATH
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path=None):
    """Initialize schema using raw connection.

    Must NOT use get_db — executescript() issues an implicit COMMIT that
    bypasses context-manager transaction semantics.
    """
    db_path = path or DB_PATH
    schema = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        # WAL before executescript — executescript issues an implicit COMMIT,
        # so WAL must be set first.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(schema)
    finally:
        conn.close()
