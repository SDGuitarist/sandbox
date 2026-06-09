"""Schedule model functions.

Owns the schedule_entries table. Consumed by callsheets and reports
(get_schedule_entries / get_shoot_dates are orchestration entrypoints — their
full signatures and return shapes are authoritative per the spec).
"""

import sqlite3


def _strip_color(int_ext, day_night):
    """Map a scene's INT/EXT + DAY/NIGHT to its production-strip CSS class."""
    if day_night == 'NIGHT':
        return 'strip-night-ext' if int_ext == 'EXT' else 'strip-night-int'
    return 'strip-day-ext' if int_ext == 'EXT' else 'strip-day-int'


def create_schedule_entry(conn, project_id, scene_id, location_id, shoot_date, sort_order):
    """Insert a schedule entry. Returns the new entry id, or None if the scene
    is already scheduled for this project (UNIQUE(project_id, scene_id)).

    Commits internally (BEGIN IMMEDIATE + TOCTOU duplicate check inside lock).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        # TOCTOU fence: re-check the duplicate inside the lock.
        existing = conn.execute(
            'SELECT id FROM schedule_entries WHERE project_id = ? AND scene_id = ?',
            (project_id, scene_id)
        ).fetchone()
        if existing is not None:
            conn.execute('ROLLBACK')
            return None
        cur = conn.execute(
            '''INSERT INTO schedule_entries
                   (project_id, scene_id, location_id, shoot_date, sort_order)
               VALUES (?, ?, ?, ?, ?)''',
            (project_id, scene_id, location_id, shoot_date, sort_order)
        )
        entry_id = cur.lastrowid
        conn.execute('COMMIT')
        return entry_id
    except sqlite3.IntegrityError:
        conn.execute('ROLLBACK')
        return None
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_schedule_entries(conn, project_id, shoot_date):
    """Return schedule entries for a project on a given shoot date, in sort order.

    Returns: list[dict] with keys: id, scene_id, scene_number, location_id,
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
    for r in rows:
        entry = dict(r)
        entry['strip_color_class'] = _strip_color(r['int_ext'], r['day_night'])
        entries.append(entry)
    return entries


def get_shoot_dates(conn, project_id):
    """Return the distinct shoot dates for a project, ascending.

    Returns: list[str].
    """
    rows = conn.execute(
        '''SELECT DISTINCT shoot_date FROM schedule_entries
           WHERE project_id = ? ORDER BY shoot_date''',
        (project_id,)
    ).fetchall()
    return [r['shoot_date'] for r in rows]


def reorder_schedule(conn, project_id, shoot_date, ordered_ids):
    """Persist a new sort order for a day's entries.

    `ordered_ids` is the full list of entry ids for (project_id, shoot_date), in
    the desired order. Returns True on success, False if the supplied id set does
    not exactly match the DB set for that project+date (no missing/extra/foreign).

    Commits internally (BEGIN IMMEDIATE + full ID set validation inside lock).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute(
            'SELECT id FROM schedule_entries WHERE project_id = ? AND shoot_date = ?',
            (project_id, shoot_date)
        ).fetchall()
        db_ids = {r['id'] for r in rows}
        supplied = list(ordered_ids)
        # Full set validation: same length, no dupes, exact set match.
        if len(supplied) != len(db_ids) or set(supplied) != db_ids:
            conn.execute('ROLLBACK')
            return False
        for position, entry_id in enumerate(supplied):
            conn.execute(
                '''UPDATE schedule_entries SET sort_order = ?
                   WHERE id = ? AND project_id = ? AND shoot_date = ?''',
                (position, entry_id, project_id, shoot_date)
            )
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise


def delete_schedule_entry(conn, entry_id):
    """Delete a schedule entry by id. Does NOT commit — the caller commits."""
    conn.execute('DELETE FROM schedule_entries WHERE id = ?', (entry_id,))
