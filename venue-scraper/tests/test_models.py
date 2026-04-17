"""Tests for venue scraper: models, CLI helpers, crawler config, storage.

No live Claude API calls -- all tests use pre-captured JSON fixtures.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from models import VenueData, VenueSource, validate_extraction
from scrape import is_valid_url, load_urls

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


# ── validate_extraction: happy path ──────────────────────────


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


# ── validate_extraction: string input ────────────────────────


def test_json_string_input() -> None:
    json_str = '{"name": "String Venue", "capacity": 100}'
    result = validate_extraction(json_str, "https://example.com")
    assert result is not None
    assert result.name == "String Venue"
    assert result.capacity == 100


# ── validate_extraction: list output ─────────────────────────


def test_list_output_takes_first_element() -> None:
    data = [{"name": "First Venue"}, {"name": "Second Venue"}]
    result = validate_extraction(data, "https://example.com")
    assert result is not None
    assert result.name == "First Venue"


def test_empty_list_returns_none() -> None:
    result = validate_extraction([], "https://example.com")
    assert result is None


# ── validate_extraction: error cases ─────────────────────────


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


# ── VenueData schema: field constraints ──────────────────────


def test_photos_capped_at_20() -> None:
    data = {"name": "Big Gallery", "photos": [f"https://img.com/{i}.jpg" for i in range(25)]}
    result = validate_extraction(data, "https://example.com")
    assert result is None


def test_optional_fields_default_to_none_or_empty() -> None:
    result = validate_extraction({"name": "Bare Venue"}, "https://example.com")
    assert result is not None
    assert result.email is None
    assert result.phone is None
    assert result.amenities == []
    assert result.social_links == []
    assert result.photos == []


# ── VenueSource StrEnum (Step B) ─────────────────────────────


def test_source_defaults_to_website() -> None:
    result = validate_extraction({"name": "Test"}, "https://test.com")
    assert result is not None
    assert result.source == VenueSource.WEBSITE
    assert str(result.source) == "website"


def test_source_accepts_valid_enum_value() -> None:
    data = {"name": "Test", "source": "gigsalad"}
    result = validate_extraction(data, "https://test.com")
    assert result is not None
    assert result.source == VenueSource.GIGSALAD


def test_source_rejects_invalid_value() -> None:
    data = {"name": "Test", "source": "fakesource"}
    result = validate_extraction(data, "https://test.com")
    assert result is None


def test_source_can_be_set_after_creation() -> None:
    result = validate_extraction({"name": "Test"}, "https://test.com")
    assert result is not None
    result.source = VenueSource.THEBASH
    assert result.source == VenueSource.THEBASH


# ── URL validation ───────────────────────────────────────────


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


# ── load_urls ────────────────────────────────────────────────


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


# ── Crawler config ───────────────────────────────────────────


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


def test_html_mode_uses_larger_chunks() -> None:
    from crawler import get_run_config

    normal = get_run_config(html_mode=False)
    html = get_run_config(html_mode=True)
    assert html.extraction_strategy.chunk_token_threshold > normal.extraction_strategy.chunk_token_threshold


def test_html_mode_still_bypasses_cache() -> None:
    from crawl4ai import CacheMode
    from crawler import get_run_config

    config = get_run_config(html_mode=True)
    assert config.cache_mode == CacheMode.BYPASS


# ── Proxy config (Step B) ───────────────────────────────────


def test_proxy_from_env_returns_none_when_not_set() -> None:
    import os
    from crawler import get_proxy_from_env

    os.environ.pop("IPROYAL_PROXY_SERVER", None)
    assert get_proxy_from_env() is None


def test_proxy_from_env_returns_config_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from crawler import get_proxy_from_env

    monkeypatch.setenv("IPROYAL_PROXY_SERVER", "http://proxy:8080")
    monkeypatch.setenv("IPROYAL_PROXY_USER", "user1")
    monkeypatch.setenv("IPROYAL_PROXY_PASS", "pass1")
    config = get_proxy_from_env()
    assert config is not None
    assert config["server"] == "http://proxy:8080"
    assert config["username"] == "user1"
    assert config["password"] == "pass1"


def test_browser_config_accepts_proxy() -> None:
    from crawler import ProxyConfig, get_browser_config

    proxy = ProxyConfig(server="http://proxy:8080", username="u", password="p")
    config = get_browser_config(proxy_config=proxy)
    assert config.proxy_config is not None


def test_browser_config_works_without_proxy() -> None:
    from crawler import get_browser_config

    config = get_browser_config(proxy_config=None)
    assert config.proxy_config is None


# ── SQLite storage (Step C) ──────────────────────────────────


@pytest.fixture()
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """Create an in-memory-like temp DB with the real schema."""
    from db import get_db, init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _make_venue(**overrides: object) -> VenueData:
    defaults = {"name": "Test Venue", "source_url": "https://example.com"}
    defaults.update(overrides)
    return VenueData(**defaults)


def test_insert_venue_returns_inserted(db_conn: sqlite3.Connection) -> None:
    from ingest import insert_venue

    venue = _make_venue()
    assert insert_venue(db_conn, venue) == "inserted"
    db_conn.commit()


def test_insert_duplicate_returns_skipped(db_conn: sqlite3.Connection) -> None:
    from ingest import insert_venue

    venue = _make_venue()
    insert_venue(db_conn, venue)
    db_conn.commit()
    assert insert_venue(db_conn, venue) == "skipped"
    db_conn.commit()


def test_same_url_different_source_both_inserted(db_conn: sqlite3.Connection) -> None:
    from ingest import insert_venue

    v1 = _make_venue(source=VenueSource.WEBSITE)
    v2 = _make_venue(source=VenueSource.GIGSALAD)
    assert insert_venue(db_conn, v1) == "inserted"
    db_conn.commit()
    assert insert_venue(db_conn, v2) == "inserted"
    db_conn.commit()

    rows = db_conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    assert rows == 2


def test_sql_injection_payload_stored_safely(db_conn: sqlite3.Connection) -> None:
    """Parameterized queries must prevent SQL injection."""
    from ingest import insert_venue

    evil_name = "'; DROP TABLE venues; --"
    venue = _make_venue(name=evil_name, source_url="https://evil.com")
    assert insert_venue(db_conn, venue) == "inserted"
    db_conn.commit()

    # Table still exists and contains the row
    row = db_conn.execute("SELECT name FROM venues WHERE source_url = ?", ("https://evil.com",)).fetchone()
    assert row is not None
    assert row["name"] == evil_name

    # Table was not dropped
    count = db_conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
    assert count == 1


def test_init_db_creates_table(tmp_path: Path) -> None:
    from db import get_db, init_db

    db_path = tmp_path / "fresh.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t["name"] for t in tables]
        assert "venues" in table_names


def test_db_uses_wal_mode(tmp_path: Path) -> None:
    from db import get_db, init_db

    db_path = tmp_path / "wal.db"
    init_db(db_path)
    with get_db(db_path) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
