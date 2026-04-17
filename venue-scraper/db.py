"""SQLite connection lifecycle for venue storage.

Reuses the lead-scraper contextmanager pattern with added type hints.
WAL mode and busy_timeout set on every connection, not just at schema init.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "venue_scraper.db"


@contextmanager
def get_db(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables from schema.sql. Safe to call repeatedly."""
    schema = (Path(__file__).parent / "schema.sql").read_text()
    with get_db(db_path) as conn:
        conn.executescript(schema)
