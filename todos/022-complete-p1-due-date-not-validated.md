---
status: pending
priority: p1
issue_id: "022"
tags: [code-review, security, input-validation, project-tracker]
dependencies: []
unblocks: []
sub_priority: 1
---

# Due Date Not Validated Server-Side

## Problem Statement

Task create and edit routes accept any string as `due_date` with no server-side validation. The HTML `type="date"` input provides browser-side protection, but a non-browser client (curl, API tools) can submit arbitrary strings like "banana" or "9999-99-99". SQLite stores the garbage string since it has no native date type, causing `get_overdue_tasks()` comparisons with `date('now')` to silently produce wrong results.

## Findings

- `routes/tasks.py:42` (create): `due_date = request.form.get('due_date', '').strip() or None`
- `routes/tasks.py:97` (edit): same pattern, no validation
- The plan's Input Validation Rules section specified `datetime.strptime` validation, but it was not implemented

**Agents:** kieran-python-reviewer (P1), security-sentinel (P2)

## Proposed Solutions

### Option A: Add strptime validation (Recommended)
```python
from datetime import datetime
due_date = request.form.get('due_date', '').strip() or None
if due_date:
    try:
        datetime.strptime(due_date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(request.url)
```
- Pros: Simple, matches plan spec exactly
- Cons: None
- Effort: Small
- Risk: None

## Acceptance Criteria

- [ ] Invalid date strings rejected with flash message
- [ ] Valid YYYY-MM-DD dates accepted
- [ ] Empty/None dates still accepted (optional field)
- [ ] Applied to both create and edit routes
