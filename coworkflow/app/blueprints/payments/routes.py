import math
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app.db import get_db
from app.auth import login_required
from app.models.payment import (
    create_payment, get_payment, get_all_payments, delete_payment,
    get_total_paid_for_invoice,
)
from app.models.invoice import get_invoice, get_invoices_by_status

bp = Blueprint('payments', __name__)


@bp.route('/')
@login_required
def list_payments():
    conn = get_db()
    payments = get_all_payments(conn)
    return render_template('payments/list.html', payments=payments)


@bp.route('/new')
@login_required
def new_payment():
    conn = get_db()
    invoices = get_invoices_by_status(conn, 'pending')
    return render_template('payments/form.html', invoices=invoices)


@bp.route('/new', methods=['POST'])
@login_required
def create():
    conn = get_db()

    # Validate invoice_id -- required, must be valid int, must exist
    invoice_id_raw = request.form.get('invoice_id', '').strip()
    if not invoice_id_raw:
        flash('Invalid invoice.', 'error')
        return redirect(url_for('payments.new_payment'))
    try:
        invoice_id = int(invoice_id_raw)
    except (ValueError, TypeError):
        flash('Invalid invoice.', 'error')
        return redirect(url_for('payments.new_payment'))
    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        flash('Invalid invoice.', 'error')
        return redirect(url_for('payments.new_payment'))

    # Validate amount -- float, finite, >0, max 999999.99 (FC4: nan/inf guard)
    amount_raw = request.form.get('amount', '').strip()
    try:
        amount_float = float(amount_raw)
        if not math.isfinite(amount_float):
            raise ValueError('not finite')
        if amount_float <= 0:
            flash('Invalid amount.', 'error')
            return redirect(url_for('payments.new_payment'))
        if amount_float > 999999.99:
            flash('Invalid amount.', 'error')
            return redirect(url_for('payments.new_payment'))
        amount_cents = round(amount_float * 100)
    except (ValueError, TypeError):
        flash('Invalid amount.', 'error')
        return redirect(url_for('payments.new_payment'))

    # Validate payment_date -- required, valid ISO date (FC25)
    payment_date = request.form.get('payment_date', '').strip()
    if not payment_date:
        flash('Invalid date.', 'error')
        return redirect(url_for('payments.new_payment'))
    try:
        datetime.strptime(payment_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date.', 'error')
        return redirect(url_for('payments.new_payment'))

    # Validate payment_method -- must be in allowed set
    payment_method = request.form.get('payment_method', '').strip()
    if payment_method not in ('cash', 'card', 'bank_transfer', 'other'):
        flash('Invalid payment method.', 'error')
        return redirect(url_for('payments.new_payment'))

    # Optional fields
    reference_number = request.form.get('reference_number', '').strip()
    notes = request.form.get('notes', '').strip()

    # Reject payments on paid/cancelled invoices
    if invoice['status'] in ('paid', 'cancelled'):
        flash('This invoice cannot receive payments.', 'error')
        return redirect(url_for('payments.new_payment'))

    # Overpayment check (UX gate -- authoritative check is inside create_payment)
    total_paid = get_total_paid_for_invoice(conn, invoice_id)
    remaining = invoice['amount_cents'] - total_paid
    if remaining <= 0:
        flash('Invoice is already fully paid.', 'error')
        return redirect(url_for('payments.new_payment'))
    if amount_cents > remaining:
        flash('Payment exceeds remaining balance.', 'error')
        return redirect(url_for('payments.new_payment'))

    # create_payment commits internally (BEGIN IMMEDIATE)
    payment_id = create_payment(conn, invoice_id, amount_cents, payment_date,
                                payment_method, reference_number, notes)
    if payment_id is None:
        flash('Payment rejected.', 'error')
        return redirect(url_for('payments.new_payment'))
    flash('Payment created successfully.', 'success')
    return redirect(url_for('payments.list_payments'))


@bp.route('/<int:payment_id>/delete', methods=['POST'])
@login_required
def delete(payment_id):
    conn = get_db()
    payment = get_payment(conn, payment_id)
    if payment is None:
        abort(404)
    delete_payment(conn, payment_id)
    flash('Payment deleted successfully.', 'success')
    return redirect(url_for('payments.list_payments'))
