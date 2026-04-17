# Venue Intelligence Scraper Phase 1b - Brainstorm

**Date:** 2026-04-16
**Status:** Draft
**Phase:** Brainstorm
**Builds on:** Phase 1a (merged to master, 3 files, 25 tests passing)

---

## What We're Building

Extend the Phase 1a venue website scraper to support aggregator platform scraping, proxy rotation, Supabase storage with multi-source deduplication, and CSV input. This is the full Phase 1b roadmap, implemented incrementally starting with the easiest platform (GigSalad) to validate the pipeline.

### Incremental Build Order

1. **GigSalad validation** -- first platform scrape with proxy + prompt comparison
2. **SQLite storage + dedup** -- persist results locally with UNIQUE(profile_url, source). Migrate to Supabase once schema is proven.
3. **The Bash** -- second platform (moderate anti-bot)
4. **Yelp Fusion API** -- API integration, no scraping
5. **The Knot / WeddingWire / Zola** -- hardest platforms (Cloudflare)
6. **CSV input** -- venue name lookup across platforms
7. **HTML fallback** -- for image-heavy sites that fail markdown extraction

### Target Platforms (ordered by difficulty)

| Platform | Anti-Bot | Method | Proxy Needed |
|---|---|---|---|
| GigSalad | Lightest | Crawl4AI direct | Yes (prove pipeline) |
| The Bash | Light Cloudflare | Crawl4AI + stealth | Yes |
| Yelp | Aggressive (lawsuits) | Yelp Fusion API only | No |
| The Knot | Cloudflare moderate | Crawl4AI + stealth + proxy | Yes |
| WeddingWire | Cloudflare moderate (same infra as The Knot) | Crawl4AI + stealth + proxy | Yes |
| Zola | Cloudflare moderate | Crawl4AI + stealth + proxy | Yes |

### Data Schema

Reuse the existing flat VenueData Pydantic model from Phase 1a. Add a `source` field to track which platform each record came from.

### Use Cases (same as Phase 1a, now at scale)
- Personal venue research across all platforms
- Competitive intelligence (compare same venue across sources)
- Lead generation with multi-source enrichment

---

## Why This Approach

### Approach: Crawl4AI Direct + IPRoyal Proxies + Yelp API

Extend the existing Phase 1a pipeline rather than switching to Apify or building from scratch.

**Why not Apify:**
- No GigSalad/The Bash-specific actors exist (too niche)
- Generic Apify scrapers still need custom extraction logic -- same work as Crawl4AI
- We already have the extraction pipeline working with Crawl4AI + Claude
- Apify adds a dependency and cost ($5+/mo) for no clear benefit at this scale

**Why proxy from the start:**
- Even though GigSalad is the easiest target, we want to prove the proxy pipeline works before hitting The Knot
- IPRoyal pay-as-you-go ($1.75/GB) means near-zero cost for validation runs

**Why Yelp API instead of scraping:**
- Yelp has actively sued scrapers
- Yelp Fusion API is free (5K calls/day) and returns structured data
- No proxy, no stealth, no anti-bot concerns

### Prompt Strategy

Test both universal and platform-specific prompts on 3 GigSalad listings, compare quality, then decide for the full rollout. GigSalad listings have specific data (performer profiles with bio, genres, price range, booking info, reviews) that may benefit from a tailored prompt.

### Storage Strategy (from solution doc lessons)

- **Single-writer ingest pattern** -- new `ingest.py` is the ONLY module that writes to the database (lead-scraper lesson). SQLite first, Supabase later.
- **Schema-level dedup** -- `UNIQUE(profile_url, source)` catches duplicates at INSERT (recipe-organizer lesson)
- **Source-priority auto-merge** -- when same venue exists across platforms, merge per-field using priority: venue website > Yelp API > scraped platforms. No manual review. Raw per-source records kept.
- **Data Ownership table** in spec (chain-reaction-contracts lesson):

| Data | Writer | Reader |
|---|---|---|
| venues table | ingest.py only | all scrapers, CLI, future API |
| merge logic | ingest.py only | query layer |
| scrape_log | each scraper | monitoring |

---

## Key Decisions

1. **Crawl4AI direct** over Apify -- no platform-specific actors exist, same work either way, no new dependency
2. **IPRoyal proxy from the start** -- prove pipeline on GigSalad, ready for The Knot
3. **Incremental platform addition** -- GigSalad first, then The Bash, then The Knot group. Each validates before the next.
4. **Yelp Fusion API only** -- never scrape Yelp (legal risk)
5. **Prompt A/B test** on GigSalad -- universal vs platform-specific, compare on 3 listings
6. **Single-writer ingest** -- ingest.py is the only module that writes to the database (SQLite first, Supabase later)
7. **UNIQUE(profile_url, source)** at schema level for dedup
8. **Source field** added to VenueData -- tracks which platform each record came from. This is a schema change to existing Phase 1a code (add `source: str` field to Pydantic model).

---

## New Files (Phase 1b additions to venue-scraper/)

- `ingest.py` -- database writes only, single-writer pattern (SQLite first, Supabase later)
- `db.py` -- SQLite contextmanager (copy from lead-scraper pattern)
- `config.py` -- env loading for ANTHROPIC_API_KEY, IPROYAL_PROXY (add SUPABASE vars when migrating)
- `schema.sql` -- venues table DDL with UNIQUE(profile_url, source)
- `prompts/` directory -- per-platform prompts if A/B test shows they're needed
- Updated `crawler.py` -- proxy_config parameter, html fallback
- Updated `scrape.py` -- CSV input mode, --source flag, Supabase output option

---

## Resolved Questions

1. **Apify vs Crawl4AI** -- Crawl4AI direct. No platform-specific Apify actors for our niche. Same extraction work either way.
2. **Proxy timing** -- From the start. Prove the pipeline on GigSalad so it's ready for The Knot.
3. **Prompt strategy** -- A/B test universal vs platform-specific on 3 GigSalad listings, then decide.
4. **Scope** -- Full Phase 1b roadmap, implemented incrementally.

5. **Storage** -- Local SQLite first, migrate to Supabase later when schema is proven. Avoids Supabase setup overhead during validation.
6. **IPRoyal** -- Need to sign up. Budget: $1.75/GB pay-as-you-go, no minimums.
7. **GigSalad discovery** -- Manual URLs for validation, add category browsing (gigsalad.com/Category/City) as a later feature.
8. **Conflict resolution** -- Source-priority auto-merge. Venue website > Yelp API > scraped platforms. Highest-priority non-null value wins per field. No manual review needed. Raw per-source records kept in DB.
9. **CSV format** -- Deferred to after platform scraping is validated. Not needed for GigSalad validation step.

## Open Questions

1. **IPRoyal account setup** -- Need to sign up before the first platform scrape. What plan/tier to start with?

---

## Feed-Forward
- **Hardest decision:** Going Crawl4AI direct over Apify. Apify handles anti-bot for you, but adds a dependency and cost for no advantage when platform-specific actors don't exist.
- **Rejected alternatives:** Apify actors (no niche actors exist), scraping Yelp (legal risk), building all platforms at once (too much risk without GigSalad validation first).
- **Least confident:** Whether residential proxies + stealth will actually work on The Knot/WeddingWire. GigSalad is easy, but The Knot is Cloudflare-protected and we haven't tested against Cloudflare yet. This is the real test that Phase 1b must answer.
