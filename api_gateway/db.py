"""
Database connection management for the API gateway.
"""
import contextlib
import os
import re
import sqlite3
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("GATEWAY_DB", os.path.join(BASE_DIR, "gateway.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

# Shared constants used by both route modules
PROXY_TIMEOUT = 10  # seconds — caps slow-loris risk on gateway worker thread

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)


@contextlib.contextmanager
def get_connection():
    """
    Context manager that opens a WAL-mode SQLite connection and always closes it.
    sqlite3.Connection.__exit__ only handles transactions — it does NOT close.
    We wrap it here so callers get proper cleanup via 'with get_connection() as conn'.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    result = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    if result and result[0] != "wal":
        import warnings
        warnings.warn(f"WAL mode not active — got: {result[0]}", RuntimeWarning)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Create tables. Safe to call multiple times."""
    try:
        with open(SCHEMA_PATH) as f:
            schema = f.read()
    except FileNotFoundError:
        raise RuntimeError(f"Schema file not found: {SCHEMA_PATH}")
    with get_connection() as conn:
        conn.executescript(schema)
    print(f"Database initialized at {DB_PATH}")


def generate_id() -> str:
    """Generate a UUID4 for use as a primary key."""
    return str(uuid.uuid4())


def is_valid_id(value: str) -> bool:
    """Return True if value is a valid UUID4."""
    return bool(_UUID_RE.match(value.lower())) if isinstance(value, str) else False


if __name__ == "__main__":
    init_db()
