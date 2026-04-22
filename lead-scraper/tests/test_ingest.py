"""Tests for ingest.py validation and deduplication. Uses a temp DB, no Apify."""

import sys
from pathlib import Path

# Add lead-scraper/ to import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db
from ingest import ingest_leads


def _make_lead(**overrides):
    """Helper to create a valid NormalizedLead dict with overrides."""
    base = {
        "name": "Jane Doe",
        "bio": "Filmmaker",
        "location": "San Diego, CA",
        "email": None,
        "website": None,
        "profile_url": "https://example.com/jane",
        "activity": "Organized: Workshop",
        "source": "eventbrite",
    }
    base.update(overrides)
    return base


def test_ingest_valid_lead(setup_db):
    leads = [_make_lead()]
    inserted, skipped, invalid = ingest_leads(leads, setup_db)
    assert inserted == 1
    assert skipped == 0
    assert invalid == 0

    with get_db(setup_db) as conn:
        count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    assert count == 1


def test_ingest_rejects_missing_name(setup_db):
    leads = [_make_lead(name=None)]
    inserted, skipped, invalid = ingest_leads(leads, setup_db)
    assert invalid == 1
    assert inserted == 0


def test_ingest_rejects_missing_profile_url(setup_db):
    leads = [_make_lead(profile_url=None)]
    inserted, skipped, invalid = ingest_leads(leads, setup_db)
    assert invalid == 1
    assert inserted == 0


def test_ingest_rejects_non_https_url(setup_db):
    leads = [_make_lead(profile_url="javascript:alert(1)")]
    inserted, skipped, invalid = ingest_leads(leads, setup_db)
    assert invalid == 1
    assert inserted == 0


def test_ingest_rejects_http_url(setup_db):
    leads = [_make_lead(profile_url="http://example.com/jane")]
    inserted, skipped, invalid = ingest_leads(leads, setup_db)
    assert invalid == 1
    assert inserted == 0


def test_ingest_dedup_same_source_and_url(setup_db):
    """Same (source, profile_url) inserted twice -> second is skipped."""
    lead = _make_lead()
    inserted1, skipped1, _ = ingest_leads([lead], setup_db)
    inserted2, skipped2, _ = ingest_leads([lead], setup_db)
    assert inserted1 == 1
    assert inserted2 == 0
    assert skipped2 == 1


def test_ingest_allows_same_url_different_source(setup_db):
    """Same profile_url with different source = two distinct leads."""
    lead1 = _make_lead(source="eventbrite")
    lead2 = _make_lead(source="meetup")
    ingest_leads([lead1], setup_db)
    inserted, skipped, _ = ingest_leads([lead2], setup_db)
    assert inserted == 1
    assert skipped == 0


def test_ingest_batch_counts(setup_db):
    """Batch of mixed valid/invalid leads returns correct counts."""
    leads = [
        _make_lead(profile_url="https://example.com/a"),
        _make_lead(profile_url="https://example.com/b"),
        _make_lead(profile_url="javascript:bad"),  # invalid
        _make_lead(name=None),  # invalid
    ]
    inserted, skipped, invalid = ingest_leads(leads, setup_db)
    assert inserted == 2
    assert skipped == 0
    assert invalid == 2
