from contextlib import contextmanager
from pathlib import Path
import re
import shutil
import sqlite3
from datetime import datetime

# Canonical DB path: same directory as this file
DB_PATH = Path(__file__).parent / "leads.db"


@contextmanager
def get_db(db_path=DB_PATH):
    """Context manager for SQLite connections. Works from CLI and Flask."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_SAFE_IDENTIFIER = re.compile(r"^[a-z_]+$")


def migrate_db(db_path=DB_PATH):
    """Add new columns to existing leads table. Idempotent and safe to re-run."""
    if not db_path.exists():
        return  # No DB to migrate; init_db will create fresh schema

    new_columns = [
        ("phone", "TEXT"),
        ("website", "TEXT"),
        ("enriched_at", "TEXT"),
        ("social_handles", "TEXT"),
        ("profile_bio", "TEXT"),
        ("ig_profile_enriched_at", "TEXT"),
    ]
    with get_db(db_path) as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
        to_add = [(n, t) for n, t in new_columns if n not in existing]
        if not to_add:
            return  # Schema is up to date, no backup needed

        # Backup only when we actually need to alter the schema
        backup = db_path.with_suffix(
            f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
        )
        shutil.copy2(db_path, backup)

        for col_name, col_type in to_add:
            if not _SAFE_IDENTIFIER.match(col_name):
                raise ValueError(f"Unsafe column name: {col_name!r}")
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")


def init_db(db_path=DB_PATH):
    """Create tables from schema.sql if they don't exist. Safe to call repeatedly."""
    schema_path = Path(__file__).parent / "schema.sql"
    with get_db(db_path) as conn:
        conn.executescript(schema_path.read_text())
    migrate_db(db_path)  # Ensure existing DBs get new columns
