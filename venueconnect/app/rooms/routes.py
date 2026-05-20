from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (create_room, get_room, get_rooms_by_venue,
                         get_venue, update_room, delete_room)

rooms_bp = Blueprint('rooms', __name__)


@rooms_bp.route('/venue/<int:venue_id>')
@login_required
@role_required('venue_manager')
def list(venue_id):
    conn = get_db()
    venue = get_venue(conn, venue_id)
    if venue is None:
        abort(404)
    if venue['user_id'] != g.user['id']:
        abort(403)
    rooms = get_rooms_by_venue(conn, venue_id)
    return render_template('rooms/list.html', venue=venue, rooms=rooms)


@rooms_bp.route('/<int:id>')
@login_required
@role_required('venue_manager')
def detail(id):
    conn = get_db()
    room = get_room(conn, id)
    if room is None:
        abort(404)
    venue = get_venue(conn, room['venue_id'])
    if venue is None:
        abort(404)
    if venue['user_id'] != g.user['id']:
        abort(403)
    return render_template('rooms/detail.html', room=room, venue=venue)


@rooms_bp.route('/venue/<int:venue_id>/new', methods=['GET', 'POST'])
@login_required
@role_required('venue_manager')
def create(venue_id):
    conn = get_db()
    venue = get_venue(conn, venue_id)
    if venue is None:
        abort(404)
    if venue['user_id'] != g.user['id']:
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        capacity = request.form.get('capacity', '').strip()
        description = request.form.get('description', '').strip()
        has_pa = 1 if 'has_pa' in request.form else 0
        has_lighting = 1 if 'has_lighting' in request.form else 0

        if not name:
            flash('Room name is required.', 'error')
            return render_template('rooms/form.html', room=None, venue=venue)
        if not capacity:
            flash('Capacity is required.', 'error')
            return render_template('rooms/form.html', room=None, venue=venue)

        try:
            capacity_int = int(capacity)
        except ValueError:
            flash('Capacity must be a number.', 'error')
            return render_template('rooms/form.html', room=None, venue=venue)

        room_id = create_room(conn, venue_id, name, capacity_int, description,
                              has_pa, has_lighting)
        conn.commit()
        flash('Room created successfully.', 'success')
        return redirect(url_for('rooms.detail', id=room_id))

    return render_template('rooms/form.html', room=None, venue=venue)


@rooms_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('venue_manager')
def edit(id):
    conn = get_db()
    room = get_room(conn, id)
    if room is None:
        abort(404)
    venue = get_venue(conn, room['venue_id'])
    if venue is None:
        abort(404)
    if venue['user_id'] != g.user['id']:
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        capacity = request.form.get('capacity', '').strip()
        description = request.form.get('description', '').strip()
        has_pa = 1 if 'has_pa' in request.form else 0
        has_lighting = 1 if 'has_lighting' in request.form else 0

        if not name:
            flash('Room name is required.', 'error')
            return render_template('rooms/form.html', room=room, venue=venue)
        if not capacity:
            flash('Capacity is required.', 'error')
            return render_template('rooms/form.html', room=room, venue=venue)

        try:
            capacity_int = int(capacity)
        except ValueError:
            flash('Capacity must be a number.', 'error')
            return render_template('rooms/form.html', room=room, venue=venue)

        update_room(conn, id, name, capacity_int, description,
                    has_pa, has_lighting)
        conn.commit()
        flash('Room updated successfully.', 'success')
        return redirect(url_for('rooms.detail', id=id))

    return render_template('rooms/form.html', room=room, venue=venue)


@rooms_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@role_required('venue_manager')
def delete(id):
    conn = get_db()
    room = get_room(conn, id)
    if room is None:
        abort(404)
    venue = get_venue(conn, room['venue_id'])
    if venue is None:
        abort(404)
    if venue['user_id'] != g.user['id']:
        abort(403)
    venue_id = venue['id']
    delete_room(conn, id)
    conn.commit()
    flash('Room deleted successfully.', 'success')
    return redirect(url_for('rooms.list', venue_id=venue_id))
