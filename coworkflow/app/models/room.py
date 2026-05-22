import sqlite3


def create_room(conn: sqlite3.Connection, name: str, capacity: int,
                hourly_rate_cents: int, location: str) -> int:
    cursor = conn.execute(
        "INSERT INTO meeting_rooms (name, capacity, hourly_rate_cents, location) VALUES (?, ?, ?, ?)",
        (name, capacity, hourly_rate_cents, location))
    conn.commit()
    return cursor.lastrowid


def get_room(conn: sqlite3.Connection, room_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM meeting_rooms WHERE id=?", (room_id,)).fetchone()


def get_all_rooms(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM meeting_rooms ORDER BY name").fetchall()


def get_active_rooms(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM meeting_rooms WHERE is_active=1 ORDER BY name").fetchall()


def update_room(conn: sqlite3.Connection, room_id: int, name: str, capacity: int,
                hourly_rate_cents: int, location: str, is_active: int) -> None:
    conn.execute(
        """UPDATE meeting_rooms SET name=?, capacity=?, hourly_rate_cents=?, location=?,
           is_active=?, updated_at=datetime('now') WHERE id=?""",
        (name, capacity, hourly_rate_cents, location, is_active, room_id))
    conn.commit()


def delete_room(conn: sqlite3.Connection, room_id: int) -> None:
    """Raises sqlite3.IntegrityError if room has bookings (ON DELETE RESTRICT)."""
    conn.execute("DELETE FROM meeting_rooms WHERE id=?", (room_id,))
    conn.commit()
