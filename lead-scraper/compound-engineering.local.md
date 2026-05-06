---
review_agents:
  - security-sentinel
  - performance-oracle
  - architecture-strategist
  - code-simplicity-reviewer
  - kieran-python-reviewer
---

# Review Context -- Lead Scraper

## Risk Chain

**Brainstorm risk:** "Circuit breaker reset strategy -- resetting per batch run is simple but means a flaky API that recovers mid-batch won't be retried."

**Plan mitigation:** Per-function circuit breaker instances (not shared across steps). Batch-reset is acceptable. Simplified from class to inline counter.

**Work risk (from Feed-Forward):** "The _research_single_hook retry loop coordinates with two existing timing mechanisms: parse_retry_after() sleep on 429 and the existing time.sleep(1.2) rate-limit sleep in enrich_hook() outer loop."

**Review resolution:** 8 agents, 1 P1 + 4 P2 + 1 P3. All P1/P2 fixed. enrich_leads() breaker removed (dead code -- function never raises). Hunter pct denominator fixed. Final-429 sleep waste fixed. Codex caught 4 additional issues, all resolved. 154 tests pass.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| enrich.py | Retry loop in _research_single_hook, circuit breakers in 2 loops, Hunter alerts | Double-timing interaction, failure signal correctness |
| resilience.py | parse_retry_after (120s cap), ANSI color constants | Security cap, TTY detection |
| models.py | COALESCE in 4 UNION branches, unhold_lead, merge preservation | NULL handling, admin flag ownership |
| campaign.py | assign_leads OR clause with segment guard | SQL grouping correctness |
| run.py | leads unhold CLI, null segment warning | CLI validation completeness |

## Plan Reference

`docs/plans/2026-05-06-feat-reliability-hardening-plan.md`
