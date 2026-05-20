from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, g
)
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (
    get_all_venues, get_room, get_venue, get_availability_windows,
    check_room_available, create_booking, get_bookings_by_musician,
    get_booking, get_booking_history, get_settlement_by_booking,
    get_ticket_tiers
)

booking_create_bp = Blueprint('booking_create', __name__)


@booking_create_bp.route('/browse')
@login_required
@role_required('musician')
def browse():
    """List all venues for musicians to browse and pick rooms."""
    conn = get_db()
    venues = get_all_venues(conn)
    return render_template('booking_create/browse.html', venues=venues)


@booking_create_bp.route('/room/<int:room_id>/check')
@login_required
@role_required('musician')
def room_availability(room_id):
    """Show a room's availability windows so the musician can pick a slot."""
    conn = get_db()
    room = get_room(conn, room_id)
    if room is None:
        abort(404)
    venue = get_venue(conn, room['venue_id'])
    if venue is None:
        abort(404)
    windows = get_availability_windows(conn, room_id)
    return render_template(
        'booking_create/room_availability.html',
        room=room, venue=venue, windows=windows
    )


@booking_create_bp.route('/room/<int:room_id>/request', methods=['GET', 'POST'])
@login_required
@role_required('musician')
def request_booking(room_id):
    """GET: show booking request form. POST: create a new booking."""
    conn = get_db()
    room = get_room(conn, room_id)
    if room is None:
        abort(404)
    venue = get_venue(conn, room['venue_id'])
    if venue is None:
        abort(404)

    if request.method == 'POST':
        event_name = request.form.get('event_name', '').strip()
        event_date = request.form.get('event_date', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()
        deal_type = request.form.get('deal_type', 'door_split').strip()
        guarantee_dollars = request.form.get('guarantee_dollars', '0').strip()
        door_split_pct = request.form.get('door_split_pct', '70').strip()
        promoter_fee_pct = request.form.get('promoter_fee_pct', '0').strip()
        tax_pct = request.form.get('tax_pct', '0').strip()
        notes = request.form.get('notes', '').strip()

        # Validate required fields
        if not event_name:
            flash('Event name is required.', 'error')
            return render_template(
                'booking_create/request_form.html', room=room, venue=venue
            )
        if not event_date:
            flash('Event date is required.', 'error')
            return render_template(
                'booking_create/request_form.html', room=room, venue=venue
            )
        if not start_time:
            flash('Start time is required.', 'error')
            return render_template(
                'booking_create/request_form.html', room=room, venue=venue
            )
        if not end_time:
            flash('End time is required.', 'error')
            return render_template(
                'booking_create/request_form.html', room=room, venue=venue
            )
        if deal_type not in ('guarantee', 'door_split', 'hybrid'):
            flash('Invalid deal type.', 'error')
            return render_template(
                'booking_create/request_form.html', room=room, venue=venue
            )

        # Convert money: dollars -> cents (with validation)
        try:
            guarantee_cents = int(round(float(guarantee_dollars) * 100))
            door_split_pct_int = int(door_split_pct)
            promoter_fee_pct_int = int(promoter_fee_pct)
            tax_pct_int = int(tax_pct)
        except (ValueError, TypeError):
            flash('Invalid numeric value.', 'error')
            return render_template(
                'booking_create/request_form.html', room=room, venue=venue
            )
        if not (0 <= door_split_pct_int <= 100 and 0 <= promoter_fee_pct_int <= 100 and 0 <= tax_pct_int <= 100):
            flash('Percentages must be between 0 and 100.', 'error')
            return render_template(
                'booking_create/request_form.html', room=room, venue=venue
            )

        # Transaction: BEGIN IMMEDIATE -> check availability -> create booking -> commit
        # FC29: do NOT commit inside check_room_available or create_booking
        conn.execute('BEGIN IMMEDIATE')
        if not check_room_available(conn, room_id, event_date, start_time, end_time):
            conn.rollback()
            flash('Time slot conflict.', 'error')
            return redirect(url_for('booking_create.room_availability', room_id=room_id))

        booking_id = create_booking(
            conn, room_id, g.user['id'], event_name, event_date,
            start_time, end_time, deal_type, guarantee_cents,
            door_split_pct_int, promoter_fee_pct_int, tax_pct_int, notes
        )
        conn.commit()

        flash('Booking request submitted successfully.', 'success')
        return redirect(url_for('booking_create.detail', id=booking_id))

    return render_template(
        'booking_create/request_form.html', room=room, venue=venue
    )


@booking_create_bp.route('/mine')
@login_required
@role_required('musician')
def my_bookings():
    """List all bookings for the logged-in musician."""
    conn = get_db()
    bookings = get_bookings_by_musician(conn, g.user['id'])
    return render_template('booking_create/my_bookings.html', bookings=bookings)


@booking_create_bp.route('/<int:id>')
@login_required
@role_required('musician')
def detail(id):
    """Show full booking detail with history, settlement, and ticket tiers."""
    conn = get_db()
    booking = get_booking(conn, id)
    if booking is None:
        abort(404)
    if booking['musician_user_id'] != g.user['id']:
        abort(403)
    history = get_booking_history(conn, id)
    settlement = get_settlement_by_booking(conn, id)
    tiers = get_ticket_tiers(conn, id)
    return render_template(
        'booking_create/detail.html',
        booking=booking, history=history, settlement=settlement, tiers=tiers
    )
