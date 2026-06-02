"""Crew member model functions.

Owns the crew_members table. Read by callsheets, reports, and search agents.
"""
import sqlite3


def create_crew_member(conn, project_id, name, role_title, department_id,
                       user_id=None, phone=None, email=None,
                       daily_rate_cents=0):
    """Create a crew member record.

    Returns: int (crew_member_id) -- commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            '''INSERT INTO crew_members
               (project_id, name, role_title, department_id, user_id,
                phone, email, daily_rate_cents)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (project_id, name, role_title, department_id, user_id,
             phone, email, daily_rate_cents)
        )
        crew_member_id = cursor.lastrowid
        conn.execute('COMMIT')
        return crew_member_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_crew_members(conn, project_id):
    """Get all crew members for a project.

    Returns: list[dict] with keys: id, name, role_title, department_name,
             phone, email, daily_rate_cents.
    """
    rows = conn.execute(
        '''SELECT cm.id, cm.name, cm.role_title, d.name AS department_name,
                  cm.phone, cm.email, cm.daily_rate_cents
           FROM crew_members cm
           JOIN departments d ON d.id = cm.department_id
           WHERE cm.project_id = ?
           ORDER BY d.name, cm.name''',
        (project_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def get_crew_by_department(conn, project_id):
    """Get crew members grouped by department.

    Returns: list[dict] with structure:
        [{department_name, members: [{id, name, role_title, phone}]}]
    Used by callsheets routes for call sheet detail page.
    """
    rows = conn.execute(
        '''SELECT cm.id, cm.name, cm.role_title, cm.phone,
                  d.name AS department_name
           FROM crew_members cm
           JOIN departments d ON d.id = cm.department_id
           WHERE cm.project_id = ?
           ORDER BY d.name, cm.name''',
        (project_id,)
    ).fetchall()

    departments = {}
    for row in rows:
        dept_name = row['department_name']
        if dept_name not in departments:
            departments[dept_name] = {
                'department_name': dept_name,
                'members': []
            }
        departments[dept_name]['members'].append({
            'id': row['id'],
            'name': row['name'],
            'role_title': row['role_title'],
            'phone': row['phone']
        })

    return list(departments.values())


def get_crew_member(conn, crew_member_id):
    """Get a single crew member by ID.

    Returns: dict or None with all crew_members columns plus department_name.
    """
    row = conn.execute(
        '''SELECT cm.*, d.name AS department_name
           FROM crew_members cm
           JOIN departments d ON d.id = cm.department_id
           WHERE cm.id = ?''',
        (crew_member_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def update_crew_member(conn, crew_member_id, name, role_title, department_id,
                       phone=None, email=None, daily_rate_cents=0):
    """Update a crew member record.

    Returns: None -- commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(
            '''UPDATE crew_members
               SET name = ?, role_title = ?, department_id = ?,
                   phone = ?, email = ?, daily_rate_cents = ?
               WHERE id = ?''',
            (name, role_title, department_id, phone, email,
             daily_rate_cents, crew_member_id)
        )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
