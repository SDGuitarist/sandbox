import math
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models.tank_models import (
    create_tank,
    delete_tank,
    get_all_tanks,
    get_tank,
    update_tank,
)

bp = Blueprint('tanks', __name__)

VALID_TANK_TYPES = ('fermenter', 'brite', 'conditioning')


@bp.route('/')
@login_required
def list():
    conn = get_db()
    tanks = get_all_tanks(conn)
    return render_template('tanks/list.html', tanks=tanks)


@bp.route('/new')
@login_required
def new():
    return render_template('tanks/form.html', tank=None, tank_types=VALID_TANK_TYPES)


@bp.route('/', methods=['POST'])
@login_required
def create():
    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Tank name is required', 'error')
        return redirect(url_for('tanks.new'))

    tank_type = request.form.get('tank_type', '')
    if tank_type not in VALID_TANK_TYPES:
        flash('Invalid tank type', 'error')
        return redirect(url_for('tanks.new'))

    try:
        capacity = float(request.form.get('capacity_gallons', ''))
        if not math.isfinite(capacity) or capacity <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid capacity', 'error')
        return redirect(url_for('tanks.new'))

    notes = request.form.get('notes', '').strip()

    conn = get_db()
    try:
        tank_id = create_tank(conn, name, capacity, tank_type, notes)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Name already exists', 'error')
        return redirect(url_for('tanks.new'))

    flash('Tank created successfully', 'success')
    return redirect(url_for('tanks.detail', tank_id=tank_id))


@bp.route('/<int:tank_id>')
@login_required
def detail(tank_id):
    conn = get_db()
    tank = get_tank(conn, tank_id)
    if tank is None:
        abort(404)
    return render_template('tanks/detail.html', tank=tank)


@bp.route('/<int:tank_id>/edit')
@login_required
def edit(tank_id):
    conn = get_db()
    tank = get_tank(conn, tank_id)
    if tank is None:
        abort(404)
    return render_template('tanks/form.html', tank=tank, tank_types=VALID_TANK_TYPES)


@bp.route('/<int:tank_id>/edit', methods=['POST'])
@login_required
def update(tank_id):
    conn = get_db()
    tank = get_tank(conn, tank_id)
    if tank is None:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Tank name is required', 'error')
        return redirect(url_for('tanks.edit', tank_id=tank_id))

    tank_type = request.form.get('tank_type', '')
    if tank_type not in VALID_TANK_TYPES:
        flash('Invalid tank type', 'error')
        return redirect(url_for('tanks.edit', tank_id=tank_id))

    try:
        capacity = float(request.form.get('capacity_gallons', ''))
        if not math.isfinite(capacity) or capacity <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid capacity', 'error')
        return redirect(url_for('tanks.edit', tank_id=tank_id))

    notes = request.form.get('notes', '').strip()

    try:
        update_tank(conn, tank_id, name, capacity, tank_type, notes)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Name already exists', 'error')
        return redirect(url_for('tanks.edit', tank_id=tank_id))

    flash('Tank updated successfully', 'success')
    return redirect(url_for('tanks.detail', tank_id=tank_id))


@bp.route('/<int:tank_id>/delete', methods=['POST'])
@login_required
def delete(tank_id):
    conn = get_db()
    tank = get_tank(conn, tank_id)
    if tank is None:
        abort(404)

    if tank['current_batch_id'] is not None:
        flash('Cannot delete: tank has an active batch', 'error')
        return redirect(url_for('tanks.detail', tank_id=tank_id))

    try:
        delete_tank(conn, tank_id)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Cannot delete: tank is referenced by other records', 'error')
        return redirect(url_for('tanks.detail', tank_id=tank_id))

    flash('Tank deleted successfully', 'success')
    return redirect(url_for('tanks.list'))
