"""Tests for crawler.py link-based discovery and SSRF protection."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler import _is_same_origin, discover_subpages_from_links

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestIsSameOrigin:
    """Test SSRF protection via same-origin validation."""

    def test_same_origin_passes(self) -> None:
        assert _is_same_origin("https://example.com", "https://example.com/contact") is True

    def test_different_hostname_rejected(self) -> None:
        assert _is_same_origin("https://example.com", "https://evil.com/contact") is False

    def test_file_scheme_rejected(self) -> None:
        assert _is_same_origin("https://example.com", "file:///etc/passwd") is False

    def test_ftp_scheme_rejected(self) -> None:
        assert _is_same_origin("https://example.com", "ftp://example.com/data") is False

    def test_javascript_scheme_rejected(self) -> None:
        assert _is_same_origin("https://example.com", "javascript:alert(1)") is False

    def test_different_port_rejected(self) -> None:
        # Different port = different netloc
        assert _is_same_origin("https://example.com", "https://example.com:8080/page") is False

    def test_http_vs_https_same_host_passes(self) -> None:
        # Same netloc, different scheme (both http/https) -- passes scheme check
        assert _is_same_origin("https://example.com", "http://example.com/page") is True

    def test_subdomain_rejected(self) -> None:
        # Subdomain has different netloc
        assert _is_same_origin("https://example.com", "https://sub.example.com/page") is False


class TestDiscoverSubpagesFromLinks:
    """Test link-based subpage discovery."""

    @pytest.fixture
    def internal_links(self) -> list[dict]:
        fixture_path = FIXTURES_DIR / "internal_links.json"
        return json.loads(fixture_path.read_text())

    def test_finds_contact_and_about(self, internal_links: list[dict]) -> None:
        base_url = "https://example-studio.com"
        result = discover_subpages_from_links(base_url, internal_links)

        # Should find Contact Us (contact keyword) and About Our Studio (about keyword)
        assert len(result) <= 2
        assert any("/contact" in url for url in result)
        assert any("/about" in url for url in result)

    def test_rejects_external_links(self, internal_links: list[dict]) -> None:
        base_url = "https://example-studio.com"
        result = discover_subpages_from_links(base_url, internal_links)

        # evil.com link should never appear
        for url in result:
            assert "evil.com" not in url

    def test_max_two_subpages(self, internal_links: list[dict]) -> None:
        base_url = "https://example-studio.com"
        result = discover_subpages_from_links(base_url, internal_links)
        assert len(result) <= 2

    def test_empty_links_uses_fallback(self) -> None:
        base_url = "https://example.com"
        result = discover_subpages_from_links(base_url, [])

        # Should fall back to hardcoded /contact and /about
        assert "https://example.com/contact" in result
        assert "https://example.com/about" in result

    def test_additive_fallback_fills_to_cap(self) -> None:
        """When only one link found, fallback adds second up to cap."""
        base_url = "https://example.com"
        # Only has a contact link, no about link
        links = [{"href": "/reach-us", "text": "Contact our team"}]
        result = discover_subpages_from_links(base_url, links)

        # Should have the contact link plus one fallback path
        assert len(result) == 2
        assert "https://example.com/reach-us" in result

    def test_no_fallback_when_cap_reached(self) -> None:
        """When 2 links found via keywords, no hardcoded paths added."""
        base_url = "https://example.com"
        links = [
            {"href": "/get-in-touch", "text": "Get in Touch"},
            {"href": "/our-team", "text": "About the Team"},
        ]
        result = discover_subpages_from_links(base_url, links)

        assert len(result) == 2
        assert "https://example.com/get-in-touch" in result
        assert "https://example.com/our-team" in result
        # Hardcoded paths should NOT be present since cap is reached
        assert "https://example.com/contact" not in result

    def test_skips_links_with_empty_text(self) -> None:
        base_url = "https://example.com"
        links = [
            {"href": "/gallery", "text": ""},
            {"href": "/contact", "text": "Contact Us"},
        ]
        result = discover_subpages_from_links(base_url, links)
        assert any("/contact" in url for url in result)

    def test_skips_links_with_empty_href(self) -> None:
        base_url = "https://example.com"
        links = [
            {"href": "", "text": "Contact Us"},
            {"href": "/about", "text": "About"},
        ]
        result = discover_subpages_from_links(base_url, links)
        # Empty href should be skipped, about should be found
        assert any("/about" in url for url in result)

    def test_does_not_include_base_url(self) -> None:
        base_url = "https://example.com"
        links = [{"href": "/contact", "text": "Contact Us"}]
        result = discover_subpages_from_links(base_url, links)

        # base_url itself should not be in the result list
        assert base_url not in result
