from tests.conftest import add_bookmark, get_csrf


def test_empty_url_rejected(client):
    """WHEN a user submits an empty URL THE SYSTEM SHALL flash an error
    and not create a bookmark."""
    csrf = get_csrf(client)
    resp = client.post('/add', data={'url': '', 'tags': '', 'csrf_token': csrf},
                       follow_redirects=True)
    assert b'URL is required.' in resp.data


def test_file_scheme_rejected(client):
    """WHEN a user submits file:///etc/passwd THE SYSTEM SHALL flash
    'Invalid URL scheme' and reject."""
    resp = add_bookmark(client, url='file:///etc/passwd')
    assert b'Invalid URL scheme' in resp.data


def test_ftp_scheme_rejected(client):
    """WHEN a user submits ftp://... THE SYSTEM SHALL reject."""
    resp = add_bookmark(client, url='ftp://files.example.com/data.csv')
    assert b'Invalid URL scheme' in resp.data


def test_no_hostname_rejected(client):
    """WHEN a user submits a URL with no hostname THE SYSTEM SHALL reject."""
    resp = add_bookmark(client, url='http://')
    assert b'Invalid URL scheme' in resp.data


def test_fetch_failure_saves_empty_meta(client, monkeypatch):
    """WHEN fetch returns empty (timeout/error) THE SYSTEM SHALL save the
    bookmark with title='' and description=''."""
    monkeypatch.setattr(
        'app.fetch_page_meta',
        lambda url: {'title': '', 'description': ''},
    )
    resp = add_bookmark(client, url='https://timeout.example.com')
    assert b'Bookmark added.' in resp.data
    assert b'timeout.example.com' in resp.data


def test_url_too_long_rejected(client):
    """WHEN a user submits a URL longer than 2048 chars THE SYSTEM SHALL
    flash an error and reject."""
    long_url = 'https://example.com/' + 'a' * 2040
    resp = add_bookmark(client, url=long_url)
    assert b'2048 characters or less' in resp.data


def test_csrf_mismatch_returns_403(client):
    """WHEN a user submits a POST with missing/wrong CSRF token THE SYSTEM
    SHALL return 403."""
    resp = client.post('/add', data={'url': 'https://example.com', 'csrf_token': 'wrong'})
    assert resp.status_code == 403


def test_tag_limit_enforced(client):
    """WHEN a user submits 25 comma-separated tags THE SYSTEM SHALL keep
    the first 20 and flash a warning."""
    tags = ', '.join(f'tag{i}' for i in range(25))
    resp = add_bookmark(client, url='https://example.com', tags=tags)
    assert b'Only the first 20 tags were kept.' in resp.data
    # Verify only 20 tags are shown (not 25)
    for i in range(20):
        assert f'tag{i}'.encode() in resp.data
    assert b'tag24' not in resp.data


def test_overlong_tag_truncated_with_warning(client):
    """WHEN a submitted tag exceeds 50 characters THE SYSTEM SHALL truncate
    it and flash a warning."""
    long_tag = 'a' * 60
    resp = add_bookmark(client, url='https://example.com', tags=long_tag)
    assert b'truncated to 50 characters' in resp.data
    # The tag should be stored as 50 chars, not 60
    assert ('a' * 50).encode() in resp.data
    assert ('a' * 60).encode() not in resp.data


def test_delete_nonexistent_redirects(client):
    """WHEN a user deletes a nonexistent bookmark id THE SYSTEM SHALL
    redirect to / (no error, no crash)."""
    csrf = get_csrf(client)
    resp = client.post('/delete/99999', data={'csrf_token': csrf}, follow_redirects=True)
    assert resp.status_code == 200
