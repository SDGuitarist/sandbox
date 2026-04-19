"""Tests for schema migration idempotence and data preservation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db, init_db, migrate_db


def _temp_db(tmp_path):
    return tmp_path / "test.db"


def test_migrate_adds_new_columns(tmp_path):
    db = _temp_db(tmp_path)
    init_db(db)
    with get_db(db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
    assert "social_handles" in cols
    assert "profile_bio" in cols
    assert "ig_profile_enriched_at" in cols


def test_migrate_idempotent(tmp_path):
    db = _temp_db(tmp_path)
    init_db(db)
    migrate_db(db)  # second run
    migrate_db(db)  # third run -- no error


def test_migrate_preserves_data(tmp_path):
    db = _temp_db(tmp_path)
    init_db(db)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO leads (name, profile_url, source) VALUES (?, ?, ?)",
            ("Test Lead", "https://example.com/test", "eventbrite"),
        )
    migrate_db(db)
    with get_db(db) as conn:
        row = conn.execute("SELECT name FROM leads WHERE name = 'Test Lead'").fetchone()
    assert row is not None
    assert row["name"] == "Test Lead"


def test_fresh_db_then_migrate(tmp_path):
    db = _temp_db(tmp_path)
    init_db(db)  # creates from schema.sql
    migrate_db(db)  # should not error
