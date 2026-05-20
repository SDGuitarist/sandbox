"""SerpAPI Google Search -> lead discovery.

Ported from venue-scraper/discover.py and adapted for person-finding.
Discovered URLs are fetched and contact-extracted via LLM (Phase 4).

Requires: SERPAPI_API_KEY environment variable.
Free tier: 100 searches/month.
Disk cache: ./serpapi_cache/ with 7-day TTL.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

SERPAPI_URL = "https://serpapi.com/search.json"
MAX_RESULTS_PER_QUERY = 10
REQUEST_TIMEOUT = 10
DELAY_BETWEEN_QUERIES = 1.0
CACHE_DIR = Path("./serpapi_cache")
CACHE_TTL_DAYS = 7
USAGE_FILE = CACHE_DIR / "usage.json"

# Person-finding queries for creative professionals
PERSON_QUERIES = [
    "filmmaker {location}",
    "film composer {location}",
    "music producer {location}",
    "screenwriter {location}",
    "video production {location}",
]

# Domains that are directories/social, not personal websites
DIRECTORY_DOMAINS = {
    "yelp.com", "facebook.com", "instagram.com", "niche.com",
    "wikipedia.org", "productionhub.com", "linkedin.com",
    "twitter.com", "x.com", "tiktok.com", "youtube.com",
    "google.com", "maps.google.com", "glassdoor.com",
    "imdb.com", "soundcloud.com", "spotify.com", "bandcamp.com",
}


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


def _cache_is_fresh(cache_file: Path) -> bool:
    """Check if cache file exists and is less than CACHE_TTL_DAYS old."""
    if not cache_file.exists():
        return False
    mtime = cache_file.stat().st_mtime
    age_days = (time.time() - mtime) / 86400
    return age_days < CACHE_TTL_DAYS


def _track_usage() -> None:
    """Track monthly SerpAPI credit usage. Warns at 90% of free tier."""
    CACHE_DIR.mkdir(exist_ok=True)
    usage = json.loads(USAGE_FILE.read_text()) if USAGE_FILE.exists() else {"month": "", "count": 0}
    current_month = datetime.now().strftime("%Y-%m")
    if usage["month"] != current_month:
        usage = {"month": current_month, "count": 0}
    usage["count"] += 1
    USAGE_FILE.write_text(json.dumps(usage))
    if usage["count"] >= 90:
        print(f"[google] WARNING: {usage['count']}/100 monthly SerpAPI credits used", file=sys.stderr)


def search_people(
    query: str,
    location: str = "San Diego, California, United States",
    use_cache: bool = True,
) -> list[str]:
    """Search Google via SerpAPI and return organic result URLs.

    Returns empty list on any error (prints warning, never crashes pipeline).
    """
    if use_cache:
        CACHE_DIR.mkdir(exist_ok=True)
        key = _cache_key(query, location)
        cache_file = CACHE_DIR / f"{key}.json"
        if _cache_is_fresh(cache_file):
            print(f"[google] CACHE HIT: '{query}'")
            data = json.loads(cache_file.read_text())
            return _extract_urls(data)

    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        print("[google] ERROR: SERPAPI_API_KEY not set", file=sys.stderr)
        return []

    params = {
        "engine": "google",
        "q": query,
        "location": location,
        "api_key": api_key,
        "hl": "en",
        "gl": "us",
        "num": 20,
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        print(f"[google] TIMEOUT for '{query}'", file=sys.stderr)
        return []
    except requests.exceptions.ConnectionError:
        print(f"[google] CONNECTION ERROR for '{query}'", file=sys.stderr)
        return []

    if response.status_code == 429:
        print("[google] SerpAPI free tier exhausted (429)", file=sys.stderr)
        return []
    if response.status_code == 401:
        print("[google] INVALID API KEY (401)", file=sys.stderr)
        return []
    if response.status_code != 200:
        print(f"[google] HTTP {response.status_code}", file=sys.stderr)
        return []

    try:
        data = response.json()
    except ValueError:
        print("[google] Invalid JSON response", file=sys.stderr)
        return []

    if "error" in data:
        print(f"[google] API ERROR: {data['error']}", file=sys.stderr)
        return []

    if use_cache:
        cache_file.write_text(json.dumps(data, indent=2))

    _track_usage()

    urls = _extract_urls(data)
    print(f"[google] Found {len(urls)} URLs for '{query}'")
    return urls


def scrape(config: dict) -> list[dict]:
    """Run person-finding queries and extract contacts from discovered URLs.

    Returns list of lead dicts ready for ingest_leads().
    Each discovered URL is fetched and contact-extracted via LLM.
    Pages where no name is extracted are skipped (not a personal site).
    """
    from enrich import _fetch_page, _strip_html_to_text, _extract_with_llm

    location = config.get("location", "San Diego, California, United States")
    queries = config.get("queries") or PERSON_QUERIES

    # Discover URLs from all queries
    all_urls: list[str] = []
    seen: set[str] = set()

    for i, query_template in enumerate(queries):
        query = query_template.format(location=location) if "{location}" in query_template else query_template
        urls = search_people(query, location=location)

        for url in urls:
            if url not in seen:
                seen.add(url)
                all_urls.append(url)

        if i < len(queries) - 1:
            time.sleep(DELAY_BETWEEN_QUERIES)

    if not all_urls:
        print("[google] No URLs discovered.")
        return []

    print(f"[google] Discovered {len(all_urls)} unique URLs. Extracting contacts...")

    # Extract contacts from discovered pages
    try:
        import anthropic
        from pydantic import BaseModel, Field

        class WebsiteContactModel(BaseModel):
            name: str | None = None
            email: str | None = None
            phone: str | None = None
            social_handles: list[str] = Field(default_factory=list)
            role: str | None = None
            bio_snippet: str | None = None

        client = anthropic.Anthropic(max_retries=2)
    except Exception as e:
        print(f"[google] Anthropic SDK not available: {e}. Returning URLs without extraction.")
        return []

    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    leads: list[dict] = []
    for url in all_urls:
        # SECURITY: Always use _fetch_page(), never requests.get() directly
        html = _fetch_page(session, url)
        if not html:
            continue

        visible_text = _strip_html_to_text(html)
        if len(visible_text) < 200:
            continue

        extraction, _in_tok, _out_tok = _extract_with_llm(client, "claude-haiku-4-5-20251001", visible_text, WebsiteContactModel)
        if extraction is None or not extraction.name:
            continue  # Not a personal site

        lead = {
            "name": extraction.name,
            "profile_url": url,
            "source": "google",
            "email": extraction.email,
            "phone": extraction.phone,
            "website": url,
        }
        if extraction.social_handles:
            lead["activity"] = ", ".join(extraction.social_handles[:3])
        if extraction.bio_snippet:
            lead["bio"] = extraction.bio_snippet

        leads.append(lead)
        print(f"  {extraction.name}: email={extraction.email}, phone={extraction.phone}")

    session.close()
    print(f"[google] Extracted {len(leads)} leads from {len(all_urls)} pages.")
    return leads
