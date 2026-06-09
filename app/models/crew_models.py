"""Crew member model functions.

Owns the crew_members table. Read by callsheets, reports, and search.

Transaction contract (FC29):
- create_crew_member: BEGIN IMMEDIATE, commits internally.
- All read functions: no transaction.

Cross-boundary export (FC50): get_crew_by_department is consumed by the
callsheets routes with the exact signature and return shape below.
"""

import sqlite3


def create_crew_member(conn, project_id, name, role_title, department_id,
                       user_id=None, phone=None, email=None,
                       daily_rate_cents=0) -> int:
    """Insert a crew member. Commits internally (BEGIN IMMEDIATE).

    daily_rate_cents is an integer count of cents (the route parses the
    `daily_rate` dollars form field into cents before calling this).

    Returns the new crew_member id.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            '''INSERT INTO crew_members
                   (project_id, user_id, name, role_title, department_id,
                    phone, email, daily_rate_cents)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (project_id, user_id, name, role_title, department_id,
             phone, email, daily_rate_cents))
        crew_member_id = cur.lastrowid
        conn.execute('COMMIT')
        return crew_member_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_crew_members(conn, project_id) -> list:
    """All crew for a project, flat list ordered by department then name.

    Returns list[dict] with keys: id, name, role_title, department_name,
    phone, email, daily_rate_cents.
    """
    rows = conn.execute(
        '''SELECT c.id, c.name, c.role_title, d.name AS department_name,
                  c.phone, c.email, c.daily_rate_cents
           FROM crew_members c
           JOIN departments d ON d.id = c.department_id
           WHERE c.project_id = ?
           ORDER BY d.name, c.name''',
        (project_id,)).fetchall()
    return [dict(r) for r in rows]


def get_crew_by_department(conn, project_id) -> list:
    """Crew grouped by department (FC50 cross-boundary export).

    Consumed by the callsheets routes. Exact shape:
        [{department_name, members: [{id, name, role_title, phone}]}]

    Only departments that have at least one crew member appear, ordered by
    department name; members ordered by name.
    """
    rows = conn.execute(
        '''SELECT d.name AS department_name,
                  c.id, c.name, c.role_title, c.phone
           FROM crew_members c
           JOIN departments d ON d.id = c.department_id
           WHERE c.project_id = ?
           ORDER BY d.name, c.name''',
        (project_id,)).fetchall()

    grouped = []
    current_name = None
    current_group = None
    for r in rows:
        if r['department_name'] != current_name:
            current_name = r['department_name']
            current_group = {'department_name': current_name, 'members': []}
            grouped.append(current_group)
        current_group['members'].append({
            'id': r['id'],
            'name': r['name'],
            'role_title': r['role_title'],
            'phone': r['phone'],
        })
    return grouped


def get_crew_member(conn, crew_member_id) -> dict | None:
    """Single crew member with department name joined.

    Returns dict or None with keys: id, project_id, name, role_title,
    department_id, department_name, phone, email, daily_rate_cents.
    """
    row = conn.execute(
        '''SELECT c.id, c.project_id, c.name, c.role_title,
                  c.department_id, d.name AS department_name,
                  c.phone, c.email, c.daily_rate_cents
           FROM crew_members c
           JOIN departments d ON d.id = c.department_id
           WHERE c.id = ?''',
        (crew_member_id,)).fetchone()
    return dict(row) if row else None
