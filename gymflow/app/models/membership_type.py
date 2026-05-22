import sqlite3


def create_membership_type(conn: sqlite3.Connection, name: str,
                           duration_months: int, price_cents: int,
                           description: str) -> int:
    """Create a membership type. Returns the new type ID.

    Args:
        conn: SQLite connection.
        name: Unique name for the membership type (e.g. 'Monthly').
        duration_months: Duration in months (e.g. 1, 6, 12).
        price_cents: Price stored as integer cents (e.g. 4999 = $49.99).
        description: Short description of the membership type.

    Returns:
        The auto-generated ID of the new membership type row.

    Commits: yes -- commits internally.
    """
    cursor = conn.execute(
        """INSERT INTO membership_types (name, duration_months, price_cents,
               description, is_active, created_at, updated_at)
           VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))""",
        (name, duration_months, price_cents, description),
    )
    conn.commit()
    return cursor.lastrowid


def get_membership_type(conn: sqlite3.Connection, type_id: int) -> sqlite3.Row | None:
    """Get a single membership type by ID.

    Returns a Row dict-like object, or None if not found.
    """
    return conn.execute(
        "SELECT * FROM membership_types WHERE id = ?", (type_id,)
    ).fetchone()


def get_all_membership_types(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all membership types ordered by name."""
    return conn.execute(
        "SELECT * FROM membership_types ORDER BY name"
    ).fetchall()


def get_active_membership_types(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get membership types where is_active = 1, ordered by name."""
    return conn.execute(
        "SELECT * FROM membership_types WHERE is_active = 1 ORDER BY name"
    ).fetchall()


def update_membership_type(conn: sqlite3.Connection, type_id: int, name: str,
                           duration_months: int, price_cents: int,
                           description: str, is_active: int) -> None:
    """Update an existing membership type.

    Args:
        conn: SQLite connection.
        type_id: ID of the membership type to update.
        name: New name.
        duration_months: New duration in months.
        price_cents: New price in cents.
        description: New description.
        is_active: 1 for active, 0 for inactive.

    Commits: yes -- commits internally.
    """
    conn.execute(
        """UPDATE membership_types
           SET name = ?, duration_months = ?, price_cents = ?,
               description = ?, is_active = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (name, duration_months, price_cents, description, is_active, type_id),
    )
    conn.commit()


def delete_membership_type(conn: sqlite3.Connection, type_id: int) -> None:
    """Delete a membership type by ID.

    The FK constraint on members.membership_type_id is ON DELETE SET NULL,
    so any members referencing this type will have their membership_type_id
    set to NULL automatically. No IntegrityError is raised.

    Commits: yes -- commits internally.
    """
    conn.execute("DELETE FROM membership_types WHERE id = ?", (type_id,))
    conn.commit()
