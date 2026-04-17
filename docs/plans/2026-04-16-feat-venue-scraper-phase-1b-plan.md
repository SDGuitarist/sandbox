---
title: "feat: Venue Scraper Phase 1b -- Platform Scraping + Storage"
type: feat
status: active
date: 2026-04-16
origin: docs/brainstorms/2026-04-16-venue-scraper-phase-1b-brainstorm.md
feed_forward:
  risk: "Whether residential proxies + stealth work on aggregator platforms (GigSalad first, Cloudflare platforms deferred to 1c)"
  verify_first: true
---

# feat: Venue Scraper Phase 1b -- Platform Scraping + Storage

## Enhancement Summary

**Deepened on:** 2026-04-16
**Agents used:** Python Reviewer, Architecture Strategist, Security Sentinel, Code Simplicity Reviewer, Performance Oracle, Plan Quality Gate

### Key Improvements
1. **Collapsed 7 steps to 3** -- simplicity review found 75% of planned code was YAGNI (separate scraper files, merge logic, CSV lookup, platform prompts). Focused on what validates the riskiest assumptions.
2. **Reordered: HTML fallback is Step 1** -- fixes a known Phase 1a bug (40% of test sites failed). Highest-certainty, highest-value change. Was Step 7 in original plan.
3. **Deferred merge logic** -- architecture + performance reviewers flagged cross-platform venue matching as an unsolved problem. Store raw per-source records; merge when we have real multi-source data.
4. **StrEnum for source field** -- Python reviewer: bare `str` allows typos that silently poison data
5. **Security hardening** -- parameterized SQL requirement, Yelp API must NOT route through proxy, `*.db` added to .gitignore, anti-injection language in extraction prompt

### Deferred to Phase 1c (after data validates the need)
- Per-platform scraper files (use `--source` flag instead)
- `scrapers/__init__.py` formal interface
- `merge_venues()` + `SOURCE_PRIORITY` auto-merge
- CSV input with cross-platform lookup
- Platform-specific prompts
- Yelp Fusion API (separate concern, add after storage works)
- The Knot / WeddingWire / Zola (Cloudflare bypass -- separate experiment)

---

## Overview

Extend the Phase 1a venue website scraper to support platform scraping with residential proxies, fix the empty-extraction bug, and add SQLite storage with deduplication. Built in 3 focused steps, each validating one thing.

(see brainstorm: docs/brainstorms/2026-04-16-venue-scraper-phase-1b-brainstorm.md)

## Problem Statement / Motivation

Phase 1a proved the extraction pipeline works on venue websites (3/5 extracted). Two gaps remain: (1) image-heavy sites return empty extraction (40% failure rate on reachable sites), and (2) no persistence or platform scraping. Phase 1b fixes the extraction gap, proves proxy-based platform scraping works, and adds local storage.

## Proposed Solution

3 focused steps (~100 lines total):

| Step | What | Validates | Changes |
|---|---|---|---|
| A | HTML fallback | Fixes known 40% extraction failure | crawler.py, scrape.py |
| B | Proxy + source tagging | Platform scraping pipeline works | crawler.py, models.py, scrape.py |
| C | SQLite storage + dedup | Persistence with UNIQUE constraint | db.py, ingest.py, schema.sql |

**What this phase does NOT include:**
- Per-platform scraper files (use `--source` flag on existing scrape.py)
- Source-priority merge logic (store raw records, merge later with real data)
- Yelp Fusion API (separate concern -- Phase 1c)
- CSV input (urls.txt already handles URL lists)
- Supabase migration (SQLite first)
- API server, job queue, auth (Phase 2)

## Technical Approach

### Step A: HTML Fallback (~20 lines)

Fixes the known Phase 1a failure where image-heavy sites (Brick15, The Prado) return empty `[]` from markdown extraction. When markdown returns empty, retry with HTML.

```python
# crawler.py -- add fallback config
def get_run_config(html_mode: bool = False) -> CrawlerRunConfig:
    """Build run config. Set html_mode=True for sites that fail markdown extraction."""
    strategy = get_strategy()
    if html_mode:
        # Override to use raw HTML instead of markdown
        strategy = LLMExtractionStrategy(
            llm_config=strategy.llm_config,
            schema=VenueData.model_json_schema(),
            extraction_type="schema",
            instruction=EXTRACTION_PROMPT,
            input_format="fit_markdown",  # HTML with basic cleanup
            chunk_token_threshold=4000,   # larger chunks for HTML
            overlap_rate=0.1,
        )
    return CrawlerRunConfig(
        extraction_strategy=strategy,
        cache_mode=CacheMode.BYPASS,
        page_timeout=15000,
        wait_until="domcontentloaded",
        delay_before_return_html=2.0,
        excluded_tags=["nav", "footer", "aside", "header"],  # keep even in HTML mode
        remove_overlay_elements=True,
    )
```

```python
# scrape.py -- add retry logic in main()
for result in crawl_results:
    if not result.success or not result.extracted_content:
        # ... existing error handling ...
        continue

    venue = validate_extraction(result.extracted_content, result.url)

    # HTML fallback: retry if markdown extraction returned empty
    if venue is None and result.success:
        print(f"  RETRY (HTML): {result.url}", file=sys.stderr)
        fallback_result = await crawler.arun(
            url=result.url,
            config=get_run_config(html_mode=True),
        )
        if fallback_result.success and fallback_result.extracted_content:
            venue = validate_extraction(fallback_result.extracted_content, result.url)

    if venue is None:
        # ... existing error handling ...
        continue
```

**Research insight (Performance Oracle):** Keep `excluded_tags` in the HTML fallback config. The original plan removed all tag exclusions for HTML mode, but nav/footer/aside are noise in any format.

### Step B: Proxy + Source Tagging (~40 lines)

Prove the proxy pipeline works by scraping GigSalad listings through IPRoyal.

**Schema change -- add `source` field with StrEnum:**

```python
# models.py -- add these
from enum import StrEnum

class VenueSource(StrEnum):
    WEBSITE = "website"
    GIGSALAD = "gigsalad"
    THEBASH = "thebash"
    YELP = "yelp"
    THEKNOT = "theknot"
    WEDDINGWIRE = "weddingwire"
    ZOLA = "zola"

class VenueData(BaseModel):
    # ... existing fields ...
    source: VenueSource = VenueSource.WEBSITE  # validated, not bare str
```

**Proxy config (inline in crawler.py, no config.py needed):**

```python
# crawler.py -- add proxy support
from typing import TypedDict

class ProxyConfig(TypedDict):
    server: str
    username: str
    password: str

def get_proxy_from_env() -> ProxyConfig | None:
    """Read IPRoyal proxy config from env vars. Returns None if not configured."""
    server = os.environ.get("IPROYAL_PROXY_SERVER")
    if not server:
        return None
    return ProxyConfig(
        server=server,
        username=os.environ.get("IPROYAL_PROXY_USER", ""),
        password=os.environ.get("IPROYAL_PROXY_PASS", ""),
    )

def get_browser_config(proxy_config: ProxyConfig | None = None) -> BrowserConfig:
    return BrowserConfig(
        headless=True,
        enable_stealth=True,
        proxy_config=dict(proxy_config) if proxy_config else None,
    )
```

**CLI changes:**

```python
# scrape.py -- add flags
parser.add_argument("--source", type=VenueSource, default=VenueSource.WEBSITE, choices=list(VenueSource), help="Source tag")
parser.add_argument("--proxy", action="store_true", help="Use IPRoyal residential proxy")
```

**Security requirement (Security Sentinel):** Proxy credentials must never appear in log output. The `ProxyConfig` TypedDict does not have a custom `__repr__`, but since it is only passed to Crawl4AI's BrowserConfig (not logged directly), this is acceptable for Phase 1b.

### Step C: SQLite Storage + Dedup (~50 lines, 3 new files)

```sql
-- schema.sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'website',
    source_url TEXT NOT NULL,
    data JSON NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_url, source)
);

-- Indexes for common queries (Performance Oracle)
CREATE INDEX IF NOT EXISTS idx_venues_name ON venues(name);
CREATE INDEX IF NOT EXISTS idx_venues_source ON venues(source);
```

```python
# db.py -- copy from lead-scraper, add type hints
from __future__ import annotations
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "venue_scraper.db"

@contextmanager
def get_db(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection]:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: Path = DB_PATH) -> None:
    schema = (Path(__file__).parent / "schema.sql").read_text()
    with get_db(db_path) as conn:
        conn.executescript(schema)
```

```python
# ingest.py -- single-writer, parameterized queries ONLY
from __future__ import annotations
import json
import sqlite3
from typing import Literal

from models import VenueData

def insert_venue(conn: sqlite3.Connection, venue: VenueData) -> Literal["inserted", "skipped"]:
    """Insert a venue. Uses INSERT OR IGNORE for dedup. Parameterized queries only."""
    try:
        conn.execute(
            "INSERT OR IGNORE INTO venues (name, source, source_url, data) VALUES (?, ?, ?, ?)",
            (venue.name, str(venue.source), venue.source_url, venue.model_dump_json()),
        )
        return "inserted" if conn.total_changes else "skipped"
    except sqlite3.IntegrityError:
        return "skipped"
```

**Security requirement (Security Sentinel):** All SQL in ingest.py MUST use parameterized queries (`?` placeholders). No f-strings or `.format()` in any SQL context. Add a test that inserts SQL injection payloads as venue names.

**What Step C deliberately omits:**
- `merge_venues()` -- deferred. The cross-platform venue matching problem is unsolved (how to know GigSalad's "Grand Ballroom" and Yelp's "Grand Ballroom SD" are the same venue). Store raw per-source records. Merge when we have real multi-source data to design against.
- `SOURCE_PRIORITY` ranking -- deferred for same reason.
- `upsert_venue()` -- use simple `insert_venue()` with INSERT OR IGNORE. No update logic yet.

### Updated .gitignore

```
.env
results/
__pycache__/
*.pyc
*.db
*.db-wal
*.db-shm
```

### Updated .env.example

```
ANTHROPIC_API_KEY=your-key-here
# Proxy (optional -- only needed for --proxy flag)
IPROYAL_PROXY_SERVER=
IPROYAL_PROXY_USER=
IPROYAL_PROXY_PASS=
```

## Acceptance Tests

### Step A: HTML Fallback
- WHEN markdown extraction returns empty `[]` THE SYSTEM SHALL retry with HTML input format
- WHEN HTML fallback also returns empty THE SYSTEM SHALL log and skip (not retry indefinitely)
- WHEN HTML fallback succeeds THE SYSTEM SHALL include the result in output normally
- WHEN a site works on markdown THE SYSTEM SHALL NOT attempt HTML fallback (no double-cost)

### Step B: Proxy + Source Tagging
- WHEN `--proxy` flag is used THE SYSTEM SHALL route browser traffic through IPRoyal residential proxy
- WHEN `--source gigsalad` is provided THE SYSTEM SHALL tag each result with `source: "gigsalad"`
- WHEN an invalid source value is provided THE SYSTEM SHALL reject it (StrEnum validation)
- WHEN proxy connection fails THE SYSTEM SHALL log the error and continue to next URL

### Step C: SQLite Storage
- WHEN `--db` flag is used THE SYSTEM SHALL persist results to `venue_scraper.db`
- WHEN the same source_url + source is inserted twice THE SYSTEM SHALL ignore the duplicate
- WHEN a venue name contains SQL injection payload THE SYSTEM SHALL store it safely (parameterized query)
- WHEN SQLite is in WAL mode THE SYSTEM SHALL handle concurrent reads without SQLITE_BUSY

### Verification Commands
```bash
# Step A: HTML fallback
python scrape.py --url "https://www.theprado.com" --output results/
cat results/results.json | python -c "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} venues')"

# Step B: Proxy + source (requires IPRoyal signup)
python scrape.py urls.txt --source gigsalad --proxy --output results/

# Step C: SQLite
python scrape.py urls.txt --db
sqlite3 venue_scraper.db "SELECT name, source, source_url FROM venues;"

# All tests
pytest tests/ -v
```

## Implementation Steps

### Step A: HTML Fallback (~20 lines, 1 commit)
1. Add `html_mode` parameter to `get_run_config()` in `crawler.py`
2. Add retry logic in `scrape.py` `main()` when extraction returns None but crawl succeeded
3. Test: re-run The Prado and Brick15 (Phase 1a failures)
4. **Validation gate:** At least 1 of the 2 previously-failed sites now extracts data

### Step B: Proxy + Source Tagging (~40 lines, 1 commit)
1. Add `VenueSource` StrEnum to `models.py`
2. Add `source` field to `VenueData`
3. Add `ProxyConfig` TypedDict + `get_proxy_from_env()` to `crawler.py`
4. Modify `get_browser_config()` to accept `proxy_config`
5. Add `--source` and `--proxy` flags to `scrape.py`
6. Update `.env.example`
7. **Validation gate:** Scrape 3 GigSalad listing URLs through proxy with `--source gigsalad`

### Step C: SQLite Storage (~50 lines, 1 commit)
1. `schema.sql` -- venues table with UNIQUE + indexes + WAL pragma
2. `db.py` -- contextmanager with WAL + busy_timeout (lead-scraper pattern, with type hints)
3. `ingest.py` -- `insert_venue()` with parameterized queries only
4. Add `--db` flag to `scrape.py`
5. Tests: insert, dedup, SQL injection payload safety
6. Update `.gitignore` with `*.db` patterns
7. **Validation gate:** Scrape 3 URLs with `--db`, verify data in SQLite

**Total: ~110 lines new code, 3 commits**

## Dependencies & Risks

### Dependencies
- IPRoyal account (need to sign up, $1.75/GB pay-as-you-go) -- required for Step B
- Existing: crawl4ai==0.8.5, pydantic>=2.0

### Risks

| Risk | Likelihood | Step | Mitigation |
|---|---|---|---|
| HTML fallback still fails on some sites | Low | A | Accept as limitation. Vision-based extraction in Phase 2. |
| IPRoyal proxy unreliable on GigSalad | Low | B | SmartProxy as fallback ($4.50/GB, larger pool) |
| GigSalad blocks residential proxy + stealth | Medium | B | Try different proxy geo. If still blocked, this is the answer to the Feed-Forward risk. |
| SQLite SQLITE_BUSY with WAL | Very Low | C | WAL + busy_timeout=5000 handles this. Single-user CLI. |

## Phase 1c Roadmap (After 1b Validates)

Once Steps A-C prove the pipeline works, these are the next additions:

1. **Yelp Fusion API** -- `scrapers/yelp.py` with normalize/search (separate from Crawl4AI pipeline). 500/day rate limit -- add file-based daily counter.
2. **The Bash** -- scrape through proxy, same pipeline as GigSalad
3. **The Knot / WeddingWire / Zola** -- the Cloudflare test (Feed-Forward risk)
4. **Cross-platform merge** -- design matching algorithm when we have real multi-source data (normalized name + city? phone number? address?)
5. **CSV input** -- batch URL lists with extra metadata columns

## Sources & References

### Origin
- **Brainstorm:** [docs/brainstorms/2026-04-16-venue-scraper-phase-1b-brainstorm.md](docs/brainstorms/2026-04-16-venue-scraper-phase-1b-brainstorm.md)
- Key decisions: Crawl4AI direct over Apify, IPRoyal proxy from start, SQLite first, incremental platform addition

### Internal References
- Phase 1a plan: `docs/plans/2026-04-15-feat-venue-intelligence-scraper-plan.md`
- Lead-scraper patterns: `lead-scraper/db.py` (SQLite WAL), `lead-scraper/ingest.py` (single-writer)
- Solution docs: `docs/solutions/2026-03-30-chain-reaction-inter-service-contracts.md` (data ownership), `docs/solutions/2026-04-09-recipe-organizer-swarm-build.md` (schema-level dedup)

### External References
- Crawl4AI proxy docs: https://docs.crawl4ai.com/advanced/proxy-security/
- IPRoyal residential proxies: https://iproyal.com/residential-proxies/

### Deepening Sources
- Simplicity review: collapsed 7 steps to 3 (75% LOC reduction)
- Python review: StrEnum for source, ProxyConfig TypedDict, no dict mutation in normalize
- Architecture review: deferred merge logic (cross-platform matching unsolved)
- Security review: parameterized SQL, proxy not for API calls, *.db in .gitignore
- Performance review: WAL pragma in db.py, indexes for name/source

## Feed-Forward
- **Hardest decision:** Deferring merge logic. The brainstorm decided on source-priority auto-merge, but 3 reviewers flagged that cross-platform venue matching is unsolved (how to know two records from different platforms are the same venue). Storing raw per-source records and merging later when we have real data to design against is safer than building a merge system in the dark.
- **Rejected alternatives:** 7-step plan with per-platform files (YAGNI -- `--source` flag does the same thing), Apify actors (no niche actors exist), merge logic before data (designing in the dark).
- **Least confident:** Whether residential proxies + stealth work on GigSalad. This is a lighter target than The Knot, so if it fails here, The Knot is definitely out. Step B is the real validation gate for the entire platform scraping concept.
