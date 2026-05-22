import sqlite3
from datetime import date, timedelta


def create_schedule(conn: sqlite3.Connection, class_type_id: int,
                    trainer_id: int | None, session_date: str,
                    start_time: str, end_time: str, room: str,
                    capacity: int, notes: str) -> int:
    """Create class schedule. Returns new schedule ID.

    Commits: yes (conn.commit())
    """
    cursor = conn.execute(
        """INSERT INTO class_schedules
           (class_type_id, trainer_id, session_date, start_time, end_time,
            room, capacity, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (class_type_id, trainer_id, session_date, start_time, end_time,
         room, capacity, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_schedule(conn: sqlite3.Connection, schedule_id: int) -> sqlite3.Row | None:
    """Get schedule by ID with class_type_name and trainer_name joined.

    Returns Row with: id, class_type_id, trainer_id, session_date, start_time,
    end_time, room, capacity, notes, created_at, updated_at,
    class_type_name, trainer_name (may be NULL).
    """
    return conn.execute(
        """SELECT cs.id, cs.class_type_id, cs.trainer_id, cs.session_date,
                  cs.start_time, cs.end_time, cs.room, cs.capacity, cs.notes,
                  cs.created_at, cs.updated_at,
                  ct.name AS class_type_name,
                  t.name AS trainer_name
           FROM class_schedules cs
           JOIN class_types ct ON cs.class_type_id = ct.id
           LEFT JOIN trainers t ON cs.trainer_id = t.id
           WHERE cs.id = ?""",
        (schedule_id,),
    ).fetchone()


def get_schedules_by_date(conn: sqlite3.Connection, date: str) -> list[sqlite3.Row]:
    """Get schedules for a specific date. Includes class_type_name, trainer_name.

    Ordered by start_time.
    """
    return conn.execute(
        """SELECT cs.id, cs.class_type_id, cs.trainer_id, cs.session_date,
                  cs.start_time, cs.end_time, cs.room, cs.capacity, cs.notes,
                  cs.created_at, cs.updated_at,
                  ct.name AS class_type_name,
                  t.name AS trainer_name
           FROM class_schedules cs
           JOIN class_types ct ON cs.class_type_id = ct.id
           LEFT JOIN trainers t ON cs.trainer_id = t.id
           WHERE cs.session_date = ?
           ORDER BY cs.start_time""",
        (date,),
    ).fetchall()


def get_schedules_by_date_range(conn: sqlite3.Connection, start_date: str,
                                 end_date: str) -> list[sqlite3.Row]:
    """Get schedules between start_date and end_date (inclusive).

    Ordered by session_date, start_time.
    """
    return conn.execute(
        """SELECT cs.id, cs.class_type_id, cs.trainer_id, cs.session_date,
                  cs.start_time, cs.end_time, cs.room, cs.capacity, cs.notes,
                  cs.created_at, cs.updated_at,
                  ct.name AS class_type_name,
                  t.name AS trainer_name
           FROM class_schedules cs
           JOIN class_types ct ON cs.class_type_id = ct.id
           LEFT JOIN trainers t ON cs.trainer_id = t.id
           WHERE cs.session_date >= ? AND cs.session_date <= ?
           ORDER BY cs.session_date, cs.start_time""",
        (start_date, end_date),
    ).fetchall()


def get_schedules_by_trainer(conn: sqlite3.Connection, trainer_id: int) -> list[sqlite3.Row]:
    """Get schedules for a specific trainer. Includes class_type_name."""
    return conn.execute(
        """SELECT cs.id, cs.class_type_id, cs.trainer_id, cs.session_date,
                  cs.start_time, cs.end_time, cs.room, cs.capacity, cs.notes,
                  cs.created_at, cs.updated_at,
                  ct.name AS class_type_name
           FROM class_schedules cs
           JOIN class_types ct ON cs.class_type_id = ct.id
           WHERE cs.trainer_id = ?
           ORDER BY cs.session_date, cs.start_time""",
        (trainer_id,),
    ).fetchall()


def update_schedule(conn: sqlite3.Connection, schedule_id: int,
                    class_type_id: int, trainer_id: int | None,
                    session_date: str, start_time: str, end_time: str,
                    room: str, capacity: int, notes: str) -> None:
    """Update schedule. Commits: yes."""
    conn.execute(
        """UPDATE class_schedules
           SET class_type_id = ?, trainer_id = ?, session_date = ?,
               start_time = ?, end_time = ?, room = ?, capacity = ?,
               notes = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (class_type_id, trainer_id, session_date, start_time, end_time,
         room, capacity, notes, schedule_id),
    )
    conn.commit()


def delete_schedule(conn: sqlite3.Connection, schedule_id: int) -> None:
    """Delete schedule. Commits: yes.

    Raises sqlite3.IntegrityError if attendance records exist
    (FK RESTRICT on attendance.class_schedule_id).
    """
    conn.execute(
        "DELETE FROM class_schedules WHERE id = ?",
        (schedule_id,),
    )
    conn.commit()


def _monday_of_week(d: date) -> date:
    """Return the Monday of the week containing the given date."""
    return d - timedelta(days=d.weekday())


def copy_week_schedules(conn: sqlite3.Connection, source_date: str,
                        target_date: str) -> int:
    """Copy all schedules from source week (Mon-Sun) to target week.

    source_date and target_date are any dates within their respective weeks.
    Returns count of schedules created.
    Commits: yes (single transaction via BEGIN IMMEDIATE).
    """
    source_monday = _monday_of_week(date.fromisoformat(source_date))
    target_monday = _monday_of_week(date.fromisoformat(target_date))
    source_sunday = source_monday + timedelta(days=6)
    day_offset = (target_monday - source_monday).days

    # Fetch all schedules in the source week
    rows = conn.execute(
        """SELECT class_type_id, trainer_id, session_date, start_time,
                  end_time, room, capacity, notes
           FROM class_schedules
           WHERE session_date >= ? AND session_date <= ?""",
        (source_monday.isoformat(), source_sunday.isoformat()),
    ).fetchall()

    conn.execute("BEGIN IMMEDIATE")
    try:
        for row in rows:
            original_date = date.fromisoformat(row["session_date"])
            new_date = original_date + timedelta(days=day_offset)
            conn.execute(
                """INSERT INTO class_schedules
                   (class_type_id, trainer_id, session_date, start_time,
                    end_time, room, capacity, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["class_type_id"], row["trainer_id"], new_date.isoformat(),
                 row["start_time"], row["end_time"], row["room"],
                 row["capacity"], row["notes"]),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return len(rows)


def get_schedule_attendance_count(conn: sqlite3.Connection,
                                   schedule_id: int) -> int:
    """Count attendance records for a schedule. Returns int (scalar)."""
    row = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE class_schedule_id = ?",
        (schedule_id,),
    ).fetchone()
    return row[0]
