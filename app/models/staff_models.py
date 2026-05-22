import sqlite3


# All functions are SERIAL-SAFE: single-row INSERT/UPDATE/DELETE
# with no cross-table dependencies. Route handler calls conn.commit()
# after the model function returns.


def get_all_staff(conn: sqlite3.Connection) -> list:
    """Return all staff members ordered by name."""
    return conn.execute('SELECT * FROM staff ORDER BY name').fetchall()


def get_staff_member(conn: sqlite3.Connection, staff_id: int):
    """Return a single staff member by ID, or None if not found."""
    return conn.execute(
        'SELECT * FROM staff WHERE id = ?', (staff_id,)
    ).fetchone()


def create_staff(conn: sqlite3.Connection, name: str, role: str,
                 email: str | None, phone: str,
                 hire_date: str | None) -> int:
    """Insert a new staff member. Returns the new staff member's ID."""
    cur = conn.execute(
        'INSERT INTO staff (name, role, email, phone, hire_date) '
        'VALUES (?, ?, ?, ?, ?)',
        (name, role, email, phone, hire_date))
    return cur.lastrowid


def update_staff(conn: sqlite3.Connection, staff_id: int, name: str,
                 role: str, email: str | None, phone: str,
                 hire_date: str | None, status: str) -> None:
    """Update an existing staff member's fields."""
    conn.execute(
        "UPDATE staff SET name=?, role=?, email=?, phone=?, hire_date=?, "
        "status=?, updated_at=datetime('now') WHERE id=?",
        (name, role, email, phone, hire_date, status, staff_id))


def delete_staff(conn: sqlite3.Connection, staff_id: int) -> None:
    """Delete a staff member by ID."""
    conn.execute('DELETE FROM staff WHERE id = ?', (staff_id,))
