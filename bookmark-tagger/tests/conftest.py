import os
import tempfile

import pytest

from app import create_app


@pytest.fixture
def app(monkeypatch):
    """Create app with a temporary database and monkeypatched fetch."""
    monkeypatch.setattr(
        'app.fetch_page_meta',
        lambda url: {'title': f'Title for {url}', 'description': f'Desc for {url}'},
    )
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    app = create_app(db_path=db_path)
    app.config['TESTING'] = True

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def add_bookmark(client, url='https://example.com', tags='', csrf_token=None):
    """Helper to add a bookmark via POST."""
    if csrf_token is None:
        # Get a CSRF token from a GET request
        resp = client.get('/')
        with client.session_transaction() as sess:
            csrf_token = sess['csrf_token']
    return client.post('/add', data={
        'url': url,
        'tags': tags,
        'csrf_token': csrf_token,
    }, follow_redirects=True)


def get_csrf(client):
    """Get a valid CSRF token."""
    client.get('/')
    with client.session_transaction() as sess:
        return sess['csrf_token']
