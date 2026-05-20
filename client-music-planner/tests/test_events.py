"""Tests for events blueprint: event CRUD, token, archive.

EARS acceptance tests covered:
- WHEN a musician creates an event with name/date/client_name THE SYSTEM SHALL
  generate a portal_token and show the shareable link
- WHEN a musician tries to access another musician's event THE SYSTEM SHALL
  return 404
"""

from tests.conftest import (
    _create_event, _get_portal_token, _get_event_id,
    _register_user, _login_user,
)
from app.db import get_db


class TestEventIndex:
    """Event list page tests."""

    def test_index_requires_login(self, client):
        """GET /events/ without login redirects."""
        resp = client.get("/events/")
        assert resp.status_code == 302

    def test_index_empty(self, auth_client):
        """Event index loads with no events."""
        resp = auth_client.get("/events/")
        assert resp.status_code == 200

    def test_index_shows_events(self, auth_client):
        """After creating an event, it appears on the index."""
        _create_event(auth_client, name="Johnson Birthday")
        resp = auth_client.get("/events/")
        assert resp.status_code == 200
        assert b"Johnson Birthday" in resp.data


class TestEventCreate:
    """Event creation tests."""

    def test_create_form_loads(self, auth_client):
        """GET /events/new returns the form."""
        resp = auth_client.get("/events/new")
        assert resp.status_code == 200

    def test_create_happy_path(self, app, auth_client):
        """Creating an event generates a portal token."""
        resp = _create_event(
            auth_client,
            name="Davis Corporate Gala",
            event_date="2026-09-20",
            event_type="corporate",
            venue="Hilton Ballroom",
            client_name="Sarah Davis",
            client_email="sarah@corp.com",
            notes="300 guests expected",
        )
        assert resp.status_code == 200

        # Verify a portal token was generated
        token = _get_portal_token(app)
        assert token is not None
        assert len(token) > 0

    def test_create_missing_name(self, auth_client):
        """Creating an event without a name should fail."""
        resp = _create_event(auth_client, name="")
        assert resp.status_code == 200

    def test_create_missing_client_name(self, auth_client):
        """Creating an event without client_name should fail."""
        resp = _create_event(auth_client, client_name="")
        assert resp.status_code == 200


class TestEventDetail:
    """Event detail view tests."""

    def test_detail_page(self, app, auth_client):
        """Event detail shows the event and portal link."""
        _create_event(auth_client, name="Detail Test Event")
        token = _get_portal_token(app)
        event_id = _get_event_id(app, token)
        resp = auth_client.get(f"/events/{event_id}")
        assert resp.status_code == 200
        assert b"Detail Test Event" in resp.data
        # Portal link should be visible
        assert token.encode() in resp.data

    def test_detail_nonexistent(self, auth_client):
        """Requesting a nonexistent event returns 404."""
        resp = auth_client.get("/events/99999")
        assert resp.status_code == 404


class TestEventEdit:
    """Event edit tests."""

    def test_edit_form_loads(self, app, auth_client):
        """GET /events/<id>/edit loads the form."""
        _create_event(auth_client, name="Edit Me")
        token = _get_portal_token(app)
        event_id = _get_event_id(app, token)
        resp = auth_client.get(f"/events/{event_id}/edit")
        assert resp.status_code == 200

    def test_edit_happy_path(self, app, auth_client):
        """Editing an event updates it."""
        _create_event(auth_client, name="Old Name")
        token = _get_portal_token(app)
        event_id = _get_event_id(app, token)
        resp = auth_client.post(f"/events/{event_id}/edit", data={
            "name": "New Name",
            "event_date": "2026-08-01",
            "event_type": "birthday",
            "venue": "New Venue",
            "client_name": "New Client",
            "client_email": "new@example.com",
            "notes": "Updated",
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestEventDelete:
    """Event deletion tests."""

    def test_delete_event(self, app, auth_client):
        """Deleting an event removes it."""
        _create_event(auth_client, name="To Delete")
        token = _get_portal_token(app)
        event_id = _get_event_id(app, token)
        resp = auth_client.post(
            f"/events/{event_id}/delete",
            follow_redirects=True,
        )
        assert resp.status_code == 200


class TestRegenerateToken:
    """Portal token regeneration tests."""

    def test_regenerate_token(self, app, auth_client):
        """Regenerating the token changes it."""
        _create_event(auth_client)
        old_token = _get_portal_token(app)
        event_id = _get_event_id(app, old_token)
        resp = auth_client.post(
            f"/events/{event_id}/regenerate-token",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        new_token = _get_portal_token(app)
        assert new_token != old_token


class TestArchive:
    """Event archive toggle tests."""

    def test_archive_toggle(self, app, auth_client):
        """Archiving an event sets is_archived."""
        _create_event(auth_client)
        token = _get_portal_token(app)
        event_id = _get_event_id(app, token)
        resp = auth_client.post(
            f"/events/{event_id}/archive",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Verify archived in DB
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT is_archived FROM event WHERE id = ?", (event_id,)
                ).fetchone()
        assert row["is_archived"] == 1


class TestEventOwnership:
    """Events are scoped to the user who created them.

    EARS: WHEN a musician tries to access another musician's event THE SYSTEM
    SHALL return 404.
    """

    def test_cannot_view_other_users_event(self, app, client):
        """User B cannot view User A's events."""
        # User A creates an event
        _register_user(client, email="eventa@test.com", display_name="Ev A")
        _create_event(client, name="User A Event")
        token = _get_portal_token(app)
        event_id = _get_event_id(app, token)
        client.post("/auth/logout", follow_redirects=True)

        # User B tries to access it
        _register_user(client, email="eventb@test.com", display_name="Ev B")
        resp = client.get(f"/events/{event_id}")
        assert resp.status_code == 404
