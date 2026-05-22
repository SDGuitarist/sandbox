import sqlite3

VALID_SLOT_STARTS = [
    '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
    '11:00', '11:30', '12:00', '12:30', '13:00', '13:30',
    '14:00', '14:30', '15:00', '15:30', '16:00', '16:30',
    '17:00', '17:30'
]


def create_room_booking(conn: sqlite3.Connection, room_id: int,
                        member_id: int, booking_date: str,
                        slot_start: str, purpose: str) -> int | None:
    """Book a single 30-min room slot. Returns booking ID or None if conflict."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        conflict = conn.execute(
            "SELECT 1 FROM room_bookings WHERE room_id=? AND booking_date=? AND slot_start=? AND status='confirmed'",
            (room_id, booking_date, slot_start)).fetchone()
        if conflict:
            conn.execute('ROLLBACK')
            return None
        conn.execute(
            "INSERT INTO room_bookings (room_id, member_id, booking_date, slot_start, purpose) VALUES (?, ?, ?, ?, ?)",
            (room_id, member_id, booking_date, slot_start, purpose))
        booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute('COMMIT')
        return booking_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_room_booking(conn: sqlite3.Connection, booking_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT rb.*, r.name AS room_name, m.name AS member_name, r.capacity AS room_capacity
           FROM room_bookings rb
           JOIN meeting_rooms r ON rb.room_id = r.id
           JOIN members m ON rb.member_id = m.id
           WHERE rb.id = ?""", (booking_id,)).fetchone()


def get_all_room_bookings(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT rb.*, r.name AS room_name, m.name AS member_name
           FROM room_bookings rb
           JOIN meeting_rooms r ON rb.room_id = r.id
           JOIN members m ON rb.member_id = m.id
           ORDER BY rb.booking_date DESC, rb.slot_start""").fetchall()


def get_room_bookings_by_date(conn: sqlite3.Connection, booking_date: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT rb.*, r.name AS room_name, m.name AS member_name
           FROM room_bookings rb
           JOIN meeting_rooms r ON rb.room_id = r.id
           JOIN members m ON rb.member_id = m.id
           WHERE rb.booking_date = ?
           ORDER BY r.name, rb.slot_start""", (booking_date,)).fetchall()


def get_room_bookings_by_member(conn: sqlite3.Connection, member_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT rb.*, r.name AS room_name
           FROM room_bookings rb
           JOIN meeting_rooms r ON rb.room_id = r.id
           WHERE rb.member_id = ?
           ORDER BY rb.booking_date DESC""", (member_id,)).fetchall()


def get_available_slots(conn: sqlite3.Connection, room_id: int, booking_date: str) -> list[str]:
    booked = conn.execute(
        "SELECT slot_start FROM room_bookings WHERE room_id=? AND booking_date=? AND status='confirmed'",
        (room_id, booking_date)).fetchall()
    booked_set = {row['slot_start'] for row in booked}
    return [s for s in VALID_SLOT_STARTS if s not in booked_set]


def cancel_room_booking(conn: sqlite3.Connection, booking_id: int) -> None:
    conn.execute(
        "UPDATE room_bookings SET status='cancelled', updated_at=datetime('now') WHERE id=?",
        (booking_id,))
    conn.commit()


def count_room_bookings_today(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM room_bookings WHERE booking_date=date('now') AND status='confirmed'"
    ).fetchone()
    return row[0]
