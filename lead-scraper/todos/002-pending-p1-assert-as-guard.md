---
status: resolved
priority: p1
issue_id: "002"
tags: [code-review, security]
---

# assert used for SQL injection guard in migrate_db

## Problem Statement
`db.py:52` uses `assert _SAFE_IDENTIFIER.match(col_name)` which is stripped with `python -O`.

## Proposed Solution
Replace with `if not ... : raise ValueError(...)`.

## Acceptance Criteria
- [ ] No `assert` used for runtime validation in production code
