"""Department routes: list, detail, head assignment.

Blueprint: departments, url_prefix=/departments
"""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.database import get_db
from app.models.department_models import assign_department_head, get_department, get_departments

bp = Blueprint('departments', __name__)


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    """Show all departments for this project."""
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
    """Show department detail with crew roster."""
    conn = get_db()
    dept = get_department(conn, department_id)
    if dept is None:
        abort(404)
    # IDOR check: department must belong to the current project
    if dept['project_id'] != project_id:
        abort(404)

    # Fetch crew members assigned to this department
    crew_rows = conn.execute(
        '''SELECT id, name, role_title, phone, email, daily_rate_cents
           FROM crew_members
           WHERE department_id = ? AND project_id = ?
           ORDER BY name''',
        (department_id, project_id),
    ).fetchall()
    crew = [dict(r) for r in crew_rows]

    # Fetch project members for the head-assignment dropdown (producer only)
    members = []
    if g.member['role'] == 'producer':
        member_rows = conn.execute(
            '''SELECT u.id, u.display_name
               FROM project_members pm
               JOIN users u ON u.id = pm.user_id
               WHERE pm.project_id = ?
               ORDER BY u.display_name''',
            (project_id,),
        ).fetchall()
        members = [dict(r) for r in member_rows]

    return render_template(
        'departments/detail.html',
        project=g.project,
        dept=dept,
        crew=crew,
        members=members,
    )


@bp.route('/<int:project_id>/<int:department_id>/head', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def assign_head(project_id, department_id):
    """Assign a department head. Producer only."""
    conn = get_db()
    dept = get_department(conn, department_id)
    if dept is None:
        abort(404)
    # IDOR check
    if dept['project_id'] != project_id:
        abort(404)

    user_id = request.form.get('user_id', '').strip()
    if not user_id:
        flash('User is required.', 'error')
        return redirect(url_for('departments.detail', project_id=project_id, department_id=department_id))

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        flash('User not found.', 'error')
        return redirect(url_for('departments.detail', project_id=project_id, department_id=department_id))

    # Validate user_id is a project member
    member = conn.execute(
        'SELECT id FROM project_members WHERE project_id = ? AND user_id = ?',
        (project_id, user_id),
    ).fetchone()
    if member is None:
        flash('User not found.', 'error')
        return redirect(url_for('departments.detail', project_id=project_id, department_id=department_id))

    assign_department_head(conn, department_id, user_id)
    flash('Department head assigned.', 'success')
    return redirect(url_for('departments.detail', project_id=project_id, department_id=department_id))
