"""Model functions for daily specials.

All functions receive a sqlite3.Connection and do NOT commit.
Callers (routes) are responsible for BEGIN / commit().
"""
from __future__ import annotations

import sqlite3
from datetime import date


def create_special(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    price_cents: int,
    menu_item_id: int | None,
    start_date: str,
    end_date: str,
) -> int:
    """Insert a new daily special and return its id.

    Args:
        conn: Database connection (caller manages transaction).
        name: Display name for the special.
        description: Optional longer description.
        price_cents: Price stored as integer cents.
        menu_item_id: FK to menu_items (nullable).
        start_date: YYYY-MM-DD when the special becomes active.
        end_date: YYYY-MM-DD when the special stops being active.

    Returns:
        The new row's integer id (lastrowid).
    """
    cursor = conn.execute(
        """INSERT INTO specials (name, description, price_cents, menu_item_id,
                                start_date, end_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, description, price_cents, menu_item_id, start_date, end_date),
    )
    return cursor.lastrowid


def get_active_specials(conn: sqlite3.Connection) -> list:
    """Return specials where start_date <= today <= end_date and is_active=1.

    Sorted by end_date ascending so soonest-expiring specials appear first.
    """
    today = date.today().isoformat()
    return conn.execute(
        """SELECT * FROM specials
           WHERE is_active = 1
             AND start_date <= ?
             AND end_date >= ?
           ORDER BY end_date ASC""",
        (today, today),
    ).fetchall()


def get_all_specials(conn: sqlite3.Connection) -> list:
    """Return every special, newest first."""
    return conn.execute(
        "SELECT * FROM specials ORDER BY created_at DESC"
    ).fetchall()


def get_special(conn: sqlite3.Connection, special_id: int):
    """Return a single special by id, or None if not found."""
    return conn.execute(
        "SELECT * FROM specials WHERE id = ?", (special_id,)
    ).fetchone()


def update_special(
    conn: sqlite3.Connection,
    special_id: int,
    name: str,
    description: str,
    price_cents: int,
    menu_item_id: int | None,
    start_date: str,
    end_date: str,
    is_active: int,
) -> None:
    """Update all mutable fields of an existing special.

    Args:
        conn: Database connection (caller manages transaction).
        special_id: Row to update.
        name: Display name.
        description: Longer description.
        price_cents: Price in integer cents.
        menu_item_id: FK to menu_items (nullable).
        start_date: YYYY-MM-DD.
        end_date: YYYY-MM-DD.
        is_active: 1 or 0.
    """
    conn.execute(
        """UPDATE specials
           SET name = ?, description = ?, price_cents = ?,
               menu_item_id = ?, start_date = ?, end_date = ?,
               is_active = ?
           WHERE id = ?""",
        (name, description, price_cents, menu_item_id,
         start_date, end_date, is_active, special_id),
    )


def delete_special(conn: sqlite3.Connection, special_id: int) -> None:
    """Delete a special by id."""
    conn.execute("DELETE FROM specials WHERE id = ?", (special_id,))
