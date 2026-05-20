from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, g)
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (create_event, get_event, get_events_by_promoter,
                         update_event, get_all_venues, link_booking_to_event,
                         get_bookings_by_event)

events_bp = Blueprint('events', __name__)


@events_bp.route('/')
@login_required
@role_required('promoter')
def list():
    conn = get_db()
    events = get_events_by_promoter(conn, g.user['id'])
    return render_template('events/list.html', events=events)


@events_bp.route('/<int:id>')
@login_required
@role_required('promoter')
def detail(id):
    conn = get_db()
    event = get_event(conn, id)
    if event is None:
        abort(404)
    if event['promoter_user_id'] != g.user['id']:
        abort(403)
    bookings = get_bookings_by_event(conn, id)
    return render_template('events/detail.html', event=event, bookings=bookings)


@events_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('promoter')
def create():
    conn = get_db()
    venues = get_all_venues(conn)

    if request.method == 'POST':
        venue_id = request.form.get('venue_id', '').strip()
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()

        if not venue_id:
            flash('Venue is required.', 'error')
            return render_template('events/form.html', event=None, venues=venues)
        if not name:
            flash('Event name is required.', 'error')
            return render_template('events/form.html', event=None, venues=venues)
        if not event_date:
            flash('Event date is required.', 'error')
            return render_template('events/form.html', event=None, venues=venues)

        event_id = create_event(conn, g.user['id'], int(venue_id),
                                name, description, event_date)
        conn.commit()
        flash('Event created successfully.', 'success')
        return redirect(url_for('events.detail', id=event_id))

    return render_template('events/form.html', event=None, venues=venues)


@events_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('promoter')
def edit(id):
    conn = get_db()
    event = get_event(conn, id)
    if event is None:
        abort(404)
    if event['promoter_user_id'] != g.user['id']:
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        event_date = request.form.get('event_date', '').strip()

        if not name:
            flash('Event name is required.', 'error')
            venues = get_all_venues(conn)
            return render_template('events/form.html', event=event, venues=venues)
        if not event_date:
            flash('Event date is required.', 'error')
            venues = get_all_venues(conn)
            return render_template('events/form.html', event=event, venues=venues)

        update_event(conn, id, name, description, event_date)
        conn.commit()
        flash('Event updated successfully.', 'success')
        return redirect(url_for('events.detail', id=id))

    venues = get_all_venues(conn)
    return render_template('events/form.html', event=event, venues=venues)


@events_bp.route('/<int:id>/link-booking', methods=['POST'])
@login_required
@role_required('promoter')
def link_booking(id):
    conn = get_db()
    event = get_event(conn, id)
    if event is None:
        abort(404)
    if event['promoter_user_id'] != g.user['id']:
        abort(403)

    booking_id = request.form.get('booking_id', '').strip()
    if not booking_id:
        flash('Booking ID is required.', 'error')
        return redirect(url_for('events.detail', id=id))

    link_booking_to_event(conn, int(booking_id), id)
    conn.commit()
    flash('Booking linked successfully.', 'success')
    return redirect(url_for('events.detail', id=id))
