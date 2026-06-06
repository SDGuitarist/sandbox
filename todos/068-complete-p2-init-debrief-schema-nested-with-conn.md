---
status: pending
priority: p2
issue_id: "068"
tags: [code-review, gig-outcome-tracker, run-068, sqlite3, transaction]
dependencies: []
---

# init_debrief_schema uses nested with conn: inside init_db outer block

## Problem Statement

`init_debrief_schema` in `app/debrief_models.py` wraps its DDL in `with conn:`,
but it is called from inside `init_db()`'s outer `with conn:` block in
`app/__init__.py`. All four other `init_*_schema` functions call `conn.execute(DDL)`
directly (no nested `with conn:`), which is the correct pattern when the outer
block owns the transaction.

In sqlite3-Python, `with conn:` on a DDL statement inside an already-active
transaction attempts a nested savepoint / implicit re-commit. In CPython's
stdlib implementation this silently succeeds (the inner block commits if no
exception, matching the outer block's intent), but it is non-idiomatic,
creates a SAVEPOINT RELEASE on DDL, and could surface differently if the
connection isolation level is changed.

## Findings

- **File:** `app/debrief_models.py`, line 26
- **Inconsistency:** 4/5 init functions use bare `conn.execute()`; 1/5 adds `with conn:`
- **Risk:** Benign in current CPython stdlib sqlite3 with default isolation level;
  non-zero risk if isolation level is set to `None` (autocommit) elsewhere.

## Proposed Solutions

### Option A: Remove the extra with conn: (Recommended)
```python
def init_debrief_schema(conn) -> None:
    conn.execute(DEBRIEF_SCHEMA)
```
Matches all other init_*_schema functions exactly.

**Pros:** Consistent with all sibling init functions. Transaction owned by caller.
**Effort:** Trivial
**Risk:** None

### Option B: Leave as-is, document the inconsistency
The current behavior is functionally correct.

**Pros:** Zero code change.
**Cons:** Inconsistency will confuse future readers.
**Effort:** None
**Risk:** None today, non-zero in edge cases.

## Recommended Action

Apply Option A — one-line fix.

## Technical Details

- **File:** `app/debrief_models.py`
- **Function:** `init_debrief_schema`
- **Discovered by:** Review Agent (run 068 tail)

## Acceptance Criteria

- [ ] `init_debrief_schema` matches the pattern of other init_*_schema functions
- [ ] Smoke tests still pass after change

## Work Log

- 2026-06-06: Identified during run 068 tail review. P2 finding.
