---
title: "feat: Multi-Source Lead Scraper"
type: feat
status: active
date: 2026-04-15
origin: docs/brainstorms/2026-04-15-lead-scraper-brainstorm.md
feed_forward:
  risk: "Meetup/Eventbrite don't expose attendee data publicly — architecture shifts toward Apify-heavy"
  verify_first: true
deepened: 2026-04-15
agents_used: 10 (python-reviewer, security-sentinel, architecture-strategist, performance-oracle, code-simplicity-reviewer, pattern-recognition-specialist, data-integrity-guardian, best-practices-researcher, framework-docs-researcher, solution-doc-checker)
---

# feat: Multi-Source Lead Scraper

## Enhancement Summary

**Deepened on:** 2026-04-15
**Sections enhanced:** All major sections
**Agents used:** 10 parallel reviewers + researchers

### Key Improvements from Deepening
1. **Eventbrite search API deprecated** -- pivoted to Apify actor (all 4 sources now use Apify)
2. **NULL dedup trap fixed** -- `profile_url` now NOT NULL, prevents silent duplicate insertion
3. **Flask context conflict resolved** -- `get_db()` takes explicit path parameter, works in CLI and Flask
4. **YAGNI cuts applied** -- status tracking deferred to v2, collapsed to 2 phases, Phase 1 ships usable CSV
5. **Security hardened** -- CSV formula injection protection, debug=False default, profile URL validation
6. **Typed interface** -- `NormalizedLead` TypedDict replaces loose `dict` return type
7. **Batch performance** -- `executemany` in single transaction, not per-row inserts

### New Risks Discovered
- Eventbrite public search API deprecated since 2020 (shifted to Apify)
- SQLite UNIQUE constraint silently ignores NULL values (fixed with NOT NULL)
- CSV formula injection when opening exports in Excel/Sheets (mitigated with sanitization)

---

## Overview

A pipeline-architecture lead scraper that pulls creative professionals from 4 sources (Meetup, Eventbrite, Facebook, LinkedIn) via Apify actors, deduplicates them into a SQLite database, and provides a Flask web UI with CSV export. Designed to fill Amplify workshop seats and build a reusable lead generation tool for any city.

## Problem Statement / Motivation

29 seats remain for the April 25 Amplify AI workshop. Direct network outreach is nearly exhausted. A scraper that finds creative professionals across multiple platforms gives Alex a reusable pipeline for this and future workshops, audits, and outcome sprints. (see brainstorm: docs/brainstorms/2026-04-15-lead-scraper-brainstorm.md)

## Critical Research Findings

### Finding 1: Attendee data is gated (from brainstorm Feed-Forward)

**The brainstorm's Feed-Forward risk materialized.** Neither Meetup nor Eventbrite exposes attendee/member data without authentication.

### Finding 2: Eventbrite search API deprecated (from framework-docs-researcher)

**The Eventbrite public event search endpoint (`GET /v3/events/search/`) was deprecated in December 2019 and shut off February 2020.** The remaining API only supports org-scoped and venue-scoped queries, which require knowing the org/venue ID upfront. This eliminates Eventbrite as a "direct API" source.

### Revised Source Verdicts

| Platform | Event Listings | People Data | Verdict |
|----------|---------------|-------------|---------|
| Meetup | Public | Login required | Apify actor |
| Eventbrite | **API search deprecated** | Organizer auth only | **Apify actor** (changed from direct API) |
| Facebook | Via Apify | Via Apify | Apify actor |
| LinkedIn | Via Apify | Via Apify | Apify actor |

**Impact:** All 4 sources now use Apify actors. The original "direct scraping for learning" goal is replaced by "Apify client integration + data pipeline design" as the primary learning pattern. One shared Apify wrapper pattern serves all 4 scrapers.

## Proposed Solution

### Architecture: Pipeline with Shared Interface

Each source gets its own scraper module behind a common typed interface. All write to a shared SQLite database through a central ingestion layer (not directly -- lesson from solution doc on inter-service contracts).

```
lead-scraper/
  app.py              # Flask web UI + CSV export
  db.py               # get_db() + init_db(), canonical DB_PATH
  models.py           # Lead read queries + delete_lead() (no inserts)
  schema.sql          # CREATE TABLE leads
  ingest.py           # Central ingestion: validate + dedup + INSERT (only writer)
  scrapers/
    __init__.py       # NormalizedLead TypedDict
    _apify_helpers.py # Shared run_actor() wrapper
    meetup.py         # scrape() + normalize() per raw item
    eventbrite.py     # scrape() + normalize() per raw item
    facebook.py       # scrape() + normalize() per raw item
    linkedin.py       # scrape() + normalize() per raw item
  config.py           # Source configs, token validation, .env loader
  run.py              # CLI dispatcher (scrape + serve + export), calls init_db()
  requirements.txt
  .env                # APIFY_TOKEN (gitignored)
  .env.example        # Placeholder strings only, never real tokens
  tests/
    fixtures/         # Raw + normalized JSON per source (from Phase 0)
    test_normalization.py  # Fixture-based: raw → NormalizedLead
    test_ingest.py         # Fixture-based: validation + dedup
```

**Note:** `run.py` is a multi-command CLI dispatcher here, which departs from the sandbox convention where `run.py` is a one-liner Flask starter. This is deliberate -- a scraper needs both CLI and web entry points.

### Data Ownership (from solution doc: chain-reaction-inter-service-contracts)

| Component | Owns | Reads |
|-----------|------|-------|
| scrapers/*.py | Nothing -- returns list[NormalizedLead] | External APIs via Apify |
| ingest.py | leads table INSERT (single writer) | scrapers output |
| models.py | Read queries + `delete_lead(id)` (only DELETE path) | leads table |
| db.py | Connection lifecycle, PRAGMAs, schema bootstrap (`init_db()`) | SQLite file |
| app.py (Flask) | Nothing -- calls models for reads + deletes | leads table via models.py |

**Write Ownership Rules:**
- Scrapers never touch the database. They return typed dicts.
- `ingest.py` is the **only** file allowed to execute `INSERT` on the leads table.
- `models.py` exposes read queries and `delete_lead(id)`. No insert functions.
- `app.py` may call `models.delete_lead(id)` for PII compliance (CCPA). This is the only write operation outside `ingest.py`.

**Why DELETE is in scope despite not being in the brainstorm:** The security-sentinel review identified that storing real people's names, emails, and profile URLs without consent creates CCPA liability. Individual lead deletion is the minimum viable compliance feature. The brainstorm predates the security review -- this is a legitimate scope addition driven by a review finding, not scope creep. DELETE ownership is assigned to `models.py` (not `app.py` directly) to keep the SQL centralized.

### Scraper Interface Contract (from solution doc: swarm-scale-shared-spec)

```python
# scrapers/__init__.py
from typing import TypedDict

class NormalizedLead(TypedDict):
    name: str
    bio: str | None
    location: str | None
    email: str | None
    profile_url: str          # Required -- dedup key
    activity: str | None
    source: str               # Required -- dedup key
```

Every scraper module exposes two functions:

```python
# scrapers/eventbrite.py (example)

def normalize(raw_item: dict) -> NormalizedLead:
    """Convert one raw Apify result to a NormalizedLead.
    Tested independently via fixtures -- no Apify dependency."""
    ...

def scrape(location: str, config: dict) -> list[NormalizedLead]:
    """Run the Apify actor and normalize all results."""
    raw_items = run_actor(config["actor"], ...)
    return [normalize(item) for item in raw_items]
```

Splitting `normalize()` from `scrape()` is the key design decision from the Codex review: it makes the field mapping testable with fixtures (Phase 0 payloads) without hitting Apify.

**Sample output (Meetup):**

```json
{
  "name": "Jane Doe",
  "bio": "Filmmaker and AI enthusiast",
  "location": "San Diego, CA",
  "email": null,
  "profile_url": "https://meetup.com/members/12345",
  "activity": "Member of SD Film Collective, attended 3 events",
  "source": "meetup"
}
```

**Key rules:**
- Fields unavailable for a source return `null` (not omitted).
- `name`, `profile_url`, and `source` are always required (non-null).
- `scraped_at` is NOT in the scraper output -- the ingestion layer timestamps when it arrives.
- Each scraper receives only its own config slice, not the full `SOURCES` dict.

### Lead Field Registry (reference during implementation)

| Normalized Field | Meetup (Apify) | Eventbrite (Apify) | Facebook (Apify) | LinkedIn (Apify) |
|-----------------|----------------|---------------------|-------------------|-------------------|
| name | member.name | organizer.name | profile.name | firstName + lastName |
| bio | member.bio | event.description | profile.about | headline |
| location | member.city | venue.city | profile.location | locationName |
| email | member.email (rare) | organizer.email (rare) | null | null |
| profile_url | member.profileUrl | organizer.url | profile.url | profileUrl |
| activity | groups joined, RSVPs | events organized | group posts, comments | connections, activity |
| source | "meetup" | "eventbrite" | "facebook" | "linkedin" |

### Database Bootstrap and Connection Pattern

#### Path Ownership

The canonical database location is `lead-scraper/leads.db` (project-local, sibling to `app.py`). All entry points resolve the same absolute path:

```python
# db.py
from contextlib import contextmanager
from pathlib import Path
import sqlite3

# Canonical DB path: same directory as this file
DB_PATH = Path(__file__).parent / "leads.db"

@contextmanager
def get_db(db_path: Path = DB_PATH):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: Path = DB_PATH):
    """Create tables from schema.sql if they don't exist. Safe to call repeatedly."""
    schema_path = Path(__file__).parent / "schema.sql"
    with get_db(db_path) as conn:
        conn.executescript(schema_path.read_text())
```

**`DB_PATH` uses `Path(__file__).parent`** so it resolves to the same absolute path regardless of the caller's working directory. Both `run.py scrape` and `run.py serve` (Flask) import from `db.py` and get the same path.

#### Bootstrap Ownership

`db.py` owns schema initialization via `init_db()`. It is called:
- By `run.py` at startup (before scrape, export, or serve subcommands)
- `CREATE TABLE IF NOT EXISTS` makes it idempotent -- safe to call every run

No other module creates tables or runs DDL.

**Three PRAGMAs** (matching bookmark-manager + url_health_monitor patterns):
- `journal_mode=WAL` -- safe concurrent reads during Flask + CLI usage
- `foreign_keys=ON` -- future-proofs for related tables in v2
- `busy_timeout=5000` -- retries instead of immediate SQLITE_BUSY errors

### SQLite Schema

```sql
-- schema.sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    bio         TEXT,
    location    TEXT,
    email       TEXT,
    profile_url TEXT NOT NULL,
    activity    TEXT,
    source      TEXT NOT NULL,
    scraped_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    UNIQUE(source, profile_url)
);
```

**Research-driven schema decisions:**
- `profile_url TEXT NOT NULL` -- closes the NULL dedup trap (data-integrity review: SQLite UNIQUE ignores NULL values, so NULL profile_urls would bypass dedup silently)
- `strftime('%Y-%m-%d %H:%M:%S', 'now')` instead of `datetime('now')` -- matches sandbox timestamp convention
- `scraped_at` handled by schema DEFAULT, not scrapers -- ingestion layer stamps arrival time
- No indexes for v1 -- premature at hundreds of rows (simplicity review). Add when queries feel slow.
- No `status` column for v1 -- deferred to v2 (see YAGNI section below)
- `INSERT OR IGNORE` is the correct conflict resolution -- preserves original data, does not overwrite. Updated profiles from re-scrapes are NOT applied (conscious decision, manual refresh deferred to v2).

### Deduplication Strategy

**Primary dedup key:** `(source, profile_url)` -- UNIQUE constraint in schema. Same person from same source = `INSERT OR IGNORE` skips on conflict.

**Cross-source dedup:** Deferred to v2. Same person from Meetup and LinkedIn appears as two rows. The Flask UI shows source badges for manual identification.

**Why `INSERT OR IGNORE` over `INSERT OR REPLACE`:** REPLACE would delete and re-insert the row, losing any future columns like status or notes. IGNORE is safe -- original data wins.

### Ingestion Layer

```python
# ingest.py -- single writer, batch inserts
from db import get_db
from scrapers import NormalizedLead

REQUIRED_FIELDS = {"name", "profile_url", "source"}

def ingest_leads(leads: list[NormalizedLead]) -> tuple[int, int, int]:
    """Returns (inserted, skipped, invalid) counts."""
    inserted = skipped = invalid = 0
    valid_leads = []

    for lead in leads:
        # Validate required fields
        if not all(lead.get(f) for f in REQUIRED_FIELDS):
            invalid += 1
            continue
        # Validate profile_url is https
        if not lead["profile_url"].startswith("https://"):
            invalid += 1
            continue
        valid_leads.append(lead)

    with get_db() as conn:
        for lead in valid_leads:
            conn.execute(
                """INSERT OR IGNORE INTO leads
                   (name, bio, location, email, profile_url, activity, source)
                   VALUES (:name, :bio, :location, :email, :profile_url, :activity, :source)""",
                lead
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
            else:
                skipped += 1

    return inserted, skipped, invalid
```

**Key patterns:**
- Entire batch from one source in a single transaction (performance review: 100x faster than per-row commits)
- Validation before insert: reject leads missing required fields or with non-https URLs
- `INSERT OR IGNORE` handles dedup via UNIQUE constraint -- no separate SELECT needed
- Returns counts so `run.py` can report results per source

## Source Implementation Details

### All Sources: Shared Apify Wrapper Pattern

Since all 4 sources now use Apify, a shared helper reduces duplication:

```python
# scrapers/_apify_helpers.py
from apify_client import ApifyClient
from config import get_apify_token

def run_actor(actor_id: str, run_input: dict, timeout_secs: int = 300) -> list[dict]:
    """Run an Apify actor and return its dataset items."""
    client = ApifyClient(get_apify_token())
    run = client.actor(actor_id).call(
        run_input=run_input,
        timeout_secs=timeout_secs,
    )
    if run["status"] != "SUCCEEDED":
        raise RuntimeError(f"Apify actor {actor_id} failed: {run['status']}")
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())
```

### 1. Meetup (scrapers/meetup.py)

- **Actor:** `apify/meetup-scraper` or `datapilot/meetup-event-scraper`
- **What we get:** Group members, event RSVPs, member profiles
- **Config:** Group URLs to scrape

### 2. Eventbrite (scrapers/eventbrite.py)

- **Actor:** `aitorsm/eventbrite` or `parseforge/eventbrite-scraper`
- **What we get:** Event listings by keyword + city, organizer info
- **Config:** Search keywords, location
- **Note:** Switched from direct API to Apify because search endpoint was deprecated in 2020

### 3. Facebook (scrapers/facebook.py)

- **Actor:** `apify/facebook-groups-scraper`
- **What we get:** Group members, post authors, commenters
- **Config:** Group URLs

### 4. LinkedIn (scrapers/linkedin.py)

- **Actor:** `apify/linkedin-scraper`
- **What we get:** Profiles matching search queries in target location
- **Config:** Search queries

## Source Configuration

```python
# config.py
import os
from pathlib import Path

# Load .env file if it exists (project-local, sibling to this file).
# This avoids requiring python-dotenv as a dependency.
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

def _require_env(key: str) -> str:
    """Validate env var exists with clear error message."""
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value

def get_apify_token() -> str:
    return _require_env("APIFY_TOKEN")

# Source configs -- edit to add/remove groups
SOURCES = {
    "meetup": {
        "enabled": True,
        "actor": "datapilot/meetup-event-scraper",
        "groups": [
            "https://www.meetup.com/filmnet-sd/",
        ],
    },
    "eventbrite": {
        "enabled": True,
        "actor": "aitorsm/eventbrite",
        "keywords": ["AI workshop", "film", "creative", "music production"],
        "max_pages": 5,
    },
    "facebook": {
        "enabled": True,
        "actor": "apify/facebook-groups-scraper",
        "groups": [],
    },
    "linkedin": {
        "enabled": True,
        "actor": "apify/linkedin-scraper",
        "queries": ["filmmaker San Diego", "musician San Diego", "creative director San Diego"],
    },
}
```

**Key changes from original plan:**
- Token validation via `_require_env()` with clear error messages (not silent `None`)
- `max_pages` per source prevents unbounded crawling
- Actor IDs stored in config (easy to swap)
- Only `APIFY_TOKEN` needed now (no separate Eventbrite token)

**Environment bootstrap:** `config.py` loads `.env` on import using a minimal built-in parser (no `python-dotenv` dependency). It reads `KEY=VALUE` lines and sets them via `os.environ.setdefault()` so exported shell vars take precedence. If `.env` does not exist, only exported shell vars are used. Both paths work; `.env` is the developer convenience, exported vars are the production/CI path.

## Run Flow

### CLI: `python run.py scrape --location "San Diego, CA"`

1. Validate `APIFY_TOKEN` exists (fail fast with clear message)
2. For each enabled source:
   a. Call `scraper.scrape(location, source_config)`
   b. Log: `"Scraping {source}... found {n} leads"`
   c. Pass results to `ingest.ingest_leads(leads)`
   d. Log: `"{inserted} new, {skipped} duplicates, {invalid} rejected"`
3. If a source fails, log the error (masking any tokens in the message) and continue
4. Collect results per source:
   ```python
   results = []  # list of {"source": str, "inserted": int, "skipped": int, "error": str | None}
   ```
5. Print summary. If ALL sources have errors, exit with code 1.

### CLI: `python run.py export --output leads.csv`

Export leads to CSV from the command line (no Flask needed). Immediately usable after Phase 1.

### Web UI: `python run.py serve`

Flask app on 127.0.0.1:5000 (`debug=False` by default):
- `GET /` -- Lead list with source filter, search, pagination (LIMIT 100)
- `GET /leads/export.csv` -- CSV download (respects current filters)
- `POST /leads/<id>/delete` -- Delete a lead (PII compliance)

## Security Requirements

From security-sentinel review:

1. **`debug=False` by default**, controlled by `FLASK_DEBUG` env var. Bind to `127.0.0.1`, never `0.0.0.0`.
2. **CSV formula injection protection** -- sanitize cells starting with `=`, `-`, `+`, `@`, `|` by prefixing with a single-quote before writing to CSV. Implemented in `utils.sanitize_csv_cell()`.
3. **Filter parameter validation** -- source filter is checked against `VALID_SOURCES` allowlist. Unknown values are ignored (filter is dropped, all leads shown). This prevents SQL injection while keeping UX forgiving -- no 400 errors for a mistyped filter.
4. **Token masking in logs** -- never log raw exception objects from HTTP requests (may contain tokens in URLs). Mask tokens: `token[:4] + "****"`.
5. **Profile URL validation** -- reject non-https URLs at ingest time. Prevents stored XSS via `javascript:` URLs.
6. **`.env.example` hygiene** -- placeholder strings only, never real tokens.
7. **Lead deletion** -- `POST /leads/<id>/delete` for PII compliance (CCPA).
8. **No unencrypted secrets in code** -- all tokens via `.env` + `os.getenv()`.

## Technical Considerations

- **Apify SDK pattern:** Use `client.actor(id).call(run_input=..., timeout_secs=300)` which blocks with internal backoff. Do not implement manual polling.
- **Error handling:** Follow url_health_monitor pattern -- catch Timeout, ConnectionError, APIError per source. Never let one source crash the whole run. Truncate stored error messages to 500 chars.
- **DB pattern:** `get_db(db_path)` context manager in `db.py` with explicit path parameter (works in CLI and Flask).
- **No ORM:** Raw SQL with parameterized queries (matches all sandbox apps).
- **Batch inserts:** Entire source batch in one transaction via the context manager. Not per-row commits.
- **Apify free tier:** Confirm your Apify account has enough compute units for initial test runs before committing to all 4 sources. Start with one small Eventbrite run to validate the pipeline.

## YAGNI Decisions (from simplicity review)

These features were cut from v1 to reduce complexity and ship faster:

| Cut Feature | Why | When to Add |
|-------------|-----|-------------|
| Status tracking (5-state pipeline) | CRM feature, not scraper. Manage outreach in a spreadsheet for now. | v2 -- if you miss it after a week of use |
| Lead detail view (`/leads/<id>`) | Only needed for status updates, which are cut | v2 -- with status tracking |
| `--dry-run` flag | Double the CLI complexity for a rarely-used feature | v2 -- if Apify costs become a concern |
| Three separate DB indexes | Premature at hundreds of rows. SQLite scans in milliseconds. | When a query feels slow (it won't) |
| Location filter in Flask UI | All leads will be from the same city per scrape run | v2 -- if multi-city scraping happens |
| `scrapers/__init__.py` as formal Protocol | Python doesn't enforce it. The TypedDict is enough. | Never -- the TypedDict IS the contract |

## Implementation Phases (Collapsed to 2 + Phase 0)

### Phase 0: Actor Payload Validation (before any code)

**Goal:** Capture one real sample payload from each Apify actor used in Phase 1, define the exact raw-to-NormalizedLead mapping, and write fixture files so normalization and ingest can be tested without live Apify runs.

**Steps:**
1. Run the Eventbrite actor (`aitorsm/eventbrite`) manually via the Apify console with a small input (1 keyword, 1 page, San Diego). Save the raw JSON response to `tests/fixtures/eventbrite_raw.json`.
2. Inspect the raw payload. Identify which fields map to each `NormalizedLead` key. Update the Lead Field Registry table with the **actual** field paths (not guesses).
3. Write `tests/fixtures/eventbrite_normalized.json` — the expected output after normalization.
4. Repeat for any Phase 2 actor you can run cheaply (Meetup is a good candidate). Save to `tests/fixtures/meetup_raw.json` + `meetup_normalized.json`.

**Fixture-based verification (implemented in Phase 1):**

```python
# tests/test_normalization.py
import json
from scrapers.eventbrite import normalize  # each scraper exposes normalize(raw_item) -> NormalizedLead

def test_eventbrite_normalization():
    with open("tests/fixtures/eventbrite_raw.json") as f:
        raw_items = json.load(f)
    with open("tests/fixtures/eventbrite_normalized.json") as f:
        expected = json.load(f)
    result = [normalize(item) for item in raw_items]
    assert result == expected

# tests/test_ingest.py
def test_ingest_rejects_missing_profile_url():
    leads = [{"name": "Jane", "source": "eventbrite", "profile_url": None, ...}]
    inserted, skipped, invalid = ingest_leads(leads)
    assert invalid == 1
    assert inserted == 0

def test_ingest_rejects_non_https_url():
    leads = [{"name": "Jane", "source": "eventbrite", "profile_url": "javascript:alert(1)", ...}]
    inserted, skipped, invalid = ingest_leads(leads)
    assert invalid == 1
```

**Why Phase 0 matters:** The Feed-Forward "least confident" risk is Apify data shape consistency. Phase 0 converts this from a live-run gamble into a deterministic, testable contract. If the actor output doesn't match expectations, we find out before writing any scraper code.

**Exit criteria:** At least `eventbrite_raw.json` + `eventbrite_normalized.json` exist. The field registry table is updated with actual field paths. Phase 1 can begin.

### Phase 1: Foundation + Eventbrite + CLI Export

Files: `schema.sql`, `db.py`, `models.py`, `ingest.py`, `config.py`, `scrapers/__init__.py`, `scrapers/_apify_helpers.py`, `scrapers/eventbrite.py`, `run.py`, `requirements.txt`, `.env.example`, `tests/test_normalization.py`, `tests/test_ingest.py`, `tests/fixtures/`

- Set up project structure and SQLite schema
- Implement `db.py` with `get_db()` context manager and `init_db()` bootstrap
- Implement `ingest.py` with validation + dedup + batch insert
- Build Eventbrite scraper with `normalize()` function using Phase 0 field mapping
- Fixture-based tests for normalization + ingest validation (no live Apify dependency)
- CLI `run.py scrape` working for one source
- CLI `run.py export` for CSV output
- **Phase 1 ships a usable artifact** -- run scrape, get CSV, do outreach

### Phase 2: Remaining Sources + Flask Web UI

**Pre-Phase-2 validation:** Run Meetup, Facebook, and LinkedIn actors manually. Save raw payloads to `tests/fixtures/`. Update field registry. Write normalization tests before writing scrapers.

Files: `scrapers/meetup.py`, `scrapers/facebook.py`, `scrapers/linkedin.py`, `app.py`, `templates/index.html`, `static/style.css`, `tests/fixtures/meetup_raw.json`, etc.

- Add Meetup, Facebook, LinkedIn scrapers (all use shared Apify helper)
- Normalization tests pass against fixtures before connecting to live actors
- All 4 sources running via CLI
- Flask web UI: lead list with source filter + search + pagination
- CSV export endpoint
- Delete lead endpoint (see Write Ownership below)
- `run.py serve` command

## What Must NOT Change

- No changes to any other sandbox app
- No ORM or heavy dependencies (keep it Flask + apify-client)
- Scraper modules must stay independent -- no scraper imports another scraper
- `ingest.py` is the ONLY file that executes INSERT on the leads table. `models.delete_lead()` is the only DELETE path.
- `.env` with secrets must be gitignored
- `debug=False` by default in Flask

## Acceptance Tests

### Happy Path (EARS notation)

- WHEN `python run.py scrape --location "San Diego, CA"` is run with valid APIFY_TOKEN THE SYSTEM SHALL call the Eventbrite Apify actor and store organizer leads in SQLite
- WHEN the same scrape is run twice THE SYSTEM SHALL skip duplicate leads (same source + profile_url) and report the skip count
- WHEN `python run.py export --output leads.csv` is run THE SYSTEM SHALL write all leads to a CSV file with sanitized cell values
- WHEN a user visits `/` THE SYSTEM SHALL display leads with name, source badge, and location with pagination (100 per page)
- WHEN a user filters by source "meetup" THE SYSTEM SHALL display only Meetup-sourced leads
- WHEN a user clicks "Export CSV" THE SYSTEM SHALL download a CSV file with all currently filtered leads, with formula-injection-safe cell values
- WHEN a user deletes a lead via `POST /leads/<id>/delete` THE SYSTEM SHALL remove the row from the database

### Error Cases

- WHEN APIFY_TOKEN is missing THE SYSTEM SHALL print "Missing required environment variable: APIFY_TOKEN" and exit with code 1
- WHEN an Apify actor times out (>300s) THE SYSTEM SHALL log the error without exposing the token, save zero leads for that source, and continue
- WHEN a lead has no profile_url THE SYSTEM SHALL reject it at ingest and increment the invalid count
- WHEN a lead has a non-https profile_url THE SYSTEM SHALL reject it at ingest
- WHEN all sources fail THE SYSTEM SHALL print "No leads scraped. Check your tokens and network." and exit with code 1
- WHEN a source filter parameter is not in VALID_SOURCES THE SYSTEM SHALL ignore it and show all leads

### Verification Commands

```bash
# Phase 1: Foundation works
python run.py scrape --location "San Diego, CA"
sqlite3 leads.db "SELECT COUNT(*) FROM leads;"  # > 0
python run.py export --output test.csv && head -1 test.csv  # CSV header

# Phase 2: Multiple sources + web UI
python run.py scrape --location "San Diego, CA"
sqlite3 leads.db "SELECT source, COUNT(*) FROM leads GROUP BY source;"  # multiple sources
python run.py serve &
curl http://127.0.0.1:5000/ | grep "leads"  # HTML with lead data
curl http://127.0.0.1:5000/leads/export.csv | head -1  # CSV header
```

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Apify actors return different data shapes than expected | High | Field registry + validation in ingest.py, reject invalid leads |
| Apify free tier runs out mid-scrape | Medium | Log per-source costs, start with small runs |
| Eventbrite Apify actor discontinued | Low | Multiple actors available, easy to swap in config |
| Meetup Apify actor sessions blocked | Medium | Actor maintainers handle this; disable source if broken |
| NULL profile_url bypasses dedup | Eliminated | NOT NULL constraint + ingest validation |
| CSV formula injection | Eliminated | Cell sanitization in export |

## Sources & References

### Origin

- **Brainstorm:** [docs/brainstorms/2026-04-15-lead-scraper-brainstorm.md](docs/brainstorms/2026-04-15-lead-scraper-brainstorm.md) -- Key decisions: pipeline architecture, all 4 sources, configurable location, SQLite + CSV + Flask

### Solution Docs Applied

- **Inter-service contracts** (`docs/solutions/2026-03-30-chain-reaction-inter-service-contracts.md`) -- Data ownership table, single-writer pattern
- **Swarm shared spec** (`docs/solutions/2026-03-30-swarm-scale-shared-spec.md`) -- Typed interface contract with sample JSON
- **Bookmark manager build** (`docs/solutions/2026-04-09-bookmark-manager-swarm-build.md`) -- Field registry pattern
- **Finance tracker build** (`docs/solutions/2026-04-09-personal-finance-tracker-swarm-build.md`) -- PRAGMA foreign_keys, defense-in-depth
- **URL health monitor** (`docs/solutions/2026-04-05-url-health-monitor.md`) -- HTTP error handling, timeout truncation, SSRF awareness
- **API key manager** (`docs/solutions/2026-04-05-api-key-manager.md`) -- Datetime normalization, BEGIN IMMEDIATE for TOCTOU
- **Webhook delivery** (`docs/solutions/2026-04-05-webhook-delivery-system.md`) -- Exponential backoff, retry boundary pattern

### Repo Patterns Used

- Flat layout from `contact-book/` (app.py + models.py + schema.sql)
- Context manager DB adapted from `bookmark-manager/app/db.py` (with explicit path param for CLI compatibility)
- HTTP error handling from `url_health_monitor/worker.py`
- Minimal requirements.txt: `flask`, `apify-client`

### External Research

- Meetup GraphQL API requires Pro account for member data -- Apify actor needed
- **Eventbrite REST API search endpoint deprecated February 2020** -- Apify actor needed
- Apify Python client: use `.call(timeout_secs=300)` for sync blocking with internal backoff
- Apify actors exist for all 4 platforms at compute-based pricing (~$5-50/month)

## Plan Quality Gate

1. **What exactly is changing?** Adding a new `lead-scraper/` app to the sandbox with 4 Apify-based scrapers, SQLite storage, Flask UI, CLI export, data validation pipeline, and fixture-based tests.
2. **What must not change?** No other sandbox apps. No ORM. `ingest.py` is the single INSERT writer. `models.delete_lead()` is the only DELETE path. `debug=False` default.
3. **How will we know it worked?** EARS acceptance tests + verification commands + fixture-based normalization tests (deterministic, no live Apify dependency).
4. **What is the most likely way this plan is wrong?** Apify actors may return data in shapes we don't expect. **This risk is now concretely addressed by Phase 0:** real payloads are captured before any code is written, exact field mappings are defined from observed data (not guesses), and fixture-based tests verify normalization + ingest validation without live runs. If an actor's output changes later, the fixture test fails immediately and points to the exact field that broke.

## Feed-Forward

- **Hardest decision:** Accepting that all 4 sources need Apify after discovering the Eventbrite API deprecation. This shifts learning value entirely from HTML scraping to API integration and data pipeline patterns.
- **Rejected alternatives:** Direct scraping for Meetup/Eventbrite (login walls + deprecated API), Apify-first from the start (brainstorm chose pipeline, but research proved it right anyway), status tracking in v1 (YAGNI -- CRM feature, not scraper feature).
- **Least confident:** Whether Apify actors for all 4 sources return consistent enough data to fit the normalized schema without heavy per-source transformation. **Status: concretely addressed.** Phase 0 captures real payloads before any code, fixture tests lock the mapping, and validation in `ingest.py` rejects unexpected shapes safely. The risk shifts from "unknown data shape" to "known shape may change over time" -- which the fixture tests catch.
