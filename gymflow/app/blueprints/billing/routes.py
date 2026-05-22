import math
import sqlite3

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models import (
    create_invoice,
    delete_invoice,
    get_all_invoices,
    get_all_members,
    get_invoice,
    get_invoice_paid_amount,
    get_invoices_by_member,
    get_invoices_by_status,
    get_payments_by_invoice,
    update_invoice,
)

bp = Blueprint('billing', __name__)


@bp.route('/')
@login_required
def list_invoices():
    conn = get_db()
    status_filter = request.args.get('status', '').strip()
    if status_filter in ('pending', 'paid', 'overdue', 'cancelled'):
        invoices = get_invoices_by_status(conn, status_filter)
    else:
        invoices = get_all_invoices(conn)
    return render_template('billing/list.html', invoices=invoices)


@bp.route('/new')
@login_required
def new_invoice():
    conn = get_db()
    return render_template('billing/form.html', invoice=None, members=get_all_members(conn))


@bp.route('/', methods=['POST'])
@login_required
def create_invoice_route():
    conn = get_db()

    # Validate member_id
    try:
        member_id = int(request.form.get('member_id', ''))
    except (ValueError, TypeError):
        flash('Member is required.', 'error')
        return redirect(url_for('billing.new_invoice'))

    # Validate amount (money parsing pattern -- FC4)
    try:
        raw = float(request.form.get('amount', '0'))
        if math.isnan(raw) or math.isinf(raw):
            raise ValueError('Invalid amount')
        amount_cents = round(raw * 100)
        if amount_cents <= 0:
            flash('Amount must be positive.', 'error')
            return redirect(url_for('billing.new_invoice'))
        if amount_cents > 99999999:  # Cap at $999,999.99
            flash('Amount too large.', 'error')
            return redirect(url_for('billing.new_invoice'))
    except (ValueError, TypeError):
        flash('Valid amount is required.', 'error')
        return redirect(url_for('billing.new_invoice'))

    # Validate description
    description = request.form.get('description', '').strip()
    if not description or len(description) > 500:
        flash('Description is required.', 'error')
        return redirect(url_for('billing.new_invoice'))

    # Validate due_date
    due_date = request.form.get('due_date', '').strip()
    if not due_date:
        flash('Due date is required.', 'error')
        return redirect(url_for('billing.new_invoice'))

    invoice_id = create_invoice(conn, member_id, amount_cents, description, due_date)
    flash('Invoice created successfully.', 'success')
    return redirect(url_for('billing.detail', invoice_id=invoice_id))


@bp.route('/<int:invoice_id>')
@login_required
def detail(invoice_id):
    conn = get_db()
    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        abort(404)
    payments = get_payments_by_invoice(conn, invoice_id)
    paid_amount = get_invoice_paid_amount(conn, invoice_id)
    return render_template('billing/detail.html',
                           invoice=invoice,
                           payments=payments,
                           paid_amount=paid_amount)


@bp.route('/<int:invoice_id>/edit')
@login_required
def edit_invoice(invoice_id):
    conn = get_db()
    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        abort(404)
    return render_template('billing/form.html', invoice=invoice, members=get_all_members(conn))


@bp.route('/<int:invoice_id>/edit', methods=['POST'])
@login_required
def update_invoice_route(invoice_id):
    conn = get_db()
    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        abort(404)

    # Validate amount (money parsing pattern -- FC4)
    try:
        raw = float(request.form.get('amount', '0'))
        if math.isnan(raw) or math.isinf(raw):
            raise ValueError('Invalid amount')
        amount_cents = round(raw * 100)
        if amount_cents <= 0:
            flash('Amount must be positive.', 'error')
            return redirect(url_for('billing.edit_invoice', invoice_id=invoice_id))
        if amount_cents > 99999999:  # Cap at $999,999.99
            flash('Amount too large.', 'error')
            return redirect(url_for('billing.edit_invoice', invoice_id=invoice_id))
    except (ValueError, TypeError):
        flash('Valid amount is required.', 'error')
        return redirect(url_for('billing.edit_invoice', invoice_id=invoice_id))

    # Validate description
    description = request.form.get('description', '').strip()
    if not description or len(description) > 500:
        flash('Description is required.', 'error')
        return redirect(url_for('billing.edit_invoice', invoice_id=invoice_id))

    # Validate due_date
    due_date = request.form.get('due_date', '').strip()
    if not due_date:
        flash('Due date is required.', 'error')
        return redirect(url_for('billing.edit_invoice', invoice_id=invoice_id))

    # Validate status
    status = request.form.get('status', '').strip()
    if status not in ('pending', 'paid', 'overdue', 'cancelled'):
        flash('Invalid status.', 'error')
        return redirect(url_for('billing.edit_invoice', invoice_id=invoice_id))

    update_invoice(conn, invoice_id, amount_cents, description, due_date, status)
    flash('Invoice updated successfully.', 'success')
    return redirect(url_for('billing.detail', invoice_id=invoice_id))


@bp.route('/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice_route(invoice_id):
    conn = get_db()
    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        abort(404)
    try:
        delete_invoice(conn, invoice_id)
        flash('Invoice deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete: referenced by other records.', 'error')
    return redirect(url_for('billing.list_invoices'))
