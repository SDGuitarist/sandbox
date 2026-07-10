---
status: resolved
priority: p2
issue_id: "070"
tags: [code-review, performance, callsheets, run-070]
dependencies: []
---

# 070 — callsheets.generate double get_schedule_entries call (regressed from run-063)

## Problem Statement

`callsheets.generate` calls `get_schedule_entries(conn, project_id, shoot_date)` at the route
level as a guard check (line 70), then `generate_call_sheet` calls it again internally (line 32
of callsheet_models.py). This is the same double-query P2 found in Run 063 — the fix was applied
there but not carried into the converged spec, so it regressed in Run 070.

## Impact

Two identical SQL queries per generate request. Minor performance impact, no correctness issue.

## Proposed Fix

Option A (minimal): Accept the double query; the route-level guard provides better UX with an
explicit "No scenes scheduled" flash message. Defer as acceptable at indie scale.

Option B (optimal): Add an optional `entries` parameter to `generate_call_sheet` so the route can
pass its pre-fetched entries and skip the internal re-fetch:
```python
def generate_call_sheet(conn, project_id, shoot_date, entries=None):
    if entries is None:
        entries = get_schedule_entries(conn, project_id, shoot_date)
```

## Acceptance Criteria

- [ ] `get_schedule_entries` called exactly once per generate request
- [ ] UX flash message for empty day preserved
- [ ] Smoke tests pass

## Work Log

- 2026-06-02: Fixed in Run 063. Fix not carried into converged spec.
- 2026-06-08: Regressed in Run 070. Found during review (P2-2). Deferred.
