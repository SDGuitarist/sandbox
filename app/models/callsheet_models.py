"""Call sheet models — generate, retrieve, and publish call sheets.

generate_call_sheet is the highest-risk function in the app: it pulls data from
schedule_models, scene_models, cast_models, and location_models in a single
BEGIN IMMEDIATE transaction to produce call_sheets + call_sheet_scenes +
call_sheet_cast rows.
"""

from app.models.schedule_models import get_schedule_entries
from app.models.cast_models import get_cast_for_scenes
from app.models.location_models import get_location
from app.models.scene_models import get_scenes_by_ids


# ---------------------------------------------------------------------------
# generate_call_sheet
# Returns: int (call_sheet_id) -- commits internally (BEGIN IMMEDIATE, multi-table)
# ---------------------------------------------------------------------------
def generate_call_sheet(conn, project_id, shoot_date):
    """Create a call sheet for *shoot_date* inside *project_id*.

    Steps:
    1. Get schedule entries for date
    2. Get scene IDs, fetch scenes by IDs
    3. Get cast for those scenes, compute DOOD status (W/SW/WF/SWF/H)
    4. Get location from first entry
    5. INSERT call_sheets parent row + call_sheet_scenes + call_sheet_cast
    6. All inside BEGIN IMMEDIATE + try/except/ROLLBACK
    """
    # --- Pre-transaction reads (safe outside the lock) ---
    entries = get_schedule_entries(conn, project_id, shoot_date)
    if not entries:
        return None  # nothing scheduled for this date

    scene_ids = [e['scene_id'] for e in entries]
    scenes = get_scenes_by_ids(conn, scene_ids)

    # Cast members assigned to any of the scheduled scenes
    cast_members = get_cast_for_scenes(conn, scene_ids)

    # Location from the first schedule entry
    location_id = entries[0]['location_id'] if entries[0]['location_id'] else None
    location = get_location(conn, location_id) if location_id else None

    # --- Compute DOOD statuses for each cast member on this date ---
    # We need to know every shoot date for each cast member to derive
    # SW / W / WF / SWF / H.
    all_shoot_dates = [
        row['shoot_date']
        for row in conn.execute(
            'SELECT DISTINCT shoot_date FROM schedule_entries '
            'WHERE project_id = ? ORDER BY shoot_date',
            (project_id,),
        ).fetchall()
    ]

    cast_statuses = {}
    for member in cast_members:
        working_days = set()
        for row in conn.execute(
            '''
            SELECT DISTINCT se.shoot_date
            FROM schedule_entries se
            JOIN scene_cast sc ON sc.scene_id = se.scene_id
            WHERE se.project_id = ? AND sc.cast_member_id = ?
            ORDER BY se.shoot_date
            ''',
            (project_id, member['id']),
        ).fetchall():
            working_days.add(row['shoot_date'])

        if not working_days:
            cast_statuses[member['id']] = ''
            continue

        sorted_working = sorted(working_days)
        first_day = sorted_working[0]
        last_day = sorted_working[-1]

        if shoot_date in working_days:
            if first_day == last_day and shoot_date == first_day:
                cast_statuses[member['id']] = 'SWF'
            elif shoot_date == first_day:
                cast_statuses[member['id']] = 'SW'
            elif shoot_date == last_day:
                cast_statuses[member['id']] = 'WF'
            else:
                cast_statuses[member['id']] = 'W'
        elif first_day < shoot_date < last_day:
            cast_statuses[member['id']] = 'H'
        else:
            cast_statuses[member['id']] = ''

    # --- Determine sheet_number (next sequential for this project) ---
    max_row = conn.execute(
        'SELECT COALESCE(MAX(sheet_number), 0) AS mx FROM call_sheets WHERE project_id = ?',
        (project_id,),
    ).fetchone()
    next_sheet_number = max_row['mx'] + 1

    # --- Transactional write ---
    conn.execute('BEGIN IMMEDIATE')
    try:
        cursor = conn.execute(
            '''
            INSERT INTO call_sheets (project_id, sheet_number, shoot_date, weather_note, general_notes, status)
            VALUES (?, ?, ?, ?, ?, 'draft')
            ''',
            (
                project_id,
                next_sheet_number,
                shoot_date,
                None,
                f"Nearest hospital: {location['nearest_hospital']}" if location and location.get('nearest_hospital') else None,
            ),
        )
        call_sheet_id = cursor.lastrowid

        # Insert call_sheet_scenes
        for idx, entry in enumerate(entries):
            conn.execute(
                'INSERT INTO call_sheet_scenes (call_sheet_id, scene_id, sort_order) VALUES (?, ?, ?)',
                (call_sheet_id, entry['scene_id'], idx),
            )

        # Insert call_sheet_cast
        for member in cast_members:
            status = cast_statuses.get(member['id'], 'W')
            conn.execute(
                '''
                INSERT INTO call_sheet_cast
                    (call_sheet_id, cast_member_id, status, remarks)
                VALUES (?, ?, ?, ?)
                ''',
                (call_sheet_id, member['id'], status if status else 'W', None),
            )

        conn.execute('COMMIT')
        return call_sheet_id

    except Exception:
        conn.execute('ROLLBACK')
        raise


# ---------------------------------------------------------------------------
# get_call_sheet
# Returns: dict or None
# ---------------------------------------------------------------------------
def get_call_sheet(conn, call_sheet_id):
    """Return a single call sheet row as a dict, or None."""
    row = conn.execute(
        '''
        SELECT cs.*, p.title AS project_title
        FROM call_sheets cs
        JOIN projects p ON p.id = cs.project_id
        WHERE cs.id = ?
        ''',
        (call_sheet_id,),
    ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# get_call_sheet_scenes
# Returns: list[dict] with scene details
# ---------------------------------------------------------------------------
def get_call_sheet_scenes(conn, call_sheet_id):
    """Return scenes attached to a call sheet, ordered by sort_order."""
    rows = conn.execute(
        '''
        SELECT css.sort_order, s.id, s.scene_number, s.description,
               s.int_ext, s.day_night, s.page_count_eighths,
               l.name AS location_name
        FROM call_sheet_scenes css
        JOIN scenes s ON s.id = css.scene_id
        LEFT JOIN locations l ON l.id = s.location_id
        WHERE css.call_sheet_id = ?
        ORDER BY css.sort_order
        ''',
        (call_sheet_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# get_call_sheet_cast
# Returns: list[dict] with cast details + status
# ---------------------------------------------------------------------------
def get_call_sheet_cast(conn, call_sheet_id):
    """Return cast members on a call sheet with their DOOD status."""
    rows = conn.execute(
        '''
        SELECT csc.pickup_time, csc.makeup_time, csc.on_set_time,
               csc.status, csc.remarks,
               cm.id AS cast_member_id, cm.name, cm.character_name,
               cm.cast_id_number
        FROM call_sheet_cast csc
        JOIN cast_members cm ON cm.id = csc.cast_member_id
        WHERE csc.call_sheet_id = ?
        ORDER BY cm.cast_id_number
        ''',
        (call_sheet_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# publish_call_sheet
# Returns: bool -- commits internally (BEGIN IMMEDIATE)
# ---------------------------------------------------------------------------
def publish_call_sheet(conn, call_sheet_id):
    """Set call sheet status to 'published'. Returns True on success."""
    conn.execute('BEGIN IMMEDIATE')
    try:
        row = conn.execute(
            'SELECT status FROM call_sheets WHERE id = ?',
            (call_sheet_id,),
        ).fetchone()
        if row is None:
            conn.execute('ROLLBACK')
            return False
        if row['status'] != 'draft':
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
