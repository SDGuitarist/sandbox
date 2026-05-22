---
title: "GymFlow Run 054 -- Cross-Flow Data Integrity Review"
date: 2026-05-21
reviewer: flow-trace-reviewer
---

# GymFlow Run 054 -- Cross-Flow Data Integrity Review

Scope: 6 critical data flows traced end-to-end across model and route agent boundaries.
Method: Each value is followed from creation through storage to consumption, with all code paths checked including error branches.

---

### Flow 1: Attendance Capacity Check (BEGIN IMMEDIATE)

`attendance/check_in.html` form -> `POST /attendance/check-in` (`gymflow/app/blueprints/attendance/routes.py`) -> `check_in_class()` (`gymflow/app/models/attendance.py`) -> SQLite BEGIN IMMEDIATE transaction

**Data traced:** `class_schedule_id` (int from form) used to fetch capacity from `class_schedules`, count current `attendance` rows, INSERT if room, ROLLBACK if full.

**Code paths checked:**
- Happy path: schedule exists, not full -> INSERT -> COMMIT -> return attendance_id
- Full path: schedule exists, full -> ROLLBACK -> raise ValueError -> route catches -> flash error
- Non-existent schedule: schedule_row is None -> TypeError on schedule_row[0] -> no ROLLBACK -> transaction open -> 500 propagates

**Result: FAIL**

**Bug:** In `check_in_class` (attendance.py), after `conn.execute('BEGIN IMMEDIATE')` on line 12, the function queries `class_schedules WHERE id = ?` (lines 22-25). If the schedule does not exist, `fetchone()` returns None. Line 26 executes `capacity = schedule_row[0]`, raising `TypeError`. No ROLLBACK is issued. The open BEGIN IMMEDIATE transaction is never closed within the function.

The route (attendance/routes.py lines 78-83) catches only `ValueError`. The TypeError propagates as an unhandled exception while the connection holds an open write lock.

**File:** `gymflow/app/models/attendance.py` line 26
**Impact:** Unhandled 500. Request-scoped `g.db` connection holds open BEGIN IMMEDIATE write lock for request lifetime.
**Fix:** Add schedule_row None check + wrap in try/except/ROLLBACK.

---

### Flow 2: Payment Creation -> Invoice Paid Amount

`POST /payments/` -> `create_payment()` -> INSERT into `payments` -> `GET /billing/<id>` -> `get_invoice_paid_amount()` -> SELECT SUM from `payments`

**Data traced:** `invoice_id` and `amount_cents` created in payments route, stored in `payments`, consumed by `get_invoice_paid_amount()`.

**Result: PASS**

`create_payment` inserts with `(invoice_id, amount_cents, ...)` and calls `conn.commit()`. Route validates `invoice_id` against DB before insert. `get_invoice_paid_amount` queries `COALESCE(SUM(amount_cents), 0)` on same table and FK. Types consistent (int cents throughout).

---

### Flow 3: Member Delete Cascade

`POST /members/<id>/delete` -> `delete_member()` -> DELETE from `members` -> FK enforcement

**Data traced:** `member_id` used to DELETE, blocked by RESTRICT FKs.

**Result: PASS**

Schema uses `ON DELETE RESTRICT` for `attendance.member_id`, `invoices.member_id`, and `fitness_assessments.member_id`. Route catches `sqlite3.IntegrityError` and flashes correct error. Docstring matches schema.

**Note:** The learnings review (docs/reports/054/learnings-review.md) claims these FKs use "ON DELETE CASCADE." The actual schema uses RESTRICT. The "MASSIVE VIOLATION" finding is a false positive.

---

### Flow 4: Dashboard Aggregation (6 Cross-Agent Functions)

`GET /` -> 6 model functions from 4 model files

**Data traced:** Return values passed as template variables.

**Result: PASS**

All 6 functions exported from barrel, return correct types (int for counts/revenue, list[Row] for collections). Template variable names match function call sites.

---

### Flow 5: Schedule/Attendance Count Consistency

`get_schedule_attendance_count()` (schedule.py) vs count query in `check_in_class()` (attendance.py).

**Result: PASS**

Both queries are identical: `SELECT COUNT(*) FROM attendance WHERE class_schedule_id = ?`. Consistent counting.

---

### Flow 6: Invoice Writes Missing Explicit conn.commit()

`POST /billing/` -> `create_invoice()`, `POST /billing/<id>/edit` -> `update_invoice()`, `POST /billing/<id>/delete` -> `delete_invoice()`

**Data traced:** All three write operations in invoice.py.

**Result: FAIL (P2 -- latent, not a current runtime failure)**

`create_invoice`, `update_invoice`, and `delete_invoice` all execute SQL writes without calling `conn.commit()`. Docstrings acknowledge this: "Commits: yes (autocommit via isolation_level=None)." Every other model calls `conn.commit()` explicitly. Works under autocommit but data loss risk if isolation_level changes.

**File:** `gymflow/app/models/invoice.py` lines 14-19, 85-92, 100-103
**Fix:** Add `conn.commit()` after each write, matching all other model files.

---

## Summary

| # | Flow | Files | Result | Severity |
|---|------|-------|--------|----------|
| 1 | Attendance capacity / BEGIN IMMEDIATE | attendance/routes.py -> models/attendance.py | FAIL | P1 |
| 2 | Payment creation -> invoice paid amount | payments/routes.py -> models/payment.py -> billing/routes.py | PASS | -- |
| 3 | Member delete cascade | members/routes.py -> models/member.py -> schema.sql | PASS | -- |
| 4 | Dashboard aggregation (6 functions) | dashboard/routes.py -> models/__init__.py -> 4 model files | PASS | -- |
| 5 | Schedule/attendance count consistency | schedules/routes.py -> models/schedule.py vs models/attendance.py | PASS | -- |
| 6 | Invoice writes missing conn.commit() | billing/routes.py -> models/invoice.py | FAIL | P2 |

STATUS: FAIL -- 6 flows traced, 2 issues found (1 P1, 1 P2)

### P1 Issues

**P1-001: Missing ROLLBACK on non-existent schedule in check_in_class**
- File: `gymflow/app/models/attendance.py` line 26
- Runtime impact: Unhandled 500, connection holds open write lock
- **Status: FIXED** in commit d410fbc (try/except/ROLLBACK wrapper + schedule_row None check)

### P2 Issues

**P2-001: Invoice model omits conn.commit() on all 3 write functions**
- File: `gymflow/app/models/invoice.py` lines 14-19, 85-92, 100-103
- Runtime impact: None currently; data loss if isolation_level changes
- Status: Deferred (consistent with python-review P2-1: inconsistent commit strategy)
