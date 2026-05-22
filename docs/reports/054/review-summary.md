# Review Summary -- GymFlow (Run 054)

**Date:** 2026-05-21
**Reviewers:** security-sentinel, kieran-python-reviewer, learnings-researcher, flow-trace-reviewer
**Feed-Forward risk:** "Attendance capacity check with BEGIN IMMEDIATE"

## P1 Findings (Must Fix)

| # | Finding | Source | File(s) | Fix |
|---|---------|--------|---------|-----|
| P1-1 | `check_in_class` missing try/except/ROLLBACK on exception paths | security, python | `app/models/attendance.py:12-44` | Wrap in try/except with ROLLBACK, add schedule_row None check |
| P1-2 | `membership_type.py` redundant `conn.row_factory = sqlite3.Row` | python | `app/models/membership_type.py:38,47,55` | Remove 3 lines |
| P1-3 | `membership_type.py` uses Python `datetime.now()` instead of SQL `datetime('now')` | python | `app/models/membership_type.py:22,77` | Use SQL datetime('now') in INSERT/UPDATE |

## P2 Findings (Deferred)

| # | Finding | Source | Rationale for deferral |
|---|---------|--------|----------------------|
| P2-1 | No duplicate check-in guard (missing UNIQUE constraint) | security | Security hardening, not code bug |
| P2-2 | No login brute-force protection | security | Security hardening feature |
| P2-3 | Inconsistent commit strategy (conn.commit() vs autocommit) | python | Works correctly, cosmetic inconsistency |
| P2-4 | Missing type hints on route functions | python | Style, not functionality |
| P2-5 | Money parsing duplicated across 5 route files | python | Works correctly, DRY improvement |
| P2-6 | No security headers | security | Deployment-level concern |
| P2-7 | No session expiration | security | Deployment-level concern |
| P2-8 | Dead `field_label` parameter in schedules/routes.py | python | Cosmetic |
| P2-9 | Maintenance routes loads full equipment table for ID check | python | Performance, not correctness |
| P2-10 | Spec-consistency-check 12 FAILs are FALSE POSITIVES | learnings | Checker misread RESTRICT as CASCADE |

## Feed-Forward Verdict

The Feed-Forward risk was **confirmed**:
- TOCTOU: NOT vulnerable (BEGIN IMMEDIATE correctly serializes)
- ROLLBACK on exception: INCOMPLETE (P1-1 above)
- Transaction pattern divergence: attendance_models agent did NOT follow copy_week_schedules pattern from schedule_models agent

## False Positive Analysis

The spec-consistency-check (pre-swarm, 12 FAILs) incorrectly claimed FK constraints
used CASCADE where the actual schema and plan both specify RESTRICT. Verified by
grepping both `schema.sql` and the plan for `ON DELETE` -- all match. The learnings
review propagated this error as a "P0". Actual schema is correct.
