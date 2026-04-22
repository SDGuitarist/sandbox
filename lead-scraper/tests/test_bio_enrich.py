"""Tests for enrich_from_bios selection logic and integration."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db
from enrich import (
    enrich_from_bios,
    _get_leads_for_bio_parsing,
    _get_leads_for_website_crawl,
    _get_leads_for_hunter,
    _merge_social_handles,
    _extract_domain,
    _split_name,
)


# --- Selection logic ---

def test_selects_missing_email(setup_db, insert_lead):
    insert_lead(setup_db, "a", bio="some bio", source="instagram")
    leads = _get_leads_for_bio_parsing(setup_db)
    assert len(leads) == 1


def test_selects_missing_phone(setup_db, insert_lead):
    insert_lead(setup_db, "a", bio="some bio", email="a@b.com", source="instagram")
    leads = _get_leads_for_bio_parsing(setup_db)
    assert len(leads) == 1


def test_selects_missing_social(setup_db, insert_lead):
    insert_lead(setup_db, "a", bio="some bio", email="a@b.com", phone="1234567890", source="instagram")
    leads = _get_leads_for_bio_parsing(setup_db)
    assert len(leads) == 1


def test_skips_complete_lead(setup_db, insert_lead):
    insert_lead(setup_db, "a", bio="some bio", email="a@b.com",
                phone="1234567890", social_handles='["instagram:x"]', source="instagram")
    leads = _get_leads_for_bio_parsing(setup_db)
    assert len(leads) == 0


def test_skips_no_bio(setup_db, insert_lead):
    insert_lead(setup_db, "a", source="instagram")
    leads = _get_leads_for_bio_parsing(setup_db)
    assert len(leads) == 0


# --- Integration ---

def test_enrich_does_not_overwrite_existing_email(setup_db, insert_lead):
    insert_lead(setup_db, "a", bio="email: new@new.com", email="original@keep.com", source="instagram")
    enrich_from_bios(db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute("SELECT email FROM leads WHERE name = 'a'").fetchone()
    assert row["email"] == "original@keep.com"


def test_social_handles_json_roundtrip(setup_db, insert_lead):
    insert_lead(setup_db, "a", bio="IG: @testuser", source="instagram")
    enrich_from_bios(db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT social_handles FROM leads WHERE name = 'a'"
        ).fetchone()
    handles = json.loads(row["social_handles"])
    assert isinstance(handles, list)
    assert "instagram:testuser" in handles


def test_social_handles_null_when_empty(setup_db, insert_lead):
    insert_lead(setup_db, "a", bio="no handles here just text", source="instagram")
    enrich_from_bios(db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT social_handles FROM leads WHERE name = 'a'"
        ).fetchone()
    assert row["social_handles"] is None


def test_bio_not_mutated(setup_db, insert_lead):
    original_bio = "Check out IG: @myhandle for more"
    insert_lead(setup_db, "a", bio=original_bio, source="instagram")
    enrich_from_bios(db_path=setup_db)
    with get_db(setup_db) as conn:
        row = conn.execute("SELECT bio FROM leads WHERE name = 'a'").fetchone()
    assert row["bio"] == original_bio


# --- Website crawl selection ---

def test_website_crawl_selects_no_email(setup_db, insert_lead):
    insert_lead(setup_db, "a", website="https://example.com", source="eventbrite")
    leads = _get_leads_for_website_crawl(setup_db)
    assert len(leads) == 1


def test_website_crawl_skips_with_email(setup_db, insert_lead):
    insert_lead(setup_db, "a", website="https://example.com", email="a@b.com", source="eventbrite")
    leads = _get_leads_for_website_crawl(setup_db)
    assert len(leads) == 0


def test_website_crawl_skips_no_website(setup_db, insert_lead):
    insert_lead(setup_db, "a", source="instagram")
    leads = _get_leads_for_website_crawl(setup_db)
    assert len(leads) == 0


# --- Social handle merging ---

def test_merge_handles_empty_existing():
    result = _merge_social_handles(None, ["instagram:user"])
    assert result == '["instagram:user"]'


def test_merge_handles_dedup():
    existing = '["instagram:user"]'
    result = _merge_social_handles(existing, ["instagram:user", "twitter:handle"])
    parsed = json.loads(result)
    assert parsed == ["instagram:user", "twitter:handle"]


def test_merge_handles_no_new():
    result = _merge_social_handles(None, [])
    assert result is None


# --- Domain extraction ---

def test_extract_domain_basic():
    assert _extract_domain("https://www.patcruzevents.com/about") == "patcruzevents.com"


def test_extract_domain_strips_www():
    assert _extract_domain("https://www.example.com") == "example.com"


def test_extract_domain_skips_instagram():
    assert _extract_domain("https://www.instagram.com/user") is None


def test_extract_domain_skips_eventbrite():
    assert _extract_domain("https://www.eventbrite.com/o/org-123") is None


def test_extract_domain_skips_facebook():
    assert _extract_domain("https://www.facebook.com/page") is None


def test_extract_domain_skips_linktree():
    assert _extract_domain("https://linktr.ee/user") is None


# --- Name splitting ---

def test_split_name_full():
    assert _split_name("John Doe") == ("John", "Doe")


def test_split_name_three_parts():
    assert _split_name("John Q Doe") == ("John", "Doe")


def test_split_name_single():
    assert _split_name("Madonna") == ("Madonna", None)


def test_split_name_empty():
    assert _split_name("") == (None, None)


# --- Hunter lead selection ---

def test_hunter_selects_with_website_no_email(setup_db, insert_lead):
    insert_lead(setup_db, "Pat Cruz", website="https://www.patcruzevents.com", source="eventbrite")
    leads = _get_leads_for_hunter(setup_db)
    assert len(leads) == 1
    assert leads[0]["domain"] == "patcruzevents.com"


def test_hunter_skips_platform_domains(setup_db, insert_lead):
    insert_lead(setup_db, "User", website="https://www.instagram.com/user", source="instagram")
    leads = _get_leads_for_hunter(setup_db)
    assert len(leads) == 0


def test_hunter_skips_with_email(setup_db, insert_lead):
    insert_lead(setup_db, "Pat", website="https://patcruz.com", email="pat@patcruz.com", source="eventbrite")
    leads = _get_leads_for_hunter(setup_db)
    assert len(leads) == 0
