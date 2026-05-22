import sqlite3


def create_member(conn: sqlite3.Connection, name: str, email: str,
                  phone: str, company: str,
                  membership_plan_id: int | None, notes: str) -> int:
    """Create a new member. Returns the new member's ID.
    Commits: yes (conn.commit())"""
    cursor = conn.execute(
        "INSERT INTO members (name, email, phone, company, membership_plan_id, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (name, email, phone, company, membership_plan_id, notes)
    )
    conn.commit()
    return cursor.lastrowid


def get_member(conn: sqlite3.Connection, member_id: int) -> sqlite3.Row | None:
    """Get member by ID with membership plan name joined.
    Returns Row with columns: id, name, email, phone, company,
    membership_plan_id, status, join_date, notes, created_at, updated_at,
    plan_name (from LEFT JOIN membership_plans, may be NULL)."""
    return conn.execute(
        """SELECT m.*, mp.name AS plan_name
           FROM members m
           LEFT JOIN membership_plans mp ON m.membership_plan_id = mp.id
           WHERE m.id = ?""",
        (member_id,)
    ).fetchone()


def get_all_members(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all members ordered by name. Includes plan_name LEFT JOIN."""
    return conn.execute(
        """SELECT m.*, mp.name AS plan_name
           FROM members m
           LEFT JOIN membership_plans mp ON m.membership_plan_id = mp.id
           ORDER BY m.name"""
    ).fetchall()


def update_member(conn: sqlite3.Connection, member_id: int, name: str,
                  email: str, phone: str, company: str,
                  membership_plan_id: int | None, status: str,
                  notes: str) -> None:
    """Update member fields. Also sets updated_at = datetime('now').
    Commits: yes."""
    conn.execute(
        """UPDATE members SET name=?, email=?, phone=?, company=?,
           membership_plan_id=?, status=?, notes=?, updated_at=datetime('now')
           WHERE id=?""",
        (name, email, phone, company, membership_plan_id, status, notes, member_id)
    )
    conn.commit()


def delete_member(conn: sqlite3.Connection, member_id: int) -> None:
    """Delete member. Commits: yes.
    Raises sqlite3.IntegrityError if member has desk_bookings, room_bookings,
    or invoices (all ON DELETE RESTRICT)."""
    conn.execute("DELETE FROM members WHERE id=?", (member_id,))
    conn.commit()


def count_active_members(conn: sqlite3.Connection) -> int:
    """Count members with status='active'. Returns int."""
    row = conn.execute("SELECT COUNT(*) FROM members WHERE status='active'").fetchone()
    return row[0]


def search_members(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    """Search members by name or email (LIKE %query%). Returns list.
    MUST use parameterized query."""
    return conn.execute(
        """SELECT m.*, mp.name AS plan_name
           FROM members m
           LEFT JOIN membership_plans mp ON m.membership_plan_id = mp.id
           WHERE m.name LIKE ? OR m.email LIKE ?
           ORDER BY m.name""",
        (f"%{query}%", f"%{query}%")
    ).fetchall()
