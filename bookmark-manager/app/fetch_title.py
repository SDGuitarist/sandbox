import re
import urllib.request
import urllib.error

FETCH_TIMEOUT: int = 3

def fetch_page_title(url: str) -> str | None:
    try:
        resp = urllib.request.urlopen(url, timeout=FETCH_TIMEOUT)
        content = resp.read(100_000).decode('utf-8', errors='ignore')
        match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else None
    except Exception:
        return None
