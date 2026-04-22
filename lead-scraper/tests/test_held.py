"""Tests for held leads query."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import query_held_leads


def test_held_shows_low_confidence(setup_db, insert_lead):
    insert_lead(setup_db, "LowConf", segment="writer", segment_confidence=0.4, hook_quality=1)
    held = query_held_leads(setup_db)
    reasons = {h["hold_reason"] for h in held if h["name"] == "LowConf"}
    assert "low_confidence" in reasons


def test_held_shows_no_hook(setup_db, insert_lead):
    insert_lead(setup_db, "NoHook", segment="writer", segment_confidence=0.9, hook_quality=0)
    held = query_held_leads(setup_db)
    reasons = {h["hold_reason"] for h in held if h["name"] == "NoHook"}
    assert "no_hook" in reasons


def test_held_shows_low_quality_hook(setup_db, insert_lead):
    insert_lead(setup_db, "BadHook", segment="writer", segment_confidence=0.9, hook_quality=4)
    held = query_held_leads(setup_db)
    reasons = {h["hold_reason"] for h in held if h["name"] == "BadHook"}
    assert "low_quality_hook" in reasons


def test_held_shows_unsupported_segment(setup_db, insert_lead):
    insert_lead(setup_db, "Wellness", segment="wellness", segment_confidence=0.9, hook_quality=1)
    held = query_held_leads(setup_db)
    reasons = {h["hold_reason"] for h in held if h["name"] == "Wellness"}
    assert "unsupported_segment" in reasons


def test_held_excludes_good_leads(setup_db, insert_lead):
    insert_lead(setup_db, "Good", segment="connector", segment_confidence=0.9, hook_quality=1)
    held = query_held_leads(setup_db)
    names = {h["name"] for h in held}
    assert "Good" not in names
