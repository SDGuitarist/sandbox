"""Project model functions.

Owns: projects, project_members tables.
Transaction pattern: BEGIN IMMEDIATE + try/except/ROLLBACK for all write functions.
"""


# Valid phase transition map (linear only):
# development -> pre_production -> production -> post_production -> distribution
VALID_PHASE_TRANSITIONS = {
    'development': ['pre_production'],
    'pre_production': ['production'],
    'production': ['post_production'],
    'post_production': ['distribution'],
    'distribution': [],
}

PHASE_LABELS = {
    'development': 'Development',
    'pre_production': 'Pre-Production',
    'production': 'Production',
    'post_production': 'Post-Production',
    'distribution': 'Distribution',
}


def create_project(conn, title, description, total_budget_cents, created_by):
    """Create a new project and add creator as producer member.

    Returns: int (project_id) -- commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            '''INSERT INTO projects (title, description, total_budget_cents, created_by)
               VALUES (?, ?, ?, ?)''',
            (title, description, total_budget_cents, created_by)
        )
        project_id = cursor.lastrowid
        conn.execute(
            '''INSERT INTO project_members (project_id, user_id, role)
               VALUES (?, ?, 'producer')''',
            (project_id, created_by)
        )
        conn.execute('COMMIT')
        return project_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_project(conn, project_id):
    """Fetch a single project by ID.

    Returns: dict or None.
    """
    row = conn.execute(
        'SELECT * FROM projects WHERE id = ?',
        (project_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_active_project(conn):
    """Get the most recently created project (single-project MVP).

    Returns: dict or None -- the single active project.
    """
    row = conn.execute(
        'SELECT * FROM projects ORDER BY created_at DESC LIMIT 1'
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_project_stats(conn, project_id):
    """Compute dashboard statistics for a project.

    Returns: dict with keys: total_scenes, scenes_wrapped, total_budget_cents,
             spent_cents, shoot_days_count.
    """
    # Total scenes
    total_scenes_row = conn.execute(
        'SELECT COUNT(*) AS cnt FROM scenes WHERE project_id = ?',
        (project_id,)
    ).fetchone()
    total_scenes = total_scenes_row['cnt'] if total_scenes_row else 0

    # Scenes wrapped (status = 'wrapped')
    wrapped_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM scenes WHERE project_id = ? AND status = 'wrapped'",
        (project_id,)
    ).fetchone()
    scenes_wrapped = wrapped_row['cnt'] if wrapped_row else 0

    # Budget: total from project row
    project_row = conn.execute(
        'SELECT total_budget_cents FROM projects WHERE id = ?',
        (project_id,)
    ).fetchone()
    total_budget_cents = project_row['total_budget_cents'] if project_row else 0

    # Spent: sum of all expenses for this project
    spent_row = conn.execute(
        'SELECT COALESCE(SUM(amount_cents), 0) AS total FROM expenses WHERE project_id = ?',
        (project_id,)
    ).fetchone()
    spent_cents = spent_row['total'] if spent_row else 0

    # Shoot days count: distinct shoot dates in schedule
    days_row = conn.execute(
        'SELECT COUNT(DISTINCT shoot_date) AS cnt FROM schedule_entries WHERE project_id = ?',
        (project_id,)
    ).fetchone()
    shoot_days_count = days_row['cnt'] if days_row else 0

    return {
        'total_scenes': total_scenes,
        'scenes_wrapped': scenes_wrapped,
        'total_budget_cents': total_budget_cents,
        'spent_cents': spent_cents,
        'shoot_days_count': shoot_days_count,
    }


def transition_project_phase(conn, project_id, new_phase):
    """Transition a project to a new phase if the transition is valid.

    Validates inside the lock (re-reads current phase after BEGIN IMMEDIATE)
    to prevent TOCTOU race conditions.

    Returns: bool -- True if transition succeeded, False if invalid.
    Commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Re-read current phase inside lock to prevent TOCTOU
        row = conn.execute(
            'SELECT phase FROM projects WHERE id = ?',
            (project_id,)
        ).fetchone()

        if row is None:
            conn.execute('ROLLBACK')
            return False

        current_phase = row['phase']
        allowed = VALID_PHASE_TRANSITIONS.get(current_phase, [])

        if new_phase not in allowed:
            conn.execute('ROLLBACK')
            return False

        conn.execute(
            "UPDATE projects SET phase = ?, updated_at = datetime('now') WHERE id = ?",
            (new_phase, project_id)
        )
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise
