"""Expense model functions.

Owns the `expenses` table. Writes to `department_budgets.spent_cents` inside the
same transaction as the expense insert/delete so the running spend total stays
consistent with the expense ledger.

Transaction Contracts (from spec):
- create_expense:  BEGIN IMMEDIATE, commits internally, spent_cents update in same txn
- delete_expense:  BEGIN IMMEDIATE, commits internally, spent_cents rollback in same txn
- approve_expense: BEGIN IMMEDIATE, commits internally
- get_expense / get_expenses: read-only, no transaction
"""


def create_expense(conn, project_id, department_id, amount_cents, vendor,
                    description, expense_date, category_id, created_by) -> int | None:
    """Create an expense and increment department_budgets.spent_cents atomically.

    Overspend is a RETURN VALUE, not an error: re-checks
    spent_cents + amount_cents <= allocated_cents INSIDE the BEGIN IMMEDIATE
    lock. On overspend (or no allocation row) it ROLLBACKs and returns None.

    Returns: int (expense_id) on success, None on overspend / missing allocation.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        allocation = conn.execute(
            'SELECT allocated_cents, spent_cents FROM department_budgets '
            'WHERE project_id = ? AND department_id = ?',
            (project_id, department_id)
        ).fetchone()
        # No allocation -> nothing to spend against -> reject.
        if allocation is None:
            conn.execute('ROLLBACK')
            return None
        if allocation['spent_cents'] + amount_cents > allocation['allocated_cents']:
            conn.execute('ROLLBACK')
            return None

        cur = conn.execute(
            'INSERT INTO expenses '
            '(project_id, department_id, category_id, amount_cents, vendor, '
            ' description, expense_date, created_by) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (project_id, department_id, category_id, amount_cents, vendor,
             description, expense_date, created_by)
        )
        expense_id = cur.lastrowid
        conn.execute(
            'UPDATE department_budgets SET spent_cents = spent_cents + ? '
            'WHERE project_id = ? AND department_id = ?',
            (amount_cents, project_id, department_id)
        )
        conn.execute('COMMIT')
        return expense_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def delete_expense(conn, expense_id) -> bool:
    """Delete an expense and restore department_budgets.spent_cents atomically.

    Returns: True if a row was deleted, False if the expense did not exist.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        expense = conn.execute(
            'SELECT project_id, department_id, amount_cents FROM expenses WHERE id = ?',
            (expense_id,)
        ).fetchone()
        if expense is None:
            conn.execute('ROLLBACK')
            return False

        conn.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        conn.execute(
            'UPDATE department_budgets SET spent_cents = spent_cents - ? '
            'WHERE project_id = ? AND department_id = ?',
            (expense['amount_cents'], expense['project_id'], expense['department_id'])
        )
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise


def approve_expense(conn, expense_id, approved_by) -> bool:
    """Mark an expense approved by stamping approved_by.

    Returns: True if updated, False if the expense did not exist.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        expense = conn.execute(
            'SELECT id FROM expenses WHERE id = ?', (expense_id,)
        ).fetchone()
        if expense is None:
            conn.execute('ROLLBACK')
            return False
        conn.execute(
            'UPDATE expenses SET approved_by = ? WHERE id = ?',
            (approved_by, expense_id)
        )
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_expense(conn, expense_id) -> dict | None:
    """Fetch a single expense by id (ownership/IDOR check helper).

    Returns: dict with all expense columns plus department_name, or None.
    """
    row = conn.execute(
        'SELECT e.id, e.project_id, e.department_id, e.category_id, '
        '       e.amount_cents, e.vendor, e.description, e.expense_date, '
        '       e.approved_by, e.created_by, e.created_at, '
        '       d.name AS department_name, d.head_id AS department_head_id '
        'FROM expenses e '
        'JOIN departments d ON d.id = e.department_id '
        'WHERE e.id = ?',
        (expense_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def get_expenses(conn, project_id, department_id=None) -> list:
    """List expenses for a project, optionally filtered by department.

    Returns: list[dict] with expense columns plus department_name,
    category_name, approver_name, creator_name. Newest first.
    """
    sql = (
        'SELECT e.id, e.project_id, e.department_id, e.category_id, '
        '       e.amount_cents, e.vendor, e.description, e.expense_date, '
        '       e.approved_by, e.created_by, e.created_at, '
        '       d.name AS department_name, '
        '       bc.name AS category_name, '
        '       approver.display_name AS approver_name, '
        '       creator.display_name AS creator_name '
        'FROM expenses e '
        'JOIN departments d ON d.id = e.department_id '
        'LEFT JOIN budget_categories bc ON bc.id = e.category_id '
        'LEFT JOIN users approver ON approver.id = e.approved_by '
        'LEFT JOIN users creator ON creator.id = e.created_by '
        'WHERE e.project_id = ?'
    )
    params = [project_id]
    if department_id is not None:
        sql += ' AND e.department_id = ?'
        params.append(department_id)
    sql += ' ORDER BY e.expense_date DESC, e.id DESC'
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
