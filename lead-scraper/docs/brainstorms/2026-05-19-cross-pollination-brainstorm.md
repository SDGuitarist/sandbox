# Cross-Pollination: Lead Scraper x Venue Scraper Integration

**Date:** 2026-05-19
**Status:** Brainstorm complete
**Scope:** Long-term architecture (not gated by May 30 deadline)

## What We're Building

A phased integration that ports the best patterns from each project into the other, connected by a CSV handoff interface. The goal is to make both projects stronger without merging them into a monolith or introducing shared mutable state.

**Five cross-pollination items:**
1. Pydantic validation at lead-scraper's ingest boundary
2. SQLite backend with outreach tracking for venue-scraper
3. CSV handoff pipeline (venue-scraper exports, lead-scraper imports as a source)
4. Tiered LLM extraction to replace regex-based website enrichment in lead-scraper
5. SerpAPI as a new lead discovery source in lead-scraper

## Why This Approach

### End-State: Two Repos, CSV Handoff

Evaluated four options for the relationship between the two projects:

| Option | Verdict | Reason |
|--------|---------|--------|
| **A. One repo** | Rejected | Lead-scraper is already monolithic (51KB run.py, 66KB enrich.py). Absorbing venue-scraper grows that problem. |
| **B. Shared DB** | Rejected | Two writers to leads.db violates the WRC swarm build lesson ("two services wrote to same table" = data misalignment). Lead-scraper's 3 DB wipe incidents make this dangerous. |
| **C. CSV Handoff** | **Selected** | Loosest coupling. Both pieces already exist (`export_outreach_csv()` and `import_from_csv()`). `VENUE_SCRAPER_DIR` config var already in lead-scraper. Each project stays in its lane. |
| **D. Shared library** | Rejected | ~700 lines of overlap doesn't justify a third project with packaging/versioning overhead. Premature abstraction. |

### Sequencing: Strict Dependencies (Foundation First)

Given lead-scraper's history of 3 production DB wipes, safety infrastructure lands before any new data flows. Each phase builds on the last.

```
Phase 1: Pydantic at Ingest ──> Phase 3: CSV Handoff ──> Phase 5: SerpAPI Discovery
                            ──> Phase 4: LLM Extraction ──/
Phase 2: Venue SQLite ─────────> Phase 3: CSV Handoff
```

## Key Decisions

### 1. Pydantic Scope: Ingest Boundary Only

- Add Pydantic model at the ingest layer to validate data BEFORE it hits SQLite
- Internal code (campaign, enrichment, etc.) stays as-is with raw dicts
- Smallest blast radius, biggest safety gain
- Directly addresses root cause of 2 of 3 DB wipe incidents (type confusion)

### 2. LLM Model: Tiered (Haiku First, Sonnet Fallback)

- Primary: Claude Haiku (~$0.001/page) for website contact extraction
- Fallback: Claude Sonnet (~$0.01/page) when Haiku returns zero contact fields from a page with visible text
- Lead-scraper already uses Haiku for segmentation/hooks, so same cost profile
- Venue-scraper's Sonnet-based extraction prompt is the template for the schema

### 3. Venue SQLite: Full Outreach Tracking

- Not just a dedup cache. Track venue outreach status (contacted, replied, partnered)
- Venue-scraper becomes self-contained for venue-specific campaigns
- CSV export to lead-scraper is for cross-pollination, not the only outreach path
- **Scope boundary:** Phase 2 delivers the DB schema + CLI status commands (`mark-contacted`, `mark-partnered`). No web UI, no automated status transitions, no notification system. Those are future cycles if needed.

### 4. SerpAPI: Port discover.py Pattern

- Venue-scraper's `discover.py` (195 lines) is the ready-made module
- Adapt for person-finding queries ("filmmaker San Diego", "composer San Diego")
- Use existing disk caching pattern (saves API credits during dev)
- Free tier: 100 searches/month. Sufficient for discovery, not bulk scraping.

## Phased Implementation Plan (High-Level)

### Phase 1: Pydantic at Lead-Scraper Ingest

**What changes:**
- Create `LeadModel` (Pydantic BaseModel) replacing `NormalizedLead` TypedDict
- Validate in `ingest_leads()` before any SQLite INSERT
- Reject invalid records with structured error messages
- Keep existing downstream code untouched (model exports to dict for SQL)

**What must NOT change:**
- No changes to existing scrapers' normalize() return format (they produce dicts, validation wraps them)
- No changes to enrichment, campaign, or sending code
- No schema migration needed (Pydantic validates in Python, not SQL)

**Depends on:** Nothing (foundational)

**Key files:** `ingest.py`, `scrapers/__init__.py` (TypedDict definition), `models.py`

### Phase 2: Venue-Scraper SQLite Backend

**What changes:**
- Add `venues.db` with schema: venues table + outreach_status table
- Store scraped results in DB instead of (or in addition to) JSON files
- Dedup by source_url across runs
- Track outreach status per venue (new, contacted, replied, partnered, declined) via CLI commands
- CSV export reads from DB instead of in-memory results
- **Scope boundary:** CLI-only status management. No web UI, no automated transitions, no notifications. Just `python scrape.py status set <id> contacted` and `python scrape.py status list`.

**What must NOT change:**
- Existing CLI interface (`python scrape.py --search-film --csv`)
- Crawl4AI extraction pipeline
- JSON output format (keep as secondary output)

**Depends on:** Nothing (different repo, independent work)

**Key files (venue-scraper):** `scrape.py`, `export.py`, new `db.py`, new `schema.sql`

**Lesson to apply:** Lead-scraper's migration pattern minus the auto-run bug. Explicit `python scrape.py migrate` command, never auto-run on startup.

### Phase 3: CSV Handoff Pipeline

**What changes:**
- Wire up `VENUE_SCRAPER_DIR` config in lead-scraper to auto-discover venue CSV
- Add `venue_csv` as a source in lead-scraper's `BASE_SOURCES` config
- Map venue CSV columns to `LeadModel` fields (name, email, phone, website, venue_type -> segment)
- **Column gap to resolve:** venue CSV currently lacks `source_url`. Either add it to venue-scraper's CSV export (preferred -- small change in export.py) or synthesize `profile_url` from the `website` column during import.
- Venue contacts appear in lead-scraper campaigns with `source="venue_scraper"`

**What must NOT change:**
- Venue-scraper's CSV export format (except adding `source_url` column, which is required for lead-scraper compatibility)
- Lead-scraper's existing source configs (Eventbrite, Facebook, Instagram)
- Existing campaign templates (will need a new `venue.md` template -- venues are businesses, not individuals, so existing segment templates don't apply)

**Depends on:** Phase 1 (new data flows through Pydantic validation), Phase 2 (venue DB produces the CSV)

**Key files:** `config.py` (VENUE_SCRAPER_DIR wiring), `ingest.py` (CSV import path), `scrapers/` (new venue_csv normalizer)

### Phase 4: Tiered LLM Extraction Enrichment

**What changes:**
- New `enrich_website_llm()` function using Claude with Pydantic schema (venue-scraper pattern)
- Schema: extract name, email, phone, social handles, role/bio from any website
- Tier 1: Haiku extraction. Tier 2 trigger: if Haiku returns zero contact fields (no email, no phone, no social handles) from a page that has visible text content, retry with Sonnet. This is a concrete, measurable condition -- not a fuzzy "confidence score."
- Replaces regex parsing in `enrich_parsers.py` for website enrichment
- Keep regex parsing as fallback for when LLM is unavailable/rate-limited

**What must NOT change:**
- Bio parsing (regex is fine for structured bio fields)
- Segment classification (already uses Haiku well)
- Hook research (different purpose)
- Existing enrichment CLI interface (`python run.py enrich --step website`)

**Depends on:** Phase 1 (extraction output validates through Pydantic)

**Key files:** `enrich.py` (enrich_leads function), `enrich_parsers.py` (regex to replace), new extraction schema

**Lesson to apply:** Venue-scraper solution doc warns about cost. Multi-page crawl at 8 subpaths = $0.30/venue. Lead-scraper has thousands of leads. Must cap at 1 page per lead (homepage only) with Haiku. At ~$0.001/page, 4,000 leads = ~$4. Subpage crawling (contact/about pages) is a future enhancement if homepage-only accuracy is insufficient.

### Phase 5: SerpAPI Discovery Source

**What changes:**
- Port `discover.py` from venue-scraper (195 lines) into lead-scraper as `scrapers/google.py`
- Adapt queries for person discovery ("filmmaker San Diego" etc.)
- Add `google` source to `BASE_SOURCES` config
- Discovery flow: SerpAPI -> URLs -> LLM extraction (Phase 4) -> ingest (Phase 1)
- Extraction schema must handle non-person pages gracefully (portfolio sites, IMDB, news articles). Return null fields for pages that aren't personal websites rather than hallucinating contacts.
- Disk caching for development (venue-scraper pattern)

**What must NOT change:**
- Existing Apify-based scrapers
- Venue-scraper's own discover.py (lead-scraper gets a copy, not a shared module)

**Depends on:** Phase 4 (discovered URLs need LLM extraction to parse), Phase 1 (results validate through Pydantic)

**Key files:** New `scrapers/google.py`, `config.py` (new source config), `discover.py` (ported from venue-scraper)

**Constraint:** SerpAPI free tier = 100 searches/month. Use for targeted discovery, not bulk. Consider paid tier if ROI proven.

## Prior Lessons That Apply

| Lesson | Source | Phase it affects |
|--------|--------|-----------------|
| Two services writing same table = data misalignment | WRC swarm build solution doc | Architecture decision (rejected Option B) |
| SSRF check must happen at TWO points (pre-request + post-redirect) | Lead-scraper enrichment solution doc | Phase 4 (LLM extraction fetches websites) |
| Runaway costs: 8 subpaths = $0.30/venue | Venue-scraper LLM extraction solution doc | Phase 4 (must cap pages-per-lead) |
| Exclusive fallback causes data loss (use additive) | Venue-scraper search discovery solution doc | Phase 5 (subpage discovery fallback) |
| NULL profile_url bypasses UNIQUE constraint | Lead-scraper multi-source pipeline solution doc | Phase 1 (Pydantic must reject null profile_url) |
| `assert` as SQL guard silently stripped in production | Lead-scraper enrichment expansion solution doc | Phase 1 (use Pydantic validation, not assert) |

## Open Questions

*None remaining -- all resolved during brainstorm dialogue.*

## Feed-Forward

- **Hardest decision:** End-state architecture (CSV handoff vs monolith vs shared DB vs shared library). Chose CSV handoff because it's the only option that respects both projects' data ownership boundaries and avoids the shared-state bugs that caused lead-scraper's DB wipes.
- **Rejected alternatives:** Shared DB (too risky with lead-scraper's wipe history), shared library (premature abstraction for ~700 lines of overlap), monolith (grows lead-scraper's already-excessive file sizes).
- **Least confident:** Phase 3 column mapping. Venue-scraper's CSV currently exports 5 columns (name, email, phone, website, venue_type) but does NOT include `source_url`. Lead-scraper's Pydantic model will require `profile_url` (non-null). Phase 3 must either add `source_url` to the venue CSV export or synthesize `profile_url` from the website column. Decide during planning.
