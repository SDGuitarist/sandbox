"""Project model functions.

Owns the `projects` and `project_members` tables. All other blueprints read
projects via `get_project`. See the Transaction Contracts and Model Functions
sections of docs/plans/film-production-pm-plan.md -- this module is authoritative
for project creation, lookup, stats, and phase transitions.
"""

import sqlite3


# Production phase state machine -- linear, forward-only.
# development -> pre_production -> production -> post_production -> distribution
# Each phase maps to the set of phases it is allowed to transition INTO.
# distribution is terminal (no outbound transitions).
VALID_PHASE_TRANSITIONS = {
    'development': {'pre_production'},
    'pre_production': {'production'},
    'production': {'post_production'},
    'post_production': {'distribution'},
    'distribution': set(),
}


def create_project(conn, title, description, total_budget_cents, created_by) -> int:
    """Create a project and enroll the creator as a producer member.

    Returns the new project_id. Commits internally (BEGIN IMMEDIATE).
    The creating user is added to project_members with role='producer' in the
    same transaction so they can immediately access the project dashboard
    (which is guarded by require_project_member).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            '''INSERT INTO projects (title, description, total_budget_cents, created_by)
               VALUES (?, ?, ?, ?)''',
            (title, description, total_budget_cents, created_by),
        )
        project_id = cur.lastrowid
        conn.execute(
            '''INSERT INTO project_members (project_id, user_id, role)
               VALUES (?, ?, 'producer')''',
            (project_id, created_by),
        )
        conn.execute('COMMIT')
        return project_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_project(conn, project_id) -> dict | None:
    """Return a project row as a dict, or None if not found."""
    row = conn.execute(
        'SELECT * FROM projects WHERE id = ?', (project_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def get_active_project(conn) -> dict | None:
    """Return the single active project (lowest id), or None if none exist."""
    row = conn.execute(
        'SELECT * FROM projects ORDER BY id LIMIT 1'
    ).fetchone()
    return dict(row) if row is not None else None


def get_project_stats(conn, project_id) -> dict:
    """Return dashboard statistics for a project.

    Keys (read char-for-char by projects/dashboard.html):
        total_scenes, scenes_wrapped, total_budget_cents, spent_cents,
        shoot_days_count
    """
    total_scenes = conn.execute(
        'SELECT COUNT(*) AS c FROM scenes WHERE project_id = ?',
        (project_id,),
    ).fetchone()['c']

    scenes_wrapped = conn.execute(
        "SELECT COUNT(*) AS c FROM scenes WHERE project_id = ? AND status = 'wrapped'",
        (project_id,),
    ).fetchone()['c']

    project = conn.execute(
        'SELECT total_budget_cents FROM projects WHERE id = ?',
        (project_id,),
    ).fetchone()
    total_budget_cents = project['total_budget_cents'] if project is not None else 0

    spent_cents = conn.execute(
        '''SELECT COALESCE(SUM(spent_cents), 0) AS s
           FROM department_budgets WHERE project_id = ?''',
        (project_id,),
    ).fetchone()['s']

    shoot_days_count = conn.execute(
        '''SELECT COUNT(DISTINCT shoot_date) AS c
           FROM schedule_entries WHERE project_id = ?''',
        (project_id,),
    ).fetchone()['c']

    return {
        'total_scenes': total_scenes,
        'scenes_wrapped': scenes_wrapped,
        'total_budget_cents': total_budget_cents,
        'spent_cents': spent_cents,
        'shoot_days_count': shoot_days_count,
    }


def transition_project_phase(conn, project_id, new_phase) -> bool:
    """Transition a project to new_phase if the move is valid.

    Validates against VALID_PHASE_TRANSITIONS. Re-reads the current phase
    inside the lock (TOCTOU-safe) and rejects invalid transitions. Returns
    True on success, False if the project is missing or the transition is not
    permitted. Commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            'SELECT phase FROM projects WHERE id = ?', (project_id,)
        ).fetchone()
        if row is None:
            conn.execute('ROLLBACK')
            return False
        current_phase = row['phase']
        allowed = VALID_PHASE_TRANSITIONS.get(current_phase, set())
        if new_phase not in allowed:
            conn.execute('ROLLBACK')
            return False
        conn.execute(
            "UPDATE projects SET phase = ?, updated_at = datetime('now') WHERE id = ?",
            (new_phase, project_id),
        )
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise
