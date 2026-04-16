---
title: "Lead Scraper: Multi-Source Apify Pipeline with Fixture-Based Testing"
category: architecture
tags: [scraping, apify, sqlite, flask, dedup, fixtures, pipeline, csv-security]
module: lead-scraper
problem: "Building a 4-source lead scraper where 3 of 4 data sources can't be directly scraped"
solution: "Apify actors for all 4 sources, normalize()/scrape() split for testability, single-writer ingestion, composable query layer"
date: 2026-04-15
---

# Lead Scraper: Multi-Source Apify Pipeline with Fixture-Based Testing

## What Was Built

A pipeline-architecture lead scraper that pulls creative professionals from Meetup, Eventbrite, Facebook, and LinkedIn via Apify actors, deduplicates into SQLite, and serves a Flask web UI with CSV export. 28 tests, 4 commits, 2 Codex review passes.

## Risk Resolution Table

| Flagged Risk (Plan) | What Actually Happened | Lesson Learned |
|---------------------|----------------------|----------------|
| Meetup/Eventbrite may require auth for attendee data | Both require login for people data. Eventbrite's search API was deprecated in 2020. | Always verify API availability before planning around it. "The API exists" is not the same as "the endpoint you need exists." |
| Apify actors may return inconsistent data shapes | Mock fixtures worked, but real payloads will differ. The normalize()/scrape() split made this testable. | Split normalization from data fetching. Test normalization against fixtures. When real data arrives, update fixtures and re-run -- don't rewrite scrapers. |
| NULL profile_url bypasses UNIQUE dedup | SQLite UNIQUE constraint silently ignores NULL values. Fixed with NOT NULL on profile_url. | Always test dedup with NULL values. SQLite's NULL behavior in UNIQUE is a documented gotcha that bites every time. |
| Flask get_db() won't work from CLI | bookmark-manager's get_db() uses Flask's current_app context. CLI has no Flask context. | Use Path-based DB paths, not Flask config. If a module serves both CLI and web, design the connection layer to be framework-agnostic. |
| CSV formula injection when exporting scraped data | Implemented single-quote prefix on cells starting with =, -, +, @, \|. Also caught the pipe char that the original plan missed. | CSV injection is a real attack vector when exporting user-generated or scraped content. Add sanitization at export time, not storage time. |

## Key Patterns Worth Reusing

### 1. normalize() + scrape() Split

Each scraper exposes two functions:
- `normalize(raw_item)` -- pure function, no I/O, testable with fixtures
- `scrape(location, config)` -- calls Apify, then maps normalize() over results

This means you can test all field mapping logic without an Apify token, without network access, and without spending compute credits. When the real Apify payload differs from the mock, you update the fixture JSON and the normalize() function -- not the test infrastructure.

### 2. Single-Writer Ingestion

`ingest.py` is the ONLY module that executes INSERT on the leads table. Scrapers return dicts. Models expose reads + one delete. Flask never writes. This prevents double-write bugs and makes the write path auditable from one file.

### 3. Composable query_leads()

One function replaces four (`get_all_leads`, `get_leads_by_source`, `search_leads`, `count_leads`). Filters compose via AND. Returns `(rows, count)` tuple so pagination and totals always match the filtered result set.

**Before:** 4 functions, `q` and `source` short-circuited each other, total was always all-leads count.
**After:** 1 function, filters compose, total reflects the filtered set.

### 4. Built-in .env Loader

A 6-line parser in config.py reads `.env` files without adding `python-dotenv` as a dependency. Uses `os.environ.setdefault()` so exported shell vars take precedence. Both paths work.

### 5. Phase 0: Payload Validation Before Code

Capture one real (or realistic mock) payload from each Apify actor BEFORE writing any scraper code. Save as `tests/fixtures/{source}_raw.json` + `{source}_normalized.json`. This converts the "will the data shape work?" risk from a live-run gamble into a deterministic test.

## What Went Wrong

1. **Eventbrite API assumption survived two planning rounds.** The brainstorm and initial plan both assumed Eventbrite's search API worked. The framework-docs-researcher caught the deprecation during deepening. Without that agent, we'd have discovered it mid-implementation.

2. **Filter composition bug shipped in Phase 2 and survived the 4-agent review.** The `if q: ... elif source:` short-circuit meant you couldn't search within a source. Codex caught it. Lesson: test filter combinations, not just individual filters.

3. **Duplicate timestamp columns (`scraped_at` + `created_at`) shipped and weren't caught until simplicity review.** Both had identical defaults. One was used for sorting, the other for CSV export. Lesson: if two columns have the same default, one is redundant.

## What Went Right

1. **10-agent plan deepening** caught the Eventbrite deprecation, NULL dedup trap, and Flask context conflict before any code was written. These would have been expensive mid-implementation discoveries.

2. **Solution doc lessons from prior builds** (inter-service contracts, swarm shared spec, bookmark manager) directly shaped the architecture. The single-writer pattern, data ownership table, and field registry all came from past compound docs.

3. **Fixture-based testing** enabled 28 tests running in 0.12 seconds with zero external dependencies. Every normalization path and every ingest validation rule is covered.

4. **Two Codex review passes** caught real bugs (filter composition, route contract mismatch, doc drift) that the automated agents missed.

## Feed-Forward

- **Hardest decision:** Accepting all 4 sources need Apify after the Eventbrite API discovery. This changed the project's learning value from "HTML scraping" to "API integration + data pipeline."
- **Rejected alternatives:** Direct scraping (login walls), status tracking in v1 (YAGNI), separate query functions per filter (couldn't compose).
- **For the next scraper/pipeline build:** Always run a real actor manually in Phase 0 and save the payload before writing normalize(). Mock fixtures are a starting point, not a substitute. The field registry table in the plan is only as good as the real data behind it.
