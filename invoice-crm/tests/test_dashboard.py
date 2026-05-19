"""Tests for the dashboard blueprint (loads, overdue, recurring, login required)."""

from app.db import get_db
from tests.conftest import create_test_client


class TestDashboardLoads:
    def test_dashboard_loads(self, auth_client):
        """WHEN an authenticated user visits the dashboard
        THE SYSTEM SHALL display the main dashboard page."""
        response = auth_client.get('/')
        assert response.status_code == 200

    def test_dashboard_requires_login(self, client):
        """WHEN an unauthenticated user visits the dashboard
        THE SYSTEM SHALL redirect to login."""
        response = client.get('/')
        assert response.status_code == 302
        assert 'login' in response.headers.get('Location', '').lower()


class TestOverdueDetection:
    def test_overdue_detection(self, auth_client, app):
        """WHEN an invoice is past due date with status 'sent'
        THE SYSTEM SHALL mark as 'overdue' on dashboard load."""
        client_id = create_test_client(auth_client, app)

        # Create an invoice with a past due date and 'sent' status
        with app.app_context():
            with get_db() as db:
                user = db.execute(
                    "SELECT id FROM users WHERE email = 'test@example.com'"
                ).fetchone()
                db.execute("""
                    INSERT INTO invoices
                        (user_id, client_id, invoice_number, status,
                         issue_date, due_date, subtotal_cents, tax_cents,
                         total_cents, notes)
                    VALUES (?, ?, 'INV-OVERDUE', 'sent',
                            '2026-01-01', '2026-01-15', 10000, 0, 10000, '')
                """, (user['id'], client_id))
                db.commit()

        # Visit dashboard -- this should trigger overdue detection
        auth_client.get('/')

        # Verify the invoice status was updated to 'overdue'
        with app.app_context():
            with get_db() as db:
                invoice = db.execute(
                    "SELECT status FROM invoices WHERE invoice_number = 'INV-OVERDUE'"
                ).fetchone()
                assert invoice['status'] == 'overdue'


class TestRecurringGeneration:
    def test_recurring_generation(self, auth_client, app):
        """WHEN a recurring invoice is due today or earlier
        THE SYSTEM SHALL generate a new draft invoice on dashboard load."""
        client_id = create_test_client(auth_client, app)

        # Create a recurring invoice that is due for generation
        with app.app_context():
            with get_db() as db:
                user = db.execute(
                    "SELECT id FROM users WHERE email = 'test@example.com'"
                ).fetchone()
                db.execute("""
                    INSERT INTO invoices
                        (user_id, client_id, invoice_number, status,
                         issue_date, due_date, subtotal_cents, tax_cents,
                         total_cents, notes, is_recurring,
                         recurrence_interval, next_recurrence_date)
                    VALUES (?, ?, 'INV-REC', 'sent',
                            '2026-01-01', '2026-01-31', 25000, 0, 25000,
                            'Monthly service', 1, 'monthly', '2026-01-01')
                """, (user['id'], client_id))

                # Add a line item to the parent invoice
                parent_id = db.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]
                db.execute("""
                    INSERT INTO invoice_line_items
                        (invoice_id, description, quantity, unit_price_cents,
                         tax_rate, line_total_cents, sort_order)
                    VALUES (?, 'Monthly Retainer', 1.0, 25000, 0, 25000, 0)
                """, (parent_id,))
                db.commit()

        # Visit dashboard -- should trigger recurring generation
        response = auth_client.get('/')
        assert response.status_code == 200

        # Verify a new child invoice was generated
        with app.app_context():
            with get_db() as db:
                child = db.execute(
                    "SELECT * FROM invoices WHERE parent_invoice_id IS NOT NULL"
                ).fetchone()
                assert child is not None
                assert child['status'] == 'draft'
                assert child['total_cents'] == 25000

                # Verify the parent's next_recurrence_date was advanced
                parent = db.execute(
                    "SELECT next_recurrence_date FROM invoices "
                    "WHERE invoice_number = 'INV-REC'"
                ).fetchone()
                assert parent['next_recurrence_date'] != '2026-01-01'

    def test_recurring_not_generated_for_draft(self, auth_client, app):
        """WHEN a recurring invoice has status 'draft'
        THE SYSTEM SHALL NOT generate a child invoice."""
        client_id = create_test_client(auth_client, app)

        # Create a recurring invoice that is draft (should NOT generate)
        with app.app_context():
            with get_db() as db:
                user = db.execute(
                    "SELECT id FROM users WHERE email = 'test@example.com'"
                ).fetchone()
                db.execute("""
                    INSERT INTO invoices
                        (user_id, client_id, invoice_number, status,
                         issue_date, due_date, subtotal_cents, tax_cents,
                         total_cents, notes, is_recurring,
                         recurrence_interval, next_recurrence_date)
                    VALUES (?, ?, 'INV-DRAFT-REC', 'draft',
                            '2026-01-01', '2026-01-31', 10000, 0, 10000,
                            'Draft recurring', 1, 'monthly', '2026-01-01')
                """, (user['id'], client_id))
                db.commit()

        # Visit dashboard
        auth_client.get('/')

        # No child should be generated from a draft recurring invoice
        with app.app_context():
            with get_db() as db:
                children = db.execute("""
                    SELECT * FROM invoices
                    WHERE parent_invoice_id = (
                        SELECT id FROM invoices
                        WHERE invoice_number = 'INV-DRAFT-REC'
                    )
                """).fetchall()
                assert len(children) == 0
