import math
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models import (
    create_maintenance as model_create_maintenance,
    delete_maintenance as model_delete_maintenance,
    get_all_equipment,
    get_all_maintenance,
    get_maintenance,
    update_maintenance as model_update_maintenance,
)

bp = Blueprint('maintenance', __name__)


@bp.route('/')
@login_required
def list_maintenance():
    conn = get_db()
    records = get_all_maintenance(conn)
    return render_template('maintenance/list.html', records=records)


@bp.route('/new')
@login_required
def new_maintenance():
    conn = get_db()
    return render_template(
        'maintenance/form.html',
        record=None,
        equipment_list=get_all_equipment(conn),
    )


def _validate_maintenance_form(conn, redirect_url):
    """Validate maintenance form fields. Returns (data_dict, None) on success
    or (None, redirect_response) on validation failure."""

    # Validate equipment_id
    try:
        equipment_id = int(request.form.get('equipment_id', ''))
    except (ValueError, TypeError):
        flash('Equipment is required.', 'error')
        return None, redirect(redirect_url)

    # Verify equipment exists (FC4)
    equipment_list = get_all_equipment(conn)
    equipment_ids = {e['id'] for e in equipment_list}
    if equipment_id not in equipment_ids:
        flash('Equipment is required.', 'error')
        return None, redirect(redirect_url)

    # Validate description
    description = request.form.get('description', '').strip()
    if not description or len(description) > 500:
        flash('Description is required.', 'error')
        return None, redirect(redirect_url)

    # Validate cost (dollars -> cents, FC4 money parsing)
    try:
        raw = float(request.form.get('cost', '0'))
        if math.isnan(raw) or math.isinf(raw):
            raise ValueError('Invalid cost')
        cost_cents = round(raw * 100)
        if cost_cents < 0:
            flash('Valid cost is required.', 'error')
            return None, redirect(redirect_url)
        if cost_cents > 99999999:
            flash('Cost too large.', 'error')
            return None, redirect(redirect_url)
    except (ValueError, TypeError):
        flash('Valid cost is required.', 'error')
        return None, redirect(redirect_url)

    # Validate maintenance_date
    maintenance_date = request.form.get('maintenance_date', '').strip()
    if not maintenance_date:
        flash('Maintenance date is required.', 'error')
        return None, redirect(redirect_url)

    # Optional fields
    performed_by = request.form.get('performed_by', '').strip()
    next_due_date = request.form.get('next_due_date', '').strip() or None

    data = {
        'equipment_id': equipment_id,
        'description': description,
        'maintenance_date': maintenance_date,
        'cost_cents': cost_cents,
        'performed_by': performed_by,
        'next_due_date': next_due_date,
    }
    return data, None


@bp.route('/', methods=['POST'])
@login_required
def create_maintenance():
    conn = get_db()
    redirect_url = url_for('maintenance.new_maintenance')
    data, error_response = _validate_maintenance_form(conn, redirect_url)
    if error_response:
        return error_response

    model_create_maintenance(
        conn, data['equipment_id'], data['description'],
        data['maintenance_date'], data['cost_cents'],
        data['performed_by'], data['next_due_date'],
    )
    flash('Maintenance record created successfully.', 'success')
    return redirect(url_for('maintenance.list_maintenance'))


@bp.route('/<int:maintenance_id>/edit')
@login_required
def edit_maintenance(maintenance_id):
    conn = get_db()
    record = get_maintenance(conn, maintenance_id)
    if record is None:
        abort(404)
    return render_template(
        'maintenance/form.html',
        record=record,
        equipment_list=get_all_equipment(conn),
    )


@bp.route('/<int:maintenance_id>/edit', methods=['POST'])
@login_required
def update_maintenance(maintenance_id):
    conn = get_db()
    record = get_maintenance(conn, maintenance_id)
    if record is None:
        abort(404)

    redirect_url = url_for('maintenance.edit_maintenance', maintenance_id=maintenance_id)
    data, error_response = _validate_maintenance_form(conn, redirect_url)
    if error_response:
        return error_response

    model_update_maintenance(
        conn, maintenance_id, data['equipment_id'], data['description'],
        data['maintenance_date'], data['cost_cents'],
        data['performed_by'], data['next_due_date'],
    )
    flash('Maintenance record updated successfully.', 'success')
    return redirect(url_for('maintenance.list_maintenance'))


@bp.route('/<int:maintenance_id>/delete', methods=['POST'])
@login_required
def delete_maintenance(maintenance_id):
    conn = get_db()
    record = get_maintenance(conn, maintenance_id)
    if record is None:
        abort(404)
    try:
        model_delete_maintenance(conn, maintenance_id)
        flash('Maintenance record deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete: referenced by other records.', 'error')
    return redirect(url_for('maintenance.list_maintenance'))
