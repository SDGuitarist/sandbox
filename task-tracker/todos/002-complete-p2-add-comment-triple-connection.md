---
status: pending
priority: p2
issue_id: "002"
tags: [code-review, performance, simplicity]
dependencies: []
---

# add_comment Opens 3 DB Connections

## Problem Statement

The `add_comment` route handler opens the database 3 times: once to verify
task/project exist, once to re-fetch comments on validation failure, once for
the actual write. Each `with get_db()` call opens a new SQLite connection,
runs WAL/FK pragmas, and closes it. Should be one connection.

## Findings

- `tasks/routes.py` lines 155-180: three separate `with get_db()` blocks
- Source: code-simplicity-reviewer

## Proposed Solutions

### Option A: Single connection block (Recommended)
- Use one `with get_db(immediate=True) as db:` for the entire handler
- Read task/project, validate, fetch comments if needed, write if valid
- All in one connection
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] `add_comment` uses a single `with get_db()` block
- [ ] Validation failure still re-renders with comments
- [ ] Successful comment creation still works
