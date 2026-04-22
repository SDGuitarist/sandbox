"""Shared test helpers -- database setup and lead insertion."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db, init_db


@pytest.fixture
def setup_db(tmp_path):
    """Create a fresh test database. Returns the db path."""
    db = tmp_path / "test.db"
    init_db(db)
    return db


def _insert_lead(db, name="Test", **kwargs):
    """Insert a lead with any combination of columns.

    Always sets name, profile_url, and source. All other columns are optional
    keyword arguments that map directly to leads table columns.
    """
    kwargs.setdefault("profile_url", f"https://example.com/{name.lower()}")
    kwargs.setdefault("source", "test")

    columns = ["name"] + list(kwargs.keys())
    placeholders = ", ".join("?" for _ in columns)
    col_names = ", ".join(columns)
    values = [name] + list(kwargs.values())

    with get_db(db) as conn:
        conn.execute(
            f"INSERT INTO leads ({col_names}) VALUES ({placeholders})",
            values,
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


@pytest.fixture
def insert_lead():
    """Fixture that provides the _insert_lead helper function."""
    return _insert_lead
