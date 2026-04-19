---
status: pending
priority: p1
issue_id: "009"
tags: [code-review, performance, api]
---

# Hunter.io API Rate Limiting Missing

## Problem Statement
`enrich_with_hunter()` makes up to 2 HTTP requests per lead with zero delay. Hunter.io limits to 10 req/sec. With 587 leads, the code fires ~1,174 requests at full speed, hits 429, and permanently skips all remaining leads with `break`. No retry, no backoff.

## Findings
- **Source:** Performance Oracle + Security Sentinel
- **File:** `enrich.py` lines 468-563
- **Evidence:** No `time.sleep()` or backoff in the loop. 429 handler at lines 515-516 does `break` (stop forever), not retry.
- **Risk:** API key gets throttled. Free plan has 25 searches/month -- a single run blows through it.

## Proposed Solutions

### Option A: Simple delay (Recommended)
Add `time.sleep(0.2)` between leads (5 req/sec, well under limit).
- **Pros:** 1 line, no dependencies
- **Cons:** Adds ~2 min for 587 leads
- **Effort:** Small (5 min)
- **Risk:** None

### Option B: Retry with exponential backoff on 429
On 429, wait `retry-after` header seconds, then retry. Max 3 retries.
- **Pros:** Handles bursts gracefully
- **Cons:** More complex, 429 may indicate daily limit not just rate limit
- **Effort:** Medium (30 min)

## Acceptance Criteria
- [ ] Delay between Hunter.io requests prevents 429 responses
- [ ] 429 response triggers wait + retry, not permanent skip
- [ ] Free plan credits (25/month) are not exhausted in one run
