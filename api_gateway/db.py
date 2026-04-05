"""
Database connection management for the API gateway.
"""
import os
import re
import sqlite3
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("GATEWAY_DB", os.path.join(BASE_DIR, "gateway.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables. Safe to call multiple times."""
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


def generate_id() -> str:
    """Generate a UUID4 for use as a primary key."""
    return str(uuid.uuid4())


def is_valid_id(value: str) -> bool:
    """Return True if value is a valid UUID4."""
    return bool(_UUID_RE.match(value.lower())) if isinstance(value, str) else False


if __name__ == "__main__":
    init_db()
