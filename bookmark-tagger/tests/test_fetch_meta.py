"""Direct tests for fetch_meta parser logic (no monkeypatching)."""
from unittest.mock import patch, MagicMock
from app.fetch_meta import fetch_page_meta, is_safe_url


# --- is_safe_url tests ---

def test_safe_url_http():
    assert is_safe_url('http://example.com') is True

def test_safe_url_https():
    assert is_safe_url('https://example.com') is True

def test_reject_file_scheme():
    assert is_safe_url('file:///etc/passwd') is False

def test_reject_ftp_scheme():
    assert is_safe_url('ftp://example.com') is False

def test_reject_no_hostname():
    assert is_safe_url('http://') is False

def test_reject_empty_string():
    assert is_safe_url('') is False

def test_reject_no_scheme():
    assert is_safe_url('example.com') is False


# --- fetch_page_meta parser tests ---

def _mock_urlopen(html, content_type='text/html; charset=utf-8'):
    """Create a mock response for urllib.request.urlopen."""
    resp = MagicMock()
    resp.headers = {'content-type': content_type}
    resp.read.return_value = html.encode('utf-8')
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


@patch('app.fetch_meta.urllib.request.urlopen')
def test_extract_title(mock_urlopen):
    mock_urlopen.return_value = _mock_urlopen('<html><title>My Page</title></html>')
    result = fetch_page_meta('https://example.com')
    assert result['title'] == 'My Page'


@patch('app.fetch_meta.urllib.request.urlopen')
def test_extract_meta_description_name_first(mock_urlopen):
    """Handle <meta name="description" content="...">"""
    html = '<html><head><meta name="description" content="A great page"></head></html>'
    mock_urlopen.return_value = _mock_urlopen(html)
    result = fetch_page_meta('https://example.com')
    assert result['description'] == 'A great page'


@patch('app.fetch_meta.urllib.request.urlopen')
def test_extract_meta_description_content_first(mock_urlopen):
    """Handle <meta content="..." name="description">"""
    html = '<html><head><meta content="Reversed order" name="description"></head></html>'
    mock_urlopen.return_value = _mock_urlopen(html)
    result = fetch_page_meta('https://example.com')
    assert result['description'] == 'Reversed order'


@patch('app.fetch_meta.urllib.request.urlopen')
def test_non_html_returns_empty(mock_urlopen):
    """Non-HTML Content-Type returns empty title/description."""
    mock_urlopen.return_value = _mock_urlopen(
        b'%PDF-1.4'.decode('utf-8'), content_type='application/pdf'
    )
    result = fetch_page_meta('https://example.com/doc.pdf')
    assert result == {'title': '', 'description': ''}


@patch('app.fetch_meta.urllib.request.urlopen')
def test_fetch_timeout_returns_empty(mock_urlopen):
    mock_urlopen.side_effect = TimeoutError('timed out')
    result = fetch_page_meta('https://slow.example.com')
    assert result == {'title': '', 'description': ''}


def test_unsafe_url_skips_fetch():
    result = fetch_page_meta('file:///etc/passwd')
    assert result == {'title': '', 'description': ''}
