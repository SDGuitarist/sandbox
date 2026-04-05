"""
Database connection management for the file upload service.
"""
import os
import re
import sqlite3
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("UPLOAD_DB", os.path.join(BASE_DIR, "uploads.db"))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "upload_dir"))

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
    """Create tables and upload directory. Safe to call multiple times."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
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
    print(f"Upload directory: {UPLOAD_DIR}")


def generate_file_id() -> str:
    """Generate a v4 UUID for use as a file ID."""
    return str(uuid.uuid4())


def is_valid_file_id(file_id: str) -> bool:
    """Validate that file_id is a proper UUID4 — prevents path traversal."""
    return bool(_UUID_RE.match(file_id.lower())) if isinstance(file_id, str) else False


def get_file_upload_dir(file_id: str) -> str:
    """
    Return the filesystem path for a file's upload directory.
    Raises ValueError if file_id is not a valid UUID (path traversal guard).
    """
    if not is_valid_file_id(file_id):
        raise ValueError(f"Invalid file_id: {file_id!r}")
    return os.path.join(UPLOAD_DIR, file_id)


if __name__ == "__main__":
    init_db()
