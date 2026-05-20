"""Tests for db.py -- connection, migration, backup, safety guards."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import (
    backup_db,
    ensure_outreach_status,
    get_db,
    init_db,
    upsert_venue,
)


SAMPLE_VENUE = {
    "name": "Studio A",
    "source_url": "https://studioa.com",
    "email": "info@studioa.com",
    "phone": "555-1234",
    "address": "123 Main St",
    "website": "https://studioa.com",
    "description": "A recording studio",
    "venue_type": "Recording Studio",
    "social_links": ["https://instagram.com/studioa"],
    "capacity": "50",
    "pricing": "$100/hr",
    "star_rating": 4.5,
    "review_count": 42,
}


class TestInitDb:
    """Test database creation and migration."""

    def test_creates_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        assert db_path.exists()

        with get_db(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        names = [t["name"] for t in tables]
        assert "venues" in names
        assert "outreach_status" in names

    def test_migration_is_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        # Insert a venue
        with get_db(db_path) as conn:
            upsert_venue(conn, SAMPLE_VENUE)

        # Run migration again -- should not lose data
        init_db(db_path)

        with get_db(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
        assert count == 1

    def test_health_snapshot_created(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        health_path = db_path.with_suffix(".health.json")
        assert health_path.exists()
        snapshot = json.loads(health_path.read_text())
        assert snapshot["integrity"] == "ok"
        assert snapshot["venue_count"] == 0


class TestGetDb:
    """Test connection context manager."""

    def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with get_db(db_path) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_enabled(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        with get_db(db_path) as conn:
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_rollback_on_exception(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(ValueError):
            with get_db(db_path) as conn:
                upsert_venue(conn, SAMPLE_VENUE)
                raise ValueError("force rollback")

        # Venue should not be persisted
        with get_db(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
        assert count == 0


class TestPytestGuard:
    """Test that production DB is protected during tests."""

    def test_rejects_production_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from db import DB_PATH, _assert_not_pytest_production

        # PYTEST_CURRENT_TEST is already set because we're in pytest
        with pytest.raises(RuntimeError, match="production venues.db"):
            _assert_not_pytest_production(DB_PATH)


class TestBackupDb:
    """Test WAL-safe backup."""

    def test_creates_backup_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        # Insert data before backup
        with get_db(db_path) as conn:
            upsert_venue(conn, SAMPLE_VENUE)

        backup_path = backup_db(db_path)
        assert backup_path.exists()
        assert "backup" in backup_path.name

        # Backup should contain the venue
        with get_db(backup_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
        assert count == 1

    def test_backup_missing_db_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            backup_db(tmp_path / "nonexistent.db")


class TestUpsertVenue:
    """Test single-writer venue insert/update."""

    def test_insert_new_venue(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_db(db_path) as conn:
            venue_id = upsert_venue(conn, SAMPLE_VENUE)

        assert venue_id == 1

        with get_db(db_path) as conn:
            row = conn.execute("SELECT * FROM venues WHERE id = 1").fetchone()
        assert row["name"] == "Studio A"
        assert row["email"] == "info@studioa.com"
        assert row["star_rating"] == 4.5

    def test_upsert_updates_existing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_db(db_path) as conn:
            upsert_venue(conn, SAMPLE_VENUE)
            # Re-scrape with updated phone, null email
            updated = {**SAMPLE_VENUE, "phone": "555-9999", "email": None}
            upsert_venue(conn, updated)

        with get_db(db_path) as conn:
            row = conn.execute("SELECT * FROM venues WHERE id = 1").fetchone()
        # Phone updated, email preserved (COALESCE)
        assert row["phone"] == "555-9999"
        assert row["email"] == "info@studioa.com"
        assert row["updated_at"] is not None

    def test_upsert_dedup_by_source_url(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_db(db_path) as conn:
            upsert_venue(conn, SAMPLE_VENUE)
            upsert_venue(conn, SAMPLE_VENUE)
            count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
        assert count == 1


class TestOutreachStatus:
    """Test outreach status management."""

    def test_ensure_creates_new_status(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_db(db_path) as conn:
            venue_id = upsert_venue(conn, SAMPLE_VENUE)
            ensure_outreach_status(conn, venue_id)

            row = conn.execute(
                "SELECT status FROM outreach_status WHERE venue_id = ?",
                (venue_id,),
            ).fetchone()
        assert row["status"] == "new"

    def test_ensure_is_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with get_db(db_path) as conn:
            venue_id = upsert_venue(conn, SAMPLE_VENUE)
            ensure_outreach_status(conn, venue_id)
            ensure_outreach_status(conn, venue_id)  # should not raise

            count = conn.execute(
                "SELECT COUNT(*) FROM outreach_status WHERE venue_id = ?",
                (venue_id,),
            ).fetchone()[0]
        assert count == 1
