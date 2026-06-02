---
status: pending
priority: p1
issue_id: "056"
tags: [code-review, security, callsheets, validation, run-063]
dependencies: []
---

# 056 — callsheets.generate missing shoot_date format validation

## Problem Statement

`POST /call-sheets/<project_id>/generate` accepts `shoot_date` from form data
with only a non-empty check. No YYYY-MM-DD format validation is performed before
the value is passed to `get_schedule_entries`, a raw SQL query
(`SELECT id FROM call_sheets WHERE project_id = ? AND shoot_date = ?`), and
ultimately to `generate_call_sheet`. A malformed date like `2026-99-99` or
`'; DROP TABLE call_sheets; --` passes through.

The `schedule.create` route (schedule/routes.py line 121) already has the correct
pattern:
```python
if not shoot_date or not re.match(r'^\d{4}-\d{2}-\d{2}$', shoot_date):
```
The callsheets route omits this check entirely.

## Findings

- **File:** `app/blueprints/callsheets/routes.py` line 59–61
- **Contrast:** `app/blueprints/schedule/routes.py` line 121 — same validation done correctly
- **Impact:** SQLite will store and query against invalid date strings silently.
  The UNIQUE(project_id, shoot_date) constraint won't catch malformed dates;
  a malformed date creates a call sheet with a corrupt shoot_date.
- **Known Pattern:** date input validation is required for every date-accepting
  route — flagged in personal-finance-tracker solution doc (Run 015 P1 fix).

## Proposed Solutions

### Option A: Add re.match guard (Recommended)
```python
import re
shoot_date = request.form.get('shoot_date', '').strip()
if not shoot_date or not re.match(r'^\d{4}-\d{2}-\d{2}$', shoot_date):
    flash('Valid date (YYYY-MM-DD) is required', 'error')
    return redirect(url_for('callsheets.list', project_id=project_id))
```
Effort: Small. Risk: None. Mirrors schedule.create exactly.

### Option B: Validate via datetime.fromisoformat
```python
from datetime import date
try:
    date.fromisoformat(shoot_date)
except ValueError:
    flash('Valid date (YYYY-MM-DD) is required', 'error')
    return redirect(url_for('callsheets.list', project_id=project_id))
```
Effort: Small. Stricter (rejects 2026-13-01). Acceptable alternative.

## Recommended Action

Option A — mirrors the existing pattern used in schedule/routes.py. Minimal diff.

## Technical Details

- **Affected file:** `app/blueprints/callsheets/routes.py` — `generate()` function
- **Fix location:** After line 61 (after the `if not shoot_date:` check)
- **re module:** Already available in schedule/routes.py but NOT imported in callsheets/routes.py — must add import

## Acceptance Criteria

- [ ] `POST /call-sheets/1/generate` with `shoot_date=not-a-date` returns 302 with flash error, not 500
- [ ] `POST /call-sheets/1/generate` with `shoot_date=2026-06-15` proceeds normally
- [ ] re.match pattern added to callsheets/routes.py generate() function

## Work Log

- 2026-06-02: Found by flow-trace-reviewer during Run 063 review (Feed-Forward risk surface)
