import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (get_availability_windows, create_availability_window,
                         delete_availability_window, get_room, get_venue)

availability_bp = Blueprint('availability', __name__)


@availability_bp.route('/room/<int:room_id>')
@login_required
@role_required('venue_manager')
def calendar(room_id):
    conn = get_db()
    room = get_room(conn, room_id)
    if room is None:
        abort(404)

    venue = get_venue(conn, room['venue_id'])
    if venue is None:
        abort(404)

    # Ownership check: venue must belong to current user
    if venue['user_id'] != g.user['id']:
        abort(403)

    windows = get_availability_windows(conn, room_id)

    # Fetch upcoming bookings for this room (read-only, no ownership conflict)
    bookings = conn.execute(
        '''SELECT b.*, u.display_name AS musician_name
           FROM bookings b
           JOIN users u ON b.musician_user_id = u.id
           WHERE b.room_id = ?
           AND b.state NOT IN ('rejected', 'cancelled')
           ORDER BY b.event_date ASC, b.start_time ASC''',
        (room_id,)
    ).fetchall()

    return render_template('availability/calendar.html',
                           room=room, venue=venue, windows=windows, bookings=bookings)


@availability_bp.route('/room/<int:room_id>/add', methods=['GET', 'POST'])
@login_required
@role_required('venue_manager')
def add(room_id):
    conn = get_db()
    room = get_room(conn, room_id)
    if room is None:
        abort(404)

    venue = get_venue(conn, room['venue_id'])
    if venue is None:
        abort(404)

    # Ownership check: venue must belong to current user
    if venue['user_id'] != g.user['id']:
        abort(403)

    if request.method == 'POST':
        day_of_week = request.form.get('day_of_week', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()

        # Validate required fields
        if not day_of_week or not start_time or not end_time:
            flash('All fields are required.', 'error')
            return render_template('availability/form.html', room=room)

        # Validate day_of_week is 0-6
        try:
            day_of_week = int(day_of_week)
        except ValueError:
            flash('Invalid day of week.', 'error')
            return render_template('availability/form.html', room=room)

        if day_of_week < 0 or day_of_week > 6:
            flash('Day of week must be between 0 and 6.', 'error')
            return render_template('availability/form.html', room=room)

        # Validate time format (HH:MM)
        time_pattern = re.compile(r'^\d{2}:\d{2}$')
        if not time_pattern.match(start_time) or not time_pattern.match(end_time):
            flash('Times must be in HH:MM format.', 'error')
            return render_template('availability/form.html', room=room)

        create_availability_window(conn, room_id, day_of_week, start_time, end_time)
        conn.commit()

        flash('Availability window added successfully.', 'success')
        return redirect(url_for('availability.calendar', room_id=room_id))

    return render_template('availability/form.html', room=room)


@availability_bp.route('/<int:window_id>/delete', methods=['POST'])
@login_required
@role_required('venue_manager')
def delete(window_id):
    conn = get_db()

    # Look up the window to find the room and venue for ownership check
    window = conn.execute(
        'SELECT * FROM availability_windows WHERE id = ?', (window_id,)
    ).fetchone()
    if window is None:
        abort(404)

    room = get_room(conn, window['room_id'])
    if room is None:
        abort(404)

    venue = get_venue(conn, room['venue_id'])
    if venue is None:
        abort(404)

    # Ownership check: venue must belong to current user
    if venue['user_id'] != g.user['id']:
        abort(403)

    delete_availability_window(conn, window_id)
    conn.commit()

    flash('Availability window deleted successfully.', 'success')
    return redirect(url_for('availability.calendar', room_id=window['room_id']))
