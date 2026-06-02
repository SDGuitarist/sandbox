"""Schedule blueprint -- shoot day management with drag-and-drop reorder."""

import re
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, g, jsonify
)

from app.blueprints.auth.routes import login_required, require_project_member, require_role
from app.database import get_db
from app.models.schedule_models import (
    create_schedule_entry,
    get_schedule_entries,
    get_shoot_dates,
    reorder_schedule,
    delete_schedule_entry,
)
from app.models.scene_models import get_scenes
from app.models.location_models import get_locations

bp = Blueprint('schedule', __name__)


@bp.route('/<int:project_id>')
@login_required
@require_project_member
def index(project_id):
    """List all shoot dates for the project."""
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
    """Day view with SortableJS drag-and-drop schedule entries."""
    # Validate date format
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        abort(404)

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
    """Form to add a scene to the schedule."""
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
    """Create a new schedule entry."""
    conn = get_db()

    # Validate scene_id
    scene_id_raw = request.form.get('scene_id', '').strip()
    if not scene_id_raw:
        flash('Scene is required', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))
    try:
        scene_id = int(scene_id_raw)
    except (ValueError, TypeError):
        flash('Invalid scene', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))

    # Verify scene exists and belongs to project
    scene = conn.execute(
        'SELECT id FROM scenes WHERE id = ? AND project_id = ?',
        (scene_id, project_id)
    ).fetchone()
    if scene is None:
        flash('Scene not found', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))

    # Validate location_id
    location_id_raw = request.form.get('location_id', '').strip()
    location_id = None
    if location_id_raw:
        try:
            location_id = int(location_id_raw)
        except (ValueError, TypeError):
            flash('Invalid location', 'error')
            return redirect(url_for('schedule.new', project_id=project_id))

        loc = conn.execute(
            'SELECT id FROM locations WHERE id = ? AND project_id = ?',
            (location_id, project_id)
        ).fetchone()
        if loc is None:
            flash('Location not found', 'error')
            return redirect(url_for('schedule.new', project_id=project_id))

    # Validate shoot_date
    shoot_date = request.form.get('shoot_date', '').strip()
    if not shoot_date or not re.match(r'^\d{4}-\d{2}-\d{2}$', shoot_date):
        flash('Valid date (YYYY-MM-DD) is required', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))

    # Determine sort_order: append at end of the day's entries
    existing_count = conn.execute(
        'SELECT COUNT(*) AS cnt FROM schedule_entries WHERE project_id = ? AND shoot_date = ?',
        (project_id, shoot_date)
    ).fetchone()['cnt']
    sort_order = existing_count

    # Create entry (TOCTOU-safe -- handles duplicate scene check internally)
    entry_id = create_schedule_entry(conn, project_id, scene_id, location_id, shoot_date, sort_order)
    if entry_id is None:
        flash('This scene is already scheduled', 'error')
        return redirect(url_for('schedule.new', project_id=project_id))

    flash('Scene added to schedule', 'success')
    return redirect(url_for('schedule.day_view', project_id=project_id, date=shoot_date))


@bp.route('/<int:project_id>/reorder', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def reorder(project_id):
    """Reorder schedule entries via JSON POST from SortableJS.

    Expects JSON body: {order: [int, ...], shoot_date: "YYYY-MM-DD"}
    Returns JSON response.
    """
    conn = get_db()
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Invalid JSON'}), 400

    ordered_ids = data.get('order')
    shoot_date = data.get('shoot_date')

    if not isinstance(ordered_ids, list) or not shoot_date:
        return jsonify({'error': 'Missing order or shoot_date'}), 400

    # Validate shoot_date format
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', shoot_date):
        return jsonify({'error': 'Invalid date format'}), 400

    # Validate all IDs are integers
    try:
        ordered_ids = [int(i) for i in ordered_ids]
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid ID in order list'}), 400

    # reorder_schedule validates the full ID set inside BEGIN IMMEDIATE
    success = reorder_schedule(conn, project_id, shoot_date, ordered_ids)
    if not success:
        return jsonify({'error': 'ID set does not match scheduled entries for this date'}), 400

    return jsonify({'ok': True})


@bp.route('/<int:project_id>/<int:entry_id>/delete', methods=['POST'])
@login_required
@require_project_member
@require_role('producer', 'ad')
def delete(project_id, entry_id):
    """Delete a schedule entry."""
    conn = get_db()

    # Verify entry exists and belongs to project (IDOR prevention per FC35)
    entry = conn.execute(
        'SELECT id, project_id, shoot_date FROM schedule_entries WHERE id = ?',
        (entry_id,)
    ).fetchone()
    if entry is None:
        abort(404)
    if entry['project_id'] != project_id:
        abort(404)

    shoot_date = entry['shoot_date']

    # delete_schedule_entry does NOT commit -- we manage the transaction
    conn.execute('BEGIN IMMEDIATE')
    try:
        delete_schedule_entry(conn, entry_id)
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    flash('Schedule entry deleted', 'success')
    return redirect(url_for('schedule.day_view', project_id=project_id, date=shoot_date))
