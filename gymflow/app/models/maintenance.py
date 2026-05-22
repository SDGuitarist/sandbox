import sqlite3


def create_maintenance(conn: sqlite3.Connection, equipment_id: int,
                       description: str, maintenance_date: str,
                       cost_cents: int, performed_by: str,
                       next_due_date: str | None) -> int:
    """Create maintenance record. Returns new record ID.

    Usage:
        maint_id = create_maintenance(conn, 1, 'Belt replaced',
                                      '2026-05-21', 5000, 'Bob', '2026-08-21')
        return redirect(url_for('maintenance.list_maintenance'))
    Commits: yes (conn.commit())
    """
    cursor = conn.execute(
        """INSERT INTO maintenance_log
           (equipment_id, description, maintenance_date, cost_cents,
            performed_by, next_due_date)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (equipment_id, description, maintenance_date, cost_cents,
         performed_by, next_due_date),
    )
    conn.commit()
    return cursor.lastrowid


def get_maintenance(conn: sqlite3.Connection,
                    maintenance_id: int) -> sqlite3.Row | None:
    """Get maintenance record by ID with equipment_name joined."""
    return conn.execute(
        """SELECT m.*, e.name AS equipment_name
           FROM maintenance_log m
           JOIN equipment e ON e.id = m.equipment_id
           WHERE m.id = ?""",
        (maintenance_id,),
    ).fetchone()


def get_maintenance_by_equipment(conn: sqlite3.Connection,
                                 equipment_id: int) -> list[sqlite3.Row]:
    """Get maintenance records for equipment. Ordered by maintenance_date DESC."""
    return conn.execute(
        """SELECT m.*, e.name AS equipment_name
           FROM maintenance_log m
           JOIN equipment e ON e.id = m.equipment_id
           WHERE m.equipment_id = ?
           ORDER BY m.maintenance_date DESC""",
        (equipment_id,),
    ).fetchall()


def get_all_maintenance(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all maintenance records with equipment_name. Ordered by date DESC."""
    return conn.execute(
        """SELECT m.*, e.name AS equipment_name
           FROM maintenance_log m
           JOIN equipment e ON e.id = m.equipment_id
           ORDER BY m.maintenance_date DESC""",
    ).fetchall()


def update_maintenance(conn: sqlite3.Connection, maintenance_id: int,
                       equipment_id: int, description: str,
                       maintenance_date: str, cost_cents: int,
                       performed_by: str,
                       next_due_date: str | None) -> None:
    """Update maintenance record. Commits: yes."""
    conn.execute(
        """UPDATE maintenance_log
           SET equipment_id = ?, description = ?, maintenance_date = ?,
               cost_cents = ?, performed_by = ?, next_due_date = ?
           WHERE id = ?""",
        (equipment_id, description, maintenance_date, cost_cents,
         performed_by, next_due_date, maintenance_id),
    )
    conn.commit()


def delete_maintenance(conn: sqlite3.Connection,
                       maintenance_id: int) -> None:
    """Delete maintenance record. Commits: yes."""
    conn.execute(
        "DELETE FROM maintenance_log WHERE id = ?",
        (maintenance_id,),
    )
    conn.commit()
