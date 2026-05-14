---
status: resolved
priority: p1
issue_id: "001"
tags: [code-review, architecture, data-integrity]
---

# Transaction Safety: Premature Commits and Non-Atomic Operations

## Problem Statement
Four related transaction safety issues cause data integrity violations under concurrent load:

1. **`update_status()` commits prematurely** (`app/models.py:59`): Callers expect to do additional work after calling `update_status()` but the function commits internally, breaking transaction boundaries.
2. **`try_promote_next()` commits before checkout link** (`app/waitlist/routes.py:34`): If `create_checkout_link()` fails after the commit, the registrant is stranded -- removed from waitlist but has no payment path.
3. **Re-registration path lacks BEGIN IMMEDIATE** (`app/registration/routes.py:113-154`): Capacity check and status update are not atomic, allowing last-seat races.
4. **Stale capacity check in new registration** (`app/registration/routes.py:156`): `get_paid_count()` on line 156 can disagree with `register_attendee()`'s internal check, causing status override.

## Findings
- Architecture review: P1-02, P1-03, P1-04, P1-05
- Learnings review: try_promote_next non-transactional (from ethics-toolkit lesson)

## Proposed Solution

1. Remove `conn.commit()` from `update_status()` -- callers must commit explicitly
2. In `try_promote_next()`, defer commit until after checkout link creation; rollback on failure
3. Wrap re-registration path in `BEGIN IMMEDIATE` transaction
4. After `register_attendee()`, read the actual inserted status instead of using stale `paid_count`

## Acceptance Criteria
- [x] `update_status()` does not call `conn.commit()`
- [x] `try_promote_next()` rolls back if `create_checkout_link()` fails
- [x] Re-registration uses `BEGIN IMMEDIATE`
- [x] New registration reads status from DB after `register_attendee()`
