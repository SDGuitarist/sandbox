from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, g
)
from app.db import get_db
from app.decorators import login_required, role_required
from app.booking_lifecycle import advance_booking_state
from app.models import (
    get_booking, get_pending_bookings_for_venue, get_bookings_by_venue,
    get_booking_history, get_venues_by_manager, get_settlement_by_booking,
    get_ticket_tiers
)

booking_manage_bp = Blueprint('booking_manage', __name__)


@booking_manage_bp.route('/bookings')
@login_required
@role_required('venue_manager')
def pending():
    """Show pending (requested) bookings for the manager's first venue."""
    conn = get_db()
    venues = get_venues_by_manager(conn, g.user['id'])
    if not venues:
        flash('You have no venues yet.', 'error')
        return redirect(url_for('venues.list'))
    venue = venues[0]
    bookings = get_pending_bookings_for_venue(conn, venue['id'])
    return render_template(
        'booking_manage/pending.html', bookings=bookings, venue=venue
    )


@booking_manage_bp.route('/bookings/all')
@login_required
@role_required('venue_manager')
def all_bookings():
    """Show all bookings (any state) for the manager's first venue."""
    conn = get_db()
    venues = get_venues_by_manager(conn, g.user['id'])
    if not venues:
        flash('You have no venues yet.', 'error')
        return redirect(url_for('venues.list'))
    venue = venues[0]
    bookings = get_bookings_by_venue(conn, venue['id'])
    return render_template(
        'booking_manage/all_bookings.html', bookings=bookings, venue=venue
    )


@booking_manage_bp.route('/bookings/<int:booking_id>')
@login_required
@role_required('venue_manager')
def detail(booking_id):
    """Show booking detail with history, settlement, and ticket tiers."""
    conn = get_db()
    booking = get_booking(conn, booking_id)
    if booking is None:
        abort(404)
    # Only the venue manager who owns this venue can view
    if booking['venue_manager_id'] != g.user['id']:
        abort(403)
    history = get_booking_history(conn, booking_id)
    settlement = get_settlement_by_booking(conn, booking_id)
    tiers = get_ticket_tiers(conn, booking_id)
    return render_template(
        'booking_manage/detail.html',
        booking=booking, history=history, settlement=settlement, tiers=tiers
    )


@booking_manage_bp.route('/bookings/<int:booking_id>/confirm', methods=['POST'])
@login_required
@role_required('venue_manager')
def confirm(booking_id):
    """Confirm a requested booking."""
    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    success = advance_booking_state(
        conn, booking_id, 'confirmed', g.user['id']
    )
    if not success:
        conn.rollback()
        flash('Cannot transition booking to this state.', 'error')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))
    conn.commit()
    flash('Booking confirmed.', 'success')
    return redirect(url_for('booking_manage.detail', booking_id=booking_id))


@booking_manage_bp.route('/bookings/<int:booking_id>/reject', methods=['POST'])
@login_required
@role_required('venue_manager')
def reject(booking_id):
    """Reject a requested booking with notes."""
    rejection_notes = request.form.get('rejection_notes', '')
    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    success = advance_booking_state(
        conn, booking_id, 'rejected', g.user['id'], notes=rejection_notes
    )
    if not success:
        conn.rollback()
        flash('Cannot transition booking to this state.', 'error')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))
    conn.commit()
    flash('Booking rejected.', 'success')
    return redirect(url_for('booking_manage.detail', booking_id=booking_id))


@booking_manage_bp.route('/bookings/<int:booking_id>/advance', methods=['POST'])
@login_required
@role_required('venue_manager')
def record_advance(booking_id):
    """Record advance payment and transition to advanced state."""
    advance_dollars = request.form.get('advance_dollars', '0')
    try:
        advance_cents = int(float(advance_dollars) * 100)
    except (ValueError, TypeError):
        flash('Invalid advance amount.', 'error')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))

    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    # Record the advance amount on the booking
    conn.execute(
        'UPDATE bookings SET advance_cents = ?, updated_at = datetime("now") '
        'WHERE id = ?',
        (advance_cents, booking_id)
    )
    success = advance_booking_state(
        conn, booking_id, 'advanced', g.user['id']
    )
    if not success:
        conn.rollback()
        flash('Cannot transition booking to this state.', 'error')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))
    conn.commit()
    flash('Advance payment recorded.', 'success')
    return redirect(url_for('booking_manage.detail', booking_id=booking_id))


@booking_manage_bp.route('/bookings/<int:booking_id>/perform', methods=['POST'])
@login_required
@role_required('venue_manager')
def mark_performed(booking_id):
    """Mark a booking as performed after the show."""
    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    success = advance_booking_state(
        conn, booking_id, 'performed', g.user['id']
    )
    if not success:
        conn.rollback()
        flash('Cannot transition booking to this state.', 'error')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))
    conn.commit()
    flash('Show marked as performed.', 'success')
    return redirect(url_for('booking_manage.detail', booking_id=booking_id))


@booking_manage_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
@role_required('venue_manager')
def cancel(booking_id):
    """Cancel a confirmed or advanced booking with notes."""
    cancel_notes = request.form.get('cancel_notes', '')
    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    success = advance_booking_state(
        conn, booking_id, 'cancelled', g.user['id'], notes=cancel_notes
    )
    if not success:
        conn.rollback()
        flash('Cannot transition booking to this state.', 'error')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))
    conn.commit()
    flash('Booking cancelled.', 'success')
    return redirect(url_for('booking_manage.detail', booking_id=booking_id))


@booking_manage_bp.route('/bookings/<int:booking_id>/mark-paid', methods=['POST'])
@login_required
@role_required('venue_manager')
def mark_paid(booking_id):
    """Mark a settled booking as paid."""
    conn = get_db()
    conn.execute('BEGIN IMMEDIATE')
    success = advance_booking_state(
        conn, booking_id, 'paid', g.user['id']
    )
    if not success:
        conn.rollback()
        flash('Cannot transition booking to this state.', 'error')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))
    conn.commit()
    flash('Booking marked as paid.', 'success')
    return redirect(url_for('booking_manage.detail', booking_id=booking_id))
