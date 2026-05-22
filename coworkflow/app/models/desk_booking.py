import sqlite3


def create_desk_booking(conn: sqlite3.Connection, desk_id: int,
                        member_id: int, booking_date: str, block: str) -> int | None:
    """Book a desk. Returns booking ID or None if conflict.
    BEGIN IMMEDIATE -> conflict check -> INSERT -> COMMIT.
    With try/except/ROLLBACK wrapper."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        if block == 'full':
            conflict = conn.execute(
                "SELECT 1 FROM desk_bookings WHERE desk_id=? AND booking_date=? AND status='confirmed'",
                (desk_id, booking_date)).fetchone()
        elif block == 'am':
            conflict = conn.execute(
                "SELECT 1 FROM desk_bookings WHERE desk_id=? AND booking_date=? AND block IN ('am','full') AND status='confirmed'",
                (desk_id, booking_date)).fetchone()
        else:  # pm
            conflict = conn.execute(
                "SELECT 1 FROM desk_bookings WHERE desk_id=? AND booking_date=? AND block IN ('pm','full') AND status='confirmed'",
                (desk_id, booking_date)).fetchone()
        if conflict:
            conn.execute('ROLLBACK')
            return None
        conn.execute(
            "INSERT INTO desk_bookings (desk_id, member_id, booking_date, block) VALUES (?, ?, ?, ?)",
            (desk_id, member_id, booking_date, block))
        booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute('COMMIT')
        return booking_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_desk_booking(conn: sqlite3.Connection, booking_id: int) -> sqlite3.Row | None:
    """Joins desk name and member name."""
    return conn.execute(
        """SELECT db.*, d.name AS desk_name, m.name AS member_name
           FROM desk_bookings db
           JOIN desks d ON db.desk_id = d.id
           JOIN members m ON db.member_id = m.id
           WHERE db.id = ?""", (booking_id,)).fetchone()


def get_all_desk_bookings(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT db.*, d.name AS desk_name, m.name AS member_name
           FROM desk_bookings db
           JOIN desks d ON db.desk_id = d.id
           JOIN members m ON db.member_id = m.id
           ORDER BY db.booking_date DESC, db.block""").fetchall()


def get_desk_bookings_by_date(conn: sqlite3.Connection, booking_date: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT db.*, d.name AS desk_name, m.name AS member_name
           FROM desk_bookings db
           JOIN desks d ON db.desk_id = d.id
           JOIN members m ON db.member_id = m.id
           WHERE db.booking_date = ?
           ORDER BY d.name, db.block""", (booking_date,)).fetchall()


def get_desk_bookings_by_member(conn: sqlite3.Connection, member_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT db.*, d.name AS desk_name
           FROM desk_bookings db
           JOIN desks d ON db.desk_id = d.id
           WHERE db.member_id = ?
           ORDER BY db.booking_date DESC""", (member_id,)).fetchall()


def cancel_desk_booking(conn: sqlite3.Connection, booking_id: int) -> None:
    conn.execute(
        "UPDATE desk_bookings SET status='cancelled', updated_at=datetime('now') WHERE id=?",
        (booking_id,))
    conn.commit()


def count_desk_bookings_today(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM desk_bookings WHERE booking_date=date('now') AND status='confirmed'"
    ).fetchone()
    return row[0]
