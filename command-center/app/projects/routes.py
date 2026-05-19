from datetime import date, timedelta

from flask import flash, redirect, render_template, request, url_for

from ..db import get_db
from ..decorators import setup_required
from . import bp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_cents(value_str):
    """Convert a dollar string from the form to integer cents."""
    try:
        return int(float(value_str) * 100)
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@bp.route('/')
@setup_required
def index():
    status_filter = request.args.get('status', '')
    type_filter = request.args.get('type', '')

    with get_db() as db:
        query = (
            "SELECT p.*, c.name AS contact_name "
            "FROM project p "
            "LEFT JOIN contact c ON p.contact_id = c.id "
            "WHERE 1=1"
        )
        params = []

        if status_filter:
            query += " AND p.status = ?"
            params.append(status_filter)

        if type_filter:
            query += " AND p.type = ?"
            params.append(type_filter)

        query += " ORDER BY p.created_at DESC LIMIT 1000"
        projects = db.execute(query, params).fetchall()

        contacts = db.execute(
            "SELECT id, name FROM contact ORDER BY name"
        ).fetchall()

    return render_template(
        'projects/list.html',
        projects=projects,
        contacts=contacts,
        status_filter=status_filter,
        statuses=['not_started', 'in_progress', 'on_hold', 'completed', 'cancelled'],
        types=['fixed_price', 'hourly', 'retainer', 'pro_bono'],
    )


@bp.route('/<int:id>')
@setup_required
def detail(id):
    with get_db() as db:
        project = db.execute("SELECT * FROM project WHERE id = ?", (id,)).fetchone()
        if not project:
            flash("Project not found.", "error")
            return redirect(url_for('projects.index'))

        contact = None
        if project['contact_id']:
            contact = db.execute(
                "SELECT * FROM contact WHERE id = ?", (project['contact_id'],)
            ).fetchone()

        milestones = db.execute(
            "SELECT * FROM milestone WHERE project_id = ? ORDER BY due_date",
            (id,),
        ).fetchall()

        tasks = db.execute(
            "SELECT * FROM task WHERE project_id = ? ORDER BY status, priority DESC",
            (id,),
        ).fetchall()

        time_entries = db.execute(
            "SELECT * FROM time_entry WHERE project_id = ? ORDER BY date DESC LIMIT 50",
            (id,),
        ).fetchall()

        row = db.execute(
            "SELECT COALESCE(SUM(minutes), 0) AS total, "
            "COALESCE(SUM(CASE WHEN billable = 1 THEN minutes ELSE 0 END), 0) AS billable "
            "FROM time_entry WHERE project_id = ?",
            (id,),
        ).fetchone()
        total_hours = row['total']
        billable_hours = row['billable']

        # Budget spent calculation
        # Fixed price: value is the budget; spent = total_hours/60 * hourly_rate/100 (in cents)
        # Hourly: spent = total_hours/60 * hourly_rate/100 (in cents)
        if project['hourly_rate']:
            budget_spent = int((total_hours / 60) * (project['hourly_rate'] / 100) * 100)
        else:
            budget_spent = 0

    return render_template(
        'projects/detail.html',
        project=project,
        contact=contact,
        milestones=milestones,
        tasks=tasks,
        time_entries=time_entries,
        total_hours=total_hours,
        billable_hours=billable_hours,
        budget_spent=budget_spent,
    )


@bp.route('/new', methods=['GET', 'POST'])
@setup_required
def create():
    deal_id = request.args.get('deal_id', type=int)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Project name is required.", "error")
            with get_db() as db:
                contacts = db.execute("SELECT id, name FROM contact ORDER BY name").fetchall()
            return render_template(
                'projects/form.html',
                project=None,
                contacts=contacts,
                statuses=['not_started', 'in_progress', 'on_hold', 'completed', 'cancelled'],
                types=['fixed_price', 'hourly', 'retainer', 'pro_bono'],
                deal_id=deal_id,
            )

        contact_id = request.form.get('contact_id', type=int)
        status = request.form.get('status', 'not_started')
        project_type = request.form.get('type', 'hourly')
        value = _parse_cents(request.form.get('value', '0'))
        hourly_rate = _parse_cents(request.form.get('hourly_rate', '0'))
        start_date = request.form.get('start_date', '').strip() or None
        target_end_date = request.form.get('target_end_date', '').strip() or None
        description = request.form.get('description', '').strip()
        notes = request.form.get('notes', '').strip()
        form_deal_id = request.form.get('deal_id', type=int)

        with get_db(immediate=True) as db:
            project_id = db.execute(
                "INSERT INTO project (name, contact_id, status, type, value, hourly_rate, "
                "start_date, target_end_date, description, notes, deal_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, contact_id, status, project_type, value, hourly_rate,
                 start_date, target_end_date, description, notes, form_deal_id),
            ).lastrowid

            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) "
                "VALUES (?, ?, ?, ?)",
                ('created', 'project', project_id, f"Created project {name}"),
            )

        flash("Project created successfully.", "success")
        return redirect(url_for('projects.detail', id=project_id))

    # GET
    with get_db() as db:
        contacts = db.execute("SELECT id, name FROM contact ORDER BY name").fetchall()

    return render_template(
        'projects/form.html',
        project=None,
        contacts=contacts,
        statuses=['not_started', 'in_progress', 'on_hold', 'completed', 'cancelled'],
        types=['fixed_price', 'hourly', 'retainer', 'pro_bono'],
        deal_id=deal_id,
    )


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit(id):
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Project name is required.", "error")
            with get_db() as db:
                project = db.execute("SELECT * FROM project WHERE id = ?", (id,)).fetchone()
                contacts = db.execute("SELECT id, name FROM contact ORDER BY name").fetchall()
            return render_template(
                'projects/form.html',
                project=project,
                contacts=contacts,
                statuses=['not_started', 'in_progress', 'on_hold', 'completed', 'cancelled'],
                types=['fixed_price', 'hourly', 'retainer', 'pro_bono'],
                deal_id=None,
            )

        contact_id = request.form.get('contact_id', type=int)
        status = request.form.get('status', 'not_started')
        project_type = request.form.get('type', 'hourly')
        value = _parse_cents(request.form.get('value', '0'))
        hourly_rate = _parse_cents(request.form.get('hourly_rate', '0'))
        start_date = request.form.get('start_date', '').strip() or None
        target_end_date = request.form.get('target_end_date', '').strip() or None
        description = request.form.get('description', '').strip()
        notes = request.form.get('notes', '').strip()

        with get_db(immediate=True) as db:
            # Check if status changed to completed
            old_project = db.execute(
                "SELECT status, name FROM project WHERE id = ?", (id,)
            ).fetchone()

            actual_end_date = None
            if status == 'completed' and old_project and old_project['status'] != 'completed':
                actual_end_date = date.today().isoformat()

            db.execute(
                "UPDATE project SET name=?, contact_id=?, status=?, type=?, value=?, "
                "hourly_rate=?, start_date=?, target_end_date=?, actual_end_date=COALESCE(?, actual_end_date), "
                "description=?, notes=?, updated_at=datetime('now') WHERE id=?",
                (name, contact_id, status, project_type, value, hourly_rate,
                 start_date, target_end_date, actual_end_date, description, notes, id),
            )

            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) "
                "VALUES (?, ?, ?, ?)",
                ('updated', 'project', id, f"Updated project {name}"),
            )

            # Extra activity log entry if completed
            if status == 'completed' and old_project and old_project['status'] != 'completed':
                db.execute(
                    "INSERT INTO activity_log (action, entity_type, entity_id, description) "
                    "VALUES (?, ?, ?, ?)",
                    ('completed', 'project', id, f"Completed project {name}"),
                )

        flash("Project updated successfully.", "success")
        return redirect(url_for('projects.detail', id=id))

    # GET
    with get_db() as db:
        project = db.execute("SELECT * FROM project WHERE id = ?", (id,)).fetchone()
        if not project:
            flash("Project not found.", "error")
            return redirect(url_for('projects.index'))
        contacts = db.execute("SELECT id, name FROM contact ORDER BY name").fetchall()

    return render_template(
        'projects/form.html',
        project=project,
        contacts=contacts,
        statuses=['not_started', 'in_progress', 'on_hold', 'completed', 'cancelled'],
        types=['fixed_price', 'hourly', 'retainer', 'pro_bono'],
        deal_id=None,
    )


@bp.route('/<int:id>/delete', methods=['POST'])
@setup_required
def delete(id):
    with get_db(immediate=True) as db:
        project = db.execute("SELECT name FROM project WHERE id = ?", (id,)).fetchone()
        if not project:
            flash("Project not found.", "error")
            return redirect(url_for('projects.index'))

        db.execute("DELETE FROM project WHERE id = ?", (id,))

        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) "
            "VALUES (?, ?, ?, ?)",
            ('deleted', 'project', id, f"Deleted project {project['name']}"),
        )

    flash("Project deleted.", "success")
    return redirect(url_for('projects.index'))


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------

@bp.route('/<int:id>/milestone', methods=['POST'])
@setup_required
def add_milestone(id):
    name = request.form.get('name', '').strip()
    if not name:
        flash("Milestone name is required.", "error")
        return redirect(url_for('projects.detail', id=id))

    due_date = request.form.get('due_date', '').strip() or None
    description = request.form.get('description', '').strip()

    with get_db(immediate=True) as db:
        project = db.execute("SELECT id FROM project WHERE id = ?", (id,)).fetchone()
        if not project:
            flash("Project not found.", "error")
            return redirect(url_for('projects.index'))

        db.execute(
            "INSERT INTO milestone (project_id, name, due_date, description) "
            "VALUES (?, ?, ?, ?)",
            (id, name, due_date, description),
        )

    flash("Milestone added.", "success")
    return redirect(url_for('projects.detail', id=id))


@bp.route('/milestone/<int:id>/complete', methods=['POST'])
@setup_required
def complete_milestone(id):
    with get_db(immediate=True) as db:
        milestone = db.execute(
            "SELECT * FROM milestone WHERE id = ?", (id,)
        ).fetchone()
        if not milestone:
            flash("Milestone not found.", "error")
            return redirect(url_for('projects.index'))

        db.execute(
            "UPDATE milestone SET status = 'completed' WHERE id = ?", (id,)
        )

    flash("Milestone completed.", "success")
    return redirect(url_for('projects.detail', id=milestone['project_id']))


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@bp.route('/templates')
@setup_required
def templates():
    with get_db() as db:
        rows = db.execute(
            "SELECT pt.*, "
            "(SELECT COUNT(*) FROM template_milestone WHERE template_id = pt.id) AS milestone_count, "
            "(SELECT COUNT(*) FROM template_task WHERE template_id = pt.id) AS task_count "
            "FROM project_template pt ORDER BY pt.name"
        ).fetchall()

    return render_template('projects/templates.html', templates=rows)


@bp.route('/<int:id>/save-template', methods=['POST'])
@setup_required
def save_template(id):
    template_name = request.form.get('template_name', '').strip()

    with get_db(immediate=True) as db:
        project = db.execute("SELECT * FROM project WHERE id = ?", (id,)).fetchone()
        if not project:
            flash("Project not found.", "error")
            return redirect(url_for('projects.index'))

        if not template_name:
            template_name = f"Template from {project['name']}"

        template_id = db.execute(
            "INSERT INTO project_template (name, description) VALUES (?, ?)",
            (template_name, project['description']),
        ).lastrowid

        # Copy milestones
        milestones = db.execute(
            "SELECT * FROM milestone WHERE project_id = ?", (id,)
        ).fetchall()
        for ms in milestones:
            db.execute(
                "INSERT INTO template_milestone (template_id, name, offset_days, description) "
                "VALUES (?, ?, ?, ?)",
                (template_id, ms['name'], 0, ms['description']),
            )

        # Copy tasks
        tasks = db.execute(
            "SELECT * FROM task WHERE project_id = ?", (id,)
        ).fetchall()
        for t in tasks:
            db.execute(
                "INSERT INTO template_task (template_id, title, description, priority, estimated_hours) "
                "VALUES (?, ?, ?, ?, ?)",
                (template_id, t['title'], t['description'], t['priority'], t['estimated_hours']),
            )

    flash("Template saved.", "success")
    return redirect(url_for('projects.templates'))


@bp.route('/from-template/<int:template_id>', methods=['POST'])
@setup_required
def create_from_template(template_id):
    project_name = request.form.get('name', '').strip()

    with get_db(immediate=True) as db:
        template = db.execute(
            "SELECT * FROM project_template WHERE id = ?", (template_id,)
        ).fetchone()
        if not template:
            flash("Template not found.", "error")
            return redirect(url_for('projects.templates'))

        if not project_name:
            project_name = template['name']

        start_date = date.today().isoformat()

        project_id = db.execute(
            "INSERT INTO project (name, status, type, description, start_date) "
            "VALUES (?, 'not_started', 'hourly', ?, ?)",
            (project_name, template['description'], start_date),
        ).lastrowid

        # Create milestones from template
        template_milestones = db.execute(
            "SELECT * FROM template_milestone WHERE template_id = ?", (template_id,)
        ).fetchall()
        for tm in template_milestones:
            due = None
            if tm['offset_days']:
                due = (date.today() + timedelta(days=tm['offset_days'])).isoformat()
            db.execute(
                "INSERT INTO milestone (project_id, name, due_date, description) "
                "VALUES (?, ?, ?, ?)",
                (project_id, tm['name'], due, tm['description']),
            )

        # Create tasks from template
        template_tasks = db.execute(
            "SELECT * FROM template_task WHERE template_id = ?", (template_id,)
        ).fetchall()
        for tt in template_tasks:
            db.execute(
                "INSERT INTO task (title, description, project_id, priority, estimated_hours) "
                "VALUES (?, ?, ?, ?, ?)",
                (tt['title'], tt['description'], project_id, tt['priority'], tt['estimated_hours']),
            )

        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) "
            "VALUES (?, ?, ?, ?)",
            ('created', 'project', project_id, f"Created project {project_name}"),
        )

    flash("Project created from template.", "success")
    return redirect(url_for('projects.detail', id=project_id))
