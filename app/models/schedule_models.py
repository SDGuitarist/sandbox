"""Schedule models -- shoot day management with TOCTOU-safe writes."""

import sqlite3


def _strip_color(int_ext, day_night):
    """Derive strip color CSS class from scene properties.

    Strip colors follow the film industry standard:
    - DAY + EXT = yellow
    - DAY + INT = white
    - NIGHT + INT = blue
    - NIGHT + EXT = green
    INT/EXT and DAWN/DUSK fall through to the DAY/EXT default.
    """
    if day_night == 'NIGHT':
        return 'strip-night-ext' if int_ext == 'EXT' else 'strip-night-int'
    return 'strip-day-ext' if int_ext == 'EXT' else 'strip-day-int'


def create_schedule_entry(conn, project_id, scene_id, location_id, shoot_date, sort_order):
    """Create a schedule entry with TOCTOU duplicate check.

    Returns int (entry_id) on success, None if the scene is already scheduled
    (same scene on a different day counts as a conflict because of the
    UNIQUE(project_id, scene_id) constraint on schedule_entries).

    Commits internally via BEGIN IMMEDIATE.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        # TOCTOU fence: check for duplicate scene scheduling inside the lock
        existing = conn.execute(
            'SELECT id FROM schedule_entries WHERE project_id = ? AND scene_id = ?',
            (project_id, scene_id)
        ).fetchone()
        if existing is not None:
            conn.execute('ROLLBACK')
            return None

        cursor = conn.execute(
            '''INSERT INTO schedule_entries (project_id, scene_id, location_id, shoot_date, sort_order)
               VALUES (?, ?, ?, ?, ?)''',
            (project_id, scene_id, location_id, shoot_date, sort_order)
        )
        entry_id = cursor.lastrowid
        conn.execute('COMMIT')
        return entry_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_schedule_entries(conn, project_id, shoot_date):
    """Get schedule entries for a project+date, joined with scene data.

    Returns list[dict] with keys: id, scene_id, scene_number, location_id,
    location_name, shoot_date, sort_order, int_ext, day_night,
    page_count_eighths, strip_color_class.
    """
    rows = conn.execute(
        '''SELECT se.id, se.scene_id, s.scene_number, se.location_id,
                  l.name AS location_name, se.shoot_date, se.sort_order,
                  s.int_ext, s.day_night, s.page_count_eighths
           FROM schedule_entries se
           JOIN scenes s ON s.id = se.scene_id
           LEFT JOIN locations l ON l.id = se.location_id
           WHERE se.project_id = ? AND se.shoot_date = ?
           ORDER BY se.sort_order''',
        (project_id, shoot_date)
    ).fetchall()

    entries = []
    for row in rows:
        entry = dict(row)
        entry['strip_color_class'] = _strip_color(entry['int_ext'], entry['day_night'])
        entries.append(entry)
    return entries


def get_shoot_dates(conn, project_id):
    """Get distinct shoot dates for a project in chronological order.

    Returns list[str] of date strings (YYYY-MM-DD).
    """
    rows = conn.execute(
        'SELECT DISTINCT shoot_date FROM schedule_entries WHERE project_id = ? ORDER BY shoot_date',
        (project_id,)
    ).fetchall()
    return [row['shoot_date'] for row in rows]


def reorder_schedule(conn, project_id, shoot_date, ordered_ids):
    """Reorder schedule entries for a project+date.

    Validates that the provided IDs exactly match the DB set for that
    project+date (no missing, no extra, no duplicates).

    Returns True on success, False on validation failure.
    Commits internally via BEGIN IMMEDIATE.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Full ID set validation inside the lock
        db_rows = conn.execute(
            'SELECT id FROM schedule_entries WHERE project_id = ? AND shoot_date = ?',
            (project_id, shoot_date)
        ).fetchall()
        db_ids = {row['id'] for row in db_rows}

        # Check for duplicates in the provided list
        if len(ordered_ids) != len(set(ordered_ids)):
            conn.execute('ROLLBACK')
            return False

        provided_ids = set(ordered_ids)

        if provided_ids != db_ids:
            conn.execute('ROLLBACK')
            return False

        # Batch UPDATE sort_order
        for new_order, entry_id in enumerate(ordered_ids):
            conn.execute(
                'UPDATE schedule_entries SET sort_order = ? WHERE id = ?',
                (new_order, entry_id)
            )

        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise


def delete_schedule_entry(conn, entry_id):
    """Delete a schedule entry. Does NOT commit -- caller must manage transaction."""
    conn.execute('DELETE FROM schedule_entries WHERE id = ?', (entry_id,))
