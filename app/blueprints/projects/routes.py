"""Projects blueprint -- CRUD, dashboard, phase transitions.

Blueprint: bp = Blueprint('projects', __name__)
url_prefix=/projects (registered in app factory).
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort

from app.database import get_db
from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.models.project_models import (
    create_project,
    get_project,
    get_project_stats,
    update_project,
    transition_project_phase,
    VALID_PHASE_TRANSITIONS,
    PHASE_LABELS,
)

bp = Blueprint('projects', __name__)


@bp.route('/new', methods=['GET'])
@login_required
def new():
    """Show the create-project form."""
    return render_template('projects/new.html')


@bp.route('/', methods=['POST'])
@login_required
def create():
    """Handle project creation form submission.

    Validation: title required, stripped, 1-200 chars.
    Budget defaults to 0 cents on creation.
    """
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    if not title or len(title) > 200:
        flash('Title is required (max 200 characters).', 'error')
        return redirect(url_for('projects.new'))

    conn = get_db()
    project_id = create_project(conn, title, description, 0, g.user['id'])
    flash('Project created.', 'success')
    return redirect(url_for('projects.dashboard', project_id=project_id))


@bp.route('/<int:project_id>', methods=['GET'])
@login_required
@require_project_member
def dashboard(project_id):
    """Project dashboard -- shows title, phase, budget, scene progress."""
    conn = get_db()
    project = get_project(conn, project_id)
    if project is None:
        abort(404)
    stats = get_project_stats(conn, project_id)
    return render_template(
        'projects/dashboard.html',
        project=project,
        stats=stats,
        phase_labels=PHASE_LABELS,
        valid_transitions=VALID_PHASE_TRANSITIONS,
    )


@bp.route('/<int:project_id>/edit', methods=['GET'])
@login_required
@require_project_member
@require_role('producer')
def edit(project_id):
    """Show the edit-project form (producer only)."""
    return render_template(
        'projects/edit.html',
        project=g.project,
        phase_labels=PHASE_LABELS,
        valid_transitions=VALID_PHASE_TRANSITIONS,
    )


@bp.route('/<int:project_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def update(project_id):
    """Handle project edit form submission (producer only).

    Validation: title required 1-200, budget int >= 0.
    """
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    budget_raw = request.form.get('total_budget', '').strip()

    if not title or len(title) > 200:
        flash('Title is required (max 200 characters).', 'error')
        return redirect(url_for('projects.edit', project_id=project_id))

    # Parse budget: user enters dollars, we store cents
    try:
        total_budget_cents = int(round(float(budget_raw) * 100)) if budget_raw else 0
    except (ValueError, TypeError):
        flash('Invalid budget amount.', 'error')
        return redirect(url_for('projects.edit', project_id=project_id))

    if total_budget_cents < 0:
        flash('Budget cannot be negative.', 'error')
        return redirect(url_for('projects.edit', project_id=project_id))

    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    try:
        update_project(conn, project_id, title, description, total_budget_cents)
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
    """Advance project phase (producer only).

    Validation: new_phase must be in VALID_TRANSITIONS[current_phase].
    """
    new_phase = request.form.get('new_phase', '').strip()

    # Validate the requested phase is a known phase value
    if new_phase not in VALID_PHASE_TRANSITIONS:
        flash('Invalid phase.', 'error')
        return redirect(url_for('projects.dashboard', project_id=project_id))

    conn = get_db()
    success = transition_project_phase(conn, project_id, new_phase)

    if not success:
        flash('Invalid phase transition.', 'error')
    else:
        flash(f'Phase advanced to {PHASE_LABELS.get(new_phase, new_phase)}.', 'success')

    return redirect(url_for('projects.dashboard', project_id=project_id))
