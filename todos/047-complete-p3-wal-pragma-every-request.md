---
status: pending
priority: p3
issue_id: "047"
tags: [code-review, performance, brewops]
---

# WAL Pragma Runs on Every Request

## Problem Statement
`PRAGMA journal_mode=WAL` is set on every new connection in `get_db()`, but WAL mode is persistent -- once set, it stays set for the database file. `init_db()` already sets it. Running it per-connection is unnecessary overhead.

## Findings
- Performance reviewer: OPT-4

## Proposed Solution
Remove `g.db.execute('PRAGMA journal_mode=WAL')` from `get_db()`. Keep `foreign_keys=ON` and `busy_timeout=5000` (these are per-connection).

## Affected Files
- `app/db.py` line 12

## Acceptance Criteria
- [ ] WAL pragma only set during init_db(), not per-request
