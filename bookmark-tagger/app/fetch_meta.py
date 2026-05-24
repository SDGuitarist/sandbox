import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

FETCH_TIMEOUT = 3
MAX_READ_BYTES = 100_000


def is_safe_url(url: str) -> bool:
    """Check that URL uses http or https scheme and has a hostname."""
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and parsed.hostname is not None


def fetch_page_meta(url: str) -> dict:
    """Fetch title and description from a URL.

    Returns {'title': str, 'description': str}. Both default to '' on failure.
    """
    result = {'title': '', 'description': ''}

    if not is_safe_url(url):
        return result

    try:
        req = urllib.request.Request(
            url, headers={'User-Agent': 'BookmarkTagger/1.0'}
        )
        resp = urllib.request.urlopen(req, timeout=FETCH_TIMEOUT)

        content_type = resp.headers.get('content-type', '')
        if 'text/html' not in content_type.lower():
            return result

        # Detect charset
        charset = 'utf-8'
        m = re.search(r'charset=([^;\s]+)', content_type, re.IGNORECASE)
        if m:
            charset = m.group(1).strip('"\'')

        content = resp.read(MAX_READ_BYTES).decode(charset, errors='ignore')

        # Extract title
        t = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        if t:
            result['title'] = t.group(1).strip()

        # Extract meta description
        d = re.search(
            r'<meta\s+name=["\']?description["\']?\s+content=["\']([^"\']*)["\']',
            content, re.IGNORECASE,
        )
        if d:
            result['description'] = d.group(1).strip()

    except Exception:
        pass

    return result
