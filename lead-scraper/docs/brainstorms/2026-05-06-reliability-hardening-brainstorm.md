---
title: "Lead-Scraper Reliability Hardening"
date: 2026-05-06
status: brainstorm
tags: [reliability, retry, circuit-breaker, alerts, cli]
---

# Lead-Scraper Reliability Hardening

## What We're Building

Three reliability improvements to the lead-scraper enrichment pipeline:

1. **Unified retry decorator with circuit breaker** -- A shared `@with_retry` decorator and `CircuitBreaker` class that all enrichment API calls use. Replaces the three different retry patterns currently in `enrich.py` with one consistent approach. Circuit breaker trips after 3 consecutive failures and stops calling that API for the rest of the batch.

2. **Hunter.io spend alerts (louder)** -- The code already warns at 30% and stops at <1 remaining. The gap is visibility: warnings are just print statements that scroll past. Make the 30% warning unmissable (colored output, summary at end of run).

3. **CLI `unhold` command** -- Force-approve held leads for campaign assignment regardless of computed hold reasons (low confidence, no hook, bad hook, unsupported segment). Single boolean flag on the lead, checked in `query_held_leads()`.

## Why This Approach

- **Decorator pattern** was chosen over minimal patching because there are already 3 different retry implementations in `enrich.py` (`_fetch_page`, `_hunter_get`, `_research_single_hook`). Consolidating now prevents a fourth pattern and makes behavior consistent across all API calls.
- **Circuit breaker at 3 failures** is aggressive by design -- these are paid APIs. Better to stop fast and surface the issue than burn quota on a down service.
- **Force unhold** (not per-reason override) keeps it simple. One column (`manual_approved`), one command. The hold reasons are computed dynamically so overriding individual reasons would fight the query logic.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Retry scope | Unified decorator for all API calls | DRY, consistent, testable |
| Circuit breaker threshold | 3 consecutive failures | Aggressive -- protects paid API quota |
| Alert threshold | 30% remaining (existing) | Already implemented, just needs louder output |
| Alert mechanism | Colored terminal output + end-of-run summary | No external dependencies needed |
| Unhold behavior | Force override (single boolean) | Simpler than per-reason granularity |
| Existing retry code | Refactor to use new decorator | Small regression risk but worth the consistency |

## Architecture Note: Two Layers

- **Retry layer** (network): `@with_retry` wraps pure HTTP call functions only (e.g., the actual `requests.get` inside `_hunter_get`, the Perplexity API call inside `_research_single_hook`). Never wraps functions that mix API calls with DB writes -- retrying those risks duplicate writes.
- **Circuit breaker layer** (batch loop): `CircuitBreaker` is checked in the enrichment loop *before* processing each lead. If tripped, the loop skips that API step for remaining leads. Resets at the start of each batch run.

## Scope Boundaries

### In scope
- `@with_retry` decorator with configurable max_retries, backoff_base, retryable exceptions
- `CircuitBreaker` class (trips at 3, resets per batch run)
- Refactor `_fetch_page`, `_hunter_get`, `_research_single_hook` to use decorator
- Colored 30% Hunter.io warning (ANSI escape codes, no dependencies) + quota summary at end of enrichment run
- `manual_approved` column on leads table (migration)
- `python run.py leads unhold <lead_id>` CLI command
- Update `query_held_leads()` to exclude manually approved leads
- Tests for retry, circuit breaker, unhold

### Out of scope
- Structured logging (separate initiative)
- Async/concurrent enrichment
- Alerts for Perplexity or Apify quota
- Per-reason hold overrides
- External notification (email/Slack alerts)

## Resolved Questions

- **Should we touch working retry code?** Yes -- consolidate into shared decorator for consistency.
- **Alert delivery method?** Terminal only. No external services.
- **Unhold granularity?** Force override all reasons. Simple boolean flag.

## Feed-Forward

- **Hardest decision:** Whether to refactor working retry code (`_fetch_page`, `_hunter_get`) into the new decorator. Risk of regression, but three different retry patterns in one file is a maintenance problem.
- **Rejected alternatives:** Minimal patch (fix only Perplexity, leave existing retry code alone). Would have been safer but adds a fourth retry pattern.
- **Least confident:** Circuit breaker reset strategy -- resetting per batch run is simple but means a flaky API that recovers mid-batch won't be retried. May need a time-based reset later.
