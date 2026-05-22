import re
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models.staff_models import (
    create_staff,
    delete_staff,
    get_all_staff,
    get_staff_member,
    update_staff,
)

bp = Blueprint('staff', __name__)

VALID_ROLES = ('brewer', 'server', 'manager')
VALID_STATUSES = ('active', 'inactive')


def _validate_staff_form(require_status=False):
    """Validate staff form fields. Returns (data_dict, error_list).

    When require_status is True (edit form), status is also validated.
    """
    errors = []

    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        errors.append('Staff name is required')

    role = request.form.get('role', '').strip()
    if role not in VALID_ROLES:
        errors.append('Invalid role')

    email_raw = request.form.get('email', '').strip()
    email = email_raw if email_raw else None
    if email is not None:
        # Basic email format check: something@something.something
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            errors.append('Invalid email')

    phone = request.form.get('phone', '').strip()
    hire_date_raw = request.form.get('hire_date', '').strip()
    hire_date = hire_date_raw if hire_date_raw else None

    status = None
    if require_status:
        status = request.form.get('status', '').strip()
        if status not in VALID_STATUSES:
            errors.append('Invalid status')

    data = {
        'name': name,
        'role': role,
        'email': email,
        'phone': phone,
        'hire_date': hire_date,
        'status': status,
    }
    return data, errors


@bp.route('/')
@login_required
def list():
    conn = get_db()
    staff = get_all_staff(conn)
    return render_template('staff/list.html', staff=staff)


@bp.route('/new')
@login_required
def new():
    return render_template('staff/form.html', staff=None, roles=VALID_ROLES)


@bp.route('/', methods=['POST'])
@login_required
def create():
    data, errors = _validate_staff_form(require_status=False)

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('staff.new'))

    conn = get_db()
    try:
        staff_id = create_staff(
            conn,
            data['name'],
            data['role'],
            data['email'],
            data['phone'],
            data['hire_date'],
        )
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Email already in use', 'error')
        return redirect(url_for('staff.new'))

    flash('Staff member created', 'success')
    return redirect(url_for('staff.detail', staff_id=staff_id))


@bp.route('/<int:staff_id>')
@login_required
def detail(staff_id):
    conn = get_db()
    member = get_staff_member(conn, staff_id)
    if member is None:
        abort(404)
    return render_template('staff/detail.html', member=member)


@bp.route('/<int:staff_id>/edit')
@login_required
def edit(staff_id):
    conn = get_db()
    member = get_staff_member(conn, staff_id)
    if member is None:
        abort(404)
    return render_template(
        'staff/form.html',
        staff=member,
        roles=VALID_ROLES,
        statuses=VALID_STATUSES,
    )


@bp.route('/<int:staff_id>/edit', methods=['POST'])
@login_required
def update(staff_id):
    conn = get_db()
    member = get_staff_member(conn, staff_id)
    if member is None:
        abort(404)

    data, errors = _validate_staff_form(require_status=True)

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('staff.edit', staff_id=staff_id))

    try:
        update_staff(
            conn,
            staff_id,
            data['name'],
            data['role'],
            data['email'],
            data['phone'],
            data['hire_date'],
            data['status'],
        )
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Email already in use', 'error')
        return redirect(url_for('staff.edit', staff_id=staff_id))

    flash('Staff member updated', 'success')
    return redirect(url_for('staff.detail', staff_id=staff_id))


@bp.route('/<int:staff_id>/delete', methods=['POST'])
@login_required
def delete(staff_id):
    conn = get_db()
    member = get_staff_member(conn, staff_id)
    if member is None:
        abort(404)

    try:
        delete_staff(conn, staff_id)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Cannot delete: staff member is referenced by other records', 'error')
        return redirect(url_for('staff.detail', staff_id=staff_id))

    flash('Staff member deleted', 'success')
    return redirect(url_for('staff.list'))
