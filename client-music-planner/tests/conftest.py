"""Shared fixtures for the Client Music Planner test suite."""

import os
import tempfile
import secrets

import pytest

from app import create_app
from app.db import get_db, init_db


@pytest.fixture()
def app():
    """Create a Flask application configured for testing.

    Uses a temporary file for the SQLite database so each test gets a
    clean slate.  The database schema is applied automatically via
    init_db (called inside create_app -> init_app).
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    app = create_app()
    app.config.update(
        TESTING=True,
        DATABASE=db_path,
        WTF_CSRF_ENABLED=False,  # disable CSRF for test form submissions
        SECRET_KEY="test-secret-key",
    )

    # Re-initialise the database with our temp path now that config is
    # updated (create_app already ran init_db against the default path).
    with app.app_context():
        init_db()

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def client(app):
    """A Flask test client for sending requests."""
    return app.test_client()


@pytest.fixture()
def runner(app):
    """A Flask CLI test runner."""
    return app.test_cli_runner()


# ------------------------------------------------------------------
# Helper: create a test user and log them in
# ------------------------------------------------------------------

def _register_user(client, email="musician@test.com", password="TestPass123!",
                   confirm_password=None, display_name="Test Musician"):
    """Register a user via the auth form using EXACT spec field names."""
    if confirm_password is None:
        confirm_password = password
    return client.post("/auth/register", data={
        "email": email,
        "password": password,
        "confirm_password": confirm_password,
        "display_name": display_name,
    }, follow_redirects=True)


def _login_user(client, email="musician@test.com", password="TestPass123!"):
    """Log in a user via the auth form using EXACT spec field names."""
    return client.post("/auth/login", data={
        "email": email,
        "password": password,
    }, follow_redirects=True)


@pytest.fixture()
def auth_client(client):
    """A test client that is already registered and logged in."""
    _register_user(client)
    _login_user(client)
    return client


# ------------------------------------------------------------------
# Helper: create a song for the logged-in user
# ------------------------------------------------------------------

def _create_song(client, title="Wonderwall", artist="Oasis", genre="rock",
                 musical_key="C", tempo="120", energy="3",
                 duration_seconds="240", notes=""):
    """Create a song via the repertoire form using EXACT spec field names."""
    return client.post("/repertoire/new", data={
        "title": title,
        "artist": artist,
        "genre": genre,
        "musical_key": musical_key,
        "tempo": tempo,
        "energy": energy,
        "duration_seconds": duration_seconds,
        "notes": notes,
    }, follow_redirects=True)


# ------------------------------------------------------------------
# Helper: create an event for the logged-in user
# ------------------------------------------------------------------

def _create_event(client, name="Smith Wedding", event_date="2026-07-15",
                  event_type="wedding", venue="Grand Hall",
                  client_name="John Smith", client_email="john@example.com",
                  notes=""):
    """Create an event via the events form using EXACT spec field names."""
    return client.post("/events/new", data={
        "name": name,
        "event_date": event_date,
        "event_type": event_type,
        "venue": venue,
        "client_name": client_name,
        "client_email": client_email,
        "notes": notes,
    }, follow_redirects=True)


# ------------------------------------------------------------------
# Helper: get portal token for the most recent event
# ------------------------------------------------------------------

def _get_portal_token(app):
    """Read the portal_token of the first event from the database."""
    with app.app_context():
        with get_db() as db:
            row = db.execute(
                "SELECT portal_token FROM event ORDER BY id DESC LIMIT 1"
            ).fetchone()
    return row["portal_token"] if row else None


# ------------------------------------------------------------------
# Helper: create event + get portal token in one step
# ------------------------------------------------------------------

@pytest.fixture()
def portal_event(app, auth_client):
    """Create an event and return (client, token) for portal tests.

    Also creates a song so portal browsing has content.
    """
    _create_song(auth_client, title="Bohemian Rhapsody", artist="Queen",
                 genre="rock", energy="5")
    _create_song(auth_client, title="Fly Me to the Moon", artist="Sinatra",
                 genre="jazz", energy="2")
    _create_event(auth_client)
    token = _get_portal_token(app)
    return auth_client, token


# ------------------------------------------------------------------
# Helper: add a song to the portal playlist
# ------------------------------------------------------------------

def _portal_add_to_playlist(client, token, song_id, client_note=""):
    """Add a song to the portal playlist using EXACT spec field names."""
    return client.post(f"/portal/{token}/playlist/add", data={
        "song_id": song_id,
        "client_note": client_note,
    }, follow_redirects=True)


# ------------------------------------------------------------------
# Helper: get song IDs from the database
# ------------------------------------------------------------------

def _get_song_ids(app):
    """Return a list of all song IDs."""
    with app.app_context():
        with get_db() as db:
            rows = db.execute("SELECT id FROM song ORDER BY id").fetchall()
    return [r["id"] for r in rows]


# ------------------------------------------------------------------
# Helper: get playlist item IDs for an event
# ------------------------------------------------------------------

def _get_playlist_item_ids(app, event_id):
    """Return playlist item IDs ordered by position."""
    with app.app_context():
        with get_db() as db:
            rows = db.execute(
                "SELECT id FROM playlist_item WHERE event_id = ? ORDER BY position",
                (event_id,)
            ).fetchall()
    return [r["id"] for r in rows]


# ------------------------------------------------------------------
# Helper: get event ID from token
# ------------------------------------------------------------------

def _get_event_id(app, token):
    """Return the event ID for a given portal token."""
    with app.app_context():
        with get_db() as db:
            row = db.execute(
                "SELECT id FROM event WHERE portal_token = ?", (token,)
            ).fetchone()
    return row["id"] if row else None
