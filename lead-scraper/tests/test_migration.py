"""Tests for schema migration idempotence and data preservation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db, init_db, migrate_db


def test_migrate_adds_new_columns(setup_db):
    with get_db(setup_db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
    assert "social_handles" in cols
    assert "profile_bio" in cols
    assert "ig_profile_enriched_at" in cols


def test_migrate_idempotent(setup_db):
    migrate_db(setup_db)  # second run
    migrate_db(setup_db)  # third run -- no error


def test_migrate_preserves_data(setup_db):
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO leads (name, profile_url, source) VALUES (?, ?, ?)",
            ("Test Lead", "https://example.com/test", "eventbrite"),
        )
    migrate_db(setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute("SELECT name FROM leads WHERE name = 'Test Lead'").fetchone()
    assert row is not None
    assert row["name"] == "Test Lead"


def test_fresh_db_then_migrate(setup_db):
    migrate_db(setup_db)  # should not error


def test_migrate_adds_segment_columns(setup_db):
    with get_db(setup_db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
    assert "segment" in cols
    assert "segment_confidence" in cols


def test_migrate_adds_hook_columns(setup_db):
    with get_db(setup_db) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
    assert "hook_text" in cols
    assert "hook_source_url" in cols
    assert "hook_quality" in cols


def test_campaign_tables_created(setup_db):
    with get_db(setup_db) as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert "campaigns" in tables
    assert "campaign_leads" in tables
    assert "outreach_queue" in tables


def test_campaign_tables_idempotent(setup_db):
    init_db(setup_db)  # second call -- no error


def test_backup_uses_sqlite_api(tmp_path):
    """Verify migrate_db creates a valid backup when schema changes are needed."""
    db = tmp_path / "test.db"
    # Create a DB with only the base schema (no migration columns)
    import sqlite3
    conn = sqlite3.connect(str(db))
    conn.execute("""CREATE TABLE leads (
        id INTEGER PRIMARY KEY, name TEXT NOT NULL,
        profile_url TEXT NOT NULL, source TEXT NOT NULL,
        UNIQUE(source, profile_url)
    )""")
    conn.execute("INSERT INTO leads (name, profile_url, source) VALUES ('A', 'https://a.com', 'test')")
    conn.commit()
    conn.close()
    # migrate_db will detect missing columns and create a backup
    migrate_db(db)
    backups = list(tmp_path.glob("test.backup-*.db"))
    assert len(backups) == 1
    # Verify backup is readable and has the original data
    bconn = sqlite3.connect(str(backups[0]))
    row = bconn.execute("SELECT name FROM leads").fetchone()
    bconn.close()
    assert row[0] == "A"
