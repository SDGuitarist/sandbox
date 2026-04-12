"""Task model functions for the project tracker."""


def get_all_tasks(db):
    """Return all tasks with category name, ordered by created_at DESC."""
    return db.execute(
        """SELECT t.*, c.name AS category_name, c.color AS category_color
           FROM tasks t
           JOIN categories c ON t.category_id = c.id
           ORDER BY t.created_at DESC"""
    ).fetchall()


def get_task(db, task_id):
    """Return a single task with category info, or None."""
    return db.execute(
        """SELECT t.*, c.name AS category_name, c.color AS category_color
           FROM tasks t
           JOIN categories c ON t.category_id = c.id
           WHERE t.id = ?""",
        (task_id,),
    ).fetchone()


def create_task(db, title, description, status, due_date, category_id):
    """Insert a new task and return its ID."""
    cursor = db.execute(
        """INSERT INTO tasks (title, description, status, due_date, category_id)
           VALUES (?, ?, ?, ?, ?)""",
        (title, description, status, due_date, category_id),
    )
    return cursor.lastrowid


def update_task(db, task_id, title, description, status, due_date, category_id):
    """Update an existing task and set updated_at to now."""
    db.execute(
        """UPDATE tasks
           SET title = ?, description = ?, status = ?, due_date = ?,
               category_id = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (title, description, status, due_date, category_id, task_id),
    )


def delete_task(db, task_id):
    """Delete a task. CASCADE removes associated task_members."""
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def get_task_members(db, task_id):
    """Return members assigned to a task."""
    return db.execute(
        """SELECT m.*
           FROM members m
           JOIN task_members tm ON m.id = tm.member_id
           WHERE tm.task_id = ?""",
        (task_id,),
    ).fetchall()


def get_available_members(db, task_id):
    """Return members NOT assigned to a task."""
    return db.execute(
        """SELECT m.*
           FROM members m
           LEFT JOIN task_members tm ON m.id = tm.member_id AND tm.task_id = ?
           WHERE tm.member_id IS NULL""",
        (task_id,),
    ).fetchall()


def assign_member(db, task_id, member_id):
    """Assign a member to a task. Ignores duplicates."""
    db.execute(
        "INSERT OR IGNORE INTO task_members (task_id, member_id) VALUES (?, ?)",
        (task_id, member_id),
    )


def unassign_member(db, task_id, member_id):
    """Remove a member from a task."""
    db.execute(
        "DELETE FROM task_members WHERE task_id = ? AND member_id = ?",
        (task_id, member_id),
    )


def get_tasks_by_category(db, category_id):
    """Return all tasks in a category."""
    return db.execute(
        """SELECT t.*, c.name AS category_name, c.color AS category_color
           FROM tasks t
           JOIN categories c ON t.category_id = c.id
           WHERE t.category_id = ?
           ORDER BY t.created_at DESC""",
        (category_id,),
    ).fetchall()


def get_tasks_by_member(db, member_id):
    """Return all tasks assigned to a member."""
    return db.execute(
        """SELECT t.*, c.name AS category_name, c.color AS category_color
           FROM tasks t
           JOIN categories c ON t.category_id = c.id
           JOIN task_members tm ON t.id = tm.task_id
           WHERE tm.member_id = ?
           ORDER BY t.created_at DESC""",
        (member_id,),
    ).fetchall()


def count_tasks_by_status(db):
    """Return a plain dict of status counts: {'todo': N, 'in_progress': N, 'done': N}."""
    rows = db.execute(
        "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"
    ).fetchall()
    result = {"todo": 0, "in_progress": 0, "done": 0}
    for row in rows:
        result[row["status"]] = row["count"]
    return result


def count_tasks_by_category(db):
    """Return list of Rows with name, color, count per category."""
    return db.execute(
        """SELECT c.name, c.color, COUNT(t.id) AS count
           FROM categories c
           LEFT JOIN tasks t ON c.id = t.category_id
           GROUP BY c.id
           ORDER BY count DESC"""
    ).fetchall()


def get_overdue_tasks(db):
    """Return tasks that are past due and not done."""
    return db.execute(
        """SELECT t.*, c.name AS category_name, c.color AS category_color
           FROM tasks t
           JOIN categories c ON t.category_id = c.id
           WHERE t.due_date IS NOT NULL
             AND t.due_date < date('now')
             AND t.status != 'done'
           ORDER BY t.due_date ASC"""
    ).fetchall()
