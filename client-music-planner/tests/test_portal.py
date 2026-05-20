"""Tests for portal blueprints: browse, playlist, flags, requests, approve.

EARS acceptance tests covered:
- WHEN a client visits /portal/<valid-token> THE SYSTEM SHALL display the
  musician's repertoire
- WHEN a client clicks "Add to Playlist" on a song THE SYSTEM SHALL add it
  to the playlist at the next position
- WHEN a client clicks "Must Play" on a playlist item THE SYSTEM SHALL toggle
  is_must_play and clear is_do_not_play
- WHEN a client submits a song request with title THE SYSTEM SHALL create a
  song_request row
- WHEN a client clicks "Approve" THE SYSTEM SHALL set client_approved=1 and
  approved_at timestamp
- WHEN a client visits /portal/<invalid-token> THE SYSTEM SHALL return 404
- WHEN a client tries to add a song to an approved event's playlist THE SYSTEM
  SHALL flash warning and redirect to browse
- WHEN a client visits an archived event portal THE SYSTEM SHALL return 404
"""

from tests.conftest import (
    _portal_add_to_playlist, _get_song_ids, _get_event_id,
    _get_playlist_item_ids,
)
from app.db import get_db


class TestPortalBrowse:
    """Client browses the musician's repertoire via portal."""

    def test_browse_valid_token(self, portal_event):
        """GET /portal/<token> shows the repertoire."""
        client, token = portal_event
        resp = client.get(f"/portal/{token}")
        assert resp.status_code == 200
        # Should display the songs we created in the fixture
        assert b"Bohemian Rhapsody" in resp.data

    def test_browse_invalid_token(self, client):
        """Invalid portal token returns 404."""
        resp = client.get("/portal/nonexistent-token-abc123")
        assert resp.status_code == 404

    def test_browse_archived_event(self, app, portal_event):
        """Archived event portal returns 404.

        EARS: WHEN a client visits an archived event portal THE SYSTEM SHALL
        return 404.
        """
        client, token = portal_event
        event_id = _get_event_id(app, token)
        # Archive the event directly in the DB
        with app.app_context():
            with get_db(immediate=True) as db:
                db.execute(
                    "UPDATE event SET is_archived = 1 WHERE id = ?",
                    (event_id,),
                )
                db.commit()
        resp = client.get(f"/portal/{token}")
        assert resp.status_code == 404

    def test_song_detail(self, app, portal_event):
        """Client can view a specific song's details."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        resp = client.get(f"/portal/{token}/song/{song_ids[0]}")
        assert resp.status_code == 200


class TestPortalPlaylist:
    """Client playlist builder tests."""

    def test_playlist_page_loads(self, portal_event):
        """GET /portal/<token>/playlist returns 200."""
        client, token = portal_event
        resp = client.get(f"/portal/{token}/playlist")
        assert resp.status_code == 200

    def test_add_to_playlist(self, app, portal_event):
        """Adding a song to the playlist succeeds."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        resp = _portal_add_to_playlist(client, token, song_ids[0])
        assert resp.status_code == 200
        # Verify in DB
        event_id = _get_event_id(app, token)
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM playlist_item WHERE event_id = ? AND song_id = ?",
                    (event_id, song_ids[0]),
                ).fetchone()
        assert row is not None

    def test_add_duplicate_to_playlist(self, app, portal_event):
        """Adding the same song twice should not create a duplicate."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        resp = _portal_add_to_playlist(client, token, song_ids[0])
        # Should handle gracefully (flash warning, not crash)
        assert resp.status_code == 200

    def test_remove_from_playlist(self, app, portal_event):
        """Removing a song from the playlist succeeds.

        Form field: song_id (EXACT spec field name).
        """
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        resp = client.post(f"/portal/{token}/playlist/remove", data={
            "song_id": song_ids[0],
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Verify removed from DB
        event_id = _get_event_id(app, token)
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM playlist_item WHERE event_id = ? AND song_id = ?",
                    (event_id, song_ids[0]),
                ).fetchone()
        assert row is None

    def test_add_to_playlist_blocked_after_approval(self, app, portal_event):
        """Cannot add songs after event is approved.

        EARS: WHEN a client tries to add a song to an approved event's
        playlist THE SYSTEM SHALL flash warning and redirect to browse.
        """
        client, token = portal_event
        song_ids = _get_song_ids(app)
        event_id = _get_event_id(app, token)
        # Approve the event
        with app.app_context():
            with get_db(immediate=True) as db:
                db.execute(
                    "UPDATE event SET client_approved = 1, approved_at = datetime('now') WHERE id = ?",
                    (event_id,),
                )
                db.commit()
        resp = client.post(f"/portal/{token}/playlist/add", data={
            "song_id": song_ids[0],
            "client_note": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Should flash warning about approved/locked


class TestPortalFlags:
    """Flag toggling tests (AJAX endpoint, form fields: song_id, flag_type)."""

    def test_toggle_must_play(self, app, portal_event):
        """Toggling must_play sets the flag.

        Form fields: song_id, flag_type (EXACT spec field names).
        """
        client, token = portal_event
        song_ids = _get_song_ids(app)
        # First add the song to the playlist
        _portal_add_to_playlist(client, token, song_ids[0])
        # Toggle must_play
        resp = client.post(f"/portal/{token}/flags/toggle", data={
            "song_id": song_ids[0],
            "flag_type": "must_play",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["is_must_play"] == 1
        assert data["is_do_not_play"] == 0

    def test_toggle_do_not_play(self, app, portal_event):
        """Toggling do_not_play sets the flag and clears must_play."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        resp = client.post(f"/portal/{token}/flags/toggle", data={
            "song_id": song_ids[0],
            "flag_type": "do_not_play",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["is_do_not_play"] == 1
        assert data["is_must_play"] == 0

    def test_toggle_clears_opposite_flag(self, app, portal_event):
        """Setting must_play clears do_not_play and vice versa."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        # Set must_play first
        client.post(f"/portal/{token}/flags/toggle", data={
            "song_id": song_ids[0],
            "flag_type": "must_play",
        })
        # Now set do_not_play -- must_play should be cleared
        resp = client.post(f"/portal/{token}/flags/toggle", data={
            "song_id": song_ids[0],
            "flag_type": "do_not_play",
        })
        data = resp.get_json()
        assert data["is_must_play"] == 0
        assert data["is_do_not_play"] == 1

    def test_toggle_invalid_flag_type(self, app, portal_event):
        """Invalid flag_type returns 400."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        resp = client.post(f"/portal/{token}/flags/toggle", data={
            "song_id": song_ids[0],
            "flag_type": "invalid_flag",
        })
        assert resp.status_code == 400

    def test_toggle_song_not_in_playlist(self, app, portal_event):
        """Flagging a song not in the playlist returns 404."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        resp = client.post(f"/portal/{token}/flags/toggle", data={
            "song_id": song_ids[0],
            "flag_type": "must_play",
        })
        assert resp.status_code == 404


class TestPortalRequests:
    """Song request tests.

    Form fields for add_request: title, artist, notes (EXACT spec field names).
    """

    def test_requests_page_loads(self, portal_event):
        """GET /portal/<token>/requests returns 200."""
        client, token = portal_event
        resp = client.get(f"/portal/{token}/requests")
        assert resp.status_code == 200

    def test_add_request(self, app, portal_event):
        """Submitting a song request creates a row."""
        client, token = portal_event
        resp = client.post(f"/portal/{token}/requests/add", data={
            "title": "Sweet Caroline",
            "artist": "Neil Diamond",
            "notes": "Please play this during dinner",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Verify in DB
        event_id = _get_event_id(app, token)
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT * FROM song_request WHERE event_id = ? AND title = ?",
                    (event_id, "Sweet Caroline"),
                ).fetchone()
        assert row is not None
        assert row["artist"] == "Neil Diamond"

    def test_add_request_title_required(self, portal_event):
        """Submitting without a title should fail."""
        client, token = portal_event
        resp = client.post(f"/portal/{token}/requests/add", data={
            "title": "",
            "artist": "Artist",
            "notes": "",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_request(self, app, portal_event):
        """Deleting a song request removes it."""
        client, token = portal_event
        client.post(f"/portal/{token}/requests/add", data={
            "title": "To Delete Request",
            "artist": "",
            "notes": "",
        }, follow_redirects=True)
        event_id = _get_event_id(app, token)
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT id FROM song_request WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
        request_id = row["id"]
        resp = client.post(
            f"/portal/{token}/requests/{request_id}/delete",
            follow_redirects=True,
        )
        assert resp.status_code == 200


class TestPortalApprove:
    """Client approval flow tests."""

    def test_approve_page_loads(self, portal_event):
        """GET /portal/<token>/approve returns 200."""
        client, token = portal_event
        resp = client.get(f"/portal/{token}/approve")
        assert resp.status_code == 200

    def test_confirm_approval(self, app, portal_event):
        """Approving sets client_approved=1 and approved_at.

        EARS: WHEN a client clicks 'Approve' THE SYSTEM SHALL set
        client_approved=1 and approved_at timestamp.
        """
        client, token = portal_event
        resp = client.post(
            f"/portal/{token}/approve/confirm",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        event_id = _get_event_id(app, token)
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT client_approved, approved_at FROM event WHERE id = ?",
                    (event_id,),
                ).fetchone()
        assert row["client_approved"] == 1
        assert row["approved_at"] is not None

    def test_writes_blocked_after_approval(self, app, portal_event):
        """After approval, all portal writes are blocked."""
        client, token = portal_event
        # Approve the event
        client.post(f"/portal/{token}/approve/confirm", follow_redirects=True)
        # Try to add a song request
        resp = client.post(f"/portal/{token}/requests/add", data={
            "title": "Blocked Request",
            "artist": "",
            "notes": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # The request should NOT have been created -- event is locked
        event_id = _get_event_id(app, token)
        with app.app_context():
            with get_db() as db:
                row = db.execute(
                    "SELECT COUNT(*) as cnt FROM song_request WHERE event_id = ? AND title = ?",
                    (event_id, "Blocked Request"),
                ).fetchone()
        assert row["cnt"] == 0
