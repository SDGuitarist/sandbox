---
title: "Contact Enrichment: 5-Step Pipeline with API Spikes, Multi-Page Crawling, and Review"
date: 2026-04-19
tags:
  - enrichment-pipeline
  - web-scraping
  - email-extraction
  - contact-data
  - hunter-io
  - apify
  - crawl4ai
  - regex
  - multi-agent-review
  - sqlite
problem_type: integration-pipeline
components:
  - lead-scraper/enrich.py
  - lead-scraper/enrich_parsers.py
  - lead-scraper/run.py
  - lead-scraper/db.py
  - venue-scraper/crawler.py
  - venue-scraper/models.py
  - venue-scraper/scrape.py
severity: P0
root_cause: |
  587 leads with only 24 emails (4%). Instagram/Facebook leads had zero contact info.
  Instagram web API does not expose email/phone fields (confirmed via 2 spikes).
  Solved with 5-step enrichment pipeline + Hunter.io for high-accuracy email finding.
  DB stability false alarm caused by CWD mismatch in sqlite3 CLI vs Python absolute paths.
---

# Contact Enrichment: 5-Step Pipeline

## Problem

587 leads in the database from Eventbrite, Facebook Groups, and Instagram hashtags. Only 24 had email addresses (all from Eventbrite organizer pages). Instagram and Facebook leads had zero contact info. The scraper collected names and profile URLs but the enrichment pipeline couldn't extract emails or phones because social media profiles require authentication to view.

## Investigation: What Failed

### Instagram Profile Actor Spikes (Both Failed)

**Spike 1: `apify/instagram-profile-scraper` (official)**
- Returns: `biography`, `externalUrls` (array), `followersCount`, `isBusinessAccount`
- Does NOT return: `publicEmail`, `publicPhoneNumber`, or any contact fields
- Root cause: Uses Instagram's web API, which no longer exposes contact info

**Spike 2: `logical_scrapers/instagram-profile-scraper`**
- Returns: `bio`, `bioLinks`, `homepage`, `followers`
- Does NOT return: email or phone fields
- Same root cause: web API only

**Conclusion:** Instagram email/phone requires the mobile API with session cookies. No free Apify actor provides this. Spike results saved in `docs/spikes/2026-04-18-ig-profile-actor-output.md`.

**Lesson:** Always spike external APIs before planning features around them. Save output as fixtures. Both spikes cost < $0.01 and saved days of wasted implementation.

## What Worked: 5-Step Enrichment Pipeline

```bash
python run.py enrich              # all 5 steps
python run.py enrich --step bio   # specific step
python run.py enrich --step hunter
```

### Step 1: Bio Parsing (free, no network)

Regex extraction of emails, phones, and social handles from bio text already in the database. Keyword-prefix-only matching for social handles prevents false positives.

**Key pattern -- keyword-prefix regex:**
```python
# GOOD: requires "IG", "instagram", or "insta" before the handle
r"\b(?:IG|instagram|insta)[:\s|]+@?([a-zA-Z0-9_.]{3,30})\b"

# BAD: bare @handle matches "d-IG-ital" -> captures "ital"
r"(?:IG)[:\s]*@?([a-zA-Z0-9_.]+)"
```

The `\b` word boundary and `+` (require separator) are both essential. Without `\b`, "IG" matches inside "digital". Without `+`, "Instagramif" matches "if" as a handle.

### Step 2: Website Fetch (free, HTTP)

Existing pipeline: HTTP GET on profile_url and website, parse HTML with BeautifulSoup for `mailto:` links and email regex in visible text. SSRF protection validates all resolved IPs against private ranges, including post-redirect validation.

### Step 3: Deep Crawl (Apify free tier)

`vdrmota/contact-info-scraper` crawls lead websites and their subpages (/contact, /about, /press). Extracts structured data: emails, phones, Instagram handles, Twitter handles, LinkedIn profiles, Facebook pages.

### Step 4: Venue Scraper (Anthropic API credits)

Crawl4AI + Claude Sonnet multi-page LLM extraction. Upgraded from single-page to multi-page crawling (/contact, /about). The LLM reads pages intelligently and extracts contact info that regex misses (e.g., email in paragraph text, phone in a contact form description).

**Cost controls:**
- URLs capped at 15 per run (`MAX_VENUE_URLS = 15`)
- Subpaths trimmed from 8 to 2 (`/contact`, `/about`) -- 70% cost savings
- Called via subprocess to isolate venvs

**Test result:** Music Box SD returned zero contact info from homepage-only scrape. Multi-page scrape found `BoxOffice@MusicBoxSD.com` + `619-795-1337` from the /contact page.

### Step 5: Hunter.io (25 free/month)

Email Finder API (name + domain) with Domain Search fallback. Highest accuracy of any step.

**Rate limiting:** 0.25s delay between requests, retry on 429 with `Retry-After` header.

**Test result:** Found `cathy@bluewillowbookshop.com` with 99% confidence.

## Architecture Decisions

### Unified Persist Function

All 5 enrichment steps use a single `_persist_lead_update()` with COALESCE to never overwrite existing data:

```python
def _persist_lead_update(lead_id, updates, db_path=DB_PATH):
    conn.execute("""UPDATE leads SET
        email = COALESCE(email, :email),
        phone = COALESCE(phone, :phone),
        website = COALESCE(website, :website),
        social_handles = COALESCE(social_handles, :social_handles),
        enriched_at = COALESCE(enriched_at, :enriched_at)
    WHERE id = :id""", ...)
```

Originally had 5 separate persist functions (3 named + 2 inline SQL). Unified during review. **Lesson:** Extract shared persist logic from the start when adding enrichment steps.

### Social Handles as JSON Array

Stored as `TEXT` column with JSON arrays: `["instagram:user", "twitter:handle"]`. JSON (not comma-separated) because handles can contain commas. Parsed with `json.loads()` on read. The `normalize_social_urls()` helper in `enrich_parsers.py` converts full URLs to `platform:handle` format.

### Independent Enrichment State

`ig_profile_enriched_at` tracks Instagram profile enrichment separately from `enriched_at` (which `cmd_scrape` auto-sets). Two independent enrichment paths that don't block each other.

## DB Stability Investigation

### Symptom
`leads.db` appeared to "wipe to 0 bytes" repeatedly during the session.

### Root Cause
**CWD mismatch, not a WAL bug.** The `sqlite3` CLI commands used relative `leads.db` paths. When CWD was `sandbox/` (parent directory), `sqlite3 leads.db` created a ghost 0-byte file at `sandbox/leads.db` instead of accessing `sandbox/lead-scraper/leads.db`. Python code always used the correct absolute path (`Path(__file__).parent / "leads.db"`).

### Prevention
Always use absolute paths in CLI commands when working with SQLite databases.

## Code Review: 5-Agent Review, 17 Todos Resolved

### Agents Used
Security Sentinel, Architecture Strategist, Performance Oracle, Code Simplicity Reviewer, Learnings Researcher

### Key Findings

| Priority | Finding | Fix |
|----------|---------|-----|
| P1 | Hunter.io no rate limiting | Added 0.25s delay + retry-after |
| P1 | Venue scraper uncapped cost | MAX_VENUE_URLS=15, subpaths 8->2 |
| P2 | 5 duplicated persist functions | Unified to `_persist_lead_update()` |
| P2 | No `--step` CLI flag | Added `--step bio/website/deep/venue/hunter/all` |
| P2 | Hardcoded venue scraper path | Configurable via `VENUE_SCRAPER_DIR` env var |
| P2 | No bio length cap (ReDoS risk) | `text = text[:10_000]` before regex |
| P3 | Duplicated social URL parsing | Extracted `normalize_social_urls()` |
| P3 | Domain substring false match | Changed to exact domain comparison |

### Discarded Finding
`_merge_social_handles` flagged as dead code by simplicity reviewer. Investigation showed it IS needed: website crawl queries filter on `email IS NULL`, not `social_handles IS NULL`, so a lead can get social handles from bio parsing AND from deep crawl.

## Prevention Strategies

1. **Spike external APIs before planning.** Save output as fixtures. Cost: < $0.01. Savings: days of wasted implementation.

2. **Use absolute paths for database access.** `Path(__file__).parent / "db.db"` in Python. Full paths in CLI commands.

3. **Extract shared persist functions from the start.** One function, one UPDATE pattern, one place to fix bugs.

4. **Keyword-prefix regex for social handles.** Require word boundary + separator. Never match bare `@handle`.

5. **Calculate LLM extraction cost before running.** Cap URLs, trim subpaths, estimate: `N_urls * N_pages * cost_per_call`.

6. **Always rate-limit paid API integrations.** Add delay, check credits before batch, handle 429 with retry-after.

## Related Documentation

- `docs/solutions/2026-04-16-lead-scraper-enrichment-expansion.md` -- Prior enrichment pipeline (SSRF, BeautifulSoup, schema migration)
- `docs/solutions/2026-04-15-lead-scraper-multi-source-pipeline.md` -- Multi-source scraping architecture
- `docs/spikes/2026-04-18-ig-profile-actor-output.md` -- Instagram actor spike results
- `docs/plans/2026-04-18-feat-contact-info-enrichment-plan.md` -- Original plan (revised 3x)

## Feed-Forward

- **Hardest decision:** Killing Instagram profile enrichment after 2 spikes confirmed no email/phone. Pivoted to Hunter.io which actually works.
- **Rejected alternatives:** Maigret OSINT (brand risk), Instagram Graph API (needs auth), bare @handle regex (false positive flood), comma-separated social_handles (handles can contain commas), 3 separate persist functions (unified to 1).
- **Least confident:** Whether the 5-step pipeline is overkill. Steps 3 (Apify deep crawl) and 4 (venue scraper) overlap in capability. May want to drop step 3 if venue scraper consistently outperforms it. Needs data comparison on a larger dataset.
