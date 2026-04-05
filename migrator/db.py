import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = "migrator.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class MigrationLockError(Exception):
    """Raised when the migrations lock is already held."""


class ChecksumMismatchError(Exception):
    """Raised when an applied migration file has been modified on disk."""


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()


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
    """Initialize DB schema.

    Uses raw connection + executescript (NOT get_db) because executescript()
    issues an implicit COMMIT before running, which would bypass get_db's
    transaction semantics.
    """
    db_path = path or DB_PATH
    schema = SCHEMA_PATH.read_text()
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        # WAL must be set before executescript — executescript issues an
        # implicit COMMIT; setting WAL first ensures it takes effect.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(schema)
    finally:
        conn.close()


def acquire_lock(conn, locked_by: str):
    """Acquire the migrations lock inside the caller's BEGIN IMMEDIATE transaction.

    Raises MigrationLockError if already locked.
    """
    existing = conn.execute("SELECT locked_by, locked_at FROM migrations_lock WHERE id = 1").fetchone()
    if existing:
        raise MigrationLockError(
            f"Migrations lock held by '{existing['locked_by']}' since {existing['locked_at']}"
        )
    conn.execute(
        "INSERT INTO migrations_lock (id, locked_at, locked_by) VALUES (1, ?, ?)",
        (_now(), locked_by),
    )


def release_lock(conn):
    """Release the migrations lock."""
    conn.execute("DELETE FROM migrations_lock WHERE id = 1")


def get_applied(conn) -> list[dict]:
    """Return list of applied migrations ordered by version."""
    rows = conn.execute(
        "SELECT version, name, applied_at, checksum FROM schema_migrations ORDER BY version ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def mark_applied(conn, version: str, name: str, up_sql: str):
    """Record a migration as applied."""
    conn.execute(
        "INSERT INTO schema_migrations (version, name, applied_at, checksum) VALUES (?, ?, ?, ?)",
        (version, name, _now(), checksum(up_sql)),
    )


def mark_rolled_back(conn, version: str):
    """Remove a migration's applied record."""
    conn.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))
