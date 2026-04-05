"""
Database connection management for the URL health monitor.

Every connection enables WAL journal mode and a busy timeout so concurrent
writes from scheduler, workers, and Flask don't immediately fail with
SQLITE_BUSY — they retry for up to 5 seconds instead.
"""
import sqlite3
import os

DB_PATH = os.environ.get(
    "HEALTH_MONITOR_DB",
    os.path.join(os.path.dirname(__file__), "health_monitor.db"),
)
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    try:
        with open(SCHEMA_PATH) as f:
            schema = f.read()
    except FileNotFoundError:
        raise RuntimeError(f"Schema file not found: {SCHEMA_PATH}")

    conn = get_connection()
    try:
        conn.executescript(schema)
    finally:
        conn.close()

    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
