"""Tests for enrich_from_bios selection logic and integration."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db, init_db
from enrich import enrich_from_bios, _get_leads_for_bio_parsing


def _setup_db(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return db


def _insert_lead(db, name, bio=None, profile_bio=None, email=None,
                 phone=None, social_handles=None, source="instagram"):
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO leads (name, bio, profile_bio, email, phone, "
            "social_handles, profile_url, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, bio, profile_bio, email, phone, social_handles,
             f"https://example.com/{name}", source),
        )


# --- Selection logic ---

def test_selects_missing_email(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "a", bio="some bio")
    leads = _get_leads_for_bio_parsing(db)
    assert len(leads) == 1


def test_selects_missing_phone(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "a", bio="some bio", email="a@b.com")
    leads = _get_leads_for_bio_parsing(db)
    assert len(leads) == 1


def test_selects_missing_social(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "a", bio="some bio", email="a@b.com", phone="1234567890")
    leads = _get_leads_for_bio_parsing(db)
    assert len(leads) == 1


def test_skips_complete_lead(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "a", bio="some bio", email="a@b.com",
                 phone="1234567890", social_handles='["instagram:x"]')
    leads = _get_leads_for_bio_parsing(db)
    assert len(leads) == 0


def test_skips_no_bio(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "a")
    leads = _get_leads_for_bio_parsing(db)
    assert len(leads) == 0


# --- Integration ---

def test_enrich_does_not_overwrite_existing_email(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "a", bio="email: new@new.com", email="original@keep.com")
    enrich_from_bios(db_path=db)
    with get_db(db) as conn:
        row = conn.execute("SELECT email FROM leads WHERE name = 'a'").fetchone()
    assert row["email"] == "original@keep.com"


def test_social_handles_json_roundtrip(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "a", bio="IG: @testuser")
    enrich_from_bios(db_path=db)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT social_handles FROM leads WHERE name = 'a'"
        ).fetchone()
    handles = json.loads(row["social_handles"])
    assert isinstance(handles, list)
    assert "instagram:testuser" in handles


def test_social_handles_null_when_empty(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "a", bio="no handles here just text")
    enrich_from_bios(db_path=db)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT social_handles FROM leads WHERE name = 'a'"
        ).fetchone()
    assert row["social_handles"] is None


def test_bio_not_mutated(tmp_path):
    db = _setup_db(tmp_path)
    original_bio = "Check out IG: @myhandle for more"
    _insert_lead(db, "a", bio=original_bio)
    enrich_from_bios(db_path=db)
    with get_db(db) as conn:
        row = conn.execute("SELECT bio FROM leads WHERE name = 'a'").fetchone()
    assert row["bio"] == original_bio
