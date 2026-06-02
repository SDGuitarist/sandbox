---
status: pending
priority: p2
issue_id: "058"
tags: [code-review, performance, callsheets, run-063]
dependencies: []
---

# 058 — callsheets.generate calls get_schedule_entries twice (redundant query)

## Problem Statement

`POST /call-sheets/<project_id>/generate` calls `get_schedule_entries` twice
for the same `(project_id, shoot_date)`:

1. Route handler (line 67): validates entries exist before proceeding
2. `generate_call_sheet` model (callsheet_models.py line 31): calls the same
   function internally as its first step

The route's pre-check result is discarded. `generate_call_sheet` re-runs the
identical query. This is an N+1 pattern within a single request — on a busy
production database with many schedule entries, this doubles the I/O for every
call sheet generation.

## Findings

- **File 1:** `app/blueprints/callsheets/routes.py` lines 66–70
- **File 2:** `app/models/callsheet_models.py` lines 31–33
- **Impact:** Double SQL hit per generate request. Negligible for tiny DBs;
  meaningful at scale (many schedule entries per date).
- **Design tension:** `generate_call_sheet` is self-contained (documented as
  returning None when no entries exist). The route's pre-check is defensive
  but redundant given `generate_call_sheet` already handles the empty case.

## Proposed Solutions

### Option A: Remove the pre-check from the route (Recommended)
The route already handles `call_sheet_id is None` on line 82, which covers the
empty-entries case. The pre-check at lines 66–70 is fully redundant.

```python
# Remove lines 65–70 entirely:
# from app.models.schedule_models import get_schedule_entries
# entries = get_schedule_entries(conn, project_id, shoot_date)
# if not entries:
#     flash('No scenes scheduled for that date', 'error')
#     return redirect(url_for('callsheets.list', project_id=project_id))
```
Effort: Small. Risk: Low.

### Option B: Pass entries into generate_call_sheet
Add an `entries` parameter to `generate_call_sheet` so the route can pass
pre-fetched entries. More invasive but eliminates the double query cleanly.
Effort: Medium. Risk: Low (internal API change only).

## Recommended Action

Option A — cleanest fix. The model already handles the None case.

## Technical Details

- **Affected file:** `app/blueprints/callsheets/routes.py` lines 65–70
- **Also remove:** the lazy `from app.models.schedule_models import get_schedule_entries` import at line 66 (only used for the redundant check)

## Acceptance Criteria

- [ ] `generate_call_sheet` is called directly without a pre-check query
- [ ] Route still handles `call_sheet_id is None` correctly (already does)
- [ ] Smoke test continues to pass

## Work Log

- 2026-06-02: Found by flow-trace-reviewer during Run 063 review
