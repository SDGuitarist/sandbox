from datetime import date, timedelta

from flask import (
    flash, redirect, render_template, request, session, url_for
)

from app.db import get_db
from app.helpers import login_required, log_activity
from . import bp
from .forms import InvoiceForm, StatusForm


# ---------------------------------------------------------------------------
# Allowed status transitions
# ---------------------------------------------------------------------------
ALLOWED_TRANSITIONS = {
    'draft': ['sent'],
    'sent': ['viewed', 'paid', 'overdue'],
    'viewed': ['paid', 'overdue'],
    'overdue': ['paid'],
    'paid': [],
}


# ---------------------------------------------------------------------------
# list_invoices
# ---------------------------------------------------------------------------
@bp.route('/')
@login_required
def list_invoices():
    user_id = session['user_id']
    with get_db() as db:
        query = """
            SELECT i.*, c.name AS client_name
            FROM invoices i
            LEFT JOIN clients c ON i.client_id = c.id
            WHERE i.user_id = ?
        """
        params = [user_id]

        status_filter = request.args.get('status', '').strip()
        if status_filter:
            query += " AND i.status = ?"
            params.append(status_filter)

        client_id_filter = request.args.get('client_id', type=int)
        if client_id_filter:
            query += " AND i.client_id = ?"
            params.append(client_id_filter)

        start_date = request.args.get('start_date', '').strip()
        if start_date:
            query += " AND i.issue_date >= ?"
            params.append(start_date)

        end_date = request.args.get('end_date', '').strip()
        if end_date:
            query += " AND i.issue_date <= ?"
            params.append(end_date)

        query += " ORDER BY i.issue_date DESC"
        invoices = db.execute(query, params).fetchall()

        clients = db.execute(
            "SELECT id, name FROM clients WHERE user_id = ? ORDER BY name",
            (user_id,)
        ).fetchall()

    return render_template(
        'invoices/list.html',
        invoices=invoices,
        clients=clients,
        status_filter=status_filter,
        client_id_filter=client_id_filter,
        start_date=start_date if start_date else '',
        end_date=end_date if end_date else '',
    )


# ---------------------------------------------------------------------------
# create_invoice
# ---------------------------------------------------------------------------
@bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_invoice():
    user_id = session['user_id']

    if request.method == 'GET':
        with get_db() as db:
            clients = db.execute(
                "SELECT id, name FROM clients WHERE user_id = ? ORDER BY name",
                (user_id,)
            ).fetchall()
            catalog_items = db.execute(
                "SELECT id, name, description, unit_price_cents FROM catalog_items WHERE user_id = ? ORDER BY name",
                (user_id,)
            ).fetchall()
            user_row = db.execute(
                "SELECT default_payment_terms, default_tax_rate FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()

            default_payment_terms = user_row['default_payment_terms'] if user_row else 30
            default_tax_rate = user_row['default_tax_rate'] if user_row else 0.0

            # Check for deal-to-invoice prefill
            from_deal_id = request.args.get('from_deal', type=int)
            prefill_client_id = None
            prefill_notes = ''
            if from_deal_id:
                deal = db.execute(
                    "SELECT * FROM deals WHERE id = ? AND user_id = ?",
                    (from_deal_id, user_id)
                ).fetchone()
                if deal:
                    prefill_client_id = deal['client_id']
                    prefill_notes = f"From deal: {deal['title']}"

        today = date.today()
        due = today + timedelta(days=default_payment_terms)

        return render_template(
            'invoices/form.html',
            clients=clients,
            catalog_items=catalog_items,
            default_tax_rate=default_tax_rate,
            issue_date=today.isoformat(),
            due_date=due.isoformat(),
            prefill_client_id=prefill_client_id,
            prefill_notes=prefill_notes,
            invoice=None,
            line_items=[],
            editing=False,
        )

    # --- POST -----------------------------------------------------------------
    client_id = request.form.get('client_id', type=int)
    issue_date = request.form.get('issue_date', '').strip()
    due_date = request.form.get('due_date', '').strip()
    notes = request.form.get('notes', '').strip()

    if not client_id or not issue_date or not due_date:
        flash('Client, issue date, and due date are required.', 'danger')
        return redirect(url_for('invoices.create_invoice'))

    # Parallel arrays for line items
    descriptions = request.form.getlist('descriptions[]')
    quantities = request.form.getlist('quantities[]')
    unit_prices = request.form.getlist('unit_prices[]')
    tax_rates = request.form.getlist('tax_rates[]')
    catalog_item_ids = request.form.getlist('catalog_item_ids[]')

    # FC: Length-check all arrays before zip()
    if not descriptions or not (
        len(descriptions) == len(quantities) == len(unit_prices) == len(tax_rates)
    ):
        flash('Line item data is invalid. All fields must have the same number of entries.', 'danger')
        return redirect(url_for('invoices.create_invoice'))

    with get_db() as db:
        # Generate invoice number
        user_row = db.execute(
            "SELECT invoice_prefix, default_payment_terms FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        prefix = user_row['invoice_prefix'] if user_row else 'INV'

        max_num_row = db.execute(
            "SELECT MAX(CAST(SUBSTR(invoice_number, LENGTH(?) + 2) AS INTEGER)) FROM invoices WHERE user_id = ?",
            (prefix, user_id)
        ).fetchone()
        max_num = max_num_row[0] if max_num_row[0] is not None else 0
        invoice_number = f"{prefix}-{max_num + 1:03d}"

        # Calculate line item totals
        subtotal_cents = 0
        tax_cents = 0
        parsed_items = []
        for i in range(len(descriptions)):
            desc = descriptions[i].strip()
            if not desc:
                continue
            try:
                qty = float(quantities[i])
                up_cents = int(round(float(unit_prices[i]) * 100))
                tr = float(tax_rates[i])
            except (ValueError, IndexError):
                flash('Invalid numeric value in line items.', 'danger')
                return redirect(url_for('invoices.create_invoice'))

            line_subtotal = int(round(qty * up_cents))
            line_tax = int(round(qty * up_cents * (tr / 100)))
            line_total_cents = line_subtotal + line_tax

            cat_id = None
            if i < len(catalog_item_ids) and catalog_item_ids[i]:
                try:
                    cat_id = int(catalog_item_ids[i])
                except ValueError:
                    cat_id = None

            parsed_items.append({
                'description': desc,
                'quantity': qty,
                'unit_price_cents': up_cents,
                'tax_rate': tr,
                'line_total_cents': line_total_cents,
                'catalog_item_id': cat_id,
                'sort_order': i,
            })
            subtotal_cents += line_subtotal
            tax_cents += line_tax

        total_cents = subtotal_cents + tax_cents

        if not parsed_items:
            flash('At least one line item is required.', 'danger')
            return redirect(url_for('invoices.create_invoice'))

        # Insert invoice
        db.execute("""
            INSERT INTO invoices
                (user_id, client_id, invoice_number, status, issue_date, due_date,
                 subtotal_cents, tax_cents, total_cents, notes)
            VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)
        """, (user_id, client_id, invoice_number, issue_date, due_date,
              subtotal_cents, tax_cents, total_cents, notes))

        invoice_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Insert line items
        for item in parsed_items:
            db.execute("""
                INSERT INTO invoice_line_items
                    (invoice_id, catalog_item_id, description, quantity,
                     unit_price_cents, tax_rate, line_total_cents, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_id, item['catalog_item_id'], item['description'],
                  item['quantity'], item['unit_price_cents'], item['tax_rate'],
                  item['line_total_cents'], item['sort_order']))

        # Log activity (does NOT commit)
        log_activity(db, client_id, user_id, 'note',
                     f"Invoice {invoice_number} created")

        db.commit()

    flash('Invoice created successfully.', 'success')
    return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


# ---------------------------------------------------------------------------
# view_invoice
# ---------------------------------------------------------------------------
@bp.route('/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    user_id = session['user_id']
    with get_db() as db:
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
            (invoice_id, user_id)
        ).fetchone()
        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices.list_invoices'))

        client = None
        if invoice['client_id']:
            client = db.execute(
                "SELECT * FROM clients WHERE id = ?",
                (invoice['client_id'],)
            ).fetchone()

        line_items = db.execute(
            "SELECT * FROM invoice_line_items WHERE invoice_id = ? ORDER BY sort_order",
            (invoice_id,)
        ).fetchall()

        payments = db.execute(
            "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date DESC",
            (invoice_id,)
        ).fetchall()

        total_paid = sum(p['amount_cents'] for p in payments)
        remaining = invoice['total_cents'] - total_paid

        user_info = db.execute(
            "SELECT company_name, address, phone, business_email, tax_id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        allowed_next = ALLOWED_TRANSITIONS.get(invoice['status'], [])

    status_form = StatusForm()

    return render_template(
        'invoices/detail.html',
        invoice=invoice,
        client=client,
        line_items=line_items,
        payments=payments,
        total_paid=total_paid,
        remaining=remaining,
        user_info=user_info,
        allowed_next=allowed_next,
        status_form=status_form,
    )


# ---------------------------------------------------------------------------
# edit_invoice
# ---------------------------------------------------------------------------
@bp.route('/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    user_id = session['user_id']

    with get_db() as db:
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
            (invoice_id, user_id)
        ).fetchone()
        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices.list_invoices'))

        if invoice['status'] != 'draft':
            flash('Only draft invoices can be edited.', 'danger')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

        if request.method == 'GET':
            clients = db.execute(
                "SELECT id, name FROM clients WHERE user_id = ? ORDER BY name",
                (user_id,)
            ).fetchall()
            catalog_items = db.execute(
                "SELECT id, name, description, unit_price_cents FROM catalog_items WHERE user_id = ? ORDER BY name",
                (user_id,)
            ).fetchall()
            line_items = db.execute(
                "SELECT * FROM invoice_line_items WHERE invoice_id = ? ORDER BY sort_order",
                (invoice_id,)
            ).fetchall()
            user_row = db.execute(
                "SELECT default_tax_rate FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            default_tax_rate = user_row['default_tax_rate'] if user_row else 0.0

            return render_template(
                'invoices/form.html',
                clients=clients,
                catalog_items=catalog_items,
                default_tax_rate=default_tax_rate,
                issue_date=invoice['issue_date'],
                due_date=invoice['due_date'],
                prefill_client_id=invoice['client_id'],
                prefill_notes=invoice['notes'],
                invoice=invoice,
                line_items=line_items,
                editing=True,
            )

        # --- POST (edit) ------------------------------------------------------
        client_id = request.form.get('client_id', type=int)
        issue_date = request.form.get('issue_date', '').strip()
        due_date = request.form.get('due_date', '').strip()
        notes = request.form.get('notes', '').strip()

        if not client_id or not issue_date or not due_date:
            flash('Client, issue date, and due date are required.', 'danger')
            return redirect(url_for('invoices.edit_invoice', invoice_id=invoice_id))

        descriptions = request.form.getlist('descriptions[]')
        quantities = request.form.getlist('quantities[]')
        unit_prices = request.form.getlist('unit_prices[]')
        tax_rates = request.form.getlist('tax_rates[]')
        catalog_item_ids = request.form.getlist('catalog_item_ids[]')

        if not descriptions or not (
            len(descriptions) == len(quantities) == len(unit_prices) == len(tax_rates)
        ):
            flash('Line item data is invalid. All fields must have the same number of entries.', 'danger')
            return redirect(url_for('invoices.edit_invoice', invoice_id=invoice_id))

        subtotal_cents = 0
        tax_cents = 0
        parsed_items = []
        for i in range(len(descriptions)):
            desc = descriptions[i].strip()
            if not desc:
                continue
            try:
                qty = float(quantities[i])
                up_cents = int(round(float(unit_prices[i]) * 100))
                tr = float(tax_rates[i])
            except (ValueError, IndexError):
                flash('Invalid numeric value in line items.', 'danger')
                return redirect(url_for('invoices.edit_invoice', invoice_id=invoice_id))

            line_subtotal = int(round(qty * up_cents))
            line_tax = int(round(qty * up_cents * (tr / 100)))
            line_total_cents = line_subtotal + line_tax

            cat_id = None
            if i < len(catalog_item_ids) and catalog_item_ids[i]:
                try:
                    cat_id = int(catalog_item_ids[i])
                except ValueError:
                    cat_id = None

            parsed_items.append({
                'description': desc,
                'quantity': qty,
                'unit_price_cents': up_cents,
                'tax_rate': tr,
                'line_total_cents': line_total_cents,
                'catalog_item_id': cat_id,
                'sort_order': i,
            })
            subtotal_cents += line_subtotal
            tax_cents += line_tax

        total_cents = subtotal_cents + tax_cents

        if not parsed_items:
            flash('At least one line item is required.', 'danger')
            return redirect(url_for('invoices.edit_invoice', invoice_id=invoice_id))

        # Delete old line items and re-insert
        db.execute("DELETE FROM invoice_line_items WHERE invoice_id = ?", (invoice_id,))

        db.execute("""
            UPDATE invoices
            SET client_id = ?, issue_date = ?, due_date = ?, notes = ?,
                subtotal_cents = ?, tax_cents = ?, total_cents = ?,
                updated_at = datetime('now')
            WHERE id = ?
        """, (client_id, issue_date, due_date, notes,
              subtotal_cents, tax_cents, total_cents, invoice_id))

        for item in parsed_items:
            db.execute("""
                INSERT INTO invoice_line_items
                    (invoice_id, catalog_item_id, description, quantity,
                     unit_price_cents, tax_rate, line_total_cents, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_id, item['catalog_item_id'], item['description'],
                  item['quantity'], item['unit_price_cents'], item['tax_rate'],
                  item['line_total_cents'], item['sort_order']))

        db.commit()

    flash('Invoice updated successfully.', 'success')
    return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------
@bp.route('/<int:invoice_id>/status', methods=['POST'])
@login_required
def update_status(invoice_id):
    user_id = session['user_id']
    form = StatusForm()

    if not form.validate_on_submit():
        flash('Invalid status update request.', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

    new_status = form.new_status.data.strip()

    with get_db() as db:
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
            (invoice_id, user_id)
        ).fetchone()
        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices.list_invoices'))

        old_status = invoice['status']
        allowed = ALLOWED_TRANSITIONS.get(old_status, [])
        if new_status not in allowed:
            flash(f'Cannot transition from {old_status} to {new_status}.', 'danger')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

        db.execute(
            "UPDATE invoices SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, invoice_id)
        )

        # Log activity (does NOT commit)
        log_activity(
            db, invoice['client_id'], user_id, 'note',
            f"Invoice {invoice['invoice_number']} status: {old_status} -> {new_status}"
        )

        db.commit()

    flash(f'Invoice status updated to {new_status}.', 'success')
    return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


# ---------------------------------------------------------------------------
# duplicate_invoice
# ---------------------------------------------------------------------------
@bp.route('/<int:invoice_id>/duplicate', methods=['POST'])
@login_required
def duplicate_invoice(invoice_id):
    user_id = session['user_id']

    with get_db() as db:
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
            (invoice_id, user_id)
        ).fetchone()
        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices.list_invoices'))

        # Generate new invoice number
        user_row = db.execute(
            "SELECT invoice_prefix, default_payment_terms FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        prefix = user_row['invoice_prefix'] if user_row else 'INV'
        payment_terms = user_row['default_payment_terms'] if user_row else 30

        max_num_row = db.execute(
            "SELECT MAX(CAST(SUBSTR(invoice_number, LENGTH(?) + 2) AS INTEGER)) FROM invoices WHERE user_id = ?",
            (prefix, user_id)
        ).fetchone()
        max_num = max_num_row[0] if max_num_row[0] is not None else 0
        new_number = f"{prefix}-{max_num + 1:03d}"

        today = date.today()
        new_due = today + timedelta(days=payment_terms)

        # Insert duplicated invoice as draft
        db.execute("""
            INSERT INTO invoices
                (user_id, client_id, invoice_number, status, issue_date, due_date,
                 subtotal_cents, tax_cents, total_cents, notes)
            VALUES (?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)
        """, (user_id, invoice['client_id'], new_number,
              today.isoformat(), new_due.isoformat(),
              invoice['subtotal_cents'], invoice['tax_cents'],
              invoice['total_cents'], invoice['notes']))

        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Copy line items
        items = db.execute(
            "SELECT * FROM invoice_line_items WHERE invoice_id = ? ORDER BY sort_order",
            (invoice_id,)
        ).fetchall()
        for item in items:
            db.execute("""
                INSERT INTO invoice_line_items
                    (invoice_id, catalog_item_id, description, quantity,
                     unit_price_cents, tax_rate, line_total_cents, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_id, item['catalog_item_id'], item['description'],
                  item['quantity'], item['unit_price_cents'], item['tax_rate'],
                  item['line_total_cents'], item['sort_order']))

        db.commit()

    flash(f'Invoice duplicated as draft {new_number}.', 'success')
    return redirect(url_for('invoices.view_invoice', invoice_id=new_id))


# ---------------------------------------------------------------------------
# delete_invoice
# ---------------------------------------------------------------------------
@bp.route('/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    user_id = session['user_id']

    with get_db() as db:
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
            (invoice_id, user_id)
        ).fetchone()
        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices.list_invoices'))

        db.execute("DELETE FROM invoice_line_items WHERE invoice_id = ?", (invoice_id,))
        db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
        db.commit()

    flash('Invoice deleted.', 'success')
    return redirect(url_for('invoices.list_invoices'))
