"""Department routes: list, detail (with crew roster), head assignment.

Authorization (per Authorization Matrix):
  GET  /<pid>             -> login_required + require_project_member
  GET  /<pid>/<did>       -> login_required + require_project_member + dept.project_id == pid
  POST /<pid>/<did>/head  -> login_required + require_project_member + require_role('producer')
                             + dept.project_id == pid
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required,
    require_project_member,
    require_role,
)
from app.models.department_models import (
    get_departments,
    get_department,
    assign_department_head,
)

bp = Blueprint('departments', __name__)


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    conn = get_db()
    departments = get_departments(conn, project_id)
    return render_template(
        'departments/list.html',
        project=g.project,
        departments=departments,
    )


@bp.route('/<int:project_id>/<int:department_id>')
@login_required
@require_project_member
def detail(project_id, department_id):
    conn = get_db()
    department = get_department(conn, department_id)
    if department is None:
        abort(404)
    # IDOR prevention (FC35): use 404 not 403 to avoid info leak.
    if department['project_id'] != project_id:
        abort(404)

    # Crew roster scoped to this department (read-only query on owned join).
    crew_rows = conn.execute(
        '''SELECT id, name, role_title, phone, email
             FROM crew_members
            WHERE project_id = ? AND department_id = ?
            ORDER BY role_title, name''',
        (project_id, department_id)
    ).fetchall()
    crew = [dict(row) for row in crew_rows]

    # Project members eligible to be assigned as head.
    member_rows = conn.execute(
        '''SELECT u.id AS id, u.display_name AS display_name
             FROM project_members pm
             JOIN users u ON u.id = pm.user_id
            WHERE pm.project_id = ?
            ORDER BY u.display_name''',
        (project_id,)
    ).fetchall()
    members = [dict(row) for row in member_rows]

    return render_template(
        'departments/detail.html',
        project=g.project,
        department=department,
        crew=crew,
        members=members,
    )


@bp.route('/<int:project_id>/<int:department_id>/head', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def assign_head(project_id, department_id):
    conn = get_db()

    department = get_department(conn, department_id)
    if department is None:
        abort(404)
    # IDOR prevention (FC35): department must belong to this project.
    if department['project_id'] != project_id:
        abort(404)

    # Validate user_id input (per Input Validation Prescriptions).
    raw_user_id = (request.form.get('user_id') or '').strip()
    try:
        user_id = int(raw_user_id)
    except (ValueError, TypeError):
        flash('User not found', 'error')
        return redirect(url_for('departments.detail',
                                project_id=project_id,
                                department_id=department_id))

    # user_id must exist AND be a member of this project.
    member = conn.execute(
        'SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?',
        (project_id, user_id)
    ).fetchone()
    if member is None:
        flash('User not found', 'error')
        return redirect(url_for('departments.detail',
                                project_id=project_id,
                                department_id=department_id))

    assign_department_head(conn, department_id, user_id)
    flash('Department head assigned.', 'success')
    return redirect(url_for('departments.detail',
                            project_id=project_id,
                            department_id=department_id))
