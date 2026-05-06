---
title: Venue Scraper Search Discovery + CSV Pipeline
date: 2026-05-05
tags: [serpapi, crawl4ai, csv-export, web-scraping, link-discovery, ssrf-protection]
problem: Manually curating venue URLs and missing contact pages on non-standard paths
outcome: End-to-end pipeline from Google search query to outreach-ready CSV with smart subpage discovery
difficulty: medium
reuse_potential: high
---

## Problem

The venue-scraper required manual URL curation (urls.txt) and only checked hardcoded /contact + /about paths. For the May 30 workshop outreach, we needed to find ~30-40 San Diego film venues automatically and get contact info from pages regardless of their URL path.

## Solution

Three modules added to create a full pipeline: search -> scrape -> export.

### 1. SerpAPI Search Discovery (discover.py)

- Google search via SerpAPI returns venue URLs from organic results
- Filters out directory/social sites (yelp, facebook, etc.) by domain
- Deduplicates by domain (one result per website)
- Disk cache (./serpapi_cache/) saves free-tier credits during development
- 4 predefined queries for film venues: schools, studios, post houses, commissions

### 2. Link-Based Subpage Discovery (crawler.py)

- After homepage crawl, parse `CrawlResult.links["internal"]` for contact/about pages
- Keyword matching on anchor text: "contact", "get in touch", "inquir", "about", "team", "connect"
- SSRF protection: `_is_same_origin()` validates scheme + netloc before following any discovered link
- Additive fallback: always tries hardcoded /contact + /about if cap allows (prevents data loss)
- `networkidle` wait only for homepage (link discovery needs JS); `domcontentloaded` for subpages (faster)

### 3. CSV Export (export.py)

- Formula injection prevention: prefix `'` on cells starting with `=-+@|`
- Control character stripping: null bytes, tabs, carriage returns, newlines
- Skips venues with no email AND no phone (not actionable for outreach)
- Always creates file with headers (even if zero rows)

## Key Lessons

### Performance: Split wait strategies by purpose

`networkidle` adds ~2.5s per page vs `domcontentloaded`. Only use it where you need JS-rendered content (homepage for link discovery). Subpages only need text content -- use faster `domcontentloaded`. Saved ~37 seconds per 15-venue run.

### Security: Same-origin validation on crawled links

A malicious page can include internal links pointing to `//evil.com` or `file:///etc/passwd`. Always validate resolved URLs against the base URL's origin before following. The `_is_same_origin()` pattern (check scheme + netloc) is minimal and effective.

### Cost control: Disk cache for external API calls during development

SerpAPI free tier (100/mo) burns credits on every test run -- no sandbox mode. Caching raw JSON responses to disk means you only hit the API once per query. Parse/filter logic can be iterated for free. Trade-off: cache goes stale (no TTL currently).

### Cache the LLM strategy singleton

`LLMExtractionStrategy` instantiation runs `model_json_schema()` every time. At 30+ calls per run, caching at module level eliminates redundant work. Simple `global` pattern is appropriate for a single-process CLI tool.

### Additive fallback > exclusive fallback

When link-based discovery finds 1 match, don't skip hardcoded paths entirely. Append hardcoded paths that weren't already found, up to the cap. This prevents data loss when /contact exists but isn't linked from the homepage (e.g., only in footer which is excluded by `excluded_tags`).

## Risk Resolution

**Flagged risk (from brainstorm):** "Whether SerpAPI free tier returns enough film-specific results for San Diego."
**What happened:** Web search verification returned 30-40 unique venue URLs across 4 queries. Actual API would perform even better (more results per page).
**Learned:** Verifying external API results before planning is fast (5 minutes) and eliminates the biggest uncertainty early.

**Flagged risk (from plan):** "Whether networkidle significantly increases crawl time."
**What happened:** Performance review quantified it: ~37s added for 15 venues. Fixed by splitting strategies (networkidle for homepage only).
**Learned:** Wait strategies should be purpose-specific, not global. Different pages in the same pipeline have different rendering needs.

## Feed-Forward

- **Hardest decision:** Additive vs exclusive fallback for subpage discovery. Chose additive -- max 1-2 extra requests per venue, prevents silent data loss.
- **Rejected alternatives:** Two-phase double-crawl (wastes a request), global networkidle (too slow), import-time API key validation (breaks non-search users).
- **Least confident:** Whether `excluded_tags` in Crawl4AI affects `CrawlResult.links` extraction. Research says no (links extracted from full DOM before tag exclusion), but unverified on live venues. The additive fallback protects against this if wrong.
