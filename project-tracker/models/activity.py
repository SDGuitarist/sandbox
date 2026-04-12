"""Activity log model functions for the project tracker."""


def log_activity(db, entity_type, entity_id, action, description):
    """Write a single activity log entry.

    Args:
        db: sqlite3.Connection -- the CALLER'S connection (same transaction)
        entity_type: str -- 'task', 'category', or 'member'
        entity_id: int
        action: str -- 'created', 'updated', or 'deleted'
        description: str -- e.g. "Created task 'Fix login bug'"

    Returns: None
    """
    db.execute(
        'INSERT INTO activity_log (entity_type, entity_id, action, description) VALUES (?, ?, ?, ?)',
        (entity_type, entity_id, action, description)
    )


def get_recent_activity(db, limit=10):
    """Return the most recent activity log entries.

    Args:
        db: sqlite3.Connection
        limit: int -- maximum number of entries to return (default 10)

    Returns: list[sqlite3.Row] -- most recent activity entries
    """
    return db.execute(
        'SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?',
        (limit,)
    ).fetchall()
