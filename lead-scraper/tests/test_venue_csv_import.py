"""Tests for scrapers/venue_csv.py -- venue CSV normalization and import."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.venue_csv import normalize, scrape


FIXTURE_CSV = Path(__file__).parent / "fixtures" / "venue_outreach.csv"


class TestNormalize:
    """Test venue CSV row -> lead dict mapping."""

    def test_full_row_maps_correctly(self) -> None:
        row = {
            "name": "Studio A",
            "email": "info@studioa.com",
            "phone": "555-1234",
            "website": "https://studioa.com",
            "source_url": "https://studioa.com",
            "description": "A great recording studio",
            "venue_type": "Recording Studio",
        }
        lead = normalize(row)
        assert lead is not None
        assert lead["name"] == "Studio A"
        assert lead["profile_url"] == "https://studioa.com"
        assert lead["email"] == "info@studioa.com"
        assert lead["phone"] == "555-1234"
        assert lead["website"] == "https://studioa.com"
        assert lead["bio"] == "A great recording studio"
        assert lead["source"] == "venue_scraper"
        assert lead["activity"] == "Venue: Recording Studio"

    def test_missing_source_url_returns_none(self) -> None:
        row = {"name": "Test", "source_url": "", "email": "a@b.com"}
        assert normalize(row) is None

    def test_missing_name_returns_none(self) -> None:
        row = {"name": "", "source_url": "https://test.com"}
        assert normalize(row) is None

    def test_optional_fields_default_to_none(self) -> None:
        row = {"name": "Minimal", "source_url": "https://minimal.com"}
        lead = normalize(row)
        assert lead is not None
        assert lead["email"] is None
        assert lead["phone"] is None
        assert lead["website"] is None
        assert lead["bio"] is None

    def test_venue_type_prefixed_in_activity(self) -> None:
        row = {"name": "Test", "source_url": "https://test.com", "venue_type": "Gallery"}
        lead = normalize(row)
        assert lead["activity"] == "Venue: Gallery"

    def test_empty_venue_type_no_activity(self) -> None:
        row = {"name": "Test", "source_url": "https://test.com", "venue_type": ""}
        lead = normalize(row)
        assert "activity" not in lead

    def test_source_always_venue_scraper(self) -> None:
        row = {"name": "Test", "source_url": "https://test.com"}
        lead = normalize(row)
        assert lead["source"] == "venue_scraper"


class TestScrape:
    """Test CSV file reading."""

    def test_reads_fixture_csv(self) -> None:
        config = {"csv_path": str(FIXTURE_CSV)}
        leads = scrape(config)
        # Fixture has 6 rows: Studio A, Venue B, No Contact (no source), No Source URL (no source), Phone Only, Special Chars
        # No Contact has no source_url -> skipped
        # No Source URL has no source_url -> skipped
        assert len(leads) == 4
        assert leads[0]["name"] == "Studio A"
        assert leads[1]["name"] == "Venue B, LLC"

    def test_skips_rows_without_source_url(self) -> None:
        config = {"csv_path": str(FIXTURE_CSV)}
        leads = scrape(config)
        names = [l["name"] for l in leads]
        assert "No Source URL" not in names
        assert "No Contact" not in names

    def test_phone_carries_through(self) -> None:
        config = {"csv_path": str(FIXTURE_CSV)}
        leads = scrape(config)
        phone_only = [l for l in leads if l["name"] == "Phone Only"][0]
        assert phone_only["phone"] == "555-9999"

    def test_missing_csv_returns_empty(self, tmp_path: Path) -> None:
        config = {"csv_path": str(tmp_path / "nonexistent.csv")}
        leads = scrape(config)
        assert leads == []

    def test_special_characters_handled(self) -> None:
        config = {"csv_path": str(FIXTURE_CSV)}
        leads = scrape(config)
        special = [l for l in leads if "Special" in l["name"]][0]
        assert special["name"] == 'Special "Chars" Venue'
