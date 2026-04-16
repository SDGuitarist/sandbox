"""Fixture-based tests for scraper normalization. No Apify dependency."""

import json
import sys
from pathlib import Path

# Add lead-scraper/ to import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.eventbrite import normalize as eb_normalize
from scrapers.meetup import normalize as mu_normalize
from scrapers.facebook import normalize as fb_normalize
from scrapers.linkedin import normalize as li_normalize

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name):
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def test_eventbrite_normalization():
    _run_fixture_test(eb_normalize, "eventbrite_raw.json", "eventbrite_normalized.json", "Eventbrite")


def test_normalize_missing_organizer():
    """Items without organizer data return None."""
    raw = {"url": "https://example.com", "name": "Event", "organizer": None}
    assert eb_normalize(raw) is None


def test_normalize_missing_organizer_url():
    """Items with organizer but no URL return None."""
    raw = {
        "url": "https://example.com",
        "name": "Event",
        "organizer": {"name": "Someone", "url": None},
    }
    assert eb_normalize(raw) is None


def test_normalize_missing_organizer_name():
    """Items with organizer URL but no name return None."""
    raw = {
        "url": "https://example.com",
        "name": "Event",
        "organizer": {"name": None, "url": "https://eventbrite.com/o/123"},
    }
    assert eb_normalize(raw) is None


def test_normalize_null_location():
    """Items with null location produce None location field."""
    raw = {
        "url": "https://example.com",
        "name": "Event",
        "location": None,
        "organizer": {"name": "Org", "url": "https://eventbrite.com/o/org-123", "description": None},
    }
    result = eb_normalize(raw)
    assert result is not None
    assert result["location"] is None


def _run_fixture_test(normalize_fn, raw_file, expected_file, source_name):
    """Generic fixture test: normalize raw items and compare to expected."""
    raw_items = load_fixture(raw_file)
    expected = load_fixture(expected_file)
    result = [lead for item in raw_items if (lead := normalize_fn(item)) is not None]
    assert len(result) == len(expected), f"{source_name}: expected {len(expected)} leads, got {len(result)}"
    for i, (got, want) in enumerate(zip(result, expected)):
        assert got == want, f"{source_name} lead {i} mismatch:\n  got:  {got}\n  want: {want}"


def test_meetup_normalization():
    _run_fixture_test(mu_normalize, "meetup_raw.json", "meetup_normalized.json", "Meetup")


def test_facebook_normalization():
    _run_fixture_test(fb_normalize, "facebook_raw.json", "facebook_normalized.json", "Facebook")


def test_linkedin_normalization():
    _run_fixture_test(li_normalize, "linkedin_raw.json", "linkedin_normalized.json", "LinkedIn")


def test_meetup_missing_profile_url():
    raw = {"name": "Someone", "profileUrl": None, "city": "SD"}
    assert mu_normalize(raw) is None


def test_linkedin_missing_names():
    raw = {"firstName": "", "lastName": "", "profileUrl": "https://linkedin.com/in/x"}
    assert li_normalize(raw) is None


def test_facebook_missing_profile_url():
    raw = {"name": "Someone", "profileUrl": None}
    assert fb_normalize(raw) is None
