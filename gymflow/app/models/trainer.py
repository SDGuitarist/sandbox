import sqlite3


def create_trainer(conn: sqlite3.Connection, name: str, email: str,
                   phone: str, specializations: str, bio: str) -> int:
    """Create trainer. Returns new trainer ID.
    Usage:
        trainer_id = create_trainer(conn, 'Jane Smith', 'jane@gym.com',
                                    '555-0200', 'Yoga, Pilates', 'Bio text')
        return redirect(url_for('trainers.detail', trainer_id=trainer_id))
    Commits: yes
    """
    cursor = conn.execute(
        "INSERT INTO trainers (name, email, phone, specializations, bio) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, email, phone, specializations, bio),
    )
    conn.commit()
    return cursor.lastrowid


def get_trainer(conn: sqlite3.Connection, trainer_id: int) -> sqlite3.Row | None:
    """Get trainer by ID. Returns Row or None."""
    return conn.execute(
        "SELECT * FROM trainers WHERE id = ?", (trainer_id,)
    ).fetchone()


def get_all_trainers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all trainers ordered by name."""
    return conn.execute(
        "SELECT * FROM trainers ORDER BY name"
    ).fetchall()


def get_active_trainers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get trainers with status='active'."""
    return conn.execute(
        "SELECT * FROM trainers WHERE status = 'active' ORDER BY name"
    ).fetchall()


def update_trainer(conn: sqlite3.Connection, trainer_id: int, name: str,
                   email: str, phone: str, specializations: str,
                   bio: str, status: str) -> None:
    """Update trainer fields. Commits: yes."""
    conn.execute(
        "UPDATE trainers SET name = ?, email = ?, phone = ?, "
        "specializations = ?, bio = ?, status = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (name, email, phone, specializations, bio, status, trainer_id),
    )
    conn.commit()


def delete_trainer(conn: sqlite3.Connection, trainer_id: int) -> None:
    """Delete trainer. Commits: yes.
    FK constraints are SET NULL -- trainer_id on schedules/assessments
    becomes NULL automatically. No IntegrityError raised.
    """
    conn.execute("DELETE FROM trainers WHERE id = ?", (trainer_id,))
    conn.commit()
