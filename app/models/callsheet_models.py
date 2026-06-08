"""Call sheet model functions.

HIGHEST-RISK MODULE: aggregates data from 4 other model modules.
Cross-boundary imports (per Cross-Boundary Wiring Table — Call Sheet Wiring):
  - schedule_models.get_schedule_entries(conn, project_id, shoot_date) -> list[dict]
  - scene_models.get_scenes_by_ids(conn, scene_ids) -> list[dict]
  - cast_models.get_cast_for_scenes(conn, scene_ids) -> list[dict]
  - location_models.get_location(conn, location_id) -> dict | None

Transaction Contracts:
  - generate_call_sheet: BEGIN IMMEDIATE, commits internally (multi-table)
  - publish_call_sheet:  BEGIN IMMEDIATE, commits internally
  - get_*: read-only, no transaction
"""

from app.models.schedule_models import get_schedule_entries
from app.models.scene_models import get_scenes_by_ids
from app.models.cast_models import get_cast_for_scenes
from app.models.location_models import get_location


def generate_call_sheet(conn, project_id, shoot_date):
    """Generate (or regenerate) a call sheet for a project's shoot day.

    Idempotent: if a call sheet already exists for (project_id, shoot_date),
    it is deleted and rebuilt rather than duplicated (call_sheet_scenes and
    call_sheet_cast cascade on the call_sheets delete via FK ON DELETE CASCADE).

    Returns: int (call_sheet_id) -- commits internally (BEGIN IMMEDIATE).
    """
    # ----- ALL READS OUTSIDE THE LOCK (TOCTOU-safe; reads do not block writers) -----
    entries = get_schedule_entries(conn, project_id, shoot_date)

    # scene_id and location_id come straight from schedule_entries rows.
    scene_ids = [entry['scene_id'] for entry in entries]

    # Location: derive from the first scheduled entry that has a location_id.
    location_id = None
    for entry in entries:
        if entry['location_id'] is not None:
            location_id = entry['location_id']
            break

    # Cast assigned to the scheduled scenes (deduplicated by cast_models).
    cast = get_cast_for_scenes(conn, scene_ids) if scene_ids else []

    # Determine the next sheet_number for this project (max existing + 1).
    row = conn.execute(
        'SELECT COALESCE(MAX(sheet_number), 0) AS max_num FROM call_sheets WHERE project_id = ?',
        (project_id,),
    ).fetchone()
    next_sheet_number = row['max_num'] + 1

    # Preserve an existing sheet_number if regenerating for this date.
    existing = conn.execute(
        'SELECT id, sheet_number FROM call_sheets WHERE project_id = ? AND shoot_date = ?',
        (project_id, shoot_date),
    ).fetchone()
    if existing is not None:
        sheet_number = existing['sheet_number']
    else:
        sheet_number = next_sheet_number

    # ----- WRITES INSIDE THE LOCK (single BEGIN IMMEDIATE, multi-table) -----
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Idempotency: remove any prior sheet for this (project, date).
        # ON DELETE CASCADE clears call_sheet_scenes and call_sheet_cast.
        conn.execute(
            'DELETE FROM call_sheets WHERE project_id = ? AND shoot_date = ?',
            (project_id, shoot_date),
        )

        cur = conn.execute(
            '''INSERT INTO call_sheets (project_id, sheet_number, shoot_date, status)
               VALUES (?, ?, ?, 'draft')''',
            (project_id, sheet_number, shoot_date),
        )
        call_sheet_id = cur.lastrowid

        for sort_order, scene_id in enumerate(scene_ids):
            conn.execute(
                '''INSERT INTO call_sheet_scenes (call_sheet_id, scene_id, sort_order)
                   VALUES (?, ?, ?)''',
                (call_sheet_id, scene_id, sort_order),
            )

        for member in cast:
            conn.execute(
                '''INSERT INTO call_sheet_cast (call_sheet_id, cast_member_id, status)
                   VALUES (?, ?, 'W')''',
                (call_sheet_id, member['id']),
            )

        conn.execute('COMMIT')
        return call_sheet_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_call_sheet(conn, call_sheet_id):
    """Return a call sheet header row, or None.

    Returns: dict or None with keys: id, project_id, sheet_number, shoot_date,
             crew_call_time, weather_note, general_notes, status, created_at,
             plus derived location_name / location_address / location_hospital.
    """
    row = conn.execute(
        '''SELECT id, project_id, sheet_number, shoot_date, crew_call_time,
                  weather_note, general_notes, status, created_at
           FROM call_sheets WHERE id = ?''',
        (call_sheet_id,),
    ).fetchone()
    if row is None:
        return None

    sheet = dict(row)

    # Derive the location from the first scheduled scene (same rule as generation).
    entries = get_schedule_entries(conn, sheet['project_id'], sheet['shoot_date'])
    location = None
    for entry in entries:
        if entry['location_id'] is not None:
            location = get_location(conn, entry['location_id'])
            break

    if location is not None:
        sheet['location_name'] = location['name']
        sheet['location_address'] = location['address']
        sheet['location_hospital'] = location['nearest_hospital']
    else:
        sheet['location_name'] = None
        sheet['location_address'] = None
        sheet['location_hospital'] = None

    return sheet


def get_call_sheet_scenes(conn, call_sheet_id):
    """Return scenes on a call sheet in sort order, with scene detail.

    Returns: list[dict] with keys: scene_id, sort_order, scene_number,
             int_ext, day_night, page_count_eighths.
    """
    rows = conn.execute(
        '''SELECT scene_id, sort_order
           FROM call_sheet_scenes
           WHERE call_sheet_id = ?
           ORDER BY sort_order''',
        (call_sheet_id,),
    ).fetchall()

    scene_ids = [row['scene_id'] for row in rows]
    if not scene_ids:
        return []

    # Cross-boundary: scene_models.get_scenes_by_ids(conn, scene_ids)
    # -> list[dict] with scene_number, int_ext, day_night, page_count_eighths.
    scenes = get_scenes_by_ids(conn, scene_ids)
    by_id = {scene['id']: scene for scene in scenes}

    result = []
    for row in rows:
        scene = by_id.get(row['scene_id'])
        if scene is None:
            continue
        result.append({
            'scene_id': row['scene_id'],
            'sort_order': row['sort_order'],
            'scene_number': scene['scene_number'],
            'int_ext': scene['int_ext'],
            'day_night': scene['day_night'],
            'page_count_eighths': scene['page_count_eighths'],
        })
    return result


def get_call_sheet_cast(conn, call_sheet_id):
    """Return cast on a call sheet with call times and status.

    Returns: list[dict] with keys: cast_member_id, name, character_name,
             cast_id_number, pickup_time, makeup_time, on_set_time, status, remarks.
    """
    rows = conn.execute(
        '''SELECT csc.cast_member_id, csc.pickup_time, csc.makeup_time,
                  csc.on_set_time, csc.status, csc.remarks,
                  cm.name, cm.character_name, cm.cast_id_number
           FROM call_sheet_cast csc
           JOIN cast_members cm ON cm.id = csc.cast_member_id
           WHERE csc.call_sheet_id = ?
           ORDER BY cm.cast_id_number''',
        (call_sheet_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def publish_call_sheet(conn, call_sheet_id):
    """Mark a draft call sheet as published.

    Returns: bool -- True if a draft was published, False otherwise.
    Commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Re-check status inside the lock to avoid double-publish races.
        row = conn.execute(
            'SELECT status FROM call_sheets WHERE id = ?',
            (call_sheet_id,),
        ).fetchone()
        if row is None or row['status'] != 'draft':
            conn.execute('ROLLBACK')
            return False
        conn.execute(
            "UPDATE call_sheets SET status = 'published' WHERE id = ?",
            (call_sheet_id,),
        )
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise
