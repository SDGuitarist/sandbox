---
status: pending
priority: p1
issue_id: "010"
tags: [code-review, performance, cost]
---

# Venue Scraper Timeout Too Short + Uncapped Cost

## Problem Statement
`enrich_with_venue_scraper()` has a 600-second subprocess timeout. Each URL crawls 9 subpages with LLM extraction. At 3 concurrency, only ~17 URLs fit in 10 minutes. More than that = timeout, partial results lost (temp dir cleaned up), API credits burned for nothing. At 500 URLs, estimated cost is ~$86 per run.

## Findings
- **Source:** Performance Oracle + Simplicity Reviewer
- **File:** `enrich.py` line 633 (subprocess timeout), `crawler.py` lines 42-55 (CONTACT_SUBPATHS)
- **Evidence:** 8 subpaths + base = 9 pages per URL. CONCURRENCY_LIMIT = 3. Each page = LLM call at ~$0.02.
- **Risk:** Burns Anthropic API credits on URLs that never complete. Silent failure.

## Proposed Solutions

### Option A: Cap URLs + trim subpaths (Recommended)
Add `MAX_VENUE_URLS = 15` in enrich.py. Trim CONTACT_SUBPATHS to `["/contact", "/about"]` (3 pages instead of 9). This cuts cost by ~70% and fits within timeout.
- **Pros:** Simple, huge cost savings, fits within timeout
- **Cons:** May miss contact info on /booking or /private-events pages
- **Effort:** Small (10 min)
- **Risk:** Low

### Option B: Batch processing with intermediate persistence
Process 10 URLs at a time, persist results between batches, increase timeout.
- **Pros:** Handles any number of URLs
- **Cons:** More complex, longer total runtime
- **Effort:** Medium (1 hour)

## Acceptance Criteria
- [ ] Venue scraper never processes more than 15 URLs per run
- [ ] CONTACT_SUBPATHS reduced to /contact and /about
- [ ] Subprocess timeout matches expected runtime for capped URL count
