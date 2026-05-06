"""discover.py -- SerpAPI Google Search -> venue URL discovery.

Requires: SERPAPI_API_KEY environment variable (validated at usage-time only).
Free tier: 100 searches/month. 4 queries x search_film_venues() = 4 credits per run.
Disk cache: ./serpapi_cache/ stores raw JSON responses to save credits during dev.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

SERPAPI_URL = "https://serpapi.com/search.json"
MAX_RESULTS_PER_QUERY = 10
REQUEST_TIMEOUT = 10  # seconds
DELAY_BETWEEN_QUERIES = 1.0  # seconds -- be polite to the API
CACHE_DIR = Path("./serpapi_cache")

# Domains that are directories/social, not actual venue websites
DIRECTORY_DOMAINS = {
    "yelp.com", "facebook.com", "instagram.com", "niche.com",
    "wikipedia.org", "productionhub.com", "linkedin.com",
    "twitter.com", "x.com", "tiktok.com", "youtube.com",
    "google.com", "maps.google.com", "glassdoor.com",
}

# Predefined queries for San Diego film venues
FILM_VENUE_QUERIES = [
    "film school {location}",
    "production studio {location}",
    "post production house {location}",
    "film commission {location} filmmaker resources",
]


def _is_directory_site(url: str) -> bool:
    """Check if URL belongs to a known directory/social site."""
    try:
        hostname = urlparse(url).hostname or ""
        hostname = hostname.removeprefix("www.")
        return any(hostname == d or hostname.endswith("." + d) for d in DIRECTORY_DOMAINS)
    except Exception:
        return False


def _extract_urls(data: dict) -> list[str]:
    """Pull organic result URLs from SerpAPI JSON, filtering directories.

    Deduplicates by domain (keeps first result per domain).
    """
    organic_results = data.get("organic_results", [])
    seen_domains: set[str] = set()
    urls: list[str] = []

    for result in organic_results:
        link = result.get("link")
        if not link:
            continue
        if _is_directory_site(link):
            continue
        # Must be http/https
        if not link.startswith(("http://", "https://")):
            continue

        domain = urlparse(link).hostname or ""
        domain = domain.removeprefix("www.")
        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        urls.append(link)
        if len(urls) >= MAX_RESULTS_PER_QUERY:
            break

    return urls


def _cache_key(query: str, location: str) -> str:
    """Generate filesystem-safe cache key from query + location."""
    raw = f"{query}|{location}"
    return hashlib.md5(raw.encode()).hexdigest()


def search_venues(
    query: str,
    location: str = "San Diego, California, United States",
    use_cache: bool = True,
) -> list[str]:
    """Search Google via SerpAPI and return organic result URLs.

    Returns up to MAX_RESULTS_PER_QUERY URLs, filtering out directory sites.
    Returns empty list on any error (prints warning, never crashes pipeline).

    SECURITY: Never logs request URLs (would expose API key).
    """
    # Check cache first (saves free-tier credits during development)
    if use_cache:
        CACHE_DIR.mkdir(exist_ok=True)
        key = _cache_key(query, location)
        cache_file = CACHE_DIR / f"{key}.json"
        if cache_file.exists():
            print(f"[discover] CACHE HIT: '{query}'")
            data = json.loads(cache_file.read_text())
            return _extract_urls(data)

    # Validate API key at usage-time (not import-time)
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        print("[discover] ERROR: SERPAPI_API_KEY not set", file=sys.stderr)
        return []

    params = {
        "engine": "google",
        "q": query,
        "location": location,
        "api_key": api_key,
        "hl": "en",
        "gl": "us",
        "num": 20,  # Request extra to compensate for filtering
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        print(f"[discover] TIMEOUT for '{query}'", file=sys.stderr)
        return []
    except requests.exceptions.ConnectionError:
        print(f"[discover] CONNECTION ERROR for '{query}'", file=sys.stderr)
        return []

    # Handle HTTP errors (never log full response -- may contain key in URL)
    if response.status_code == 429:
        print("[discover] RATE LIMIT: quota exhausted (429)", file=sys.stderr)
        return []
    if response.status_code == 401:
        print("[discover] INVALID API KEY (401)", file=sys.stderr)
        return []
    if response.status_code != 200:
        print(f"[discover] HTTP {response.status_code} for query", file=sys.stderr)
        return []

    try:
        data = response.json()
    except ValueError:
        print("[discover] Invalid JSON response", file=sys.stderr)
        return []

    if "error" in data:
        print(f"[discover] API ERROR: {data['error']}", file=sys.stderr)
        return []

    # Cache successful responses
    if use_cache and "error" not in data:
        cache_file.write_text(json.dumps(data, indent=2))

    if not data.get("organic_results"):
        print(f"[discover] No results for '{query}'", file=sys.stderr)
        return []

    urls = _extract_urls(data)
    print(f"[discover] Found {len(urls)} URLs for '{query}'")
    return urls


def search_film_venues(location: str = "San Diego, California, United States") -> list[str]:
    """Run predefined film-venue queries and return deduplicated URLs.

    Uses 4 API credits per call (one per FILM_VENUE_QUERIES).
    """
    all_urls: list[str] = []
    seen: set[str] = set()

    for i, query_template in enumerate(FILM_VENUE_QUERIES):
        query = query_template.format(location=location)
        urls = search_venues(query, location=location)

        for url in urls:
            if url not in seen:
                seen.add(url)
                all_urls.append(url)

        # Be polite between requests
        if i < len(FILM_VENUE_QUERIES) - 1:
            time.sleep(DELAY_BETWEEN_QUERIES)

    print(f"[discover] Total unique URLs: {len(all_urls)}")
    return all_urls
