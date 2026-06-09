"""Cast member model functions.

Owns: cast_members, scene_cast (M2M join).
Read by: scenes (M2M), callsheets, reports, search.

Transaction contracts (per spec):
- create_cast_member      -> commits internally (BEGIN IMMEDIATE)
- add_cast_to_scene       -> does NOT commit (caller commits)
- remove_cast_from_scene  -> does NOT commit (caller commits)
"""

import sqlite3


def create_cast_member(conn, project_id, name, character_name, cast_id_number) -> int:
    """Insert a cast member. Commits internally (BEGIN IMMEDIATE).

    Returns the new cast_member_id.
    Raises sqlite3.IntegrityError on duplicate cast_id_number for the project.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            '''INSERT INTO cast_members (project_id, name, character_name, cast_id_number)
               VALUES (?, ?, ?, ?)''',
            (project_id, name, character_name, cast_id_number),
        )
        new_id = cur.lastrowid
        conn.execute('COMMIT')
        return new_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def update_cast_member(conn, cast_member_id, name, character_name, cast_id_number) -> None:
    """Update an existing cast member. Commits internally (BEGIN IMMEDIATE).

    Raises sqlite3.IntegrityError on duplicate cast_id_number for the project.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(
            '''UPDATE cast_members
               SET name = ?, character_name = ?, cast_id_number = ?
               WHERE id = ?''',
            (name, character_name, cast_id_number, cast_member_id),
        )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_cast_members(conn, project_id) -> list:
    """Return all cast members for a project.

    Returns: list[dict] with keys: id, name, character_name, cast_id_number, agent_name
    """
    rows = conn.execute(
        '''SELECT id, name, character_name, cast_id_number, agent_name
           FROM cast_members
           WHERE project_id = ?
           ORDER BY cast_id_number''',
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_cast_member(conn, cast_member_id) -> dict | None:
    """Return a single cast member (all columns) or None."""
    row = conn.execute(
        '''SELECT id, project_id, name, character_name, cast_id_number,
                  agent_name, agent_phone, agent_email, notes, created_at
           FROM cast_members
           WHERE id = ?''',
        (cast_member_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def get_cast_for_scenes(conn, scene_ids) -> list:
    """Return distinct cast members appearing in any of the given scenes.

    Cross-boundary export consumed by callsheet_models (FC50).
    Returns: list[dict] with keys: id, name, character_name, cast_id_number
    """
    if not scene_ids:
        return []
    placeholders = ','.join('?' for _ in scene_ids)
    rows = conn.execute(
        f'''SELECT DISTINCT cm.id, cm.name, cm.character_name, cm.cast_id_number
            FROM cast_members cm
            JOIN scene_cast sc ON sc.cast_member_id = cm.id
            WHERE sc.scene_id IN ({placeholders})
            ORDER BY cm.cast_id_number''',
        tuple(scene_ids),
    ).fetchall()
    return [dict(row) for row in rows]


def add_cast_to_scene(conn, scene_id, cast_member_id) -> None:
    """Link a cast member to a scene. Does NOT commit (caller commits).

    Idempotent: INSERT OR IGNORE respects the UNIQUE(scene_id, cast_member_id)
    constraint without raising on duplicates.
    """
    conn.execute(
        '''INSERT OR IGNORE INTO scene_cast (scene_id, cast_member_id)
           VALUES (?, ?)''',
        (scene_id, cast_member_id),
    )


def remove_cast_from_scene(conn, scene_id, cast_member_id) -> None:
    """Unlink a cast member from a scene. Does NOT commit (caller commits)."""
    conn.execute(
        '''DELETE FROM scene_cast
           WHERE scene_id = ? AND cast_member_id = ?''',
        (scene_id, cast_member_id),
    )


def get_scene_cast(conn, scene_id) -> list:
    """Return cast members assigned to a specific scene.

    Returns: list[dict] with keys: id, name, character_name, cast_id_number
    """
    rows = conn.execute(
        '''SELECT cm.id, cm.name, cm.character_name, cm.cast_id_number
           FROM cast_members cm
           JOIN scene_cast sc ON sc.cast_member_id = cm.id
           WHERE sc.scene_id = ?
           ORDER BY cm.cast_id_number''',
        (scene_id,),
    ).fetchall()
    return [dict(row) for row in rows]
