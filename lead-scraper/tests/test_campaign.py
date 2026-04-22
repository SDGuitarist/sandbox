"""Tests for campaign management."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db
from campaign import (
    create_campaign, assign_leads, generate_messages,
    show_queue, approve_message, skip_message, mark_sent, show_status,
    _fill_template, _available_segments,
)
from config import TEMPLATES_DIR


def test_create_campaign(setup_db):
    cid = create_campaign("Workshop", "connector,writer",
                          {"date": "April 25", "seat_count": "30"}, "2026-04-25", setup_db)
    assert cid > 0
    with get_db(setup_db) as conn:
        row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (cid,)).fetchone()
    assert row["name"] == "Workshop"
    assert row["segment_filter"] == "connector,writer"
    assert json.loads(row["template_vars_json"]) == {"date": "April 25", "seat_count": "30"}


def test_assign_filters_by_segment_and_quality(setup_db, insert_lead):
    lid1 = insert_lead(setup_db, "Good", segment="connector", hook_quality=1, segment_confidence=0.9)
    lid2 = insert_lead(setup_db, "BadHook", segment="connector", hook_quality=4, segment_confidence=0.9)
    lid3 = insert_lead(setup_db, "LowConf", segment="connector", hook_quality=1, segment_confidence=0.5)
    lid4 = insert_lead(setup_db, "WrongSeg", segment="wellness", hook_quality=1, segment_confidence=0.9)

    cid = create_campaign("Test", "connector", None, None, setup_db)
    count = assign_leads(cid, min_hook_quality=3, db_path=setup_db)

    with get_db(setup_db) as conn:
        assigned = conn.execute(
            "SELECT lead_id FROM campaign_leads WHERE campaign_id = ?", (cid,)
        ).fetchall()
    assigned_ids = {r["lead_id"] for r in assigned}

    assert lid1 in assigned_ids  # good
    assert lid2 not in assigned_ids  # hook quality too low (4 > 3)
    assert lid3 not in assigned_ids  # confidence < 0.7
    assert lid4 not in assigned_ids  # wrong segment
    assert count == 1


def test_assign_derives_segments_from_templates(setup_db):
    """Only segments with template files should be eligible."""
    available = _available_segments()
    # connector.md should exist
    assert "connector" in available
    # wellness.md should NOT exist (removed in Phase 1)
    assert "wellness" not in available


def test_fill_template_replaces_variables():
    body = "Event on {{date}} with {{seat_count}} seats."
    result = _fill_template(body, {"date": "April 25", "seat_count": "30"})
    assert result == "Event on April 25 with 30 seats."


def test_fill_template_errors_on_missing_variable():
    body = "Event on {{date}} at {{venue}}."
    try:
        _fill_template(body, {"date": "April 25"})
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "venue" in str(e)


def test_generate_skips_existing_queue_row(setup_db, insert_lead):
    """Re-running generate should not create duplicate queue entries."""
    lid = insert_lead(setup_db, "Alice", segment="connector", segment_confidence=0.9,
                      hook_text="Gave a talk", hook_quality=1)
    cid = create_campaign("Test", "connector",
                          {"date": "Apr 25", "seat_count": "30",
                           "format": "workshop", "event_name": "AI"}, None, setup_db)
    assign_leads(cid, db_path=setup_db)

    # Manually insert a queue row
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Existing message"),
        )

    # generate should find 0 leads (LEFT JOIN excludes existing queue rows)
    # No API call needed -- the query returns empty before the Anthropic import
    count = generate_messages(cid, db_path=setup_db)
    assert count == 0


def test_queue_shows_hook_source_url(setup_db, insert_lead, capsys):
    """Queue output should include hook_source_url for verification."""
    lid = insert_lead(setup_db, "Alice", hook_source_url="https://kpbs.org/article")
    cid = create_campaign("Test", "connector", None, None, setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO campaign_leads (campaign_id, lead_id) VALUES (?, ?)",
            (cid, lid),
        )
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Test message"),
        )
    show_queue(cid, db_path=setup_db)
    output = capsys.readouterr().out
    assert "https://kpbs.org/article" in output
    assert "Verify:" in output


def test_queue_shows_no_source_url_warning(setup_db, insert_lead, capsys):
    """Queue should warn when hook_source_url is missing."""
    lid = insert_lead(setup_db, "Bob", hook_source_url=None)
    cid = create_campaign("Test", "connector", None, None, setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO campaign_leads (campaign_id, lead_id) VALUES (?, ?)", (cid, lid)
        )
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Test message"),
        )
    show_queue(cid, db_path=setup_db)
    output = capsys.readouterr().out
    assert "NO SOURCE URL" in output


def test_approve_atomic_claim(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Alice")
    cid = create_campaign("Test", None, None, None, setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Message"),
        )
    result = approve_message(cid, lid, db_path=setup_db)
    assert result is True
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, approved_at FROM outreach_queue WHERE lead_id = ? AND campaign_id = ?",
            (lid, cid),
        ).fetchone()
    assert row["status"] == "approved"
    assert row["approved_at"] is not None


def test_approve_already_approved(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Alice")
    cid = create_campaign("Test", None, None, None, setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message, status) VALUES (?, ?, ?, 'approved')",
            (lid, cid, "Message"),
        )
    result = approve_message(cid, lid, db_path=setup_db)
    assert result is False


def test_skip_message(setup_db, insert_lead):
    lid = insert_lead(setup_db, "Alice")
    cid = create_campaign("Test", None, None, None, setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Message"),
        )
    result = skip_message(cid, lid, db_path=setup_db)
    assert result is True
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status FROM outreach_queue WHERE lead_id = ?", (lid,)
        ).fetchone()
    assert row["status"] == "skipped"


def test_sent_requires_approved(setup_db, insert_lead):
    """Cannot mark sent without first approving."""
    lid = insert_lead(setup_db, "Alice")
    cid = create_campaign("Test", None, None, None, setup_db)
    with get_db(setup_db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Message"),
        )
    # Try to mark sent from draft -- should fail
    result = mark_sent(cid, lid, db_path=setup_db)
    assert result is False

    # Approve first, then mark sent
    approve_message(cid, lid, db_path=setup_db)
    result = mark_sent(cid, lid, db_path=setup_db)
    assert result is True
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT status, sent_at FROM outreach_queue WHERE lead_id = ?", (lid,)
        ).fetchone()
    assert row["status"] == "sent"
    assert row["sent_at"] is not None


def test_status_shows_counts(setup_db, insert_lead, capsys):
    cid = create_campaign("Workshop", "connector", None, "2026-04-25", setup_db)
    lid1 = insert_lead(setup_db, "Alice")
    lid2 = insert_lead(setup_db, "Bob")
    with get_db(setup_db) as conn:
        conn.execute("INSERT INTO campaign_leads (campaign_id, lead_id) VALUES (?, ?)", (cid, lid1))
        conn.execute("INSERT INTO campaign_leads (campaign_id, lead_id) VALUES (?, ?)", (cid, lid2))
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message, status) VALUES (?, ?, ?, 'draft')",
            (lid1, cid, "Msg1"),
        )
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message, status) VALUES (?, ?, ?, 'approved')",
            (lid2, cid, "Msg2"),
        )
    show_status(cid, db_path=setup_db)
    output = capsys.readouterr().out
    assert "Workshop" in output
    assert "Leads assigned: 2" in output
    assert "Draft:    1" in output
    assert "Approved: 1" in output
