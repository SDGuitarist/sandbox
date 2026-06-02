"""Location model functions for the Film Production PM tool."""


def create_location(conn, project_id, name, address=None, contact_name=None,
                    contact_phone=None, nearest_hospital=None):
    """Create a new location. Returns location_id. Commits internally (BEGIN IMMEDIATE)."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            '''INSERT INTO locations (project_id, name, address, contact_name,
               contact_phone, nearest_hospital)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (project_id, name, address, contact_name, contact_phone,
             nearest_hospital)
        )
        location_id = cursor.lastrowid
        conn.execute('COMMIT')
        return location_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_locations(conn, project_id):
    """Return list[dict] of all locations for a project."""
    rows = conn.execute(
        '''SELECT id, name, address, contact_name, contact_phone,
                  permit_status, nearest_hospital
           FROM locations
           WHERE project_id = ?
           ORDER BY name''',
        (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def get_location(conn, location_id):
    """Return dict or None with keys: id, name, address, contact_name,
    contact_phone, permit_status, nearest_hospital, project_id, notes."""
    row = conn.execute(
        '''SELECT id, project_id, name, address, contact_name, contact_phone,
                  permit_status, nearest_hospital, notes
           FROM locations
           WHERE id = ?''',
        (location_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)
