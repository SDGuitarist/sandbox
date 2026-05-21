from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.db import get_db
from app.models.staff_models import (
    create_shift as model_create_shift,
    create_staff,
    delete_shift as model_delete_shift,
    delete_staff,
    get_all_staff,
    get_shift,
    get_shifts_by_date,
    get_shifts_by_staff,
    get_staff_member,
    update_shift,
    update_staff,
)

bp = Blueprint('staff', __name__)

ROLES = ['chef', 'sous_chef', 'server', 'host', 'busser', 'manager']


@bp.route('/')
def list_staff():
    conn = get_db()
    staff = get_all_staff(conn)
    return render_template('staff/list.html', staff=staff)


@bp.route('/create', methods=['GET'])
def create_form():
    return render_template('staff/form.html', member=None)


@bp.route('/create', methods=['POST'])
def create():
    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(request.url)

    role = request.form.get('role', 'server').strip()
    if role not in ROLES:
        role = 'server'

    phone = request.form.get('phone', '').strip()[:50]
    email = request.form.get('email', '').strip()[:200]

    conn = get_db()
    conn.execute("BEGIN")
    create_staff(conn, name, role, phone, email)
    conn.commit()

    flash('Staff member created successfully.', 'success')
    return redirect(url_for('staff.list_staff'))


@bp.route('/<int:id>')
def detail(id):
    conn = get_db()
    member = get_staff_member(conn, id)
    if member is None:
        flash('Staff member not found.', 'error')
        return redirect(url_for('staff.list_staff'))

    shifts = get_shifts_by_staff(conn, id)
    return render_template('staff/detail.html', member=member, shifts=shifts)


@bp.route('/<int:id>/edit', methods=['GET'])
def edit_form(id):
    conn = get_db()
    member = get_staff_member(conn, id)
    if member is None:
        flash('Staff member not found.', 'error')
        return redirect(url_for('staff.list_staff'))

    return render_template('staff/form.html', member=member)


@bp.route('/<int:id>/edit', methods=['POST'])
def edit(id):
    conn = get_db()
    member = get_staff_member(conn, id)
    if member is None:
        flash('Staff member not found.', 'error')
        return redirect(url_for('staff.list_staff'))

    name = request.form.get('name', '').strip()[:200]
    if not name:
        flash('Name is required.', 'error')
        return redirect(request.url)

    role = request.form.get('role', 'server').strip()
    if role not in ROLES:
        role = 'server'

    phone = request.form.get('phone', '').strip()[:50]
    email = request.form.get('email', '').strip()[:200]
    is_active = 1 if request.form.get('is_active') else 0

    conn.execute("BEGIN")
    update_staff(conn, id, name, role, phone, email, is_active)
    conn.commit()

    flash('Staff member updated successfully.', 'success')
    return redirect(url_for('staff.detail', id=id))


@bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    conn = get_db()
    member = get_staff_member(conn, id)
    if member is None:
        flash('Staff member not found.', 'error')
        return redirect(url_for('staff.list_staff'))

    conn.execute("BEGIN")
    delete_staff(conn, id)
    conn.commit()

    flash('Staff member deleted.', 'success')
    return redirect(url_for('staff.list_staff'))


@bp.route('/schedule')
def schedule():
    selected_date = request.args.get('date', date.today().isoformat())
    conn = get_db()
    shifts = get_shifts_by_date(conn, selected_date)
    staff = get_all_staff(conn)
    return render_template(
        'staff/schedule.html',
        shifts=shifts,
        staff=staff,
        selected_date=selected_date,
    )


@bp.route('/schedule/create', methods=['GET'])
def create_shift_form():
    conn = get_db()
    staff = get_all_staff(conn)
    return render_template('staff/shift_form.html', shift=None, staff=staff)


@bp.route('/schedule/create', methods=['POST'])
def create_shift():
    staff_id_raw = request.form.get('staff_id', '')
    try:
        staff_id = int(staff_id_raw)
    except (ValueError, TypeError):
        flash('Staff member is required.', 'error')
        return redirect(request.url)

    shift_date = request.form.get('shift_date', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()

    if not shift_date or not start_time or not end_time:
        flash('Date, start time, and end time are required.', 'error')
        return redirect(request.url)

    role = request.form.get('role', 'server').strip()
    if role not in ROLES:
        role = 'server'

    notes = request.form.get('notes', '').strip()[:500]

    conn = get_db()
    member = get_staff_member(conn, staff_id)
    if member is None:
        flash('Staff member not found.', 'error')
        return redirect(request.url)

    conn.execute("BEGIN")
    model_create_shift(conn, staff_id, shift_date, start_time, end_time, role, notes)
    conn.commit()

    flash('Shift created successfully.', 'success')
    return redirect(url_for('staff.schedule', date=shift_date))


@bp.route('/schedule/<int:id>/edit', methods=['GET'])
def edit_shift_form(id):
    conn = get_db()
    shift = get_shift(conn, id)
    if shift is None:
        flash('Shift not found.', 'error')
        return redirect(url_for('staff.schedule'))

    staff = get_all_staff(conn)
    return render_template('staff/shift_form.html', shift=shift, staff=staff)


@bp.route('/schedule/<int:id>/edit', methods=['POST'])
def edit_shift(id):
    conn = get_db()
    shift = get_shift(conn, id)
    if shift is None:
        flash('Shift not found.', 'error')
        return redirect(url_for('staff.schedule'))

    staff_id_raw = request.form.get('staff_id', '')
    try:
        staff_id = int(staff_id_raw)
    except (ValueError, TypeError):
        flash('Staff member is required.', 'error')
        return redirect(request.url)

    shift_date = request.form.get('shift_date', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()

    if not shift_date or not start_time or not end_time:
        flash('Date, start time, and end time are required.', 'error')
        return redirect(request.url)

    role = request.form.get('role', 'server').strip()
    if role not in ROLES:
        role = 'server'

    notes = request.form.get('notes', '').strip()[:500]

    member = get_staff_member(conn, staff_id)
    if member is None:
        flash('Staff member not found.', 'error')
        return redirect(request.url)

    conn.execute("BEGIN")
    update_shift(conn, id, staff_id, shift_date, start_time, end_time, role, notes)
    conn.commit()

    flash('Shift updated successfully.', 'success')
    return redirect(url_for('staff.schedule', date=shift_date))


@bp.route('/schedule/<int:id>/delete', methods=['POST'])
def delete_shift(id):
    conn = get_db()
    shift = get_shift(conn, id)
    if shift is None:
        flash('Shift not found.', 'error')
        return redirect(url_for('staff.schedule'))

    shift_date = shift['shift_date']

    conn.execute("BEGIN")
    model_delete_shift(conn, id)
    conn.commit()

    flash('Shift deleted.', 'success')
    return redirect(url_for('staff.schedule', date=shift_date))
