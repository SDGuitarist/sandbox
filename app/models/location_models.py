"""Location model functions.

Owns the `locations` table. Read by scenes, schedule, callsheets, and search.

Cross-boundary consumers (see plan Cross-Boundary Wiring / Export Names tables):
  - get_location  -> consumed by callsheet_models (call sheet location block)
  - get_locations -> consumed by scenes routes, schedule routes (form dropdowns)
"""

import sqlite3


def create_location(conn, project_id, name, address=None, contact_name=None,
                    contact_phone=None, nearest_hospital=None) -> int:
    """Create a location for a project.

    Returns: int (location_id). Commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            '''INSERT INTO locations
                   (project_id, name, address, contact_name, contact_phone, nearest_hospital)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (project_id, name, address, contact_name, contact_phone, nearest_hospital),
        )
        location_id = cur.lastrowid
        conn.execute('COMMIT')
        return location_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_locations(conn, project_id) -> list:
    """Return all locations for a project, ordered by name.

    Returns: list[dict] with keys: id, name, address, contact_name,
             contact_phone, permit_status, nearest_hospital, notes, created_at.
    """
    rows = conn.execute(
        '''SELECT id, name, address, contact_name, contact_phone,
                  permit_status, nearest_hospital, notes, created_at
           FROM locations
           WHERE project_id = ?
           ORDER BY name''',
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_location(conn, location_id) -> dict | None:
    """Return a single location by id, or None.

    Returns the FULL key set (FC50/FC30/FC3) so cross-boundary consumers
    (callsheet_models) get every field they may need:
      id, project_id, name, address, contact_name, contact_phone,
      permit_status, nearest_hospital, notes, created_at.
    """
    row = conn.execute(
        '''SELECT id, project_id, name, address, contact_name, contact_phone,
                  permit_status, nearest_hospital, notes, created_at
           FROM locations
           WHERE id = ?''',
        (location_id,),
    ).fetchone()
    return dict(row) if row is not None else None
