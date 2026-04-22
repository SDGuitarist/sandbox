"""Tests for campaign management."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db, init_db
from campaign import (
    create_campaign, assign_leads, generate_messages,
    show_queue, approve_message, skip_message, mark_sent, show_status,
    _fill_template, _available_segments, TEMPLATES_DIR,
)


def _setup_db(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    return db


def _insert_lead(db, name="Test", segment="connector", confidence=0.9,
                 hook_text="Gave a talk", hook_quality=1, hook_source_url="https://example.com"):
    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO leads
               (name, profile_url, source, segment, segment_confidence,
                hook_text, hook_quality, hook_source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, f"https://example.com/{name.lower()}", "test",
             segment, confidence, hook_text, hook_quality, hook_source_url),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_create_campaign(tmp_path):
    db = _setup_db(tmp_path)
    cid = create_campaign("Workshop", "connector,writer",
                          {"date": "April 25", "seat_count": "30"}, "2026-04-25", db)
    assert cid > 0
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (cid,)).fetchone()
    assert row["name"] == "Workshop"
    assert row["segment_filter"] == "connector,writer"
    assert json.loads(row["template_vars_json"]) == {"date": "April 25", "seat_count": "30"}


def test_assign_filters_by_segment_and_quality(tmp_path):
    db = _setup_db(tmp_path)
    lid1 = _insert_lead(db, "Good", segment="connector", hook_quality=1, confidence=0.9)
    lid2 = _insert_lead(db, "BadHook", segment="connector", hook_quality=4, confidence=0.9)
    lid3 = _insert_lead(db, "LowConf", segment="connector", hook_quality=1, confidence=0.5)
    lid4 = _insert_lead(db, "WrongSeg", segment="wellness", hook_quality=1, confidence=0.9)

    cid = create_campaign("Test", "connector", None, None, db)
    count = assign_leads(cid, min_hook_quality=3, db_path=db)

    with get_db(db) as conn:
        assigned = conn.execute(
            "SELECT lead_id FROM campaign_leads WHERE campaign_id = ?", (cid,)
        ).fetchall()
    assigned_ids = {r["lead_id"] for r in assigned}

    assert lid1 in assigned_ids  # good
    assert lid2 not in assigned_ids  # hook quality too low (4 > 3)
    assert lid3 not in assigned_ids  # confidence < 0.7
    assert lid4 not in assigned_ids  # wrong segment
    assert count == 1


def test_assign_derives_segments_from_templates(tmp_path):
    """Only segments with template files should be eligible."""
    db = _setup_db(tmp_path)
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


def test_generate_skips_existing_queue_row(tmp_path):
    """Re-running generate should not create duplicate queue entries."""
    db = _setup_db(tmp_path)
    lid = _insert_lead(db, "Alice", segment="connector")
    cid = create_campaign("Test", "connector",
                          {"date": "Apr 25", "seat_count": "30",
                           "format": "workshop", "event_name": "AI"}, None, db)
    assign_leads(cid, db_path=db)

    # Manually insert a queue row
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Existing message"),
        )

    # generate should find 0 leads (LEFT JOIN excludes existing queue rows)
    # No API call needed -- the query returns empty before the Anthropic import
    count = generate_messages(cid, db_path=db)
    assert count == 0


def test_queue_shows_hook_source_url(tmp_path, capsys):
    """Queue output should include hook_source_url for verification."""
    db = _setup_db(tmp_path)
    lid = _insert_lead(db, "Alice", hook_source_url="https://kpbs.org/article")
    cid = create_campaign("Test", "connector", None, None, db)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO campaign_leads (campaign_id, lead_id) VALUES (?, ?)",
            (cid, lid),
        )
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Test message"),
        )
    show_queue(cid, db_path=db)
    output = capsys.readouterr().out
    assert "https://kpbs.org/article" in output
    assert "Verify:" in output


def test_queue_shows_no_source_url_warning(tmp_path, capsys):
    """Queue should warn when hook_source_url is missing."""
    db = _setup_db(tmp_path)
    lid = _insert_lead(db, "Bob", hook_source_url=None)
    cid = create_campaign("Test", "connector", None, None, db)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO campaign_leads (campaign_id, lead_id) VALUES (?, ?)", (cid, lid)
        )
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Test message"),
        )
    show_queue(cid, db_path=db)
    output = capsys.readouterr().out
    assert "NO SOURCE URL" in output


def test_approve_atomic_claim(tmp_path):
    db = _setup_db(tmp_path)
    lid = _insert_lead(db, "Alice")
    cid = create_campaign("Test", None, None, None, db)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Message"),
        )
    result = approve_message(cid, lid, db_path=db)
    assert result is True
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT status, approved_at FROM outreach_queue WHERE lead_id = ? AND campaign_id = ?",
            (lid, cid),
        ).fetchone()
    assert row["status"] == "approved"
    assert row["approved_at"] is not None


def test_approve_already_approved(tmp_path):
    db = _setup_db(tmp_path)
    lid = _insert_lead(db, "Alice")
    cid = create_campaign("Test", None, None, None, db)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message, status) VALUES (?, ?, ?, 'approved')",
            (lid, cid, "Message"),
        )
    result = approve_message(cid, lid, db_path=db)
    assert result is False


def test_skip_message(tmp_path):
    db = _setup_db(tmp_path)
    lid = _insert_lead(db, "Alice")
    cid = create_campaign("Test", None, None, None, db)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Message"),
        )
    result = skip_message(cid, lid, db_path=db)
    assert result is True
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT status FROM outreach_queue WHERE lead_id = ?", (lid,)
        ).fetchone()
    assert row["status"] == "skipped"


def test_sent_requires_approved(tmp_path):
    """Cannot mark sent without first approving."""
    db = _setup_db(tmp_path)
    lid = _insert_lead(db, "Alice")
    cid = create_campaign("Test", None, None, None, db)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO outreach_queue (lead_id, campaign_id, full_message) VALUES (?, ?, ?)",
            (lid, cid, "Message"),
        )
    # Try to mark sent from draft -- should fail
    result = mark_sent(cid, lid, db_path=db)
    assert result is False

    # Approve first, then mark sent
    approve_message(cid, lid, db_path=db)
    result = mark_sent(cid, lid, db_path=db)
    assert result is True
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT status, sent_at FROM outreach_queue WHERE lead_id = ?", (lid,)
        ).fetchone()
    assert row["status"] == "sent"
    assert row["sent_at"] is not None


def test_status_shows_counts(tmp_path, capsys):
    db = _setup_db(tmp_path)
    cid = create_campaign("Workshop", "connector", None, "2026-04-25", db)
    lid1 = _insert_lead(db, "Alice")
    lid2 = _insert_lead(db, "Bob")
    with get_db(db) as conn:
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
    show_status(cid, db_path=db)
    output = capsys.readouterr().out
    assert "Workshop" in output
    assert "Leads assigned: 2" in output
    assert "Draft:    1" in output
    assert "Approved: 1" in output
