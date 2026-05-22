import sqlite3


def create_class_type(conn: sqlite3.Connection, name: str,
                      description: str, duration_minutes: int,
                      default_capacity: int) -> int:
    """Create class type. Returns new type ID.

    Usage:
        type_id = create_class_type(conn, 'Yoga Basics', 'Beginner yoga', 60, 20)
        return redirect(url_for('class_types.list_types'))

    Commits: yes
    """
    cursor = conn.execute(
        "INSERT INTO class_types (name, description, duration_minutes, default_capacity) "
        "VALUES (?, ?, ?, ?)",
        (name, description, duration_minutes, default_capacity),
    )
    conn.commit()
    return cursor.lastrowid


def get_class_type(conn: sqlite3.Connection, type_id: int) -> sqlite3.Row | None:
    """Get class type by ID."""
    return conn.execute(
        "SELECT * FROM class_types WHERE id = ?", (type_id,)
    ).fetchone()


def get_all_class_types(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all class types ordered by name."""
    return conn.execute(
        "SELECT * FROM class_types ORDER BY name"
    ).fetchall()


def update_class_type(conn: sqlite3.Connection, type_id: int, name: str,
                      description: str, duration_minutes: int,
                      default_capacity: int) -> None:
    """Update class type. Commits: yes."""
    conn.execute(
        "UPDATE class_types SET name = ?, description = ?, duration_minutes = ?, "
        "default_capacity = ?, updated_at = datetime('now') WHERE id = ?",
        (name, description, duration_minutes, default_capacity, type_id),
    )
    conn.commit()


def delete_class_type(conn: sqlite3.Connection, type_id: int) -> None:
    """Delete class type. Commits: yes.

    Raises sqlite3.IntegrityError if schedules reference this type
    (FK RESTRICT on class_schedules.class_type_id).
    """
    conn.execute("DELETE FROM class_types WHERE id = ?", (type_id,))
    conn.commit()
