"""
Database connection management for the task scheduler.

Every connection enables WAL journal mode and a busy timeout so concurrent
writes from the scheduler process and Flask workers don't immediately fail
with SQLITE_BUSY — they retry for up to 5 seconds instead.
"""
import sqlite3
import os

DB_PATH = os.environ.get("SCHEDULER_DB", os.path.join(os.path.dirname(__file__), "scheduler.db"))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the scheduler database.

    Sets:
      - WAL journal mode: concurrent readers don't block writers
      - busy_timeout 5000ms: retry on SQLITE_BUSY instead of raising immediately
      - row_factory: rows accessible as dicts
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Enable WAL mode — survives reconnects once set on the file, but safe to
    # call every time (it's a no-op if already set).
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")

    return conn


def init_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    with get_connection() as conn:
        with open(SCHEMA_PATH) as f:
            conn.executescript(f.read())
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
