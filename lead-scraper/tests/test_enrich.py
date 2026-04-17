"""Tests for enrich_parsers.py — HTML contact extraction. No network calls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_parsers import parse_profile_page

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_html(name):
    return (FIXTURES_DIR / name).read_text()


def test_parse_extracts_mailto_email():
    html = _load_html("enrich_website.html")
    info = parse_profile_page(html)
    assert "info@streetwear.com" in info.emails


def test_parse_extracts_text_email():
    """Emails in visible text (not mailto:) are also found."""
    html = _load_html("enrich_website.html")
    info = parse_profile_page(html)
    assert "hello@streetwear.com" in info.emails


def test_parse_extracts_phone():
    html = _load_html("enrich_website.html")
    info = parse_profile_page(html)
    assert any("4045551234" in p for p in info.phones)


def test_parse_extracts_social_links():
    html = _load_html("enrich_website.html")
    info = parse_profile_page(html)
    assert "instagram" in info.social_urls
    assert "twitter" in info.social_urls
    assert "linkedin" in info.social_urls
    assert "tiktok" in info.social_urls


def test_parse_skips_share_urls():
    """Facebook share links should not be counted as social profiles."""
    html = _load_html("enrich_website.html")
    info = parse_profile_page(html)
    # The facebook social_url should be from JSON-LD sameAs, not the sharer link
    assert "sharer" not in info.social_urls.get("facebook", "")


def test_parse_jsonld_sameas():
    """Schema.org sameAs provides social links even without <a> tags."""
    html = _load_html("enrich_website.html")
    info = parse_profile_page(html)
    # JSON-LD has instagram and facebook
    assert "instagram" in info.social_urls
    assert "facebook" in info.social_urls


def test_parse_empty_html():
    info = parse_profile_page("")
    assert info.emails == []
    assert info.phones == []
    assert info.social_urls == {}


def test_parse_no_contact_info():
    html = "<html><body><p>Hello world</p></body></html>"
    info = parse_profile_page(html)
    assert info.emails == []
    assert info.phones == []


def test_parse_rejects_image_emails():
    """Filenames like photo@2x.png should not be extracted as emails."""
    html = '<html><body><p>icon@2x.png and photo@3x.jpg</p></body></html>'
    info = parse_profile_page(html)
    assert len(info.emails) == 0
