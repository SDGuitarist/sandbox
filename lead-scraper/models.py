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


def delete_lead(lead_id: int, db_path=DB_PATH) -> bool:
    """Delete a lead by ID. Returns True if a row was deleted.

    This is the ONLY delete path for the leads table.
    Added for PII compliance (CCPA) per security review.
    """
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        return conn.execute("SELECT changes()").fetchone()[0] > 0
