from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from app.db import get_db
from app.decorators import login_required, role_required  # noqa: F401
from app.models import (
    get_booking,
    get_ticket_tiers,
    create_ticket_tier,
    update_ticket_tier,
    delete_ticket_tier,
)

tickets_bp = Blueprint('tickets', __name__)


# ---------------------------------------------------------------------------
# Helper: verify current user owns booking (venue_manager or promoter)
# ---------------------------------------------------------------------------
def _check_booking_access(booking):
    """Abort 403 if user is neither the venue manager nor the booking musician.

    The spec says ticket tiers are managed by venue_manager or promoter.
    - venue_manager: owns the venue (booking['venue_manager_id'] == g.user['id'])
    - promoter: linked via event (booking['event_id'] links to event whose
      promoter_user_id == g.user['id']). For simplicity and because the spec
      says 'check booking ownership', we check if the user is the venue manager
      for the booking's venue.
    """
    role = g.user['role']
    if role == 'venue_manager' and booking['venue_manager_id'] == g.user['id']:
        return
    if role == 'promoter':
        # Promoter access: check if they own the event linked to this booking
        if booking['event_id']:
            conn = get_db()
            event = conn.execute(
                'SELECT promoter_user_id FROM events WHERE id = ?',
                (booking['event_id'],)
            ).fetchone()
            if event and event['promoter_user_id'] == g.user['id']:
                return
    abort(403)


# ---------------------------------------------------------------------------
# Helper: fetch a single ticket tier by ID
# ---------------------------------------------------------------------------
def _get_tier_or_404(conn, tier_id):
    """Return a single ticket tier row or abort 404."""
    tier = conn.execute(
        'SELECT * FROM ticket_tiers WHERE id = ?', (tier_id,)
    ).fetchone()
    if tier is None:
        abort(404)
    return tier


# ---------------------------------------------------------------------------
# GET /tickets/booking/<booking_id> -- Manage ticket tiers for a booking
# ---------------------------------------------------------------------------
@tickets_bp.route('/booking/<int:booking_id>')
@login_required
def manage(booking_id):
    conn = get_db()
    booking = get_booking(conn, booking_id)
    if booking is None:
        abort(404)
    _check_booking_access(booking)
    tiers = get_ticket_tiers(conn, booking_id)
    return render_template('tickets/manage.html', booking=booking, tiers=tiers)


# ---------------------------------------------------------------------------
# GET/POST /tickets/booking/<booking_id>/add -- Add a new ticket tier
# ---------------------------------------------------------------------------
@tickets_bp.route('/booking/<int:booking_id>/add', methods=['GET', 'POST'])
@login_required
def add(booking_id):
    conn = get_db()
    booking = get_booking(conn, booking_id)
    if booking is None:
        abort(404)
    _check_booking_access(booking)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price_dollars_str = request.form.get('price_dollars', '0')
        quantity_str = request.form.get('quantity', '0')

        # Validate name
        if not name:
            flash('Tier name is required.', 'error')
            return render_template('tickets/form.html', tier=None, booking=booking)

        # Parse money: dollars string -> integer cents
        try:
            price_cents = int(round(float(price_dollars_str) * 100))
        except (ValueError, TypeError):
            flash('Invalid price.', 'error')
            return render_template('tickets/form.html', tier=None, booking=booking)

        if price_cents < 0:
            flash('Price cannot be negative.', 'error')
            return render_template('tickets/form.html', tier=None, booking=booking)

        # Parse quantity
        try:
            quantity = int(quantity_str)
        except (ValueError, TypeError):
            flash('Invalid quantity.', 'error')
            return render_template('tickets/form.html', tier=None, booking=booking)

        if quantity < 0:
            flash('Quantity cannot be negative.', 'error')
            return render_template('tickets/form.html', tier=None, booking=booking)

        conn.execute('BEGIN IMMEDIATE')
        try:
            create_ticket_tier(conn, booking_id, name, price_cents, quantity)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        flash('Ticket tier created successfully.', 'success')
        return redirect(url_for('tickets.manage', booking_id=booking_id))

    # GET
    return render_template('tickets/form.html', tier=None, booking=booking)


# ---------------------------------------------------------------------------
# GET/POST /tickets/<tier_id>/edit -- Edit an existing ticket tier
# ---------------------------------------------------------------------------
@tickets_bp.route('/<int:tier_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(tier_id):
    conn = get_db()
    tier = _get_tier_or_404(conn, tier_id)
    booking = get_booking(conn, tier['booking_id'])
    if booking is None:
        abort(404)
    _check_booking_access(booking)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price_dollars_str = request.form.get('price_dollars', '0')
        quantity_str = request.form.get('quantity', '0')
        sold_count_str = request.form.get('sold_count', '0')

        # Validate name
        if not name:
            flash('Tier name is required.', 'error')
            return render_template('tickets/form.html', tier=tier, booking=booking)

        # Parse money: dollars string -> integer cents
        try:
            price_cents = int(round(float(price_dollars_str) * 100))
        except (ValueError, TypeError):
            flash('Invalid price.', 'error')
            return render_template('tickets/form.html', tier=tier, booking=booking)

        if price_cents < 0:
            flash('Price cannot be negative.', 'error')
            return render_template('tickets/form.html', tier=tier, booking=booking)

        # Parse quantity
        try:
            quantity = int(quantity_str)
        except (ValueError, TypeError):
            flash('Invalid quantity.', 'error')
            return render_template('tickets/form.html', tier=tier, booking=booking)

        if quantity < 0:
            flash('Quantity cannot be negative.', 'error')
            return render_template('tickets/form.html', tier=tier, booking=booking)

        # Parse sold_count
        try:
            sold_count = int(sold_count_str)
        except (ValueError, TypeError):
            flash('Invalid sold count.', 'error')
            return render_template('tickets/form.html', tier=tier, booking=booking)

        if sold_count < 0:
            flash('Sold count cannot be negative.', 'error')
            return render_template('tickets/form.html', tier=tier, booking=booking)

        conn.execute('BEGIN IMMEDIATE')
        try:
            update_ticket_tier(conn, tier_id, name, price_cents, quantity, sold_count)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        flash('Ticket tier updated successfully.', 'success')
        return redirect(url_for('tickets.manage', booking_id=tier['booking_id']))

    # GET
    return render_template('tickets/form.html', tier=tier, booking=booking)


# ---------------------------------------------------------------------------
# POST /tickets/<tier_id>/delete -- Delete a ticket tier
# ---------------------------------------------------------------------------
@tickets_bp.route('/<int:tier_id>/delete', methods=['POST'])
@login_required
def delete(tier_id):
    conn = get_db()
    tier = _get_tier_or_404(conn, tier_id)
    booking = get_booking(conn, tier['booking_id'])
    if booking is None:
        abort(404)
    _check_booking_access(booking)

    conn.execute('BEGIN IMMEDIATE')
    try:
        delete_ticket_tier(conn, tier_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    flash('Ticket tier deleted successfully.', 'success')
    return redirect(url_for('tickets.manage', booking_id=tier['booking_id']))
