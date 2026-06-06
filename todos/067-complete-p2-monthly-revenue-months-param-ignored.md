---
status: pending
priority: p2
issue_id: "067"
tags: [code-review, gig-outcome-tracker, run-068, api-contract]
dependencies: []
---

# monthly_revenue months parameter silently ignored

## Problem Statement

`monthly_revenue(conn, months=6)` in `app/gig_models.py` accepts a `months`
parameter but the SQL query hardcodes `'-6 months'` rather than using the
argument. Any caller passing a value other than the default 6 receives
silently wrong results. The API contract is a lie.

## Findings

- **File:** `app/gig_models.py`, line 186
- **Evidence:** `AND g.date >= date('now', '-6 months')` — literal string, not parameterized
- **Impact:** Low today (dashboard always passes `months=6`), but the function signature
  is misleading and future callers will be silently burned.
- **Spec prescription:** Section 12 calls for a `months` parameter, implying it should be used.

## Proposed Solutions

### Option A: Parameterize the interval (Recommended)
Use Python string formatting to insert the months value into the SQLite `date()` call:
```python
AND g.date >= date('now', ? || ' months')
```
Bind `f'-{months} months'` or `f'-{months}'` (SQLite accepts both forms with `date()`).

**Pros:** Correct. One-line fix.
**Cons:** Slight increase in query construction.
**Effort:** Small
**Risk:** Low

### Option B: Fix the hardcode to match the spec default exactly, document the limitation
Keep `'-6 months'` but rename/document that the parameter is ignored.

**Pros:** No change in behavior.
**Cons:** Confusing API, still violates contract.
**Effort:** Tiny
**Risk:** Low but doesn't actually fix the problem.

## Recommended Action

Apply Option A.

## Technical Details

- **File:** `app/gig_models.py`
- **Function:** `monthly_revenue`
- **Discovered by:** Review Agent (run 068 tail)

## Acceptance Criteria

- [ ] `monthly_revenue(conn, months=3)` only returns gigs from the last 3 months
- [ ] `monthly_revenue(conn, months=6)` behavior unchanged from current

## Work Log

- 2026-06-06: Identified during run 068 tail review. P2 finding.
