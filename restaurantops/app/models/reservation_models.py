"""Reservation CRUD and status-transition helpers.

All write functions receive a sqlite3.Connection but do NOT commit.
The caller (route) owns BEGIN IMMEDIATE and conn.commit().
"""

import sqlite3
from datetime import datetime, timedelta

from app.models.table_models import update_table_status


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_reservation(
    conn: sqlite3.Connection,
    table_id: int,
    guest_name: str,
    guest_phone: str,
    party_size: int,
    reservation_date: str,
    reservation_time: str,
    duration_minutes: int,
    notes: str,
) -> int:
    """Insert a new reservation and return its id. Does NOT commit."""
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    cur = conn.execute(
        """INSERT INTO reservations
               (table_id, guest_name, guest_phone, party_size,
                reservation_date, reservation_time, duration_minutes,
                notes, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?)""",
        (
            table_id,
            guest_name,
            guest_phone,
            party_size,
            reservation_date,
            reservation_time,
            duration_minutes,
            notes,
            now,
            now,
        ),
    )
    return cur.lastrowid


def get_all_reservations(
    conn: sqlite3.Connection, date: str | None = None
) -> list:
    """Return all reservations, optionally filtered by date.

    Joins with the tables table so the caller gets table_number for display.
    """
    base = """
        SELECT r.*, t.table_number
        FROM reservations r
        JOIN tables t ON t.id = r.table_id
    """
    if date:
        return conn.execute(
            base + " WHERE r.reservation_date = ? ORDER BY r.reservation_time",
            (date,),
        ).fetchall()
    return conn.execute(
        base + " ORDER BY r.reservation_date, r.reservation_time"
    ).fetchall()


def get_reservation(conn: sqlite3.Connection, reservation_id: int):
    """Return a single reservation row (with table_number) or None."""
    return conn.execute(
        """SELECT r.*, t.table_number
           FROM reservations r
           JOIN tables t ON t.id = r.table_id
           WHERE r.id = ?""",
        (reservation_id,),
    ).fetchone()


def update_reservation(
    conn: sqlite3.Connection,
    reservation_id: int,
    table_id: int,
    guest_name: str,
    guest_phone: str,
    party_size: int,
    reservation_date: str,
    reservation_time: str,
    duration_minutes: int,
    notes: str,
) -> None:
    """Update an existing reservation's details. Does NOT commit."""
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    conn.execute(
        """UPDATE reservations
           SET table_id = ?, guest_name = ?, guest_phone = ?,
               party_size = ?, reservation_date = ?, reservation_time = ?,
               duration_minutes = ?, notes = ?, updated_at = ?
           WHERE id = ?""",
        (
            table_id,
            guest_name,
            guest_phone,
            party_size,
            reservation_date,
            reservation_time,
            duration_minutes,
            notes,
            now,
            reservation_id,
        ),
    )


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

def seat_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    """confirmed -> seated, update table status to 'occupied'. Does NOT commit."""
    row = conn.execute(
        "SELECT table_id, status FROM reservations WHERE id = ?",
        (reservation_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Reservation {reservation_id} not found")
    if row["status"] != "confirmed":
        raise ValueError(
            f"Cannot seat reservation with status '{row['status']}'"
        )
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "UPDATE reservations SET status = 'seated', updated_at = ? WHERE id = ?",
        (now, reservation_id),
    )
    update_table_status(conn, row["table_id"], "occupied")


def complete_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    """seated -> completed, update table status to 'needs_cleaning'. Does NOT commit."""
    row = conn.execute(
        "SELECT table_id, status FROM reservations WHERE id = ?",
        (reservation_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Reservation {reservation_id} not found")
    if row["status"] != "seated":
        raise ValueError(
            f"Cannot complete reservation with status '{row['status']}'"
        )
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "UPDATE reservations SET status = 'completed', updated_at = ? WHERE id = ?",
        (now, reservation_id),
    )
    update_table_status(conn, row["table_id"], "needs_cleaning")


def cancel_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    """any -> cancelled, update table status to 'available' if was reserved. Does NOT commit."""
    row = conn.execute(
        "SELECT table_id, status FROM reservations WHERE id = ?",
        (reservation_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Reservation {reservation_id} not found")
    if row["status"] in ("cancelled", "completed"):
        raise ValueError(
            f"Cannot cancel reservation with status '{row['status']}'"
        )
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "UPDATE reservations SET status = 'cancelled', updated_at = ? WHERE id = ?",
        (now, reservation_id),
    )
    update_table_status(conn, row["table_id"], "available")


def no_show_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    """confirmed -> no_show, update table status to 'available'. Does NOT commit."""
    row = conn.execute(
        "SELECT table_id, status FROM reservations WHERE id = ?",
        (reservation_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Reservation {reservation_id} not found")
    if row["status"] != "confirmed":
        raise ValueError(
            f"Cannot mark no-show for reservation with status '{row['status']}'"
        )
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    conn.execute(
        "UPDATE reservations SET status = 'no_show', updated_at = ? WHERE id = ?",
        (now, reservation_id),
    )
    update_table_status(conn, row["table_id"], "available")


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def is_table_available(
    conn: sqlite3.Connection,
    table_id: int,
    reservation_date: str,
    reservation_time: str,
    duration_minutes: int,
    exclude_reservation_id: int | None = None,
) -> bool:
    """Check whether *table_id* is free for the requested time window.

    A table is unavailable if any existing non-cancelled/non-completed/non-no-show
    reservation overlaps with the requested [start, start+duration) window.

    Time overlap logic:
        existing_start < requested_end AND requested_start < existing_end
    """
    # Parse the requested window
    req_start = datetime.strptime(
        f"{reservation_date} {reservation_time}", "%Y-%m-%d %H:%M"
    )
    req_end = req_start + timedelta(minutes=duration_minutes)

    # Fetch active reservations for this table on the same date
    query = """
        SELECT reservation_time, duration_minutes, id
        FROM reservations
        WHERE table_id = ?
          AND reservation_date = ?
          AND status IN ('confirmed', 'seated')
    """
    params: list = [table_id, reservation_date]

    if exclude_reservation_id is not None:
        query += " AND id != ?"
        params.append(exclude_reservation_id)

    rows = conn.execute(query, params).fetchall()

    for row in rows:
        existing_start = datetime.strptime(
            f"{reservation_date} {row['reservation_time']}", "%Y-%m-%d %H:%M"
        )
        existing_end = existing_start + timedelta(minutes=row["duration_minutes"])

        # Overlap check: two intervals overlap if each starts before the other ends
        if existing_start < req_end and req_start < existing_end:
            return False

    return True
