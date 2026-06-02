"""Expense model functions.

Owns: expenses table
Reads: department_budgets (via cross-boundary import from budget_models)

Transaction contracts:
  - create_expense: BEGIN IMMEDIATE, commits internally
  - delete_expense: BEGIN IMMEDIATE, commits internally
  - approve_expense: BEGIN IMMEDIATE, commits internally
  - get_expenses: read-only, no transaction
"""
import logging
import sqlite3

logger = logging.getLogger(__name__)


def create_expense(conn, project_id, department_id, amount_cents, vendor,
                   description, expense_date, category_id, created_by):
    """Create an expense and atomically update department spent_cents.

    Returns: int (expense_id)
    Raises: ValueError if spent + amount > allocated (budget exceeded)
    Transaction: BEGIN IMMEDIATE -- commits internally
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Re-check allocation constraint inside the lock (TOCTOU protection)
        row = conn.execute(
            'SELECT allocated_cents, spent_cents FROM department_budgets '
            'WHERE project_id = ? AND department_id = ?',
            (project_id, department_id)
        ).fetchone()

        if row is None:
            conn.execute('ROLLBACK')
            raise ValueError('No budget allocation for this department')

        if row['spent_cents'] + amount_cents > row['allocated_cents']:
            remaining = row['allocated_cents'] - row['spent_cents']
            conn.execute('ROLLBACK')
            raise ValueError(
                f'Budget exceeded. Remaining: {remaining} cents'
            )

        # Update spent_cents atomically
        conn.execute(
            'UPDATE department_budgets SET spent_cents = spent_cents + ? '
            'WHERE project_id = ? AND department_id = ?',
            (amount_cents, project_id, department_id)
        )

        # Insert the expense
        cursor = conn.execute(
            'INSERT INTO expenses '
            '(project_id, department_id, category_id, amount_cents, vendor, '
            'description, expense_date, created_by) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (project_id, department_id, category_id, amount_cents, vendor,
             description, expense_date, created_by)
        )
        expense_id = cursor.lastrowid

        conn.execute('COMMIT')
        logger.info(
            'Expense %d created: %d cents for dept %d in project %d',
            expense_id, amount_cents, department_id, project_id
        )
        return expense_id

    except ValueError:
        # Already rolled back above; re-raise for route to handle
        raise
    except Exception:
        conn.execute('ROLLBACK')
        raise


def delete_expense(conn, expense_id):
    """Delete an expense and atomically restore department spent_cents.

    Returns: bool (True if deleted, False if expense not found)
    Transaction: BEGIN IMMEDIATE -- commits internally
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Fetch expense details inside the lock
        expense = conn.execute(
            'SELECT id, project_id, department_id, amount_cents '
            'FROM expenses WHERE id = ?',
            (expense_id,)
        ).fetchone()

        if expense is None:
            conn.execute('ROLLBACK')
            return False

        # Restore spent_cents
        conn.execute(
            'UPDATE department_budgets SET spent_cents = spent_cents - ? '
            'WHERE project_id = ? AND department_id = ?',
            (expense['amount_cents'], expense['project_id'],
             expense['department_id'])
        )

        # Delete the expense
        conn.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))

        conn.execute('COMMIT')
        logger.info(
            'Expense %d deleted: restored %d cents to dept %d',
            expense_id, expense['amount_cents'], expense['department_id']
        )
        return True

    except Exception:
        conn.execute('ROLLBACK')
        raise


def approve_expense(conn, expense_id, approved_by):
    """Mark an expense as approved.

    Returns: bool (True if approved, False if expense not found)
    Transaction: BEGIN IMMEDIATE -- commits internally
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        expense = conn.execute(
            'SELECT id FROM expenses WHERE id = ?',
            (expense_id,)
        ).fetchone()

        if expense is None:
            conn.execute('ROLLBACK')
            return False

        conn.execute(
            'UPDATE expenses SET approved_by = ? WHERE id = ?',
            (approved_by, expense_id)
        )

        conn.execute('COMMIT')
        logger.info(
            'Expense %d approved by user %d', expense_id, approved_by
        )
        return True

    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_expenses(conn, project_id, department_id=None):
    """Get expenses for a project, optionally filtered by department.

    Returns: list[dict] with keys: id, project_id, department_id,
             department_name, category_id, category_name, amount_cents,
             vendor, description, expense_date, approved_by, created_by,
             creator_name, created_at
    """
    query = '''
        SELECT e.id, e.project_id, e.department_id, d.name AS department_name,
               e.category_id, bc.name AS category_name,
               e.amount_cents, e.vendor, e.description, e.expense_date,
               e.approved_by, e.created_by, u.display_name AS creator_name,
               e.created_at
        FROM expenses e
        JOIN departments d ON d.id = e.department_id
        LEFT JOIN budget_categories bc ON bc.id = e.category_id
        JOIN users u ON u.id = e.created_by
        WHERE e.project_id = ?
    '''
    params = [project_id]

    if department_id is not None:
        query += ' AND e.department_id = ?'
        params.append(department_id)

    query += ' ORDER BY e.expense_date DESC, e.created_at DESC'

    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
