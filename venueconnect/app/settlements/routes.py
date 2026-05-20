from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g, Response
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (get_booking, get_settlement, get_settlement_by_booking,
                         create_settlement, approve_settlement, get_settlements_list,
                         get_total_door_revenue_cents)
from app.settlement_engine import calculate_settlement
from app.settlement_pdf import generate_settlement_pdf
from app.booking_lifecycle import advance_booking_state

settlements_bp = Blueprint('settlements', __name__)


@settlements_bp.route('/')
@login_required
def list():
    conn = get_db()
    settlements = get_settlements_list(conn, g.user['id'], g.user['role'])
    return render_template('settlements/list.html', settlements=settlements)


@settlements_bp.route('/<int:id>')
@login_required
def detail(id):
    conn = get_db()
    settlement = get_settlement(conn, id)
    if settlement is None:
        abort(404)
    return render_template('settlements/detail.html', settlement=settlement)


@settlements_bp.route('/booking/<int:booking_id>/create', methods=['GET', 'POST'])
@login_required
@role_required('venue_manager')
def create(booking_id):
    conn = get_db()
    booking = get_booking(conn, booking_id)
    if booking is None:
        abort(404)

    # Check if settlement already exists for this booking
    existing = get_settlement_by_booking(conn, booking_id)
    if existing is not None:
        flash('Settlement already exists for this booking.', 'error')
        return redirect(url_for('settlements.detail', id=existing['id']))

    if request.method == 'POST':
        # Parse dollars to cents
        door_revenue_cents = int(round(float(request.form.get('door_revenue_dollars', '0')) * 100))
        expenses_cents = int(round(float(request.form.get('expenses_dollars', '0')) * 100))

        # Calculate settlement
        result = calculate_settlement(
            door_revenue_cents, expenses_cents,
            booking['deal_type'], booking['guarantee_cents'],
            booking['door_split_pct'], booking['promoter_fee_pct'],
            booking['tax_pct']
        )

        # Create settlement record
        settlement_id = create_settlement(
            conn, booking_id, door_revenue_cents, expenses_cents,
            result['musician_payout_cents'], result['venue_share_cents'],
            result['promoter_fee_cents'], result['tax_amount_cents'],
            g.user['id']
        )
        conn.commit()

        flash('Settlement created successfully.', 'success')
        return redirect(url_for('settlements.detail', id=settlement_id))

    # GET: show form with suggested revenue from ticket sales
    suggested_revenue_cents = get_total_door_revenue_cents(conn, booking_id)
    return render_template('settlements/form.html',
                           booking=booking,
                           suggested_revenue_cents=suggested_revenue_cents)


@settlements_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
@role_required('venue_manager')
def approve(id):
    conn = get_db()
    settlement = get_settlement(conn, id)
    if settlement is None:
        abort(404)

    booking = get_booking(conn, settlement['booking_id'])
    if booking is None:
        abort(404)

    conn.execute('BEGIN IMMEDIATE')
    approve_settlement(conn, id, g.user['id'])
    success = advance_booking_state(conn, booking['id'], 'settled', g.user['id'])
    if not success:
        conn.rollback()
        flash('Cannot transition booking to this state.', 'error')
        return redirect(url_for('settlements.detail', id=id))
    conn.commit()

    flash('Settlement approved successfully.', 'success')
    return redirect(url_for('settlements.detail', id=id))


@settlements_bp.route('/<int:id>/pdf')
@login_required
def download_pdf(id):
    conn = get_db()
    settlement = get_settlement(conn, id)
    if settlement is None:
        abort(404)

    pdf_bytes = generate_settlement_pdf(settlement)
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename=settlement_{id}.pdf'}
    )
