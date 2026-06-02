"""Cast member model functions.

Owns: cast_members table, scene_cast table (M2M).
Transaction contracts: create_cast_member commits internally (BEGIN IMMEDIATE).
add_cast_to_scene, remove_cast_from_scene, get_scene_cast do NOT commit.
"""
import sqlite3


def create_cast_member(conn, project_id, name, character_name, cast_id_number):
    """Create a new cast member.

    Returns: int (cast_member_id) -- commits internally (BEGIN IMMEDIATE).
    Raises sqlite3.IntegrityError if cast_id_number is not unique per project.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            '''INSERT INTO cast_members (project_id, name, character_name, cast_id_number)
               VALUES (?, ?, ?, ?)''',
            (project_id, name, character_name, cast_id_number)
        )
        cast_member_id = cursor.lastrowid
        conn.execute('COMMIT')
        return cast_member_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_cast_members(conn, project_id):
    """Get all cast members for a project.

    Returns: list[dict] with keys: id, name, character_name, cast_id_number, agent_name.
    Ordered by cast_id_number ascending.
    """
    rows = conn.execute(
        '''SELECT id, name, character_name, cast_id_number, agent_name
           FROM cast_members
           WHERE project_id = ?
           ORDER BY cast_id_number''',
        (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def get_cast_member(conn, cast_member_id):
    """Get a single cast member by ID.

    Returns: dict or None. Includes all columns.
    """
    row = conn.execute(
        '''SELECT id, project_id, name, character_name, cast_id_number,
                  agent_name, agent_phone, agent_email, notes, created_at
           FROM cast_members
           WHERE id = ?''',
        (cast_member_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_cast_for_scenes(conn, scene_ids):
    """Get cast members assigned to any of the given scenes.

    Used by callsheet_models to populate call sheet cast.

    Returns: list[dict] with keys: id, name, character_name, cast_id_number.
    """
    if not scene_ids:
        return []
    placeholders = ','.join('?' for _ in scene_ids)
    rows = conn.execute(
        f'''SELECT DISTINCT cm.id, cm.name, cm.character_name, cm.cast_id_number
            FROM scene_cast sc
            JOIN cast_members cm ON cm.id = sc.cast_member_id
            WHERE sc.scene_id IN ({placeholders})
            ORDER BY cm.cast_id_number''',
        list(scene_ids)
    ).fetchall()
    return [dict(row) for row in rows]


def add_cast_to_scene(conn, scene_id, cast_member_id):
    """Assign a cast member to a scene (M2M).

    Returns: None -- does NOT commit. Caller must manage transaction.
    Uses INSERT OR IGNORE to handle duplicate gracefully.
    """
    conn.execute(
        '''INSERT OR IGNORE INTO scene_cast (scene_id, cast_member_id)
           VALUES (?, ?)''',
        (scene_id, cast_member_id)
    )


def remove_cast_from_scene(conn, scene_id, cast_member_id):
    """Remove a cast member from a scene (M2M).

    Returns: None -- does NOT commit. Caller must manage transaction.
    """
    conn.execute(
        '''DELETE FROM scene_cast
           WHERE scene_id = ? AND cast_member_id = ?''',
        (scene_id, cast_member_id)
    )


def update_cast_member(conn, cast_member_id, name, character_name, cast_id_number,
                       agent_name=None, agent_phone=None, agent_email=None, notes=None):
    """Update an existing cast member.

    Returns: None -- requires BEGIN IMMEDIATE from caller.
    Raises sqlite3.IntegrityError if cast_id_number is not unique per project.
    """
    conn.execute(
        '''UPDATE cast_members
           SET name = ?, character_name = ?, cast_id_number = ?,
               agent_name = ?, agent_phone = ?, agent_email = ?, notes = ?
           WHERE id = ?''',
        (name, character_name, cast_id_number,
         agent_name, agent_phone, agent_email, notes, cast_member_id)
    )


def get_scene_cast(conn, scene_id):
    """Get all cast members assigned to a specific scene.

    Returns: list[dict] with keys: id, name, character_name, cast_id_number.
    """
    rows = conn.execute(
        '''SELECT cm.id, cm.name, cm.character_name, cm.cast_id_number
           FROM scene_cast sc
           JOIN cast_members cm ON cm.id = sc.cast_member_id
           WHERE sc.scene_id = ?
           ORDER BY cm.cast_id_number''',
        (scene_id,)
    ).fetchall()
    return [dict(row) for row in rows]
