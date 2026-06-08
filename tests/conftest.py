"""Pytest fixtures for the Film Production PM Tool.

Provides a freshly-seeded app on a temporary on-disk SQLite database (never
:memory: -- a per-request connection model means an in-memory DB would not
persist seed data across requests), a test client, and authentication helpers.
"""
import os
import re
import tempfile

import pytest

# Secrets must be set BEFORE importing the app factory -- create_app() reads
# SECRET_KEY at call time and seed_data() reads ADMIN_PASSWORD during init_db().
ADMIN_PASSWORD = "test-strong-pw-123"
os.environ.setdefault("SECRET_KEY", "test-conftest-key-not-production")
os.environ.setdefault("ADMIN_PASSWORD", ADMIN_PASSWORD)


@pytest.fixture
def app():
    """Create the Flask app bound to a clean temporary database.

    FC49: never use ':memory:'. Allocate a temp file path, delete it, and let
    init_app() detect the missing file and run init_db() (schema + seed) against
    that clean path.
    """
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(db_path)

    os.environ["DATABASE"] = db_path
    os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", "test-conftest-key-not-production")
    os.environ["ADMIN_PASSWORD"] = ADMIN_PASSWORD

    from app import create_app

    application = create_app()
    application.config["TESTING"] = True
    application.config["DATABASE"] = db_path

    yield application

    for path in (db_path, db_path + "-wal", db_path + "-shm"):
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture
def client(app):
    """A test client for the seeded app."""
    return app.test_client()


def _csrf_token(client):
    """Fetch the login page and extract the rendered CSRF token.

    Exercises that ``{{ csrf_token() }}`` actually renders in the template.
    """
    resp = client.get("/auth/login")
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp.data.decode())
    assert match is not None, "csrf_token input not found on login page"
    return match.group(1)


def _login(client, username, password):
    """Log in via the real login form with a valid CSRF token."""
    token = _csrf_token(client)
    return client.post(
        "/auth/login",
        data={"username": username, "password": password, "csrf_token": token},
        follow_redirects=False,
    )


@pytest.fixture
def csrf_token(client):
    """The CSRF token rendered on the login page (a callable per fresh page load)."""
    return lambda: _csrf_token(client)


@pytest.fixture
def auth(client):
    """Authentication helper bound to the test client.

    Usage:
        auth.login()                      # log in as the seeded producer
        auth.login("dept_head", "pw")     # log in as another user
        auth.logout()
        auth.csrf()                       # current login-page CSRF token
    """

    class AuthActions:
        def login(self, username="producer", password=ADMIN_PASSWORD):
            return _login(client, username, password)

        def logout(self):
            token = _csrf_token(client)
            return client.post(
                "/auth/logout",
                data={"csrf_token": token},
                follow_redirects=False,
            )

        def csrf(self):
            return _csrf_token(client)

    return AuthActions()
