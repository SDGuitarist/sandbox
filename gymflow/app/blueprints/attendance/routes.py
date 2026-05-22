from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort

from app.auth import login_required
from app.db import get_db
from app.models import (
    check_in_class,
    check_in_open_gym,
    check_out as model_check_out,
    get_attendance,
    get_attendance_by_member,
    get_today_checkins,
    delete_attendance as model_delete_attendance,
    get_all_members,
    get_schedules_by_date,
)

bp = Blueprint('attendance', __name__)


@bp.route('/')
@login_required
def list_attendance():
    conn = get_db()
    records = get_today_checkins(conn)
    return render_template('attendance/list.html', records=records)


@bp.route('/check-in', methods=['GET'])
@login_required
def check_in_form():
    conn = get_db()
    today = date.today().isoformat()
    return render_template(
        'attendance/check_in.html',
        members=get_all_members(conn),
        schedules=get_schedules_by_date(conn, today),
    )


@bp.route('/check-in', methods=['POST'])
@login_required
def check_in():
    conn = get_db()

    # Validate member_id (FC4: required, must be int)
    raw_member_id = request.form.get('member_id', '').strip()
    if not raw_member_id:
        flash('Member is required.', 'error')
        return redirect(url_for('attendance.check_in_form'))
    try:
        member_id = int(raw_member_id)
    except (ValueError, TypeError):
        flash('Member is required.', 'error')
        return redirect(url_for('attendance.check_in_form'))

    # Validate attendance_type (FC4: must be 'class' or 'open_gym')
    attendance_type = request.form.get('attendance_type', '').strip()
    if attendance_type not in ('class', 'open_gym'):
        flash('Invalid type.', 'error')
        return redirect(url_for('attendance.check_in_form'))

    if attendance_type == 'class':
        # Validate class_schedule_id (FC4: required when type='class')
        raw_schedule_id = request.form.get('class_schedule_id', '').strip()
        if not raw_schedule_id:
            flash('Class is required for class check-in.', 'error')
            return redirect(url_for('attendance.check_in_form'))
        try:
            schedule_id = int(raw_schedule_id)
        except (ValueError, TypeError):
            flash('Class is required for class check-in.', 'error')
            return redirect(url_for('attendance.check_in_form'))

        # FC29: check_in_class handles its own BEGIN IMMEDIATE + capacity check
        # FC37: check_in_class commits internally
        try:
            check_in_class(conn, member_id, schedule_id)
            flash('Checked in successfully.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('attendance.check_in_form'))
    else:
        # open_gym -- no schedule needed
        # FC37: check_in_open_gym commits internally
        check_in_open_gym(conn, member_id)
        flash('Checked in successfully.', 'success')

    return redirect(url_for('attendance.list_attendance'))


@bp.route('/<int:attendance_id>/check-out', methods=['POST'])
@login_required
def check_out(attendance_id):
    conn = get_db()

    # Coordinated Behavior #7: 404 pattern
    record = get_attendance(conn, attendance_id)
    if record is None:
        abort(404)

    # Validate check_out_time is NULL (not already checked out)
    if record['check_out_time'] is not None:
        flash('Already checked out.', 'error')
        return redirect(url_for('attendance.list_attendance'))

    # FC37: model_check_out commits internally
    model_check_out(conn, attendance_id)
    flash('Checked out successfully.', 'success')
    return redirect(url_for('attendance.list_attendance'))


@bp.route('/<int:attendance_id>/delete', methods=['POST'])
@login_required
def delete_attendance(attendance_id):
    conn = get_db()

    # Coordinated Behavior #7: 404 pattern
    record = get_attendance(conn, attendance_id)
    if record is None:
        abort(404)

    # FC37: model_delete_attendance commits internally
    # attendance table has no RESTRICT FK children, so no IntegrityError handling needed
    model_delete_attendance(conn, attendance_id)
    flash('Attendance record deleted successfully.', 'success')
    return redirect(url_for('attendance.list_attendance'))
