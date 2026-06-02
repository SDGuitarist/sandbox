"""Budget model functions for Film Production PM Tool.

Handles budget summaries, categories, department allocations, and line items.
All money values are stored as integer cents.
"""

def get_budget_summary(conn, project_id):
    """Get budget summary with totals and per-category breakdown.

    Returns: dict with keys: total_estimated_cents, total_actual_cents,
             variance_cents, categories (list of dicts with
             parent_group, name, estimated_cents, actual_cents)
    """
    # Get totals from line items
    totals = conn.execute(
        '''SELECT COALESCE(SUM(estimated_cents), 0) AS total_estimated_cents,
                  COALESCE(SUM(actual_cents), 0) AS total_actual_cents
           FROM budget_line_items WHERE project_id = ?''',
        (project_id,)
    ).fetchone()

    total_estimated = totals['total_estimated_cents']
    total_actual = totals['total_actual_cents']

    # Get per-category totals
    categories = conn.execute(
        '''SELECT bc.parent_group, bc.name, bc.account_number,
                  COALESCE(SUM(bli.estimated_cents), 0) AS estimated_cents,
                  COALESCE(SUM(bli.actual_cents), 0) AS actual_cents
           FROM budget_categories bc
           LEFT JOIN budget_line_items bli ON bli.category_id = bc.id
           WHERE bc.project_id = ?
           GROUP BY bc.id
           ORDER BY bc.account_number''',
        (project_id,)
    ).fetchall()

    return {
        'total_estimated_cents': total_estimated,
        'total_actual_cents': total_actual,
        'variance_cents': total_estimated - total_actual,
        'categories': [dict(row) for row in categories],
    }


def get_budget_categories(conn, project_id):
    """Get all budget categories with their line items.

    Returns: list[dict] -- categories with nested line_items list.
    Each category dict has: id, account_number, name, parent_group, line_items.
    Each line_item dict has: id, description, estimated_cents, actual_cents, notes.
    """
    categories = conn.execute(
        '''SELECT id, account_number, name, parent_group
           FROM budget_categories
           WHERE project_id = ?
           ORDER BY account_number''',
        (project_id,)
    ).fetchall()

    result = []
    for cat in categories:
        cat_dict = dict(cat)
        items = conn.execute(
            '''SELECT id, description, estimated_cents, actual_cents, notes
               FROM budget_line_items
               WHERE category_id = ?
               ORDER BY id''',
            (cat_dict['id'],)
        ).fetchall()
        cat_dict['line_items'] = [dict(item) for item in items]
        result.append(cat_dict)

    return result


def get_department_allocation(conn, department_id):
    """Get budget allocation for a single department.

    Returns: dict with keys: id, project_id, department_id, allocated_cents,
             spent_cents. Returns None if no allocation exists.
    """
    row = conn.execute(
        '''SELECT id, project_id, department_id, allocated_cents, spent_cents
           FROM department_budgets
           WHERE department_id = ?''',
        (department_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def allocate_budget(conn, project_id, department_id, amount_cents):
    """Allocate budget to a department with overspend protection.

    Uses BEGIN IMMEDIATE to get a write lock, then checks that the total
    allocated across all departments does not exceed the project's
    total_budget_cents. If it would exceed, rolls back and returns False.

    Returns: bool -- True if allocation succeeded, False if it would exceed.
    Commits internally (BEGIN IMMEDIATE + SUM check).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Get project total budget inside the lock
        project = conn.execute(
            'SELECT total_budget_cents FROM projects WHERE id = ?',
            (project_id,)
        ).fetchone()
        if project is None:
            conn.execute('ROLLBACK')
            return False

        total_budget = project['total_budget_cents']

        # Get current total allocated (excluding this department if it already
        # has an allocation, since we'll be replacing it)
        current_sum_row = conn.execute(
            '''SELECT COALESCE(SUM(allocated_cents), 0) AS total_allocated
               FROM department_budgets
               WHERE project_id = ? AND department_id != ?''',
            (project_id, department_id)
        ).fetchone()
        current_sum = current_sum_row['total_allocated']

        # Check if new allocation would exceed total budget
        if current_sum + amount_cents > total_budget:
            conn.execute('ROLLBACK')
            return False

        # Upsert the department budget allocation
        existing = conn.execute(
            '''SELECT id, spent_cents FROM department_budgets
               WHERE project_id = ? AND department_id = ?''',
            (project_id, department_id)
        ).fetchone()

        if existing:
            conn.execute(
                '''UPDATE department_budgets
                   SET allocated_cents = ?
                   WHERE id = ?''',
                (amount_cents, existing['id'])
            )
        else:
            conn.execute(
                '''INSERT INTO department_budgets
                   (project_id, department_id, allocated_cents, spent_cents)
                   VALUES (?, ?, ?, 0)''',
                (project_id, department_id, amount_cents)
            )

        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise


def create_line_item(conn, project_id, category_id, description, estimated_cents, actual_cents=0):
    """Create a new budget line item.

    Returns: int (line_item_id).
    Commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cursor = conn.execute(
            '''INSERT INTO budget_line_items
               (category_id, project_id, description, estimated_cents, actual_cents)
               VALUES (?, ?, ?, ?, ?)''',
            (category_id, project_id, description, estimated_cents, actual_cents)
        )
        line_item_id = cursor.lastrowid
        conn.execute('COMMIT')
        return line_item_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def update_line_item(conn, line_item_id, estimated_cents=None, actual_cents=None):
    """Update a budget line item's estimated and/or actual cents.

    Returns: bool -- True if the item was found and updated.
    Commits internally (BEGIN IMMEDIATE).
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        item = conn.execute(
            'SELECT id FROM budget_line_items WHERE id = ?',
            (line_item_id,)
        ).fetchone()
        if item is None:
            conn.execute('ROLLBACK')
            return False

        if estimated_cents is not None:
            conn.execute(
                'UPDATE budget_line_items SET estimated_cents = ? WHERE id = ?',
                (estimated_cents, line_item_id)
            )
        if actual_cents is not None:
            conn.execute(
                'UPDATE budget_line_items SET actual_cents = ? WHERE id = ?',
                (actual_cents, line_item_id)
            )

        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise
