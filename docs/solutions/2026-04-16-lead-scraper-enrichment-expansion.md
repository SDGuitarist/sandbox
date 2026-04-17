---
title: "Lead Scraper Expansion — Multi-Source Scraping + HTTP Enrichment Pipeline"
category: feature
tags: [web-scraping, data-enrichment, sqlite, apify, beautifulsoup, ssrf-protection, cli-tool, schema-migration]
module: lead-scraper
symptom: "361 leads with profile URLs but zero contact info — outreach required manually visiting each profile"
root_cause: "Single-source scraper with no contact extraction pipeline; schema lacked enrichment columns; no mechanism to follow published links"
date: 2026-04-16
prior_doc: docs/solutions/2026-04-15-lead-scraper-multi-source-pipeline.md
---

# Lead Scraper Expansion — Multi-Source Scraping + HTTP Enrichment Pipeline

## Problem

The lead scraper had one working source (Eventbrite, 361 leads) that collected organizer names and profile URLs but zero contact information. The only outreach path was manually visiting each of 361 profiles. Needed: (1) additional sources (Facebook Groups, Instagram), (2) automated contact enrichment that follows published links to extract emails and phones.

## What Was Built

- **3 scraper sources:** Eventbrite (active), Facebook Groups + Instagram (wired, ready to enable)
- **HTTP enrichment pipeline:** auto-fetches lead websites, extracts emails/phones via BeautifulSoup
- **Schema expansion:** 3 new columns (phone, website, enriched_at) with safe ALTER TABLE migration
- **Security:** .gitignore, SSRF protection with post-redirect validation, CSV sanitization hardening
- **Result:** 95 leads scraped, 3 emails + 2 phones extracted automatically on first run

## Reusable Patterns

### 1. TypedDict as Scraper Interface Contract

Every scraper returns the same `NormalizedLead` TypedDict. When Facebook was completely rewritten (member profiles -> posts/comments), `ingest.py` required zero changes because the contract held. New sources become plug-and-play.

```python
class NormalizedLead(TypedDict):
    name: str
    bio: str | None
    profile_url: str       # dedup key
    source: str            # dedup key
    ...
```

**Lesson:** Define the shared shape once in the package `__init__.py`. When one source's raw data format changes completely, only the normalizer changes — downstream is untouched.

### 2. Module Ownership Boundaries (INSERT vs UPDATE)

`ingest.py` owns all INSERTs. `enrich.py` owns all UPDATEs on enrichment columns. The docstring at the top of each file explicitly states this. When the review found issues, it was immediately clear which file to fix.

**Lesson:** One module, one write operation. Document ownership in the module docstring so the rule is discoverable, not just in your head.

### 3. COALESCE for Non-Destructive Enrichment

The enrichment UPDATE uses `COALESCE(email, :email)` so it only fills NULL columns and never overwrites data from the original scrape. The pipeline is idempotent and safe to re-run.

```python
UPDATE leads SET
    email = COALESCE(email, :email),
    phone = COALESCE(phone, :phone),
    website = COALESCE(website, :website),
    enriched_at = :enriched_at
WHERE id = :id
```

**Lesson:** Any "scrape then enrich" pipeline needs this pattern. Without COALESCE, a re-run could overwrite good data with NULL if the source goes down.

### 4. SSRF Defense Requires Post-Redirect Validation

The initial `_fetch_page` validated the URL before the request but used `allow_redirects=True`. A URL could 302-redirect to `http://169.254.169.254/` (AWS metadata). The 6-agent review caught this as P1. The fix validates `resp.url` after redirects complete and checks ALL DNS results (not just the first) against IPv4 AND IPv6 private ranges.

**Lesson:** SSRF validation at two points: before request (input URL) and after redirects (final URL). Also check all DNS results, not just `addr_info[0]`.

### 5. Idempotent Migration with Conditional Backup

The initial `migrate_db` created a backup on every call (10+ files in one evening). The fix checks whether columns actually need adding before creating the backup.

```python
to_add = [(n, t) for n, t in new_columns if n not in existing]
if not to_add:
    return  # Schema is up to date, no backup needed
```

**Lesson:** Any function called on every startup must be careful about side effects like file creation. Check-before-act.

### 6. Separate I/O from Parsing (Pure Function Extraction)

`enrich_parsers.py` is a pure module — no network calls, no database, just HTML in and data out. This made it trivially testable (no mocking), easy to review, and easy to fix when the review found dead code (80+ lines of unused social URL parsing removed).

**Lesson:** Always separate "fetch the page" from "parse the page." The parser becomes a pure function testable with fixture HTML.

### 7. assert Is Not a Runtime Guard

`db.py` used `assert` to validate column names before SQL interpolation. `assert` is stripped with `python -O`, turning a security check into a no-op. Fixed to `if not ... : raise ValueError(...)`.

**Lesson:** `assert` is for developer-facing invariants during testing. Security/validation checks must use `if/raise`.

## What Went Wrong

| Issue | Found By | Impact |
|-------|----------|--------|
| SSRF redirect bypass | Python + Security reviewers | P1 — could hit AWS metadata via redirect |
| assert as SQL guard | Python + Architecture reviewers | P1 — silently stripped in optimized mode |
| Backup spam on every startup | Python + Simplicity reviewers | P1 — 10+ files from one evening |
| 80 lines of dead social URL parsing | Simplicity reviewer | P1 — never consumed, pure YAGNI |
| Missing IPv6 in SSRF blocklist | Python + Security reviewers | P2 — ::1 loopback bypass |
| Triple BS4 parse per page | Performance + Python reviewers | P2 — 3x CPU cost for no reason |
| Non-200 responses parsed | Architecture reviewer | P2 — bogus emails from error pages |

All 8 findings resolved in 3 fix commits before merge.

## Key Decisions and Why

| Decision | Why | Alternative Rejected |
|----------|-----|---------------------|
| 1 enrichment tier (HTTP fetch), not 3 | YAGNI — 361 leads, test Tier 1 first | Maigret OSINT (60s/lead, heavy dep), Apify paid ($0.002/page) |
| 3 new columns, not 9 | No data source populates social URLs yet | instagram_url, twitter_url, linkedin_url, company, job_title |
| Simple for-loop, not ThreadPoolExecutor | 361 leads at ~2s each = ~12 min | Threading adds complexity for marginal gain |
| Follow-the-links, not fuzzy name matching | Deterministic, ~90%+ precision | Name + location matching has too many collisions |
| Skip Twitter/X | $3 min/run or $0.04/tweet on free tier | Instagram gives ~1,600 profiles/mo for same cost |

## Cross-References

- **Prior build:** [docs/solutions/2026-04-15-lead-scraper-multi-source-pipeline.md](../2026-04-15-lead-scraper-multi-source-pipeline.md) — original normalize/scrape/ingest patterns
- **Data ownership pattern:** [docs/solutions/2026-03-30-chain-reaction-inter-service-contracts.md](../2026-03-30-chain-reaction-inter-service-contracts.md) — single-writer rule
- **SSRF defense lineage:** [docs/solutions/2026-04-05-url-health-monitor.md](../2026-04-05-url-health-monitor.md), [docs/solutions/2026-04-05-multi-tenant-api-gateway.md](../2026-04-05-multi-tenant-api-gateway.md)
- **SQLite migration:** [docs/solutions/2026-04-05-db-migration-runner.md](../2026-04-05-db-migration-runner.md)

## Deferred Work

- **Tier 2 (Maigret OSINT):** Build if Tier 1 hit rate <30%
- **Tier 3 (Apify contact scraper):** Build if Tiers 1+2 insufficient
- **ThreadPoolExecutor:** Add when enrichment exceeds 15 minutes
- **Additional columns:** instagram_url, twitter_url, etc. — add when data exists
- **Twitter/X scraper:** Revisit on paid Apify plan

## Feed-Forward
- **Hardest decision:** Cutting Maigret and Tier 3 after brainstorming designed a 3-tier waterfall. 6/7 reviewers flagged complexity. Tier 1 covers the most valuable path (organizer website URLs).
- **Rejected alternatives:** 3-tier waterfall (over-engineered), 9 columns (YAGNI), ThreadPoolExecutor (premature), fuzzy name matching (low precision)
- **Least confident:** Tier 1 enrichment hit rate (3 emails from 95 leads = ~3%). May need Tier 2/3 for higher coverage. The `website_url` from Eventbrite organizer data is the real prize — leads without it get almost nothing from Tier 1.
