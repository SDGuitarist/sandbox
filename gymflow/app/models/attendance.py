import sqlite3


def check_in_class(conn: sqlite3.Connection, member_id: int,
                   class_schedule_id: int) -> int:
    """Check in member to a class. Returns new attendance ID.
    Uses BEGIN IMMEDIATE for atomic capacity check.
    Raises ValueError if class is full or schedule not found.
    Commits: yes (via BEGIN IMMEDIATE ... COMMIT)
    """
    conn.execute('BEGIN IMMEDIATE')
    try:
        row = conn.execute(
            'SELECT COUNT(*) FROM attendance WHERE class_schedule_id = ?',
            (class_schedule_id,)
        ).fetchone()
        count = row[0]

        schedule_row = conn.execute(
            'SELECT capacity FROM class_schedules WHERE id = ?',
            (class_schedule_id,)
        ).fetchone()
        if schedule_row is None:
            raise ValueError('Class schedule not found')
        capacity = schedule_row[0]

        if count >= capacity:
            raise ValueError('Class is full')

        cursor = conn.execute(
            'INSERT INTO attendance (member_id, class_schedule_id, attendance_type) '
            'VALUES (?, ?, ?)',
            (member_id, class_schedule_id, 'class')
        )
        attendance_id = cursor.lastrowid
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    return attendance_id


def check_in_open_gym(conn: sqlite3.Connection, member_id: int) -> int:
    """Check in member for open gym (no class). Returns new attendance ID.
    Commits: yes
    """
    cursor = conn.execute(
        'INSERT INTO attendance (member_id, class_schedule_id, attendance_type) '
        'VALUES (?, NULL, ?)',
        (member_id, 'open_gym')
    )
    conn.commit()
    return cursor.lastrowid


def check_out(conn: sqlite3.Connection, attendance_id: int) -> None:
    """Record check-out time. Commits: yes."""
    conn.execute(
        "UPDATE attendance SET check_out_time = datetime('now') WHERE id = ?",
        (attendance_id,)
    )
    conn.commit()


def get_attendance(conn: sqlite3.Connection,
                   attendance_id: int) -> sqlite3.Row | None:
    """Get attendance record by ID with member_name joined."""
    return conn.execute(
        'SELECT a.*, m.name AS member_name '
        'FROM attendance a '
        'JOIN members m ON a.member_id = m.id '
        'WHERE a.id = ?',
        (attendance_id,)
    ).fetchone()


def get_attendance_by_schedule(conn: sqlite3.Connection,
                               schedule_id: int) -> list[sqlite3.Row]:
    """Get all attendance for a class schedule. Includes member_name."""
    return conn.execute(
        'SELECT a.*, m.name AS member_name '
        'FROM attendance a '
        'JOIN members m ON a.member_id = m.id '
        'WHERE a.class_schedule_id = ? '
        'ORDER BY a.check_in_time DESC',
        (schedule_id,)
    ).fetchall()


def get_attendance_by_member(conn: sqlite3.Connection,
                              member_id: int) -> list[sqlite3.Row]:
    """Get all attendance for a member. Includes class_type_name (may be NULL
    for open_gym)."""
    return conn.execute(
        'SELECT a.*, ct.name AS class_type_name '
        'FROM attendance a '
        'LEFT JOIN class_schedules cs ON a.class_schedule_id = cs.id '
        'LEFT JOIN class_types ct ON cs.class_type_id = ct.id '
        'WHERE a.member_id = ? '
        'ORDER BY a.check_in_time DESC',
        (member_id,)
    ).fetchall()


def get_recent_checkins(conn: sqlite3.Connection,
                        limit: int = 10) -> list[sqlite3.Row]:
    """Get most recent check-ins. Includes member_name, class_type_name."""
    return conn.execute(
        'SELECT a.*, m.name AS member_name, ct.name AS class_type_name '
        'FROM attendance a '
        'JOIN members m ON a.member_id = m.id '
        'LEFT JOIN class_schedules cs ON a.class_schedule_id = cs.id '
        'LEFT JOIN class_types ct ON cs.class_type_id = ct.id '
        'ORDER BY a.check_in_time DESC '
        'LIMIT ?',
        (limit,)
    ).fetchall()


def get_today_checkins(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get today's check-ins. Includes member_name."""
    return conn.execute(
        'SELECT a.*, m.name AS member_name '
        'FROM attendance a '
        'JOIN members m ON a.member_id = m.id '
        "WHERE date(a.check_in_time) = date('now') "
        'ORDER BY a.check_in_time DESC'
    ).fetchall()


def delete_attendance(conn: sqlite3.Connection, attendance_id: int) -> None:
    """Delete attendance record. Commits: yes."""
    conn.execute(
        'DELETE FROM attendance WHERE id = ?',
        (attendance_id,)
    )
    conn.commit()
