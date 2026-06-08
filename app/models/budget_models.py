"""Budget model functions.

Money is always stored and returned as integer cents. The `remaining` value
for a department budget is NEVER stored -- it is always computed as
`allocated_cents - spent_cents` (Negative Constraint 2).
"""
import sqlite3


def get_budget_summary(conn, project_id) -> dict:
    """Return overall budget totals plus a per-category rollup.

    Returns a dict with keys:
      - total_estimated_cents (int)
      - total_actual_cents (int)
      - variance_cents (int)  -- estimated minus actual
      - categories (list[dict]): one row per budget category with
        keys: id, account_number, name, parent_group,
        estimated_cents, actual_cents
    """
    totals = conn.execute(
        '''SELECT COALESCE(SUM(estimated_cents), 0) AS total_estimated_cents,
                  COALESCE(SUM(actual_cents), 0)    AS total_actual_cents
           FROM budget_line_items
           WHERE project_id = ?''',
        (project_id,)
    ).fetchone()

    total_estimated_cents = totals['total_estimated_cents']
    total_actual_cents = totals['total_actual_cents']

    category_rows = conn.execute(
        '''SELECT bc.id            AS id,
                  bc.account_number AS account_number,
                  bc.name          AS name,
                  bc.parent_group  AS parent_group,
                  COALESCE(SUM(bli.estimated_cents), 0) AS estimated_cents,
                  COALESCE(SUM(bli.actual_cents), 0)    AS actual_cents
           FROM budget_categories bc
           LEFT JOIN budget_line_items bli ON bli.category_id = bc.id
           WHERE bc.project_id = ?
           GROUP BY bc.id, bc.account_number, bc.name, bc.parent_group
           ORDER BY bc.account_number''',
        (project_id,)
    ).fetchall()

    categories = [dict(row) for row in category_rows]

    return {
        'total_estimated_cents': total_estimated_cents,
        'total_actual_cents': total_actual_cents,
        'variance_cents': total_estimated_cents - total_actual_cents,
        'categories': categories,
    }


def get_budget_categories(conn, project_id) -> list:
    """Return all budget categories for a project, each with its line items.

    Returns list[dict]; each dict has keys: id, account_number, name,
    parent_group, estimated_cents, actual_cents, line_items (list[dict]).
    Each line item dict has keys: id, description, estimated_cents,
    actual_cents, notes.
    """
    category_rows = conn.execute(
        '''SELECT id, account_number, name, parent_group
           FROM budget_categories
           WHERE project_id = ?
           ORDER BY account_number''',
        (project_id,)
    ).fetchall()

    item_rows = conn.execute(
        '''SELECT id, category_id, description, estimated_cents, actual_cents, notes
           FROM budget_line_items
           WHERE project_id = ?
           ORDER BY id''',
        (project_id,)
    ).fetchall()

    items_by_category = {}
    for row in item_rows:
        items_by_category.setdefault(row['category_id'], []).append({
            'id': row['id'],
            'description': row['description'],
            'estimated_cents': row['estimated_cents'],
            'actual_cents': row['actual_cents'],
            'notes': row['notes'],
        })

    categories = []
    for row in category_rows:
        line_items = items_by_category.get(row['id'], [])
        estimated_cents = sum(item['estimated_cents'] for item in line_items)
        actual_cents = sum(item['actual_cents'] for item in line_items)
        categories.append({
            'id': row['id'],
            'account_number': row['account_number'],
            'name': row['name'],
            'parent_group': row['parent_group'],
            'estimated_cents': estimated_cents,
            'actual_cents': actual_cents,
            'line_items': line_items,
        })

    return categories


def get_department_allocation(conn, department_id) -> dict | None:
    """Return the department budget row for a department, or None.

    Returns dict with keys: id, project_id, department_id, allocated_cents,
    spent_cents, remaining_cents. `remaining_cents` is computed, never stored.
    """
    row = conn.execute(
        '''SELECT id, project_id, department_id, allocated_cents, spent_cents
           FROM department_budgets
           WHERE department_id = ?''',
        (department_id,)
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result['remaining_cents'] = result['allocated_cents'] - result['spent_cents']
    return result


def allocate_budget(conn, project_id, department_id, amount_cents) -> bool:
    """Set a department's allocation to amount_cents.

    Enforces SUM(allocations across all departments) <= project total_budget.
    Re-reads current allocations and the constraint INSIDE the lock to avoid
    a TOCTOU race. Commits internally (BEGIN IMMEDIATE). Returns True on
    success, False if the allocation would exceed the project total budget
    or would drop below the department's already-spent amount.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        project = conn.execute(
            'SELECT total_budget_cents FROM projects WHERE id = ?',
            (project_id,)
        ).fetchone()
        if project is None:
            conn.execute('ROLLBACK')
            return False
        total_budget_cents = project['total_budget_cents']

        # Re-read the existing allocation (and spent) for THIS department.
        existing = conn.execute(
            '''SELECT allocated_cents, spent_cents
               FROM department_budgets
               WHERE project_id = ? AND department_id = ?''',
            (project_id, department_id)
        ).fetchone()
        current_allocated = existing['allocated_cents'] if existing else 0
        current_spent = existing['spent_cents'] if existing else 0

        # Cannot allocate less than already spent (DB CHECK: spent <= allocated).
        if amount_cents < current_spent:
            conn.execute('ROLLBACK')
            return False

        # Sum of all OTHER departments' allocations for this project.
        other = conn.execute(
            '''SELECT COALESCE(SUM(allocated_cents), 0) AS other_allocated
               FROM department_budgets
               WHERE project_id = ? AND department_id != ?''',
            (project_id, department_id)
        ).fetchone()
        other_allocated = other['other_allocated']

        # Enforce SUM(allocations) <= total_budget inside the lock.
        if other_allocated + amount_cents > total_budget_cents:
            conn.execute('ROLLBACK')
            return False

        if existing is None:
            conn.execute(
                '''INSERT INTO department_budgets
                       (project_id, department_id, allocated_cents, spent_cents)
                   VALUES (?, ?, ?, 0)''',
                (project_id, department_id, amount_cents)
            )
        else:
            conn.execute(
                '''UPDATE department_budgets
                   SET allocated_cents = ?
                   WHERE project_id = ? AND department_id = ?''',
                (amount_cents, project_id, department_id)
            )

        conn.execute('COMMIT')
        return True
    except sqlite3.IntegrityError:
        conn.execute('ROLLBACK')
        return False
    except Exception:
        conn.execute('ROLLBACK')
        raise


def create_line_item(conn, project_id, category_id, description,
                     estimated_cents, actual_cents=0) -> int:
    """Insert a budget line item. Commits internally (BEGIN IMMEDIATE).

    Returns the new line item id.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')
        cur = conn.execute(
            '''INSERT INTO budget_line_items
                   (category_id, project_id, description, estimated_cents, actual_cents)
               VALUES (?, ?, ?, ?, ?)''',
            (category_id, project_id, description, estimated_cents, actual_cents)
        )
        line_item_id = cur.lastrowid
        conn.execute('COMMIT')
        return line_item_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def update_line_item(conn, line_item_id, estimated_cents=None,
                     actual_cents=None) -> bool:
    """Update estimated and/or actual cents on a line item.

    Commits internally (BEGIN IMMEDIATE). Returns True if a row was updated,
    False if the line item does not exist or nothing was provided to update.
    """
    fields = []
    params = []
    if estimated_cents is not None:
        fields.append('estimated_cents = ?')
        params.append(estimated_cents)
    if actual_cents is not None:
        fields.append('actual_cents = ?')
        params.append(actual_cents)

    if not fields:
        return False

    params.append(line_item_id)
    try:
        conn.execute('BEGIN IMMEDIATE')
        existing = conn.execute(
            'SELECT id FROM budget_line_items WHERE id = ?',
            (line_item_id,)
        ).fetchone()
        if existing is None:
            conn.execute('ROLLBACK')
            return False
        conn.execute(
            f'UPDATE budget_line_items SET {", ".join(fields)} WHERE id = ?',
            params
        )
        conn.execute('COMMIT')
        return True
    except Exception:
        conn.execute('ROLLBACK')
        raise
