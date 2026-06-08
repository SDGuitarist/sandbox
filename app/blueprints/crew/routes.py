"""Crew blueprint routes.

Paths are RELATIVE to the /crew url_prefix registered in create_app (FC7).

Authorization (Authorization Matrix):
- list / detail: any project member (require_project_member).
- new / create / edit: producer, ad, department_head (require_role), AND a
  department_head is scoped to departments they head (head_id == g.user['id']).
  Producer and AD are unrestricted; the scope checks fire ONLY for heads.

Cross-boundary imports (FC50):
- get_departments from department_models (form dropdown + scope check).
- index_entity / remove_entity from search_models (FTS5 single-writer).
- get_db from app.database.
- login_required / require_project_member / require_role from auth routes.
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g, abort
)

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role
)
from app.models.crew_models import (
    create_crew_member, get_crew_members, get_crew_member
)
from app.models.department_models import get_departments
from app.models.search_models import index_entity, remove_entity

bp = Blueprint('crew', __name__)


# --- Department-head ownership helpers (F-H6) -------------------------------

def _allowed_dept_ids(conn, project_id):
    """Set of department ids this user heads. Empty for non-heads."""
    return {d['id'] for d in get_departments(conn, project_id)
            if d['head_id'] == g.user['id']}


def _is_head():
    return g.member['role'] == 'department_head'


def _parse_department_id():
    """Guarded parse of the department_id form field (FC4 / parse-safety).

    Returns int or None. None means the caller should flash + redirect; a raw
    int() on missing/non-numeric input would be a 500.
    """
    try:
        return int(request.form['department_id'])
    except (KeyError, ValueError):
        return None


def _crew_body(name, role_title):
    """FTS5 body text for a crew member."""
    return f'{name} {role_title}'.strip()


# --- Routes -----------------------------------------------------------------

@bp.route('/<int:project_id>', methods=['GET'])
@login_required
@require_project_member
def list(project_id):
    conn = get_db()
    crew = get_crew_members(conn, project_id)
    departments = get_departments(conn, project_id)

    # Optional department filter (?department_id=).
    selected_department_id = None
    raw = request.args.get('department_id')
    if raw:
        try:
            selected_department_id = int(raw)
        except ValueError:
            selected_department_id = None
        if selected_department_id is not None:
            crew = [c for c in crew
                    if c['department_name'] in {
                        d['name'] for d in departments
                        if d['id'] == selected_department_id}]

    return render_template(
        'crew/list.html',
        crew=crew,
        departments=departments,
        selected_department_id=selected_department_id)


@bp.route('/<int:project_id>/new', methods=['GET'])
@login_required
@require_project_member
@require_role('producer', 'ad', 'department_head')
def new(project_id):
    conn = get_db()
    departments = get_departments(conn, project_id)
    if _is_head():
        allowed = _allowed_dept_ids(conn, project_id)
        if not allowed:
            abort(403)  # head of nothing
        departments = [d for d in departments if d['id'] in allowed]
    return render_template('crew/new.html', departments=departments)


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad', 'department_head')
def create(project_id):
    conn = get_db()

    # department_head scope: must head at least one department.
    if _is_head() and not _allowed_dept_ids(conn, project_id):
        abort(403)

    name = (request.form.get('name') or '').strip()
    role_title = (request.form.get('role_title') or '').strip()
    phone = (request.form.get('phone') or '').strip() or None
    email = (request.form.get('email') or '').strip() or None

    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('crew.new', project_id=project_id))
    if not role_title:
        flash('Role title is required', 'error')
        return redirect(url_for('crew.new', project_id=project_id))

    department_id = _parse_department_id()
    if department_id is None:
        flash('Department is required', 'error')
        return redirect(url_for('crew.new', project_id=project_id))

    # department_id must exist in this project.
    dept_ids = {d['id'] for d in get_departments(conn, project_id)}
    if department_id not in dept_ids:
        flash('Department not found', 'error')
        return redirect(url_for('crew.new', project_id=project_id))

    # department_head: target department must be one they head.
    if _is_head() and department_id not in _allowed_dept_ids(conn, project_id):
        abort(403)

    # daily_rate (dollars) -> integer cents (FC55). Optional; default 0.
    daily_rate_cents = 0
    raw_rate = (request.form.get('daily_rate') or '').strip()
    if raw_rate:
        try:
            daily_rate_cents = int(round(float(raw_rate) * 100))
        except (ValueError, TypeError):
            flash('Invalid amount', 'error')
            return redirect(url_for('crew.new', project_id=project_id))
        if daily_rate_cents < 0:
            flash('Amount must be non-negative', 'error')
            return redirect(url_for('crew.new', project_id=project_id))

    crew_member_id = create_crew_member(
        conn, project_id, name, role_title, department_id,
        phone=phone, email=email, daily_rate_cents=daily_rate_cents)

    # Maintain FTS5 index (FC52 single-writer; explicit call from the route).
    index_entity(conn, 'crew', crew_member_id, name, _crew_body(name, role_title))

    flash('Crew member added', 'success')
    return redirect(url_for('crew.detail', project_id=project_id,
                            crew_member_id=crew_member_id))


@bp.route('/<int:project_id>/<int:crew_member_id>', methods=['GET'])
@login_required
@require_project_member
def detail(project_id, crew_member_id):
    conn = get_db()
    crew = get_crew_member(conn, crew_member_id)
    if crew is None or crew['project_id'] != project_id:
        abort(404)  # 404 not 403 to avoid info leak (FC35)
    return render_template('crew/detail.html', crew=crew)


@bp.route('/<int:project_id>/<int:crew_member_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad', 'department_head')
def update(project_id, crew_member_id):
    conn = get_db()

    crew = get_crew_member(conn, crew_member_id)
    if crew is None or crew['project_id'] != project_id:
        abort(404)

    # department_head scope on the EXISTING department.
    if _is_head():
        allowed = _allowed_dept_ids(conn, project_id)
        if not allowed:
            abort(403)
        if crew['department_id'] not in allowed:
            abort(404)  # existing dept not owned -> hide existence

    name = (request.form.get('name') or '').strip()
    role_title = (request.form.get('role_title') or '').strip()
    phone = (request.form.get('phone') or '').strip() or None
    email = (request.form.get('email') or '').strip() or None

    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('crew.detail', project_id=project_id,
                                crew_member_id=crew_member_id))
    if not role_title:
        flash('Role title is required', 'error')
        return redirect(url_for('crew.detail', project_id=project_id,
                                crew_member_id=crew_member_id))

    department_id = _parse_department_id()
    if department_id is None:
        flash('Department is required', 'error')
        return redirect(url_for('crew.detail', project_id=project_id,
                                crew_member_id=crew_member_id))

    dept_ids = {d['id'] for d in get_departments(conn, project_id)}
    if department_id not in dept_ids:
        flash('Department not found', 'error')
        return redirect(url_for('crew.detail', project_id=project_id,
                                crew_member_id=crew_member_id))

    # department_head: target department must be owned too.
    if _is_head() and department_id not in _allowed_dept_ids(conn, project_id):
        abort(403)

    # daily_rate (dollars) -> integer cents (FC55). Optional; default 0.
    daily_rate_cents = 0
    raw_rate = (request.form.get('daily_rate') or '').strip()
    if raw_rate:
        try:
            daily_rate_cents = int(round(float(raw_rate) * 100))
        except (ValueError, TypeError):
            flash('Invalid amount', 'error')
            return redirect(url_for('crew.detail', project_id=project_id,
                                    crew_member_id=crew_member_id))
        if daily_rate_cents < 0:
            flash('Amount must be non-negative', 'error')
            return redirect(url_for('crew.detail', project_id=project_id,
                                    crew_member_id=crew_member_id))

    # No model update function in the spec contract; perform the UPDATE here
    # in a single transaction together with the FTS5 re-index (FC52).
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute(
            '''UPDATE crew_members
               SET name = ?, role_title = ?, department_id = ?,
                   phone = ?, email = ?, daily_rate_cents = ?
               WHERE id = ?''',
            (name, role_title, department_id, phone, email,
             daily_rate_cents, crew_member_id))
        remove_entity(conn, 'crew', crew_member_id)
        index_entity(conn, 'crew', crew_member_id, name,
                     _crew_body(name, role_title))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    flash('Crew member updated', 'success')
    return redirect(url_for('crew.detail', project_id=project_id,
                            crew_member_id=crew_member_id))
