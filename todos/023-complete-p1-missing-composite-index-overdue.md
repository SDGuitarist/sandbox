---
status: pending
priority: p1
issue_id: "023"
tags: [code-review, performance, project-tracker]
dependencies: []
unblocks: []
sub_priority: 2
---

# Missing Composite Index for Overdue Tasks Query

## Problem Statement

The `get_overdue_tasks()` function filters on `due_date IS NOT NULL AND due_date < date('now') AND status != 'done'` but there is no index covering both `due_date` and `status`. SQLite does a full table scan on every dashboard page load.

## Findings

- `schema.sql:44-47` has indexes on `category_id`, `status`, `task_members.member_id`, `activity_log.created_at` but none on `due_date`
- `models/tasks.py:136-146` runs this query on every dashboard visit
- Performance oracle: at 10K tasks, dashboard load reaches ~100ms; at 100K, ~500ms+

**Agent:** performance-oracle (P1)

## Proposed Solutions

### Option A: Add composite index (Recommended)
Add to `schema.sql`:
```sql
CREATE INDEX IF NOT EXISTS idx_tasks_due_date_status ON tasks(due_date, status);
```
- Pros: 1-line fix, converts full scan to index seek
- Cons: Slightly larger DB file (negligible)
- Effort: Small
- Risk: None

## Acceptance Criteria

- [ ] Index exists in schema.sql
- [ ] Dashboard overdue section loads efficiently
