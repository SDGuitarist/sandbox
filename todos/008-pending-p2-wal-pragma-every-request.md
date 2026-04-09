---
status: resolved
priority: p2
issue_id: "008"
tags: [code-review, performance, sqlite]
dependencies: []
unblocks: []
sub_priority: 4
---

# WAL Pragma Runs on Every Request

## Problem Statement

`PRAGMA journal_mode=WAL` is set on every database connection in `get_db()`.
WAL mode is a persistent database-level setting that only needs to be set
once. Running it per-request is wasted I/O.

## Findings

- **Performance Oracle (P2):** "Move it into init_db() where it runs once
  at startup. Keep PRAGMA foreign_keys=ON per-connection (that one resets)."

## Proposed Solutions

Move WAL pragma to `init_db()`, remove from `get_db()`.

- Effort: Small (2-line change)
- Risk: None

## Acceptance Criteria

- [ ] WAL pragma set in init_db() only
- [ ] foreign_keys pragma remains in get_db()
