# Venue Intelligence Scraper - Brainstorm

**Date:** 2026-04-15
**Status:** Draft
**Phase:** Brainstorm

---

## What We're Building

A Python-based web scraping tool that extracts structured business intelligence from venue websites AND aggregator platforms, then stores it in a unified schema for research, competitive intel, and lead generation.

### Target Platforms
- **Wedding:** The Knot, Zola, WeddingWire
- **Gig/Event:** The Bash (formerly GigMasters), GigSalad
- **Review/General:** Yelp, Google Places
- **Individual venue websites** (any URL)

### Data Schema (Everything Possible)
- **Contact:** Name, email, phone, address, booking URL, social links
- **Business:** Capacity, pricing/packages, amenities, event types hosted
- **Reputation:** Star ratings, review counts, review excerpts
- **Media:** Photos, videos, virtual tour links
- **Availability:** Calendar data, booking windows, seasonal pricing
- **Vendor:** Preferred vendor lists, partnerships (from wedding platforms)

### Input Methods (Phased)
1. **Phase 1a:** List of URLs (paste URLs, scrape each)
2. **Phase 1b:** CSV of venue names/locations (lookup across platforms)
3. **Phase 2:** Search query ("wedding venues in San Diego" -> discover + scrape)

### Use Cases
- **Personal venue research** -- intel on venues for pitching, workshops, gigs
- **Competitive intelligence** -- pricing, services, market gaps
- **Lead generation** -- find and qualify venue leads for outcome-based services

---

## Why This Approach

### Approach: Crawl4AI + Claude API (Recommended)

AI-powered extraction with no brittle CSS selectors. The LLM adapts to each site's unique layout -- critical when scraping 8+ different platforms with different DOM structures.

**Stack:**
- **Crawl4AI** -- open source, handles JS rendering via Playwright, sends content to Claude for structured extraction
- **Claude API** -- extracts structured JSON from raw page content using a venue schema prompt
- **Playwright + stealth plugins** -- anti-detection for platform scraping
- **Residential proxies** -- required for The Knot, etc. at scale (IPRoyal, ~$1-5/mo at personal volume)
- **Supabase** -- result storage (existing connection available)
- **Redis + job queue** -- for batch processing (Phase 2)

**Why not alternatives:**
- **Scrapy + CSS selectors** -- would need separate selectors per platform, breaks when layouts change. Too fragile for 8+ platforms.
- **Firecrawl** -- great but costs scale fast. Crawl4AI gives same AI extraction, free.
- **Browser-use (vision agent)** -- too slow and expensive for batch scraping. Overkill.
- **Platform APIs only** -- Google Places and Yelp APIs cover basics, but The Bash, GigMasters, Zola, WeddingWire have no public APIs. Must scrape.

### Anti-Detection Strategy (for platforms)
- Playwright stealth plugin (patches webdriver detection)
- Residential proxy rotation (IPRoyal or SmartProxy)
- Fingerprint rotation (user-agent, timezone, canvas, WebGL)
- CAPTCHA solving via 2Captcha/CapSolver (~$1-3 per 1K solves)
- Polite rate limiting (2-5 second random delays)
- robots.txt respect

### Ethical Boundaries
- Public data only (no login bypassing)
- Use APIs where available (Google Places, Yelp Fusion) before scraping
- Respect robots.txt and rate limits
- Internal research use initially
- Venue websites actively want discovery -- low risk

---

## Key Decisions

1. **Python** -- matches sandbox ecosystem (18/19 apps), Crawl4AI is Python-native, strongest scraping libraries
2. **AI extraction over CSS selectors** -- LLM adapts per site, no maintenance when layouts change
3. **Buy proxies, don't build network** -- residential proxy providers are commodity ($50-500/mo), building a network requires thousands of opt-in users
4. **Phase 1 = CLI tool** -- no API server, no queue, no auth. Just: `python scrape.py urls.txt` -> JSON/Supabase
5. **Universal schema** -- one venue data model that works across all platforms, with platform-specific fields as optional
6. **Productization path** -- CLI -> API -> SaaS, credit-based pricing ($49/mo for 500 scrapes)

---

## Productization Path

### Phase 1a: Venue Website Scraper (Build First -- Ship This Week)
- Python CLI script: `python scrape.py urls.txt`
- Input: list of individual venue website URLs (not platforms)
- Output: structured JSON files
- No proxies, no anti-detection needed (venue sites want to be found)
- Goal: validate that Crawl4AI + Claude reliably extracts structured venue data
- Success = 5 venue websites scraped with consistent JSON output

### Phase 1b: Platform Scraping (Add One at a Time)
- Add platforms in order of difficulty: GigSalad -> The Bash -> The Knot/Zola/WeddingWire
- Add IPRoyal residential proxies when hitting first platform
- Add Yelp Fusion API integration (no scraping needed)
- Add stealth/fingerprint rotation as needed per platform
- Add CSV input (venue name lookup across platforms)
- Add Supabase storage + deduplication with conflict flags

### Phase 1c: Search Discovery
- Search query input ("wedding venues in San Diego")
- Auto-discover venues across platforms and scrape results

### Phase 2: API Service
- FastAPI endpoint: POST /scrape with URL -> returns structured JSON
- Job queue (Redis + BullMQ or Celery) for async processing
- Webhook delivery for completed jobs
- Basic API key auth
- Deploy on Railway

### Phase 3: Full Product
- Stripe billing (credit-based, $49/mo for 500 scrapes)
- Dashboard showing job status, results, history
- Proxy rotation built into infrastructure
- Pre-built "actors" per platform (like Apify marketplace)
- Vertical positioning: "Venue Intelligence API"

### Market Opportunity
- No one owns hospitality/venue scraping as a vertical
- PhantomBuster built $10M+ on social media scraping alone
- Credit-based model with 10-50x markup over cost ($2-5/1K pages cost vs $49/500 scrapes)

---

## Resolved Questions

1. **Data freshness** -- On-demand only. No scheduled re-scraping. Re-scrape when you specifically need updated data. Keeps it simple, avoids unnecessary proxy costs.
2. **Deduplication** -- Merge all sources, flag conflicts. Each venue record stores data from every source, with a conflict flag when values disagree (e.g., Yelp says capacity 200, venue site says 250). Manual review decides.
3. **Proxy provider** -- **IPRoyal** for start. Cheapest pay-as-you-go ($1.75/GB), no minimums, no expiry. At 10K-50K requests (~0.5-2.5GB), cost is $1-5/mo. Upgrade to SmartProxy ($4.50/GB, 55M IP pool) if IPRoyal's smaller pool (2M IPs) causes reliability issues on The Knot/WeddingWire.
4. **Platform ToS & anti-bot** -- All six platforms prohibit scraping in ToS. Practical assessment:
   - **Yelp**: Most aggressive. Has sued scrapers. **Use Yelp Fusion API instead** (free, 5K calls/day).
   - **The Knot / WeddingWire / Zola**: Cloudflare-protected. Moderate anti-bot. Residential proxies + stealth + polite rate limiting should work at low volume (<500 venues).
   - **The Bash**: Lighter Cloudflare protection. Lower risk.
   - **GigSalad**: Lightest protection. Lowest risk.
   - **Legal reality**: Public data on public pages is generally fair game (*hiQ v. LinkedIn*), but circumventing technical barriers is gray area under CFAA. At personal-use scale with polite behavior, practical risk is very low. Don't republish raw scraped data.

## Open Questions

1. **Live CAPTCHA testing** -- Need to actually visit each platform and see how quickly they challenge. Research says Cloudflare triggers on "suspicious patterns" not first visit, but we should verify hands-on before building.
2. **LLM extraction reliability** -- Will a single Claude prompt reliably extract structured data from wildly different page layouts (WordPress venue site vs. The Knot vendor profile vs. GigSalad listing)? Phase 1a will answer this. If extraction is inconsistent, we may need per-platform prompt tuning.

---

## Feed-Forward
- **Hardest decision:** Going AI extraction over CSS selectors. It's the right call for multi-platform scraping, but adds LLM API cost per page and makes output less deterministic.
- **Rejected alternatives:** Scrapy + per-platform selectors (too fragile), Firecrawl (costs scale), browser-use vision agent (too slow/expensive for batch).
- **Least confident:** Whether wedding platforms (The Knot, Zola, WeddingWire) will aggressively block scraping at even small scale (~200 venues). Research says Cloudflare triggers on patterns not first visits, and residential proxies help, but we haven't tested hands-on yet. Plan phase should include a 5-URL smoke test per platform before building the full pipeline.
