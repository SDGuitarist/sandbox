import math
import sqlite3
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth import login_required
from app.db import get_db
from app.models.invoice import (
    create_invoice,
    delete_invoice,
    get_all_invoices,
    get_invoice,
    get_invoices_by_member,
    update_invoice,
)
from app.models.member import get_all_members
from app.models.payment import get_payments_by_invoice, get_total_paid_for_invoice

bp = Blueprint('billing', __name__)


@bp.route('/')
@login_required
def list_invoices():
    conn = get_db()
    invoices = get_all_invoices(conn)
    return render_template('billing/list.html', invoices=invoices)


@bp.route('/new')
@login_required
def new_invoice():
    conn = get_db()
    return render_template('billing/form.html', invoice=None, members=get_all_members(conn))


@bp.route('/new', methods=['POST'])
@login_required
def create():
    conn = get_db()

    # Validate member_id -- required int, member must exist
    try:
        member_id = int(request.form.get('member_id', ''))
    except (ValueError, TypeError):
        flash('Invalid member.', 'error')
        return redirect(url_for('billing.new_invoice'))

    # Check member exists by querying all members and checking
    members = get_all_members(conn)
    member_exists = any(m['id'] == member_id for m in members)
    if not member_exists:
        flash('Invalid member.', 'error')
        return redirect(url_for('billing.new_invoice'))

    # Validate amount -- money parsing pattern (FC4, FC7)
    raw = request.form.get('amount', '0').strip()
    try:
        val = float(raw)
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(url_for('billing.new_invoice'))
    if not math.isfinite(val) or val <= 0 or val > 999999.99:
        flash('Invalid amount.', 'error')
        return redirect(url_for('billing.new_invoice'))
    amount_cents = round(val * 100)

    # Validate description -- strip, 1-500 chars, required
    description = request.form.get('description', '').strip()
    if not description or len(description) > 500:
        flash('Description is required.', 'error')
        return redirect(url_for('billing.new_invoice'))

    # Validate due_date -- required, valid ISO date (FC23)
    due_date = request.form.get('due_date', '').strip()
    if not due_date:
        flash('Invalid due date.', 'error')
        return redirect(url_for('billing.new_invoice'))
    try:
        datetime.strptime(due_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid due date.', 'error')
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
    total_paid = get_total_paid_for_invoice(conn, invoice_id)
    return render_template('billing/detail.html',
                           invoice=invoice,
                           payments=payments,
                           total_paid=total_paid)


@bp.route('/<int:invoice_id>/edit')
@login_required
def edit_form(invoice_id):
    conn = get_db()
    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        abort(404)
    return render_template('billing/form.html', invoice=invoice, members=get_all_members(conn))


@bp.route('/<int:invoice_id>/edit', methods=['POST'])
@login_required
def update(invoice_id):
    conn = get_db()
    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        abort(404)

    # Validate amount -- money parsing pattern (FC4, FC7)
    raw = request.form.get('amount', '0').strip()
    try:
        val = float(raw)
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(url_for('billing.edit_form', invoice_id=invoice_id))
    if not math.isfinite(val) or val <= 0 or val > 999999.99:
        flash('Invalid amount.', 'error')
        return redirect(url_for('billing.edit_form', invoice_id=invoice_id))
    amount_cents = round(val * 100)

    # Validate description -- strip, 1-500 chars, required
    description = request.form.get('description', '').strip()
    if not description or len(description) > 500:
        flash('Description is required.', 'error')
        return redirect(url_for('billing.edit_form', invoice_id=invoice_id))

    # Validate due_date -- required, valid ISO date (FC23)
    due_date = request.form.get('due_date', '').strip()
    if not due_date:
        flash('Invalid due date.', 'error')
        return redirect(url_for('billing.edit_form', invoice_id=invoice_id))
    try:
        datetime.strptime(due_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid due date.', 'error')
        return redirect(url_for('billing.edit_form', invoice_id=invoice_id))

    # Validate status -- must be in allowed set
    status = request.form.get('status', '').strip()
    if status not in ('pending', 'paid', 'overdue', 'cancelled'):
        flash('Invalid status.', 'error')
        return redirect(url_for('billing.edit_form', invoice_id=invoice_id))

    update_invoice(conn, invoice_id, amount_cents, description, due_date, status)
    flash('Invoice updated successfully.', 'success')
    return redirect(url_for('billing.detail', invoice_id=invoice_id))


@bp.route('/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete(invoice_id):
    conn = get_db()
    invoice = get_invoice(conn, invoice_id)
    if invoice is None:
        abort(404)
    try:
        delete_invoice(conn, invoice_id)
        flash('Invoice deleted successfully.', 'success')
    except sqlite3.IntegrityError:
        flash('Cannot delete: invoice has payments.', 'error')
    return redirect(url_for('billing.list_invoices'))
