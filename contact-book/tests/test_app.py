import os
import sys
import tempfile
import sqlite3
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, get_db


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'test_contacts.db')
    monkeypatch.chdir(tmp_path)

    models_src = os.path.join(os.path.dirname(__file__), '..')
    sys.path.insert(0, models_src)

    app = create_app()
    app.config['TESTING'] = True
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def get_csrf_token(client):
    with client.session_transaction() as sess:
        import secrets
        token = secrets.token_hex(32)
        sess['_csrf_token'] = token
    return token


def test_index(client):
    response = client.get('/')
    assert response.status_code == 200


def test_add_form(client):
    response = client.get('/add')
    assert response.status_code == 200


def test_add_contact(client):
    token = get_csrf_token(client)
    response = client.post('/add', data={
        'name': 'Alice',
        'email': 'alice@example.com',
        'phone': '555-0100',
        'notes': 'Friend',
        '_csrf_token': token,
    })
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/')

    response = client.get('/')
    assert b'Alice' in response.data


def test_edit_form(client):
    token = get_csrf_token(client)
    client.post('/add', data={
        'name': 'Bob',
        'email': 'bob@example.com',
        'phone': '555-0200',
        'notes': '',
        '_csrf_token': token,
    })

    response = client.get('/edit/1')
    assert response.status_code == 200
    assert b'Bob' in response.data


def test_edit_contact(client):
    token = get_csrf_token(client)
    client.post('/add', data={
        'name': 'Charlie',
        'email': 'charlie@example.com',
        'phone': '555-0300',
        'notes': '',
        '_csrf_token': token,
    })

    token = get_csrf_token(client)
    response = client.post('/edit/1', data={
        'name': 'Charlie Updated',
        'email': 'charlie_new@example.com',
        'phone': '555-0301',
        'notes': 'Updated',
        '_csrf_token': token,
    })
    assert response.status_code == 302

    response = client.get('/')
    assert b'Charlie Updated' in response.data


def test_delete_contact(client):
    token = get_csrf_token(client)
    client.post('/add', data={
        'name': 'Dave',
        'email': 'dave@example.com',
        'phone': '555-0400',
        'notes': '',
        '_csrf_token': token,
    })

    response = client.get('/')
    assert b'Dave' in response.data

    token = get_csrf_token(client)
    response = client.post('/delete/1', data={
        '_csrf_token': token,
    })
    assert response.status_code == 302

    response = client.get('/')
    assert b'Dave' not in response.data


def test_csrf_rejection(client):
    response = client.post('/add', data={
        'name': 'Eve',
        'email': 'eve@example.com',
        'phone': '555-0500',
        'notes': '',
    })
    assert response.status_code == 403
