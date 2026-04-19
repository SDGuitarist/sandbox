---
title: "Multi-page Crawling + Lead Scraper Integration"
phase: plan
created: 2026-04-19
---

# Multi-page Crawling + Lead Scraper Integration

## Problem

The venue scraper only hits the landing page. Contact info (email, phone) is almost always on /contact or /about pages, not the homepage. Music Box SD returned rich venue data but no email or phone. The lead scraper needs a way to call the venue scraper on lead websites and get contact info back.

## What Exactly Is Changing

### Change 1: Subpage Discovery + Multi-page Crawl

**What:** Before scraping a URL, generate candidate subpage URLs and crawl them all. Merge results.

**How:**
- Add `discover_subpages(base_url: str) -> list[str]` to `crawler.py`
- Generate candidates by appending common contact paths to the base URL:
  `/contact`, `/about`, `/about-us`, `/connect`, `/booking`, `/private-events`, `/info`
- Feed the start URL + candidates into `arun_many`
- Add `merge_venue_results(results: list[VenueData]) -> VenueData` to `models.py`
  - Takes the first non-null value for each scalar field (name, email, phone, etc.)
  - Merges list fields (amenities, social_links, event_types, photos) with deduplication
- Update `scrape.py:main()` to use discovery + merge

**Files:** `crawler.py`, `models.py`, `scrape.py`

### Change 2: Contact-only Export Mode

**What:** Add `--contacts-only` flag to CLI that outputs just name, email, phone, social_links as JSON lines. This is the interface the lead scraper consumes.

**How:**
- Add `--contacts-only` argument to `scrape.py`
- When set, output one JSON line per URL with only contact fields
- Output format: `{"source_url": "...", "email": "...", "phone": "...", "social_links": [...]}`

**Files:** `scrape.py`

### Change 3: Lead Scraper Integration

**What:** Add `enrich_with_venue_scraper()` to lead scraper's `enrich.py` that calls the venue scraper via subprocess on leads with websites.

**How:**
- Export lead websites to a temp file
- Run `python /path/to/venue-scraper/scrape.py tempfile --contacts-only --output /tmp/contacts`
- Parse results and persist email/phone/social back into leads DB
- Only runs if venue-scraper is available (graceful skip if not)

**Files:** lead-scraper `enrich.py`, `run.py`

## What Must Not Change

- Existing 27 tests pass
- Single-URL mode (`--url`) still works
- VenueData schema unchanged
- Landing page is always scraped (subpages are additive)

## Implementation Order

1. Change 1: subpage discovery + merge
2. Change 2: contacts-only export
3. Change 3: lead scraper integration
