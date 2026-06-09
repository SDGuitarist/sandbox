"""Expense routes.

Authorization (Authorization Matrix):
  GET  /<pid>            producer, department_head  (dept_head: own dept only)
  GET  /<pid>/new        producer, department_head  (dept_head: own dept only)
  POST /<pid>            producer, department_head  (dept_head: own dept only)
  POST /<pid>/<eid>/delete  producer, department_head
                            (dept_head: own dept + created_by == g.user['id'])
  POST /<pid>/<eid>/approve producer only

Cross-boundary imports (Cross-Boundary Wiring):
  - get_db                   from app.database
  - login_required,          from app.blueprints.auth.routes
    require_project_member,
    require_role
  - get_departments          from app.models.department_models
  - get_department_allocation from app.models.budget_models
"""

import re

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, abort, g)

from app.database import get_db
from app.blueprints.auth.routes import (login_required, require_project_member,
                                         require_role)
from app.models.department_models import get_departments
from app.models.budget_models import get_department_allocation
from app.models.expense_models import (create_expense, delete_expense,
                                        approve_expense, get_expense,
                                        get_expenses)

bp = Blueprint('expenses', __name__)

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _headed_dept_ids(conn, project_id):
    """Department IDs in this project headed by the current user (g.user)."""
    return {
        d['id'] for d in get_departments(conn, project_id)
        if d['head_id'] == g.user['id']
    }


@bp.route('/<int:project_id>', methods=['GET'])
@login_required
@require_project_member
@require_role('producer', 'department_head')
def list(project_id):
    conn = get_db()
    if g.member['role'] == 'producer':
        expenses = get_expenses(conn, project_id)
        departments = get_departments(conn, project_id)
    else:
        # department_head: own departments only
        headed = _headed_dept_ids(conn, project_id)
        departments = [d for d in get_departments(conn, project_id)
                       if d['id'] in headed]
        expenses = []
        for dept_id in headed:
            expenses.extend(get_expenses(conn, project_id, department_id=dept_id))
        expenses.sort(key=lambda e: (e['expense_date'], e['id']), reverse=True)
    return render_template('expenses/list.html', project=g.project,
                           expenses=expenses, departments=departments)


@bp.route('/<int:project_id>/new', methods=['GET'])
@login_required
@require_project_member
@require_role('producer', 'department_head')
def new(project_id):
    conn = get_db()
    if g.member['role'] == 'producer':
        departments = get_departments(conn, project_id)
    else:
        headed = _headed_dept_ids(conn, project_id)
        departments = [d for d in get_departments(conn, project_id)
                       if d['id'] in headed]
    return render_template('expenses/new.html', project=g.project,
                           departments=departments)


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'department_head')
def create(project_id):
    conn = get_db()

    # department_id required + must exist in this project
    try:
        department_id = int(request.form['department_id'])
    except (KeyError, ValueError, TypeError):
        flash('Department is required', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    project_depts = {d['id']: d for d in get_departments(conn, project_id)}
    dept = project_depts.get(department_id)
    if dept is None:
        flash('Department not found', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    # Ownership: department_head may only file against a department they head.
    if g.member['role'] == 'department_head' and dept['head_id'] != g.user['id']:
        abort(403)

    # Money parsing (form field `amount` in dollars -> cents)
    try:
        amount_cents = int(round(float(request.form['amount']) * 100))
    except (KeyError, ValueError, TypeError):
        flash('Invalid amount', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))
    if amount_cents <= 0:
        flash('Amount must be positive', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    vendor = request.form.get('vendor', '').strip()
    if not vendor:
        flash('Vendor is required', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    expense_date = request.form.get('expense_date', '').strip()
    if not DATE_RE.match(expense_date):
        flash('Expense date must be in YYYY-MM-DD format', 'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    description = request.form.get('description', '').strip() or None

    # category_id optional; if provided must exist in this project
    category_id = None
    raw_category = request.form.get('category_id', '').strip()
    if raw_category:
        try:
            category_id = int(raw_category)
        except (ValueError, TypeError):
            flash('Invalid category', 'error')
            return redirect(url_for('expenses.new', project_id=project_id))
        exists = conn.execute(
            'SELECT 1 FROM budget_categories WHERE id = ? AND project_id = ?',
            (category_id, project_id)
        ).fetchone()
        if exists is None:
            flash('Category not found', 'error')
            return redirect(url_for('expenses.new', project_id=project_id))

    # created_by pinned from session, never from form.
    expense_id = create_expense(
        conn, project_id, department_id, amount_cents, vendor,
        description, expense_date, category_id, g.user['id']
    )
    if expense_id is None:
        allocation = get_department_allocation(conn, department_id)
        if allocation is None:
            flash('No budget allocated to this department', 'error')
        else:
            remaining = allocation['allocated_cents'] - allocation['spent_cents']
            flash(f'Expense exceeds remaining budget of ${remaining / 100:,.2f}',
                  'error')
        return redirect(url_for('expenses.new', project_id=project_id))

    flash('Expense logged', 'success')
    return redirect(url_for('expenses.list', project_id=project_id))


@bp.route('/<int:project_id>/<int:expense_id>/delete', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'department_head')
def delete(project_id, expense_id):
    conn = get_db()
    expense = get_expense(conn, expense_id)
    if expense is None:
        abort(404)
    # IDOR: resource must belong to the URL's project (404, not 403).
    if expense['project_id'] != project_id:
        abort(404)

    # department_head: own dept AND must be the creator.
    if g.member['role'] == 'department_head':
        if expense['department_head_id'] != g.user['id']:
            abort(403)
        if expense['created_by'] != g.user['id']:
            abort(403)

    delete_expense(conn, expense_id)
    flash('Expense deleted', 'success')
    return redirect(url_for('expenses.list', project_id=project_id))


@bp.route('/<int:project_id>/<int:expense_id>/approve', methods=['POST'])
@login_required
@require_project_member
@require_role('producer')
def approve(project_id, expense_id):
    conn = get_db()
    expense = get_expense(conn, expense_id)
    if expense is None:
        abort(404)
    if expense['project_id'] != project_id:
        abort(404)

    approve_expense(conn, expense_id, g.user['id'])
    flash('Expense approved', 'success')
    return redirect(url_for('expenses.list', project_id=project_id))
