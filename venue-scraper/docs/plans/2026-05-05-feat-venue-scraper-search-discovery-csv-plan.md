---
title: "feat: Add search discovery, smart subpage crawling, and CSV export"
type: feat
status: active
date: 2026-05-05
origin: docs/brainstorms/2026-05-05-venue-scraper-low-effort-upgrades-brainstorm.md
feed_forward:
  risk: "Single-pass crawl refactors scrape.py main loop + networkidle may slow crawl time by 30-75s total"
  verify_first: false
---

## Enhancement Summary

**Deepened on:** 2026-05-05
**Sections enhanced:** 4 (discover.py, crawler.py, export.py, CLI)
**Research agents used:** SerpAPI best-practices, Crawl4AI framework-docs, security-sentinel, spec-flow-analyzer

### Key Improvements from Deepening
1. Added disk caching for SerpAPI responses (saves free-tier credits during dev)
2. Resolved single-pass vs two-phase ambiguity (single-pass is final decision)
3. Added SSRF protection for link-based discovery (same-origin validation)
4. Expanded CSV sanitization to strip control characters (\t, \r, \n)
5. Resolved CLI argument architecture (search flags replace mutually exclusive group)
6. Added `wait_until="networkidle"` for reliable link extraction

### Critical Gaps Resolved
- Q1: --search flags join the source group as new options (not additive)
- Q3: Single-pass crawling is the ONLY approach (two-phase deleted)
- Q4: SERPAPI_API_KEY validated at usage-time, not import-time
- Q5: Fallback is additive (always try hardcoded paths not already found via links)

---

# feat: Add search discovery, smart subpage crawling, and CSV export

## Overview

Three upgrades to the venue-scraper that create an end-to-end pipeline: search query -> URL discovery -> smart multi-page scrape -> outreach-ready CSV. Designed for autopilot execution (well-scoped modules, clear interfaces, no human judgment needed).

## Problem Statement / Motivation

Currently the scraper requires manually curated `urls.txt` files and only checks hardcoded `/contact` + `/about` paths. For the May 30 Amplify workshop, we need to quickly find ~30-40 San Diego film venues and get their contact info into an outreach-ready format.

## Proposed Solution

Three new/modified modules with clear boundaries:

1. **`discover.py`** (NEW) -- SerpAPI Google search -> list of URLs
2. **`crawler.py`** (MODIFIED) -- Single-pass crawl with link-based subpage discovery
3. **`export.py`** (NEW) -- JSON results -> sanitized CSV outreach list

## Technical Approach

### Module 1: discover.py (SerpAPI Integration)

**Purpose:** Given a search query, return venue website URLs from Google results.

```python
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
        print(f"[discover] Invalid JSON response", file=sys.stderr)
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
```

### Research Insights (SerpAPI)

**Location parameter:** Use full canonical form `"San Diego, California, United States"` (not "San Diego, CA") for reliable geo-matching in SerpAPI's location database.

**Legal risk (low impact):** Google sued SerpAPI in Dec 2025 (case 4:2025cv10826). Hearing May 19, 2026. API is operational; just don't build mission-critical pipelines without a fallback.

**Free tier gotchas:**
- Empty results still consume 1 credit
- 429 fires for BOTH hourly burst limit AND monthly quota exhaustion (indistinguishable)
- No sandbox/test mode -- integration tests burn credits
- Disk cache (`./serpapi_cache/`) prevents credit waste during development

---

### Module 2: crawler.py (Single-Pass Subpage Discovery)

**FINAL DECISION: Single-pass crawling.** Homepage gets crawled WITH LLM extraction, then `result.links["internal"]` is used for subpage discovery. No double-crawl.

**New state:** Add `discover_subpages_from_links()` alongside existing `discover_subpages()`:

```python
from urllib.parse import urljoin, urlparse

# Keywords for link-text matching (case-insensitive substring)
CONTACT_KEYWORDS = ["contact", "get in touch", "inquir"]
ABOUT_KEYWORDS = ["about", "team", "connect"]

# Existing hardcoded paths kept as fallback
CONTACT_SUBPATHS = ["/contact", "/about"]


def _is_same_origin(base_url: str, candidate_url: str) -> bool:
    """SSRF protection: ensure candidate URL is same-origin as base.

    Rejects: different hostnames, non-HTTP schemes, protocol-relative URLs.
    """
    base_parsed = urlparse(base_url)
    cand_parsed = urlparse(candidate_url)

    if cand_parsed.scheme not in ("http", "https"):
        return False
    if cand_parsed.netloc != base_parsed.netloc:
        return False
    return True


def discover_subpages_from_links(
    base_url: str,
    internal_links: list[dict],
) -> list[str]:
    """Find contact/about pages from homepage links.

    Searches internal_links for anchor text matching CONTACT_KEYWORDS
    and ABOUT_KEYWORDS. Returns up to 2 discovered URLs.

    FALLBACK BEHAVIOR (additive, cap-aware): After link-based discovery,
    appends hardcoded paths that were NOT already found via links, up to
    the 2-subpage cap. If links already found 2 pages, hardcoded paths
    are skipped. This prevents missing /contact pages not linked from
    the homepage while respecting cost controls.

    Args:
        base_url: The homepage URL (for urljoin on relative hrefs).
        internal_links: List of {"href": str, "text": str} from CrawlResult.links["internal"].

    Returns:
        List of subpage URLs to crawl (max 2, does NOT include base_url).
    """
    found: list[str] = []
    found_contact = False
    found_about = False

    for link in internal_links:
        text = (link.get("text") or "").lower().strip()
        href = link.get("href", "")
        if not text or not href:
            continue

        resolved = urljoin(base_url, href)

        # SSRF protection: same-origin only
        if not _is_same_origin(base_url, resolved):
            continue

        # Check contact keywords
        if not found_contact and any(kw in text for kw in CONTACT_KEYWORDS):
            found.append(resolved)
            found_contact = True

        # Check about keywords
        if not found_about and any(kw in text for kw in ABOUT_KEYWORDS):
            if resolved not in found:
                found.append(resolved)
            found_about = True

        if found_contact and found_about:
            break

    # ADDITIVE FALLBACK: append hardcoded paths not already discovered
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    for path in CONTACT_SUBPATHS:
        candidate = urljoin(origin, path)
        if candidate not in found and len(found) < 2:
            found.append(candidate)

    return found[:2]  # Hard cap at 2 subpages


def discover_subpages(base_url: str) -> list[str]:
    """Fallback: Generate subpage URLs from hardcoded paths.

    Used when no CrawlResult links are available (e.g., homepage crawl failed).
    Unchanged from existing implementation.
    """
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    urls = [base_url]
    for path in CONTACT_SUBPATHS:
        candidate = urljoin(origin, path)
        if candidate not in urls:
            urls.append(candidate)
    return urls
```

### Research Insights (Crawl4AI Links)

**CrawlResult.links["internal"] structure (confirmed from source):**
```python
[{"href": "/contact", "text": "Contact Us", "title": "...", "base_domain": "example.com", "context": "..."}, ...]
```

**Reliability findings:**
- Server-rendered sites: reliable (extraction uses lxml XPath on rendered DOM)
- JS-heavy SPAs: may miss links not yet rendered at DOM snapshot time
- `excluded_tags=["nav", "footer", "aside", "header"]` does NOT affect link extraction (links are extracted from the full DOM before tag exclusion applies to content)

**Config improvement for reliable link extraction:**
```python
def get_run_config() -> CrawlerRunConfig:
    return CrawlerRunConfig(
        extraction_strategy=get_strategy(),
        cache_mode=CacheMode.BYPASS,
        page_timeout=15000,
        wait_until="networkidle",      # CHANGED from domcontentloaded -- waits for JS
        delay_before_return_html=2.0,
        scan_full_page=True,           # NEW -- catches lazy-loaded nav links
        excluded_tags=["nav", "footer", "aside", "header"],
        remove_overlay_elements=True,
    )
```

**Why `networkidle` over `domcontentloaded`:** The old setting fires when HTML is parsed but before async JS completes. Venue sites with React/JS nav menus may not have rendered their `<a>` tags yet. `networkidle` waits until no network requests for 500ms -- catches JS-loaded navigation.

---

### Module 3: export.py (CSV Export with Sanitization)

```python
"""export.py -- JSON results -> sanitized CSV outreach list.

Applies formula injection prevention on all cells.
Skips venues with no email AND no phone (not actionable for outreach).
"""
from __future__ import annotations

import csv
from pathlib import Path

OUTREACH_COLUMNS = ["name", "email", "phone", "website", "venue_type"]


def sanitize_cell(value: str | None) -> str:
    """Prevent CSV formula injection.

    1. Strips control characters (tab, carriage return, newline)
    2. Prefixes cells starting with =, -, +, @, or | with a single quote

    (see: lead-scraper solution doc + liverequest CSV export lesson)
    """
    if not value:
        return ""
    # Strip control characters that can break cell boundaries
    value = value.strip()
    value = value.replace("\t", " ").replace("\r", "").replace("\n", " ")
    if value and value[0] in "=-+@|":
        return "'" + value
    return value


def export_outreach_csv(results: list[dict], output_path: Path) -> int:
    """Write venue results as a sanitized CSV outreach list.

    Args:
        results: List of VenueData dicts (from model_dump).
        output_path: Full path to output CSV file.

    Returns:
        Number of rows written (excluding header).
        Creates file with header even if zero rows qualify.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTREACH_COLUMNS)
        writer.writeheader()

        for venue in results:
            email = venue.get("email")
            phone = venue.get("phone")

            # Skip venues with no contact info (not actionable)
            if not email and not phone:
                continue

            row = {
                "name": sanitize_cell(venue.get("name")),
                "email": sanitize_cell(email),
                "phone": sanitize_cell(phone),
                "website": sanitize_cell(venue.get("source_url") or venue.get("website")),
                "venue_type": sanitize_cell(venue.get("venue_type")),
            }
            writer.writerow(row)
            rows_written += 1

    print(f"[export] Wrote {rows_written} venues to {output_path}")
    return rows_written
```

### Research Insights (CSV Security)

**Additional sanitization:** Control characters `\t`, `\r`, `\n` are stripped because they can break cell boundaries in some spreadsheet parsers. A venue name like `Studio\t=HYPERLINK(...)` would inject into the next column without this protection.

**Encoding:** UTF-8 without BOM (Python default). Excel on Windows may not auto-detect UTF-8, but this is acceptable for the outreach use case (Google Sheets handles UTF-8 correctly).

**Empty results:** File is always created with headers (even if zero rows). This prevents downstream confusion about whether the export ran.

---

### Module 4: scrape.py CLI Updates

**Argument architecture (RESOLVED):**

The existing mutually exclusive group `(urls_file | --url)` is expanded to include the new search options:

```python
# Replace existing mutually exclusive group with expanded one:
source = parser.add_mutually_exclusive_group(required=True)
source.add_argument("urls_file", nargs="?", type=Path, help="File with one URL per line")
source.add_argument("--url", type=str, help="Scrape a single URL")
source.add_argument("--search", type=str, metavar="QUERY",
    help="Search Google for venue URLs (uses SerpAPI)")
source.add_argument("--search-film", action="store_true",
    help="Run predefined film-venue searches for San Diego")

# Separate (non-exclusive) output flag:
parser.add_argument("--csv", action="store_true",
    help="Also export results as outreach CSV")
```

**This means:**
- Exactly ONE source: `urls_file` OR `--url` OR `--search` OR `--search-film`
- `--csv` can combine with any source
- `--contacts-only` and `--csv` are independent (both can be used)
- No merging of sources needed -- simpler than additive approach

**Updated pipeline flow (FINAL -- single-pass):**

```python
async def main(urls: list[str], output_dir: Path, contacts_only: bool = False, csv_export: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    errors: list[dict] = []

    # Apply 15-URL cap
    if len(urls) > 15:
        print(f"  Found {len(urls)} URLs, capping at 15.")
        urls = urls[:15]

    async with AsyncWebCrawler(config=get_browser_config()) as crawler:
        for start_url in urls:
            # SINGLE-PASS: crawl homepage WITH extraction, then use links for subpages
            homepage_results = await crawler.arun_many(
                urls=[start_url], config=get_run_config(), dispatcher=get_dispatcher()
            )
            homepage_result = homepage_results[0]

            page_venues = []

            # Extract from homepage
            if homepage_result.success and homepage_result.extracted_content:
                venue = validate_extraction(homepage_result.extracted_content, homepage_result.url)
                if venue:
                    page_venues.append(venue)
                    print(f"    OK: {homepage_result.url}")

            # Discover subpages from homepage links
            internal_links = homepage_result.links.get("internal", []) if homepage_result.success else []
            subpages = discover_subpages_from_links(start_url, internal_links)

            # Crawl subpages
            if subpages:
                subpage_results = await crawler.arun_many(
                    urls=subpages, config=get_run_config(), dispatcher=get_dispatcher()
                )
                for result in subpage_results:
                    if result.success and result.extracted_content:
                        venue = validate_extraction(result.extracted_content, result.url)
                        if venue:
                            page_venues.append(venue)
                            print(f"    OK: {result.url}")

            # Merge pages into one result
            if page_venues:
                merged = merge_venue_results(page_venues)
                if merged:
                    merged.source_url = start_url
                    results.append(merged.model_dump(mode="json"))
            else:
                errors.append({"url": start_url, "error": "No data from any page"})
                print(f"  FAIL: {start_url}", file=sys.stderr)

    # Write standard output (existing behavior)
    # ... (unchanged JSON/JSONL writing logic)

    # CSV export (new)
    if csv_export and results:
        from export import export_outreach_csv
        export_outreach_csv(results, output_dir / "outreach.csv")
```

**Env var validation (USAGE-TIME, not import-time):**

```python
if __name__ == "__main__":
    # ANTHROPIC_API_KEY always required
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    # SERPAPI_API_KEY only required if using search
    if (args.search or args.search_film) and not os.environ.get("SERPAPI_API_KEY"):
        print("Error: SERPAPI_API_KEY not set. Required for --search/--search-film.", file=sys.stderr)
        sys.exit(1)
```

**15-URL cap behavior:**
- Applied AFTER deduplication, BEFORE crawling
- Takes first N (preserves SerpAPI ranking order)
- Prints message: `"Found {N} URLs, capping at 15."`
- Uncapped URLs are NOT saved (user can re-run; keeps it simple)

## What Must Not Change

- Existing `urls.txt` + `--url` input paths must continue working unchanged
- `validate_extraction()` and `merge_venue_results()` in models.py are NOT modified
- `results.json` and `contacts.jsonl` output formats remain the same
- Cost controls: 15 URL cap per run, 3 concurrency limit, CacheMode.BYPASS
- Test fixtures and existing tests pass without modification

## Acceptance Tests

### Happy Path

- WHEN `--search-film` flag is used THE SYSTEM SHALL call SerpAPI with 4 predefined queries and return 20-40 deduplicated venue URLs (capped at 15 for crawling)
- WHEN a homepage has a link with text "Contact Us" THE SYSTEM SHALL discover that URL and crawl it for contact extraction
- WHEN `--csv` flag is used THE SYSTEM SHALL write `{output_dir}/outreach.csv` with columns name, email, phone, website, venue_type
- WHEN a venue has no email AND no phone THE SYSTEM SHALL exclude it from the CSV output
- WHEN `--search-film --csv` flags are combined THE SYSTEM SHALL run the full pipeline: search -> scrape -> CSV
- WHEN search returns more than 15 URLs THE SYSTEM SHALL crawl only the first 15 and print "Found N URLs, capping at 15."
- WHEN link-based discovery finds /team but site also has /contact (hardcoded) THE SYSTEM SHALL crawl both (additive fallback)

### Error Cases

- WHEN SERPAPI_API_KEY is not set and --search-film is used THE SYSTEM SHALL exit with error "SERPAPI_API_KEY not set. Required for --search/--search-film."
- WHEN SerpAPI returns HTTP 429 THE SYSTEM SHALL print "RATE LIMIT: quota exhausted" and return empty list (pipeline exits with "No URLs found")
- WHEN homepage crawl fails (no links available) THE SYSTEM SHALL fall back to hardcoded /contact + /about subpaths
- WHEN a CSV cell starts with = or - THE SYSTEM SHALL prefix it with a single quote
- WHEN a CSV cell contains \t or \r characters THE SYSTEM SHALL replace them with space/empty
- WHEN a discovered link resolves to a different origin THE SYSTEM SHALL reject it (SSRF protection)
- WHEN all search results are filtered as directory sites THE SYSTEM SHALL exit with "No URLs found"

### Verification Commands

```bash
# Unit tests pass
cd /Users/alejandroguillen/Projects/sandbox/venue-scraper && python -m pytest tests/ -v

# Syntax check on new files
python -c "import ast; ast.parse(open('discover.py').read())"
python -c "import ast; ast.parse(open('export.py').read())"

# CSV export produces valid output (after a scrape)
python scrape.py urls.txt --csv --output results/ && head -5 results/outreach.csv

# Search discovery returns URLs (requires SERPAPI_API_KEY)
python -c "from discover import search_film_venues; print(search_film_venues()[:5])"

# SSRF protection test
python -c "
from crawler import _is_same_origin
assert _is_same_origin('https://example.com', 'https://example.com/contact') == True
assert _is_same_origin('https://example.com', 'https://evil.com/contact') == False
assert _is_same_origin('https://example.com', 'file:///etc/passwd') == False
print('SSRF checks pass')
"

# CSV sanitization test
python -c "
from export import sanitize_cell
assert sanitize_cell('=1+1') == \"'=1+1\"
assert sanitize_cell('Normal') == 'Normal'
assert sanitize_cell('Tab\there') == 'Tab here'
assert sanitize_cell(None) == ''
print('Sanitization checks pass')
"
```

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Single-pass crawl breaks existing main loop | Medium | Existing `urls.txt` tests validate old path. New code is additive. |
| SerpAPI returns mostly directory sites | Low | DIRECTORY_DOMAINS filter; verified with web search that real venue URLs come back |
| Link-text matching misses non-English pages | Low | SD venues are English; additive fallback always tries hardcoded paths |
| `CrawlResult.links` empty for JS-heavy sites | Medium | `networkidle` wait + additive fallback covers this. Verified Crawl4AI extracts from rendered DOM. |
| SSRF via malicious link in homepage | Low | `_is_same_origin()` validation on every discovered URL |
| SerpAPI legal uncertainty (Google lawsuit) | Low | Service operational; 4 queries/run is negligible usage. Can swap to DuckDuckGo if needed. |

## Security Requirements

- [x] API key via env var, validated at usage-time only
- [x] Never log request URLs (would expose API key in query params)
- [x] Same-origin validation on all discovered links (`_is_same_origin()`)
- [x] CSV formula injection prevention with control character stripping
- [x] URL scheme validation on search results (http/https only)
- [x] Request timeout (10s) on all external HTTP calls
- [x] Output filename hardcoded (not data-driven -- no path traversal)

## New Dependencies

```
# Add to requirements.txt
requests>=2.28.0  # For SerpAPI HTTP calls
```

## File Inventory

| File | Action | Purpose |
|------|--------|---------|
| `discover.py` | CREATE | SerpAPI search -> URL list (with disk caching) |
| `export.py` | CREATE | JSON results -> sanitized CSV |
| `crawler.py` | MODIFY | Add `discover_subpages_from_links()`, `_is_same_origin()`, keep existing function. Change `wait_until` to `networkidle`, add `scan_full_page=True`. |
| `scrape.py` | MODIFY | Expand mutually exclusive group with --search/--search-film. Add --csv flag. Refactor main loop to single-pass. |
| `requirements.txt` | MODIFY | Add `requests>=2.28.0` |
| `tests/test_discover.py` | CREATE | Mock SerpAPI responses, test URL filtering, directory site detection |
| `tests/test_export.py` | CREATE | Test CSV output, sanitization (including control chars), skip logic |
| `tests/test_crawler_links.py` | CREATE | Test link-based discovery with mock links, SSRF rejection, additive fallback |
| `tests/fixtures/serpapi_response.json` | CREATE | Captured SerpAPI response for testing without API calls |
| `tests/fixtures/internal_links.json` | CREATE | Mock CrawlResult.links["internal"] for link discovery tests |
| `.gitignore` | MODIFY | Add `serpapi_cache/` |

## Sources & References

- **Origin brainstorm:** [docs/brainstorms/2026-05-05-venue-scraper-low-effort-upgrades-brainstorm.md](docs/brainstorms/2026-05-05-venue-scraper-low-effort-upgrades-brainstorm.md) -- Key decisions: SerpAPI, SD-only, film venues, link parsing with hardcoded fallback, outreach CSV format
- **Venue scraper solution doc:** `docs/solutions/2026-05-05-venue-scraper-llm-extraction-pipeline.md` -- Cost control patterns, merge logic, CacheMode.BYPASS
- **Lead scraper solution doc:** `docs/solutions/2026-04-15-lead-scraper-multi-source-pipeline.md` -- normalize()/scrape() split, CSV safety patterns
- **Lead scraper enrichment doc:** `docs/solutions/2026-04-16-lead-scraper-enrichment-expansion.md` -- External API integration, SSRF post-redirect validation
- **CrawlResult.links structure:** `venv/lib/python3.14/site-packages/crawl4ai/models.py:137` -- `Dict[str, List[Dict]]` with `{"href": str, "text": str}` entries
- **SerpAPI docs:** serpapi.com/search-api (organic results structure, location parameter, error codes)
- **Crawl4AI link extraction:** docs.crawl4ai.com/core/link-media/ (lxml-based extraction from rendered DOM)
- **Security:** CSV formula injection (OWASP), SSRF via URL following (lead-scraper enrichment lesson)

## Feed-Forward

- **Hardest decision:** Whether to make the hardcoded fallback additive (always try /contact + /about even when links found something) or exclusive (only fallback on zero matches). Chose additive -- prevents data loss at cost of max 1-2 extra requests per venue.
- **Rejected alternatives:** Two-phase double-crawl (wasteful), expanding hardcoded list to 8+ paths (cost regression), BeautifulSoup for link parsing (Crawl4AI provides links natively), import-time API key validation (breaks non-search users).
- **Least confident:** Whether `networkidle` wait significantly increases crawl time. Could add 2-5 seconds per venue vs `domcontentloaded`. For 15 venues, that is 30-75 extra seconds total -- acceptable, but monitor.
