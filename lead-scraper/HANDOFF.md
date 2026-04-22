# Lead Scraper -- Handoff

**Date:** 2026-04-21
**Branch:** `feat/v2-outreach-intelligence` (PR #3 against master)
**Tests:** 139/139 passing
**Phase:** Review fixes -- fix P1s and P2s, then merge

## Current State

Phase 1 implemented (11 commits). 5-agent review completed (Security, Architecture, Performance, Simplicity, Learnings). 17 findings: 3 P1, 7 P2, 7 P3. P3s deferred to Phase 2.

## Next Session: Fix P1s and P2s

Apply fixes in cascade order (zero-risk first, behavioral second, additive last).

### P1 -- BLOCKS MERGE

| # | Fix | File | Est. |
|---|-----|------|------|
| 1 | Add indexes on leads(segment, hook_quality) and outreach_queue(campaign_id, status) | schema_campaigns.sql | 2 min |
| 2 | Batch DB connections -- refactor persist functions to accept connection, not open per lead | enrich.py, campaign.py | 15 min |
| 3 | Update .env.example with all 4 required keys | .env.example | 2 min |

### P2 -- SHOULD FIX

| # | Fix | File | Est. |
|---|-----|------|------|
| 4 | Add `--limit` flag to enrich steps + campaign generate (default 50) | run.py | 10 min |
| 5 | Skip _persist_hook on 429 -- don't write hook_quality=0 for rate-limited leads | enrich.py | 5 min |
| 6 | Move _available_segments() to config.py -- models.py imports from campaign.py (reverse dep) | campaign.py, models.py, config.py | 10 min |
| 7 | Remove campaigns.status column (dead -- never updated) | schema_campaigns.sql | 5 min |
| 8 | Path containment check in _read_template() | campaign.py | 2 min |
| 9 | Anti-injection note in LLM system prompts | enrich.py, campaign.py | 5 min |
| 10 | Extract test helpers to conftest.py (duplicated in 6 files) | tests/conftest.py | 15 min |

### P3 -- DEFER TO PHASE 2

- CSV formula injection on import
- CSRF on Flask delete endpoint
- Cache templates in generate loop
- Extract _transition_status() helper
- CSV field map redundant keys
- CSV phone column warning
- .env parser quoted values

### Implementation Order

1, 3, 8, 5, 9, 7, 6, 4, 2, 10

Zero-risk schema/config first. Behavioral fixes second. Additive refactors last. Each fix is one commit. Run tests after each.

## Key Files

| File | What to change |
|------|---------------|
| schema_campaigns.sql | Add 2 indexes, remove status column |
| enrich.py | Batch connections in segment/hook loops, skip persist on 429, anti-injection prompt |
| campaign.py | Batch connections in generate loop, path check, anti-injection prompt, move _available_segments |
| models.py | Update import after _available_segments move |
| config.py | Add _available_segments() |
| .env.example | Add HUNTER_API_KEY, PERPLEXITY_API_KEY, ANTHROPIC_API_KEY |
| run.py | Add --limit flag to enrich and campaign generate |
| tests/conftest.py | New file with shared _setup_db and _insert_lead |

## Review Agents Used

Security Sentinel, Architecture Strategist, Performance Oracle, Code Simplicity Reviewer, Learnings Researcher (solution doc cross-reference)

## Feed-Forward

- **Hardest decision:** Whether to batch DB connections (changes the persist function signatures) or just add indexes (simpler). Both P1. Do both -- indexes are zero-risk, batching is the right architecture.
- **Rejected alternatives:** Keeping campaigns.status column "for future use" (YAGNI -- dead columns confuse). Persisting hook_quality=0 on 429 (breaks retry, learnings researcher flagged this from gig-lead-responder pattern).
- **Least confident:** The --limit flag default (50). Too low slows down legitimate batches. Too high risks accidental cost. May need user feedback after first real campaign to calibrate.
