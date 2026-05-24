from tests.conftest import add_bookmark, get_csrf


def test_add_bookmark_with_metadata(client):
    """WHEN a user submits a valid URL THE SYSTEM SHALL save the bookmark
    with fetched title/description and redirect to / with the bookmark visible."""
    resp = add_bookmark(client, url='https://example.com')
    assert resp.status_code == 200
    assert b'Title for https://example.com' in resp.data
    assert b'Bookmark added.' in resp.data


def test_add_bookmark_with_tags(client):
    """WHEN a user submits a URL with tags THE SYSTEM SHALL create tags
    (lowercased, stripped) and associate them with the bookmark."""
    resp = add_bookmark(client, url='https://example.com', tags='Python, Flask, Tutorial')
    assert resp.status_code == 200
    assert b'python' in resp.data
    assert b'flask' in resp.data
    assert b'tutorial' in resp.data


def test_tag_dedup_case_insensitive(client):
    """WHEN tag "python" already exists and user submits "Python" THE SYSTEM
    SHALL reuse the existing tag."""
    add_bookmark(client, url='https://a.com', tags='python')
    add_bookmark(client, url='https://b.com', tags='Python')
    resp = client.get('/')
    # Both bookmarks should show the same "python" tag, not create "Python"
    assert resp.data.count(b'>python<') == 2


def test_search_by_keyword(client):
    """WHEN a user searches ?q=flask THE SYSTEM SHALL return matching bookmarks."""
    add_bookmark(client, url='https://flask.dev', tags='flask')
    add_bookmark(client, url='https://django.dev', tags='django')
    resp = client.get('/?q=flask')
    assert b'flask.dev' in resp.data
    assert b'django.dev' not in resp.data


def test_filter_by_tag(client):
    """WHEN a user filters ?tag=python THE SYSTEM SHALL return only
    bookmarks tagged python."""
    add_bookmark(client, url='https://a.com', tags='python')
    add_bookmark(client, url='https://b.com', tags='rust')
    resp = client.get('/?tag=python')
    assert b'a.com' in resp.data
    assert b'b.com' not in resp.data


def test_combined_search_and_tag(client):
    """WHEN a user searches ?q=tutorial&tag=python THE SYSTEM SHALL return
    bookmarks matching both (AND)."""
    add_bookmark(client, url='https://python-tutorial.com', tags='python')
    add_bookmark(client, url='https://python-reference.com', tags='python')
    add_bookmark(client, url='https://rust-tutorial.com', tags='rust')
    resp = client.get('/?q=tutorial&tag=python')
    assert b'python-tutorial.com' in resp.data
    assert b'python-reference.com' not in resp.data
    assert b'rust-tutorial.com' not in resp.data


def test_delete_bookmark_with_orphan_cleanup(client, app):
    """WHEN a user deletes a bookmark THE SYSTEM SHALL remove the bookmark,
    its bookmark_tags rows, and any orphaned tags."""
    add_bookmark(client, url='https://only.com', tags='unique-tag')
    csrf = get_csrf(client)

    # Find the bookmark id
    with app.app_context():
        from app.db import get_db
        db = get_db()
        row = db.execute("SELECT id FROM bookmarks WHERE url = 'https://only.com'").fetchone()
        bookmark_id = row['id']

    # Delete it
    resp = client.post(f'/delete/{bookmark_id}', data={'csrf_token': csrf}, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Bookmark deleted.' in resp.data
    assert b'only.com' not in resp.data

    # Verify orphaned tag was cleaned up
    with app.app_context():
        from app.db import get_db
        db = get_db()
        tag = db.execute("SELECT * FROM tags WHERE name = 'unique-tag'").fetchone()
        assert tag is None
