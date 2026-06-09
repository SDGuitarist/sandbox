"""Budget blueprint routes. All routes are producer-only (Authorization Matrix).

Money: form fields are suffix-free dollar strings (amount, estimated, actual).
Routes parse them to integer cents and pass cents to the models.
"""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g, abort
)

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role
)
from app.models.budget_models import (
    get_budget_summary,
    get_budget_categories,
    get_department_allocation,
    allocate_budget,
    create_line_item as create_line_item_model,
    update_line_item as update_line_item_model,
)
from app.models.department_models import get_departments

bp = Blueprint('budget', __name__)


def _parse_cents(field_name, allow_zero=True):
    """Parse a suffix-free dollar form field into integer cents.

    Returns (cents, None) on success or (None, error_message) on failure.
    """
    raw = request.form.get(field_name)
    if raw is None or raw.strip() == '':
        return None, 'Invalid amount'
    try:
        cents = int(round(float(raw) * 100))
    except (ValueError, TypeError):
        return None, 'Invalid amount'
    if cents < 0:
        return None, 'Amount must not be negative'
    if not allow_zero and cents <= 0:
        return None, 'Amount must be positive'
    return cents, None


@bp.route('/<int:project_id>')
@login_required
@require_project_member
@require_role('producer')
def index(project_id):
    conn = get_db()
    summary = get_budget_summary(conn, project_id)
    categories = get_budget_categories(conn, project_id)
    departments = get_departments(conn, project_id)
    return render_template(
        'budget/index.html',
        project=g.project,
        summary=summary,
        categories=categories,
        departments=departments,
    )


@bp.route('/<int:project_id>/top-sheet')
@login_required
@require_project_member
@require_role('producer')
def top_sheet(project_id):
    conn = get_db()
    summary = get_budget_summary(conn, project_id)
    return render_template(
        'budget/top_sheet.html',
        project=g.project,
        summary=summary,
    )


@bp.route('/<int:project_id>/allocate', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def allocate(project_id):
    conn = get_db()

    # Validate department_id: must be an integer and belong to this project.
    try:
        department_id = int(request.form['department_id'])
    except (KeyError, ValueError, TypeError):
        flash('Invalid department', 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    departments = get_departments(conn, project_id)
    if not any(d['id'] == department_id for d in departments):
        flash('Invalid department', 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    amount_cents, error = _parse_cents('amount', allow_zero=True)
    if error is not None:
        flash(error, 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    ok = allocate_budget(conn, project_id, department_id, amount_cents)
    if not ok:
        remaining_cents = g.project['total_budget_cents']
        for d in departments:
            allocation = get_department_allocation(conn, d['id'])
            if allocation is not None and d['id'] != department_id:
                remaining_cents -= allocation['allocated_cents']
        flash(
            f'Allocation rejected. Remaining budget: ${remaining_cents / 100:,.2f}',
            'error'
        )
        return redirect(url_for('budget.index', project_id=project_id))

    flash('Budget allocated', 'success')
    return redirect(url_for('budget.index', project_id=project_id))


@bp.route('/<int:project_id>/line-items/new')
@login_required
@require_project_member
@require_role('producer')
def new_line_item(project_id):
    conn = get_db()
    categories = get_budget_categories(conn, project_id)
    return render_template(
        'budget/new_line_item.html',
        project=g.project,
        categories=categories,
    )


@bp.route('/<int:project_id>/line-items', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def create_line_item(project_id):
    conn = get_db()

    try:
        category_id = int(request.form['category_id'])
    except (KeyError, ValueError, TypeError):
        flash('Invalid category', 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    # Category must exist within this project.
    category = conn.execute(
        'SELECT id FROM budget_categories WHERE id = ? AND project_id = ?',
        (category_id, project_id)
    ).fetchone()
    if category is None:
        flash('Invalid category', 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    description = (request.form.get('description') or '').strip()
    if not description:
        flash('Description is required', 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    estimated_cents, error = _parse_cents('estimated', allow_zero=True)
    if error is not None:
        flash(error, 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    actual_cents, error = _parse_cents('actual', allow_zero=True)
    if error is not None:
        actual_cents = 0

    create_line_item_model(
        conn, project_id, category_id, description,
        estimated_cents, actual_cents
    )
    flash('Line item created', 'success')
    return redirect(url_for('budget.index', project_id=project_id))


@bp.route('/<int:project_id>/line-items/<int:item_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def update_line_item(project_id, item_id):
    conn = get_db()

    # IDOR: line item must exist and belong to this project (404 not 403).
    item = conn.execute(
        'SELECT id, project_id FROM budget_line_items WHERE id = ?',
        (item_id,)
    ).fetchone()
    if item is None:
        abort(404)
    if item['project_id'] != project_id:
        abort(404)

    estimated_cents, est_error = _parse_cents('estimated', allow_zero=True)
    actual_cents, act_error = _parse_cents('actual', allow_zero=True)

    if est_error is not None and act_error is not None:
        flash('Invalid amount', 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    update_line_item_model(
        conn, item_id,
        estimated_cents=estimated_cents if est_error is None else None,
        actual_cents=actual_cents if act_error is None else None,
    )
    flash('Line item updated', 'success')
    return redirect(url_for('budget.index', project_id=project_id))
