---
status: pending
priority: p2
issue_id: "024"
tags: [code-review, input-validation, project-tracker]
dependencies: []
unblocks: []
sub_priority: 1
---

# Category ID Not Validated Against Database

## Problem Statement

Task create/edit routes parse `category_id` as int but never check the category exists. An invalid ID causes `sqlite3.IntegrityError` (FK violation) resulting in an unhandled 500 error instead of a flash message.

## Findings

- `routes/tasks.py:44-48` (create) and `:99-103` (edit)
- FK constraint ON with PRAGMA foreign_keys=ON catches it at DB level, but no exception handling

**Agent:** kieran-python-reviewer (P1), security-sentinel

## Proposed Solutions

### Option A: Verify category exists before insert
```python
from models.categories import get_category
if get_category(db, category_id) is None:
    flash('Invalid category', 'error')
    return redirect(request.url)
```
- Effort: Small
- Risk: None

## Acceptance Criteria

- [ ] Invalid category_id shows flash error, not 500
- [ ] Applied to both create and edit routes
