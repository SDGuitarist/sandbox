from datetime import date, timedelta

from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..db import get_db
from ..decorators import setup_required
from . import bp


# ---------------------------------------------------------------------------
# Helper: priority badge class mapping
# urgent=danger, high=warning, medium=info, low=secondary
# ---------------------------------------------------------------------------
PRIORITY_BADGE = {
    'urgent': 'danger',
    'high': 'warning',
    'medium': 'info',
    'low': 'secondary',
}


# ---------------------------------------------------------------------------
# GET /  — Task list with optional filters
# ---------------------------------------------------------------------------
@bp.route('/')
@setup_required
def index():
    priority_filter = request.args.get('priority', '')
    status_filter = request.args.get('status', '')
    project_filter = request.args.get('project', '')

    query = "SELECT t.*, p.name AS project_name FROM task t LEFT JOIN project p ON t.project_id = p.id WHERE 1=1"
    params = []

    if priority_filter:
        query += " AND t.priority = ?"
        params.append(priority_filter)
    if status_filter:
        query += " AND t.status = ?"
        params.append(status_filter)
    if project_filter:
        query += " AND t.project_id = ?"
        params.append(project_filter)

    query += " ORDER BY CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END, t.due_date ASC"

    with get_db() as db:
        tasks = db.execute(query, params).fetchall()
        projects = db.execute("SELECT id, name FROM project ORDER BY name").fetchall()

    return render_template(
        'tasks/list.html',
        tasks=tasks,
        projects=projects,
        priority_filter=priority_filter,
        status_filter=status_filter,
        priorities=['low', 'medium', 'high', 'urgent'],
        statuses=['todo', 'in_progress', 'done'],
        now_date=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /my-day  — Today + overdue tasks, ordered by priority
# ---------------------------------------------------------------------------
@bp.route('/my-day')
@setup_required
def my_day():
    query = """
        SELECT t.*, p.name AS project_name
        FROM task t
        LEFT JOIN project p ON t.project_id = p.id
        WHERE (t.due_date <= date('now') OR t.due_date IS NULL)
          AND t.status != 'done'
        ORDER BY CASE t.priority
            WHEN 'urgent' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            WHEN 'low' THEN 4
        END
    """
    with get_db() as db:
        tasks = db.execute(query).fetchall()

    return render_template('tasks/my_day.html', tasks=tasks, now_date=date.today().isoformat())


# ---------------------------------------------------------------------------
# GET,POST /new  — Create a new task
# ---------------------------------------------------------------------------
@bp.route('/new', methods=['GET', 'POST'])
@setup_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash("Title is required.", "error")
            with get_db() as db:
                projects = db.execute("SELECT id, name FROM project ORDER BY name").fetchall()
            return render_template(
                'tasks/form.html',
                task=None,
                projects=projects,
                priorities=['low', 'medium', 'high', 'urgent'],
                statuses=['todo', 'in_progress', 'done'],
            )

        description = request.form.get('description', '').strip()
        project_id = request.form.get('project_id', '') or None
        if project_id:
            project_id = int(project_id)
        priority = request.form.get('priority', 'medium')
        status = request.form.get('status', 'todo')
        due_date = request.form.get('due_date', '').strip() or None
        estimated_hours_str = request.form.get('estimated_hours', '0')
        try:
            estimated_hours = float(estimated_hours_str)
        except (ValueError, TypeError):
            estimated_hours = 0
        tags = request.form.get('tags', '').strip()
        is_recurring = 1 if request.form.get('is_recurring') else 0
        recurrence_interval = request.form.get('recurrence_interval', '') or None
        recurrence_days_str = request.form.get('recurrence_days', '0')
        try:
            recurrence_days = int(recurrence_days_str)
        except (ValueError, TypeError):
            recurrence_days = 0

        with get_db(immediate=True) as db:
            db.execute(
                """INSERT INTO task
                   (title, description, project_id, priority, status, due_date,
                    estimated_hours, tags, is_recurring, recurrence_interval, recurrence_days)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, description, project_id, priority, status, due_date,
                 estimated_hours, tags, is_recurring, recurrence_interval, recurrence_days),
            )
            task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('created', 'task', task_id, f"Created task {title}"),
            )

        flash("Task created successfully.", "success")
        return redirect(url_for('tasks.index'))

    # GET
    with get_db() as db:
        projects = db.execute("SELECT id, name FROM project ORDER BY name").fetchall()

    return render_template(
        'tasks/form.html',
        task=None,
        projects=projects,
        priorities=['low', 'medium', 'high', 'urgent'],
        statuses=['todo', 'in_progress', 'done'],
    )


# ---------------------------------------------------------------------------
# GET,POST /<int:id>/edit  — Edit an existing task
# ---------------------------------------------------------------------------
@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit(id):
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash("Title is required.", "error")
            with get_db() as db:
                task = db.execute("SELECT * FROM task WHERE id = ?", (id,)).fetchone()
                projects = db.execute("SELECT id, name FROM project ORDER BY name").fetchall()
            return render_template(
                'tasks/form.html',
                task=task,
                projects=projects,
                priorities=['low', 'medium', 'high', 'urgent'],
                statuses=['todo', 'in_progress', 'done'],
            )

        description = request.form.get('description', '').strip()
        project_id = request.form.get('project_id', '') or None
        if project_id:
            project_id = int(project_id)
        priority = request.form.get('priority', 'medium')
        status = request.form.get('status', 'todo')
        due_date = request.form.get('due_date', '').strip() or None
        estimated_hours_str = request.form.get('estimated_hours', '0')
        try:
            estimated_hours = float(estimated_hours_str)
        except (ValueError, TypeError):
            estimated_hours = 0
        tags = request.form.get('tags', '').strip()
        is_recurring = 1 if request.form.get('is_recurring') else 0
        recurrence_interval = request.form.get('recurrence_interval', '') or None
        recurrence_days_str = request.form.get('recurrence_days', '0')
        try:
            recurrence_days = int(recurrence_days_str)
        except (ValueError, TypeError):
            recurrence_days = 0

        with get_db(immediate=True) as db:
            db.execute(
                """UPDATE task SET
                   title=?, description=?, project_id=?, priority=?, status=?,
                   due_date=?, estimated_hours=?, tags=?, is_recurring=?,
                   recurrence_interval=?, recurrence_days=?,
                   updated_at=datetime('now')
                   WHERE id=?""",
                (title, description, project_id, priority, status, due_date,
                 estimated_hours, tags, is_recurring, recurrence_interval,
                 recurrence_days, id),
            )
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('updated', 'task', id, f"Updated task {title}"),
            )

        flash("Task updated successfully.", "success")
        return redirect(url_for('tasks.index'))

    # GET
    with get_db() as db:
        task = db.execute("SELECT * FROM task WHERE id = ?", (id,)).fetchone()
        if not task:
            flash("Task not found.", "error")
            return redirect(url_for('tasks.index'))
        projects = db.execute("SELECT id, name FROM project ORDER BY name").fetchall()

    return render_template(
        'tasks/form.html',
        task=task,
        projects=projects,
        priorities=['low', 'medium', 'high', 'urgent'],
        statuses=['todo', 'in_progress', 'done'],
    )


# ---------------------------------------------------------------------------
# POST /<int:id>/delete  — Delete a task
# ---------------------------------------------------------------------------
@bp.route('/<int:id>/delete', methods=['POST'])
@setup_required
def delete(id):
    with get_db(immediate=True) as db:
        task = db.execute("SELECT title FROM task WHERE id = ?", (id,)).fetchone()
        if not task:
            flash("Task not found.", "error")
            return redirect(url_for('tasks.index'))
        db.execute("DELETE FROM task WHERE id = ?", (id,))
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('deleted', 'task', id, f"Deleted task {task['title']}"),
        )

    flash("Task deleted.", "success")
    return redirect(url_for('tasks.index'))


# ---------------------------------------------------------------------------
# POST /<int:id>/complete  — Mark task as done (+ recurring logic)
# ---------------------------------------------------------------------------
@bp.route('/<int:id>/complete', methods=['POST'])
@setup_required
def complete(id):
    with get_db(immediate=True) as db:
        task = db.execute("SELECT * FROM task WHERE id = ?", (id,)).fetchone()
        if not task:
            flash("Task not found.", "error")
            return redirect(url_for('tasks.index'))

        # Mark the current task as done
        db.execute(
            "UPDATE task SET status = 'done', updated_at = datetime('now') WHERE id = ?",
            (id,),
        )

        # Activity log
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('completed', 'task', id, f"Completed task {task['title']}"),
        )

        # Recurring task: auto-create next instance
        if task['is_recurring'] and task['due_date']:
            interval = task['recurrence_interval']
            old_due = date.fromisoformat(task['due_date'])

            if interval == 'daily':
                new_due = old_due + timedelta(days=1)
            elif interval == 'weekly':
                new_due = old_due + timedelta(days=7)
            elif interval == 'monthly':
                new_due = old_due + timedelta(days=30)
            elif interval == 'custom' and task['recurrence_days'] > 0:
                new_due = old_due + timedelta(days=task['recurrence_days'])
            else:
                new_due = None

            if new_due:
                db.execute(
                    """INSERT INTO task
                       (title, description, project_id, priority, status, due_date,
                        estimated_hours, tags, is_recurring, recurrence_interval, recurrence_days)
                       VALUES (?, ?, ?, ?, 'todo', ?, ?, ?, ?, ?, ?)""",
                    (task['title'], task['description'], task['project_id'],
                     task['priority'], new_due.isoformat(), task['estimated_hours'],
                     task['tags'], task['is_recurring'], task['recurrence_interval'],
                     task['recurrence_days']),
                )
                new_task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.execute(
                    "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                    ('created', 'task', new_task_id,
                     f"Created task {task['title']}"),
                )
                flash(f"Task completed. Next occurrence created for {new_due.isoformat()}.", "success")
            else:
                flash("Task completed.", "success")
        else:
            flash("Task completed.", "success")

    # Redirect back to the page the user was on
    next_url = request.form.get('next', url_for('tasks.index'))
    return redirect(next_url)


# ---------------------------------------------------------------------------
# POST /quick-add  — Quick-add a task (from modal or sidebar)
# ---------------------------------------------------------------------------
@bp.route('/quick-add', methods=['POST'])
@setup_required
def quick_add():
    title = request.form.get('title', '').strip()
    if not title:
        flash("Title is required.", "error")
        return redirect(url_for('tasks.index'))

    project_id = request.form.get('project_id', '') or None
    if project_id:
        project_id = int(project_id)
    priority = request.form.get('priority', 'medium')
    due_date = request.form.get('due_date', '').strip() or None

    with get_db(immediate=True) as db:
        db.execute(
            """INSERT INTO task (title, project_id, priority, due_date)
               VALUES (?, ?, ?, ?)""",
            (title, project_id, priority, due_date),
        )
        task_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('created', 'task', task_id, f"Created task {title}"),
        )

    flash("Task added.", "success")
    return redirect(request.referrer or url_for('tasks.index'))
