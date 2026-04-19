"""Tests for enrich_parsers.py — HTML contact extraction. No network calls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enrich_parsers import parse_bio, parse_profile_page

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


def test_parse_empty_html():
    info = parse_profile_page("")
    assert info.emails == []
    assert info.phones == []


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


# --- Bio parsing: emails ---

def test_bio_extracts_email():
    info = parse_bio("Contact: booking@studio.com")
    assert "booking@studio.com" in info.emails


def test_bio_extracts_email_in_sentence():
    info = parse_bio("email me at hello@example.com for bookings")
    assert "hello@example.com" in info.emails


def test_bio_rejects_image_email():
    info = parse_bio("photo@2x.png")
    assert info.emails == []


def test_bio_empty_string():
    info = parse_bio("")
    assert info.emails == []
    assert info.phones == []
    assert info.social_handles == []


# --- Bio parsing: phones ---

def test_bio_extracts_phone_parens():
    info = parse_bio("Call (619) 555-1234")
    assert any("6195551234" in p for p in info.phones)


def test_bio_extracts_phone_dashes():
    info = parse_bio("Call 619-555-1234")
    assert any("6195551234" in p for p in info.phones)


def test_bio_extracts_phone_dots():
    info = parse_bio("Call 619.555.1234")
    assert any("6195551234" in p for p in info.phones)


def test_bio_rejects_short_numbers():
    info = parse_bio("#sandiegophotographer #12345")
    assert info.phones == []


# --- Bio parsing: social handles (keyword-prefix required) ---

def test_bio_ig_colon_handle():
    info = parse_bio("IG: @somename")
    assert "instagram:somename" in info.social_handles


def test_bio_instagram_space_handle():
    info = parse_bio("instagram @my_handle")
    assert "instagram:my_handle" in info.social_handles


def test_bio_insta_colon_handle():
    info = parse_bio("insta: coolperson")
    assert "instagram:coolperson" in info.social_handles


def test_bio_twitter_url():
    info = parse_bio("twitter.com/myhandle")
    assert "twitter:myhandle" in info.social_handles


def test_bio_x_url():
    info = parse_bio("x.com/myhandle")
    assert "twitter:myhandle" in info.social_handles


def test_bio_linkedin_url():
    info = parse_bio("linkedin.com/in/john-doe")
    assert "linkedin:in/john-doe" in info.social_handles


def test_bio_tiktok_handle():
    info = parse_bio("tiktok @dancer123")
    assert "tiktok:dancer123" in info.social_handles


def test_bio_youtube_url():
    info = parse_bio("youtube.com/@channelname")
    assert "youtube:channelname" in info.social_handles


# --- Bio parsing: false positives (MUST NOT match) ---

def test_bio_rejects_bare_at_everyone():
    info = parse_bio("@everyone come to the event")
    assert info.social_handles == []


def test_bio_rejects_bare_at_photo_credit():
    info = parse_bio("Photo by @americanportra")
    assert info.social_handles == []


def test_bio_rejects_bare_at_vendor():
    info = parse_bio("Vendor Team @westandmadisonevents")
    assert info.social_handles == []


def test_bio_rejects_hashtags():
    info = parse_bio("#SDCreatives #sandiegophotographer")
    assert info.social_handles == []


def test_bio_rejects_bare_at_admin():
    info = parse_bio("Contact @admin for help")
    assert info.social_handles == []
