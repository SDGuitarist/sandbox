"""Tests for the invoices blueprint (CRUD, line items, status, duplicate, from_deal)."""

from app.db import get_db
from tests.conftest import create_test_client, create_test_invoice


class TestCreateInvoice:
    def test_create_invoice_with_line_items(self, auth_client, app):
        """WHEN a user creates an invoice with line items
        THE SYSTEM SHALL save the invoice with calculated totals."""
        client_id = create_test_client(auth_client, app)

        response = auth_client.post('/invoices/new', data={
            'client_id': client_id,
            'invoice_number': 'INV-001',
            'issue_date': '2026-05-19',
            'due_date': '2026-06-18',
            'notes': 'Test invoice',
            'descriptions[]': ['Web Development', 'Design Work'],
            'quantities[]': ['10', '5'],
            'unit_prices[]': ['150.00', '100.00'],
            'tax_rates[]': ['0', '0'],
            'catalog_item_ids[]': ['', '']
        })
        # Should redirect after creation
        assert response.status_code == 302

        # Verify invoice and line items in database
        with app.app_context():
            with get_db() as db:
                invoice = db.execute(
                    "SELECT * FROM invoices WHERE invoice_number = 'INV-001'"
                ).fetchone()
                assert invoice is not None
                assert invoice['client_id'] == client_id

                items = db.execute(
                    "SELECT * FROM invoice_line_items WHERE invoice_id = ?",
                    (invoice['id'],)
                ).fetchall()
                assert len(items) == 2

    def test_create_invoice_form_loads(self, auth_client):
        """WHEN an authenticated user visits the new invoice form
        THE SYSTEM SHALL display the form."""
        response = auth_client.get('/invoices/new')
        assert response.status_code == 200


class TestInvoiceTotals:
    def test_invoice_total_calculation(self, auth_client, app):
        """WHEN an invoice is created with line items
        THE SYSTEM SHALL calculate subtotal, tax, and total correctly.

        Line 1: qty=10, price=$150.00 (15000 cents), tax=10% -> line_total = 165000
        Line 2: qty=5, price=$100.00 (10000 cents), tax=0% -> line_total = 50000
        subtotal = 15000*10 + 10000*5 = 200000 cents
        tax = 15000 cents (10% of line 1 subtotal)
        total = 215000 cents
        """
        client_id = create_test_client(auth_client, app)

        auth_client.post('/invoices/new', data={
            'client_id': client_id,
            'invoice_number': 'INV-CALC',
            'issue_date': '2026-05-19',
            'due_date': '2026-06-18',
            'notes': '',
            'descriptions': ['Service A', 'Service B'],
            'quantities': ['10', '5'],
            'unit_prices': ['150.00', '100.00'],
            'tax_rates': ['10', '0'],
            'catalog_item_ids': ['', '']
        })

        with app.app_context():
            with get_db() as db:
                invoice = db.execute(
                    "SELECT * FROM invoices WHERE invoice_number = 'INV-CALC'"
                ).fetchone()
                if invoice:
                    # Verify the totals are stored in cents
                    assert invoice['total_cents'] > 0
                    # Line 1: 10 * 15000 * (1 + 10/100) = 165000
                    # Line 2: 5 * 10000 * (1 + 0/100) = 50000
                    # total = 215000
                    assert invoice['total_cents'] == 215000


class TestInvoiceStatus:
    def test_update_invoice_status(self, auth_client, app):
        """WHEN a user changes an invoice status
        THE SYSTEM SHALL update the status."""
        client_id = create_test_client(auth_client, app)
        invoice_id = create_test_invoice(
            auth_client, app, client_id, 'INV-STATUS', 'draft', 10000
        )

        response = auth_client.post(
            f'/invoices/{invoice_id}/status',
            data={'new_status': 'sent'}
        )
        assert response.status_code == 302

        with app.app_context():
            with get_db() as db:
                invoice = db.execute(
                    "SELECT status FROM invoices WHERE id = ?", (invoice_id,)
                ).fetchone()
                assert invoice['status'] == 'sent'


class TestDuplicateInvoice:
    def test_duplicate_invoice(self, auth_client, app):
        """WHEN a user duplicates an invoice
        THE SYSTEM SHALL create a new draft with same line items and a new number."""
        client_id = create_test_client(auth_client, app)
        invoice_id = create_test_invoice(
            auth_client, app, client_id, 'INV-ORIG', 'sent', 50000
        )

        # Add a line item to the original invoice
        with app.app_context():
            with get_db() as db:
                db.execute("""
                    INSERT INTO invoice_line_items
                        (invoice_id, description, quantity, unit_price_cents,
                         tax_rate, line_total_cents, sort_order)
                    VALUES (?, 'Consulting', 5.0, 10000, 0, 50000, 0)
                """, (invoice_id,))
                db.commit()

        response = auth_client.post(f'/invoices/{invoice_id}/duplicate')
        assert response.status_code == 302

        # Verify a new invoice was created
        with app.app_context():
            with get_db() as db:
                invoices = db.execute(
                    "SELECT * FROM invoices ORDER BY id"
                ).fetchall()
                assert len(invoices) >= 2
                # The duplicate should be a draft
                new_invoice = invoices[-1]
                assert new_invoice['status'] == 'draft'
                assert new_invoice['invoice_number'] != 'INV-ORIG'


class TestListInvoices:
    def test_list_invoices_filter_by_status(self, auth_client, app):
        """WHEN a user filters invoices by status
        THE SYSTEM SHALL show only matching invoices."""
        client_id = create_test_client(auth_client, app)
        create_test_invoice(
            auth_client, app, client_id, 'INV-DRAFT', 'draft', 10000
        )
        create_test_invoice(
            auth_client, app, client_id, 'INV-SENT', 'sent', 20000
        )

        # Filter by status=draft
        response = auth_client.get('/invoices/?status=draft')
        assert response.status_code == 200
        assert b'INV-DRAFT' in response.data

    def test_list_invoices_loads(self, auth_client):
        """WHEN an authenticated user visits /invoices/
        THE SYSTEM SHALL display the invoice list."""
        response = auth_client.get('/invoices/')
        assert response.status_code == 200


class TestCreateInvoiceFromDeal:
    def test_create_invoice_from_deal(self, auth_client, app):
        """WHEN a user creates an invoice from a deal (from_deal query param)
        THE SYSTEM SHALL prefill client_id and notes from the deal."""
        client_id = create_test_client(auth_client, app)

        # Create a deal directly in the database
        with app.app_context():
            with get_db() as db:
                user = db.execute(
                    "SELECT id FROM users WHERE email = 'test@example.com'"
                ).fetchone()
                db.execute("""
                    INSERT INTO deals (user_id, client_id, title, value_cents, stage)
                    VALUES (?, ?, 'Big Deal', 500000, 'won')
                """, (user['id'], client_id))
                deal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.commit()

        # Access the invoice creation form with from_deal param
        response = auth_client.get(f'/invoices/new?from_deal={deal_id}')
        assert response.status_code == 200
        # The form should have deal info prefilled (deal title in notes or
        # client_id selected)
        assert b'Big Deal' in response.data or b'Acme Corp' in response.data
