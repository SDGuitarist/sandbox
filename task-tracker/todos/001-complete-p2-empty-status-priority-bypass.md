---
status: pending
priority: p2
issue_id: "001"
tags: [code-review, security, validation]
dependencies: []
---

# Empty Status/Priority Bypass on Task Update

## Problem Statement

Task update validation checks `if status and status not in TASK_STATUSES` —
the `if status` guard means empty strings pass validation silently. An empty
status gets sent to `update_task()` which runs `UPDATE tasks SET status = ?`
with an empty string. The SQLite CHECK constraint catches this and returns a
500 error instead of a user-friendly validation message.

Empty priority has the same issue on both create and update routes.

## Findings

- `tasks/routes.py` lines 119-122: validation only triggers on non-empty values
- SQLite CHECK constraint is the only safety net, producing a 500 not a flash message
- Source: security-sentinel review

## Proposed Solutions

### Option A: Require non-empty status and priority (Recommended)
- Change `if status and ...` to always validate when field is expected
- For update: status is always expected (dropdown always sends a value)
- For create: priority defaults to 'medium' if empty (current behavior is correct)
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] Submitting empty status on task update shows flash error, not 500
- [ ] Submitting empty priority on task update shows flash error, not 500
- [ ] Valid status/priority values still accepted
