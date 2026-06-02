"""Budget blueprint routes for Film Production PM Tool.

All routes are producer-only. Money is stored as integer cents.
url_prefix=/budget is registered in app/__init__.py.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.database import get_db
from app.models.budget_models import (
    get_budget_summary,
    get_budget_categories,
    get_department_allocation,
    allocate_budget,
    create_line_item as model_create_line_item,
    update_line_item as model_update_line_item,
)

bp = Blueprint('budget', __name__)


@bp.route('/<int:project_id>')
@login_required
@require_project_member
@require_role('producer')
def index(project_id):
    """Budget overview page showing summary and categories with line items."""
    conn = get_db()
    summary = get_budget_summary(conn, project_id)
    categories = get_budget_categories(conn, project_id)
    # Departments for the allocation form dropdown
    departments = conn.execute(
        'SELECT id, name FROM departments WHERE project_id = ? ORDER BY name',
        (project_id,)
    ).fetchall()
    return render_template('budget/index.html',
                           project=g.project,
                           summary=summary,
                           categories=categories,
                           departments=departments)


@bp.route('/<int:project_id>/top-sheet')
@login_required
@require_project_member
@require_role('producer')
def top_sheet(project_id):
    """Top sheet summary page grouped by parent_group with totals."""
    conn = get_db()
    summary = get_budget_summary(conn, project_id)

    # Group categories by parent_group for the top sheet
    groups = {}
    for cat in summary['categories']:
        group = cat['parent_group']
        if group not in groups:
            groups[group] = {
                'parent_group': group,
                'categories': [],
                'total_estimated_cents': 0,
                'total_actual_cents': 0,
            }
        groups[group]['categories'].append(cat)
        groups[group]['total_estimated_cents'] += cat['estimated_cents']
        groups[group]['total_actual_cents'] += cat['actual_cents']

    # Order groups in standard film budget order
    group_order = ['ATL', 'BTL_PRODUCTION', 'BTL_POST', 'OTHER']
    ordered_groups = [groups[g_name] for g_name in group_order if g_name in groups]

    return render_template('budget/top_sheet.html',
                           project=g.project,
                           summary=summary,
                           groups=ordered_groups)


@bp.route('/<int:project_id>/allocate', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def allocate(project_id):
    """Allocate budget to a department. Rejects if allocation would exceed total."""
    conn = get_db()

    # Validate department_id
    try:
        department_id = int(request.form['department_id'])
    except (ValueError, TypeError, KeyError):
        flash('Invalid department', 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    # Validate department exists in this project
    dept = conn.execute(
        'SELECT id FROM departments WHERE id = ? AND project_id = ?',
        (department_id, project_id)
    ).fetchone()
    if dept is None:
        flash('Department not found', 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    # Parse money: amount_cents from dollar input
    try:
        amount_cents = int(round(float(request.form['amount_cents']) * 100))
    except (ValueError, TypeError, KeyError):
        flash('Invalid amount', 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    if amount_cents < 0:
        flash('Amount must be zero or positive', 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    # Attempt allocation with overspend protection
    success = allocate_budget(conn, project_id, department_id, amount_cents)
    if not success:
        # Calculate remaining budget for the flash message
        project = conn.execute(
            'SELECT total_budget_cents FROM projects WHERE id = ?',
            (project_id,)
        ).fetchone()
        current_sum = conn.execute(
            '''SELECT COALESCE(SUM(allocated_cents), 0) AS total
               FROM department_budgets
               WHERE project_id = ? AND department_id != ?''',
            (project_id, department_id)
        ).fetchone()
        remaining = project['total_budget_cents'] - current_sum['total']
        flash(f'Allocation exceeds total budget. Remaining: ${remaining / 100:,.2f}', 'error')
        return redirect(url_for('budget.index', project_id=project_id))

    flash('Budget allocated successfully', 'success')
    return redirect(url_for('budget.index', project_id=project_id))


@bp.route('/<int:project_id>/line-items/new')
@login_required
@require_project_member
@require_role('producer')
def new_line_item(project_id):
    """Form to create a new budget line item."""
    conn = get_db()
    categories = conn.execute(
        '''SELECT id, account_number, name, parent_group
           FROM budget_categories WHERE project_id = ?
           ORDER BY account_number''',
        (project_id,)
    ).fetchall()
    return render_template('budget/new_line_item.html',
                           project=g.project,
                           categories=categories)


@bp.route('/<int:project_id>/line-items', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def create_line_item(project_id):
    """Create a new budget line item."""
    conn = get_db()

    # Validate category_id
    try:
        category_id = int(request.form['category_id'])
    except (ValueError, TypeError, KeyError):
        flash('Invalid category', 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    # Verify category belongs to this project
    cat = conn.execute(
        'SELECT id FROM budget_categories WHERE id = ? AND project_id = ?',
        (category_id, project_id)
    ).fetchone()
    if cat is None:
        flash('Category not found', 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    # Validate description
    description = request.form.get('description', '').strip()
    if not description:
        flash('Description is required', 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    # Parse estimated_cents from dollar input
    try:
        estimated_cents = int(round(float(request.form['estimated_cents']) * 100))
    except (ValueError, TypeError, KeyError):
        flash('Invalid amount', 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    if estimated_cents < 0:
        flash('Amount must be zero or positive', 'error')
        return redirect(url_for('budget.new_line_item', project_id=project_id))

    model_create_line_item(conn, project_id, category_id, description, estimated_cents)
    flash('Line item created', 'success')
    return redirect(url_for('budget.index', project_id=project_id))


@bp.route('/<int:project_id>/line-items/<int:item_id>/edit', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def update_line_item(project_id, item_id):
    """Update estimated and/or actual cents on a budget line item."""
    conn = get_db()

    # IDOR check: verify the line item belongs to this project
    item = conn.execute(
        'SELECT id, project_id FROM budget_line_items WHERE id = ?',
        (item_id,)
    ).fetchone()
    if item is None:
        abort(404)
    if item['project_id'] != project_id:
        abort(404)

    # Parse estimated_cents
    estimated_cents = None
    if 'estimated_cents' in request.form and request.form['estimated_cents'].strip():
        try:
            estimated_cents = int(round(float(request.form['estimated_cents']) * 100))
        except (ValueError, TypeError):
            flash('Invalid amount', 'error')
            return redirect(url_for('budget.index', project_id=project_id))
        if estimated_cents < 0:
            flash('Invalid amount', 'error')
            return redirect(url_for('budget.index', project_id=project_id))

    # Parse actual_cents
    actual_cents = None
    if 'actual_cents' in request.form and request.form['actual_cents'].strip():
        try:
            actual_cents = int(round(float(request.form['actual_cents']) * 100))
        except (ValueError, TypeError):
            flash('Invalid amount', 'error')
            return redirect(url_for('budget.index', project_id=project_id))
        if actual_cents < 0:
            flash('Invalid amount', 'error')
            return redirect(url_for('budget.index', project_id=project_id))

    model_update_line_item(conn, item_id, estimated_cents=estimated_cents, actual_cents=actual_cents)
    flash('Line item updated', 'success')
    return redirect(url_for('budget.index', project_id=project_id))
