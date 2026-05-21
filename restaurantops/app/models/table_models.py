"""Table CRUD and status management functions.

All functions take a sqlite3.Connection and do NOT commit.
The caller (route) is responsible for BEGIN/COMMIT.
"""

import sqlite3
from datetime import datetime

ALLOWED_STATUSES = ('available', 'reserved', 'occupied', 'needs_cleaning')


def create_table(conn: sqlite3.Connection, table_number: str,
                 capacity: int, zone: str) -> int:
    """Create a new table and return its ID.

    Args:
        conn: Database connection (caller manages transaction).
        table_number: Unique table identifier (e.g. "T1", "Patio-3").
        capacity: Number of seats.
        zone: Dining zone (e.g. "main", "patio", "bar").

    Returns:
        int: The new table's row ID.
    """
    cursor = conn.execute(
        "INSERT INTO tables (table_number, capacity, zone) VALUES (?, ?, ?)",
        (table_number, capacity, zone),
    )
    return cursor.lastrowid


def get_all_tables(conn: sqlite3.Connection) -> list:
    """Return all tables ordered by table_number.

    Returns:
        list[sqlite3.Row]: All table rows.
    """
    return conn.execute(
        "SELECT * FROM tables ORDER BY table_number"
    ).fetchall()


def get_table(conn: sqlite3.Connection, table_id: int):
    """Return a single table by ID, or None if not found.

    Args:
        conn: Database connection.
        table_id: Primary key of the table.

    Returns:
        sqlite3.Row or None
    """
    return conn.execute(
        "SELECT * FROM tables WHERE id = ?", (table_id,)
    ).fetchone()


def update_table(conn: sqlite3.Connection, table_id: int, table_number: str,
                 capacity: int, zone: str) -> None:
    """Update a table's core attributes (number, capacity, zone).

    Does NOT change the status -- use update_table_status for that.
    """
    conn.execute(
        """UPDATE tables
           SET table_number = ?, capacity = ?, zone = ?,
               updated_at = ?
           WHERE id = ?""",
        (table_number, capacity, zone, datetime.now().isoformat(), table_id),
    )


def delete_table(conn: sqlite3.Connection, table_id: int) -> None:
    """Delete a table by ID."""
    conn.execute("DELETE FROM tables WHERE id = ?", (table_id,))


def update_table_status(conn: sqlite3.Connection, table_id: int,
                        status: str) -> None:
    """Update a table's status after validating against the allowed set.

    Args:
        conn: Database connection (caller manages transaction).
        table_id: Primary key of the table.
        status: Must be one of 'available', 'reserved', 'occupied',
                or 'needs_cleaning'.

    Raises:
        ValueError: If status is not in the allowed set.
    """
    if status not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid table status '{status}'. "
            f"Must be one of: {', '.join(ALLOWED_STATUSES)}"
        )
    conn.execute(
        "UPDATE tables SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), table_id),
    )


def get_table_status_board(conn: sqlite3.Connection) -> list:
    """Return all tables with their current status, ordered for the status board.

    Results are ordered by zone then table_number so the board groups
    tables by dining area.

    Returns:
        list[sqlite3.Row]: Each row has id, table_number, capacity, zone,
                           status, updated_at.
    """
    return conn.execute(
        """SELECT id, table_number, capacity, zone, status, updated_at
           FROM tables
           ORDER BY zone, table_number"""
    ).fetchall()
