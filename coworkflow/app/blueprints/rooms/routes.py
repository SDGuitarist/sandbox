"""Rooms blueprint: CRUD for meeting rooms."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from app.db import get_db
from app.auth import login_required
from app.models.room import (
    create_room,
    get_room,
    get_all_rooms,
    update_room,
    delete_room,
)
import sqlite3
import math

bp = Blueprint('rooms', __name__)


@bp.route('/')
@login_required
def list_rooms():
    """GET /rooms/ -- list all meeting rooms."""
    conn = get_db()
    rooms = get_all_rooms(conn)
    return render_template('rooms/list.html', rooms=rooms)


@bp.route('/new')
@login_required
def new_room():
    """GET /rooms/new -- show create form."""
    return render_template('rooms/form.html', room=None)


@bp.route('/new', methods=['POST'])
@login_required
def create():
    """POST /rooms/new -- create a new meeting room."""
    conn = get_db()

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return redirect(url_for('rooms.new_room'))

    # Capacity: int, 1-999
    raw_capacity = request.form.get('capacity', '')
    try:
        capacity = int(raw_capacity)
        if capacity < 1 or capacity > 999:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid capacity.', 'error')
        return redirect(url_for('rooms.new_room'))

    # Hourly rate: float -> cents
    raw_rate = request.form.get('hourly_rate', '')
    try:
        rate_val = float(raw_rate)
        if not math.isfinite(rate_val) or rate_val < 0 or rate_val > 999999.99:
            raise ValueError
        hourly_rate_cents = round(rate_val * 100)
    except (ValueError, TypeError):
        flash('Invalid rate.', 'error')
        return redirect(url_for('rooms.new_room'))

    location = request.form.get('location', '').strip()

    try:
        create_room(conn, name, capacity, hourly_rate_cents, location)
    except sqlite3.IntegrityError:
        flash('A room with this name already exists.', 'error')
        return redirect(url_for('rooms.new_room'))

    flash('Room created successfully.', 'success')
    return redirect(url_for('rooms.list_rooms'))


@bp.route('/<int:room_id>')
@login_required
def detail(room_id):
    """GET /rooms/<room_id> -- show room detail."""
    conn = get_db()
    room = get_room(conn, room_id)
    if room is None:
        abort(404)
    return render_template('rooms/detail.html', room=room)


@bp.route('/<int:room_id>/edit')
@login_required
def edit_form(room_id):
    """GET /rooms/<room_id>/edit -- show edit form."""
    conn = get_db()
    room = get_room(conn, room_id)
    if room is None:
        abort(404)
    return render_template('rooms/form.html', room=room)


@bp.route('/<int:room_id>/edit', methods=['POST'])
@login_required
def update(room_id):
    """POST /rooms/<room_id>/edit -- update a meeting room."""
    conn = get_db()
    room = get_room(conn, room_id)
    if room is None:
        abort(404)

    name = request.form.get('name', '').strip()
    if not name or len(name) > 100:
        flash('Name is required.', 'error')
        return redirect(url_for('rooms.edit_form', room_id=room_id))

    # Capacity: int, 1-999
    raw_capacity = request.form.get('capacity', '')
    try:
        capacity = int(raw_capacity)
        if capacity < 1 or capacity > 999:
            raise ValueError
    except (ValueError, TypeError):
        flash('Invalid capacity.', 'error')
        return redirect(url_for('rooms.edit_form', room_id=room_id))

    # Hourly rate: float -> cents
    raw_rate = request.form.get('hourly_rate', '')
    try:
        rate_val = float(raw_rate)
        if not math.isfinite(rate_val) or rate_val < 0 or rate_val > 999999.99:
            raise ValueError
        hourly_rate_cents = round(rate_val * 100)
    except (ValueError, TypeError):
        flash('Invalid rate.', 'error')
        return redirect(url_for('rooms.edit_form', room_id=room_id))

    location = request.form.get('location', '').strip()
    is_active = 1 if request.form.get('is_active') else 0

    try:
        update_room(conn, room_id, name, capacity, hourly_rate_cents, location, is_active)
    except sqlite3.IntegrityError:
        flash('A room with this name already exists.', 'error')
        return redirect(url_for('rooms.edit_form', room_id=room_id))

    flash('Room updated successfully.', 'success')
    return redirect(url_for('rooms.detail', room_id=room_id))


@bp.route('/<int:room_id>/delete', methods=['POST'])
@login_required
def delete(room_id):
    """POST /rooms/<room_id>/delete -- delete a meeting room."""
    conn = get_db()
    room = get_room(conn, room_id)
    if room is None:
        abort(404)

    try:
        delete_room(conn, room_id)
    except sqlite3.IntegrityError:
        flash('Cannot delete: room has bookings.', 'error')
        return redirect(url_for('rooms.detail', room_id=room_id))

    flash('Room deleted successfully.', 'success')
    return redirect(url_for('rooms.list_rooms'))
