"""
Booking state machine. Manages all state transitions and guard conditions.
Dispatches notifications on each transition.

TRANSITIONS dict defines allowed state changes.
advance_booking_state() is the ONLY function that writes to bookings.state
and booking_history. It does NOT commit -- the caller commits.
"""
from app.notifications import create_notification

TRANSITIONS = {
    'requested':  ['confirmed', 'rejected'],
    'confirmed':  ['advanced', 'performed', 'cancelled'],
    'advanced':   ['performed', 'cancelled'],
    'performed':  ['settled'],
    'settled':    ['paid'],
    'paid':       [],
    'rejected':   [],
    'cancelled':  [],
}

def _guard_confirm(conn, booking, actor_user_id):
    """Only the venue manager who owns the venue can confirm."""
    venue_manager_id = booking['venue_manager_id']
    return actor_user_id == venue_manager_id

def _guard_reject(conn, booking, actor_user_id):
    """Only venue manager can reject."""
    return actor_user_id == booking['venue_manager_id']

def _guard_advance(conn, booking, actor_user_id):
    """Only venue manager can record advance payment."""
    return actor_user_id == booking['venue_manager_id']

def _guard_cancel(conn, booking, actor_user_id):
    """Venue manager or the requesting musician can cancel."""
    return actor_user_id in (booking['venue_manager_id'], booking['musician_user_id'])

def _guard_perform(conn, booking, actor_user_id):
    """Only venue manager marks as performed."""
    return actor_user_id == booking['venue_manager_id']

def _guard_settle(conn, booking, actor_user_id):
    """Only venue manager can create settlement (must have settlement row)."""
    row = conn.execute('SELECT id FROM settlements WHERE booking_id = ?',
                       (booking['id'],)).fetchone()
    return row is not None and actor_user_id == booking['venue_manager_id']

def _guard_pay(conn, booking, actor_user_id):
    """Only venue manager marks as paid."""
    return actor_user_id == booking['venue_manager_id']

GUARD_FUNCTIONS = {
    ('requested', 'confirmed'): _guard_confirm,
    ('requested', 'rejected'): _guard_reject,
    ('confirmed', 'advanced'): _guard_advance,
    ('confirmed', 'performed'): _guard_perform,
    ('confirmed', 'cancelled'): _guard_cancel,
    ('advanced', 'performed'): _guard_perform,
    ('advanced', 'cancelled'): _guard_cancel,
    ('performed', 'settled'): _guard_settle,
    ('settled', 'paid'): _guard_pay,
}

# Notification messages per transition
NOTIFICATION_MAP = {
    'confirmed': {
        'musician': 'Your booking "{event_name}" has been confirmed!',
    },
    'rejected': {
        'musician': 'Your booking request "{event_name}" was declined.',
    },
    'advanced': {
        'musician': 'Advance payment recorded for "{event_name}".',
    },
    'cancelled': {
        'musician': 'Booking "{event_name}" has been cancelled.',
        'venue_manager': 'Booking "{event_name}" has been cancelled.',
    },
    'performed': {
        'musician': 'Show "{event_name}" marked as performed. Settlement pending.',
        'venue_manager': 'Show "{event_name}" marked as performed.',
    },
    'settled': {
        'musician': 'Settlement sheet ready for "{event_name}".',
        'venue_manager': 'Settlement created for "{event_name}".',
    },
    'paid': {
        'musician': 'Payment confirmed for "{event_name}"!',
    },
}

def _dispatch_notifications(conn, booking, new_state):
    """Create notifications for affected parties after a state transition."""
    templates = NOTIFICATION_MAP.get(new_state, {})
    event_name = booking['event_name']
    booking_id = booking['id']
    link = f'/bookings/{booking_id}'

    if 'musician' in templates:
        create_notification(
            conn, booking['musician_user_id'],
            templates['musician'].format(event_name=event_name),
            link
        )
    if 'venue_manager' in templates:
        create_notification(
            conn, booking['venue_manager_id'],
            templates['venue_manager'].format(event_name=event_name),
            f'/manage/bookings/{booking_id}'
        )

def advance_booking_state(conn, booking_id, new_state, actor_user_id, notes=''):
    """
    Advance a booking to new_state. Creates audit trail + notifications.
    Does NOT commit -- caller commits.

    Returns: bool (True if transition succeeded, False if denied)

    Usage (in route handler):
        conn = get_db()
        conn.execute('BEGIN IMMEDIATE')
        success = advance_booking_state(conn, booking_id, 'confirmed', g.user['id'])
        if not success:
            conn.rollback()
            flash('Cannot transition booking to this state.', 'error')
            return redirect(url_for('booking_manage.detail', booking_id=booking_id))
        conn.commit()
        flash('Booking confirmed.', 'success')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))
    """
    booking = conn.execute(
        '''SELECT b.*, r.venue_id, v.user_id AS venue_manager_id
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE b.id = ?''',
        (booking_id,)
    ).fetchone()

    if booking is None:
        return False

    current_state = booking['state']
    if new_state not in TRANSITIONS.get(current_state, []):
        return False

    guard = GUARD_FUNCTIONS.get((current_state, new_state))
    if guard and not guard(conn, booking, actor_user_id):
        return False

    conn.execute(
        'UPDATE bookings SET state = ?, updated_at = datetime("now") WHERE id = ?',
        (new_state, booking_id)
    )

    conn.execute(
        '''INSERT INTO booking_history (booking_id, from_state, to_state,
           actor_user_id, notes, created_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))''',
        (booking_id, current_state, new_state, actor_user_id, notes)
    )

    _dispatch_notifications(conn, booking, new_state)
    return True
