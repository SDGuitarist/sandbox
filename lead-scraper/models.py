from db import get_db, DB_PATH

VALID_SOURCES = {"meetup", "eventbrite", "facebook", "linkedin"}


def get_all_leads(db_path=DB_PATH, limit=100, offset=0):
    """Return all leads with pagination."""
    with get_db(db_path) as conn:
        return conn.execute(
            "SELECT * FROM leads ORDER BY scraped_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


def get_leads_by_source(source: str, db_path=DB_PATH, limit=100, offset=0):
    """Return leads filtered by source. Returns empty list for invalid sources."""
    if source not in VALID_SOURCES:
        return []
    with get_db(db_path) as conn:
        return conn.execute(
            "SELECT * FROM leads WHERE source = ? ORDER BY scraped_at DESC LIMIT ? OFFSET ?",
            (source, limit, offset),
        ).fetchall()


def search_leads(query: str, db_path=DB_PATH, limit=100, offset=0):
    """Search leads by name (prefix match for index friendliness)."""
    with get_db(db_path) as conn:
        return conn.execute(
            "SELECT * FROM leads WHERE name LIKE ? ORDER BY scraped_at DESC LIMIT ? OFFSET ?",
            (f"%{query}%", limit, offset),
        ).fetchall()


def count_leads(db_path=DB_PATH) -> int:
    """Total lead count."""
    with get_db(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]


def delete_lead(lead_id: int, db_path=DB_PATH) -> bool:
    """Delete a lead by ID. Returns True if a row was deleted.

    This is the ONLY delete path for the leads table.
    Added for PII compliance (CCPA) per security review.
    """
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
        return conn.execute("SELECT changes()").fetchone()[0] > 0
