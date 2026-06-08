"""Report models for the Film Production PM tool.

Read-only derivations over scenes, schedule, and cast data. No writes happen
here, so none of these functions commit. The DOOD grid is implemented exactly
as prescribed in the plan's DOOD Derivation Algorithm.
"""


def get_dood_grid(conn, project_id):
    """Generate Day Out of Days grid.
    Returns: list[dict] with keys: cast_member_id, name, character_name,
             cast_id_number, days: {shoot_date: status}
    Status values: W, SW, WF, SWF, H, or '' (blank)
    """
    # 1. Get all shoot dates in order
    shoot_dates = [row['shoot_date'] for row in conn.execute(
        'SELECT DISTINCT shoot_date FROM schedule_entries WHERE project_id = ? ORDER BY shoot_date',
        (project_id,)).fetchall()]

    # 2. Get all cast members
    cast = conn.execute(
        'SELECT id, name, character_name, cast_id_number FROM cast_members WHERE project_id = ? ORDER BY cast_id_number',
        (project_id,)).fetchall()

    # 3. For each cast member, find working days
    result = []
    for member in cast:
        working_days = set()
        for row in conn.execute('''
            SELECT DISTINCT se.shoot_date
            FROM schedule_entries se
            JOIN scene_cast sc ON sc.scene_id = se.scene_id
            WHERE se.project_id = ? AND sc.cast_member_id = ?
            ORDER BY se.shoot_date
        ''', (project_id, member['id'])).fetchall():
            working_days.add(row['shoot_date'])

        if not working_days:
            result.append({
                'cast_member_id': member['id'],
                'name': member['name'],
                'character_name': member['character_name'],
                'cast_id_number': member['cast_id_number'],
                'days': {d: '' for d in shoot_dates}
            })
            continue

        sorted_working = sorted(working_days)
        first_day = sorted_working[0]
        last_day = sorted_working[-1]

        days = {}
        for d in shoot_dates:
            if d in working_days:
                if first_day == last_day and d == first_day:
                    days[d] = 'SWF'
                elif d == first_day:
                    days[d] = 'SW'
                elif d == last_day:
                    days[d] = 'WF'
                else:
                    days[d] = 'W'
            elif first_day < d < last_day:
                days[d] = 'H'
            else:
                days[d] = ''

        result.append({
            'cast_member_id': member['id'],
            'name': member['name'],
            'character_name': member['character_name'],
            'cast_id_number': member['cast_id_number'],
            'days': days
        })

    return result


def get_production_progress(conn, project_id):
    """Compute production progress statistics for a project.

    Returns: dict with keys:
        total_scenes        -- count of scenes in the project
        wrapped_scenes      -- scenes with status 'wrapped'
        scenes_by_status    -- dict {status: count} covering all valid statuses
        percent_complete    -- wrapped_scenes / total_scenes * 100 (rounded, 0 if no scenes)
        total_pages_eighths -- sum of page_count_eighths across all scenes
        wrapped_pages_eighths -- sum of page_count_eighths across wrapped scenes
        total_cast          -- count of cast members
        total_shoot_days    -- count of distinct shoot dates with schedule entries
        scheduled_scenes    -- count of scenes that have a schedule entry
    """
    # Valid scene statuses (mirror the schema CHECK constraint) so the report
    # always reports every bucket, even when zero.
    statuses = ('not_started', 'in_prep', 'ready', 'shooting', 'wrapped', 'on_hold')
    scenes_by_status = {s: 0 for s in statuses}

    for row in conn.execute(
        'SELECT status, COUNT(*) AS n FROM scenes WHERE project_id = ? GROUP BY status',
        (project_id,)).fetchall():
        # Defensive: only record statuses we know about.
        if row['status'] in scenes_by_status:
            scenes_by_status[row['status']] = row['n']

    total_scenes = sum(scenes_by_status.values())
    wrapped_scenes = scenes_by_status['wrapped']

    page_row = conn.execute(
        'SELECT '
        'COALESCE(SUM(page_count_eighths), 0) AS total_eighths, '
        "COALESCE(SUM(CASE WHEN status = 'wrapped' THEN page_count_eighths ELSE 0 END), 0) AS wrapped_eighths "
        'FROM scenes WHERE project_id = ?',
        (project_id,)).fetchone()
    total_pages_eighths = page_row['total_eighths']
    wrapped_pages_eighths = page_row['wrapped_eighths']

    total_cast = conn.execute(
        'SELECT COUNT(*) AS n FROM cast_members WHERE project_id = ?',
        (project_id,)).fetchone()['n']

    total_shoot_days = conn.execute(
        'SELECT COUNT(DISTINCT shoot_date) AS n FROM schedule_entries WHERE project_id = ?',
        (project_id,)).fetchone()['n']

    scheduled_scenes = conn.execute(
        'SELECT COUNT(DISTINCT scene_id) AS n FROM schedule_entries WHERE project_id = ?',
        (project_id,)).fetchone()['n']

    if total_scenes > 0:
        percent_complete = round(wrapped_scenes / total_scenes * 100)
    else:
        percent_complete = 0

    return {
        'total_scenes': total_scenes,
        'wrapped_scenes': wrapped_scenes,
        'scenes_by_status': scenes_by_status,
        'percent_complete': percent_complete,
        'total_pages_eighths': total_pages_eighths,
        'wrapped_pages_eighths': wrapped_pages_eighths,
        'total_cast': total_cast,
        'total_shoot_days': total_shoot_days,
        'scheduled_scenes': scheduled_scenes,
    }
