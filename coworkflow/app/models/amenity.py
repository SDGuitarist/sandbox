import sqlite3


def create_amenity(conn: sqlite3.Connection, name: str, description: str) -> int:
    cursor = conn.execute(
        "INSERT INTO amenities (name, description) VALUES (?, ?)",
        (name, description),
    )
    conn.commit()
    return cursor.lastrowid


def get_amenity(conn: sqlite3.Connection, amenity_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM amenities WHERE id=?", (amenity_id,)
    ).fetchone()


def get_all_amenities(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM amenities ORDER BY name").fetchall()


def update_amenity(
    conn: sqlite3.Connection,
    amenity_id: int,
    name: str,
    description: str,
    is_available: int,
) -> None:
    conn.execute(
        "UPDATE amenities SET name=?, description=?, is_available=?,"
        " updated_at=datetime('now') WHERE id=?",
        (name, description, is_available, amenity_id),
    )
    conn.commit()


def delete_amenity(conn: sqlite3.Connection, amenity_id: int) -> None:
    """No FK constraints -- safe to delete."""
    conn.execute("DELETE FROM amenities WHERE id=?", (amenity_id,))
    conn.commit()


def count_amenities(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM amenities").fetchone()
    return row[0]
