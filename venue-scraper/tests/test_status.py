"""Tests for outreach status management (set, list, filter)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import (
    ensure_outreach_status,
    get_db,
    init_db,
    list_venues_by_status,
    set_outreach_status,
    upsert_venue,
)


def _seed_venues(db_path: Path) -> list[int]:
    """Insert 3 venues and return their IDs."""
    venues = [
        {"name": "Studio A", "source_url": "https://a.com"},
        {"name": "Studio B", "source_url": "https://b.com"},
        {"name": "Studio C", "source_url": "https://c.com"},
    ]
    ids = []
    with get_db(db_path) as conn:
        for v in venues:
            vid = upsert_venue(conn, v)
            ensure_outreach_status(conn, vid)
            ids.append(vid)
    return ids


class TestSetOutreachStatus:

    def test_set_valid_status(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        ids = _seed_venues(db_path)

        result = set_outreach_status(ids[0], "contacted", db_path=db_path)
        assert result is True

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT status FROM outreach_status WHERE venue_id = ?",
                (ids[0],),
            ).fetchone()
        assert row["status"] == "contacted"

    def test_set_status_with_notes(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        ids = _seed_venues(db_path)

        set_outreach_status(ids[0], "contacted", notes="Called May 20", db_path=db_path)

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT notes FROM outreach_status WHERE venue_id = ?",
                (ids[0],),
            ).fetchone()
        assert row["notes"] == "Called May 20"

    def test_set_invalid_status_raises(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        ids = _seed_venues(db_path)

        with pytest.raises(ValueError, match="Invalid status"):
            set_outreach_status(ids[0], "bogus", db_path=db_path)

    def test_set_nonexistent_venue_returns_false(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        result = set_outreach_status(999, "contacted", db_path=db_path)
        assert result is False

    def test_update_status_overwrites(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        ids = _seed_venues(db_path)

        set_outreach_status(ids[0], "contacted", db_path=db_path)
        set_outreach_status(ids[0], "replied", notes="Got response", db_path=db_path)

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT status, notes FROM outreach_status WHERE venue_id = ?",
                (ids[0],),
            ).fetchone()
        assert row["status"] == "replied"
        assert row["notes"] == "Got response"


class TestListVenuesByStatus:

    def test_list_all(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        _seed_venues(db_path)

        venues = list_venues_by_status(db_path=db_path)
        assert len(venues) == 3

    def test_filter_by_status(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)
        ids = _seed_venues(db_path)

        set_outreach_status(ids[0], "contacted", db_path=db_path)

        new_venues = list_venues_by_status("new", db_path=db_path)
        contacted_venues = list_venues_by_status("contacted", db_path=db_path)
        assert len(new_venues) == 2
        assert len(contacted_venues) == 1
        assert contacted_venues[0]["name"] == "Studio A"

    def test_filter_invalid_status_raises(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        with pytest.raises(ValueError, match="Invalid status"):
            list_venues_by_status("bogus", db_path=db_path)

    def test_empty_db_returns_empty_list(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        init_db(db_path)

        venues = list_venues_by_status(db_path=db_path)
        assert venues == []
