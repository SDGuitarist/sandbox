"""Report model functions for DOOD grid and production progress."""


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
    """Get production progress statistics.
    Returns: dict with keys:
        total_scenes, scenes_wrapped, scenes_remaining,
        total_shoot_days, shoot_days_completed,
        total_page_eighths, wrapped_page_eighths
    """
    # Total scenes and status breakdown
    total_scenes = conn.execute(
        'SELECT COUNT(*) AS cnt FROM scenes WHERE project_id = ?',
        (project_id,)
    ).fetchone()['cnt']

    scenes_wrapped = conn.execute(
        "SELECT COUNT(*) AS cnt FROM scenes WHERE project_id = ? AND status = 'wrapped'",
        (project_id,)
    ).fetchone()['cnt']

    scenes_remaining = total_scenes - scenes_wrapped

    # Total shoot days (distinct dates in schedule)
    total_shoot_days = conn.execute(
        'SELECT COUNT(DISTINCT shoot_date) AS cnt FROM schedule_entries WHERE project_id = ?',
        (project_id,)
    ).fetchone()['cnt']

    # Completed shoot days: days where ALL scheduled scenes are wrapped
    # A shoot day is "completed" if every scene scheduled on that day has status = 'wrapped'
    shoot_days_completed = 0
    shoot_day_rows = conn.execute(
        'SELECT DISTINCT shoot_date FROM schedule_entries WHERE project_id = ? ORDER BY shoot_date',
        (project_id,)
    ).fetchall()
    for row in shoot_day_rows:
        not_wrapped = conn.execute('''
            SELECT COUNT(*) AS cnt
            FROM schedule_entries se
            JOIN scenes s ON s.id = se.scene_id
            WHERE se.project_id = ? AND se.shoot_date = ? AND s.status != 'wrapped'
        ''', (project_id, row['shoot_date'])).fetchone()['cnt']
        if not_wrapped == 0:
            shoot_days_completed += 1

    # Page count totals (in eighths)
    total_page_eighths = conn.execute(
        'SELECT COALESCE(SUM(page_count_eighths), 0) AS total FROM scenes WHERE project_id = ?',
        (project_id,)
    ).fetchone()['total']

    wrapped_page_eighths = conn.execute(
        "SELECT COALESCE(SUM(page_count_eighths), 0) AS total FROM scenes WHERE project_id = ? AND status = 'wrapped'",
        (project_id,)
    ).fetchone()['total']

    return {
        'total_scenes': total_scenes,
        'scenes_wrapped': scenes_wrapped,
        'scenes_remaining': scenes_remaining,
        'total_shoot_days': total_shoot_days,
        'shoot_days_completed': shoot_days_completed,
        'total_page_eighths': total_page_eighths,
        'wrapped_page_eighths': wrapped_page_eighths,
    }
