import os
import tempfile

import pytest

from app import create_app


@pytest.fixture()
def app():
    """Create a test app with a temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    test_app = create_app(db_path=db_path)
    test_app.config["TESTING"] = True

    yield test_app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    """A Flask test client with session support."""
    return app.test_client()


@pytest.fixture()
def csrf_token(client):
    """Get a valid CSRF token by hitting any GET route first."""
    # A GET request initializes the session with a csrf_token
    client.get("/recipes/")
    with client.session_transaction() as sess:
        return sess["csrf_token"]
