---
title: Venue Scraper Low-Effort Upgrades
date: 2026-05-05
status: complete
next_phase: plan
feed_forward:
  risk: "SerpAPI free tier may not return enough film-specific results for SD"
  verify_first: true
---

# Venue Scraper Low-Effort Upgrades

## What We're Building

Three upgrades batched together for autopilot execution:

1. **Auto-discover URLs via Google search (SerpAPI)** -- Given search queries like "film school San Diego" or "production studio San Diego", automatically find venue URLs and feed them into the scraper. Eliminates manual URL curation.

2. **Smarter subpage discovery** -- Instead of only checking hardcoded `/contact` and `/about`, parse the homepage links and find the actual contact/team page regardless of what it's called.

3. **CSV export for outreach** -- Output a ready-to-use outreach list with columns: name, email, phone, website, venue_type. Designed for the user's existing outreach workflow.

## Why This Approach

**Goal:** Find film venues in San Diego (film schools, production studios, post houses, screening rooms, film commissions) and extract contact info for partnership outreach to promote the May 30 Amplify AI workshop.

**Why batch these three:**
- Search discovery feeds the scraper with URLs (input)
- Smarter subpage discovery improves extraction quality (processing)
- CSV export makes the output immediately actionable (output)
- Together they create an end-to-end pipeline: query -> URLs -> scrape -> outreach list

**Why autopilot:** These are well-scoped, independent modules that don't require human judgment during implementation. Clear interfaces between them.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Search provider | Google via SerpAPI | Reliable, structured, free tier (100/mo), API key required |
| Geographic scope | San Diego only | Workshop is local, partnerships work best nearby |
| Target venues | Film-specific | Film schools, studios, post houses, screening rooms, commissions |
| Subpage discovery | Parse CrawlResult.links from homepage | Find real contact pages; hardcoded paths as fallback |
| CSV columns | name, email, phone, website, venue_type | Matches outreach template needs |
| Output location | Same `results/` dir | `results/outreach.csv` alongside existing JSON |

## Scope Boundaries

**In scope:**
- `discover.py` -- new module: SerpAPI search -> list of URLs
- Update `crawler.py` -- link-based subpage discovery (keep hardcoded paths as fallback)
- `export.py` -- new module: JSON results -> CSV outreach list
- Update `scrape.py` CLI -- add `--search "query"` and `--csv` flags
- Predefined search queries for film venues in San Diego

**Out of scope (future cycles):**
- Relevance scoring (medium effort -- separate cycle)
- Lead-scraper integration
- Scheduling/cron
- Multi-city support
- CRM integration

## Technical Notes

- SerpAPI returns structured JSON with `organic_results[].link` -- straightforward to extract URLs
- SerpAPI key read from `SERPAPI_API_KEY` env var (same pattern as ANTHROPIC_API_KEY)
- **Subpage discovery approach:** After the homepage is fetched (Crawl4AI already has the HTML), parse `result.links` for anchor text matching keywords ("contact", "get in touch", "about", "team", "connect", "inquir") -- case-insensitive substring match. Take the first match per keyword category (contact-like, about-like). Max 3 subpages total (homepage + 2 discovered). Fall back to hardcoded `/contact` + `/about` if zero links match.
- No extra HTTP request needed -- Crawl4AI's `CrawlResult` already exposes page links
- CSV uses Python stdlib `csv` module (no new dependency)
- Existing cost controls (15 URL cap, 3 concurrency) still apply

## Open Questions

None -- all resolved through dialogue.

## Feed-Forward

- **Hardest decision:** Whether to parse homepage links OR just expand the hardcoded subpath list. Chose link parsing because it's more robust long-term, with hardcoded paths as fallback.
- **Rejected alternatives:** DuckDuckGo (unreliable), Perplexity (costs per query), full-site crawl (too expensive), broad creative venues (too noisy for film workshop).
- **Least confident:** Whether SerpAPI free tier returns enough film-specific results for San Diego. May need to test with 3-4 queries before committing to full implementation.
