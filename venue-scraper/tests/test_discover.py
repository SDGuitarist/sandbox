"""Tests for discover.py -- SerpAPI search and URL filtering."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from discover import _extract_urls, _is_directory_site, search_venues

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestIsDirectorySite:
    """Test directory/social site filtering."""

    def test_yelp_is_directory(self) -> None:
        assert _is_directory_site("https://www.yelp.com/biz/something") is True

    def test_facebook_is_directory(self) -> None:
        assert _is_directory_site("https://www.facebook.com/venue") is True

    def test_instagram_is_directory(self) -> None:
        assert _is_directory_site("https://instagram.com/venue") is True

    def test_real_venue_is_not_directory(self) -> None:
        assert _is_directory_site("https://www.sandiegofilmschool.com") is False

    def test_subdomain_of_directory(self) -> None:
        assert _is_directory_site("https://m.facebook.com/page") is True

    def test_empty_url_returns_false(self) -> None:
        assert _is_directory_site("") is False

    def test_malformed_url_returns_false(self) -> None:
        assert _is_directory_site("not-a-url") is False


class TestExtractUrls:
    """Test URL extraction from SerpAPI response fixture."""

    @pytest.fixture
    def serpapi_data(self) -> dict:
        fixture_path = FIXTURES_DIR / "serpapi_response.json"
        return json.loads(fixture_path.read_text())

    def test_filters_directory_sites(self, serpapi_data: dict) -> None:
        urls = _extract_urls(serpapi_data)
        # Yelp and Facebook should be filtered out
        for url in urls:
            assert "yelp.com" not in url
            assert "facebook.com" not in url

    def test_filters_non_http_schemes(self, serpapi_data: dict) -> None:
        urls = _extract_urls(serpapi_data)
        # FTP link should be filtered
        for url in urls:
            assert not url.startswith("ftp://")

    def test_deduplicates_by_domain(self, serpapi_data: dict) -> None:
        urls = _extract_urls(serpapi_data)
        # sandiegofilmschool.com appears twice but should only be in results once
        sd_film_urls = [u for u in urls if "sandiegofilmschool" in u]
        assert len(sd_film_urls) == 1

    def test_returns_expected_urls(self, serpapi_data: dict) -> None:
        urls = _extract_urls(serpapi_data)
        assert "https://www.sandiegofilmschool.com" in urls
        assert "https://pacarts.org" in urls
        assert "https://www.mediaartscenter.org" in urls
        assert "https://studiowest.com" in urls

    def test_empty_organic_results(self) -> None:
        urls = _extract_urls({"organic_results": []})
        assert urls == []

    def test_missing_organic_results_key(self) -> None:
        urls = _extract_urls({})
        assert urls == []


class TestSearchVenues:
    """Test search_venues with mocked HTTP responses."""

    @patch("discover.requests.get")
    def test_returns_urls_on_success(self, mock_get) -> None:
        fixture_path = FIXTURES_DIR / "serpapi_response.json"
        mock_response = type("Response", (), {
            "status_code": 200,
            "json": lambda self: json.loads(fixture_path.read_text()),
        })()
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "test_key"}):
            urls = search_venues("film school San Diego", use_cache=False)

        assert len(urls) > 0
        assert all(url.startswith("http") for url in urls)

    @patch("discover.requests.get")
    def test_returns_empty_on_429(self, mock_get) -> None:
        mock_response = type("Response", (), {"status_code": 429})()
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "test_key"}):
            urls = search_venues("test query", use_cache=False)

        assert urls == []

    @patch("discover.requests.get")
    def test_returns_empty_on_401(self, mock_get) -> None:
        mock_response = type("Response", (), {"status_code": 401})()
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "bad_key"}):
            urls = search_venues("test query", use_cache=False)

        assert urls == []

    def test_returns_empty_when_no_api_key(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            # Ensure SERPAPI_API_KEY is not set
            import os
            os.environ.pop("SERPAPI_API_KEY", None)
            urls = search_venues("test query", use_cache=False)

        assert urls == []

    @patch("discover.requests.get")
    def test_handles_timeout(self, mock_get) -> None:
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("timed out")

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "test_key"}):
            urls = search_venues("test query", use_cache=False)

        assert urls == []

    @patch("discover.requests.get")
    def test_handles_connection_error(self, mock_get) -> None:
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("no connection")

        with patch.dict("os.environ", {"SERPAPI_API_KEY": "test_key"}):
            urls = search_venues("test query", use_cache=False)

        assert urls == []
