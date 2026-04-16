# Lead Scraper — Brainstorm

**Date:** 2026-04-15
**Status:** Brainstorm complete

## What We're Building

A multi-source lead scraper that finds potential clients for Amplify workshops, audits, and outcome sprints. It scrapes creative communities across 4 platforms, deduplicates and stores leads in SQLite, and provides a Flask web UI for viewing/filtering plus CSV export.

**Immediate need:** Fill 29 remaining seats for April 25 Amplify AI workshop in San Diego.
**Long-term value:** Reusable lead generation tool for future workshops in any city.

## Why This Matters

- Directly supports the revenue ladder (workshops -> audits -> sprints)
- Builds a proprietary lead database (moat asset)
- Passes the 30-day outcome test: usable leads for April 25 workshop
- New sandbox pattern: first scraper project, teaches web scraping fundamentals

## Architecture: Pipeline Approach

Each source gets its own scraper module. All feed into a shared SQLite database. A Flask web UI sits on top for viewing, filtering, deduplication, and CSV export.

```
scrapers/
  meetup.py        # Direct scraping / API
  eventbrite.py    # Direct scraping / API
  facebook.py      # Apify actor integration
  linkedin.py      # Apify actor integration

models/
  lead.py          # SQLite schema, dedup logic

app.py             # Flask web UI + CSV export
```

### Scraper Interface Contract

Every scraper module exposes one function: `scrape(location, **config) -> list[dict]`. Each dict matches the Lead schema (name, bio, location, email, profile_link, activity, source). This makes sources interchangeable and testable independently.

### Why Pipeline Over Alternatives

- **vs Apify-First:** More learning value, less external dependency, lower cost
- **vs Hybrid:** Cleaner architecture — one pattern per source, consistent interface
- **vs Monolithic:** Easier to add/remove sources, run them independently

## Target Sources

| Source | Method | Why |
|--------|--------|-----|
| Meetup | Direct scrape / API | FilmNet SD + creative groups. People who show up to things. Highest intent. |
| Eventbrite | Direct scrape / API | Past attendees of similar workshops/creative events. Proven ticket buyers. |
| Facebook groups | Apify actor | SD film, music, creative groups. High volume, lower conversion. |
| LinkedIn | Apify actor | SD-based creatives. Professional context = more likely to invest $150. |

## Data Per Lead

Full profile where available:
- Name
- Bio / interests
- Location (city/region)
- Email (if publicly available)
- Platform profile link
- Activity signals (events attended, groups joined, recent posts)
- Source platform (for dedup across sources)

## Key Decisions

1. **Pipeline architecture** — modular scraper-per-source, shared SQLite storage
2. **All 4 sources from the start** — full system build, not incremental
3. **Apify for Facebook + LinkedIn** — they handle anti-bot; direct scraping for Meetup + Eventbrite
4. **Configurable location** — not hardcoded to San Diego, reusable for future cities
5. **SQLite + CSV export** — matches sandbox patterns, dual output
6. **Flask web UI** — view, filter, deduplicate, export leads

## Open Questions

1. **Meetup/Eventbrite data access** — Do these platforms expose enough data publicly, or will we need API keys / authenticated sessions? Rate limits? This determines whether "direct scraping" is realistic or if we fall back to Apify for these too.
2. **Apify cost per run** — What do the Facebook and LinkedIn actors cost? Need to confirm this fits within budget for repeated scraping runs.
3. **Deduplication strategy** — When the same person appears on Meetup AND LinkedIn, what's the merge key? Name + location is fuzzy. Email is reliable but often missing.

## Tech Stack

- Python / Flask (matches sandbox convention)
- SQLite (matches sandbox convention)
- BeautifulSoup + requests (Meetup, Eventbrite scraping)
- Apify Python client (Facebook, LinkedIn actors)
- CSV module (export)

## Feed-Forward

- **Hardest decision:** Going with all 4 sources at once vs shipping 1-2 fast. User chose full build, which means more upfront work but a complete system.
- **Rejected alternatives:** Apify-first (too much external dependency, less learning), hybrid (inconsistent patterns), ship-fast with 2 sources (user wants the full system).
- **Least confident:** See Open Question #1 (Meetup/Eventbrite data access). If both require auth or paid API keys, the "direct scraping" half of the architecture collapses and we'd need Apify for all 4 sources -- changing the cost model and reducing learning value.
