import os
import tempfile

import pytest

from app import create_app
from app.db import init_db, get_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    app = create_app()
    app.config['DATABASE'] = db_path
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # disable CSRF for tests

    with app.app_context():
        init_db()

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client, app):
    """A test client that is already logged in."""
    # Register
    client.post('/auth/register', data={
        'email': 'test@example.com',
        'password': 'testpass123',
        'confirm_password': 'testpass123'
    })
    # Login
    client.post('/auth/login', data={
        'email': 'test@example.com',
        'password': 'testpass123'
    })
    return client


def create_test_client(auth_client, app, name='Acme Corp', email='acme@example.com'):
    """Helper to create a client and return its ID."""
    auth_client.post('/clients/new', data={
        'name': name,
        'email': email,
        'phone': '555-0100',
        'company': name,
        'address': '123 Main St',
        'notes': 'Test client',
        'status': 'active'
    })
    with app.app_context():
        with get_db() as db:
            row = db.execute(
                "SELECT id FROM clients WHERE name = ? ORDER BY id DESC LIMIT 1",
                (name,)
            ).fetchone()
            return row['id']


def create_test_invoice(auth_client, app, client_id, invoice_number='INV-001',
                        status='draft', total_cents=10000):
    """Helper to insert an invoice directly into the database."""
    with app.app_context():
        with get_db() as db:
            db.execute("SELECT id FROM users WHERE email = 'test@example.com'")
            user = db.execute(
                "SELECT id FROM users WHERE email = 'test@example.com'"
            ).fetchone()
            user_id = user['id']
            db.execute("""
                INSERT INTO invoices
                    (user_id, client_id, invoice_number, status, issue_date,
                     due_date, subtotal_cents, tax_cents, total_cents, notes)
                VALUES (?, ?, ?, ?, date('now'), date('now', '+30 days'),
                        ?, 0, ?, '')
            """, (user_id, client_id, invoice_number, status,
                  total_cents, total_cents))
            invoice_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.commit()
            return invoice_id
