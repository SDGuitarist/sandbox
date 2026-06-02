"""Department model functions.

Data owner for the departments table. Read by crew, budget, expenses,
callsheets, and reports agents.
"""


def get_departments(conn, project_id):
    """Return all departments for a project.

    Returns: list[dict] with keys: id, name, head_id, head_name
    """
    rows = conn.execute(
        '''SELECT d.id, d.name, d.head_id, u.display_name AS head_name
           FROM departments d
           LEFT JOIN users u ON u.id = d.head_id
           WHERE d.project_id = ?
           ORDER BY d.name''',
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_department(conn, department_id):
    """Return a single department or None.

    Returns: dict with keys: id, project_id, name, head_id, head_name
    """
    row = conn.execute(
        '''SELECT d.id, d.project_id, d.name, d.head_id,
                  u.display_name AS head_name
           FROM departments d
           LEFT JOIN users u ON u.id = d.head_id
           WHERE d.id = ?''',
        (department_id,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def assign_department_head(conn, department_id, user_id):
    """Assign a user as head of a department.

    Commits internally via BEGIN IMMEDIATE.
    Returns: None
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(
            'UPDATE departments SET head_id = ? WHERE id = ?',
            (user_id, department_id),
        )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
