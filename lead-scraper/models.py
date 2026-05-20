from pathlib import Path

from db import get_db, DB_PATH

VALID_SOURCES = {"meetup", "eventbrite", "facebook", "linkedin", "instagram", "csv_import", "venue_scraper", "google"}


def query_leads(source="", q="", db_path=DB_PATH, limit=100, offset=0):
    """Return leads with composable filters. source and q can be combined."""
    clauses = []
    params = []

    if source and source in VALID_SOURCES:
        clauses.append("source = ?")
        params.append(source)

    if q:
        clauses.append(
            "(name LIKE ? OR bio LIKE ? OR location LIKE ? "
            "OR email LIKE ? OR hook_text LIKE ?)"
        )
        params.extend([f"%{q}%"] * 5)

    where = " AND ".join(clauses)
    where_sql = f"WHERE {where}" if where else ""

    with get_db(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM leads {where_sql} ORDER BY scraped_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        count = conn.execute(
            f"SELECT COUNT(*) FROM leads {where_sql}",
            params,
        ).fetchone()[0]

    return rows, count


def query_held_leads(db_path: Path = DB_PATH) -> list[dict]:
    """Return leads held from auto-generation with labeled reasons.

    Hold reasons: low_confidence, no_hook, low_quality_hook, unsupported_segment.
    Computed at query time -- no new table needed.
    """
    from config import available_segments as _available_segments

    available = _available_segments()
    if not available:
        available = []

    placeholders = ",".join("?" for _ in available)

    # Build UNION ALL query for all hold conditions
    parts = []
    params: list = []

    # Each UNION part excludes manually approved leads (COALESCE handles NULL)
    approved_filter = "AND COALESCE(manual_approved, 0) = 0"

    # Low confidence classification
    parts.append(
        "SELECT id, name, segment, segment_confidence, hook_quality, "
        "'low_confidence' as hold_reason "
        f"FROM leads WHERE segment_confidence IS NOT NULL AND segment_confidence < 0.7 {approved_filter}"
    )

    # No hook found
    parts.append(
        "SELECT id, name, segment, segment_confidence, hook_quality, "
        "'no_hook' as hold_reason "
        f"FROM leads WHERE hook_quality = 0 {approved_filter}"
    )

    # Low quality hook (tier 4-5)
    parts.append(
        "SELECT id, name, segment, segment_confidence, hook_quality, "
        "'low_quality_hook' as hold_reason "
        f"FROM leads WHERE hook_quality >= 4 {approved_filter}"
    )

    # Unsupported segment (no template file)
    if available:
        parts.append(
            f"SELECT id, name, segment, segment_confidence, hook_quality, "
            f"'unsupported_segment' as hold_reason "
            f"FROM leads WHERE segment IS NOT NULL "
            f"AND segment NOT IN ({placeholders}) {approved_filter}"
        )
        params.extend(available)

    query = " UNION ALL ".join(parts) + " ORDER BY hold_reason, name"

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


def find_duplicates(db_path=DB_PATH) -> list[list[dict]]:
    """Find duplicate leads by exact email or name match (case-insensitive).

    Returns a list of groups, where each group is a list of duplicate lead dicts.
    """
    groups = []
    seen_ids: set[int] = set()

    with get_db(db_path) as conn:
        # Email duplicates (most reliable signal)
        email_groups = conn.execute(
            "SELECT LOWER(email) as match_key, GROUP_CONCAT(id) as ids "
            "FROM leads WHERE email IS NOT NULL "
            "GROUP BY LOWER(email) HAVING COUNT(*) > 1"
        ).fetchall()

        for row in email_groups:
            ids = [int(x) for x in row["ids"].split(",")]
            leads = []
            for lid in ids:
                lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lid,)).fetchone()
                if lead:
                    leads.append(dict(lead))
                    seen_ids.add(lid)
            if len(leads) > 1:
                groups.append(leads)

        # Name duplicates (only for leads not already matched by email)
        name_groups = conn.execute(
            "SELECT LOWER(TRIM(name)) as match_key, GROUP_CONCAT(id) as ids "
            "FROM leads WHERE email IS NULL "
            "GROUP BY LOWER(TRIM(name)) HAVING COUNT(*) > 1"
        ).fetchall()

        for row in name_groups:
            ids = [int(x) for x in row["ids"].split(",") if int(x) not in seen_ids]
            if len(ids) < 2:
                continue
            leads = []
            for lid in ids:
                lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lid,)).fetchone()
                if lead:
                    leads.append(dict(lead))
            if len(leads) > 1:
                groups.append(leads)

    return groups


def merge_leads(group: list[dict], db_path=DB_PATH) -> int:
    """Merge a group of duplicate leads. Keeps the most complete lead.

    Fills missing fields from duplicates, then deletes the dupes.
    Campaign assignments for deleted leads are cascade-deleted.
    Returns the ID of the surviving lead.
    """
    def completeness(lead):
        return sum(1 for v in lead.values() if v is not None)

    sorted_leads = sorted(group, key=completeness, reverse=True)
    keeper = sorted_leads[0]
    dupes = sorted_leads[1:]

    fill_fields = [
        "bio", "location", "email", "phone", "website", "social_handles",
        "profile_bio", "segment", "segment_confidence", "hook_text",
        "hook_source_url", "hook_quality", "activity",
    ]

    updates = {}
    for field in fill_fields:
        if keeper.get(field) is None:
            for dupe in dupes:
                if dupe.get(field) is not None:
                    updates[field] = dupe[field]
                    break

    # Preserve manual_approved if ANY duplicate was approved (OR/MAX semantics)
    if any(d.get("manual_approved") == 1 for d in group):
        updates["manual_approved"] = 1

    with get_db(db_path) as conn:
        if updates:
            set_parts = [f"{k} = ?" for k in updates]
            values = list(updates.values()) + [keeper["id"]]
            conn.execute(
                f"UPDATE leads SET {', '.join(set_parts)} WHERE id = ?",
                values,
            )

        for dupe in dupes:
            conn.execute("DELETE FROM leads WHERE id = ?", (dupe["id"],))

    return keeper["id"]


def readiness_score(lead: dict) -> int:
    """Compute a 0-100 readiness score for outreach.

    Scoring:
      +30 has email
      +10 has phone
      +5  has social handles
      +10 has segment
      +20 segment_confidence (scaled: confidence * 20)
      +25 hook quality (tier 1=25, 2=20, 3=15, 4=5, 5=2)
    """
    score = 0
    if lead.get("email"):
        score += 30
    if lead.get("phone"):
        score += 10
    if lead.get("social_handles"):
        score += 5
    if lead.get("segment"):
        score += 10
    conf = lead.get("segment_confidence") or 0
    score += int(conf * 20)
    hook_q = lead.get("hook_quality") or 0
    hook_points = {1: 25, 2: 20, 3: 15, 4: 5, 5: 2}.get(hook_q, 0)
    score += hook_points
    return min(score, 100)


def query_leads_scored(source="", q="", db_path=DB_PATH, limit=100, offset=0):
    """Like query_leads but returns dicts with readiness_score attached, sorted by score."""
    leads, total = query_leads(source=source, q=q, db_path=db_path, limit=limit, offset=offset)
    scored = []
    for lead in leads:
        d = dict(lead)
        d["score"] = readiness_score(d)
        scored.append(d)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored, total


def unhold_lead(lead_id: int, db_path: Path = DB_PATH) -> bool:
    """Set manual_approved=1 for a lead. Returns True if lead existed.

    Administrative override -- bypasses computed hold reasons so the lead
    becomes eligible for campaign assignment. models.py owns admin/status
    writes (delete_lead, unhold_lead) distinct from enrichment columns.
    """
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE leads SET manual_approved = 1 WHERE id = ?", (lead_id,)
        )
        return conn.execute("SELECT changes()").fetchone()[0] > 0


def delete_lead(lead_id: int, db_path=DB_PATH) -> bool:
    """Delete a lead by ID. Returns True if a row was deleted.

    This is the ONLY delete path for the leads table.
    Added for PII compliance (CCPA) per security review.
    """
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        return conn.execute("SELECT changes()").fetchone()[0] > 0


def delete_source(source_name: str, db_path=DB_PATH, dry_run: bool = False) -> dict:
    """Delete all leads from a given source.

    Refuses to delete leads with sent/replied/booked/declined outreach
    (those represent real-world actions that cannot be undone).

    Returns dict with counts: total, protected, deleted, campaign_leads, queue_entries.
    """
    with get_db(db_path) as conn:
        # Find all leads for this source
        leads = conn.execute(
            "SELECT id, name FROM leads WHERE source = ?", (source_name,)
        ).fetchall()

        if not leads:
            return {"total": 0, "protected": 0, "deleted": 0, "campaign_leads": 0, "queue_entries": 0}

        lead_ids = [row["id"] for row in leads]
        placeholders = ",".join("?" * len(lead_ids))

        # Check for protected leads (sent/replied/booked/declined outreach)
        protected_rows = conn.execute(
            f"""SELECT DISTINCT l.id, l.name, oq.status as queue_status
            FROM leads l
            JOIN outreach_queue oq ON l.id = oq.lead_id
            WHERE l.id IN ({placeholders})
            AND oq.status IN ('sent', 'replied', 'booked', 'declined')
            """,
            lead_ids,
        ).fetchall()
        protected_ids = {row["id"] for row in protected_rows}

        # Count associated records that will cascade-delete
        campaign_lead_count = conn.execute(
            f"SELECT COUNT(*) FROM campaign_leads WHERE lead_id IN ({placeholders})",
            lead_ids,
        ).fetchone()[0]

        queue_count = conn.execute(
            f"SELECT COUNT(*) FROM outreach_queue WHERE lead_id IN ({placeholders})",
            lead_ids,
        ).fetchone()[0]

        deletable_ids = [lid for lid in lead_ids if lid not in protected_ids]

        if dry_run:
            return {
                "total": len(leads),
                "protected": len(protected_ids),
                "deleted": len(deletable_ids),
                "campaign_leads": campaign_lead_count,
                "queue_entries": queue_count,
            }

        # Delete non-protected leads
        if deletable_ids:
            del_placeholders = ",".join("?" * len(deletable_ids))
            conn.execute(
                f"DELETE FROM leads WHERE id IN ({del_placeholders})",
                deletable_ids,
            )

        return {
            "total": len(leads),
            "protected": len(protected_ids),
            "deleted": len(deletable_ids),
            "campaign_leads": campaign_lead_count,
            "queue_entries": queue_count,
        }
