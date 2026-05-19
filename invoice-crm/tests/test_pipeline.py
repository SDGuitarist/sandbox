"""Tests for the pipeline blueprint (deals, stages, kanban, deal-won redirect)."""

from app.db import get_db
from tests.conftest import create_test_client


class TestCreateDeal:
    def test_create_deal(self, auth_client, app):
        """WHEN a user creates a deal
        THE SYSTEM SHALL save it and redirect."""
        client_id = create_test_client(auth_client, app)

        response = auth_client.post('/pipeline/new', data={
            'title': 'Website Redesign',
            'client_id': client_id,
            'value': '5000.00',
            'stage': 'lead',
            'expected_close_date': '2026-06-30',
            'probability': '50',
            'notes': 'Potential big project'
        })
        assert response.status_code == 302

        # Verify deal exists
        with app.app_context():
            with get_db() as db:
                deal = db.execute(
                    "SELECT * FROM deals WHERE title = 'Website Redesign'"
                ).fetchone()
                assert deal is not None
                assert deal['value_cents'] == 500000  # $5000.00 = 500000 cents
                assert deal['stage'] == 'lead'

    def test_create_deal_form_loads(self, auth_client):
        """WHEN an authenticated user visits the new deal form
        THE SYSTEM SHALL display the form."""
        response = auth_client.get('/pipeline/new')
        assert response.status_code == 200


class TestMoveDealStage:
    def test_move_deal_stage(self, auth_client, app):
        """WHEN a user moves a deal to a new stage
        THE SYSTEM SHALL update the stage."""
        client_id = create_test_client(auth_client, app)

        # Create deal directly
        with app.app_context():
            with get_db() as db:
                user = db.execute(
                    "SELECT id FROM users WHERE email = 'test@example.com'"
                ).fetchone()
                db.execute("""
                    INSERT INTO deals (user_id, client_id, title, value_cents, stage)
                    VALUES (?, ?, 'Stage Test Deal', 100000, 'lead')
                """, (user['id'], client_id))
                deal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.commit()

        response = auth_client.post(
            f'/pipeline/{deal_id}/move',
            data={'new_stage': 'qualified'}
        )
        assert response.status_code == 302

        with app.app_context():
            with get_db() as db:
                deal = db.execute(
                    "SELECT stage FROM deals WHERE id = ?", (deal_id,)
                ).fetchone()
                assert deal['stage'] == 'qualified'


class TestDealWon:
    def test_deal_won_redirects_to_invoice(self, auth_client, app):
        """WHEN a deal is moved to 'won'
        THE SYSTEM SHALL redirect to invoice creation with from_deal param."""
        client_id = create_test_client(auth_client, app)

        with app.app_context():
            with get_db() as db:
                user = db.execute(
                    "SELECT id FROM users WHERE email = 'test@example.com'"
                ).fetchone()
                db.execute("""
                    INSERT INTO deals (user_id, client_id, title, value_cents, stage)
                    VALUES (?, ?, 'Won Deal', 200000, 'negotiation')
                """, (user['id'], client_id))
                deal_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.commit()

        response = auth_client.post(
            f'/pipeline/{deal_id}/move',
            data={'new_stage': 'won'}
        )
        assert response.status_code == 302
        location = response.headers.get('Location', '')
        # Should redirect to invoice creation with from_deal parameter
        assert 'invoices' in location.lower() or 'invoice' in location.lower()
        assert f'from_deal={deal_id}' in location or 'from_deal' in location


class TestKanbanView:
    def test_kanban_view(self, auth_client, app):
        """WHEN a user visits the pipeline page
        THE SYSTEM SHALL display the kanban view with deal stages."""
        # Create a deal so there's data to display
        client_id = create_test_client(auth_client, app)

        with app.app_context():
            with get_db() as db:
                user = db.execute(
                    "SELECT id FROM users WHERE email = 'test@example.com'"
                ).fetchone()
                db.execute("""
                    INSERT INTO deals (user_id, client_id, title, value_cents, stage)
                    VALUES (?, ?, 'Kanban Deal', 50000, 'proposal')
                """, (user['id'], client_id))
                db.commit()

        response = auth_client.get('/pipeline/')
        assert response.status_code == 200
        # Should contain stage names or deal info
        assert b'Kanban Deal' in response.data or \
               b'lead' in response.data.lower() or \
               b'proposal' in response.data.lower()
