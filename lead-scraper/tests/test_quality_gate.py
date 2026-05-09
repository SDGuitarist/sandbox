"""Tests for quality gate: tier1 checks, URL classification, gate transitions."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db
from campaign import (
    create_campaign, gate_approve, gate_skip, gate_needs_review,
    force_approve, force_skip, requeue_lead,
)
from quality_gate import (
    classify_verify_url, tier1_checks, run_gate,
)


# ---------------------------------------------------------------------------
# classify_verify_url
# ---------------------------------------------------------------------------

def test_classify_missing_url():
    assert classify_verify_url(None) == "missing"
    assert classify_verify_url("") == "missing"


def test_classify_login_walled():
    assert classify_verify_url("https://www.instagram.com/p/ABC123") == "login_walled"
    assert classify_verify_url("https://www.facebook.com/events/123") == "login_walled"


def test_classify_public():
    assert classify_verify_url("https://kpbs.org/article/thing") == "public"
    assert classify_verify_url("https://sandiegouniontribune.com/art") == "public"


# ---------------------------------------------------------------------------
# tier1_checks
# ---------------------------------------------------------------------------

def test_tier1_detects_org_name():
    leads = [{"lead_id": 1, "name": "YMCA Productions", "profile_url": "https://facebook.com/ymca"}]
    results = tier1_checks(leads)
    assert 1 in results
    assert results[1][0] == "skip"
    assert "org_name" in results[1][1]


def test_tier1_detects_invalid_dm_route():
    leads = [{"lead_id": 2, "name": "John Smith", "profile_url": "https://eventbrite.com/john"}]
    results = tier1_checks(leads)
    assert 2 in results
    assert "invalid_dm_route" in results[2][1]


def test_tier1_detects_no_profile_url():
    leads = [{"lead_id": 3, "name": "Jane Doe", "profile_url": ""}]
    results = tier1_checks(leads)
    assert 3 in results
    assert "no_profile_url" in results[3][1]


def test_tier1_passes_good_lead():
    leads = [{"lead_id": 4, "name": "Alice Creator", "profile_url": "https://www.instagram.com/alice"}]
    results = tier1_checks(leads)
    assert 4 not in results


def test_tier1_dedup_by_profile_url():
    leads = [
        {"lead_id": 5, "name": "Alice", "profile_url": "https://www.instagram.com/alice"},
        {"lead_id": 6, "name": "Alice Copy", "profile_url": "https://www.instagram.com/alice"},
    ]
    results = tier1_checks(leads)
    assert 5 not in results  # First one passes
    assert 6 in results  # Duplicate skipped
    assert "duplicate" in results[6][1]


# ---------------------------------------------------------------------------
# Campaign gate transitions
# ---------------------------------------------------------------------------

def _make_draft(db, lead_id, campaign_id):
    """Insert a draft outreach_queue row."""
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) "
            "VALUES (?, ?, ?)",
            (lead_id, campaign_id, "Test message"),
        )


def test_gate_approve(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Alice")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)

    result = gate_approve(cid, lid, db_path=setup_db)
    assert result is True

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, gate_checked_at, approved_at FROM outreach_queue "
            "WHERE lead_id = ? AND campaign_id = ?", (lid, cid)
        ).fetchone()
    assert row["status"] == "approved"
    assert row["gate_checked_at"] is not None
    assert row["approved_at"] is not None


def test_gate_skip(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Bob")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)

    result = gate_skip(cid, lid, "org_name:productions", db_path=setup_db)
    assert result is True

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, skip_reason, gate_checked_at FROM outreach_queue "
            "WHERE lead_id = ? AND campaign_id = ?", (lid, cid)
        ).fetchone()
    assert row["status"] == "skipped"
    assert row["skip_reason"] == "org_name:productions"
    assert row["gate_checked_at"] is not None


def test_gate_needs_review(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Carol")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)

    result = gate_needs_review(cid, lid, "login_walled_auto_verified", db_path=setup_db)
    assert result is True

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, skip_reason FROM outreach_queue "
            "WHERE lead_id = ? AND campaign_id = ?", (lid, cid)
        ).fetchone()
    assert row["status"] == "needs_review"
    assert row["skip_reason"] == "login_walled_auto_verified"


def test_force_approve(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Dave")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)
    gate_needs_review(cid, lid, "some_reason", db_path=setup_db)

    result = force_approve(cid, lid, db_path=setup_db)
    assert result is True

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status FROM outreach_queue WHERE lead_id = ? AND campaign_id = ?",
            (lid, cid)
        ).fetchone()
    assert row["status"] == "approved"


def test_force_approve_fails_from_draft(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Eve")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)

    result = force_approve(cid, lid, db_path=setup_db)
    assert result is False  # Can't force-approve from draft


def test_force_skip(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Frank")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)
    gate_needs_review(cid, lid, "flagged", db_path=setup_db)

    result = force_skip(cid, lid, reason="wrong_person", db_path=setup_db)
    assert result is True

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, skip_reason FROM outreach_queue "
            "WHERE lead_id = ? AND campaign_id = ?", (lid, cid)
        ).fetchone()
    assert row["status"] == "skipped"
    assert row["skip_reason"] == "wrong_person"


def test_requeue_from_skipped(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Grace")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)
    gate_skip(cid, lid, "test_reason", db_path=setup_db)

    result = requeue_lead(cid, lid, db_path=setup_db)
    assert result is True

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, skip_reason, gate_checked_at FROM outreach_queue "
            "WHERE lead_id = ? AND campaign_id = ?", (lid, cid)
        ).fetchone()
    assert row["status"] == "draft"
    assert row["skip_reason"] is None
    assert row["gate_checked_at"] is None


def test_requeue_from_needs_review(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Hank")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)
    gate_needs_review(cid, lid, "unclear", db_path=setup_db)

    result = requeue_lead(cid, lid, db_path=setup_db)
    assert result is True

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status FROM outreach_queue WHERE lead_id = ? AND campaign_id = ?",
            (lid, cid)
        ).fetchone()
    assert row["status"] == "draft"


def test_requeue_fails_from_approved(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Ivy")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)
    gate_approve(cid, lid, db_path=setup_db)

    result = requeue_lead(cid, lid, db_path=setup_db)
    assert result is False  # Can't requeue from approved


# ---------------------------------------------------------------------------
# run_gate integration (mocked API)
# ---------------------------------------------------------------------------

def test_run_gate_no_drafts(setup_db, capsys):
    cid = create_campaign("Test", None, None, None, setup_db)
    run_gate(cid, db_path=setup_db)
    output = capsys.readouterr().out
    assert "No drafts to gate-check" in output


def test_run_gate_tier1_skips_org(setup_db, insert_lead, capsys):
    """Tier 1 should skip org names without calling API."""
    lid = insert_lead(setup_db, "YMCA Productions",
                      profile_url="https://www.facebook.com/ymca",
                      hook_text="Hosted event")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)

    run_gate(cid, db_path=setup_db)

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, skip_reason FROM outreach_queue "
            "WHERE lead_id = ? AND campaign_id = ?", (lid, cid)
        ).fetchone()
    assert row["status"] == "skipped"
    assert "org_name" in row["skip_reason"]


def test_run_gate_login_walled_goes_to_needs_review(setup_db, insert_lead, capsys):
    """Login-walled URLs should route to needs_review (default behavior)."""
    lid = insert_lead(setup_db, "Alice Creator",
                      profile_url="https://www.instagram.com/alice",
                      hook_text="Posted a reel",
                      hook_source_url="https://www.instagram.com/p/ABC123")
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)

    run_gate(cid, db_path=setup_db)

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, skip_reason FROM outreach_queue "
            "WHERE lead_id = ? AND campaign_id = ?", (lid, cid)
        ).fetchone()
    assert row["status"] == "needs_review"
    assert "login_walled" in row["skip_reason"]


def test_run_gate_missing_url_needs_review(setup_db, insert_lead, capsys):
    """Missing verify URL should route to needs_review."""
    lid = insert_lead(setup_db, "Bob Jones",
                      profile_url="https://www.facebook.com/bob",
                      hook_text="Gave a talk at SXSW",
                      hook_source_url=None)
    cid = create_campaign("Test", None, None, None, setup_db)
    _make_draft(setup_db, lid, cid)

    run_gate(cid, db_path=setup_db)

    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, skip_reason FROM outreach_queue "
            "WHERE lead_id = ? AND campaign_id = ?", (lid, cid)
        ).fetchone()
    assert row["status"] == "needs_review"
    assert "no_verify_url" in row["skip_reason"]
