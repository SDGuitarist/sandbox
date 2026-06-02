"""Scene model functions — owns scenes and scene_elements tables."""

import sqlite3


# Valid status transitions for scenes.
# not_started -> in_prep -> ready -> shooting -> wrapped
# Any status can go to on_hold; on_hold can return to previous status.
VALID_TRANSITIONS = {
    'not_started': ['in_prep', 'on_hold'],
    'in_prep': ['ready', 'on_hold'],
    'ready': ['shooting', 'on_hold'],
    'shooting': ['wrapped', 'on_hold'],
    'wrapped': [],
    'on_hold': ['not_started', 'in_prep', 'ready', 'shooting'],
}

VALID_INT_EXT = {'INT', 'EXT', 'INT/EXT'}
VALID_DAY_NIGHT = {'DAY', 'NIGHT', 'DAWN', 'DUSK'}
VALID_ELEMENT_TYPES = {'prop', 'wardrobe', 'sfx', 'vehicle', 'animal', 'special_equipment'}


def create_scene(conn, project_id, scene_number, description, int_ext,
                 day_night, page_count_eighths, location_id=None):
    """Create a new scene. Returns int (scene_id). Commits internally."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            '''INSERT INTO scenes
               (project_id, scene_number, description, int_ext, day_night,
                page_count_eighths, location_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (project_id, scene_number, description, int_ext, day_night,
             page_count_eighths, location_id)
        )
        scene_id = cursor.lastrowid
        conn.execute('COMMIT')
        return scene_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_scenes(conn, project_id):
    """Return list[dict] with keys: id, scene_number, description, int_ext,
    day_night, page_count_eighths, location_name, status."""
    rows = conn.execute(
        '''SELECT s.id, s.scene_number, s.description, s.int_ext, s.day_night,
                  s.page_count_eighths, l.name AS location_name, s.status
           FROM scenes s
           LEFT JOIN locations l ON s.location_id = l.id
           WHERE s.project_id = ?
           ORDER BY s.scene_number''',
        (project_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_scenes_by_ids(conn, scene_ids):
    """Return list[dict] — subset by scene IDs.
    Keys: id, scene_number, int_ext, day_night, page_count_eighths, description,
    location_id, status, project_id."""
    if not scene_ids:
        return []
    placeholders = ','.join('?' for _ in scene_ids)
    rows = conn.execute(
        f'''SELECT id, scene_number, int_ext, day_night, page_count_eighths,
                   description, location_id, status, project_id
            FROM scenes WHERE id IN ({placeholders})''',
        list(scene_ids)
    ).fetchall()
    return [dict(r) for r in rows]


def get_scene(conn, scene_id):
    """Return dict or None with full scene data including location_name and notes."""
    row = conn.execute(
        '''SELECT s.*, l.name AS location_name
           FROM scenes s
           LEFT JOIN locations l ON s.location_id = l.id
           WHERE s.id = ?''',
        (scene_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def transition_scene_status(conn, scene_id, new_status):
    """Transition scene status. Returns bool. Commits internally (BEGIN IMMEDIATE).
    Re-checks current status inside lock to avoid TOCTOU race."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            'SELECT status FROM scenes WHERE id = ?', (scene_id,)
        ).fetchone()
        if row is None:
            conn.execute('ROLLBACK')
            return False
        current = row['status']
        if new_status not in VALID_TRANSITIONS.get(current, []):
            conn.execute('ROLLBACK')
            return False
        conn.execute(
            'UPDATE scenes SET status = ? WHERE id = ?',
            (new_status, scene_id)
        )
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise


def update_scene(conn, scene_id, **kwargs):
    """Update scene fields. Does NOT commit — caller commits.
    Allowed kwargs: scene_number, description, int_ext, day_night,
    page_count_eighths, location_id, notes."""
    allowed = {'scene_number', 'description', 'int_ext', 'day_night',
               'page_count_eighths', 'location_id', 'notes'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [scene_id]
    conn.execute(
        f'UPDATE scenes SET {set_clause} WHERE id = ?',
        values
    )


# --- Scene Elements ---

def get_scene_elements(conn, scene_id):
    """Return list[dict] of elements for a scene."""
    rows = conn.execute(
        'SELECT id, element_type, description FROM scene_elements WHERE scene_id = ? ORDER BY element_type, id',
        (scene_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def add_scene_element(conn, scene_id, element_type, description):
    """Add an element to a scene. Commits internally."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            'INSERT INTO scene_elements (scene_id, element_type, description) VALUES (?, ?, ?)',
            (scene_id, element_type, description)
        )
        element_id = cursor.lastrowid
        conn.execute('COMMIT')
        return element_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def remove_scene_element(conn, element_id):
    """Remove a scene element. Commits internally."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('DELETE FROM scene_elements WHERE id = ?', (element_id,))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
