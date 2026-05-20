from flask import render_template, redirect, url_for, flash, request, session

from app.db import get_db
from app.helpers import login_required, log_activity
from app.payments import bp
from app.payments.forms import PaymentForm


@bp.route('/invoice/<int:invoice_id>/new', methods=['GET', 'POST'])
@login_required
def create_payment(invoice_id):
    user_id = session['user_id']

    with get_db() as db:
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ? AND user_id = ?",
            (invoice_id, user_id)
        ).fetchone()

        if not invoice:
            flash('Invoice not found.', 'danger')
            return redirect(url_for('payments.list_payments'))

        if invoice['status'] == 'draft':
            flash('Cannot record payments on draft invoices. Send the invoice first.', 'danger')
            return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))

        form = PaymentForm()

        if form.validate_on_submit():
            amount_cents = int(round(float(form.amount.data) * 100))
            payment_date = form.payment_date.data.strftime('%Y-%m-%d')
            method = form.method.data
            notes = form.notes.data or ''

            db.execute(
                """INSERT INTO payments (invoice_id, user_id, amount_cents, payment_date, method, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (invoice_id, user_id, amount_cents, payment_date, method, notes)
            )

            # Check if invoice is fully paid
            total_paid = db.execute(
                "SELECT COALESCE(SUM(amount_cents), 0) FROM payments WHERE invoice_id = ?",
                (invoice_id,)
            ).fetchone()[0]
            invoice_total = db.execute(
                "SELECT total_cents FROM invoices WHERE id = ?",
                (invoice_id,)
            ).fetchone()['total_cents']

            if total_paid >= invoice_total:
                db.execute(
                    "UPDATE invoices SET status = 'paid', updated_at = datetime('now') WHERE id = ?",
                    (invoice_id,)
                )
                if total_paid > invoice_total:
                    flash('Warning: Overpayment recorded.', 'warning')

            # Log activity
            amount_display = f"${amount_cents / 100:,.2f}"
            log_activity(
                db,
                invoice['client_id'],
                user_id,
                'note',
                f"Payment of {amount_display} recorded on invoice {invoice['invoice_number']}"
            )

            db.commit()

            flash('Payment created successfully.', 'success')
            return redirect(url_for('payments.list_payments'))

        return render_template(
            'payments/form.html',
            form=form,
            invoice=invoice
        )


@bp.route('/')
@login_required
def list_payments():
    user_id = session['user_id']
    client_id = request.args.get('client_id', type=int)

    with get_db() as db:
        query = """
            SELECT p.*, i.invoice_number, c.name AS client_name
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
            LEFT JOIN clients c ON i.client_id = c.id
            WHERE p.user_id = ?
        """
        params = [user_id]

        if client_id:
            query += " AND i.client_id = ?"
            params.append(client_id)

        query += " ORDER BY p.payment_date DESC, p.created_at DESC"

        payments = db.execute(query, params).fetchall()

    return render_template('payments/list.html', payments=payments, client_id=client_id)


@bp.route('/<int:payment_id>/delete', methods=['POST'])
@login_required
def delete_payment(payment_id):
    user_id = session['user_id']

    with get_db() as db:
        payment = db.execute(
            "SELECT * FROM payments WHERE id = ? AND user_id = ?",
            (payment_id, user_id)
        ).fetchone()

        if not payment:
            flash('Payment not found.', 'danger')
            return redirect(url_for('payments.list_payments'))

        invoice_id = payment['invoice_id']

        db.execute("DELETE FROM payments WHERE id = ?", (payment_id,))

        # Recalculate if invoice should revert from 'paid'
        invoice = db.execute(
            "SELECT * FROM invoices WHERE id = ?",
            (invoice_id,)
        ).fetchone()

        if invoice and invoice['status'] == 'paid':
            total_paid = db.execute(
                "SELECT COALESCE(SUM(amount_cents), 0) FROM payments WHERE invoice_id = ?",
                (invoice_id,)
            ).fetchone()[0]
            invoice_total = invoice['total_cents']

            if total_paid < invoice_total:
                # Revert to 'sent' -- the safe default. We don't track pre-payment
                # status, so 'sent' is the most conservative revert target.
                # 'viewed' invoices will be correctly handled by overdue detection.
                db.execute(
                    "UPDATE invoices SET status = 'sent', updated_at = datetime('now') WHERE id = ?",
                    (invoice_id,)
                )

        db.commit()

        flash('Payment deleted.', 'success')
        return redirect(url_for('payments.list_payments'))
