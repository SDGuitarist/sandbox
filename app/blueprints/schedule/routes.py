"""Schedule blueprint routes.

Shoot-day scheduling: list shoot dates, day view with drag-and-drop reorder,
add scenes to the schedule, reorder (JSON), and delete entries.
"""

import re

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
    jsonify, g,
)

from app.database import get_db
from app.blueprints.auth.routes import (
    login_required, require_project_member, require_role,
)
from app.models.scene_models import get_scenes
from app.models.location_models import get_locations
from app.models.schedule_models import (
    create_schedule_entry, get_schedule_entries, get_shoot_dates,
    reorder_schedule, delete_schedule_entry,
)

bp = Blueprint('schedule', __name__)

DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def index(project_id):
    conn = get_db()
    shoot_dates = get_shoot_dates(conn, project_id)
    return render_template(
        'schedule/index.html',
        project=g.project,
        shoot_dates=shoot_dates,
    )


@bp.route('/<int:project_id>/day/<date>')
@login_required
@require_project_member
def day_view(project_id, date):
    conn = get_db()
    entries = get_schedule_entries(conn, project_id, date)
    return render_template(
        'schedule/day.html',
        project=g.project,
        entries=entries,
        shoot_date=date,
    )


@bp.route('/<int:project_id>/new')
@login_required
@require_project_member
@require_role('producer', 'ad')
def new(project_id):
    conn = get_db()
    scenes = get_scenes(conn, project_id)
    locations = get_locations(conn, project_id)
    return render_template(
        'schedule/new.html',
        project=g.project,
        scenes=scenes,
        locations=locations,
    )


@bp.route('/<int:project_id>', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def create(project_id):
    conn = get_db()

    # scene_id: required, numeric, must exist in this project.
    try:
        scene_id = int(request.form['scene_id'])
    except (KeyError, ValueError):
        flash('A scene is required', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))

    scene = conn.execute(
        'SELECT id FROM scenes WHERE id = ? AND project_id = ?',
        (scene_id, project_id)
    ).fetchone()
    if scene is None:
        flash('Selected scene was not found', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))

    # location_id: optional. If supplied, must be numeric and exist in project.
    location_raw = (request.form.get('location_id') or '').strip()
    location_id = None
    if location_raw:
        try:
            location_id = int(location_raw)
        except ValueError:
            flash('Selected location was not found', 'error')
            return redirect(url_for('schedule.new', project_id=project_id))
        location = conn.execute(
            'SELECT id FROM locations WHERE id = ? AND project_id = ?',
            (location_id, project_id)
        ).fetchone()
        if location is None:
            flash('Selected location was not found', 'error')
            return redirect(url_for('schedule.new', project_id=project_id))

    # shoot_date: required, strict YYYY-MM-DD format.
    shoot_date = (request.form.get('shoot_date') or '').strip()
    if not DATE_RE.match(shoot_date):
        flash('Shoot date must be in YYYY-MM-DD format', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))

    # Append to the end of that day's strip board.
    max_row = conn.execute(
        '''SELECT COALESCE(MAX(sort_order), -1) AS m FROM schedule_entries
           WHERE project_id = ? AND shoot_date = ?''',
        (project_id, shoot_date)
    ).fetchone()
    next_sort = max_row['m'] + 1

    entry_id = create_schedule_entry(
        conn, project_id, scene_id, location_id, shoot_date, next_sort
    )
    if entry_id is None:
        flash('That scene is already on the schedule', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))

    flash('Scene added to the schedule', 'success')
    return redirect(url_for('schedule.day_view', project_id=project_id, date=shoot_date))


@bp.route('/<int:project_id>/reorder', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def reorder(project_id):
    conn = get_db()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid request body'}), 400

    shoot_date = data.get('shoot_date')
    if not isinstance(shoot_date, str) or not DATE_RE.match(shoot_date):
        return jsonify({'error': 'Invalid shoot_date'}), 400

    order = data.get('order')
    if not isinstance(order, list) or not order:
        return jsonify({'error': 'Invalid order'}), 400
    try:
        ordered_ids = [int(x) for x in order]
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid order'}), 400

    ok = reorder_schedule(conn, project_id, shoot_date, ordered_ids)
    if not ok:
        return jsonify({'error': 'Order does not match the scheduled entries'}), 400
    return jsonify({'status': 'ok'})


@bp.route('/<int:project_id>/<int:entry_id>/delete', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def delete(project_id, entry_id):
    conn = get_db()
    entry = conn.execute(
        'SELECT id, project_id, shoot_date FROM schedule_entries WHERE id = ?',
        (entry_id,)
    ).fetchone()
    if entry is None or entry['project_id'] != project_id:
        abort(404)

    shoot_date = entry['shoot_date']
    # delete_schedule_entry does NOT commit — the caller owns the transaction.
    conn.execute('BEGIN IMMEDIATE')
    try:
        delete_schedule_entry(conn, entry_id)
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    flash('Schedule entry removed', 'success')
    return redirect(url_for('schedule.day_view', project_id=project_id, date=shoot_date))
