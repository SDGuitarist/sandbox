"""Tests for delete_source() -- source-level lead deletion with protection."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import init_db, get_db
from models import delete_source


def _setup_db(db_path: Path) -> None:
    """Create a test DB with leads, campaigns, and outreach queue."""
    init_db(db_path, allow_create_production=False)
    with get_db(db_path) as conn:
        # Insert leads from two sources
        conn.execute(
            "INSERT INTO leads (name, profile_url, source) VALUES (?, ?, ?)",
            ("Venue A", "https://a.com", "venue_scraper"),
        )
        conn.execute(
            "INSERT INTO leads (name, profile_url, source) VALUES (?, ?, ?)",
            ("Venue B", "https://b.com", "venue_scraper"),
        )
        conn.execute(
            "INSERT INTO leads (name, profile_url, source) VALUES (?, ?, ?)",
            ("Person C", "https://c.com", "eventbrite"),
        )

        # Create a campaign
        conn.execute(
            "INSERT INTO campaigns (name) VALUES (?)", ("Test Campaign",)
        )

        # Assign Venue A to campaign
        conn.execute(
            "INSERT INTO campaign_leads (campaign_id, lead_id) VALUES (1, 1)"
        )

        # Create queue entry for Venue A (sent status = protected)
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, status) VALUES (1, 1, 'sent')"
        )


class TestDeleteSource:

    def test_deletes_unprotected_leads(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path)

        result = delete_source("venue_scraper", db_path=db_path)
        # Venue A is protected (sent outreach), Venue B is deletable
        assert result["total"] == 2
        assert result["protected"] == 1
        assert result["deleted"] == 1

        # Verify Venue B is gone, Venue A remains
        with get_db(db_path) as conn:
            remaining = conn.execute(
                "SELECT name FROM leads WHERE source = 'venue_scraper'"
            ).fetchall()
        assert len(remaining) == 1
        assert remaining[0]["name"] == "Venue A"

    def test_refuses_to_delete_sent_outreach(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path)

        result = delete_source("venue_scraper", db_path=db_path)
        assert result["protected"] == 1  # Venue A has sent outreach

    def test_dry_run_no_changes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path)

        result = delete_source("venue_scraper", db_path=db_path, dry_run=True)
        assert result["deleted"] == 1  # Would delete

        # But nothing actually deleted
        with get_db(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE source = 'venue_scraper'"
            ).fetchone()[0]
        assert count == 2

    def test_nonexistent_source_returns_zero(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path)

        result = delete_source("nonexistent", db_path=db_path)
        assert result["total"] == 0
        assert result["deleted"] == 0

    def test_does_not_affect_other_sources(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path)

        delete_source("venue_scraper", db_path=db_path)

        with get_db(db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE source = 'eventbrite'"
            ).fetchone()[0]
        assert count == 1

    def test_reports_campaign_and_queue_counts(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _setup_db(db_path)

        result = delete_source("venue_scraper", db_path=db_path, dry_run=True)
        assert result["campaign_leads"] == 1
        assert result["queue_entries"] == 1
