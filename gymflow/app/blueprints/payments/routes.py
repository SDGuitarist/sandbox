import math
import sqlite3
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models import create_payment, delete_payment, get_all_invoices, get_all_payments, get_invoice, get_payment

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
    invoices = get_all_invoices(conn)
    selected_invoice_id = request.args.get('invoice_id', type=int)
    return render_template(
        'payments/form.html',
        invoices=invoices,
        selected_invoice_id=selected_invoice_id,
    )


@bp.route('/', methods=['POST'])
@login_required
def create_payment_route():
    conn = get_db()

    # Validate invoice_id -- must be present and must exist in DB
    invoice_id_raw = request.form.get('invoice_id', '').strip()
    if not invoice_id_raw:
        flash('Invoice is required.', 'error')
        return redirect(url_for('payments.new_payment'))
    try:
        invoice_id = int(invoice_id_raw)
    except (ValueError, TypeError):
        flash('Invoice is required.', 'error')
        return redirect(url_for('payments.new_payment'))

    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        flash('Invoice is required.', 'error')
        return redirect(url_for('payments.new_payment'))

    # Validate amount -- money parsing (FC4: nan/inf check, cap at $999,999.99)
    try:
        raw = float(request.form.get('amount', '0'))
        if math.isnan(raw) or math.isinf(raw):
            raise ValueError('Invalid amount')
        amount_cents = round(raw * 100)
        if amount_cents <= 0:
            flash('Amount must be positive.', 'error')
            return redirect(url_for('payments.new_payment'))
        if amount_cents > 99999999:
            flash('Amount too large.', 'error')
            return redirect(url_for('payments.new_payment'))
    except (ValueError, TypeError):
        flash('Valid amount is required.', 'error')
        return redirect(url_for('payments.new_payment'))

    # Validate payment_method -- must be one of the allowed values
    payment_method = request.form.get('payment_method', '').strip()
    if payment_method not in ('cash', 'card', 'bank_transfer', 'other'):
        flash('Invalid payment method.', 'error')
        return redirect(url_for('payments.new_payment'))

    # Optional fields
    reference_number = request.form.get('reference_number', '').strip()
    notes = request.form.get('notes', '').strip()
    payment_date = request.form.get('payment_date', '').strip()

    # Default payment_date to today if not provided
    if not payment_date:
        payment_date = date.today().isoformat()

    # FC37: create_payment commits internally -- no manual commit needed
    create_payment(conn, invoice_id, amount_cents, payment_date,
                   payment_method, reference_number, notes)
    flash('Payment created successfully.', 'success')
    return redirect(url_for('billing.detail', invoice_id=invoice_id))


@bp.route('/<int:payment_id>/delete', methods=['POST'])
@login_required
def delete_payment_route(payment_id):
    conn = get_db()

    # Need to get the payment to find its invoice_id for redirect
    payment = get_payment(conn, payment_id)
    if payment is None:
        abort(404)

    invoice_id = payment['invoice_id']

    try:
        delete_payment(conn, payment_id)
        flash('Payment deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete: referenced by other records.', 'error')

    return redirect(url_for('billing.detail', invoice_id=invoice_id))
