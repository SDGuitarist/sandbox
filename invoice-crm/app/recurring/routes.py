from flask import render_template, request, redirect, url_for, flash, session
from . import bp
from app.db import get_db
from app.helpers import login_required


def generate_due_invoices(db, user_id):
    """Generate invoices for recurring items due today or earlier.
    Does NOT commit -- caller commits.
    Returns count of invoices generated."""
    due = db.execute("""
        SELECT * FROM invoices
        WHERE user_id = ? AND is_recurring = 1
          AND next_recurrence_date IS NOT NULL
          AND next_recurrence_date <= date('now')
          AND status != 'draft'
    """, (user_id,)).fetchall()

    count = 0
    for inv in due:
        # Generate next invoice number
        max_num = db.execute(
            "SELECT MAX(CAST(SUBSTR(invoice_number, LENGTH(?) + 2) AS INTEGER)) FROM invoices WHERE user_id = ?",
            (inv['invoice_number'][:3], user_id)
        ).fetchone()[0] or 0
        user_row = db.execute(
            "SELECT invoice_prefix, default_payment_terms FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        prefix = user_row['invoice_prefix']
        payment_terms = user_row['default_payment_terms']
        new_number = f"{prefix}-{max_num + 1:03d}"

        # Copy invoice as draft
        db.execute("""
            INSERT INTO invoices (user_id, client_id, invoice_number, status, issue_date, due_date,
                                  subtotal_cents, tax_cents, total_cents, notes, parent_invoice_id)
            VALUES (?, ?, ?, 'draft', date('now'), date('now', '+' || ? || ' days'), ?, ?, ?, ?, ?)
        """, (user_id, inv['client_id'], new_number,
              payment_terms,
              inv['subtotal_cents'], inv['tax_cents'], inv['total_cents'],
              inv['notes'], inv['id']))
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Copy line items
        items = db.execute(
            "SELECT * FROM invoice_line_items WHERE invoice_id = ?",
            (inv['id'],)
        ).fetchall()
        for item in items:
            db.execute("""
                INSERT INTO invoice_line_items (invoice_id, catalog_item_id, description, quantity,
                                                unit_price_cents, tax_rate, line_total_cents, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (new_id, item['catalog_item_id'], item['description'], item['quantity'],
                  item['unit_price_cents'], item['tax_rate'], item['line_total_cents'],
                  item['sort_order']))

        # Advance recurrence date
        interval_map = {
            'weekly': '+7 days',
            'monthly': '+1 month',
            'quarterly': '+3 months',
            'annually': '+1 year',
        }
        modifier = interval_map.get(inv['recurrence_interval'], '+1 month')
        db.execute("""
            UPDATE invoices SET next_recurrence_date = date(next_recurrence_date, ?)
            WHERE id = ?
        """, (modifier, inv['id']))
        count += 1

    return count


@bp.route('/<int:invoice_id>/settings', methods=['GET', 'POST'])
@login_required
def set_recurring(invoice_id):
    with get_db() as db:
        user_id = session['user_id']
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
            (invoice_id, user_id)
        ).fetchone()
        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices.list_invoices'))

        if request.method == 'POST':
            is_recurring = 1 if request.form.get('is_recurring') else 0
            recurrence_interval = request.form.get('recurrence_interval') if is_recurring else None
            next_recurrence_date = request.form.get('next_recurrence_date') if is_recurring else None

            db.execute("""
                UPDATE invoices
                SET is_recurring = ?, recurrence_interval = ?, next_recurrence_date = ?,
                    updated_at = datetime('now')
                WHERE id = ? AND user_id = ?
            """, (is_recurring, recurrence_interval, next_recurrence_date,
                  invoice_id, user_id))
            db.commit()
            flash('Recurring settings updated successfully.', 'success')
            return redirect(url_for('recurring.set_recurring', invoice_id=invoice_id))

        return render_template('recurring/settings.html', invoice=invoice)


@bp.route('/<int:invoice_id>/history')
@login_required
def view_history(invoice_id):
    with get_db() as db:
        user_id = session['user_id']
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
            (invoice_id, user_id)
        ).fetchone()
        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('invoices.list_invoices'))

        children = db.execute("""
            SELECT id, invoice_number, status, issue_date, total_cents
            FROM invoices
            WHERE parent_invoice_id = ? AND user_id = ?
            ORDER BY issue_date DESC
        """, (invoice_id, user_id)).fetchall()

        return render_template('recurring/history.html', invoice=invoice, children=children)


@bp.route('/generate', methods=['POST'])
@login_required
def generate_recurring():
    with get_db() as db:
        user_id = session['user_id']
        count = generate_due_invoices(db, user_id)
        db.commit()
        if count > 0:
            flash(f'{count} recurring invoice(s) generated.', 'info')
        else:
            flash('No recurring invoices were due.', 'info')
        return redirect(url_for('invoices.list_invoices'))
