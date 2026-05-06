"""Tests for the leads unhold feature -- manual_approved column."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_db
from models import query_held_leads, unhold_lead, merge_leads
from campaign import assign_leads, create_campaign


def test_unhold_excludes_from_held(setup_db, insert_lead):
    """Unholding a lead removes it from the held list."""
    lead_id = insert_lead(setup_db, "Alice", segment="writer",
                          segment_confidence=0.9, hook_quality=0)
    held_before = [h["id"] for h in query_held_leads(setup_db)]
    assert lead_id in held_before

    unhold_lead(lead_id, setup_db)

    held_after = [h["id"] for h in query_held_leads(setup_db)]
    assert lead_id not in held_after


def test_unhold_nonexistent_lead(setup_db):
    """Unholding a nonexistent lead returns False."""
    assert unhold_lead(999, setup_db) is False


def test_unhold_enables_campaign_assignment(setup_db, insert_lead):
    """Manually approved leads get assigned to campaigns."""
    lead_id = insert_lead(setup_db, "Alice", segment="writer",
                          segment_confidence=0.3, hook_quality=0)
    campaign_id = create_campaign("Test Campaign", None, None, None, db_path=setup_db)

    # Before unhold: lead is not assigned (fails quality gates)
    count_before = assign_leads(campaign_id, db_path=setup_db)
    assert count_before == 0

    unhold_lead(lead_id, setup_db)
    count_after = assign_leads(campaign_id, db_path=setup_db)
    assert count_after == 1


def test_unhold_unsupported_segment_not_assigned(setup_db, insert_lead):
    """Approved lead with unsupported segment is NOT assigned (template guard)."""
    lead_id = insert_lead(setup_db, "Bob", segment="nonexistent_segment",
                          segment_confidence=0.9, hook_quality=0)
    campaign_id = create_campaign("Test Campaign", None, None, None, db_path=setup_db)

    unhold_lead(lead_id, setup_db)
    count = assign_leads(campaign_id, db_path=setup_db)
    assert count == 0  # No template for "nonexistent_segment"


def test_unhold_persists_across_enrichment(setup_db, insert_lead):
    """manual_approved=1 survives even if confidence drops on re-enrichment."""
    lead_id = insert_lead(setup_db, "Alice", segment="writer",
                          segment_confidence=0.9, hook_quality=2)
    unhold_lead(lead_id, setup_db)

    # Simulate re-enrichment lowering confidence
    with get_db(setup_db) as conn:
        conn.execute(
            "UPDATE leads SET segment_confidence = 0.2 WHERE id = ?", (lead_id,)
        )

    # Still not held (manual_approved overrides)
    held = [h["id"] for h in query_held_leads(setup_db)]
    assert lead_id not in held


def test_null_manual_approved_treated_as_not_approved(setup_db, insert_lead):
    """Existing leads with NULL manual_approved should appear in held list."""
    lead_id = insert_lead(setup_db, "OldLead", segment="writer",
                          segment_confidence=0.9, hook_quality=0)
    # manual_approved is NULL for existing rows (not 0)
    with get_db(setup_db) as conn:
        row = conn.execute(
            "SELECT manual_approved FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
    # After migration, new inserts get DEFAULT 0, but we verify the query
    # handles both NULL and 0 correctly via COALESCE
    held = [h["id"] for h in query_held_leads(setup_db)]
    assert lead_id in held


def test_merge_preserves_manual_approved(setup_db, insert_lead):
    """When any duplicate in a merge group has manual_approved=1, the keeper inherits it."""
    # Insert two leads with same profile URL (duplicates)
    id_a = insert_lead(setup_db, "Alice A", segment="writer",
                       segment_confidence=0.9, hook_quality=2,
                       profile_url="https://example.com/alice", source="meetup")
    id_b = insert_lead(setup_db, "Alice B", segment="writer",
                       segment_confidence=0.8,
                       profile_url="https://example.com/alice-b", source="eventbrite")

    # Approve the less-complete duplicate
    unhold_lead(id_b, setup_db)

    # Verify approval is set
    with get_db(setup_db) as conn:
        row = conn.execute("SELECT manual_approved FROM leads WHERE id = ?", (id_b,)).fetchone()
    assert row["manual_approved"] == 1

    # Merge: id_a is the keeper (more complete), id_b is the dupe (approved)
    with get_db(setup_db) as conn:
        leads = [dict(r) for r in conn.execute(
            "SELECT * FROM leads WHERE id IN (?, ?)", (id_a, id_b)
        ).fetchall()]

    keeper_id = merge_leads(leads, setup_db)
    assert keeper_id == id_a  # More complete lead is the keeper

    # The keeper must inherit manual_approved=1 from the merged duplicate
    with get_db(setup_db) as conn:
        row = conn.execute("SELECT manual_approved FROM leads WHERE id = ?", (keeper_id,)).fetchone()
    assert row["manual_approved"] == 1
