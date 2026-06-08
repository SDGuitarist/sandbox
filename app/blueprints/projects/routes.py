"""Project routes -- CRUD, dashboard, and phase transitions.

url_prefix='/projects' (set in app factory). All paths below are RELATIVE to
that prefix. See the Route Table, Authorization Matrix, and Input Validation
Prescriptions in docs/plans/film-production-pm-plan.md.
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g
)

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role
)
from app.models.project_models import (
    create_project, get_project, get_project_stats,
    transition_project_phase, VALID_PHASE_TRANSITIONS,
)

bp = Blueprint('projects', __name__)


@bp.route('/new')
@login_required
def new():
    """Render the new-project form."""
    return render_template('projects/new.html')


@bp.route('/', methods=['POST'])
@login_required
def create():
    """Create a project owned by the current user, then go to its dashboard."""
    title = (request.form.get('title') or '').strip()
    description = (request.form.get('description') or '').strip()

    if not title or len(title) > 200:
        flash('Title is required and must be 1-200 characters.', 'error')
        return redirect(url_for('projects.new'))

    conn = get_db()
    project_id = create_project(conn, title, description, 0, g.user['id'])
    flash('Project created.', 'success')
    return redirect(url_for('projects.dashboard', project_id=project_id))


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def dashboard(project_id):
    """Project overview with production stats."""
    conn = get_db()
    return render_template(
        'projects/dashboard.html',
        project=get_project(conn, project_id),
        stats=get_project_stats(conn, project_id),
    )


@bp.route('/<int:project_id>/edit')
@login_required
@require_project_member
@require_role('producer')
def edit(project_id):
    """Render the edit form for a project."""
    conn = get_db()
    return render_template(
        'projects/edit.html',
        project=get_project(conn, project_id),
    )


@bp.route('/<int:project_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def update(project_id):
    """Update a project's title, description, and total budget."""
    title = (request.form.get('title') or '').strip()
    description = (request.form.get('description') or '').strip()

    if not title or len(title) > 200:
        flash('Title is required and must be 1-200 characters.', 'error')
        return redirect(url_for('projects.edit', project_id=project_id))

    # Money: form field is `total_budget` in dollars (suffix-free).
    # Parse to integer cents; reject non-numeric or negative values.
    try:
        total_budget_cents = int(round(float(request.form.get('total_budget', '0')) * 100))
    except (ValueError, TypeError):
        flash('Invalid budget amount.', 'error')
        return redirect(url_for('projects.edit', project_id=project_id))

    if total_budget_cents < 0:
        flash('Budget must be zero or positive.', 'error')
        return redirect(url_for('projects.edit', project_id=project_id))

    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute(
            '''UPDATE projects
               SET title = ?, description = ?, total_budget_cents = ?,
                   updated_at = datetime('now')
               WHERE id = ?''',
            (title, description, total_budget_cents, project_id),
        )
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    flash('Project updated.', 'success')
    return redirect(url_for('projects.dashboard', project_id=project_id))


@bp.route('/<int:project_id>/phase', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def transition_phase(project_id):
    """Advance the project to a new production phase if the move is valid."""
    new_phase = (request.form.get('new_phase') or '').strip()

    current_phase = g.project['phase']
    if new_phase not in VALID_PHASE_TRANSITIONS.get(current_phase, set()):
        flash('Invalid transition.', 'error')
        return redirect(url_for('projects.dashboard', project_id=project_id))

    conn = get_db()
    if transition_project_phase(conn, project_id, new_phase):
        flash('Phase updated.', 'success')
    else:
        flash('Invalid transition.', 'error')
    return redirect(url_for('projects.dashboard', project_id=project_id))
