"""Member CRUD model functions.

All functions receive a sqlite3.Connection as the first parameter.
Write functions commit internally via conn.commit().
"""

import sqlite3
from datetime import date


def create_member(conn: sqlite3.Connection, name: str, email: str,
                  phone: str, emergency_contact: str,
                  membership_type_id: int | None, notes: str) -> int:
    """Create a new member. Returns the new member's ID.

    Usage:
        member_id = create_member(conn, 'John Doe', 'john@example.com',
                                  '555-0100', 'Jane Doe 555-0101', 1, '')
        return redirect(url_for('members.detail', member_id=member_id))

    Commits: yes (conn.commit())
    """
    cursor = conn.execute(
        """INSERT INTO members (name, email, phone, emergency_contact,
                                membership_type_id, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, email, phone, emergency_contact, membership_type_id, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_member(conn: sqlite3.Connection, member_id: int) -> sqlite3.Row | None:
    """Get member by ID with membership type name joined.

    Returns Row with columns: id, name, email, phone, emergency_contact,
    membership_type_id, status, join_date, notes, created_at, updated_at,
    membership_type_name (from JOIN, may be NULL).

    Usage:
        member = get_member(conn, member_id)
        if member is None:
            abort(404)
    """
    row = conn.execute(
        """SELECT m.id, m.name, m.email, m.phone, m.emergency_contact,
                  m.membership_type_id, m.status, m.join_date, m.notes,
                  m.created_at, m.updated_at,
                  mt.name AS membership_type_name
           FROM members m
           LEFT JOIN membership_types mt ON m.membership_type_id = mt.id
           WHERE m.id = ?""",
        (member_id,),
    ).fetchone()
    return row


def get_all_members(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all members ordered by name. Includes membership_type_name JOIN."""
    rows = conn.execute(
        """SELECT m.id, m.name, m.email, m.phone, m.emergency_contact,
                  m.membership_type_id, m.status, m.join_date, m.notes,
                  m.created_at, m.updated_at,
                  mt.name AS membership_type_name
           FROM members m
           LEFT JOIN membership_types mt ON m.membership_type_id = mt.id
           ORDER BY m.name"""
    ).fetchall()
    return rows


def get_members_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    """Get members filtered by status ('active', 'frozen', 'cancelled')."""
    rows = conn.execute(
        """SELECT m.id, m.name, m.email, m.phone, m.emergency_contact,
                  m.membership_type_id, m.status, m.join_date, m.notes,
                  m.created_at, m.updated_at,
                  mt.name AS membership_type_name
           FROM members m
           LEFT JOIN membership_types mt ON m.membership_type_id = mt.id
           WHERE m.status = ?
           ORDER BY m.name""",
        (status,),
    ).fetchall()
    return rows


def update_member(conn: sqlite3.Connection, member_id: int, name: str,
                  email: str, phone: str, emergency_contact: str,
                  membership_type_id: int | None, status: str,
                  notes: str) -> None:
    """Update member fields. Commits: yes."""
    conn.execute(
        """UPDATE members
           SET name = ?, email = ?, phone = ?, emergency_contact = ?,
               membership_type_id = ?, status = ?, notes = ?,
               updated_at = datetime('now')
           WHERE id = ?""",
        (name, email, phone, emergency_contact, membership_type_id,
         status, notes, member_id),
    )
    conn.commit()


def delete_member(conn: sqlite3.Connection, member_id: int) -> None:
    """Delete member. Commits: yes.

    Raises sqlite3.IntegrityError if member has attendance/invoices/assessments
    (FK ON DELETE RESTRICT).
    """
    conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()


def count_active_members(conn: sqlite3.Connection) -> int:
    """Count members with status='active'. Returns int.

    Usage:
        active_count = count_active_members(conn)
        # active_count is an int, NOT a Row
    """
    row = conn.execute(
        "SELECT COUNT(*) FROM members WHERE status = 'active'"
    ).fetchone()
    return row[0]


def count_new_members_this_month(conn: sqlite3.Connection) -> int:
    """Count members with join_date in current month. Returns int."""
    today = date.today()
    first_of_month = today.strftime("%Y-%m-01")
    row = conn.execute(
        "SELECT COUNT(*) FROM members WHERE join_date >= ?",
        (first_of_month,),
    ).fetchone()
    return row[0]


def search_members(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    """Search members by name or email (LIKE %query%). Returns list.

    Uses parameterized query -- NEVER f-string or .format() with user input.
    """
    rows = conn.execute(
        """SELECT m.id, m.name, m.email, m.phone, m.emergency_contact,
                  m.membership_type_id, m.status, m.join_date, m.notes,
                  m.created_at, m.updated_at,
                  mt.name AS membership_type_name
           FROM members m
           LEFT JOIN membership_types mt ON m.membership_type_id = mt.id
           WHERE m.name LIKE ? OR m.email LIKE ?
           ORDER BY m.name""",
        (f"%{query}%", f"%{query}%"),
    ).fetchall()
    return rows
