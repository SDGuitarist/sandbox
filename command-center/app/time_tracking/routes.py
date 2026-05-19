from datetime import date, timedelta

from flask import flash, jsonify, redirect, render_template, request, url_for

from ..db import get_db
from ..decorators import setup_required
from . import bp


@bp.route('/')
@setup_required
def index():
    """List all time entries with totals."""
    project_filter = request.args.get('project_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    with get_db() as db:
        # Build query with optional filters
        query = """
            SELECT te.*, p.name AS project_name, t.title AS task_title
            FROM time_entry te
            JOIN project p ON te.project_id = p.id
            LEFT JOIN task t ON te.task_id = t.id
            WHERE 1=1
        """
        params = []

        if project_filter:
            query += " AND te.project_id = ?"
            params.append(int(project_filter))
        if date_from:
            query += " AND te.date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND te.date <= ?"
            params.append(date_to)

        query += " ORDER BY te.date DESC, te.created_at DESC LIMIT 1000"
        entries = db.execute(query, params).fetchall()

        # Totals
        total_hours = sum(e['minutes'] for e in entries)
        billable_hours = sum(e['minutes'] for e in entries if e['billable'])

        # Dropdowns
        projects = db.execute(
            "SELECT id, name FROM project ORDER BY name"
        ).fetchall()
        tasks = db.execute(
            "SELECT id, title FROM task ORDER BY title"
        ).fetchall()

    return render_template(
        'time_tracking/entries.html',
        entries=entries,
        projects=projects,
        tasks=tasks,
        total_hours=total_hours,
        billable_hours=billable_hours,
    )


@bp.route('/new', methods=['GET', 'POST'])
@setup_required
def create():
    """Create a new time entry."""
    with get_db() as db:
        projects = db.execute(
            "SELECT id, name FROM project ORDER BY name"
        ).fetchall()
        tasks = db.execute(
            "SELECT id, title FROM task ORDER BY title"
        ).fetchall()

    if request.method == 'POST':
        entry_date = request.form.get('date', '').strip()
        project_id_str = request.form.get('project_id', '').strip()
        task_id_str = request.form.get('task_id', '').strip()
        hours_str = request.form.get('hours', '0').strip()
        description = request.form.get('description', '').strip()
        billable = 1 if request.form.get('billable') else 0

        # Validation
        if not entry_date:
            flash("Date is required.", "error")
            return render_template(
                'time_tracking/entries.html',
                entries=[],
                projects=projects,
                tasks=tasks,
                total_hours=0,
                billable_hours=0,
            )

        if not project_id_str:
            flash("Project is required.", "error")
            return render_template(
                'time_tracking/entries.html',
                entries=[],
                projects=projects,
                tasks=tasks,
                total_hours=0,
                billable_hours=0,
            )

        try:
            project_id = int(project_id_str)
        except (ValueError, TypeError):
            flash("Invalid project.", "error")
            return render_template(
                'time_tracking/entries.html',
                entries=[],
                projects=projects,
                tasks=tasks,
                total_hours=0,
                billable_hours=0,
            )

        task_id = None
        if task_id_str:
            try:
                task_id = int(task_id_str)
            except (ValueError, TypeError):
                task_id = None

        # Convert hours to minutes
        try:
            minutes = int(float(hours_str) * 60)
        except (ValueError, TypeError):
            minutes = 0

        if minutes <= 0:
            flash("Hours must be greater than zero.", "error")
            return render_template(
                'time_tracking/entries.html',
                entries=[],
                projects=projects,
                tasks=tasks,
                total_hours=0,
                billable_hours=0,
            )

        with get_db(immediate=True) as db:
            db.execute(
                """INSERT INTO time_entry (date, project_id, task_id, minutes, description, billable)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (entry_date, project_id, task_id, minutes, description, billable),
            )
            entry_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Get project name for activity log
            project_row = db.execute(
                "SELECT name FROM project WHERE id = ?", (project_id,)
            ).fetchone()
            project_name = project_row['name'] if project_row else 'Unknown'

            # Activity log
            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('logged', 'time_entry', entry_id, f"Logged {minutes / 60:.1f}h on {project_name}"),
            )

        flash("Time entry created.", "success")
        return redirect(url_for('time_tracking.index'))

    return render_template(
        'time_tracking/entries.html',
        entries=[],
        projects=projects,
        tasks=tasks,
        total_hours=0,
        billable_hours=0,
    )


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@setup_required
def edit(id):
    """Edit an existing time entry."""
    with get_db() as db:
        entry = db.execute(
            "SELECT * FROM time_entry WHERE id = ?", (id,)
        ).fetchone()
        if not entry:
            flash("Time entry not found.", "error")
            return redirect(url_for('time_tracking.index'))

        projects = db.execute(
            "SELECT id, name FROM project ORDER BY name"
        ).fetchall()
        tasks = db.execute(
            "SELECT id, title FROM task ORDER BY title"
        ).fetchall()

    if request.method == 'POST':
        entry_date = request.form.get('date', '').strip()
        project_id_str = request.form.get('project_id', '').strip()
        task_id_str = request.form.get('task_id', '').strip()
        hours_str = request.form.get('hours', '0').strip()
        description = request.form.get('description', '').strip()
        billable = 1 if request.form.get('billable') else 0

        if not entry_date:
            flash("Date is required.", "error")
            return render_template(
                'time_tracking/entries.html',
                entries=[],
                projects=projects,
                tasks=tasks,
                total_hours=0,
                billable_hours=0,
            )

        if not project_id_str:
            flash("Project is required.", "error")
            return render_template(
                'time_tracking/entries.html',
                entries=[],
                projects=projects,
                tasks=tasks,
                total_hours=0,
                billable_hours=0,
            )

        try:
            project_id = int(project_id_str)
        except (ValueError, TypeError):
            flash("Invalid project.", "error")
            return redirect(url_for('time_tracking.edit', id=id))

        task_id = None
        if task_id_str:
            try:
                task_id = int(task_id_str)
            except (ValueError, TypeError):
                task_id = None

        try:
            minutes = int(float(hours_str) * 60)
        except (ValueError, TypeError):
            minutes = 0

        if minutes <= 0:
            flash("Hours must be greater than zero.", "error")
            return redirect(url_for('time_tracking.edit', id=id))

        with get_db(immediate=True) as db:
            db.execute(
                """UPDATE time_entry
                   SET date = ?, project_id = ?, task_id = ?, minutes = ?,
                       description = ?, billable = ?
                   WHERE id = ?""",
                (entry_date, project_id, task_id, minutes, description, billable, id),
            )

            project_row = db.execute(
                "SELECT name FROM project WHERE id = ?", (project_id,)
            ).fetchone()
            project_name = project_row['name'] if project_row else 'Unknown'

            db.execute(
                "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
                ('logged', 'time_entry', id, f"Logged {minutes / 60:.1f}h on {project_name}"),
            )

        flash("Time entry updated.", "success")
        return redirect(url_for('time_tracking.index'))

    return render_template(
        'time_tracking/entries.html',
        entries=[],
        projects=projects,
        tasks=tasks,
        total_hours=0,
        billable_hours=0,
    )


@bp.route('/<int:id>/delete', methods=['POST'])
@setup_required
def delete(id):
    """Delete a time entry."""
    with get_db(immediate=True) as db:
        entry = db.execute(
            "SELECT te.*, p.name AS project_name FROM time_entry te "
            "JOIN project p ON te.project_id = p.id WHERE te.id = ?",
            (id,),
        ).fetchone()
        if not entry:
            flash("Time entry not found.", "error")
            return redirect(url_for('time_tracking.index'))

        db.execute("DELETE FROM time_entry WHERE id = ?", (id,))

        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('deleted', 'time_entry', id, f"Deleted time entry on {entry['project_name']}"),
        )

    flash("Time entry deleted.", "success")
    return redirect(url_for('time_tracking.index'))


@bp.route('/timesheet')
@setup_required
def timesheet():
    """Weekly timesheet view grouped by project."""
    # Determine week boundaries (Monday - Sunday)
    today = date.today()
    week_offset = request.args.get('week_offset', '0')
    try:
        week_offset = int(week_offset)
    except (ValueError, TypeError):
        week_offset = 0

    # Monday of the target week
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)

    week_start = monday.isoformat()
    week_end = sunday.isoformat()

    day_keys = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

    with get_db() as db:
        entries = db.execute(
            """SELECT te.date, te.minutes, p.name AS project_name
               FROM time_entry te
               JOIN project p ON te.project_id = p.id
               WHERE te.date >= ? AND te.date <= ?
               ORDER BY p.name, te.date""",
            (week_start, week_end),
        ).fetchall()

        projects = db.execute(
            "SELECT id, name FROM project ORDER BY name"
        ).fetchall()

        # Get weekly hours target from business_profile
        profile = db.execute(
            "SELECT weekly_hours_target FROM business_profile LIMIT 1"
        ).fetchone()
        target_hours = profile['weekly_hours_target'] if profile else 40
        target = target_hours * 60  # Convert hours to minutes

    # Build week_data: {project_name: {mon: mins, tue: mins, ...}}
    week_data = {}
    total_week = 0

    for entry in entries:
        pname = entry['project_name']
        if pname not in week_data:
            week_data[pname] = {d: 0 for d in day_keys}

        entry_date = date.fromisoformat(entry['date'])
        day_index = entry_date.weekday()  # 0=Mon, 6=Sun
        if 0 <= day_index <= 6:
            week_data[pname][day_keys[day_index]] += entry['minutes']
            total_week += entry['minutes']

    return render_template(
        'time_tracking/timesheet.html',
        week_data=week_data,
        week_start=week_start,
        week_end=week_end,
        projects=projects,
        total_week=total_week,
        target=target,
    )


@bp.route('/start', methods=['POST'])
@setup_required
def start_timer():
    """Start a timer. Returns JSON for JS consumption."""
    return jsonify({'status': 'started'})


@bp.route('/stop', methods=['POST'])
@setup_required
def stop_timer():
    """Stop a timer. Receives calculated minutes from JS, creates time entry."""
    project_id_str = request.form.get('project_id', '').strip()
    task_id_str = request.form.get('task_id', '').strip()
    minutes_str = request.form.get('minutes', '0').strip()
    description = request.form.get('description', '').strip()
    billable = 1 if request.form.get('billable') else 0

    if not project_id_str:
        flash("Project is required to stop timer.", "error")
        return redirect(url_for('time_tracking.index'))

    try:
        project_id = int(project_id_str)
    except (ValueError, TypeError):
        flash("Invalid project.", "error")
        return redirect(url_for('time_tracking.index'))

    task_id = None
    if task_id_str:
        try:
            task_id = int(task_id_str)
        except (ValueError, TypeError):
            task_id = None

    try:
        minutes = int(float(minutes_str))
    except (ValueError, TypeError):
        minutes = 0

    if minutes <= 0:
        flash("Timer recorded zero minutes.", "warning")
        return redirect(url_for('time_tracking.index'))

    entry_date = date.today().isoformat()

    with get_db(immediate=True) as db:
        db.execute(
            """INSERT INTO time_entry (date, project_id, task_id, minutes, description, billable)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entry_date, project_id, task_id, minutes, description, billable),
        )
        entry_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        project_row = db.execute(
            "SELECT name FROM project WHERE id = ?", (project_id,)
        ).fetchone()
        project_name = project_row['name'] if project_row else 'Unknown'

        db.execute(
            "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
            ('logged', 'time_entry', entry_id, f"Logged {minutes / 60:.1f}h on {project_name}"),
        )

    flash(f"Timer stopped. Logged {minutes / 60:.1f}h.", "success")
    return redirect(url_for('time_tracking.index'))
