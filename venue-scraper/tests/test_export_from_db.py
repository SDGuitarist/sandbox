"""Tests for export_from_db -- CSV export from database."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import ensure_outreach_status, get_db, init_db, set_outreach_status, upsert_venue
from export import OUTREACH_COLUMNS, export_from_db


def _seed(db_path: Path) -> list[int]:
    """Insert 2 venues with contact info, 1 without."""
    venues = [
        {
            "name": "Studio A",
            "source_url": "https://studioa.com",
            "email": "a@a.com",
            "phone": "555-1111",
            "website": "https://studioa.com",
            "description": "Great studio",
            "venue_type": "Recording Studio",
        },
        {
            "name": "Studio B",
            "source_url": "https://studiob.com",
            "email": "b@b.com",
            "phone": None,
            "website": "https://studiob.com",
            "description": "Another studio",
            "venue_type": "Event Space",
        },
        {
            "name": "No Contact",
            "source_url": "https://nocontact.com",
            "email": None,
            "phone": None,
            "website": None,
            "description": None,
            "venue_type": None,
        },
    ]
    ids = []
    with get_db(db_path) as conn:
        for v in venues:
            vid = upsert_venue(conn, v)
            ensure_outreach_status(conn, vid)
            ids.append(vid)
    return ids


class TestExportFromDb:

    def test_exports_all_venues(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        _seed(db_path)

        output = tmp_path / "outreach.csv"
        count = export_from_db(output, db_path=db_path)

        # 2 of 3 venues have contact info
        assert count == 2
        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["name"] == "Studio A"
        assert rows[1]["name"] == "Studio B"

    def test_includes_source_url_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        _seed(db_path)

        output = tmp_path / "outreach.csv"
        export_from_db(output, db_path=db_path)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert "source_url" in rows[0]
        assert rows[0]["source_url"] == "https://studioa.com"

    def test_includes_description_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        _seed(db_path)

        output = tmp_path / "outreach.csv"
        export_from_db(output, db_path=db_path)

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert "description" in rows[0]
        assert rows[0]["description"] == "Great studio"

    def test_filter_by_status(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        ids = _seed(db_path)

        # Mark Studio A as contacted
        set_outreach_status(ids[0], "contacted", db_path=db_path)

        output = tmp_path / "outreach.csv"
        count = export_from_db(output, status_filter="new", db_path=db_path)

        # Only Studio B remains 'new' with contact info
        assert count == 1
        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["name"] == "Studio B"

    def test_csv_header_matches_outreach_columns(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        _seed(db_path)

        output = tmp_path / "outreach.csv"
        export_from_db(output, db_path=db_path)

        with open(output) as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == OUTREACH_COLUMNS

    def test_requires_db_exists(self, tmp_path: Path) -> None:
        output = tmp_path / "outreach.csv"
        with pytest.raises(FileNotFoundError, match="Run.*migrate"):
            export_from_db(output, db_path=tmp_path / "nonexistent.db")
