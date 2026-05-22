import sqlite3


def create_desk(conn: sqlite3.Connection, name: str, location: str) -> int:
    cursor = conn.execute(
        "INSERT INTO desks (name, location) VALUES (?, ?)", (name, location)
    )
    conn.commit()
    return cursor.lastrowid


def get_desk(conn: sqlite3.Connection, desk_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM desks WHERE id=?", (desk_id,)).fetchone()


def get_all_desks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM desks ORDER BY name").fetchall()


def get_active_desks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM desks WHERE is_active=1 ORDER BY name"
    ).fetchall()


def update_desk(
    conn: sqlite3.Connection,
    desk_id: int,
    name: str,
    location: str,
    is_active: int,
) -> None:
    conn.execute(
        "UPDATE desks SET name=?, location=?, is_active=?, updated_at=datetime('now') WHERE id=?",
        (name, location, is_active, desk_id),
    )
    conn.commit()


def delete_desk(conn: sqlite3.Connection, desk_id: int) -> None:
    """Raises sqlite3.IntegrityError if desk has bookings (ON DELETE RESTRICT)."""
    conn.execute("DELETE FROM desks WHERE id=?", (desk_id,))
    conn.commit()
