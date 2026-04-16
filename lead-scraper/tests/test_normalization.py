"""Fixture-based tests for scraper normalization. No Apify dependency."""

import json
import sys
from pathlib import Path

# Add lead-scraper/ to import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.eventbrite import normalize

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name):
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def test_eventbrite_normalization():
    """Each raw Eventbrite item normalizes to the expected NormalizedLead."""
    raw_items = load_fixture("eventbrite_raw.json")
    expected = load_fixture("eventbrite_normalized.json")

    result = []
    for item in raw_items:
        normalized = normalize(item)
        if normalized is not None:
            result.append(normalized)

    assert len(result) == len(expected), f"Expected {len(expected)} leads, got {len(result)}"
    for i, (got, want) in enumerate(zip(result, expected)):
        assert got == want, f"Lead {i} mismatch:\n  got:  {got}\n  want: {want}"


def test_normalize_missing_organizer():
    """Items without organizer data return None."""
    raw = {"url": "https://example.com", "name": "Event", "organizer": None}
    assert normalize(raw) is None


def test_normalize_missing_organizer_url():
    """Items with organizer but no URL return None."""
    raw = {
        "url": "https://example.com",
        "name": "Event",
        "organizer": {"name": "Someone", "url": None},
    }
    assert normalize(raw) is None


def test_normalize_missing_organizer_name():
    """Items with organizer URL but no name return None."""
    raw = {
        "url": "https://example.com",
        "name": "Event",
        "organizer": {"name": None, "url": "https://eventbrite.com/o/123"},
    }
    assert normalize(raw) is None


def test_normalize_null_location():
    """Items with null location produce None location field."""
    raw = {
        "url": "https://example.com",
        "name": "Event",
        "location": None,
        "organizer": {"name": "Org", "url": "https://eventbrite.com/o/org-123", "description": None},
    }
    result = normalize(raw)
    assert result is not None
    assert result["location"] is None


if __name__ == "__main__":
    test_eventbrite_normalization()
    test_normalize_missing_organizer()
    test_normalize_missing_organizer_url()
    test_normalize_missing_organizer_name()
    test_normalize_null_location()
    print("All normalization tests passed.")
