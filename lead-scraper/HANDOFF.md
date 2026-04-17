# Lead Scraper — Handoff

**Date:** 2026-04-16
**Branch:** master (all merged)
**Tests:** 38/38 passing
**Phase:** Cycle complete — ready for next task

## Current State

Full compound engineering cycle complete (brainstorm -> plan -> deepen -> work -> review -> fixes -> merge -> compound). 3 scrapers wired, enrichment pipeline working, 7 patterns documented in `docs/solutions/2026-04-16-lead-scraper-enrichment-expansion.md`.

## What Works Now

```bash
cd ~/Projects/sandbox/lead-scraper
source .venv/bin/activate
python run.py scrape --location "San Diego, CA"  # Eventbrite active, auto-enriches
python run.py enrich                              # enrich existing leads
python run.py export --output leads.csv           # includes phone, website, enriched_at
python run.py serve                               # Flask UI on localhost:5000
```

## Next Session: Enable Facebook + Instagram

### Task 1: Enable Facebook Groups scraper

In `config.py`, change `"enabled": False` to `"enabled": True` for facebook. Two SD groups already configured:
- `https://www.facebook.com/groups/1488967914699762/` — SD Actors and Filmmakers
- `https://www.facebook.com/groups/mexicanfilmmakerssd/` — Mexican Filmmakers in SD

**Risk:** Groups must be public. If private, scraper returns 0 leads with a warning. Test one group first.

**The actor returns posts/comments, not member lists.** Leads come from post authors and commenters. The normalizer (`scrapers/facebook.py`) handles this via `extract_leads_from_post()`.

### Task 2: Enable Instagram scraper

In `config.py`, change `"enabled": False` to `"enabled": True` for instagram. Hashtags configured:
- SanDiegoFilmmaker, SDCreatives, SanDiegoPhotographer, SanDiegoDesigner, SDContentCreator

**Risk:** Free tier limit is 100 profiles per run. Actor: `apify/instagram-profile-scraper`. The `usernames` field receives explore/tags URLs — undocumented behavior that may break.

**Instagram leads often have `externalUrl` (personal website)** — high-value for enrichment.

### Task 3: Run scrape + verify

```bash
python run.py scrape --location "San Diego, CA"
sqlite3 leads.db "SELECT source, COUNT(*) FROM leads GROUP BY source"
sqlite3 leads.db "SELECT COUNT(*) FROM leads WHERE email IS NOT NULL"
```

## Critical: Apify Actor Input Schema

The Eventbrite actor (`aitorsm/eventbrite`) accepts these parameters — previous bugs came from sending wrong param names:

```json
{
  "country": "united-states",
  "city": "San Diego",
  "category": "film-and-media",
  "keyword": "only used when category is 'custom'",
  "maxPages": 5
}
```

**Do NOT use:** `searchQueries`, `location`, `maxItems` — these are ignored by the actor.

## Key Files

| File | What it does |
|------|-------------|
| `config.py` | Enable/disable sources, keywords/hashtags, actor config |
| `scrapers/facebook.py` | Posts/comments normalizer + extract_leads_from_post() |
| `scrapers/instagram.py` | Hashtag-based profile scraper |
| `scrapers/eventbrite.py` | Per-keyword actor runs, handles both API formats |
| `enrich.py` | HTTP fetch + parse pipeline, SSRF protection |
| `enrich_parsers.py` | Pure HTML parsing (emails, phones) |
| `db.py` | migrate_db() with conditional backup |

## Docs

- **Solution:** `docs/solutions/2026-04-16-lead-scraper-enrichment-expansion.md`
- **Plan:** `docs/plans/2026-04-16-feat-lead-scraper-expansion-plan.md`
- **Prior build:** `docs/solutions/2026-04-15-lead-scraper-multi-source-pipeline.md`

## Deferred Work

- Tier 2 enrichment (Maigret OSINT) — build if Tier 1 hit rate stays <30%
- Tier 3 enrichment (Apify contact scraper) — build if Tiers 1+2 insufficient
- ThreadPoolExecutor — add when enrichment exceeds 15 minutes
- Twitter/X scraper — revisit on paid Apify plan
- Eventbrite category-based scraping (film-and-media, science-and-tech, arts, business)
- has-email/has-phone UI filters
