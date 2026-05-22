import math
import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.db import get_db
from app.auth import login_required
from app.models.batch_models import (
    get_all_batches, get_batch, create_batch, start_brewing,
    advance_batch_status, assign_to_tap, update_batch, delete_batch,
    VALID_TRANSITIONS,
)
from app.models.recipe_models import get_all_recipes
from app.models.tank_models import get_available_tanks
from app.models.tap_models import get_available_taps

bp = Blueprint('batches', __name__)


@bp.route('/')
@login_required
def list():
    conn = get_db()
    batches = get_all_batches(conn)
    return render_template('batches/list.html', batches=batches)


@bp.route('/new')
@login_required
def new():
    conn = get_db()
    recipes = get_all_recipes(conn)
    return render_template('batches/form.html', batch=None, recipes=recipes)


@bp.route('/', methods=['POST'])
@login_required
def create():
    conn = get_db()

    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        flash('Batch name is required', 'error')
        return redirect(url_for('batches.new'))

    try:
        recipe_id = int(request.form.get('recipe_id', ''))
    except (ValueError, TypeError):
        flash('Invalid recipe', 'error')
        return redirect(url_for('batches.new'))

    try:
        volume_gallons = float(request.form.get('volume_gallons', ''))
        if not math.isfinite(volume_gallons) or volume_gallons <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid volume', 'error')
        return redirect(url_for('batches.new'))

    notes = request.form.get('notes', '').strip()

    try:
        batch_id = create_batch(conn, recipe_id, name, volume_gallons, notes)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Invalid recipe', 'error')
        return redirect(url_for('batches.new'))

    flash('Batch created successfully', 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))


@bp.route('/<int:batch_id>')
@login_required
def detail(batch_id):
    conn = get_db()
    batch = get_batch(conn, batch_id)
    if batch is None:
        abort(404)
    available_tanks = get_available_tanks(conn)
    available_taps = get_available_taps(conn)
    return render_template('batches/detail.html',
                           batch=batch,
                           available_tanks=available_tanks,
                           available_taps=available_taps,
                           valid_transitions=VALID_TRANSITIONS)


@bp.route('/<int:batch_id>/edit')
@login_required
def edit(batch_id):
    conn = get_db()
    batch = get_batch(conn, batch_id)
    if batch is None:
        abort(404)
    recipes = get_all_recipes(conn)
    return render_template('batches/form.html', batch=batch, recipes=recipes)


@bp.route('/<int:batch_id>/edit', methods=['POST'])
@login_required
def update(batch_id):
    conn = get_db()
    batch = get_batch(conn, batch_id)
    if batch is None:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 200:
        flash('Batch name is required', 'error')
        return redirect(url_for('batches.edit', batch_id=batch_id))

    notes = request.form.get('notes', '').strip()

    update_batch(conn, batch_id, name, notes)
    conn.commit()

    flash('Batch updated successfully', 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))


@bp.route('/<int:batch_id>/delete', methods=['POST'])
@login_required
def delete(batch_id):
    conn = get_db()
    batch = get_batch(conn, batch_id)
    if batch is None:
        abort(404)

    try:
        delete_batch(conn, batch_id)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Cannot delete: batch has sales records', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    flash('Batch deleted successfully', 'success')
    return redirect(url_for('batches.list'))


@bp.route('/<int:batch_id>/start-brewing', methods=['POST'], endpoint='start_brewing')
@login_required
def start_brewing_route(batch_id):
    conn = get_db()
    batch = get_batch(conn, batch_id)
    if batch is None:
        abort(404)

    try:
        tank_id = int(request.form.get('tank_id', ''))
    except (ValueError, TypeError):
        flash('Invalid tank', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Route-level UX gate (FC43: model-level checks are authoritative)
    if batch['status'] != 'planned':
        flash('Batch must be in planned status to start brewing', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Model handles BEGIN IMMEDIATE -- do NOT call conn.commit() after this
    error = start_brewing(conn, batch_id, tank_id)
    if error:
        flash(error, 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    flash('Brewing started successfully', 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))


@bp.route('/<int:batch_id>/advance', methods=['POST'])
@login_required
def advance(batch_id):
    conn = get_db()
    batch = get_batch(conn, batch_id)
    if batch is None:
        abort(404)

    new_status = request.form.get('new_status', '').strip()

    # Route-level UX gate (FC43: model-level checks are authoritative)
    current = batch['status']
    if new_status not in VALID_TRANSITIONS.get(current, []):
        flash('Invalid status transition', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Model handles BEGIN IMMEDIATE -- do NOT call conn.commit() after this
    error = advance_batch_status(conn, batch_id, new_status)
    if error:
        flash(error, 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    flash(f'Batch advanced to {new_status}', 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))


@bp.route('/<int:batch_id>/assign-tap', methods=['POST'])
@login_required
def assign_tap(batch_id):
    conn = get_db()
    batch = get_batch(conn, batch_id)
    if batch is None:
        abort(404)

    try:
        tap_id = int(request.form.get('tap_id', ''))
    except (ValueError, TypeError):
        flash('Invalid tap', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Route-level UX gate (FC43: model-level checks are authoritative)
    if batch['status'] != 'ready':
        flash('Batch must be in ready status to assign to a tap', 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    # Model handles BEGIN IMMEDIATE -- do NOT call conn.commit() after this
    error = assign_to_tap(conn, batch_id, tap_id)
    if error:
        flash(error, 'error')
        return redirect(url_for('batches.detail', batch_id=batch_id))

    flash('Batch assigned to tap successfully', 'success')
    return redirect(url_for('batches.detail', batch_id=batch_id))
