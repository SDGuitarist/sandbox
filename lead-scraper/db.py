from contextlib import contextmanager
from pathlib import Path
import sqlite3

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


def init_db(db_path=DB_PATH):
    """Create tables from schema.sql if they don't exist. Safe to call repeatedly."""
    schema_path = Path(__file__).parent / "schema.sql"
    with get_db(db_path) as conn:
        conn.executescript(schema_path.read_text())
