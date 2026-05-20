# HANDOFF -- Lead-Scraper

**Date:** 2026-05-20
**Branch:** master
**Phase:** Compound complete -- cross-pollination integration shipped and reviewed

## Current State

5-phase cross-pollination integration between lead-scraper and venue-scraper is complete. All phases implemented, 4-agent review done, 7 findings fixed, solution doc written, learnings propagated. 326 tests passing (4 pre-existing failures). The two repos are now connected via CSV handoff with type-based source dispatch, tiered LLM extraction, and SerpAPI discovery.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-05-19-cross-pollination-brainstorm.md |
| Plan | docs/plans/2026-05-19-feat-cross-pollination-lead-venue-integration-plan.md |
| Codex Review | docs/plans/2026-05-19-codex-review-findings.md |
| Solution | docs/solutions/2026-05-20-cross-pollination-lead-venue-integration.md |

## Deferred Items

- P2: `screen_leads()` can overwrite `email_domain_mismatch` reason with screening failure reason -- needs design decision about storing multiple hold reasons
- P2: `name` field always overwrites on venue upsert (no COALESCE) -- low probability with LLM extraction
- P2: Relative `CACHE_DIR` in google.py (CWD-dependent)
- P1 (arch): `WebsiteContactModel` defined twice (enrich.py + google.py) -- should deduplicate
- P1 (arch): `scrapers/google.py` imports private `_` functions from `enrich.py` -- should extract to shared module
- Pre-existing H1: SSRF bypass in `_verify_url_contains_hook()` -- not from this work but should fix

## Three Questions

1. **Hardest decision?** Keeping `unhold_lead()` narrow (manual_approved only) vs making it clear all holds. Chose narrow because `is_sendable` is shared with `screen_leads()` screening failures.
2. **What was rejected?** Shared DB (WRC incident), monolith (complexity), shared library (~700 lines doesn't justify packaging), Sonnet-only extraction (10x cost).
3. **Least confident about?** `screen_leads()` can overwrite `email_domain_mismatch` reason when a lead also fails screening. Deferred -- needs multiple-reason design.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is lead-scraper, a lead discovery and outreach pipeline.
Cross-pollination integration (5 phases) is complete and reviewed. 326 tests passing.
Next: run `python run.py enrich --step website --max-cost 10` to LLM-enrich the full lead batch,
or start a new feature cycle. Check deferred items in HANDOFF.md for cleanup opportunities.
```
