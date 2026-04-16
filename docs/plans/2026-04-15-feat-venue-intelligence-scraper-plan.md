---
title: "feat: Venue Intelligence Scraper"
type: feat
status: active
date: 2026-04-15
origin: docs/brainstorms/2026-04-15-venue-intelligence-scraper-brainstorm.md
feed_forward:
  risk: "LLM extraction reliability across wildly different page layouts"
  verify_first: true
---

# feat: Venue Intelligence Scraper

## Enhancement Summary

**Deepened on:** 2026-04-15 (2 rounds)
**Round 1 agents:** Python Reviewer, Performance Oracle, Security Sentinel, Architecture Strategist, Code Simplicity Reviewer, Pattern Recognition Specialist, Crawl4AI Best Practices Researcher, Plan Quality Gate
**Round 2 agents:** Extraction Prompt Design, Crawl4AI Advanced Config, LLM Testing Strategies, Productization Architecture

### Key Improvements (Round 1)
1. **Simplified to 3 files** -- dropped db.py, config.py, output.py, schema.sql (YAGNI for Phase 1a validation of 5 venues)
2. **Added `validate_extraction()` function** -- testable seam between LLM output and validated schema (mirrors lead-scraper's `normalize()` pattern)
3. **Fixed critical Crawl4AI config** -- `domcontentloaded` instead of `networkidle` (prevents 30s timeouts), `input_format="markdown"` (cheaper), `max_concurrent=3`
4. **Modern Python patterns** -- `str | None` over `Optional`, `datetime` for timestamps, return type hints, `Path` for file paths
5. **Security hardening** -- `.gitignore`, pinned dependency versions, URL validation

### Key Improvements (Round 2)
6. **Prompt design** -- minimal instruction + Pydantic schema, explicit per-field null rules, golden test set for tuning
7. **Content filtering** -- strip nav/footer/ads before LLM extraction to reduce token cost
8. **Testing pyramid** -- fixtures (CI) -> schema conformance (CI) -> golden similarity (CI) -> live integration (manual)
9. **Productization architecture** -- FastAPI + arq + Redis + browser pool, credit ledger model, Apify Actor pattern

### Findings NOT incorporated (deferred to Phase 1b+)
- `pipeline.py` orchestration layer (overkill for 3-file CLI)
- `ingest.py` single write path (no database in Phase 1a)
- Custom rate limiter (3 concurrent + 5 URLs won't hit limits)
- SSRF protection (local CLI only, needed for Phase 2 API)
- Two-stage fetch/extract pipeline (optimization for 200+ URLs)

---

## Overview

Python CLI tool that scrapes venue websites and aggregator platforms to extract structured business intelligence data using AI-powered extraction (Crawl4AI + Claude API). Phase 1a focuses on venue websites only to validate the core extraction pipeline before adding platform scraping with anti-detection.

(see brainstorm: docs/brainstorms/2026-04-15-venue-intelligence-scraper-brainstorm.md)

## Problem Statement / Motivation

Venue research is manual and time-consuming. Pricing, capacity, amenities, and contact info are scattered across individual venue websites, The Knot, Zola, WeddingWire, The Bash, GigSalad, and Yelp. There's no tool that aggregates this into a unified, structured dataset. This scraper serves three use cases: personal venue research, competitive intelligence, and lead generation for outcome-based services.

## Proposed Solution

### Phase 1a: Venue Website Scraper (This Plan -- Build This Week)

A CLI tool that takes a list of venue URLs, scrapes each using Crawl4AI with Playwright rendering, extracts structured data via Claude API, and outputs validated JSON.

```
python scrape.py urls.txt --output results/
```

**What this phase validates:**
- Crawl4AI + Claude reliably extracts structured venue data
- Pydantic schema produces consistent output across different site layouts
- The extraction prompt works without per-site tuning

**What this phase does NOT include:**
- Platform scraping (The Knot, GigSalad, etc.) -- Phase 1b
- Proxy/anti-detection -- not needed for venue websites
- CSV input or search discovery -- Phase 1b/1c
- Supabase storage or SQLite -- Phase 1b
- API server, job queue, auth -- Phase 2
- Billing, dashboard -- Phase 3
- CSV export, confidence scoring, per-venue JSON files -- add when needed

## Technical Approach

### Stack

- **Python 3.11+**
- **Crawl4AI v0.8.x** -- async web crawler with Playwright, stealth, LLM extraction
- **Claude Sonnet** via Crawl4AI's `LLMExtractionStrategy` (LiteLLM under the hood)
- **Pydantic v2** -- schema definition and output validation

### Architecture

```
urls.txt
  |
  v
scrape.py (CLI + orchestration)
  - argparse: urls.txt input, --output, --url flags
  - asyncio.run() entry point
  - loads URLs, loops crawler, writes results
  |
  v
crawler.py (Crawl4AI wrapper)
  - BrowserConfig: headless=True, enable_stealth=True
  - LLMExtractionStrategy: Claude Sonnet, Venue schema
  - arun_many() with max_concurrent=3
  |
  v
models.py (Pydantic schema + validate_extraction())
  - VenueData model with optional fields
  - validate_extraction(raw_json, source_url) -> VenueData | None
  - Extraction prompt (co-located with schema it describes)
```

### Research Insights

- **Use `input_format="markdown"`** -- cheaper than HTML, reduces token count (Crawl4AI Best Practices)
- **Set `chunk_token_threshold=2000`** -- keeps chunks small for focused extraction (Crawl4AI Best Practices)
- **Use `SemaphoreDispatcher`** -- simpler concurrency control for CLI use. MemoryAdaptiveDispatcher was planned but caused MemoryError timeouts when URLs failed DNS resolution (stuck state exceeded 600s memory_wait_timeout). SemaphoreDispatcher provides the same max_concurrent=3 limit without memory monitoring overhead.
- **Check `result.success` before processing** -- not all crawl results contain extracted content (Crawl4AI Best Practices)
- **Pydantic over TypedDict is justified** -- LLM output genuinely needs runtime validation, unlike lead-scraper's API data (Pattern Recognition)

### File Structure

Simplified from 7 files to 3 (YAGNI review). No db.py, config.py, output.py, or schema.sql needed for 5-venue validation.

```
venue-scraper/
  scrape.py          # CLI entry + orchestration + JSON output
  crawler.py         # Crawl4AI wrapper, browser/run config
  models.py          # Pydantic VenueData schema + validate_extraction() + prompt
  requirements.txt   # crawl4ai==0.8.5, pydantic>=2.0
  .gitignore         # .env, results/, __pycache__/
  .env.example       # ANTHROPIC_API_KEY=your-key-here
  tests/
    fixtures/        # LLM JSON output -> expected VenueData (NOT raw HTML)
    test_models.py   # validate_extraction() + schema validation
  results/           # output directory (gitignored)
  urls.txt           # sample input file
```

**Why 3 files, not 7:**
- `config.py` -- one env var check is 3 lines at top of `scrape.py`
- `output.py` -- JSON write is `json.dump()`, one line
- `db.py` + `schema.sql` -- no database in Phase 1a
- Per-venue JSON + errors.json -- one `results.json` is enough for 5 venues
- CSV export -- no consumer exists yet

### Pydantic Schema

```python
# models.py
from __future__ import annotations
import json
from datetime import datetime, UTC
from pathlib import Path
from pydantic import BaseModel, Field

# Pydantic over TypedDict: LLM output requires runtime validation
class VenueData(BaseModel):
    name: str
    description: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    booking_url: str | None = None
    website: str | None = None
    social_links: list[str] = Field(default_factory=list)
    capacity: int | None = None
    capacity_range: str | None = None  # "50-200"
    pricing: str | None = None  # free-text, whatever the site says
    pricing_range: str | None = None  # "$5,000-$15,000"
    amenities: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    venue_type: str | None = None  # "ballroom", "outdoor", "restaurant"
    photos: list[str] = Field(default_factory=list, max_length=20)
    star_rating: float | None = None
    review_count: int | None = None
    source_url: str
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


EXTRACTION_PROMPT = """Extract venue information from this page.
Rules:
- Return null for any field not explicitly stated on the page. Never guess.
- For capacity, extract the maximum number of guests if a range is given.
- For pricing, include the unit (per hour, per event, per person).
- Combine all amenities into a flat list of short strings.
- For social links, include full URLs only.
- Prefer the most specific mention when data conflicts on the page.
"""


def validate_extraction(raw_json: str | dict, source_url: str) -> VenueData | None:
    """Validate raw LLM extraction output into a VenueData instance.

    This is the venue-scraper equivalent of lead-scraper's normalize().
    Independently testable with JSON fixtures -- no API calls needed.
    """
    try:
        if isinstance(raw_json, str):
            data = json.loads(raw_json)
        else:
            data = raw_json

        # Handle list output (Crawl4AI may return array of results)
        if isinstance(data, list):
            data = data[0] if data else {}

        data["source_url"] = source_url
        return VenueData(**data)
    except (json.JSONDecodeError, ValueError, IndexError):
        return None
```

**Prompt design insights (Round 2 research):**
- Keep instruction minimal -- let the Pydantic schema define field names/types, prompt only adds behavioral rules
- Per-field null instructions are critical: models hallucinate pricing and capacity most (fields where "reasonable guesses" exist)
- Skip chain-of-thought -- it wastes tokens and increases hallucination for structured extraction
- Golden test set of 15-20 diverse venues is the tuning mechanism (see Testing section)
- Common failure modes: hallucinated pricing, "capacity: 500 sq ft" parsed as 500 guests, truncated output from large HTML

**Changes from original plan (Python Reviewer + Simplicity Reviewer):**
- `str | None` instead of `Optional[str]` (modern Python 3.11+ syntax)
- `datetime` for `scraped_at` instead of `str` (proper type, Pydantic handles serialization)
- Flat schema instead of nested `VenueContact`/`VenueSocials` (simpler LLM extraction, fewer failures)
- `social_links: list[str]` instead of 6 separate social fields (simpler, just collect URLs)
- `photos` capped at 20 items via `max_length` (Performance Oracle -- prevents token bloat)
- Removed `extraction_confidence` (YAGNI -- eyeball 5 results manually)
- Removed `reviews_summary` (requires LLM synthesis, different task than extraction)
- `validate_extraction()` function mirrors lead-scraper's `normalize()` pattern (Architecture + Pattern Recognition)
- Extraction prompt co-located with schema (they change together)

### Crawl4AI Configuration

```python
# crawler.py
from __future__ import annotations
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    BrowserConfig,
    LLMConfig,
    CacheMode,
    SemaphoreDispatcher,
)
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from models import VenueData, EXTRACTION_PROMPT

CONCURRENCY_LIMIT = 3  # conservative -- each tab uses ~100-200MB RAM


def get_strategy() -> LLMExtractionStrategy:
    return LLMExtractionStrategy(
        llm_config=LLMConfig(
            provider="anthropic/claude-sonnet-4-20250514",
            api_token="env:ANTHROPIC_API_KEY",
        ),
        schema=VenueData.model_json_schema(),
        extraction_type="schema",
        instruction=EXTRACTION_PROMPT,
        input_format="markdown",
        chunk_token_threshold=2000,
        overlap_rate=0.1,
    )


def get_browser_config() -> BrowserConfig:
    return BrowserConfig(headless=True, enable_stealth=True)


def get_run_config() -> CrawlerRunConfig:
    return CrawlerRunConfig(
        extraction_strategy=get_strategy(),
        cache_mode=CacheMode.BYPASS,  # prevent silent LLM skip on cache hits (#1455)
        page_timeout=15000,
        wait_until="domcontentloaded",
        delay_before_return_html=2.0,
        excluded_tags=["nav", "footer", "aside", "header"],
        remove_overlay_elements=True,
    )


def get_dispatcher() -> SemaphoreDispatcher:
    return SemaphoreDispatcher(max_session_permit=CONCURRENCY_LIMIT)
```

**Changes from original plan (Performance Oracle + Crawl4AI Best Practices):**
- `wait_until="domcontentloaded"` + 2s delay instead of `"networkidle"` (prevents 30s timeouts on sites with chat widgets/analytics)
- `page_timeout=15000` instead of 30000 (15s is plenty for venue sites)
- `input_format="markdown"` (cheaper token-wise than HTML)
- `chunk_token_threshold=2000` with `overlap_rate=0.1` (focused extraction per chunk)
- `SemaphoreDispatcher` with `max_session_permit=3` (simpler than MemoryAdaptiveDispatcher, which caused MemoryError on DNS failures)
- `CacheMode.BYPASS` prevents silent LLM extraction skip on cache hits (crawl4ai #1455)
- `excluded_tags` strips nav/footer/aside/header before LLM sees content (reduces tokens, improves extraction focus)
- `remove_overlay_elements=True` strips cookie banners and modals
- All functions have return type hints

**Crawl4AI advanced config insights (Round 2 research):**
- Chunking: no built-in deduplication across overlapping chunks. If two chunks extract the same entity, you get duplicates. `validate_extraction()` should handle this (take first result).
- Cache gotcha: `LLMExtractionStrategy` is silently skipped on cache hits (#1455). Use `CacheMode.BYPASS` or don't enable caching.
- Session + parallel: never use `session_id` with `arun_many()` -- causes race conditions. Let Crawl4AI manage sessions automatically.
- Memory: if system stays above threshold for 10 minutes, dispatcher raises `MemoryError` and stops all crawling. At 3 concurrent, this is very unlikely.
- Content filtering options: `css_selector=".main-content"` can target just the main content area, `word_count_threshold=200` skips short text blocks, `avoid_ads=True` blocks ad network requests at browser level.

### CLI Entry Point

```python
# scrape.py
from __future__ import annotations
import asyncio
import json
import os
import sys
from pathlib import Path

from crawler import get_browser_config, get_run_config, get_dispatcher
from crawl4ai import AsyncWebCrawler
from models import validate_extraction


def load_urls(filepath: Path) -> list[str]:
    """Load URLs from file. One per line. Blank lines and # comments ignored."""
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    urls: list[str] = []
    for line in filepath.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if not line.startswith(("http://", "https://")):
                print(f"  Skipping invalid URL: {line}", file=sys.stderr)
                continue
            urls.append(line)

    # Deduplicate, preserve order
    return list(dict.fromkeys(urls))


async def main(urls: list[str], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    errors: list[dict] = []

    async with AsyncWebCrawler(config=get_browser_config()) as crawler:
        crawl_results = await crawler.arun_many(
            urls=urls,
            config=get_run_config(),
            dispatcher=get_dispatcher(),
        )

        for result in crawl_results:
            if not result.success or not result.extracted_content:
                errors.append({"url": result.url, "error": result.error_message or "No content extracted"})
                print(f"  FAIL: {result.url} -- {result.error_message}", file=sys.stderr)
                continue

            venue = validate_extraction(result.extracted_content, result.url)
            if venue is None:
                errors.append({"url": result.url, "error": "Pydantic validation failed"})
                print(f"  FAIL: {result.url} -- validation failed", file=sys.stderr)
                continue

            results.append(venue.model_dump(mode="json"))
            print(f"  OK: {venue.name} ({result.url})")

    # Write results
    output_file = output_dir / "results.json"
    output_file.write_text(json.dumps(results, indent=2, default=str))

    # Summary
    total = len(urls)
    succeeded = len(results)
    failed = len(errors)
    print(f"\nScraped {succeeded}/{total} venues. {failed} failed.")

    if errors:
        for err in errors:
            print(f"  - {err['url']}: {err['error']}", file=sys.stderr)


if __name__ == "__main__":
    import argparse

    # Validate API key at startup
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set. Export it or add to .env", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Scrape venue websites for business intelligence")
    parser.add_argument("urls_file", nargs="?", type=Path, help="File with one URL per line")
    parser.add_argument("--url", type=str, help="Scrape a single URL")
    parser.add_argument("--output", type=Path, default=Path("results"), help="Output directory")
    args = parser.parse_args()

    if args.url:
        urls = [args.url]
    elif args.urls_file:
        urls = load_urls(args.urls_file)
    else:
        parser.error("Provide urls_file or --url")

    if not urls:
        print("No URLs found.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(main(urls, args.output))
```

**Changes from original plan (Python + Architecture + Simplicity reviewers):**
- Shows the async entry point explicitly (`asyncio.run()`)
- Uses `Path` instead of `str` for file paths
- API key validation at startup (3 lines, no config.py needed)
- Checks `result.success` before processing (Crawl4AI best practice)
- Handles Pydantic validation failure separately from JSON parse failure
- Single `results.json` output (no per-venue files, no errors.json)
- Errors printed to stderr, not a separate file
- `--url` and positional `urls_file` are mutually exclusive via argparse

### Output Strategy

- **Single file:** `results/results.json` (array of all successfully scraped venues)
- **Errors:** printed to stderr during run (not a separate file)
- **Partial failures:** Scrape continues on error. Summary at end: "Scraped 4/5 venues. 1 failed."

### Error Handling

| Error | Behavior |
|---|---|
| URL unreachable / timeout | Log to stderr, skip, continue to next URL |
| Claude API 429 (rate limit) | Crawl4AI handles retry with backoff |
| Claude API 500 | Retry once, then log error and skip |
| Empty page / no extractable content | `result.success` is False, logged and skipped |
| Invalid JSON from Claude | `validate_extraction()` returns None, logged and skipped |
| Valid JSON, fails Pydantic validation | `validate_extraction()` returns None, logged and skipped |
| File not found (urls.txt) | Exit with clear error message |
| Missing ANTHROPIC_API_KEY | Exit at startup with instructions |

### Cost Estimate

- Claude Sonnet: ~$3/M input tokens, ~$15/M output tokens
- With `input_format="markdown"`: ~1-3K tokens input per page (reduced from 2-5K with HTML)
- 5 venues (Phase 1a validation): ~$0.01-0.03
- 200 venues (full run): ~$0.50-2
- Crawl4AI: free (open source)

## System-Wide Impact

Minimal -- this is a new standalone app in the sandbox. No existing systems affected.

- **Interaction graph:** CLI script -> Crawl4AI -> Claude API -> JSON file. No callbacks, no middleware.
- **Error propagation:** Errors are logged and skipped. No cascading failures.
- **State lifecycle risks:** None. Output is a single JSON file, written once at end.
- **API surface parity:** N/A -- standalone CLI tool.

## Acceptance Tests

### Happy Path
- WHEN a user runs `python scrape.py urls.txt` with 5 valid venue URLs THE SYSTEM SHALL output `results/results.json` containing an array of venue objects
- WHEN a venue page contains name, phone, and pricing THE SYSTEM SHALL extract all three into the correct schema fields
- WHEN a venue page is JavaScript-rendered THE SYSTEM SHALL wait for DOM content to load + 2s delay before extraction
- WHEN extraction completes THE SYSTEM SHALL print a summary: "Scraped X/Y venues. Z failed."

### Error Cases
- WHEN a URL returns 404 or times out THE SYSTEM SHALL log the error to stderr and continue to the next URL
- WHEN ANTHROPIC_API_KEY is not set THE SYSTEM SHALL exit at startup with a clear error message
- WHEN urls.txt is empty or has no valid URLs THE SYSTEM SHALL exit with "No URLs found."
- WHEN a URL is malformed (no http/https) THE SYSTEM SHALL skip it with a warning to stderr
- WHEN Claude returns unparseable JSON THE SYSTEM SHALL log via validate_extraction() returning None and skip the venue
- WHEN Claude returns valid JSON that fails Pydantic validation THE SYSTEM SHALL log and skip (distinct from parse error)

### Validation
- WHEN extraction completes THE SYSTEM SHALL validate output against Pydantic VenueData schema via validate_extraction()
- WHEN a field is not found on the page THE SYSTEM SHALL set it to null (not guess)

### Verification Commands
```bash
# Install and setup
pip install -r requirements.txt && crawl4ai-setup

# Run against sample URLs
python scrape.py urls.txt --output results/

# Verify output exists and is valid JSON
python -c "import json; data=json.load(open('results/results.json')); print(f'{len(data)} venues extracted')"

# Run tests (fixture-based, no API calls)
pytest tests/ -v

# Check a single venue
python scrape.py --url "https://example-venue.com" --output results/
```

## Dependencies & Risks

### Dependencies
- `crawl4ai==0.8.5` -- pinned exact version (Security Sentinel)
- `pydantic>=2.0` -- schema validation
- Anthropic API key with Claude Sonnet access
- Python 3.11+

### .gitignore (must be created in Step 1)
```
.env
results/
__pycache__/
*.pyc
```

### Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| LLM extraction inconsistent across site layouts | Medium | Test with 5 diverse venues first. Tune prompt if needed. |
| Crawl4AI breaking changes | Low | Pinned to exact version (0.8.5) |
| Claude API costs higher than estimated | Low | Markdown input format reduces tokens. ~$0.01-0.03 for 5 venues. |
| Some venue sites block headless browsers | Low | Stealth mode enabled by default. Venue sites rarely block. |
| `networkidle` timeout on analytics-heavy sites | Eliminated | Using `domcontentloaded` + 2s delay instead |
| LiteLLM (transitive dep) telemetry | Low | Verify during install that no telemetry phones home with API key |

## Implementation Phases (Within Phase 1a)

### Step 1: Project Setup (~10 lines)
- Create `venue-scraper/` directory
- `requirements.txt` with pinned versions
- `.gitignore` with `.env`, `results/`, `__pycache__/`
- `.env.example` with `ANTHROPIC_API_KEY=your-key-here`
- Verify Crawl4AI + Playwright install: `pip install -r requirements.txt && crawl4ai-setup`

### Step 2: Schema + Validation (~40 lines)
- `models.py` with flat `VenueData` Pydantic model
- `validate_extraction()` function (the normalize-equivalent)
- `EXTRACTION_PROMPT` string

### Step 3: Crawler (~30 lines)
- `crawler.py` with Crawl4AI config functions
- `get_strategy()`, `get_browser_config()`, `get_run_config()`, `get_dispatcher()`
- All with return type hints

### Step 4: CLI + Output (~60 lines)
- `scrape.py` with argparse, `load_urls()`, `async main()`, `asyncio.run()`
- API key validation at startup
- `result.success` checking, `validate_extraction()` calls
- Single `results.json` output
- Summary printing

### Step 5: Tests (~30 lines)
- `tests/fixtures/` with LLM JSON output -> expected VenueData pairs
- `test_models.py` testing `validate_extraction()` with fixtures
- Edge cases: missing fields, empty dict, malformed JSON, list output

**Testing pyramid (Round 2 research):**

```
Layer 1 (CI, free, fast): Fixture-based tests on validate_extraction()
  - Pre-captured LLM JSON -> assert Pydantic model parses
  - Edge cases: missing fields return None, malformed JSON returns None
  - No API calls, no network, runs in <1s

Layer 2 (CI, free, fast): Schema conformance
  - Assert required fields (name) are non-empty strings
  - Assert capacity > 0 when present
  - Assert photos list <= 20 items

Layer 3 (CI, free): Golden similarity (add after smoke test)
  - Save smoke test results as golden files
  - Future runs compare with Jaccard similarity >= 0.8
  - Catches prompt regressions without API calls

Layer 4 (Manual only): Live integration
  - Run against 5 real URLs with relaxed assertions
  - pytest -m integration (excluded from CI)
  - Costs API credits, non-deterministic
```

```python
# tests/test_models.py example
import json, pytest
from pathlib import Path
from models import validate_extraction

@pytest.fixture
def good_venue():
    return json.loads(Path("tests/fixtures/venue_complete.json").read_text())

def test_valid_extraction(good_venue):
    result = validate_extraction(good_venue, "https://example.com")
    assert result is not None
    assert result.name
    assert result.source_url == "https://example.com"

def test_missing_name_fails():
    result = validate_extraction({"capacity": 200}, "https://example.com")
    # Pydantic requires name -- should fail validation
    assert result is None

def test_malformed_json():
    result = validate_extraction("not json {{{", "https://example.com")
    assert result is None

def test_list_output():
    result = validate_extraction([{"name": "Test Venue"}], "https://example.com")
    assert result is not None
    assert result.name == "Test Venue"
```

### Step 6: Smoke Test (~0 lines, just running it)
- Scrape 5 real venue websites (mix: WordPress, Squarespace, custom, SPA)
- Review output quality
- Tune extraction prompt if needed

**Total: ~170 lines of code, 6 commits**

## Productization Architecture (Round 2 Research -- Phase 2/3 Reference)

```
Client Request
     |
     v
+----------+     +-----------+     +--------------+
| FastAPI   |---->| Redis     |---->| arq Workers  |
| Gateway   |    | Queue +   |     | (Playwright  |
|           |<---| Cache     |<----| Browser Pool)|
+----------+     +-----------+     +------+-------+
     |                                     |
     v                                     v
+----------+                      +--------------+
| Stripe   |                      | Proxy Router |
| Billing  |                      | (per-tenant) |
+----------+                      +--------------+
     |                                     |
     v                                     v
+----------+                      +--------------+
| Supabase |                      | Webhook      |
| (jobs,   |                      | Delivery     |
| credits) |                      | (w/ retries) |
+----------+                      +--------------+
```

**Key decisions for Phase 2/3 (from research):**

- **Job queue:** arq over Celery -- pure Python async, Redis-backed, lightweight, pairs naturally with FastAPI + Playwright (both async). Celery is sync-first, overkill.
- **Browser pool:** 1 Chromium per 500MB-1GB RAM. On Railway 8GB plan = 4-6 browsers max. Pool with semaphore for acquire/release.
- **Credit model:** `credit_ledger` table with `delta` column (+100 purchase, -1 scrape). Balance = `SUM(delta)`. Stripe Checkout Session -> webhook -> ledger insert.
- **Webhook delivery:** Exponential backoff (10s, 30s, 90s, 270s, 810s). HMAC-sign payloads for client verification.
- **Proxy routing:** Per-tenant and per-domain config. Resolution order: tenant-specific > domain-specific > default.
- **Railway deployment:** Use `mcr.microsoft.com/playwright/python:v1.44.0` Docker base. 3 services: FastAPI (web), arq worker (worker), Redis (plugin). No persistent disk -- store results in Supabase.
- **Apify lesson:** Define a `ScrapeActor` base class with `input_schema`, `run()`, `output_schema`. Each scraper type is a subclass. Makes scrapers composable and marketplace-ready.

## Phase 1b Readiness Notes

When Phase 1b arrives, these are the planned additions (informed by Architecture + Pattern reviews):

- **`ingest.py`** -- SQLite/Supabase single write path (lead-scraper pattern)
- **`db.py`** -- copy from lead-scraper, change DB name
- **`config.py`** -- extract env loading when more than 1 env var
- **Per-platform prompts** -- `prompts/` directory if single prompt doesn't generalize
- **`pipeline.py`** -- separate orchestration from CLI when adding CSV/search inputs
- **Proxy config** -- add `proxy_config` to `get_browser_config()` for IPRoyal
- **Resumability** -- skip already-scraped URLs (5 lines, check if result file exists)
- **`logging` module** -- replace `print()` when running unattended
- **SSRF protection** -- `is_safe_url()` validator before Phase 2 API server

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-04-15-venue-intelligence-scraper-brainstorm.md](docs/brainstorms/2026-04-15-venue-intelligence-scraper-brainstorm.md)
- Key decisions carried forward: Python + Crawl4AI + Claude API, AI extraction over CSS selectors, phased build (venue sites first), IPRoyal proxies for later phases

### Internal References
- Lead-scraper patterns: `lead-scraper/scrapers/__init__.py` (NormalizedLead TypedDict), `lead-scraper/ingest.py` (single write path), `lead-scraper/db.py` (SQLite WAL contextmanager)
- Job queue pattern: `docs/solutions/2026-04-05-job-queue-system.md` (atomic claim for Phase 2)
- Distributed scheduler: `docs/solutions/2026-04-05-distributed-task-scheduler.md` (separate scheduler process for Phase 2)

### External References
- Crawl4AI docs: https://docs.crawl4ai.com/
- Crawl4AI LLM extraction: https://docs.crawl4ai.com/extraction/llm-strategies/
- Crawl4AI multi-URL crawling: https://docs.crawl4ai.com/advanced/multi-url-crawling/
- Crawl4AI browser config: https://docs.crawl4ai.com/core/browser-crawler-config/
- Pydantic v2 docs: https://docs.pydantic.dev/latest/

### Deepening Sources
- Crawl4AI chunking issue: https://github.com/unclecode/crawl4ai/issues/957
- Crawl4AI hallucination issue: https://github.com/unclecode/crawl4ai/issues/712

## Feed-Forward
- **Hardest decision:** Simplifying to 3 files vs. the architecture reviewer's recommendation of 5+ files with proper separation. Chose simplicity because Phase 1a is a validation run for 5 venues -- if the extraction doesn't work, more files won't help. The architecture patterns (pipeline.py, ingest.py) are documented in "Phase 1b Readiness Notes" so they won't be lost.
- **Rejected alternatives:** Manual HTML-to-Claude pipeline (more control but more code), Firecrawl API (easier but costs scale), Scrapy + CSS selectors (fragile across 8+ platforms), 7-file structure (YAGNI for 5-venue validation).
- **Least confident:** Whether a single extraction prompt works across diverse venue site layouts (WordPress, Squarespace, custom builds, single-page apps). Phase 1a's 5-venue smoke test is specifically designed to answer this before we invest in platform scraping. The `validate_extraction()` function will surface any inconsistencies clearly.
