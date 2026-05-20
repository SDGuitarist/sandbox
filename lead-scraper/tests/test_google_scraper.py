"""Tests for scrapers/google.py -- SerpAPI discovery, caching, credit tracking."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.google import (
    DIRECTORY_DOMAINS,
    _cache_is_fresh,
    _cache_key,
    _extract_urls,
    _is_directory_site,
    _track_usage,
    search_people,
)


SAMPLE_SERPAPI_RESPONSE = {
    "organic_results": [
        {"link": "https://personalsite.com/about", "title": "John Doe - Filmmaker"},
        {"link": "https://facebook.com/johndoe", "title": "John Doe Facebook"},
        {"link": "https://anotherperson.com", "title": "Jane Smith - Composer"},
        {"link": "https://yelp.com/biz/studio", "title": "Studio on Yelp"},
        {"link": "https://personalsite.com/contact", "title": "John Doe Contact"},
    ]
}


class TestIsDirectorySite:

    def test_yelp_is_directory(self) -> None:
        assert _is_directory_site("https://www.yelp.com/biz/something") is True

    def test_facebook_is_directory(self) -> None:
        assert _is_directory_site("https://facebook.com/person") is True

    def test_imdb_is_directory(self) -> None:
        assert _is_directory_site("https://www.imdb.com/name/nm123") is True

    def test_personal_site_is_not_directory(self) -> None:
        assert _is_directory_site("https://johndoe-filmmaker.com") is False

    def test_empty_url_returns_false(self) -> None:
        assert _is_directory_site("") is False


class TestExtractUrls:

    def test_filters_directory_sites(self) -> None:
        urls = _extract_urls(SAMPLE_SERPAPI_RESPONSE)
        domains = [url for url in urls if "facebook.com" in url or "yelp.com" in url]
        assert len(domains) == 0

    def test_returns_non_directory_urls(self) -> None:
        urls = _extract_urls(SAMPLE_SERPAPI_RESPONSE)
        assert "https://personalsite.com/about" in urls
        assert "https://anotherperson.com" in urls

    def test_deduplicates_by_domain(self) -> None:
        urls = _extract_urls(SAMPLE_SERPAPI_RESPONSE)
        # personalsite.com appears twice but should only be in results once
        personalsite_urls = [u for u in urls if "personalsite.com" in u]
        assert len(personalsite_urls) == 1

    def test_empty_results(self) -> None:
        urls = _extract_urls({"organic_results": []})
        assert urls == []

    def test_missing_organic_results_key(self) -> None:
        urls = _extract_urls({})
        assert urls == []

    def test_filters_non_http_schemes(self) -> None:
        data = {"organic_results": [{"link": "ftp://bad.com/file"}]}
        urls = _extract_urls(data)
        assert urls == []


class TestCacheKey:

    def test_deterministic(self) -> None:
        key1 = _cache_key("filmmaker San Diego", "San Diego, CA")
        key2 = _cache_key("filmmaker San Diego", "San Diego, CA")
        assert key1 == key2

    def test_different_queries_different_keys(self) -> None:
        key1 = _cache_key("filmmaker", "San Diego")
        key2 = _cache_key("composer", "San Diego")
        assert key1 != key2


class TestCacheIsFresh:

    def test_fresh_cache(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "test.json"
        cache_file.write_text("{}")
        assert _cache_is_fresh(cache_file) is True

    def test_missing_cache(self, tmp_path: Path) -> None:
        assert _cache_is_fresh(tmp_path / "missing.json") is False

    def test_stale_cache(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "test.json"
        cache_file.write_text("{}")
        # Set mtime to 8 days ago
        old_time = time.time() - (8 * 86400)
        import os
        os.utime(cache_file, (old_time, old_time))
        assert _cache_is_fresh(cache_file) is False


class TestSearchPeople:

    @patch("scrapers.google.requests.get")
    def test_returns_urls_on_success(self, mock_get: MagicMock, tmp_path: Path) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_SERPAPI_RESPONSE
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "test-key"}):
            with patch("scrapers.google.CACHE_DIR", tmp_path):
                urls = search_people("filmmaker San Diego", use_cache=False)

        assert len(urls) >= 2
        assert any("personalsite.com" in u for u in urls)

    @patch("scrapers.google.requests.get")
    def test_returns_empty_on_429(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "test-key"}):
            urls = search_people("test", use_cache=False)

        assert urls == []

    @patch("scrapers.google.requests.get")
    def test_returns_empty_on_401(self, mock_get: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "bad-key"}):
            urls = search_people("test", use_cache=False)

        assert urls == []

    def test_returns_empty_when_no_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            # Remove SERPAPI_API_KEY if present
            import os
            os.environ.pop("SERPAPI_API_KEY", None)
            urls = search_people("test", use_cache=False)

        assert urls == []

    @patch("scrapers.google.requests.get")
    def test_handles_timeout(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = requests.exceptions.Timeout()

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "test-key"}):
            urls = search_people("test", use_cache=False)

        assert urls == []

    @patch("scrapers.google.requests.get")
    def test_handles_connection_error(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = requests.exceptions.ConnectionError()

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "test-key"}):
            urls = search_people("test", use_cache=False)

        assert urls == []

    def test_cache_hit_returns_cached(self, tmp_path: Path) -> None:
        # Write a cache file
        key = _cache_key("filmmaker San Diego", "San Diego, California, United States")
        cache_file = tmp_path / f"{key}.json"
        cache_file.write_text(json.dumps(SAMPLE_SERPAPI_RESPONSE))

        with patch("scrapers.google.CACHE_DIR", tmp_path):
            urls = search_people("filmmaker San Diego", use_cache=True)

        assert len(urls) >= 2


class TestTrackUsage:

    def test_increments_count(self, tmp_path: Path) -> None:
        usage_file = tmp_path / "usage.json"
        with patch("scrapers.google.CACHE_DIR", tmp_path), \
             patch("scrapers.google.USAGE_FILE", usage_file):
            _track_usage()
            _track_usage()

        usage = json.loads(usage_file.read_text())
        assert usage["count"] == 2

    def test_resets_on_new_month(self, tmp_path: Path) -> None:
        usage_file = tmp_path / "usage.json"
        usage_file.write_text(json.dumps({"month": "2025-01", "count": 50}))

        with patch("scrapers.google.CACHE_DIR", tmp_path), \
             patch("scrapers.google.USAGE_FILE", usage_file):
            _track_usage()

        usage = json.loads(usage_file.read_text())
        assert usage["count"] == 1  # Reset + 1
