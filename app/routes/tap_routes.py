import sqlite3

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.db import get_db
from app.auth import login_required
from app.models.tap_models import get_all_taps, get_tap, create_tap, update_tap, delete_tap

bp = Blueprint('taps', __name__)


@bp.route('/')
@login_required
def list():
    conn = get_db()
    taps = get_all_taps(conn)
    return render_template('taps/list.html', taps=taps)


@bp.route('/new')
@login_required
def new():
    return render_template('taps/form.html', tap=None)


@bp.route('/', methods=['POST'])
@login_required
def create():
    conn = get_db()

    name = (request.form.get('name') or '').strip()
    if not name or len(name) > 100:
        flash('Tap name is required', 'error')
        return redirect(url_for('taps.new'))

    try:
        position = int(request.form.get('position', ''))
        if position <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid position', 'error')
        return redirect(url_for('taps.new'))

    try:
        tap_id = create_tap(conn, name, position)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Name or position already in use', 'error')
        return redirect(url_for('taps.new'))

    flash('Tap created successfully', 'success')
    return redirect(url_for('taps.detail', tap_id=tap_id))


@bp.route('/<int:tap_id>')
@login_required
def detail(tap_id):
    conn = get_db()
    tap = get_tap(conn, tap_id)
    if tap is None:
        abort(404)
    return render_template('taps/detail.html', tap=tap)


@bp.route('/<int:tap_id>/edit')
@login_required
def edit(tap_id):
    conn = get_db()
    tap = get_tap(conn, tap_id)
    if tap is None:
        abort(404)
    return render_template('taps/form.html', tap=tap)


@bp.route('/<int:tap_id>/edit', methods=['POST'])
@login_required
def update(tap_id):
    conn = get_db()
    tap = get_tap(conn, tap_id)
    if tap is None:
        abort(404)

    name = (request.form.get('name') or '').strip()
    if not name or len(name) > 100:
        flash('Tap name is required', 'error')
        return redirect(url_for('taps.edit', tap_id=tap_id))

    try:
        position = int(request.form.get('position', ''))
        if position <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid position', 'error')
        return redirect(url_for('taps.edit', tap_id=tap_id))

    try:
        update_tap(conn, tap_id, name, position)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Name or position already in use', 'error')
        return redirect(url_for('taps.edit', tap_id=tap_id))

    flash('Tap updated successfully', 'success')
    return redirect(url_for('taps.detail', tap_id=tap_id))


@bp.route('/<int:tap_id>/delete', methods=['POST'])
@login_required
def delete(tap_id):
    conn = get_db()
    tap = get_tap(conn, tap_id)
    if tap is None:
        abort(404)

    if tap['batch_id'] is not None:
        flash('Cannot delete: tap has an active batch assigned', 'error')
        return redirect(url_for('taps.detail', tap_id=tap_id))

    try:
        delete_tap(conn, tap_id)
        conn.commit()
    except sqlite3.IntegrityError:
        flash('Cannot delete: tap has sales records', 'error')
        return redirect(url_for('taps.detail', tap_id=tap_id))

    flash('Tap deleted successfully', 'success')
    return redirect(url_for('taps.list'))
