"""Crew blueprint -- CRUD for crew members.

url_prefix=/crew
Cross-boundary imports:
  - get_departments from department_models (form dropdown)
  - index_entity, remove_entity from search_models (search index sync)
"""
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, abort, g
)
from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role
)
from app.models.crew_models import (
    create_crew_member, get_crew_members, get_crew_member, update_crew_member
)
from app.models.department_models import get_departments
from app.models.search_models import index_entity, remove_entity

bp = Blueprint('crew', __name__)


def _get_head_department_id(conn, project_id, user_id):
    """Return the department_id where this user is head, or None."""
    row = conn.execute(
        'SELECT id FROM departments WHERE project_id = ? AND head_id = ?',
        (project_id, user_id)
    ).fetchone()
    if row is None:
        return None
    return row['id']


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def list(project_id):
    """List all crew members for this project."""
    conn = get_db()
    crew = get_crew_members(conn, project_id)
    return render_template('crew/list.html', project=g.project, crew=crew)


@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'ad', 'department_head')
def new(project_id):
    """Show form to add a new crew member."""
    conn = get_db()
    departments = get_departments(conn, project_id)

    # Department heads can only add to their own department
    if g.member['role'] == 'department_head':
        head_dept_id = _get_head_department_id(conn, project_id, g.user['id'])
        if head_dept_id is None:
            abort(403)
        departments = [d for d in departments if d['id'] == head_dept_id]

    return render_template('crew/new.html', project=g.project,
                           departments=departments)


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad', 'department_head')
def create(project_id):
    """Create a new crew member."""
    conn = get_db()

    name = request.form.get('name', '').strip()
    role_title = request.form.get('role_title', '').strip()
    department_id_str = request.form.get('department_id', '')
    phone = request.form.get('phone', '').strip() or None
    email = request.form.get('email', '').strip() or None
    daily_rate_str = request.form.get('daily_rate', '').strip()

    # Validation: name required
    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('crew.new', project_id=project_id))

    # Validation: role_title required
    if not role_title:
        flash('Role/title is required', 'error')
        return redirect(url_for('crew.new', project_id=project_id))

    # Validation: department_id must exist in project
    try:
        department_id = int(department_id_str)
    except (ValueError, TypeError):
        flash('Department is required', 'error')
        return redirect(url_for('crew.new', project_id=project_id))

    departments = get_departments(conn, project_id)
    dept_ids = {d['id'] for d in departments}
    if department_id not in dept_ids:
        flash('Invalid department', 'error')
        return redirect(url_for('crew.new', project_id=project_id))

    # Department head: can only add to own department
    if g.member['role'] == 'department_head':
        head_dept_id = _get_head_department_id(conn, project_id, g.user['id'])
        if head_dept_id is None or department_id != head_dept_id:
            abort(403)

    # Parse daily rate (dollars to cents)
    daily_rate_cents = 0
    if daily_rate_str:
        try:
            daily_rate_cents = int(round(float(daily_rate_str) * 100))
        except (ValueError, TypeError):
            flash('Invalid daily rate', 'error')
            return redirect(url_for('crew.new', project_id=project_id))
        if daily_rate_cents < 0:
            flash('Daily rate must be zero or positive', 'error')
            return redirect(url_for('crew.new', project_id=project_id))

    crew_member_id = create_crew_member(
        conn, project_id, name, role_title, department_id,
        phone=phone, email=email, daily_rate_cents=daily_rate_cents
    )

    # Index for search
    index_entity(conn, 'crew_member', crew_member_id,
                 f'{name} {role_title}')

    flash('Crew member added', 'success')
    return redirect(url_for('crew.detail', project_id=project_id,
                            crew_member_id=crew_member_id))


@bp.route('/<int:project_id>/<int:crew_member_id>')
@login_required
@require_project_member
def detail(project_id, crew_member_id):
    """Show crew member detail."""
    conn = get_db()
    member = get_crew_member(conn, crew_member_id)

    if member is None:
        abort(404)

    # IDOR check: crew member must belong to this project
    if member['project_id'] != project_id:
        abort(404)

    # Check if current user can edit
    can_edit = g.member['role'] in ('producer', 'ad')
    if g.member['role'] == 'department_head':
        head_dept_id = _get_head_department_id(conn, project_id, g.user['id'])
        if head_dept_id == member['department_id']:
            can_edit = True

    departments = get_departments(conn, project_id)

    return render_template('crew/detail.html', project=g.project,
                           member=member, can_edit=can_edit,
                           departments=departments)


@bp.route('/<int:project_id>/<int:crew_member_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad', 'department_head')
def update(project_id, crew_member_id):
    """Update an existing crew member."""
    conn = get_db()
    member = get_crew_member(conn, crew_member_id)

    if member is None:
        abort(404)

    # IDOR check: crew member must belong to this project
    if member['project_id'] != project_id:
        abort(404)

    # Department head: can only edit their own department's crew
    if g.member['role'] == 'department_head':
        head_dept_id = _get_head_department_id(conn, project_id, g.user['id'])
        if head_dept_id is None or member['department_id'] != head_dept_id:
            abort(403)

    name = request.form.get('name', '').strip()
    role_title = request.form.get('role_title', '').strip()
    department_id_str = request.form.get('department_id', '')
    phone = request.form.get('phone', '').strip() or None
    email = request.form.get('email', '').strip() or None
    daily_rate_str = request.form.get('daily_rate', '').strip()

    # Validation: name required
    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('crew.detail', project_id=project_id,
                                crew_member_id=crew_member_id))

    # Validation: role_title required
    if not role_title:
        flash('Role/title is required', 'error')
        return redirect(url_for('crew.detail', project_id=project_id,
                                crew_member_id=crew_member_id))

    # Validation: department_id must exist in project
    try:
        department_id = int(department_id_str)
    except (ValueError, TypeError):
        flash('Department is required', 'error')
        return redirect(url_for('crew.detail', project_id=project_id,
                                crew_member_id=crew_member_id))

    departments = get_departments(conn, project_id)
    dept_ids = {d['id'] for d in departments}
    if department_id not in dept_ids:
        flash('Invalid department', 'error')
        return redirect(url_for('crew.detail', project_id=project_id,
                                crew_member_id=crew_member_id))

    # Department head: can only assign to own department
    if g.member['role'] == 'department_head':
        head_dept_id = _get_head_department_id(conn, project_id, g.user['id'])
        if head_dept_id is None or department_id != head_dept_id:
            abort(403)

    # Parse daily rate (dollars to cents)
    daily_rate_cents = 0
    if daily_rate_str:
        try:
            daily_rate_cents = int(round(float(daily_rate_str) * 100))
        except (ValueError, TypeError):
            flash('Invalid daily rate', 'error')
            return redirect(url_for('crew.detail', project_id=project_id,
                                    crew_member_id=crew_member_id))
        if daily_rate_cents < 0:
            flash('Daily rate must be zero or positive', 'error')
            return redirect(url_for('crew.detail', project_id=project_id,
                                    crew_member_id=crew_member_id))

    update_crew_member(conn, crew_member_id, name, role_title, department_id,
                       phone=phone, email=email,
                       daily_rate_cents=daily_rate_cents)

    # Update search index
    index_entity(conn, 'crew_member', crew_member_id,
                 f'{name} {role_title}')

    flash('Crew member updated', 'success')
    return redirect(url_for('crew.detail', project_id=project_id,
                            crew_member_id=crew_member_id))
