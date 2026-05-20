"""Tests for repertoire blueprint: song CRUD.

EARS acceptance tests covered:
- WHEN a musician creates a song with title/artist/genre/energy THE SYSTEM
  SHALL save it and redirect to repertoire index
"""

from tests.conftest import _create_song, _get_song_ids


class TestRepertoireIndex:
    """Song list page tests."""

    def test_index_requires_login(self, client):
        """GET /repertoire/ without login redirects."""
        resp = client.get("/repertoire/")
        assert resp.status_code == 302

    def test_index_empty(self, auth_client):
        """Repertoire index loads with no songs."""
        resp = auth_client.get("/repertoire/")
        assert resp.status_code == 200

    def test_index_shows_songs(self, auth_client):
        """After creating a song, it appears on the index."""
        _create_song(auth_client, title="Hotel California")
        resp = auth_client.get("/repertoire/")
        assert resp.status_code == 200
        assert b"Hotel California" in resp.data


class TestSongCreate:
    """Song creation tests."""

    def test_create_form_loads(self, auth_client):
        """GET /repertoire/new returns the form."""
        resp = auth_client.get("/repertoire/new")
        assert resp.status_code == 200

    def test_create_happy_path(self, auth_client):
        """Creating a song with all fields succeeds."""
        resp = _create_song(
            auth_client,
            title="Stairway to Heaven",
            artist="Led Zeppelin",
            genre="rock",
            musical_key="Am",
            tempo="82",
            energy="4",
            duration_seconds="480",
            notes="Classic rock anthem",
        )
        assert resp.status_code == 200
        assert b"Stairway to Heaven" in resp.data

    def test_create_minimal_fields(self, auth_client):
        """Creating a song with only required fields succeeds."""
        resp = _create_song(
            auth_client,
            title="Minimal Song",
            artist="",
            genre="other",
            musical_key="",
            tempo="",
            energy="3",
            duration_seconds="",
            notes="",
        )
        assert resp.status_code == 200

    def test_create_missing_title(self, auth_client):
        """Creating a song without a title should fail."""
        resp = _create_song(auth_client, title="")
        assert resp.status_code == 200


class TestSongDetail:
    """Song detail view tests."""

    def test_detail_page(self, app, auth_client):
        """Song detail page shows the correct song."""
        _create_song(auth_client, title="Purple Rain", artist="Prince")
        song_ids = _get_song_ids(app)
        assert len(song_ids) >= 1
        resp = auth_client.get(f"/repertoire/{song_ids[0]}")
        assert resp.status_code == 200
        assert b"Purple Rain" in resp.data

    def test_detail_nonexistent(self, auth_client):
        """Requesting a nonexistent song returns 404."""
        resp = auth_client.get("/repertoire/99999")
        assert resp.status_code == 404


class TestSongEdit:
    """Song edit tests."""

    def test_edit_form_loads(self, app, auth_client):
        """GET /repertoire/<id>/edit loads the form."""
        _create_song(auth_client, title="Old Title")
        song_ids = _get_song_ids(app)
        resp = auth_client.get(f"/repertoire/{song_ids[0]}/edit")
        assert resp.status_code == 200
        assert b"Old Title" in resp.data

    def test_edit_happy_path(self, app, auth_client):
        """Editing a song updates it and redirects."""
        _create_song(auth_client, title="Old Title")
        song_ids = _get_song_ids(app)
        resp = auth_client.post(f"/repertoire/{song_ids[0]}/edit", data={
            "title": "New Title",
            "artist": "New Artist",
            "genre": "jazz",
            "musical_key": "Bb",
            "tempo": "100",
            "energy": "2",
            "duration_seconds": "300",
            "notes": "Updated notes",
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestSongDelete:
    """Song deletion tests."""

    def test_delete_song(self, app, auth_client):
        """Deleting a song removes it."""
        _create_song(auth_client, title="To Delete")
        song_ids = _get_song_ids(app)
        assert len(song_ids) >= 1
        resp = auth_client.post(
            f"/repertoire/{song_ids[0]}/delete",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Song should be gone
        remaining = _get_song_ids(app)
        assert song_ids[0] not in remaining

    def test_delete_nonexistent(self, auth_client):
        """Deleting a nonexistent song returns 404."""
        resp = auth_client.post("/repertoire/99999/delete")
        assert resp.status_code == 404


class TestSongOwnership:
    """Songs are scoped to the user who created them.

    EARS: WHEN a musician tries to access another musician's event/song THE
    SYSTEM SHALL return 404.
    """

    def test_cannot_view_other_users_song(self, app, client):
        """User B cannot view User A's songs."""
        from tests.conftest import _register_user, _login_user

        # User A creates a song
        _register_user(client, email="a@test.com", display_name="User A")
        _create_song(client, title="User A Song")
        song_ids = _get_song_ids(app)
        client.post("/auth/logout", follow_redirects=True)

        # User B tries to access it
        _register_user(client, email="b@test.com", display_name="User B")
        resp = client.get(f"/repertoire/{song_ids[0]}")
        assert resp.status_code == 404
