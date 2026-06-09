"""Department model functions.

Owns the `departments` table. Read by crew, budget, expenses, callsheets,
and reports agents. `get_departments` is the highest fan-out export in this
build (consumed by departments routes, callsheets routes, crew routes), so its
return shape is load-bearing across three surfaces.
"""


def get_departments(conn, project_id) -> list:
    """Return all departments for a project.

    Returns: list[dict] with keys: id, name, head_id, head_name
    (head_name is None when no head is assigned). Read-only, does not commit.
    """
    rows = conn.execute(
        '''SELECT d.id        AS id,
                  d.name      AS name,
                  d.head_id   AS head_id,
                  u.display_name AS head_name
             FROM departments d
             LEFT JOIN users u ON u.id = d.head_id
            WHERE d.project_id = ?
            ORDER BY d.name''',
        (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def get_department(conn, department_id) -> dict | None:
    """Return a single department by id, or None if not found.

    Returns: dict or None with keys: id, project_id, name, head_id, head_name.
    Includes project_id so callers can perform IDOR project-scope checks.
    Read-only, does not commit.
    """
    row = conn.execute(
        '''SELECT d.id          AS id,
                  d.project_id  AS project_id,
                  d.name        AS name,
                  d.head_id     AS head_id,
                  u.display_name AS head_name
             FROM departments d
             LEFT JOIN users u ON u.id = d.head_id
            WHERE d.id = ?''',
        (department_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def assign_department_head(conn, department_id, user_id) -> None:
    """Assign a user as the head of a department.

    Transaction Contract: BEGIN IMMEDIATE, commits internally,
    try/except/ROLLBACK on failure (FC29). Returns None.

    Caller is responsible for validating that user_id exists and is a member
    of the project (per Input Validation Prescriptions).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(
            'UPDATE departments SET head_id = ? WHERE id = ?',
            (user_id, department_id)
        )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
