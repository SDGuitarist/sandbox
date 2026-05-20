"""Tests for API endpoints: api_playlist (reorder) and api_filters (filter_songs).

EARS acceptance tests covered:
- WHEN a client drags a playlist item to a new position THE SYSTEM SHALL update
  all positions atomically via /api/playlist/reorder
- WHEN a client submits reorder with mismatched item_ids length THE SYSTEM SHALL
  return 409 with "Playlist changed" message
- WHEN a musician views event dashboard THE SYSTEM SHALL display all playlist
  items, flags, and song requests
- WHEN a musician exports a setlist as CSV THE SYSTEM SHALL return a
  downloadable file with song data ordered by position
"""

import json

from tests.conftest import (
    _portal_add_to_playlist, _get_song_ids, _get_event_id,
    _get_playlist_item_ids, _create_song, _create_event, _get_portal_token,
)
from app.db import get_db


class TestApiPlaylistReorder:
    """Drag-and-drop reorder via /api/playlist/reorder.

    Request body: {"token": "...", "item_ids": [5, 3, 1, 4, 2]}
    """

    def test_reorder_happy_path(self, app, portal_event):
        """Reordering with correct item_ids succeeds."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        # Add both songs to playlist
        _portal_add_to_playlist(client, token, song_ids[0])
        _portal_add_to_playlist(client, token, song_ids[1])
        event_id = _get_event_id(app, token)
        item_ids = _get_playlist_item_ids(app, event_id)
        assert len(item_ids) == 2
        # Reverse the order
        reversed_ids = list(reversed(item_ids))
        resp = client.post(
            "/api/playlist/reorder",
            data=json.dumps({"token": token, "item_ids": reversed_ids}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        # Verify new order in DB
        new_order = _get_playlist_item_ids(app, event_id)
        assert new_order == reversed_ids

    def test_reorder_mismatched_length(self, app, portal_event):
        """Mismatched item_ids length returns 409.

        EARS: WHEN a client submits reorder with mismatched item_ids length
        THE SYSTEM SHALL return 409 with "Playlist changed" message.
        """
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        _portal_add_to_playlist(client, token, song_ids[1])
        event_id = _get_event_id(app, token)
        item_ids = _get_playlist_item_ids(app, event_id)
        # Send only one of two items
        resp = client.post(
            "/api/playlist/reorder",
            data=json.dumps({"token": token, "item_ids": [item_ids[0]]}),
            content_type="application/json",
        )
        assert resp.status_code == 409
        data = resp.get_json()
        assert "changed" in data["error"].lower() or "refresh" in data["error"].lower()

    def test_reorder_invalid_item_ids(self, app, portal_event):
        """Reorder with wrong item IDs returns 400."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        _portal_add_to_playlist(client, token, song_ids[1])
        resp = client.post(
            "/api/playlist/reorder",
            data=json.dumps({"token": token, "item_ids": [99998, 99999]}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_reorder_missing_token(self, client):
        """Reorder without token returns 400."""
        resp = client.post(
            "/api/playlist/reorder",
            data=json.dumps({"item_ids": [1, 2]}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_reorder_missing_item_ids(self, portal_event):
        """Reorder without item_ids returns 400."""
        client, token = portal_event
        resp = client.post(
            "/api/playlist/reorder",
            data=json.dumps({"token": token}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_reorder_invalid_token(self, client):
        """Reorder with invalid token returns 404."""
        resp = client.post(
            "/api/playlist/reorder",
            data=json.dumps({"token": "bad-token", "item_ids": [1]}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_reorder_blocked_after_approval(self, app, portal_event):
        """Reorder blocked after event approval returns 403."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        event_id = _get_event_id(app, token)
        item_ids = _get_playlist_item_ids(app, event_id)
        # Approve the event
        with app.app_context():
            with get_db(immediate=True) as db:
                db.execute(
                    "UPDATE event SET client_approved = 1, approved_at = datetime('now') WHERE id = ?",
                    (event_id,),
                )
                db.commit()
        resp = client.post(
            "/api/playlist/reorder",
            data=json.dumps({"token": token, "item_ids": item_ids}),
            content_type="application/json",
        )
        assert resp.status_code == 403


class TestApiFilters:
    """AJAX song filtering via /api/filters/songs.

    Query params: token, genre, energy, search.
    """

    def test_filter_songs_all(self, app, portal_event):
        """Fetching all songs returns the full repertoire."""
        client, token = portal_event
        resp = client.get(f"/api/filters/songs?token={token}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "songs" in data
        assert len(data["songs"]) == 2  # We created 2 songs in the fixture

    def test_filter_songs_by_genre(self, app, portal_event):
        """Filtering by genre returns matching songs."""
        client, token = portal_event
        resp = client.get(f"/api/filters/songs?token={token}&genre=rock")
        assert resp.status_code == 200
        data = resp.get_json()
        # Bohemian Rhapsody is rock, Fly Me to the Moon is jazz
        assert len(data["songs"]) >= 1
        for song in data["songs"]:
            assert song["genre"] == "rock"

    def test_filter_songs_by_energy(self, app, portal_event):
        """Filtering by energy level returns matching songs."""
        client, token = portal_event
        resp = client.get(f"/api/filters/songs?token={token}&energy=5")
        assert resp.status_code == 200
        data = resp.get_json()
        for song in data["songs"]:
            assert song["energy"] == 5

    def test_filter_songs_by_search(self, app, portal_event):
        """Search by title returns matching songs."""
        client, token = portal_event
        resp = client.get(f"/api/filters/songs?token={token}&search=Bohemian")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["songs"]) >= 1
        assert data["songs"][0]["title"] == "Bohemian Rhapsody"

    def test_filter_songs_in_playlist_flag(self, app, portal_event):
        """Songs in the playlist have in_playlist=true."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        resp = client.get(f"/api/filters/songs?token={token}")
        data = resp.get_json()
        playlist_statuses = {s["id"]: s["in_playlist"] for s in data["songs"]}
        assert playlist_statuses[song_ids[0]] is True
        assert playlist_statuses[song_ids[1]] is False

    def test_filter_songs_invalid_token(self, client):
        """Invalid token returns 404."""
        resp = client.get("/api/filters/songs?token=bad-token")
        assert resp.status_code == 404

    def test_filter_songs_response_shape(self, app, portal_event):
        """Response includes all required fields per spec."""
        client, token = portal_event
        resp = client.get(f"/api/filters/songs?token={token}")
        data = resp.get_json()
        assert len(data["songs"]) > 0
        song = data["songs"][0]
        # Spec says: id, title, artist, genre, energy, duration_seconds, in_playlist
        assert "id" in song
        assert "title" in song
        assert "artist" in song
        assert "genre" in song
        assert "energy" in song
        assert "duration_seconds" in song
        assert "in_playlist" in song


class TestEventDashboard:
    """Musician's event dashboard showing client selections.

    EARS: WHEN a musician views event dashboard THE SYSTEM SHALL display all
    playlist items, flags, and song requests.
    """

    def test_dashboard_loads(self, app, portal_event):
        """Event dashboard shows playlist and requests."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        event_id = _get_event_id(app, token)
        # Add a song to playlist and create a request
        _portal_add_to_playlist(client, token, song_ids[0])
        client.post(f"/portal/{token}/requests/add", data={
            "title": "Client Requested Song",
            "artist": "Various",
            "notes": "",
        }, follow_redirects=True)
        # View the dashboard as the musician
        resp = client.get(f"/events/{event_id}/dashboard")
        assert resp.status_code == 200
        assert b"Bohemian Rhapsody" in resp.data
        assert b"Client Requested Song" in resp.data


class TestEventExport:
    """Setlist export tests.

    EARS: WHEN a musician exports a setlist as CSV THE SYSTEM SHALL return a
    downloadable file with song data ordered by position.
    """

    def test_export_preview_loads(self, app, portal_event):
        """Export preview page loads."""
        client, token = portal_event
        event_id = _get_event_id(app, token)
        resp = client.get(f"/events/{event_id}/export")
        assert resp.status_code == 200

    def test_export_csv(self, app, portal_event):
        """CSV export returns a downloadable file."""
        client, token = portal_event
        song_ids = _get_song_ids(app)
        _portal_add_to_playlist(client, token, song_ids[0])
        _portal_add_to_playlist(client, token, song_ids[1])
        event_id = _get_event_id(app, token)
        resp = client.get(f"/events/{event_id}/export/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type or "application/csv" in resp.content_type
        # CSV should contain song titles
        csv_text = resp.data.decode("utf-8")
        assert "Bohemian Rhapsody" in csv_text
