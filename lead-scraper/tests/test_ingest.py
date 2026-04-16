"""Tests for ingest.py validation and deduplication. Uses a temp DB, no Apify."""

import sys
import tempfile
from pathlib import Path

# Add lead-scraper/ to import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import init_db, get_db
from ingest import ingest_leads


def _make_lead(**overrides):
    """Helper to create a valid NormalizedLead dict with overrides."""
    base = {
        "name": "Jane Doe",
        "bio": "Filmmaker",
        "location": "San Diego, CA",
        "email": None,
        "profile_url": "https://example.com/jane",
        "activity": "Organized: Workshop",
        "source": "eventbrite",
    }
    base.update(overrides)
    return base


def _temp_db():
    """Create a temporary database and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()
    init_db(db_path)
    return db_path


def test_ingest_valid_lead():
    db_path = _temp_db()
    leads = [_make_lead()]
    inserted, skipped, invalid = ingest_leads(leads, db_path)
    assert inserted == 1
    assert skipped == 0
    assert invalid == 0

    with get_db(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    assert count == 1


def test_ingest_rejects_missing_name():
    db_path = _temp_db()
    leads = [_make_lead(name=None)]
    inserted, skipped, invalid = ingest_leads(leads, db_path)
    assert invalid == 1
    assert inserted == 0


def test_ingest_rejects_missing_profile_url():
    db_path = _temp_db()
    leads = [_make_lead(profile_url=None)]
    inserted, skipped, invalid = ingest_leads(leads, db_path)
    assert invalid == 1
    assert inserted == 0


def test_ingest_rejects_non_https_url():
    db_path = _temp_db()
    leads = [_make_lead(profile_url="javascript:alert(1)")]
    inserted, skipped, invalid = ingest_leads(leads, db_path)
    assert invalid == 1
    assert inserted == 0


def test_ingest_rejects_http_url():
    db_path = _temp_db()
    leads = [_make_lead(profile_url="http://example.com/jane")]
    inserted, skipped, invalid = ingest_leads(leads, db_path)
    assert invalid == 1
    assert inserted == 0


def test_ingest_dedup_same_source_and_url():
    """Same (source, profile_url) inserted twice -> second is skipped."""
    db_path = _temp_db()
    lead = _make_lead()
    inserted1, skipped1, _ = ingest_leads([lead], db_path)
    inserted2, skipped2, _ = ingest_leads([lead], db_path)
    assert inserted1 == 1
    assert inserted2 == 0
    assert skipped2 == 1


def test_ingest_allows_same_url_different_source():
    """Same profile_url with different source = two distinct leads."""
    db_path = _temp_db()
    lead1 = _make_lead(source="eventbrite")
    lead2 = _make_lead(source="meetup")
    ingest_leads([lead1], db_path)
    inserted, skipped, _ = ingest_leads([lead2], db_path)
    assert inserted == 1
    assert skipped == 0


def test_ingest_batch_counts():
    """Batch of mixed valid/invalid leads returns correct counts."""
    db_path = _temp_db()
    leads = [
        _make_lead(profile_url="https://example.com/a"),
        _make_lead(profile_url="https://example.com/b"),
        _make_lead(profile_url="javascript:bad"),  # invalid
        _make_lead(name=None),  # invalid
    ]
    inserted, skipped, invalid = ingest_leads(leads, db_path)
    assert inserted == 2
    assert skipped == 0
    assert invalid == 2


if __name__ == "__main__":
    test_ingest_valid_lead()
    test_ingest_rejects_missing_name()
    test_ingest_rejects_missing_profile_url()
    test_ingest_rejects_non_https_url()
    test_ingest_rejects_http_url()
    test_ingest_dedup_same_source_and_url()
    test_ingest_allows_same_url_different_source()
    test_ingest_batch_counts()
    print("All ingest tests passed.")
