---
title: Cross-Pollination Integration -- Two-Repo CSV Handoff with Tiered LLM Extraction
date: 2026-05-20
tags: [lead-scraper, venue-scraper, integration, csv-handoff, pydantic, sqlite, llm-extraction, serpapi, review]
failure_class: integration-seam-failures
origin_repo: sandbox/lead-scraper + sandbox/venue-scraper
origin_context: "5-phase cross-pollination integration. Patterns ported bidirectionally between repos."
---

## Problem

Lead-scraper and venue-scraper solved overlapping problems with complementary strengths but couldn't share them. Lead-scraper had scale (4,198 leads) and a full campaign pipeline but brittle regex enrichment and no runtime validation (3 DB wipe incidents from type confusion). Venue-scraper had clean Pydantic validation and LLM extraction but no database, no outreach pipeline, and tiny output (~9 venues).

## Solution

5-phase integration connected via CSV handoff. Two repos stay separate. No shared DB, no shared library, no monolith. Each repo owns its own database writes.

### Phase 1: Pydantic at Ingest Boundary

`LeadModel` in `ingest.py` with `ConfigDict(strict=True)`. Validates via `model_validate()` (not `Model(**d)`) before INSERT. Catches type confusion at the single write boundary instead of scattering checks across scrapers.

**Key decision:** Do NOT use `HttpUrl` for profile_url. It normalizes URLs (adds trailing slashes to bare domains), which breaks the `UNIQUE(source, profile_url)` dedup constraint. Custom `@field_validator` checking `startswith("https://")` is safer.

### Phase 2: Venue SQLite Backend

Ported safety patterns from lead-scraper `db.py`:
- Explicit `python scrape.py migrate` command. NEVER auto-run `init_db()` on startup (caused 2 of 3 lead-scraper DB wipes).
- Individual `conn.execute()` calls, NEVER `executescript()` (breaks transactional guarantees with implicit COMMIT).
- `sqlite3.backup()` for backups, NEVER `shutil.copy2()` (corrupts WAL databases).
- `_assert_not_pytest_production()` guard.
- DB writes happen AFTER async crawling in one synchronous block. Never scatter `conn.execute()` across `async def` functions.

### Phase 3: CSV Handoff Pipeline

The CSV file IS the contract between repos. Column mapping tested via fixture CSV.

**Type-based source dispatch:** Added `type` field (`"apify"`, `"csv"`, `"serpapi"`) to all `BASE_SOURCES` entries. Dict dispatch routes by type. `_NON_OVERRIDABLE_FIELDS = {"type"}` prevents `sources.overrides.json` from silently changing dispatch routing. Two named tests guard this: `test_type_not_overridable` and `test_list_overrides_still_work`.

**Venue segment assignment:** Batch UPDATE in the orchestrator (`run.py`), not in the scraper module or enrichment pipeline. `WHERE source = 'venue_scraper' AND segment IS NULL` is intentionally broader (backfills older rows too). Venue leads get `segment='venue'`, `segment_confidence=1.0`.

**delete-source command:** Refuses to delete leads with `sent/replied/booked/declined` outreach. Dry-run mode. Creates backup before deletion.

### Phase 4: Tiered LLM Extraction

Haiku primary, Sonnet fallback (only when Haiku finds nothing AND page >1000 chars visible text), regex fallback when both LLM tiers return nothing or API fails.

**Critical: Strip HTML to visible text before LLM call.** Raw HTML costs ~$0.005/page. Stripped text costs ~$0.001/page. 5x cost reduction. Use `html.parser.HTMLParser` subclass, not BeautifulSoup (no extra dependency).

**COALESCE is NULL-fill only.** LLM extraction fills gaps left by regex. It does NOT overwrite existing non-null email/phone. `enriched_at` always overwrites on LLM path (`force_enriched_at=True`) to distinguish "enriched by regex" from "re-enriched by LLM".

**Domain mismatch flagging:** Extracted emails with non-matching domains get `is_sendable=0, sendable_reason='email_domain_mismatch'`. This is a SEPARATE hold system from enrichment holds (`manual_approved`) and screening holds (`org_name`, `geography`). Recovery via dedicated `leads clear-mismatch` command (not `unhold`).

### Phase 5: SerpAPI Discovery

Ported from venue-scraper `discover.py`. Disk cache with 7-day TTL. Monthly credit tracking (warns at 90/100 free tier). Directory domain filtering. Discovered URLs fetched via `_fetch_page()` (SSRF-protected) and contact-extracted via Haiku LLM. Pages with no name extracted are skipped (not personal sites).

## 4-Agent Review Findings (7 fixed)

| Severity | Finding | Root Cause | Fix |
|----------|---------|------------|-----|
| P0 | Cost cap broken -- `estimated_cost` always $0 | `_extract_with_llm` didn't return token counts | Return `(result, in_tok, out_tok)` tuple, accumulate in loop |
| P0 | `delete-source` runs without DB lock | Not registered in `_command_needs_db_lock()` | Added to lock and backup check sets |
| P0 | `clear-mismatch` runs without DB lock | Not registered in `_command_needs_db_lock()` | Added alongside `unhold` check |
| P1 | f-string LIMIT in SQL query | Direct interpolation of `limit` parameter | Parameterized with `LIMIT ?` |
| P1 | SerpAPI key in cached responses | `serpapi_cache/` not in `.gitignore` | Added to `.gitignore` |
| P1 | `http://` venue URLs silently rejected | `LeadModel.must_be_https()` validator | Normalize to `https://` in `venue_csv.normalize()` |
| P1 | Domain mismatch on wrong email | Check used proposed email, not stored email post-COALESCE | Re-read actual email from DB after persist |

## Rules for Future Cross-Repo Integrations

1. **CSV as the contract boundary.** Test it with a fixture file. Version the column names. Neither repo imports code from the other.
2. **Type-based dispatch with non-overridable guards.** Protect routing-critical fields from config overrides. Name the tests explicitly.
3. **Register every new DB-writing command in lock/backup checks.** This was missed for both `delete-source` and `clear-mismatch`. Treat it as a checklist item for every new CLI command.
4. **Token counting must be wired from day one.** Cost caps that don't track tokens are security theater. Return usage from every LLM call, accumulate in the loop.
5. **Domain mismatch check must use post-COALESCE state.** COALESCE may preserve the existing email. Checking the proposed-but-not-written email produces false positives.
6. **`http://` normalization at the boundary.** Venue sites often lack HTTPS. Normalize at the scraper/normalizer level, not in the validator.
7. **Separate hold systems for separate concerns.** Enrichment holds (`manual_approved`), screening holds (`is_sendable` via `screen_leads`), and domain-mismatch holds are independent. `unhold` only clears enrichment holds. `clear-mismatch` only clears mismatch holds. `screen_leads` must preserve mismatch holds when a lead passes screening.

## Stats

- 5 phases, 7 commits (5 features + 1 merge + 1 review fixes)
- 28 files changed, ~4,200 lines added
- 113 new tests (326 total passing, 4 pre-existing failures)
- 4 review agents: Architecture, Security, Data Integrity, Performance
- 3 P0 + 4 P1 findings fixed

## Feed-Forward

- **Hardest decision:** Keeping `unhold_lead()` narrow (manual_approved only) vs making it clear all holds. Chose narrow because `is_sendable` is shared with `screen_leads()` screening failures -- a blanket clear would silently re-enable leads that were correctly screened out.
- **Rejected alternatives:** Shared DB (WRC incident), monolith (complexity), shared library (~700 lines overlap doesn't justify packaging overhead), Sonnet-only extraction (10x more expensive).
- **Least confident:** `screen_leads()` can overwrite `email_domain_mismatch` reason when a lead also fails a screening check. The mismatch reason changes to the screening reason, making `clear_domain_mismatch()` unable to find it later. Deferred -- needs a design decision about storing multiple hold reasons.
