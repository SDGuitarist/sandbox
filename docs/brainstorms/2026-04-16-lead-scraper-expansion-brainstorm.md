# Lead Scraper Expansion — Brainstorm

**Date:** 2026-04-16
**Status:** Brainstorm complete
**Prior build:** docs/brainstorms/2026-04-15-lead-scraper-brainstorm.md

## What We're Building

Expand the lead scraper from 1 working source (Eventbrite) to 3 sources, and add a tiered contact enrichment pipeline that follows links to extract emails, phones, social profiles, and metadata.

**New sources:**
- Facebook Groups — SD Actors and Filmmakers, Mexican Filmmakers in SD (returns posts/comments, not member lists). Existing `scrapers/facebook.py` normalizer assumes member profiles — must be rewritten to extract leads from post authors and commenters instead.
- Instagram — hashtag search (#SanDiegoFilmmaker, #SDCreatives, etc.) + cross-reference existing leads

**Dropped:** Twitter/X — too expensive on free Apify plan ($3 min/run or $0.04/tweet). Revisit if upgrading to paid plan.

**Enrichment pipeline (waterfall — free first, paid for gaps):**
- Tier 1 (free): Scrape each lead's profile_url website for emails + social links in HTML
- Tier 2 (free): Maigret open-source OSINT tool — extract username from profile URL, find linked accounts across 3100+ sites
- Tier 3 (paid, manual): `vdrmota/contact-info-scraper` via `--deep-enrich` flag for leads that tiers 1-2 missed
- Store enriched data as new columns on the existing leads table
- Skip leads that are already enriched (WHERE enriched_at IS NULL)

**Discovery strategy:** Two-pronged
1. Hashtag/keyword search on Instagram for SD creatives
2. Follow-the-links: Eventbrite organizer URL -> their website -> social links in HTML/footer, Schema.org sameAs, contact page emails

**Cross-reference approach:** Deterministic matching via published links, NOT fuzzy name matching. Follow the chain of links people published themselves. ~90%+ precision.

## Why This Approach

### Waterfall enrichment (not blast-everything-through-paid-API)
Tiers 1-2 are free and cover ~70-80% of leads. Tier 3 (paid) only runs on demand via `--deep-enrich` for the remaining ~20%. Total monthly cost: under $5 (likely $0 for most runs).

**Rejected alternative:** Auto-enrich everything through paid API. Burns $2-3/run on leads that free tiers would have caught. Over a month of daily scraping, adds up.

### Skip Twitter (for now)
Instagram gives ~1,600 profiles/mo on free tier. Twitter gives ~125 tweets or costs $3 minimum per run. Instagram creatives are also more likely workshop targets.

**Rejected alternative:** Include Twitter via xtdata ($3 min/run) or apidojo ($0.04/tweet). Cost/reward ratio is bad on free plan.

### Linear pipeline (not queue-based)
The existing architecture is a simple linear pipeline: config -> scrape -> normalize -> ingest -> enrich. No job queue, no background workers. A `WHERE enriched_at IS NULL` filter skips already-enriched leads.

**Rejected alternative:** Event-driven queue with retries. YAGNI for a SQLite CLI tool.

### In-place columns (not separate table)
Enrichment data goes directly on the leads table as new columns. One row per lead, no joins.

**Rejected alternative:** Separate enriched_contacts table. Adds JOIN complexity for no benefit at this scale.

## Architecture

```
                      SCRAPE PHASE
          +----------------------------------+
          |                                  |
  Eventbrite ─┐                              |
  Facebook  ──┤── normalize() ──> ingest() ──┤
  Instagram ──┘                              |
          +----------------------------------+
                           │
               ENRICH PHASE (auto, free)
          +----------------------------------+
          |  SELECT * FROM leads             |
          |  WHERE enriched_at IS NULL       |
          |         │                        |
          |  Tier 1: HTTP fetch profile_url  |
          |    → extract emails, social links|
          |    → parse Schema.org sameAs     |
          |         │                        |
          |  Tier 2: Maigret username lookup  |
          |    → find linked accounts (3100+)|
          |         │                        |
          |  UPDATE leads SET email=...,     |
          |    phone=..., enriched_at=NOW    |
          +----------------------------------+
                           │
             DEEP ENRICH (manual, --deep-enrich)
          +----------------------------------+
          |  Tier 3: vdrmota/contact-info    |
          |  Only leads still missing email  |
          |  ~$0.002/page, ~2500 pages free  |
          +----------------------------------+
```

### Data Ownership (from past learnings)

| Table | Writer | Reader(s) |
|-------|--------|-----------|
| leads (scrape columns) | ingest.py only | enrich.py, Flask views, exports |
| leads (enrichment columns) | enrich.py only | Flask views, exports |

This avoids the dual-writer bug flagged in the chain-reaction solution doc.

## Key Decisions

1. **Waterfall enrichment** — free tiers auto, paid tier manual via `--deep-enrich`
2. **In-place columns** — no separate enrichment table
3. **Skip-if-enriched** — `enriched_at IS NULL` prevents re-processing
4. **Data ownership split** — ingest.py writes scrape columns, enrich.py writes enrichment columns
5. **Follow-the-links, not fuzzy names** — deterministic matching via published URLs
6. **Full harvest + metadata** — extract everything: emails, phones, social links, company, job title
7. **Skip Twitter** — bad cost/reward on free plan, revisit on paid plan
8. **Facebook returns posts/comments** — leads come from post authors and commenters (name + profile link), not a member list. Existing facebook.py normalizer must be rewritten.
9. **Maigret for free OSINT** — open-source username lookup across 3100+ sites, runs locally

## Resolved Questions

1. **Instagram actor pricing** — ~$0.003/profile, free tier gets ~1,600 profiles/mo. 100 per run limit on free tier. No login required.
2. **Facebook groups scraper output** — returns posts and comments with commenter name + profile link. Does NOT return member lists. Public groups only, no login needed.
3. **Cross-reference matching** — follow published links (deterministic), not fuzzy name matching. Eventbrite organizer URL -> website -> social links. Maigret for username-based lookups.
4. **Rate limiting** — waterfall approach means Tier 3 (paid) only hits ~50-60 leads max. Free tier contact scraper handles ~2,500 pages/mo. No batching needed.
5. **Enrichment cost control** — Tiers 1-2 are free. Tier 3 is manual via `--deep-enrich`. Monthly cost: ~$0-5.

## New Schema Columns

```sql
ALTER TABLE leads ADD COLUMN phone TEXT;
ALTER TABLE leads ADD COLUMN website TEXT;
ALTER TABLE leads ADD COLUMN instagram_url TEXT;
ALTER TABLE leads ADD COLUMN twitter_url TEXT;
ALTER TABLE leads ADD COLUMN linkedin_url TEXT;
ALTER TABLE leads ADD COLUMN company TEXT;
ALTER TABLE leads ADD COLUMN job_title TEXT;
ALTER TABLE leads ADD COLUMN enriched_at TEXT;
```

## Apify Actors

| Source | Actor | Free Tier |
|--------|-------|-----------|
| Instagram profiles | apify/instagram-profile-scraper | ~1,600 profiles/mo |
| Facebook groups | apify/facebook-groups-scraper | ~1,000 posts/mo |
| Contact info (Tier 3) | vdrmota/contact-info-scraper | ~2,500 pages/mo |

## New / Modified Files

- `scrapers/instagram.py` — new: normalize + scrape for Instagram profiles
- `scrapers/facebook.py` — rewrite: normalize must handle posts/comments format, not member profiles
- `enrich.py` — new: waterfall enrichment pipeline (Tier 1: HTTP scrape, Tier 2: Maigret, Tier 3: Apify)
- `tests/fixtures/instagram_raw.json` + `instagram_normalized.json`
- `tests/fixtures/facebook_raw.json` + `facebook_normalized.json` — must reflect actual posts/comments shape
- `tests/fixtures/enrich_raw.json` (contact scraper output sample)

## Touch Points for New Sources

Each new scraper requires edits in 3 places:
1. `scrapers/newsource.py` — normalize() + scrape()
2. `config.py` — add SOURCES entry
3. `run.py` — add to scraper_map dict in cmd_scrape()

## New Dependencies

- `maigret` — pip install, runs locally, no API key needed
- `beautifulsoup4` or similar — for Tier 1 HTML parsing of profile websites

## Facebook Group URLs (San Diego)

- `https://www.facebook.com/groups/1488967914699762/` — SD Actors and Filmmakers
- `https://www.facebook.com/groups/mexicanfilmmakerssd/` — Mexican Filmmakers in SD

## Instagram Hashtags (San Diego)

- #SanDiegoFilmmaker, #SDCreatives, #SanDiegoPhotographer
- #SanDiegoDesigner, #SDContentCreator, #SanDiegoFreelancer

## Feed-Forward
- **Hardest decision:** Waterfall enrichment tiers. Free-first is cost-optimal but adds implementation complexity (3 enrichment paths vs 1). Chose it because the cost savings are dramatic ($0 vs $2-3/run).
- **Rejected alternatives:** Twitter (bad free-tier pricing), queue-based enrichment (YAGNI), separate enrichment table (unnecessary joins), auto Tier 3 (burns credits on leads free tiers would catch), fuzzy name matching (low precision).
- **Least confident:** Maigret reliability — it's an OSINT tool that depends on 3100+ sites not blocking it. May need fallback if hit rates are low. Test with a few leads before building the full pipeline.
