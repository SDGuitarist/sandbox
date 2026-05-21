"""Staff and shift management model functions.

All functions take a conn parameter and do NOT commit.
The caller (route) is responsible for committing.
"""

import sqlite3


# ---------------------------------------------------------------------------
# Staff CRUD
# ---------------------------------------------------------------------------

def create_staff(conn: sqlite3.Connection, name: str, role: str,
                 phone: str, email: str) -> int:
    """Insert a new staff member and return the new row ID."""
    cursor = conn.execute(
        "INSERT INTO staff (name, role, phone, email) VALUES (?, ?, ?, ?)",
        (name, role, phone, email),
    )
    return cursor.lastrowid


def get_all_staff(conn: sqlite3.Connection, active_only: bool = True) -> list:
    """Return all staff members as a list of sqlite3.Row.

    When *active_only* is True (default), only rows with is_active = 1 are
    returned.  Pass False to include deactivated members.
    """
    if active_only:
        return conn.execute(
            "SELECT * FROM staff WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    return conn.execute(
        "SELECT * FROM staff ORDER BY name"
    ).fetchall()


def get_staff_member(conn: sqlite3.Connection, staff_id: int):
    """Return a single staff row or None if not found."""
    return conn.execute(
        "SELECT * FROM staff WHERE id = ?", (staff_id,)
    ).fetchone()


def update_staff(conn: sqlite3.Connection, staff_id: int, name: str,
                 role: str, phone: str, email: str, is_active: int) -> None:
    """Update an existing staff member's fields."""
    conn.execute(
        """UPDATE staff
           SET name = ?, role = ?, phone = ?, email = ?, is_active = ?,
               updated_at = datetime('now')
           WHERE id = ?""",
        (name, role, phone, email, is_active, staff_id),
    )


def delete_staff(conn: sqlite3.Connection, staff_id: int) -> None:
    """Delete a staff member by ID.

    Associated shifts are removed automatically via ON DELETE CASCADE.
    """
    conn.execute("DELETE FROM staff WHERE id = ?", (staff_id,))


# ---------------------------------------------------------------------------
# Shift management
# ---------------------------------------------------------------------------

def create_shift(conn: sqlite3.Connection, staff_id: int, shift_date: str,
                 start_time: str, end_time: str, role: str,
                 notes: str) -> int:
    """Insert a new shift and return the new row ID."""
    cursor = conn.execute(
        """INSERT INTO shifts (staff_id, shift_date, start_time, end_time,
                              role, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (staff_id, shift_date, start_time, end_time, role, notes),
    )
    return cursor.lastrowid


def get_shifts_by_date(conn: sqlite3.Connection, date: str) -> list:
    """Return all shifts for a given date (YYYY-MM-DD), joined with staff name."""
    return conn.execute(
        """SELECT sh.*, s.name AS staff_name
           FROM shifts sh
           JOIN staff s ON sh.staff_id = s.id
           WHERE sh.shift_date = ?
           ORDER BY sh.start_time""",
        (date,),
    ).fetchall()


def get_shifts_by_staff(conn: sqlite3.Connection, staff_id: int) -> list:
    """Return all shifts for a given staff member, most recent first."""
    return conn.execute(
        """SELECT * FROM shifts
           WHERE staff_id = ?
           ORDER BY shift_date DESC, start_time""",
        (staff_id,),
    ).fetchall()


def get_shift(conn: sqlite3.Connection, shift_id: int):
    """Return a single shift row or None if not found."""
    return conn.execute(
        "SELECT * FROM shifts WHERE id = ?", (shift_id,)
    ).fetchone()


def update_shift(conn: sqlite3.Connection, shift_id: int, staff_id: int,
                 shift_date: str, start_time: str, end_time: str,
                 role: str, notes: str) -> None:
    """Update an existing shift's fields."""
    conn.execute(
        """UPDATE shifts
           SET staff_id = ?, shift_date = ?, start_time = ?, end_time = ?,
               role = ?, notes = ?
           WHERE id = ?""",
        (staff_id, shift_date, start_time, end_time, role, notes, shift_id),
    )


def delete_shift(conn: sqlite3.Connection, shift_id: int) -> None:
    """Delete a shift by ID."""
    conn.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
