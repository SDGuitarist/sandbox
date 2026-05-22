import sqlite3
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models import (
    copy_week_schedules,
    create_schedule,
    delete_schedule,
    get_active_trainers,
    get_all_class_types,
    get_attendance_by_schedule,
    get_schedule,
    get_schedule_attendance_count,
    get_schedules_by_date,
    get_schedules_by_date_range,
    get_schedules_by_trainer,
    update_schedule,
)

bp = Blueprint('schedules', __name__)


def _validate_date(value, field_label):
    """Validate a YYYY-MM-DD date string. Returns the string or None on failure."""
    if not value or not value.strip():
        return None
    value = value.strip()
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return None
    return value


def _validate_time(value, field_label):
    """Validate an HH:MM time string. Returns the string or None on failure."""
    if not value or not value.strip():
        return None
    value = value.strip()
    try:
        datetime.strptime(value, '%H:%M')
    except ValueError:
        return None
    return value


@bp.route('/')
@login_required
def list_schedules():
    conn = get_db()
    selected_date = request.args.get('date', '').strip()

    # Default to today if no date provided or invalid
    if not selected_date:
        selected_date = date.today().isoformat()
    else:
        if _validate_date(selected_date, 'date') is None:
            selected_date = date.today().isoformat()

    schedules = get_schedules_by_date(conn, selected_date)
    return render_template('schedules/list.html',
                           schedules=schedules,
                           selected_date=selected_date)


@bp.route('/new')
@login_required
def new_schedule():
    conn = get_db()
    return render_template('schedules/form.html',
                           schedule=None,
                           class_types=get_all_class_types(conn),
                           trainers=get_active_trainers(conn))


@bp.route('/', methods=['POST'])
@login_required
def create_schedule_route():
    conn = get_db()

    # Validate class_type_id (required, int)
    try:
        class_type_id = int(request.form.get('class_type_id', ''))
    except (ValueError, TypeError):
        flash('Class type is required.', 'error')
        return redirect(url_for('schedules.new_schedule'))

    # Validate trainer_id (int or empty -> None)
    trainer_id_raw = request.form.get('trainer_id', '').strip()
    trainer_id = None
    if trainer_id_raw:
        try:
            trainer_id = int(trainer_id_raw)
        except (ValueError, TypeError):
            flash('Invalid trainer.', 'error')
            return redirect(url_for('schedules.new_schedule'))

    # Validate session_date (required, YYYY-MM-DD)
    session_date = _validate_date(request.form.get('session_date', ''), 'date')
    if session_date is None:
        flash('Valid date is required.', 'error')
        return redirect(url_for('schedules.new_schedule'))

    # Validate start_time (required, HH:MM)
    start_time = _validate_time(request.form.get('start_time', ''), 'start time')
    if start_time is None:
        flash('Valid start time is required.', 'error')
        return redirect(url_for('schedules.new_schedule'))

    # Validate end_time (required, HH:MM)
    end_time = _validate_time(request.form.get('end_time', ''), 'end time')
    if end_time is None:
        flash('Valid end time is required.', 'error')
        return redirect(url_for('schedules.new_schedule'))

    # Validate capacity (int, >= 1)
    try:
        capacity = int(request.form.get('capacity', ''))
        if capacity < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Capacity must be at least 1.', 'error')
        return redirect(url_for('schedules.new_schedule'))

    room = request.form.get('room', '').strip()
    notes = request.form.get('notes', '').strip()

    schedule_id = create_schedule(conn, class_type_id, trainer_id, session_date,
                                  start_time, end_time, room, capacity, notes)
    flash('Schedule created successfully.', 'success')
    return redirect(url_for('schedules.list_schedules'))


@bp.route('/<int:schedule_id>')
@login_required
def detail(schedule_id):
    conn = get_db()
    schedule = get_schedule(conn, schedule_id)
    if schedule is None:
        abort(404)
    return render_template('schedules/detail.html',
                           schedule=schedule,
                           attendees=get_attendance_by_schedule(conn, schedule_id),
                           attendance_count=get_schedule_attendance_count(conn, schedule_id))


@bp.route('/<int:schedule_id>/edit')
@login_required
def edit_schedule(schedule_id):
    conn = get_db()
    schedule = get_schedule(conn, schedule_id)
    if schedule is None:
        abort(404)
    return render_template('schedules/form.html',
                           schedule=schedule,
                           class_types=get_all_class_types(conn),
                           trainers=get_active_trainers(conn))


@bp.route('/<int:schedule_id>/edit', methods=['POST'])
@login_required
def update_schedule_route(schedule_id):
    conn = get_db()
    schedule = get_schedule(conn, schedule_id)
    if schedule is None:
        abort(404)

    # Validate class_type_id (required, int)
    try:
        class_type_id = int(request.form.get('class_type_id', ''))
    except (ValueError, TypeError):
        flash('Class type is required.', 'error')
        return redirect(url_for('schedules.edit_schedule', schedule_id=schedule_id))

    # Validate trainer_id (int or empty -> None)
    trainer_id_raw = request.form.get('trainer_id', '').strip()
    trainer_id = None
    if trainer_id_raw:
        try:
            trainer_id = int(trainer_id_raw)
        except (ValueError, TypeError):
            flash('Invalid trainer.', 'error')
            return redirect(url_for('schedules.edit_schedule', schedule_id=schedule_id))

    # Validate session_date (required, YYYY-MM-DD)
    session_date = _validate_date(request.form.get('session_date', ''), 'date')
    if session_date is None:
        flash('Valid date is required.', 'error')
        return redirect(url_for('schedules.edit_schedule', schedule_id=schedule_id))

    # Validate start_time (required, HH:MM)
    start_time = _validate_time(request.form.get('start_time', ''), 'start time')
    if start_time is None:
        flash('Valid start time is required.', 'error')
        return redirect(url_for('schedules.edit_schedule', schedule_id=schedule_id))

    # Validate end_time (required, HH:MM)
    end_time = _validate_time(request.form.get('end_time', ''), 'end time')
    if end_time is None:
        flash('Valid end time is required.', 'error')
        return redirect(url_for('schedules.edit_schedule', schedule_id=schedule_id))

    # Validate capacity (int, >= 1)
    try:
        capacity = int(request.form.get('capacity', ''))
        if capacity < 1:
            raise ValueError
    except (ValueError, TypeError):
        flash('Capacity must be at least 1.', 'error')
        return redirect(url_for('schedules.edit_schedule', schedule_id=schedule_id))

    room = request.form.get('room', '').strip()
    notes = request.form.get('notes', '').strip()

    update_schedule(conn, schedule_id, class_type_id, trainer_id, session_date,
                    start_time, end_time, room, capacity, notes)
    flash('Schedule updated successfully.', 'success')
    return redirect(url_for('schedules.detail', schedule_id=schedule_id))


@bp.route('/<int:schedule_id>/delete', methods=['POST'])
@login_required
def delete_schedule_route(schedule_id):
    conn = get_db()
    schedule = get_schedule(conn, schedule_id)
    if schedule is None:
        abort(404)
    try:
        delete_schedule(conn, schedule_id)
        flash('Schedule deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete: referenced by other records.', 'error')
    return redirect(url_for('schedules.list_schedules'))


@bp.route('/copy-week', methods=['POST'])
@login_required
def copy_week():
    # Validate source_date (required, YYYY-MM-DD)
    source_date = _validate_date(request.form.get('source_date', ''), 'source date')
    if source_date is None:
        flash('Source date is required.', 'error')
        return redirect(url_for('schedules.list_schedules'))

    # Validate target_date (required, YYYY-MM-DD)
    target_date = _validate_date(request.form.get('target_date', ''), 'target date')
    if target_date is None:
        flash('Target date is required.', 'error')
        return redirect(url_for('schedules.list_schedules'))

    conn = get_db()
    count = copy_week_schedules(conn, source_date, target_date)
    flash(f'Copied {count} classes to next week.', 'success')
    return redirect(url_for('schedules.list_schedules'))
