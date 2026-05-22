import math

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.auth import login_required
from app.db import get_db
from app.models import (
    create_membership_type,
    get_membership_type,
    get_all_membership_types,
    update_membership_type,
    delete_membership_type,
)

bp = Blueprint('membership_types', __name__)


def _parse_price(form_field='price'):
    """Parse a dollar amount from form data into cents.

    Returns (price_cents, error_message).  On success error_message is None.
    """
    try:
        raw = float(request.form.get(form_field, '0'))
        if math.isnan(raw) or math.isinf(raw):
            raise ValueError('Invalid price')
        price_cents = round(raw * 100)
        if price_cents < 0:
            return None, 'Valid price is required.'
        if price_cents > 99999999:  # Cap at $999,999.99
            return None, 'Price too large.'
        return price_cents, None
    except (ValueError, TypeError):
        return None, 'Valid price is required.'


# ---------- LIST ----------

@bp.route('/')
@login_required
def list_types():
    conn = get_db()
    types = get_all_membership_types(conn)
    return render_template('membership_types/list.html', types=types)


# ---------- NEW (form) ----------

@bp.route('/new')
@login_required
def new_type():
    return render_template('membership_types/form.html', mtype=None)


# ---------- CREATE ----------

@bp.route('/', methods=['POST'])
@login_required
def create_type():
    conn = get_db()

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Name is required (max 100 characters).', 'error')
        return redirect(url_for('membership_types.new_type'))

    # Duration
    try:
        duration_months = int(request.form.get('duration_months', '0'))
        if duration_months < 1:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Duration must be at least 1 month.', 'error')
        return redirect(url_for('membership_types.new_type'))

    # Price (dollars -> cents)
    price_cents, price_err = _parse_price('price')
    if price_err:
        flash(price_err, 'error')
        return redirect(url_for('membership_types.new_type'))

    description = request.form.get('description', '').strip()

    try:
        create_membership_type(conn, name, duration_months, price_cents, description)
    except Exception:
        flash('Could not create membership type (name may already exist).', 'error')
        return redirect(url_for('membership_types.new_type'))

    flash('Membership type created successfully.', 'success')
    return redirect(url_for('membership_types.list_types'))


# ---------- EDIT (form) ----------

@bp.route('/<int:type_id>/edit')
@login_required
def edit_type(type_id):
    conn = get_db()
    mtype = get_membership_type(conn, type_id)
    if mtype is None:
        abort(404)
    return render_template('membership_types/form.html', mtype=mtype)


# ---------- UPDATE ----------

@bp.route('/<int:type_id>/edit', methods=['POST'])
@login_required
def update_type(type_id):
    conn = get_db()
    mtype = get_membership_type(conn, type_id)
    if mtype is None:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Name is required (max 100 characters).', 'error')
        return redirect(url_for('membership_types.edit_type', type_id=type_id))

    # Duration
    try:
        duration_months = int(request.form.get('duration_months', '0'))
        if duration_months < 1:
            raise ValueError()
    except (ValueError, TypeError):
        flash('Duration must be at least 1 month.', 'error')
        return redirect(url_for('membership_types.edit_type', type_id=type_id))

    # Price (dollars -> cents)
    price_cents, price_err = _parse_price('price')
    if price_err:
        flash(price_err, 'error')
        return redirect(url_for('membership_types.edit_type', type_id=type_id))

    description = request.form.get('description', '').strip()

    # is_active checkbox (only on edit form)
    is_active_raw = request.form.get('is_active', '0')
    if is_active_raw not in ('0', '1'):
        flash('Invalid active status.', 'error')
        return redirect(url_for('membership_types.edit_type', type_id=type_id))
    is_active = int(is_active_raw)

    try:
        update_membership_type(conn, type_id, name, duration_months,
                               price_cents, description, is_active)
    except Exception:
        flash('Could not update membership type (name may already exist).', 'error')
        return redirect(url_for('membership_types.edit_type', type_id=type_id))

    flash('Membership type updated successfully.', 'success')
    return redirect(url_for('membership_types.list_types'))


# ---------- DELETE ----------

@bp.route('/<int:type_id>/delete', methods=['POST'])
@login_required
def delete_type(type_id):
    conn = get_db()
    mtype = get_membership_type(conn, type_id)
    if mtype is None:
        abort(404)

    # FK is SET NULL -- no IntegrityError expected
    delete_membership_type(conn, type_id)

    flash('Membership type deleted successfully.', 'success')
    return redirect(url_for('membership_types.list_types'))
