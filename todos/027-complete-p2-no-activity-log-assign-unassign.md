---
status: pending
priority: p2
issue_id: "027"
tags: [code-review, architecture, project-tracker]
dependencies: []
unblocks: []
sub_priority: 4
---

# No Activity Log for Assign/Unassign Operations

## Problem Statement

Every create/update/delete in the app calls `log_activity()`, but assign and unassign member operations do not. The audit trail has a gap.

## Findings

- `routes/tasks.py:125-138` (assign) and `:141-154` (unassign) -- commit without logging
- All other write operations in all 3 route files call log_activity

**Agent:** architecture-strategist (P2)

## Proposed Solutions

### Option A: Add log_activity calls
```python
# In assign route after assign_member():
log_activity(db, 'task', task_id, 'updated', f"Assigned member to task")

# In unassign route after unassign_member():
log_activity(db, 'task', task_id, 'updated', f"Removed member from task")
```
- Effort: Small
- Risk: None

## Acceptance Criteria

- [ ] Assign and unassign operations appear in activity log
- [ ] Follows existing log_activity pattern (db passed from caller, single commit)
