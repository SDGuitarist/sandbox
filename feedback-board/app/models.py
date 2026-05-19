import sqlite3

VALID_CATEGORIES: tuple[str, ...] = ("Feature", "Bug", "Improvement", "Other")
VALID_STATUSES: tuple[str, ...] = ("new", "planned", "in_progress", "done")


def create_feedback(conn: sqlite3.Connection, title: str, description: str,
                    category: str, ip_address: str) -> int:
    """Insert new feedback. Returns the new feedback ID (int).
    Usage: feedback_id = create_feedback(conn, title, desc, category, ip)
    """
    cursor = conn.execute(
        "INSERT INTO feedback (title, description, category, ip_address) VALUES (?, ?, ?, ?)",
        (title, description, category, ip_address),
    )
    return cursor.lastrowid


def get_all_feedback(conn: sqlite3.Connection, status: str | None = None,
                     category: str | None = None) -> list[sqlite3.Row]:
    """Get feedback with optional filters. Public sort: vote_count DESC, created_at DESC."""
    query = "SELECT * FROM feedback WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY vote_count DESC, created_at DESC"
    return conn.execute(query, params).fetchall()


def get_all_feedback_admin(conn: sqlite3.Connection, status: str | None = None,
                           category: str | None = None) -> list[sqlite3.Row]:
    """Get feedback for admin view. Admin sort: created_at DESC."""
    query = "SELECT * FROM feedback WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY created_at DESC"
    return conn.execute(query, params).fetchall()


def get_feedback_by_id(conn: sqlite3.Connection, feedback_id: int) -> sqlite3.Row | None:
    """Get single feedback item. Returns Row or None."""
    return conn.execute(
        "SELECT * FROM feedback WHERE id = ?", (feedback_id,)
    ).fetchone()


def upvote_feedback(conn: sqlite3.Connection, feedback_id: int, ip_address: str) -> bool:
    """Atomic upvote with dedup. Returns True if vote was new, False if duplicate.
    MUST be called inside get_db(immediate=True) context."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO votes (feedback_id, ip_address) VALUES (?, ?)",
        (feedback_id, ip_address),
    )
    if cursor.rowcount == 0:
        return False
    conn.execute(
        "UPDATE feedback SET vote_count = vote_count + 1 WHERE id = ?",
        (feedback_id,),
    )
    return True


def update_feedback_status(conn: sqlite3.Connection, feedback_id: int,
                           new_status: str) -> bool:
    """Update feedback status and updated_at. Returns True if row existed."""
    cursor = conn.execute(
        "UPDATE feedback SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (new_status, feedback_id),
    )
    return cursor.rowcount > 0


def get_feedback_stats(conn: sqlite3.Connection) -> dict:
    """Get counts by status. Returns dict with total and per-status counts."""
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM feedback GROUP BY status"
    ).fetchall()
    stats = {"total": 0, "new": 0, "planned": 0, "in_progress": 0, "done": 0}
    for row in rows:
        status = row["status"]
        count = row["cnt"]
        if status in stats:
            stats[status] = count
        stats["total"] += count
    return stats
