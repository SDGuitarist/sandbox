"""Scene model functions and scene_elements helpers.

Owns tables: scenes, scene_elements.
Owns constant: VALID_SCENE_TRANSITIONS.

Transaction discipline per the spec Transaction Contracts table:
  - create_scene            -> BEGIN IMMEDIATE, commits internally
  - transition_scene_status -> BEGIN IMMEDIATE, commits internally (TOCTOU re-check)
  - update_scene            -> NO transaction, caller commits
The scene_elements helpers do NOT commit (caller commits) so a route can wrap an
update + element changes + index_entity in a single transaction.
"""

# app/models/scene_models.py (scenes agent owns this constant)
VALID_SCENE_TRANSITIONS = {
    'not_started': ['in_prep', 'on_hold'],
    'in_prep':     ['ready', 'on_hold'],
    'ready':       ['shooting', 'on_hold'],
    'shooting':    ['wrapped', 'on_hold'],
    'on_hold':     ['in_prep', 'ready', 'shooting'],
    'wrapped':     [],   # terminal
}
# Used by: transition_scene_status() and POST /scenes/<pid>/<sid>/status


def create_scene(conn, project_id, scene_number, description, int_ext, day_night,
                 page_count_eighths, location_id=None) -> int:
    """Insert a scene. Returns scene_id. Commits internally (BEGIN IMMEDIATE)."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            '''INSERT INTO scenes
               (project_id, scene_number, description, int_ext, day_night,
                page_count_eighths, location_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (project_id, scene_number, description, int_ext, day_night,
             page_count_eighths, location_id))
        scene_id = cur.lastrowid
        conn.execute('COMMIT')
        return scene_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_scenes(conn, project_id) -> list:
    """List scenes for a project.
    Keys: id, scene_number, description, int_ext, day_night,
          page_count_eighths, location_name, status.
    """
    rows = conn.execute(
        '''SELECT s.id, s.scene_number, s.description, s.int_ext, s.day_night,
                  s.page_count_eighths, l.name AS location_name, s.status
           FROM scenes s
           LEFT JOIN locations l ON l.id = s.location_id
           WHERE s.project_id = ?
           ORDER BY s.id''',
        (project_id,)).fetchall()
    return [dict(r) for r in rows]


def get_scenes_by_ids(conn, scene_ids) -> list:
    """Scenes for a list of ids (consumed by callsheet_models).
    Keys: id, scene_number, description, int_ext, day_night, page_count_eighths.
    """
    if not scene_ids:
        return []
    placeholders = ','.join('?' for _ in scene_ids)
    rows = conn.execute(
        f'''SELECT id, scene_number, description, int_ext, day_night,
                   page_count_eighths
            FROM scenes
            WHERE id IN ({placeholders})''',
        tuple(scene_ids)).fetchall()
    return [dict(r) for r in rows]


def get_scene(conn, scene_id) -> dict | None:
    """Single scene with all columns (includes project_id for IDOR checks)."""
    row = conn.execute(
        '''SELECT s.id, s.project_id, s.scene_number, s.description, s.int_ext,
                  s.day_night, s.page_count_eighths, s.location_id,
                  l.name AS location_name, s.status, s.notes, s.created_at
           FROM scenes s
           LEFT JOIN locations l ON l.id = s.location_id
           WHERE s.id = ?''',
        (scene_id,)).fetchone()
    return dict(row) if row else None


def transition_scene_status(conn, scene_id, new_status) -> bool:
    """Validate + apply a status transition. Commits internally (BEGIN IMMEDIATE).
    Re-checks the current status inside the lock (TOCTOU fence). Returns False if
    the scene is gone or the transition is not allowed.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT status FROM scenes WHERE id = ?',
                           (scene_id,)).fetchone()
        if row is None:
            conn.execute('ROLLBACK')
            return False
        current = row['status']
        if new_status not in VALID_SCENE_TRANSITIONS.get(current, []):
            conn.execute('ROLLBACK')
            return False
        conn.execute('UPDATE scenes SET status = ? WHERE id = ?',
                     (new_status, scene_id))
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise


def update_scene(conn, scene_id, **kwargs) -> None:
    """Update mutable scene columns. Does NOT commit -- caller commits.
    Only whitelisted columns are written; unknown keys are ignored (fail closed).
    """
    allowed = ('scene_number', 'description', 'int_ext', 'day_night',
               'page_count_eighths', 'location_id', 'notes')
    fields = [(k, v) for k, v in kwargs.items() if k in allowed]
    if not fields:
        return
    assignments = ', '.join(f'{k} = ?' for k, _ in fields)
    values = [v for _, v in fields]
    values.append(scene_id)
    conn.execute(f'UPDATE scenes SET {assignments} WHERE id = ?', tuple(values))


# --- scene_elements helpers (scenes agent owns scene_elements) -----------------
# These do NOT commit -- caller commits (so they can be wrapped with index_entity).

def get_scene_elements(conn, scene_id) -> list:
    """Elements tagged on a scene. Keys: id, scene_id, element_type, description."""
    rows = conn.execute(
        '''SELECT id, scene_id, element_type, description
           FROM scene_elements
           WHERE scene_id = ?
           ORDER BY id''',
        (scene_id,)).fetchall()
    return [dict(r) for r in rows]


def add_scene_element(conn, scene_id, element_type, description) -> None:
    """Insert one scene element. Does NOT commit -- caller commits."""
    conn.execute(
        '''INSERT INTO scene_elements (scene_id, element_type, description)
           VALUES (?, ?, ?)''',
        (scene_id, element_type, description))


def remove_scene_element(conn, element_id) -> None:
    """Delete one scene element. Does NOT commit -- caller commits."""
    conn.execute('DELETE FROM scene_elements WHERE id = ?', (element_id,))
