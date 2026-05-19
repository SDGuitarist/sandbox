"""Tests for the clients blueprint (CRUD operations)."""

from app.db import get_db
from tests.conftest import create_test_client


class TestListClients:
    def test_list_clients(self, auth_client):
        """WHEN an authenticated user visits /clients/
        THE SYSTEM SHALL display the client list."""
        response = auth_client.get('/clients/')
        assert response.status_code == 200

    def test_list_clients_requires_login(self, client):
        """WHEN an unauthenticated user visits /clients/
        THE SYSTEM SHALL redirect to login."""
        response = client.get('/clients/')
        assert response.status_code == 302
        assert 'login' in response.headers.get('Location', '').lower()


class TestCreateClient:
    def test_create_client(self, auth_client, app):
        """WHEN a user creates a client with valid data
        THE SYSTEM SHALL save the client and redirect."""
        response = auth_client.post('/clients/new', data={
            'name': 'Acme Corp',
            'email': 'acme@example.com',
            'phone': '555-0100',
            'company': 'Acme Corp',
            'address': '123 Main St',
            'notes': 'Great client',
            'status': 'active'
        })
        # Should redirect after creation
        assert response.status_code == 302

        # Verify client exists in database
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM clients WHERE name = 'Acme Corp'"
                ).fetchone()
                assert row is not None
                assert row['email'] == 'acme@example.com'

    def test_create_client_form_loads(self, auth_client):
        """WHEN an authenticated user visits the new client form
        THE SYSTEM SHALL display the form."""
        response = auth_client.get('/clients/new')
        assert response.status_code == 200


class TestViewClient:
    def test_view_client(self, auth_client, app):
        """WHEN a user views a client detail page
        THE SYSTEM SHALL display client information."""
        client_id = create_test_client(auth_client, app)
        response = auth_client.get(f'/clients/{client_id}')
        assert response.status_code == 200
        assert b'Acme Corp' in response.data


class TestEditClient:
    def test_edit_client(self, auth_client, app):
        """WHEN a user edits a client
        THE SYSTEM SHALL update the client and redirect."""
        client_id = create_test_client(auth_client, app)

        response = auth_client.post(f'/clients/{client_id}/edit', data={
            'name': 'Acme Corp Updated',
            'email': 'updated@example.com',
            'phone': '555-0200',
            'company': 'Acme Corp Updated',
            'address': '456 New St',
            'notes': 'Updated notes',
            'status': 'active'
        })
        assert response.status_code == 302

        # Verify update
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM clients WHERE id = ?", (client_id,)
                ).fetchone()
                assert row['name'] == 'Acme Corp Updated'
                assert row['email'] == 'updated@example.com'


class TestDeleteClient:
    def test_delete_client(self, auth_client, app):
        """WHEN a user deletes a client
        THE SYSTEM SHALL remove it and redirect."""
        client_id = create_test_client(auth_client, app)

        response = auth_client.post(f'/clients/{client_id}/delete')
        assert response.status_code == 302

        # Verify deletion
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM clients WHERE id = ?", (client_id,)
                ).fetchone()
                assert row is None
