"""Tests for the payments blueprint (record, partial, full, overpayment)."""

from app.db import get_db
from tests.conftest import create_test_client, create_test_invoice


class TestRecordPayment:
    def test_record_payment(self, auth_client, app):
        """WHEN a user records a payment
        THE SYSTEM SHALL save the payment and redirect."""
        client_id = create_test_client(auth_client, app)
        invoice_id = create_test_invoice(
            auth_client, app, client_id, 'INV-PAY1', 'sent', 50000
        )

        response = auth_client.post(
            f'/payments/invoice/{invoice_id}/new',
            data={
                'amount': '200.00',
                'payment_date': '2026-05-19',
                'method': 'bank_transfer',
                'notes': 'First payment'
            }
        )
        assert response.status_code == 302

        # Verify payment exists
        with app.app_context():
            with get_db() as db:
                payment = db.execute(
                    "SELECT * FROM payments WHERE invoice_id = ?",
                    (invoice_id,)
                ).fetchone()
                assert payment is not None
                assert payment['amount_cents'] == 20000  # $200.00 = 20000 cents

    def test_payment_form_loads(self, auth_client, app):
        """WHEN a user visits the payment form
        THE SYSTEM SHALL display it."""
        client_id = create_test_client(auth_client, app)
        invoice_id = create_test_invoice(
            auth_client, app, client_id, 'INV-FORM', 'sent', 10000
        )
        response = auth_client.get(f'/payments/invoice/{invoice_id}/new')
        assert response.status_code == 200


class TestPartialPayment:
    def test_partial_payment_keeps_status(self, auth_client, app):
        """WHEN a user records a partial payment (less than total)
        THE SYSTEM SHALL keep the invoice status unchanged."""
        client_id = create_test_client(auth_client, app)
        invoice_id = create_test_invoice(
            auth_client, app, client_id, 'INV-PARTIAL', 'sent', 50000
        )

        # Pay $200 on a $500 invoice (partial)
        auth_client.post(
            f'/payments/invoice/{invoice_id}/new',
            data={
                'amount': '200.00',
                'payment_date': '2026-05-19',
                'method': 'cash',
                'notes': 'Partial payment'
            }
        )

        with app.app_context():
            with get_db() as db:
                invoice = db.execute(
                    "SELECT status FROM invoices WHERE id = ?", (invoice_id,)
                ).fetchone()
                # Status should remain 'sent' (not changed to 'paid')
                assert invoice['status'] == 'sent'


class TestFullPayment:
    def test_full_payment_marks_paid(self, auth_client, app):
        """WHEN a user records a payment equal to invoice total
        THE SYSTEM SHALL mark the invoice as 'paid'."""
        client_id = create_test_client(auth_client, app)
        invoice_id = create_test_invoice(
            auth_client, app, client_id, 'INV-FULL', 'sent', 30000
        )

        # Pay the full $300.00
        auth_client.post(
            f'/payments/invoice/{invoice_id}/new',
            data={
                'amount': '300.00',
                'payment_date': '2026-05-19',
                'method': 'card',
                'notes': 'Full payment'
            }
        )

        with app.app_context():
            with get_db() as db:
                invoice = db.execute(
                    "SELECT status FROM invoices WHERE id = ?", (invoice_id,)
                ).fetchone()
                assert invoice['status'] == 'paid'


class TestOverpayment:
    def test_overpayment_warning(self, auth_client, app):
        """WHEN a user records a payment exceeding invoice total
        THE SYSTEM SHALL mark as 'paid' and show overpayment warning."""
        client_id = create_test_client(auth_client, app)
        invoice_id = create_test_invoice(
            auth_client, app, client_id, 'INV-OVER', 'sent', 10000
        )

        # Pay $200 on a $100 invoice (overpayment)
        response = auth_client.post(
            f'/payments/invoice/{invoice_id}/new',
            data={
                'amount': '200.00',
                'payment_date': '2026-05-19',
                'method': 'check',
                'notes': 'Overpayment'
            },
            follow_redirects=True
        )

        # Should show overpayment warning
        assert b'Overpayment' in response.data or \
               b'overpayment' in response.data or \
               b'Warning' in response.data

        # Invoice should still be marked as paid
        with app.app_context():
            with get_db() as db:
                invoice = db.execute(
                    "SELECT status FROM invoices WHERE id = ?", (invoice_id,)
                ).fetchone()
                assert invoice['status'] == 'paid'
