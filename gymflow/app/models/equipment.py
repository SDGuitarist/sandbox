import sqlite3


def create_equipment(conn: sqlite3.Connection, name: str, category: str,
                     serial_number: str, purchase_date: str | None,
                     purchase_price_cents: int, status: str,
                     location: str, notes: str) -> int:
    """Create equipment. Returns new equipment ID.

    Usage:
        equip_id = create_equipment(conn, 'Treadmill X500', 'Cardio',
                                    'SN-12345', '2026-01-15', 150000,
                                    'available', 'Main Floor', '')
        return redirect(url_for('equipment.detail', equipment_id=equip_id))

    Commits: yes (conn.commit())
    """
    cursor = conn.execute(
        """INSERT INTO equipment
           (name, category, serial_number, purchase_date,
            purchase_price_cents, status, location, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, category, serial_number, purchase_date,
         purchase_price_cents, status, location, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_equipment(conn: sqlite3.Connection, equipment_id: int) -> sqlite3.Row | None:
    """Get equipment by ID. Returns a Row or None if not found."""
    return conn.execute(
        "SELECT * FROM equipment WHERE id = ?",
        (equipment_id,),
    ).fetchone()


def get_all_equipment(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all equipment ordered by name."""
    return conn.execute(
        "SELECT * FROM equipment ORDER BY name",
    ).fetchall()


def get_equipment_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    """Get equipment filtered by status."""
    return conn.execute(
        "SELECT * FROM equipment WHERE status = ? ORDER BY name",
        (status,),
    ).fetchall()


def update_equipment(conn: sqlite3.Connection, equipment_id: int, name: str,
                     category: str, serial_number: str,
                     purchase_date: str | None, purchase_price_cents: int,
                     status: str, location: str, notes: str) -> None:
    """Update equipment. Commits: yes."""
    conn.execute(
        """UPDATE equipment
           SET name = ?, category = ?, serial_number = ?,
               purchase_date = ?, purchase_price_cents = ?,
               status = ?, location = ?, notes = ?,
               updated_at = datetime('now')
           WHERE id = ?""",
        (name, category, serial_number, purchase_date,
         purchase_price_cents, status, location, notes, equipment_id),
    )
    conn.commit()


def delete_equipment(conn: sqlite3.Connection, equipment_id: int) -> None:
    """Delete equipment. Commits: yes.

    Raises sqlite3.IntegrityError if maintenance records exist
    (FK RESTRICT on maintenance_log).
    """
    conn.execute(
        "DELETE FROM equipment WHERE id = ?",
        (equipment_id,),
    )
    conn.commit()


def get_equipment_needing_maintenance(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get equipment where latest maintenance_log.next_due_date <= date('now').

    JOINs equipment with maintenance_log, finds the most recent next_due_date
    per equipment item, and returns rows where that date is today or past.
    Returns equipment rows with next_due_date column added.
    """
    return conn.execute(
        """SELECT e.*, ml.next_due_date
           FROM equipment e
           JOIN maintenance_log ml ON e.id = ml.equipment_id
           WHERE ml.next_due_date IS NOT NULL
             AND ml.next_due_date <= date('now')
             AND ml.id = (
                 SELECT ml2.id FROM maintenance_log ml2
                 WHERE ml2.equipment_id = e.id
                   AND ml2.next_due_date IS NOT NULL
                 ORDER BY ml2.maintenance_date DESC, ml2.id DESC
                 LIMIT 1
             )
           ORDER BY ml.next_due_date""",
    ).fetchall()
