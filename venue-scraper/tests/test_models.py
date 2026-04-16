"""Fixture-based tests for validate_extraction(), VenueData schema, CLI, and crawler config.

No live Claude API calls -- all tests use pre-captured JSON fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from models import VenueData, validate_extraction
from scrape import is_valid_url, load_urls

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


# --- validate_extraction: happy path ---


def test_complete_venue_extracts_all_fields() -> None:
    data = load_fixture("venue_complete.json")
    result = validate_extraction(data, "https://grandballroom.com")
    assert result is not None
    assert result.name == "The Grand Ballroom"
    assert result.capacity == 300
    assert result.source_url == "https://grandballroom.com"
    assert len(result.amenities) == 5
    assert result.star_rating == 4.7


def test_minimal_venue_with_name_only() -> None:
    data = load_fixture("venue_minimal.json")
    result = validate_extraction(data, "https://joes.com")
    assert result is not None
    assert result.name == "Joe's Bar & Grill"
    assert result.capacity is None
    assert result.pricing is None
    assert result.source_url == "https://joes.com"


def test_source_url_is_injected() -> None:
    result = validate_extraction({"name": "Test"}, "https://test.com")
    assert result is not None
    assert result.source_url == "https://test.com"


def test_scraped_at_is_set_automatically() -> None:
    result = validate_extraction({"name": "Test"}, "https://test.com")
    assert result is not None
    assert result.scraped_at is not None


# --- validate_extraction: string input ---


def test_json_string_input() -> None:
    json_str = '{"name": "String Venue", "capacity": 100}'
    result = validate_extraction(json_str, "https://example.com")
    assert result is not None
    assert result.name == "String Venue"
    assert result.capacity == 100


# --- validate_extraction: list output ---


def test_list_output_takes_first_element() -> None:
    data = [{"name": "First Venue"}, {"name": "Second Venue"}]
    result = validate_extraction(data, "https://example.com")
    assert result is not None
    assert result.name == "First Venue"


def test_empty_list_returns_none() -> None:
    result = validate_extraction([], "https://example.com")
    assert result is None


# --- validate_extraction: error cases ---


def test_missing_required_name_returns_none() -> None:
    data = load_fixture("venue_missing_name.json")
    result = validate_extraction(data, "https://example.com")
    assert result is None


def test_malformed_json_string_returns_none() -> None:
    result = validate_extraction("not json {{{", "https://example.com")
    assert result is None


def test_empty_dict_returns_none() -> None:
    result = validate_extraction({}, "https://example.com")
    assert result is None


def test_none_input_returns_none() -> None:
    result = validate_extraction(None, "https://example.com")  # type: ignore[arg-type]
    assert result is None


# --- VenueData schema: field constraints ---


def test_photos_capped_at_20() -> None:
    data = {"name": "Big Gallery", "photos": [f"https://img.com/{i}.jpg" for i in range(25)]}
    result = validate_extraction(data, "https://example.com")
    # Pydantic max_length on list should reject >20 items
    assert result is None


def test_optional_fields_default_to_none_or_empty() -> None:
    result = validate_extraction({"name": "Bare Venue"}, "https://example.com")
    assert result is not None
    assert result.email is None
    assert result.phone is None
    assert result.amenities == []
    assert result.social_links == []
    assert result.photos == []


# --- URL validation ---


def test_valid_http_url() -> None:
    assert is_valid_url("http://example.com") is True


def test_valid_https_url() -> None:
    assert is_valid_url("https://example.com") is True


def test_ftp_url_is_invalid() -> None:
    assert is_valid_url("ftp://example.com") is False


def test_bare_domain_is_invalid() -> None:
    assert is_valid_url("example.com") is False


def test_empty_string_is_invalid() -> None:
    assert is_valid_url("") is False


# --- load_urls ---


def test_load_urls_skips_comments_and_blanks(tmp_path: Path) -> None:
    f = tmp_path / "urls.txt"
    f.write_text("# comment\nhttps://a.com\n\nhttps://b.com\n")
    urls = load_urls(f)
    assert urls == ["https://a.com", "https://b.com"]


def test_load_urls_deduplicates_preserving_order(tmp_path: Path) -> None:
    f = tmp_path / "urls.txt"
    f.write_text("https://a.com\nhttps://b.com\nhttps://a.com\n")
    urls = load_urls(f)
    assert urls == ["https://a.com", "https://b.com"]


def test_load_urls_skips_invalid_schemes(tmp_path: Path) -> None:
    f = tmp_path / "urls.txt"
    f.write_text("https://good.com\nftp://bad.com\njust-text\n")
    urls = load_urls(f)
    assert urls == ["https://good.com"]


def test_load_urls_exits_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        load_urls(tmp_path / "nonexistent.txt")


# --- Crawler config assertions ---


def test_run_config_uses_cache_bypass() -> None:
    from crawl4ai import CacheMode
    from crawler import get_run_config

    config = get_run_config()
    assert config.cache_mode == CacheMode.BYPASS


def test_run_config_uses_domcontentloaded() -> None:
    from crawler import get_run_config

    config = get_run_config()
    assert config.wait_until == "domcontentloaded"


def test_dispatcher_limits_concurrency() -> None:
    from crawler import CONCURRENCY_LIMIT, get_dispatcher

    dispatcher = get_dispatcher()
    assert dispatcher.max_session_permit == CONCURRENCY_LIMIT
    assert CONCURRENCY_LIMIT == 3
