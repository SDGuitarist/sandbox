---
status: resolved
priority: p3
issue_id: "014"
tags: [code-review, performance, sqlite]
dependencies: []
unblocks: []
sub_priority: 4
---

# Missing Index on tasks.project_id

## Problem Statement

SQLite does not auto-create indexes on foreign key columns. Every query
filtering by project_id does a full table scan. Trivial 1-line fix.

## Findings

- **Performance Oracle (P3):** "Add CREATE INDEX IF NOT EXISTS
  idx_tasks_project_id ON tasks(project_id);"

## Acceptance Criteria

- [ ] Index added to schema.sql
