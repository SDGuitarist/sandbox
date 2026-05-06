---
title: "feat: Add retry helper, inline circuit breaker, Hunter alerts, and unhold CLI"
type: feat
status: active
date: 2026-05-06
origin: docs/brainstorms/2026-05-06-reliability-hardening-brainstorm.md
feed_forward:
  risk: "Adding retry to _research_single_hook changes 429 behavior from skip-and-retry-later to retry-now. The -1 sentinel and 1.2s rate-limit sleep must coordinate with retry_request()."
  verify_first: true
---

# feat: Reliability Hardening -- Retry, Circuit Breaker, Alerts, Unhold

## Enhancement Summary

**Deepened on:** 2026-05-06
**Research agents used:** 6 (Python retry best practices, architecture strategist, security sentinel, performance oracle, code simplicity reviewer, learnings researcher)

### Key Improvements from Deepening
1. **Simplified approach**: Don't refactor working retry code in `_fetch_page` and `_hunter_get`. Only fix the actual bug (Perplexity missing retry). Use inline counters instead of CircuitBreaker class.
2. **Security**: Cap `retry-after` header at 120s, handle non-integer values (HTTP-date format). Add template guard to `assign_leads` to prevent `FileNotFoundError`.
3. **Performance**: Split Perplexity timeout to `(5, 60)` connect/read -- reduces circuit breaker trip time from ~10min to ~87s. Add jitter to backoff (AWS best practice).
4. **Correctness**: Use `COALESCE(manual_approved, 0) = 0` in queries (not `manual_approved = 0`) to handle NULL existing rows.

### Simplification Decision (Simplicity Reviewer vs Architecture Reviewer)
The original plan proposed a `@with_retry` decorator + `CircuitBreaker` class in a new `resilience.py` module. The simplicity reviewer argued this is over-engineering: the actual bug is one function missing retry, and a circuit breaker is just a counter. The architecture reviewer validated the two-layer design but agreed the approach could be lighter.

**Decision: Simplify.** Don't refactor `_fetch_page` or `_hunter_get` (they work). Add a small `retry_request()` helper function + `parse_retry_after()` in `resilience.py`. Use inline `consecutive_fails` counters instead of a class. This cuts ~120 lines from the plan while keeping the reliability gains.

## Overview

Three reliability improvements to the lead-scraper enrichment pipeline (see brainstorm: `docs/brainstorms/2026-05-06-reliability-hardening-brainstorm.md`):

1. **`retry_request()` helper + inline `consecutive_fails` counters** -- Add retry to `_research_single_hook()` (the actual bug). Add 3-failure counters to enrichment loops to stop calling a failing API. Don't touch working retry code in `_fetch_page` or `_hunter_get`.
2. **Louder Hunter.io 30% spend alert** -- ANSI colored warnings + end-of-run credit summary.
3. **CLI `leads unhold <lead_id>`** -- Force-approve held leads via `manual_approved` column.

## Problem Statement

- Perplexity hook research (the most expensive enrichment step) detects 429s but does not retry -- it skips the lead. Credits are wasted on the next run rediscovering the same rate limit.
- `_research_single_hook` is the only enrichment function with no retry. `_fetch_page` and `_hunter_get` already retry and work fine.
- Hunter.io quota warnings are print statements that scroll past unnoticed. Users discover exhaustion after the fact.
- Held leads require manual SQLite UPDATE to override. No CLI path exists.

## What Must Not Change

- **Single-writer rule**: `enrich.py` owns UPDATE on enrichment columns, `ingest.py` owns INSERT, `campaign.py` owns campaign tables (see brainstorm).
- **DB safety**: No concurrent DB access. `retry_request()` wraps HTTP calls only, never functions that write to leads.db. (Memory: lost 1,093 leads twice from concurrent access.)
- **Anthropic SDK retries**: `anthropic.Anthropic(max_retries=3)` at `enrich.py:927` stays as-is. Do not wrap Claude calls with `retry_request()`.
- **COALESCE persist pattern**: `_persist_lead_update()` only fills NULLs. Do not change this.
- **Existing test suite**: All 142 tests must continue passing.

## Proposed Solution

### Phase 1: New module `resilience.py` (~25 lines)

Create `/Users/alejandroguillen/Projects/sandbox/lead-scraper/resilience.py` with helpers (no classes):

#### `parse_retry_after()` helper (security hardened)

```python
def parse_retry_after(header_value, fallback=10.0):
    """Parse Retry-After header with a 120s safety cap.
    
    Handles integer seconds and HTTP-date format. Returns fallback
    on missing/unparseable values. Caps at 120s to prevent hangs
    from misconfigured servers.
    """
    MAX_RETRY_WAIT = 120
    if header_value is None:
        return fallback
    try:
        wait = int(header_value)
    except (ValueError, TypeError):
        return fallback  # Handles HTTP-date format gracefully
    return min(max(0, wait), MAX_RETRY_WAIT)
```

- **Security**: Caps at 120s (prevents 11-day hangs from malicious/misconfigured Retry-After headers).
- **Graceful**: Returns fallback on non-integer values (HTTP-date format per RFC 9110).

#### Color constants (not functions)

```python
import sys

_IS_TTY = sys.stdout.isatty()  # Cached at module level

YELLOW = "\033[33m" if _IS_TTY else ""
RED = "\033[31m" if _IS_TTY else ""
GREEN = "\033[32m" if _IS_TTY else ""
RESET = "\033[0m" if _IS_TTY else ""
```

- **Constants, not functions** -- simpler, used inline at print sites.
- **Cached `isatty()`** at module level -- the TTY status never changes mid-process. Easier to test (monkeypatch `_IS_TTY`).
- Automatically omits ANSI codes when piped to file/cron (lesson from SpecFlow: `schedule` command pipes to `/tmp/lead-scraper.log`).

### Phase 2: Add retry to `_research_single_hook` + inline circuit breaker counters (~45 lines changed)

#### 2a. `_research_single_hook()` exact 429 behavior

**Current** (enrich.py:1058-1062): On 429, sleeps `retry-after` seconds, returns `(None, None, -1)`. The caller (`enrich_hook` line 1125) sees tier=-1 and skips persist, so the lead stays eligible for retry on the next batch.

**New behavior**: Wrap the `session.post()` in a retry loop that handles both transient network errors AND 429s:

```python
def _research_single_hook(session, api_key, name, context):
    """Research one lead. Returns (hook_text, source_url, tier).
    
    tier=-1 means transient failure (429 exhausted or network error).
    Caller must NOT persist tier=-1 -- lead stays eligible for retry.
    """
    prompt = _HOOK_PROMPT_TEMPLATE.format(name=name, context=context)

    for attempt in range(3):
        try:
            resp = session.post(
                PERPLEXITY_API_URL, ...,
                timeout=(5, 60),  # 5s connect, 60s read
            )
        except (requests.Timeout, requests.ConnectionError):
            if attempt < 2:
                delay = random.uniform(0, 2 ** attempt)
                time.sleep(delay)
                continue
            return (None, None, -1)  # All retries exhausted -> transient failure

        if resp.status_code == 429:
            wait = parse_retry_after(resp.headers.get("retry-after"), fallback=10.0)
            print(f"rate limited, waiting {wait:.0f}s...", end=" ")
            time.sleep(wait)
            if attempt < 2:
                continue
            return (None, None, -1)  # 429 exhausted -> transient failure

        if resp.status_code != 200:
            return (None, None, 0)  # Non-transient API error -> persist as "no hook"

        # ... parse JSON, extract hook, return (hook_text, source_url, tier) ...

    return (None, None, -1)  # Should not reach, safety net
```

**Key invariant preserved**: tier=-1 means "transient failure, do not persist." The caller in `enrich_hook()` (line 1125) already handles this correctly: `if tier == -1: continue`. This ensures hook_quality=0 is never persisted on a transient failure.

**What changed vs current code**: 429s are now retried up to 3 times (using `parse_retry_after()` with 120s cap) instead of being immediately skipped. On success after retry, the lead is processed normally. On exhaustion, tier=-1 is returned (same as before).

#### 2b. Hunter.io 429 handling: use `parse_retry_after()` too

Hunter's inline 429 handler at enrich.py:568 also uses `int(resp.headers.get("retry-after", 10))` -- same unbounded sleep / non-integer crash risk. Replace with `parse_retry_after()`:

```python
# enrich.py line 568 (Email Finder 429)
wait = parse_retry_after(resp.headers.get("retry-after"), fallback=10.0)

# enrich.py line 602 area (Domain Search 429 -- currently just breaks)
# No change needed, it breaks the loop.
```

This applies the 120s safety cap to Hunter.io too (not just Perplexity).

#### 2c. What does NOT change (and why):

| Function | Reason |
|----------|--------|
| `_fetch_page()` (line 89) | Working 3-retry loop. No reason to touch. |
| `_hunter_get()` (line 490) | Working 3-retry loop. No reason to touch. |
| `_check_hunter_quota()` (line 466) | Runs once; if API is down, enrichment calls will also fail. |
| `enrich_segment()` (Claude) | Anthropic SDK has internal `max_retries=3` |
| `run_actor()` (Apify) | SDK call, not raw HTTP |
| `enrich_with_venue_scraper()` | Subprocess, not HTTP |
| `enrich_from_bios()` | Local parsing, no network |

#### 2d. Perplexity timeout fix (performance-critical):

Split Perplexity timeout from `timeout=60` to `timeout=(5, 60)` (5s connect, 60s read). Already shown in the pseudocode above. This reduces circuit breaker trip time from ~10min to ~87s during outages. (Performance reviewer finding.)

#### 2e. Inline circuit breaker counters -- per-function failure signals

Each enrichment function has a different failure signal. The counter must match the actual code, not a generic `result is None`:

**`enrich_leads()` (website fetch):**
```python
consecutive_fails = 0
for i, lead in enumerate(leads, 1):
    if consecutive_fails >= 3:
        print(f"{RED}3 consecutive failures in website fetch. "
              f"Skipping remaining {len(leads) - i} leads.{RESET}")
        break
    try:
        updates = _enrich_single_lead(lead, session)
        consecutive_fails = 0  # Reset on success (even if no contact info found)
        _persist_lead_update(lead["id"], updates, db_path)
        result.leads_processed += 1
        # ... print results ...
    except Exception as e:
        consecutive_fails += 1  # _enrich_single_lead raises on network failure
        print(f"FAILED: {str(e)[:80]}")
```
**Failure signal**: `except Exception`. The function `_enrich_single_lead` does not return None -- it raises on network errors (from `_fetch_page` returning None and subsequent operations). "No contact info found" returns an empty dict, which is success (not a failure).

**`enrich_with_hunter()` (Hunter.io):**
```python
consecutive_fails = 0
for i, lead in enumerate(leads, 1):
    if consecutive_fails >= 3:
        print(f"{RED}3 consecutive failures in hunter. "
              f"Skipping remaining {len(leads) - i} leads.{RESET}")
        break
    # ... existing code ...
    resp = _hunter_get(session, ...)
    if resp is None:
        consecutive_fails += 1  # _hunter_get returns None on exhausted retries
        print("network error")
        continue
    consecutive_fails = 0  # Got a response (even if no results)
    # ... existing 429/402/200 handling ...
```
**Failure signal**: `resp is None` (from `_hunter_get`). This is correct here because `_hunter_get` explicitly returns `Response | None`. 429 and 402 are handled after the None check and do NOT increment the counter (they are API responses, not network failures).

**`enrich_hook()` (Perplexity hook research):**
```python
consecutive_fails = 0
for i, lead in enumerate(leads, 1):
    if consecutive_fails >= 3:
        print(f"{RED}3 consecutive failures in hook research. "
              f"Skipping remaining {len(leads) - i} leads.{RESET}")
        break
    # ... existing code ...
    hook_text, source_url, tier = _research_single_hook(session, api_key, ...)
    if tier == -1:
        consecutive_fails += 1  # tier=-1 = transient failure (network or 429 exhausted)
        print("skipped (transient failure)")
        continue
    consecutive_fails = 0  # Got a real result (even if tier=0 / no hook)
    _persist_hook(lead["id"], hook_text, source_url, tier, conn=conn)
    # ...
```
**Failure signal**: `tier == -1` (transient failure -- network error or 429 exhausted after retries). tier=0 ("no hook found" or non-200 API response) is NOT a counter failure because it represents a legitimate API response, not an outage.

**Summary of failure signals per function:**

| Function | Failure signal | What it means | NOT a failure |
|----------|---------------|---------------|---------------|
| `enrich_leads()` | `except Exception` | `_enrich_single_lead` raised | Empty updates dict (no contact info) |
| `enrich_with_hunter()` | `resp is None` | `_hunter_get` retries exhausted | 429, 402, "no results" (all are API responses) |
| `enrich_hook()` | `tier == -1` | Network error or 429 exhausted | tier=0 (no hook found), tier=1-5 (valid result) |

**Common rules for all counters:**
- Trip at 3 consecutive failures. `break` from loop (does NOT raise).
- Subsequent steps still run when using `--step all`.
- Counter is a local variable, fresh per function call.
- Print count of skipped leads using `RED` constant when tripping.

### Phase 3: Hunter.io alerts (~20 lines changed in `enrich.py`)

Modify `_check_hunter_quota()` and `enrich_with_hunter()`:

1. **Store pre-run balance**: Save `remaining` from `_check_hunter_quota()` at batch start.
2. **Color the 30% warning**: Use `YELLOW`/`RED`/`RESET` constants for 30%/10% thresholds.
3. **End-of-run summary**: Call `_check_hunter_quota()` again at end (skip if consecutive_fails >= 3 -- API is down), compute delta.

```
HUNTER.IO SUMMARY: Used 8 credits this run. 17/25 remaining (68%).
```

Or if under threshold:

```
WARNING: HUNTER.IO LOW -- Used 8 credits. Only 4/25 remaining (16%).
```

### Phase 4: `leads unhold` command (~40 lines across 3 files)

#### 4a. Migration: `db.py` `migrate_db()`

Add to `new_columns` list (line 37):
```python
("manual_approved", "INTEGER DEFAULT 0"),
```

Existing pattern handles the ALTER TABLE and backup. No backfill needed -- queries will use `COALESCE(manual_approved, 0)` to treat NULL as 0.

#### 4b. Model: `models.py` `query_held_leads()`

Add to each of the 4 UNION parts:
```sql
AND COALESCE(manual_approved, 0) = 0
```

This excludes manually approved leads from the held list. Uses COALESCE to handle NULL existing rows safely (lesson from SpecFlow Gap 19).

Add new function:
```python
def unhold_lead(lead_id: int, db_path=DB_PATH) -> bool:
    """Set manual_approved=1 for a lead. Returns True if lead existed."""
```

#### 4c. Campaign assignment: `campaign.py` `assign_leads()`

Restructure the WHERE clause so manually approved leads bypass quality/confidence gates BUT still require a valid segment template:

```sql
WHERE segment IN ({placeholders})
  AND (
    (hook_quality > 0 AND hook_quality <= ? AND segment_confidence >= 0.7)
    OR COALESCE(manual_approved, 0) = 1
  )
```

**Why the segment filter stays**: If a manually approved lead has segment "wellness" and no `wellness.md` template exists, `generate_messages()` would crash with `FileNotFoundError` at `_read_template()`. The segment guard prevents this. (Security reviewer + Architecture reviewer finding.)

This resolves SpecFlow Gap 15: without this change, unholding a lead would only affect `leads held` display but NOT make the lead eligible for campaigns. The user expects "unhold = eligible for campaigns."

#### 4d. CLI: `run.py`

Add `unhold` subcommand to `leads_sub` (near line 362):
```python
sp_unhold = leads_sub.add_parser("unhold", help="Force-approve a held lead")
sp_unhold.add_argument("lead_id", type=int, help="Lead ID to approve")
```

Handler `cmd_unhold(args)`:
1. Look up lead by ID (get name for confirmation).
2. If lead doesn't exist, print error and `sys.exit(1)`.
3. Call `unhold_lead(args.lead_id)`.
4. Print: `"Approved lead 42 (Sacha Boutros). Was held for: no_hook."` (show name and hold reason for confirmation).

No batch unhold in v1. No `leads hold` reverse command in v1 -- document the manual SQLite path in help text.

### Phase 5: Tests (~60 lines in new test files)

#### `tests/test_resilience.py` (2 tests -- focused on `parse_retry_after`)

- `test_parse_retry_after_caps_at_120` -- pass `"999"`, assert returns 120. Pass `"60"`, assert returns 60. Pass `None`, assert returns fallback.
- `test_parse_retry_after_handles_non_integer` -- pass `"Thu, 01 Dec 2026 16:00:00 GMT"`, assert returns fallback (not crash). Pass `""`, assert returns fallback.

**Testing pattern for retry behavior**: The retry loop lives inside `_research_single_hook`, so 429 retry behavior is tested in `test_hook.py` (see below), not in `test_resilience.py`. Patch `time.sleep` where it's imported (`enrich.time.sleep`). Use `side_effect` lists for failure sequences. Assert sleep values in a range (jitter makes exact values unpredictable).

#### `tests/test_unhold.py` (6 tests)

- `test_unhold_excludes_from_held` -- insert lead with hook_quality=0, unhold, assert not in `query_held_leads()`.
- `test_unhold_nonexistent_lead` -- call with bad ID, assert returns False.
- `test_unhold_enables_campaign_assignment` -- insert lead with hook_quality=0, unhold, run `assign_leads()`, assert lead is assigned.
- `test_unhold_unsupported_segment_not_assigned` -- insert lead with unsupported segment, unhold, run `assign_leads()`, assert lead is NOT assigned (template guard). (Security test.)
- `test_unhold_persists_across_enrichment` -- unhold lead, re-enrich with low confidence, assert still approved.
- `test_null_manual_approved_treated_as_not_approved` -- insert lead without setting column, assert appears in held.

#### `tests/test_hook.py` (2 new tests added to existing file)

- `test_hook_research_retries_429_then_succeeds` -- mock Perplexity returning 429 then 200. Assert lead is processed on second attempt (tier > 0, not skipped with -1). Verify hook_quality is persisted.
- `test_hook_research_429_exhausted_skips_persist` -- mock Perplexity returning 429 three times. Assert tier=-1 returned. Assert hook_quality is NOT persisted (stays NULL). This is the critical invariant: transient failures must never write hook_quality=0.

## System-Wide Impact

- **Interaction graph**: `resilience.py` exports `parse_retry_after()` and color constants. `parse_retry_after()` is used in `_research_single_hook()` (Perplexity 429) and `enrich_with_hunter()` (Hunter 429). `_research_single_hook()` has its own inline retry loop (not using a shared helper -- the loop handles both network errors and 429s with different sleep strategies). `consecutive_fails` counters sit in the enrichment loops of `enrich_leads`, `enrich_with_hunter`, `enrich_hook`. `unhold_lead()` in `models.py` writes the `manual_approved` administrative flag (models.py owns admin/status writes per architecture reviewer).
- **Error propagation**: `_research_single_hook` retries transient errors internally, returns tier=-1 on exhaustion (same no-persist contract). `consecutive_fails` counters cause early loop `break` (not exception). Subsequent steps still run in `--step all` mode.
- **State lifecycle risks**: `manual_approved` is write-once (set to 1). No partial-failure risk. COALESCE handles NULL existing rows.
- **API surface parity**: CLI only for v1. Flask UI unchanged. No new API endpoints.

## Acceptance Tests

### Happy Path
- WHEN `enrich --step hook` runs and Perplexity returns 429 THE SYSTEM SHALL retry with backoff and process the lead on the second attempt
- WHEN `enrich --step hunter` runs and Hunter.io is down THE SYSTEM SHALL trip the circuit breaker after 3 failed leads and skip remaining leads
- WHEN `enrich --step hunter` completes THE SYSTEM SHALL print a colored credit summary showing credits used and remaining
- WHEN a user runs `leads unhold 42` THE SYSTEM SHALL set manual_approved=1 and print the lead name and prior hold reason
- WHEN a user runs `campaign assign 1` after unholding lead 42 THE SYSTEM SHALL include lead 42 in the campaign

### Error Cases
- WHEN `leads unhold 999` is called with a non-existent ID THE SYSTEM SHALL print "Lead 999 not found" and exit with code 1
- WHEN all 3 retry attempts fail for a lead in hook research THE SYSTEM SHALL return tier=-1 and increment consecutive_fails by 1 and NOT persist hook_quality
- WHEN Perplexity returns 429 three times THE SYSTEM SHALL return tier=-1 (not tier=0) and the lead SHALL remain eligible for retry on the next batch
- WHEN consecutive_fails reaches 3 THE SYSTEM SHALL print a red warning with the number of skipped leads and continue to the next enrichment step
- WHEN enrichment output is piped to a log file THE SYSTEM SHALL omit ANSI color codes from warnings and summaries

### Verification Commands
- `python -m pytest tests/test_resilience.py -v` -- all retry/breaker tests pass
- `python -m pytest tests/test_unhold.py -v` -- all unhold tests pass
- `python -m pytest tests/ -v` -- all 142+ tests pass (no regressions)
- `python run.py leads unhold 1 && python run.py leads held` -- lead 1 no longer shown
- `python run.py enrich --step hunter 2>&1 | tail -5` -- credit summary visible at end

## Implementation Order

1. **`resilience.py` + `tests/test_resilience.py`** (new module + tests, no existing code touched) -- commit
2. **Add retry to `_research_single_hook` + `consecutive_fails` counters + Perplexity timeout split** in `enrich.py` + add 429 test to `tests/test_hook.py` -- commit. **VERIFY FIRST**: run full test suite after this commit.
3. **Hunter.io colored alerts + end-of-run summary** in `enrich.py` -- commit
4. **`manual_approved` migration + `query_held_leads` update + `unhold_lead` function + `assign_leads` template guard** in `db.py`, `models.py`, `campaign.py` -- commit
5. **`leads unhold` CLI command + `tests/test_unhold.py`** in `run.py` + tests -- commit

5 commits, ~130 lines total. Step 1 is zero-risk (new code only). Step 2 carries the highest regression risk (modifying enrichment pipeline).

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Adding retry to `_research_single_hook` changes 429 behavior | Medium | Currently: 429 -> skip immediately (tier=-1). New: retry up to 3 times, then tier=-1 on exhaustion. Two dedicated tests verify no-persist invariant. |
| Circuit breaker counter trips on normal "no data" results | Low | Per-function failure signals: `except` for enrich_leads, `resp is None` for hunter, `tier == -1` for hook. "No data" is not a failure in any case. |
| NULL vs 0 for manual_approved on existing rows | Low | COALESCE(manual_approved, 0) in all queries. Tested explicitly. |
| ANSI codes in cron log files | Low | `_IS_TTY` cached at module level, constants skip codes when False. |
| Malicious/broken retry-after header causes hang | Low | `parse_retry_after()` caps at 120s, handles non-integer gracefully. |
| Unhold lead with unsupported segment crashes campaign | Low | Template guard in `assign_leads` WHERE clause. Tested explicitly. |
| Perplexity outage takes 10min to detect | Medium (before fix) | Split timeout to `(5, 60)` connect/read. Trip time drops to ~87s. |

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-05-06-reliability-hardening-brainstorm.md](docs/brainstorms/2026-05-06-reliability-hardening-brainstorm.md) -- Key decisions: unified decorator over minimal patch, 3-failure circuit breaker, force unhold with boolean flag, retry at network layer / breaker at batch layer.

### Solution Docs Applied
- Adaptive batch backoff (research-agent): only sleep after 429, not unconditionally
- Database migration runner (sandbox): never use `executescript()`, hold lock for batch
- Webhook delivery (sandbox): circuit breaker status machine, `attempt_count + 1 < max_attempts` boundary
- Lead-scraper enrichment expansion (sandbox): module ownership, COALESCE persist, idempotent migration
- Rate-limiting race condition (gig-lead-responder): guard inside function, always cleanup in finally

### Memory
- `feedback_lead-scraper-db-safety.md`: NEVER run concurrent processes on leads.db. `retry_request()` wraps HTTP only.

### Key Files
- `enrich.py` -- `_research_single_hook` retry (lines 1034-1087), Hunter 429 (line 568), enrichment loops (lines 197, 533, 1116)
- `run.py` -- CLI additions (line 361 for leads subparser)
- `db.py` -- migration column addition (line 37 new_columns list)
- `models.py` -- query_held_leads update (lines 38-93), new unhold_lead function
- `campaign.py` -- assign_leads WHERE clause update (line 106)

### Research Insights Applied

**From retry best practices researcher:**
- Full jitter (`random.uniform(0, delay)`) is the AWS-recommended default. Prevents thundering herd.
- `retry_after` from 429 responses should be used directly (no jitter on top -- the server told you the exact wait).
- Test pattern: mock `time.sleep` where imported, use `side_effect` lists for failure sequences.

**From security sentinel:**
- Cap `retry-after` at 120s. A misconfigured server could send `Retry-After: 999999` (11-day hang).
- Handle non-integer `Retry-After` values (HTTP-date format per RFC 9110 would crash `int()`).
- `assign_leads` must keep segment filter even for `manual_approved` leads (template FileNotFoundError).

**From performance oracle:**
- Perplexity 60s timeout is the critical gap -- circuit breaker takes ~10min to trip. Split to `(5, 60)`.
- Second Hunter.io quota check is worth it (200-500ms for credit delta visibility). Skip if breaker tripped.
- COALESCE on 4 UNION queries has zero performance impact at 1000 rows.

**From architecture strategist:**
- Two-layer design (retry at network, breaker at loop) is architecturally sound.
- `unhold_lead()` in `models.py` is acceptable -- administrative flag, not enrichment data. Add docstring clarifying ownership.
- Missing 429 test case in `test_hook.py` -- the behavioral change is significant.

**From code simplicity reviewer:**
- Don't refactor `_fetch_page` and `_hunter_get` -- they work, touching them risks regression for zero user benefit.
- CircuitBreaker class is just a counter -- inline it.
- Color helpers can be constants, not functions.
- 4-5 commits, not 10.

**From learnings researcher:**
- Transient failures must skip persist (don't write hook_quality=0 on a 429). Current sentinel pattern is correct.
- COALESCE persist pattern prevents data loss and makes retries safe.

## Feed-Forward

- **Hardest decision:** Whether to simplify the approach (inline counter + helper function) vs the original brainstorm decision (decorator + class). Went with simplicity -- the actual bug is one function missing retry, not an architecture gap.
- **Rejected alternatives:** (1) Full decorator + CircuitBreaker class in resilience.py -- over-engineering for 3 call sites where 2 work. (2) Refactoring `_fetch_page` and `_hunter_get` -- risks regression for zero user benefit. (3) `manual_approved` bypassing segment filter in `assign_leads` -- would crash `generate_messages()`.
- **Least confident:** The `_research_single_hook` retry loop coordinates with two existing timing mechanisms: the `parse_retry_after()` sleep on 429 and the existing `time.sleep(1.2)` rate-limit sleep in the `enrich_hook()` outer loop (line 1139). The 1.2s sleep runs AFTER each lead regardless of retry attempts, so retries add latency on top. With 3 retry attempts each sleeping up to 120s on 429, one lead could take ~6min in the worst case. This is acceptable because it means the API is actively rate-limiting us and we should wait. The two 429 tests (success after retry + exhaustion proving no persist) are the critical verification.
