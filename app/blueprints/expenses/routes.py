"""Expenses blueprint routes.

url_prefix=/expenses
Roles: producer (full access), department_head (own department only)
AD and crew_member: no access (403)

Cross-boundary imports:
  - get_department_allocation from budget_models
  - get_departments from department_models
"""
import logging
import re

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for
)

from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role
)
from app.database import get_db
from app.models.budget_models import get_department_allocation
from app.models.department_models import get_departments
from app.models.expense_models import (
    approve_expense, create_expense, delete_expense, get_expenses
)

logger = logging.getLogger(__name__)

bp = Blueprint('expenses', __name__)


def _get_user_departments(conn, project_id, user):
    """Return list of department dicts where user is department head.

    Used for ownership checks: department_head can only access expenses
    for departments where dept.head_id == g.user['id'].
    """
    rows = conn.execute(
        'SELECT id, name FROM departments '
        'WHERE project_id = ? AND head_id = ?',
        (project_id, user['id'])
    ).fetchall()
    return [dict(r) for r in rows]


@bp.route('/<int:project_id>')
@login_required
@require_project_member
@require_role('producer', 'department_head')
def list(project_id):
    """List expenses. Producer sees all; dept_head sees own departments only."""
    conn = get_db()

    if g.member['role'] == 'producer':
        expenses = get_expenses(conn, project_id)
        departments = get_departments(conn, project_id)
    else:
        # department_head: only own departments
        user_depts = _get_user_departments(conn, project_id, g.user)
        if not user_depts:
            abort(403)
        expenses = []
        for dept in user_depts:
            expenses.extend(get_expenses(conn, project_id, dept['id']))
        # Sort combined list by date descending
        expenses.sort(
            key=lambda e: (e['expense_date'], e['created_at']), reverse=True
        )
        departments = user_depts

    # Enrich departments with budget allocation data for the summary table
    enriched_departments = []
    for dept in departments:
        dept_dict = dict(dept) if not isinstance(dept, dict) else dept.copy()
        allocation = get_department_allocation(conn, dept_dict['id'])
        if allocation:
            dept_dict['allocated_cents'] = allocation['allocated_cents']
            dept_dict['spent_cents'] = allocation['spent_cents']
        else:
            dept_dict['allocated_cents'] = 0
            dept_dict['spent_cents'] = 0
        enriched_departments.append(dept_dict)

    return render_template(
        'expenses/list.html',
        project=g.project,
        expenses=expenses,
        departments=enriched_departments
    )


@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'department_head')
def new(project_id):
    """Show new expense form. Producer sees all depts; dept_head sees own."""
    conn = get_db()

    if g.member['role'] == 'producer':
        departments = get_departments(conn, project_id)
    else:
        departments = _get_user_departments(conn, project_id, g.user)
        if not departments:
            abort(403)

    # Get budget categories for the dropdown
    categories = conn.execute(
        'SELECT id, account_number, name FROM budget_categories '
        'WHERE project_id = ? ORDER BY account_number',
        (project_id,)
    ).fetchall()

    return render_template(
        'expenses/new.html',
        project=g.project,
        departments=departments,
        categories=categories
    )


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'department_head')
def create(project_id):
    """Create a new expense with budget enforcement."""
    conn = get_db()

    # Parse and validate department_id
    try:
        department_id = int(request.form.get('department_id', ''))
    except (ValueError, TypeError):
        flash('Department is required', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    # Ownership check: dept_head can only expense own department
    if g.member['role'] == 'department_head':
        user_depts = _get_user_departments(conn, project_id, g.user)
        user_dept_ids = {d['id'] for d in user_depts}
        if department_id not in user_dept_ids:
            abort(403)

    # Verify department exists in project
    dept = conn.execute(
        'SELECT id FROM departments WHERE id = ? AND project_id = ?',
        (department_id, project_id)
    ).fetchone()
    if dept is None:
        flash('Department not found', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    # Parse amount (money parsing pattern from spec)
    try:
        amount_cents = int(round(float(request.form.get('amount', '')) * 100))
    except (ValueError, TypeError):
        flash('Invalid amount', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))
    if amount_cents <= 0:
        flash('Amount must be positive', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    # Validate vendor
    vendor = request.form.get('vendor', '').strip()
    if not vendor:
        flash('Vendor is required', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    # Validate expense_date (YYYY-MM-DD format)
    expense_date = request.form.get('expense_date', '').strip()
    if not expense_date:
        flash('Date is required', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    # Basic date format validation
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', expense_date):
        flash('Date must be in YYYY-MM-DD format', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    # Optional fields
    description = request.form.get('description', '').strip() or None
    category_id_str = request.form.get('category_id', '').strip()
    category_id = None
    if category_id_str:
        try:
            category_id = int(category_id_str)
        except (ValueError, TypeError):
            pass

    # Create expense (enforces budget constraint inside transaction)
    try:
        expense_id = create_expense(
            conn, project_id, department_id, amount_cents, vendor,
            description, expense_date, category_id, g.user['id']
        )
        logger.info(
            'User %d created expense %d in project %d',
            g.user['id'], expense_id, project_id
        )
        flash('Expense created', 'success')
    except ValueError as e:
        # Budget exceeded -- show remaining amount
        error_msg = str(e)
        if 'Remaining' in error_msg:
            match = re.search(r'Remaining: (\d+) cents', error_msg)
            if match:
                remaining_cents = int(match.group(1))
                flash(
                    f'Budget exceeded. Remaining: ${remaining_cents / 100:,.2f}',
                    'error'
                )
            else:
                flash(error_msg, 'error')
        else:
            flash(error_msg, 'error')

    return redirect(url_for('expenses.list', project_id=project_id))


@bp.route('/<int:project_id>/<int:expense_id>/delete', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'department_head')
def delete(project_id, expense_id):
    """Delete an expense and restore budget.

    Producer: can delete any expense in the project.
    Department head: can only delete expenses in own dept AND created_by self.
    """
    conn = get_db()

    # Fetch expense and verify it belongs to this project (IDOR prevention FC35)
    expense = conn.execute(
        'SELECT id, project_id, department_id, created_by, amount_cents '
        'FROM expenses WHERE id = ?',
        (expense_id,)
    ).fetchone()

    if expense is None:
        abort(404)
    if expense['project_id'] != project_id:
        abort(404)

    # Ownership check for department_head
    if g.member['role'] == 'department_head':
        user_depts = _get_user_departments(conn, project_id, g.user)
        user_dept_ids = {d['id'] for d in user_depts}
        if expense['department_id'] not in user_dept_ids:
            abort(403)
        if expense['created_by'] != g.user['id']:
            abort(403)

    result = delete_expense(conn, expense_id)
    if result:
        logger.info(
            'User %d deleted expense %d in project %d',
            g.user['id'], expense_id, project_id
        )
        flash('Expense deleted', 'success')
    else:
        flash('Expense not found', 'error')

    return redirect(url_for('expenses.list', project_id=project_id))


@bp.route('/<int:project_id>/<int:expense_id>/approve', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def approve(project_id, expense_id):
    """Approve an expense. Producer only."""
    conn = get_db()

    # Verify expense belongs to this project (IDOR prevention FC35)
    expense = conn.execute(
        'SELECT id, project_id FROM expenses WHERE id = ?',
        (expense_id,)
    ).fetchone()

    if expense is None:
        abort(404)
    if expense['project_id'] != project_id:
        abort(404)

    result = approve_expense(conn, expense_id, g.user['id'])
    if result:
        flash('Expense approved', 'success')
    else:
        flash('Expense not found', 'error')

    return redirect(url_for('expenses.list', project_id=project_id))
