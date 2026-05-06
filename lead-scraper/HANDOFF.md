# Lead Scraper -- Handoff

**Date:** 2026-05-06
**Branch:** master (all commits pushed)
**Tests:** 154 passing
**Phase:** Reliability hardening complete (brainstorm -> plan -> work -> review -> compound)

## What Was Done

### Phase 1: Outreach Intelligence Pipeline (PR #3, merged)
- Segment classification (Claude Haiku 4.5), hook research (Perplexity Sonar Pro)
- Campaign CRUD, message generation, queue review/approve/skip/sent workflow
- 10 review fix commits: indexes, batch DB, path containment, anti-injection, --limit flag, conftest

### Phase 2: Opener Quality + Security Hardening (PR #4, merged)
- Opener prompt: benchmark 2/5 -> 5/5 (banned words + conversation-opening rule)
- CSV import sanitization, CSRF protection, phone column warning

### Phase 3: Hardening Deferrals (direct to master)
- Null byte stripping in sanitize function
- Renamed sanitize_csv_cell -> sanitize_cell_value (dual-use clarity)

## Deferred Items (Closed)

| Item | Decision | Rationale |
|------|----------|-----------|
| Template caching | Won't fix | 3 templates, ~5ms worst case, premature optimization |
| .env parser quoted values | Won't fix | Use python-dotenv if needed |
| CSRF upgrade to Flask-WTF | Defer until on-network | Localhost-only, X-Requested-With sufficient |
| CSP headers + static JS | Defer until on-network | Jinja2 autoescaping blocks stored XSS |

## Verified

- Opener benchmark: 5/5 on real scraped data (Sentakku, Greenbook, Packt, Mehmet, LearneRRing)
- --limit default (50): confirmed adequate for 663-lead dataset

## What Was Done (Reliability Hardening -- 2026-05-06)

- Inline retry loop in `_research_single_hook` (3 attempts, 429 handling with `parse_retry_after` capped at 120s, timeout split to (5, 60))
- Circuit breaker counters in `enrich_with_hunter` and `enrich_hook` (trip at 3 consecutive failures)
- Colored Hunter.io quota alerts (ANSI with TTY detection) + end-of-run credit summary
- `manual_approved` column + `leads unhold <id>` CLI command
- `assign_leads()` template guard (approved leads still require valid segment)
- `merge_leads()` preserves manual_approved with OR/MAX semantics
- 12 new tests (2 resilience, 4 hook/429, 8 unhold/merge)
- 8-agent review: 1 P1 + 4 P2 fixed, 1 P3 deferred (023-pending-p3-held-count-dedup.md)

## Solution Docs

- `docs/solutions/2026-05-06-reliability-hardening.md` **(NEW)**
- `docs/solutions/2026-04-19-contact-enrichment-5-step-pipeline.md`
- `docs/solutions/2026-04-21-v2-review-cascade-fixes.md`
- `docs/solutions/2026-04-21-v2-phase2-opener-benchmark-and-security.md`

## Feed-Forward

- **Hardest decision:** Whether to remove the `enrich_leads()` circuit breaker during Codex review. `_enrich_single_lead` never raises on network failure, so the breaker was dead code. Removing code you just added feels wrong but is the right call.
- **Rejected alternatives:** (1) Full @with_retry decorator + CircuitBreaker class -- over-engineering for 3 call sites where 2 already work. (2) Keeping the dead `enrich_leads()` breaker "in case the function changes later" -- YAGNI.
- **Least confident:** The double-timing interaction between `_research_single_hook` retry sleeps and the outer `enrich_hook()` 1.2s rate-limit sleep. Worst case is ~6min per lead if Perplexity returns 429 with Retry-After: 120 three times. Tested but not load-tested.
