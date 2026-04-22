from db import get_db, DB_PATH

VALID_SOURCES = {"meetup", "eventbrite", "facebook", "linkedin", "instagram", "csv_import"}


def query_leads(source="", q="", db_path=DB_PATH, limit=100, offset=0):
    """Return leads with composable filters. source and q can be combined."""
    clauses = []
    params = []

    if source and source in VALID_SOURCES:
        clauses.append("source = ?")
        params.append(source)

    if q:
        clauses.append("name LIKE ?")
        params.append(f"%{q}%")

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


def query_held_leads(db_path=DB_PATH) -> list[dict]:
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

    # Low confidence classification
    parts.append(
        "SELECT id, name, segment, segment_confidence, hook_quality, "
        "'low_confidence' as hold_reason "
        "FROM leads WHERE segment_confidence IS NOT NULL AND segment_confidence < 0.7"
    )

    # No hook found
    parts.append(
        "SELECT id, name, segment, segment_confidence, hook_quality, "
        "'no_hook' as hold_reason "
        "FROM leads WHERE hook_quality = 0"
    )

    # Low quality hook (tier 4-5)
    parts.append(
        "SELECT id, name, segment, segment_confidence, hook_quality, "
        "'low_quality_hook' as hold_reason "
        "FROM leads WHERE hook_quality >= 4"
    )

    # Unsupported segment (no template file)
    if available:
        parts.append(
            f"SELECT id, name, segment, segment_confidence, hook_quality, "
            f"'unsupported_segment' as hold_reason "
            f"FROM leads WHERE segment IS NOT NULL "
            f"AND segment NOT IN ({placeholders})"
        )
        params.extend(available)

    query = " UNION ALL ".join(parts) + " ORDER BY hold_reason, name"

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


def delete_lead(lead_id: int, db_path=DB_PATH) -> bool:
    """Delete a lead by ID. Returns True if a row was deleted.

    This is the ONLY delete path for the leads table.
    Added for PII compliance (CCPA) per security review.
    """
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        return conn.execute("SELECT changes()").fetchone()[0] > 0
