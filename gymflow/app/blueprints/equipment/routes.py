import math
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models import (
    create_equipment,
    delete_equipment,
    get_all_equipment,
    get_equipment,
    get_equipment_by_status,
    get_maintenance_by_equipment,
    update_equipment,
)

bp = Blueprint('equipment', __name__)

VALID_STATUSES = ('available', 'in_use', 'maintenance', 'retired')


def _parse_price_cents(field_name='purchase_price'):
    """Parse a dollar amount from form input into cents.

    Returns (cents, error_redirect) tuple. If parsing succeeds,
    error_redirect is None. If parsing fails, cents is None and
    error_redirect is a redirect response to flash and return.
    """
    try:
        raw = float(request.form.get(field_name, '0'))
        if math.isnan(raw) or math.isinf(raw):
            raise ValueError('Invalid price')
        cents = round(raw * 100)
        if cents < 0:
            flash('Price cannot be negative.', 'error')
            return None, redirect(request.url)
        if cents > 99999999:  # Cap at $999,999.99
            flash('Price too large.', 'error')
            return None, redirect(request.url)
        return cents, None
    except (ValueError, TypeError):
        flash('Valid price is required.', 'error')
        return None, redirect(request.url)


@bp.route('/')
@login_required
def list_equipment():
    conn = get_db()
    status_filter = request.args.get('status', '')
    if status_filter and status_filter in VALID_STATUSES:
        equipment_list = get_equipment_by_status(conn, status_filter)
    else:
        equipment_list = get_all_equipment(conn)
    return render_template('equipment/list.html', equipment_list=equipment_list)


@bp.route('/new')
@login_required
def new_equipment():
    return render_template('equipment/form.html', item=None)


@bp.route('/', methods=['POST'])
@login_required
def create_equipment_route():
    conn = get_db()

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return redirect(url_for('equipment.new_equipment'))

    category = request.form.get('category', '').strip()
    serial_number = request.form.get('serial_number', '').strip()
    purchase_date = request.form.get('purchase_date', '').strip() or None
    location = request.form.get('location', '').strip()
    notes = request.form.get('notes', '').strip()

    status = request.form.get('status', 'available')
    if status not in VALID_STATUSES:
        flash('Invalid status.', 'error')
        return redirect(url_for('equipment.new_equipment'))

    cents, err = _parse_price_cents('purchase_price')
    if err is not None:
        return err

    equip_id = create_equipment(
        conn, name, category, serial_number, purchase_date,
        cents, status, location, notes,
    )
    flash('Equipment created successfully.', 'success')
    return redirect(url_for('equipment.detail', equipment_id=equip_id))


@bp.route('/<int:equipment_id>')
@login_required
def detail(equipment_id):
    conn = get_db()
    item = get_equipment(conn, equipment_id)
    if item is None:
        abort(404)
    maintenance_history = get_maintenance_by_equipment(conn, equipment_id)
    return render_template(
        'equipment/detail.html',
        item=item,
        maintenance_history=maintenance_history,
    )


@bp.route('/<int:equipment_id>/edit')
@login_required
def edit_equipment(equipment_id):
    conn = get_db()
    item = get_equipment(conn, equipment_id)
    if item is None:
        abort(404)
    return render_template('equipment/form.html', item=item)


@bp.route('/<int:equipment_id>/edit', methods=['POST'])
@login_required
def update_equipment_route(equipment_id):
    conn = get_db()
    item = get_equipment(conn, equipment_id)
    if item is None:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return redirect(url_for('equipment.edit_equipment', equipment_id=equipment_id))

    category = request.form.get('category', '').strip()
    serial_number = request.form.get('serial_number', '').strip()
    purchase_date = request.form.get('purchase_date', '').strip() or None
    location = request.form.get('location', '').strip()
    notes = request.form.get('notes', '').strip()

    status = request.form.get('status', 'available')
    if status not in VALID_STATUSES:
        flash('Invalid status.', 'error')
        return redirect(url_for('equipment.edit_equipment', equipment_id=equipment_id))

    cents, err = _parse_price_cents('purchase_price')
    if err is not None:
        return err

    update_equipment(
        conn, equipment_id, name, category, serial_number,
        purchase_date, cents, status, location, notes,
    )
    flash('Equipment updated successfully.', 'success')
    return redirect(url_for('equipment.detail', equipment_id=equipment_id))


@bp.route('/<int:equipment_id>/delete', methods=['POST'])
@login_required
def delete_equipment_route(equipment_id):
    conn = get_db()
    item = get_equipment(conn, equipment_id)
    if item is None:
        abort(404)
    try:
        delete_equipment(conn, equipment_id)
        flash('Equipment deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete: referenced by other records.', 'error')
    return redirect(url_for('equipment.list_equipment'))
