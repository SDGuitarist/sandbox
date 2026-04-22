"""Tests for held leads query."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db, init_db
from models import query_held_leads


def _setup_db(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return db


def _insert_lead(db, name="Test", segment=None, confidence=None,
                 hook_quality=None):
    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO leads
               (name, profile_url, source, segment, segment_confidence, hook_quality)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, f"https://example.com/{name.lower()}", "test",
             segment, confidence, hook_quality),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_held_shows_low_confidence(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "LowConf", segment="writer", confidence=0.4, hook_quality=1)
    held = query_held_leads(db)
    reasons = {h["hold_reason"] for h in held if h["name"] == "LowConf"}
    assert "low_confidence" in reasons


def test_held_shows_no_hook(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "NoHook", segment="writer", confidence=0.9, hook_quality=0)
    held = query_held_leads(db)
    reasons = {h["hold_reason"] for h in held if h["name"] == "NoHook"}
    assert "no_hook" in reasons


def test_held_shows_low_quality_hook(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "BadHook", segment="writer", confidence=0.9, hook_quality=4)
    held = query_held_leads(db)
    reasons = {h["hold_reason"] for h in held if h["name"] == "BadHook"}
    assert "low_quality_hook" in reasons


def test_held_shows_unsupported_segment(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "Wellness", segment="wellness", confidence=0.9, hook_quality=1)
    held = query_held_leads(db)
    reasons = {h["hold_reason"] for h in held if h["name"] == "Wellness"}
    assert "unsupported_segment" in reasons


def test_held_excludes_good_leads(tmp_path):
    db = _setup_db(tmp_path)
    _insert_lead(db, "Good", segment="connector", confidence=0.9, hook_quality=1)
    held = query_held_leads(db)
    names = {h["name"] for h in held}
    assert "Good" not in names
