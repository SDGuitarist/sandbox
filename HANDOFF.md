# HANDOFF -- Sandbox

**Date:** 2026-04-19
**Branch:** master
**Phase:** Cycle complete (lead-scraper enrichment + venue-scraper multi-page crawl)

## Current State

Lead-scraper enrichment pipeline built (5 steps), reviewed (5-agent review), and all 17 todos resolved. Venue-scraper upgraded with multi-page crawling. DB stability issue investigated and resolved (CWD mismatch, not a WAL bug).

### What Shipped (8 commits, ed006ea..9016bee)

| Commit | What |
|--------|------|
| `ed006ea` | Bio parsing: emails, phones, social handles from bio text via regex |
| `dd6015c` | Deep website crawl via vdrmota/contact-info-scraper Apify actor |
| `727cf3f` | CSV export + web UI: email, phone, social columns |
| `e4e0f70` | Hunter.io Email Finder + Domain Search API integration |
| `764776d` | Venue scraper: multi-page crawling + --contacts-only export |
| `2bef7e3` | Venue scraper integration into lead enrichment pipeline |
| `17f3610` | P1 fixes: Hunter.io rate limiting, venue scraper cost cap, bio length cap |
| `9016bee` | P2/P3 fixes: persist unification, --step flag, social URL helper, domain fix |

**Tests:** 91 passing (lead-scraper), 25 passing (venue-scraper)
**Todos:** 17/17 complete (0 pending)

### Enrichment Pipeline (`python run.py enrich`)

| Step | Flag | Method | Cost |
|------|------|--------|------|
| 1 | `--step bio` | Regex on bio text | Free |
| 2 | `--step website` | HTTP GET + HTML parse | Free |
| 3 | `--step deep` | vdrmota/contact-info-scraper Apify actor | Free tier |
| 4 | `--step venue` | Crawl4AI + Claude Sonnet (max 15 URLs) | API credits |
| 5 | `--step hunter` | Hunter.io Email Finder + Domain Search | 25 free/month |

### Key Decisions

- Instagram profile actors (official + logical_scrapers) do NOT return email/phone -- web API only
- Pivoted to Hunter.io for high-accuracy email finding ($0 on free tier)
- Venue scraper subpaths trimmed from 8 to 2 (/contact, /about) -- 70% cost savings
- DB stability: "0 byte wipe" was CWD mismatch (sqlite3 CLI vs Python absolute paths), not WAL corruption

### Config Required

- `HUNTER_API_KEY` in lead-scraper `.env` (set)
- `ANTHROPIC_API_KEY` for venue scraper LLM extraction
- `APIFY_TOKEN` for deep crawl actor

## Previous State

Build #10 (workshop-tool) paused on `feat/workshop-support-tool`, waiting on Jotform API key. Builds #1-9 complete.

## Deferred Items

- Instagram profile enrichment with cookies (mobile API access for email/phone)
- Tier 2 enrichment (Maigret OSINT) -- deferred for brand safety
- Venue scraper anti-bot handling (some sites block headless browsers)
- Workshop tool (Build #10): still needs Jotform API key

## Feed-Forward

- **Hardest decision:** Killing Instagram profile enrichment after 2 spikes. Pivoted to Hunter.io which works.
- **Rejected alternatives:** Maigret OSINT (brand risk), Instagram Graph API (needs auth), bare @handle regex (false positives), 3 separate persist functions (unified to 1)
- **Least confident:** Whether the 5-step pipeline is overkill for 253 leads. The simplicity reviewer flagged that steps 3 (Apify deep crawl) and 4 (venue scraper) overlap. May want to drop step 3 if venue scraper consistently outperforms it.

## Prompt for Next Session

```
Read HANDOFF.md for context. Lead-scraper enrichment cycle is complete.
Next: either /workflows:compound to document lessons, or start a new feature.

To use the enrichment pipeline:
1. Import leads into DB
2. Run `python run.py enrich` (all steps) or `python run.py enrich --step hunter` (specific step)
3. Export: `python run.py export --output leads.csv`
```
