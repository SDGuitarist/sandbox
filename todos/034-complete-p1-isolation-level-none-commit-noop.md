---
status: pending
priority: p1
issue_id: "034"
tags: [code-review, data-integrity, transactions, brewops, known-pattern]
---

# isolation_level=None Makes conn.commit() a No-Op

## Problem Statement
`app/db.py` line 10 sets `isolation_level=None` (autocommit mode). Every individual SQL statement auto-commits immediately. The `conn.commit()` calls in route handlers for SERIAL-SAFE functions are no-ops -- they do nothing because the data already committed.

This is not a live bug today (each route does only one SERIAL-SAFE write), but it is a correctness trap. If a future route ever does two SERIAL-SAFE writes expecting atomicity, they won't be atomic.

**Known Pattern:** This matches the conn.commit() no-op issue found in CoWorkFlow Run 056 (docs/solutions/2026-05-22-coworkflow-deferred-fixes-batch.md).

## Findings
- Python reviewer: P0-1
- Performance reviewer: OPT-1
- Architecture reviewer: M1
- Data-integrity reviewer: H1
- Security reviewer: M5
- Learnings researcher: Known pattern from Run 056

## Proposed Solution
Change `isolation_level=None` to `isolation_level='DEFERRED'` (Python default) so `conn.commit()` calls have real effect. The BEGIN IMMEDIATE functions already manage their own transactions explicitly and will continue working correctly.

## Affected Files
- `app/db.py` line 10

## Acceptance Criteria
- [ ] `conn.commit()` in route handlers actually commits a transaction
- [ ] BEGIN IMMEDIATE functions still work correctly
- [ ] No double-commit issues
