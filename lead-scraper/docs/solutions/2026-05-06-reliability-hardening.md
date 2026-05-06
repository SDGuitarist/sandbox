---
title: "Reliability Hardening: Inline Retry, Circuit Breakers, and Admin Overrides"
date: 2026-05-06
category: reliability
tags: [retry, circuit-breaker, resilience, 429, parse-retry-after, coalesce, migration, cli, sentinel]
module: enrich.py, resilience.py, models.py, campaign.py, run.py
symptom: "Perplexity 429s wasted credits (no retry), Hunter quota exhaustion went unnoticed, held leads required manual SQLite edits"
root_cause: "Missing retry on hook research, no circuit breaker on any enrichment loop, no CLI path for admin overrides"
---

# Reliability Hardening: Inline Retry, Circuit Breakers, and Admin Overrides

## Problem

Three reliability gaps in the lead-scraper enrichment pipeline:

1. **No retry on Perplexity hook research.** 429 rate limits returned a sentinel and skipped the lead. Credits were wasted rediscovering the same rate limit on the next batch.
2. **No circuit breaker on any enrichment loop.** If an API went down, the pipeline burned through all leads before anyone noticed. Perplexity outages could stall for ~10 minutes (60s timeout x 3 leads x 3 steps).
3. **No CLI path for admin overrides.** Held leads (low confidence, no hook) required `sqlite3 leads.db "UPDATE..."` to force-approve for campaigns.

## Key Decisions

### 1. Inline retry over decorator/class

The brainstorm proposed a `@with_retry` decorator + `CircuitBreaker` class in a new `resilience.py` module. Six review agents evaluated the plan. The **simplicity reviewer** argued this was over-engineering: the actual bug was one function missing retry, not an architecture gap. `_fetch_page` and `_hunter_get` already had working 6-line retry loops.

**Decision:** Inline retry loop in `_research_single_hook` only. Don't touch working code. `resilience.py` exports only `parse_retry_after()` and ANSI color constants.

**Why it matters for future work:** If you're adding a fourth API integration, add the retry inline. Don't create an abstraction until 4+ call sites need it. Three similar 6-line loops is better than a premature decorator that couples them.

### 2. Per-function failure signals (not generic `result is None`)

Each enrichment function has a different return type on failure:

| Function | Failure signal | What it means | NOT a failure |
|----------|---------------|---------------|---------------|
| `enrich_leads()` | No breaker (removed) | `_enrich_single_lead` returns empty dict on network failure, never raises | Empty updates = valid result |
| `enrich_with_hunter()` | `resp is None` | `_hunter_get` retries exhausted | 429, 402, "no results" (API responses) |
| `enrich_hook()` | `tier == -1` | Network error or 429 exhausted after retries | tier=0 (no hook found) |

**Critical lesson:** The `enrich_leads()` circuit breaker was removed during review because it could never trigger. `_enrich_single_lead` catches all network errors internally via `_fetch_page` returning None and just returns an empty dict. The `except Exception` in the loop only catches rare parse errors. **Always trace the actual failure path before adding a circuit breaker.**

### 3. Transient failures must never persist

The tier=-1 sentinel means "transient failure, do not persist." Without this, a 429 would write `hook_quality=0` to the database, permanently marking the lead as "no hook found" and preventing retry on the next batch.

**Invariant:** `enrich_hook()` line 1174: `if tier == -1: continue` -- skips `_persist_hook()`. Tested by `test_enrich_hook_429_leaves_hook_quality_null` which runs the full `enrich_hook()` function against a mock Perplexity returning 3x429 and asserts the database column stays NULL.

**Related pattern:** research-agent adaptive-batch-backoff doc. Same principle: only sleep after actual 429, not before every call.

### 4. Double-timing-mechanism interaction

`_research_single_hook` has its own retry sleeps (via `parse_retry_after`, up to 120s per attempt). The outer `enrich_hook()` loop has a 1.2s rate-limit sleep after each lead (line 1185). These interact:

- **On retry success:** Internal retries sleep (e.g., 10s on 429), then the outer loop persists and sleeps 1.2s. Sleeps stack but don't compound dangerously.
- **On retry exhaustion (tier=-1):** Outer loop `continue`s -- the 1.2s sleep is SKIPPED. No extra delay.
- **Worst case:** 3 attempts x 120s retry-after = 360s per lead. With 3 leads to trip the breaker: ~18 minutes. Acceptable because it means the API is actively rate-limiting us.

**The fix that saved 120s:** The final 429 attempt was sleeping before returning -1 (useless sleep). Moving `time.sleep(wait)` inside the `if attempt < 2` guard saves up to 120s per rate-limited lead. Found by the performance oracle during review.

### 5. COALESCE for admin flags on existing rows

`ALTER TABLE ADD COLUMN manual_approved INTEGER DEFAULT 0` sets DEFAULT for new INSERTs but existing rows get NULL (SQLite behavior). All queries use `COALESCE(manual_approved, 0)` to treat NULL as 0.

**5 query locations:**
- `query_held_leads()`: 4 UNION ALL branches, each with `AND COALESCE(manual_approved, 0) = 0`
- `assign_leads()`: `OR COALESCE(manual_approved, 0) = 1` with segment filter still applied

**The segment filter guard:** `manual_approved` bypasses hook_quality and segment_confidence gates but NOT the segment template filter. Without this, `generate_messages()` would crash with `FileNotFoundError` when loading a template for a nonexistent segment. Found by the security sentinel.

### 6. merge_leads preserves manual_approved

Standard `fill_fields` uses COALESCE semantics (fill NULL from dupes). But `manual_approved` needs OR/MAX semantics: if ANY duplicate in the merge group was approved, the keeper should be approved. Added as a special case after `fill_fields` processing.

## What Went Wrong During the Build

| Phase | Issue | Resolution |
|-------|-------|------------|
| Plan | Original plan proposed decorator + class (60 lines) | Simplicity reviewer cut to inline helper (25 lines) |
| Plan | `assign_leads` OR clause would bypass segment filter | Security + architecture reviewers caught it, added guard |
| Work | `enrich_leads()` got a circuit breaker that could never trigger | Codex review caught it -- `_enrich_single_lead` never raises |
| Work | Hunter percentage used wrong denominator (`start + used` instead of `start`) | Codex review caught it |
| Work | Final 429 attempt slept up to 120s for nothing | Performance oracle found it, 2-line fix |

## Prevention Strategies (Ranked by ROI)

1. **Trace the actual failure path before adding error handling.** The `enrich_leads()` breaker was dead code because no one checked whether `_enrich_single_lead` raises or returns. Read the function, don't assume.
2. **Test the sentinel at the integration level, not just unit.** `test_hook_research_429_exhausted_skips_persist` tests `_research_single_hook` in isolation. `test_enrich_hook_429_leaves_hook_quality_null` tests the full `enrich_hook()` path including the database. Both are needed -- the unit test caught the retry logic, the integration test caught the persist invariant.
3. **Cap server-controlled values.** `parse_retry_after` caps at 120s. Without the cap, a misconfigured server could hang the pipeline for days. This applies to any header or API response that controls sleep duration.
4. **Use COALESCE from day one when adding nullable columns.** Don't plan to "backfill later" -- you won't, and `WHERE col = 0` silently excludes NULL rows.

## Verification Commands

```bash
python -m pytest tests/test_resilience.py -v    # parse_retry_after safety
python -m pytest tests/test_hook.py -v          # 429 retry + integration test
python -m pytest tests/test_unhold.py -v        # unhold + merge + assignment
python -m pytest tests/ -q                      # full suite (154 tests)
python run.py leads unhold 1 && python run.py leads held
python run.py enrich --step hunter 2>&1 | tail -5
```

## Related Solution Docs

- `2026-04-21-v2-review-cascade-fixes.md` -- Rate-limit sentinel pattern (tier=-1) originated here
- `2026-04-19-contact-enrichment-5-step-pipeline.md` -- COALESCE persist pattern, module ownership
- `2026-05-05-init-db-wipes-data.md` -- Never call init_db() to query, always use absolute paths
- research-agent `adaptive-batch-backoff.md` -- Only sleep after actual 429

## Feed-Forward

- **Hardest decision:** Whether to remove the `enrich_leads()` circuit breaker during Codex review. The plan said to add it to all 3 loops. But `_enrich_single_lead` never raises on network failure, so it was dead code. Removing code you just added feels wrong but is the right call.
- **Rejected alternatives:** (1) Making `_enrich_single_lead` raise on network failure so the breaker would work. This would change the existing behavior of a working function just to enable a new feature. (2) Keeping the dead breaker "in case the function changes later." YAGNI.
- **Least confident:** The `merge_leads` manual_approved preservation uses `any(d.get("manual_approved") == 1 for d in group)`. This checks all leads in the group including the keeper. If the keeper already has `manual_approved=0` explicitly set (not NULL), the UPDATE will correctly change it to 1. But if `merge_leads` is ever called with leads not fetched from the database (e.g., synthetic data), the `get()` could return None instead of 0, and the OR semantics would be wrong. The test covers the real-world path.
