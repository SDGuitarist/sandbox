---
title: "feat: Lead Scraper Expansion — New Sources + Enrichment Pipeline"
type: feat
status: active
date: 2026-04-16
origin: docs/brainstorms/2026-04-16-lead-scraper-expansion-brainstorm.md
deepened: 2026-04-16
agents_used: 7 (kieran-python-reviewer, security-sentinel, performance-oracle, architecture-strategist, data-migration-expert, code-simplicity-reviewer, framework-docs-researcher)
feed_forward:
  risk: "Tier 1 enrichment may yield little from platform pages (Eventbrite, Facebook) — test manually before full build"
  verify_first: true
---

# feat: Lead Scraper Expansion — New Sources + Enrichment Pipeline

## Enhancement Summary

**Deepened on:** 2026-04-16
**Agents used:** 7 parallel reviewers
**Key changes from deepening:**

1. **Simplified from 3 tiers to 1** — Build Tier 1 (HTTP fetch + parse) only. Defer Maigret and Apify contact scraper until Tier 1 is tested on real data. (simplicity-reviewer)
2. **Cut from 9 columns to 3** — Add phone, website, enriched_at only. email already exists. Social URLs, company, job_title deferred. (simplicity-reviewer)
3. **Facebook normalize keeps single-return contract** — Use extract_leads_from_post() internally, keep normalize() returning NormalizedLead | None. (python-reviewer, architecture-strategist)
4. **Security: create .gitignore immediately** — .env with Apify token has no git protection. (security-sentinel)
5. **Migration: wire migrate_db() into init_db()** — Original plan defined the function but never called it. (data-migration-expert)
6. **ingest.py must include website in INSERT** — Otherwise Eventbrite website_url is silently dropped. (python-reviewer, migration-expert, architecture-strategist)
7. **Simple for-loop enrichment, not ThreadPoolExecutor** — 361 leads at ~2s each = ~12 min. Not worth threading complexity. (simplicity-reviewer, performance-oracle)

---

## Overview

Expand the lead scraper from 1 working source (Eventbrite, 361 leads) to 3 sources (+ Facebook Groups, Instagram), and add HTTP-based contact enrichment that follows profile links to extract emails and phones.

(see brainstorm: docs/brainstorms/2026-04-16-lead-scraper-expansion-brainstorm.md)

## Problem Statement / Motivation

The scraper collects organizer names and profile URLs but no contact info. Without emails or phones, the only outreach path is manually visiting each profile. Enrichment automates this — following the chain of links each lead published (profile -> website -> contact page) to build actionable contact records.

## What Exactly Is Changing

1. **Schema:** 3 new columns on leads table (phone, website, enriched_at). email already exists.
2. **Scrapers:** Facebook rewrite (posts/comments format), Instagram new module
3. **Enrichment:** New `enrich.py` + `enrich_parsers.py` — HTTP fetch + HTML parse
4. **CLI:** New `enrich` subcommand, update export fieldnames
5. **UI:** Show email/phone/website in table
6. **Export:** CSV includes new columns
7. **Dependencies:** requests, beautifulsoup4
8. **Security:** .gitignore, URL validation for website field

## What Must Not Change

- Existing 361 leads must survive schema migration with no data loss
- `normalize() -> NormalizedLead | None` contract for all scrapers
- Single-writer pattern: ingest.py owns INSERT, enrich.py owns UPDATE (enrichment columns only)
- SQLite WAL mode, dedup via UNIQUE(source, profile_url)
- All 28 existing tests must continue passing
- Flask UI remains functional throughout

## Proposed Solution

### Architecture

```
SCRAPE → INGEST → AUTO-ENRICH (HTTP fetch, free) → DB

           ┌─ Eventbrite (existing, now extracts website_url)
  scrape ──┤─ Facebook (rewrite: posts/comments)
           └─ Instagram (new: hashtag search)
              │
              ▼
         ingest_leads()  ← single writer, INSERT OR IGNORE
              │
              ▼
         enrich_leads()  ← new module, UPDATE only
              │
         HTTP fetch profile_url + website
         Parse HTML: mailto:, tel: links
         Schema.org JSON-LD sameAs (for website discovery)
              │
              ▼
         UPDATE leads SET email=..., phone=..., enriched_at=NOW
         (only columns that are currently NULL)
```

### Data Ownership

| Column Group | Writer | Reader(s) |
|---|---|---|
| name, bio, location, profile_url, activity, source | ingest.py | enrich.py, app.py, run.py |
| website | ingest.py (from Eventbrite organizer data) | enrich.py (populates if NULL) |
| email, phone, enriched_at | enrich.py only | app.py, run.py |

`website` is an ingest-phase column. enrich.py only writes to it when it's NULL (for non-Eventbrite leads where the website is discovered via HTML parsing).

## Technical Approach

### Implementation Phases

#### Phase 1: New Sources + Schema (foundation)

**Goal:** 3 sources producing leads, schema supports enrichment, .gitignore exists.

**Files changed:**

Security (do first):
- `.gitignore` — **CREATE IMMEDIATELY**: .env, *.db, __pycache__/, .venv/, *.csv

Schema + migration:
- `schema.sql` — add phone, website, enriched_at to CREATE TABLE
- `db.py` — add `migrate_db()` with backup, call from `init_db()`

Scraper contract update:
- `scrapers/__init__.py` — add `website: str | None` to NormalizedLead TypedDict
- `ingest.py` — **add website to INSERT statement** (critical: without this, website_url is silently dropped)
- All existing scrapers (eventbrite, meetup, facebook, linkedin) — add `website=None` to normalize() return

Eventbrite enhancement:
- `scrapers/eventbrite.py` — extract `website_url` from primary_organizer during normalize

Facebook rewrite:
- `scrapers/facebook.py` — rewrite for posts/comments format. Keep `normalize()` returning single lead (post author). Add `extract_leads_from_post()` for multi-lead extraction. `scrape()` calls `extract_leads_from_post()` and flattens.

Instagram new:
- `scrapers/instagram.py` — new module with normalize() + scrape()
- `config.py` — add Instagram source, update Facebook groups list
- `run.py` — add instagram to scraper_map
- `models.py` — add "instagram" to VALID_SOURCES

Tests:
- `tests/fixtures/facebook_raw.json` + `facebook_normalized.json` — real posts/comments format
- `tests/fixtures/instagram_raw.json` + `instagram_normalized.json`
- `tests/test_normalization.py` — update Facebook tests, add Instagram tests

**Migration strategy:**
```python
# db.py
import re
import shutil
from datetime import datetime

_SAFE_IDENTIFIER = re.compile(r"^[a-z_]+$")

def migrate_db(db_path: Path = DB_PATH) -> None:
    """Add enrichment columns to existing leads table. Idempotent."""
    if db_path.exists():
        backup = db_path.with_suffix(
            f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
        )
        shutil.copy2(db_path, backup)

    new_columns = [
        ("phone", "TEXT"),
        ("website", "TEXT"),
        ("enriched_at", "TEXT"),
    ]
    with get_db(db_path) as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
        for col_name, col_type in new_columns:
            assert _SAFE_IDENTIFIER.match(col_name), f"Bad column: {col_name}"
            if col_name not in existing:
                conn.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")

def init_db(db_path: Path = DB_PATH) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    with get_db(db_path) as conn:
        conn.executescript(schema_path.read_text())
    migrate_db(db_path)  # Ensure existing DBs get new columns
```

**Facebook scraper — preserving normalize() contract:**

```python
# scrapers/facebook.py

def normalize(raw_item: dict) -> NormalizedLead | None:
    """Normalize the post author. Maintains single-return contract."""
    author_name = raw_item.get("name") or raw_item.get("userName")
    author_url = raw_item.get("profileUrl") or raw_item.get("url")
    if not author_name or not author_url:
        return None
    return NormalizedLead(
        name=author_name,
        bio=(raw_item.get("text") or "")[:200],
        location=None,
        email=None,
        website=None,
        profile_url=author_url,
        activity=f"Posted in: {raw_item.get('groupTitle', '')}",
        source="facebook",
    )

def _normalize_commenter(comment: dict, group_title: str) -> NormalizedLead | None:
    """Normalize a single commenter from a Facebook post."""
    # ... extract name + profile URL from comment ...

def extract_leads_from_post(raw_item: dict) -> list[NormalizedLead]:
    """Extract all leads (author + commenters) from a single post."""
    leads: list[NormalizedLead] = []
    author = normalize(raw_item)
    if author:
        leads.append(author)
    for comment in raw_item.get("topComments", []):
        commenter = _normalize_commenter(comment, raw_item.get("groupTitle", ""))
        if commenter:
            leads.append(commenter)
    return leads

def scrape(location: str, config: dict) -> list[NormalizedLead]:
    from scrapers._apify_helpers import run_actor
    run_input = {"startUrls": [{"url": url} for url in config.get("groups", [])]}
    raw_items = run_actor(config["actor"], run_input)
    leads: list[NormalizedLead] = []
    for item in raw_items:
        leads.extend(extract_leads_from_post(item))
    return leads
```

**ingest.py INSERT update (critical):**
```python
# Must include website in INSERT — otherwise Eventbrite website_url is silently dropped
conn.execute(
    """INSERT OR IGNORE INTO leads
       (name, bio, location, email, website, profile_url, activity, source)
       VALUES (:name, :bio, :location, :email, :website, :profile_url, :activity, :source)""",
    lead,
)
```

#### Phase 1.5: Verify Enrichment Viability (gate)

**Before building Phase 2**, manually test Tier 1 on 5 real leads:

```bash
# Pick 5 Eventbrite organizers who have website_url
sqlite3 leads.db "SELECT id, name, website FROM leads WHERE website IS NOT NULL LIMIT 5"
# Fetch each website and check: does it have a mailto: link? A phone number? Social links?
curl -s <website_url> | grep -i 'mailto:\|tel:\|@.*\.com'
```

**Gate criteria:** If 2+ out of 5 websites yield at least an email, proceed with Phase 2. If 0-1 yield anything, reconsider the enrichment approach (e.g., skip enrichment, or evaluate Maigret from the Deferred section).

#### Phase 2: Enrichment

**Goal:** Automatic HTTP-based enrichment after scraping. Standalone `enrich` command for existing leads.

**enrich.py — simple for-loop, no threading:**

```python
from dataclasses import dataclass

@dataclass
class EnrichmentResult:
    leads_processed: int
    emails_found: int
    phones_found: int

def enrich_leads(*, db_path: Path = DB_PATH) -> EnrichmentResult:
    """Enrich unenriched leads by fetching their profile/website pages."""
    leads = _get_unenriched_leads(db_path)
    result = EnrichmentResult(0, 0, 0)

    for i, lead in enumerate(leads, 1):
        print(f"  {i}/{len(leads)} {lead['name'][:40]}...", end=" ", flush=True)
        try:
            updates = _enrich_single_lead(lead)
            _persist_enrichment(lead["id"], updates, db_path)
            if updates.get("email"):
                result.emails_found += 1
            if updates.get("phone"):
                result.phones_found += 1
            result.leads_processed += 1
            print("OK")
        except Exception as e:
            print(f"FAILED: {str(e)[:80]}")

    return result
```

**enrich_parsers.py — pure functions, independently testable:**

```python
@dataclass
class ParsedContactInfo:
    emails: list[str]
    phones: list[str]
    website: str | None
    # Future: social_urls, company, job_title

def parse_profile_page(html: str, url: str) -> ParsedContactInfo:
    """Extract contact info from HTML. Pure function, no I/O."""
    # BeautifulSoup with SoupStrainer for efficiency
    # Extract: mailto: links, tel: links
    # Check Schema.org JSON-LD sameAs
    # Validate emails with basic regex
    # Validate phones (strip non-digits, check 7-15 digits)
```

**Security: URL validation before HTTP fetch:**
```python
import socket
from urllib.parse import urlparse

_PRIVATE_RANGES = [...]  # 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, etc.

def _is_safe_url(url: str) -> bool:
    """Block SSRF: validate HTTPS and reject private IPs."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    try:
        ip = socket.getaddrinfo(parsed.hostname, None)[0][4][0]
        return not any(ipaddress.ip_address(ip) in net for net in _PRIVATE_RANGES)
    except (socket.gaierror, ValueError):
        return False
```

**HTTP fetching with requests.Session:**
```python
MAX_RESPONSE_BYTES = 1_000_000  # 1 MB cap

def _fetch_page(session: requests.Session, url: str) -> str | None:
    """Fetch a URL with timeout, size cap, and SSRF protection."""
    if not _is_safe_url(url):
        return None
    resp = session.get(url, timeout=10, stream=True)
    content = resp.raw.read(MAX_RESPONSE_BYTES)
    resp.close()
    return content.decode("utf-8", errors="replace")
```

**Files changed:**
- `enrich.py` — orchestration: fetch leads, call parsers, persist results
- `enrich_parsers.py` — pure functions: HTML -> ParsedContactInfo
- `run.py` — add `enrich` subcommand, wire auto-enrich after scrape, update export fieldnames
- `app.py` — update template context with new columns
- `templates/index.html` — show email/phone/website
- `requirements.txt` — add requests, beautifulsoup4
- `utils.py` — update sanitize_csv_cell to strip \t \r \n
- `tests/test_enrich.py` — unit tests for HTML parsing
- `tests/fixtures/enrich_website.html` — sample HTML for parser testing

## Acceptance Tests

### Happy Path
- WHEN a user runs `python run.py scrape --location "San Diego, CA"` on an existing database THE SYSTEM SHALL migrate the schema, scrape all enabled sources, ingest leads, and auto-enrich without data loss
- WHEN a user runs `python run.py enrich` THE SYSTEM SHALL enrich all leads where enriched_at IS NULL
- WHEN Eventbrite organizer data includes a website_url THE SYSTEM SHALL save it to the website column during ingest
- WHEN a lead's profile website contains a mailto: link THE SYSTEM SHALL extract and store the email address
- WHEN a user exports to CSV THE SYSTEM SHALL include phone, website, enriched_at columns with empty values for unenriched leads

### Error Cases
- WHEN an HTTP fetch times out (>10s) THE SYSTEM SHALL log the timeout and continue to the next lead
- WHEN a Facebook group is private THE SYSTEM SHALL log a warning and return 0 leads (not crash)
- WHEN Instagram hashtag search returns profiles without San Diego in their bio THE SYSTEM SHALL include them (false positive is acceptable)
- WHEN a lead's profile_url points to a private IP or non-HTTPS URL THE SYSTEM SHALL skip enrichment for that lead (SSRF protection)

### Verification Commands
- `python -m pytest tests/ -v` — all tests pass (existing 28 + new)
- `python run.py scrape --location "San Diego, CA"` — scrapes + enriches without error
- `python run.py enrich` — enriches existing leads
- `python run.py export --output leads.csv && head -1 leads.csv` — CSV header includes new columns
- `sqlite3 leads.db "SELECT COUNT(*) FROM leads WHERE enriched_at IS NOT NULL"` — shows enriched count

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Tier 1 yields little from platform pages | High | Eventbrite website_url is the real prize; test on 5 leads manually first |
| Facebook groups are private | Low | Both identified groups appear public; log warning if blocked |
| Instagram 100/run limit exhausts quickly | Medium | Batch hashtags across runs, cap per session |
| Schema migration fails on existing DB | Low | ALTER TABLE safe on SQLite; auto-backup before migration |

## New Dependencies

```
# requirements.txt additions
requests>=2.31
beautifulsoup4>=4.12
```

## Deferred (build if Tier 1 proves insufficient)

These were in the original brainstorm but cut during deepening per YAGNI:

- **Tier 2: Maigret OSINT** — username lookup across 3100+ sites. Heavy dependency, 60s/lead, legal concerns. Only build if Tier 1 enrichment hit rate is <30%.
- **Tier 3: Apify contact scraper** — paid API ($0.002/page). Only build if Tiers 1+2 insufficient.
- **Additional columns:** instagram_url, twitter_url, linkedin_url, company, job_title, enrichment_status. Add when there's actual data to populate them.
- **ThreadPoolExecutor parallelism** — add when enrichment takes >15 minutes.
- **has-email/has-phone UI filters** — add when enough enriched data exists to filter.

## Security Checklist (from security-sentinel review)

- [ ] Create .gitignore (.env, *.db, __pycache__/, .venv/, *.csv)
- [ ] Rotate Apify token (exposed in session)
- [ ] HTTPS-only + private-IP blocking for enrichment HTTP fetches
- [ ] Validate extracted emails with basic regex before storage
- [ ] Strip \t, \r, \n from CSV cells (enrichment data)
- [ ] website field validated before HTTP fetch (same as profile_url)

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-04-16-lead-scraper-expansion-brainstorm.md](docs/brainstorms/2026-04-16-lead-scraper-expansion-brainstorm.md) — Key decisions: waterfall enrichment (free first), skip Twitter, follow-the-links matching, in-place columns

### Internal References
- Prior build: `docs/solutions/2026-04-15-lead-scraper-multi-source-pipeline.md`
- Data ownership pattern: `docs/solutions/2026-03-30-chain-reaction-inter-service-contracts.md`
- Scraper contract: `lead-scraper/scrapers/__init__.py` (NormalizedLead TypedDict)
- Single-writer pattern: `lead-scraper/ingest.py`

### External References
- Apify Instagram Profile Scraper: apify/instagram-profile-scraper
- Apify Facebook Groups Scraper: apify/facebook-groups-scraper

### Deepening Review Findings
- **Python reviewer:** Facebook normalize contract break (fixed: Option B), migrate_db SQL injection (fixed: regex validation), ingest.py missing website INSERT (fixed), enrich_parsers.py extraction (adopted)
- **Security sentinel:** No .gitignore (fixed), SSRF in HTTP fetch (fixed: URL validation), CSV sanitization gaps (fixed: strip \t\r\n)
- **Performance oracle:** Batch DB writes, requests.Session pooling, SoupStrainer for BS4, 1MB response cap (all adopted)
- **Architecture strategist:** website dual-writer (fixed: ingest owns, enrich only if NULL), Facebook contract (fixed: Option B)
- **Data migration expert:** migrate_db never called (fixed: wired into init_db), backup before migration (adopted), schema.sql must match (noted)
- **Simplicity reviewer:** Cut 3 tiers to 1, 9 columns to 3, drop Maigret + ThreadPoolExecutor (all adopted)

## Feed-Forward
- **Hardest decision:** Cutting Maigret and Tier 3. The brainstorm designed a 3-tier waterfall, but 6/7 reviewers flagged complexity concerns. Tier 1 alone (HTTP fetch + parse) covers the most valuable path — organizer website URLs. If hit rate is <30%, Tier 2 and 3 are documented and ready to build.
- **Rejected alternatives:** Twitter (bad free-tier pricing), queue-based enrichment (YAGNI), separate enrichment table (unnecessary joins), fuzzy name matching (low precision), 3-tier waterfall for v1 (over-engineered for 361 leads).
- **Least confident:** Tier 1 enrichment on Eventbrite organizer pages — these are templated platform pages that may not expose personal contact info. The `website_url` from organizer data is the real prize. **Verify first:** manually fetch 5 organizer pages and check what's extractable before building the full parser.
