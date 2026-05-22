# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-05-21-gym-manager-plan.md
**Checked:** 2026-05-21

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Export vs Wiring | Export Names: `get_invoices_by_member` consumed by `billing_routes` | Wiring Table: `billing/routes.py` import list omits `get_invoices_by_member` | FAIL | Function declared as used by billing_routes in Export Names Table (line 1309) but not present in Cross-Boundary Wiring import for `app/blueprints/billing/routes.py` (line 1369) |
| 2 | Export vs Wiring | Export Names: `get_attendance_by_member` consumed by `attendance_routes` | Wiring Table: `attendance/routes.py` import list omits `get_attendance_by_member` | FAIL | Function declared as used by attendance_routes in Export Names Table (line 1290) but not present in Cross-Boundary Wiring import for `app/blueprints/attendance/routes.py` (line 1366) |
| 3 | Export vs Wiring | Export Names: `get_attendance` consumed by `attendance_routes` | Wiring Table: `attendance/routes.py` import list omits `get_attendance` | FAIL | Function declared as used by attendance_routes in Export Names Table (line 1288) but not present in Cross-Boundary Wiring import for `app/blueprints/attendance/routes.py` (line 1366) |
| 4 | ON DELETE vs IntegrityError | Schema: `attendance.member_id ON DELETE CASCADE` | `delete_member` docstring: "Raises sqlite3.IntegrityError if member has attendance/…/assessments" | FAIL | CASCADE means deleting a member auto-deletes attendance rows -- no IntegrityError fires. Docstring incorrectly claims IntegrityError for attendance (and assessments, which also CASCADE). Only `invoices.member_id ON DELETE RESTRICT` correctly triggers IntegrityError. |
| 5 | ON DELETE vs IntegrityError | Schema: `class_schedules.trainer_id ON DELETE SET NULL` and `fitness_assessments.trainer_id ON DELETE SET NULL` | `delete_trainer` docstring: "Raises sqlite3.IntegrityError if trainer has schedules/assessments" | FAIL | Both FK constraints are SET NULL. Deleting a trainer NULLs the trainer_id fields -- no IntegrityError fires. The docstring is entirely wrong for this function. |
| 6 | ON DELETE vs IntegrityError | Schema: `members.membership_type_id ON DELETE SET NULL` | `delete_membership_type` docstring: "Raises sqlite3.IntegrityError if members reference this type" | FAIL | FK is SET NULL. Deleting a membership type NULLs membership_type_id on referencing members -- no IntegrityError fires. |
| 7 | ON DELETE vs IntegrityError | Schema: `attendance.class_schedule_id ON DELETE CASCADE` | `delete_schedule` docstring: "Raises sqlite3.IntegrityError if attendance records exist" | FAIL | CASCADE means deleting a schedule auto-deletes its attendance records -- no IntegrityError fires. |
| 8 | ON DELETE vs IntegrityError | Schema: `maintenance_log.equipment_id ON DELETE CASCADE` | `delete_equipment` docstring: "Raises sqlite3.IntegrityError if maintenance records exist" | FAIL | CASCADE means deleting equipment auto-deletes maintenance_log rows -- no IntegrityError fires. |
| 9 | ON DELETE vs IntegrityError | Schema: `payments.invoice_id ON DELETE CASCADE` | `delete_invoice` docstring: "Raises sqlite3.IntegrityError if payments exist for this invoice" | FAIL | CASCADE means deleting an invoice auto-deletes its payments -- no IntegrityError fires. |
| 10 | Acceptance Test vs Schema | Acceptance Test: "WHEN admin tries to delete a member with attendance records THE SYSTEM SHALL flash 'Cannot delete' error" | Schema: `attendance.member_id ON DELETE CASCADE` | FAIL | CASCADE deletes attendance silently; the delete succeeds. Acceptance test contradicts schema behavior. (Same root cause as check #4.) |
| 11 | Acceptance Test vs Schema | Acceptance Test: "WHEN admin tries to delete equipment with maintenance records THE SYSTEM SHALL flash 'Cannot delete' error" | Schema: `maintenance_log.equipment_id ON DELETE CASCADE` | FAIL | CASCADE deletes maintenance records silently; delete succeeds. (Same root cause as check #8.) |
| 12 | Acceptance Test vs Schema | Acceptance Test: "WHEN admin tries to delete an invoice with payments THE SYSTEM SHALL flash 'Cannot delete' error" | Schema: `payments.invoice_id ON DELETE CASCADE` | FAIL | CASCADE deletes payments silently; delete succeeds. (Same root cause as check #9.) |
| 13 | ON DELETE vs IntegrityError | Schema: `class_schedules.class_type_id ON DELETE RESTRICT` | `delete_class_type` docstring: "Raises sqlite3.IntegrityError if schedules reference this type" | PASS | RESTRICT correctly produces IntegrityError. Docstring matches schema. |
| 14 | ON DELETE vs IntegrityError | Schema: `invoices.member_id ON DELETE RESTRICT` | `delete_member` docstring (partial): "Raises… if member has… invoices" | PASS | RESTRICT correctly produces IntegrityError for invoices. This portion of the delete_member docstring is correct. |
| 15 | Export vs Import | `models/__init__.py` barrel file re-exports `get_invoices_by_member` | barrel file (lines 929-932) | PASS | Function is present in barrel re-exports. |
| 16 | Export vs Import | `models/__init__.py` barrel re-exports all attendance functions including `get_attendance` and `get_attendance_by_member` | barrel file (lines 915-919) | PASS | Both functions are in the barrel. The gap is only in the Wiring Table (checks #2, #3). |
| 17 | Route Table vs Auth Matrix | Route Table: `POST /logout` listed | Authorization Matrix: `POST /logout` listed as `login-required` | PASS | Both agree on logout requiring login. |
| 18 | Route Table vs Auth Matrix | Route Table: `GET /health` listed | Authorization Matrix: `GET /health` listed as public | PASS | Consistent. |
| 19 | Transaction Contract vs Docstring | Transaction Contracts: `check_in_class` -> "requires BEGIN IMMEDIATE (atomic capacity check)" | `check_in_class` docstring: "Commits: yes (via BEGIN IMMEDIATE ... COMMIT)" | PASS | Both sections agree the function manages its own BEGIN IMMEDIATE transaction and commits. Wording differs but semantics match. |
| 20 | SQL Type vs App-Layer Type | SQL: `price_cents INTEGER`, `purchase_price_cents INTEGER`, `amount_cents INTEGER`, `cost_cents INTEGER` | Model function signatures: `price_cents: int`, `purchase_price_cents: int`, `amount_cents: int`, `cost_cents: int` | PASS | All money fields are INTEGER in SQL and `int` in Python signatures. |
| 21 | SQL Type vs App-Layer Type | SQL: `weight_kg REAL`, `height_cm REAL`, `body_fat_pct REAL`, `bmi REAL` | Model function: `weight_kg: float \| None`, `height_cm: float \| None`, `body_fat_pct: float \| None` | PASS | REAL in SQLite maps to float in Python. Consistent. |
| 22 | Route Table vs Input Validation | All `POST /*/create` routes | Input Validation Prescriptions section | PASS | All create POST routes have at least one explicit validation rule. |
| 23 | Input Validation vs Route Table | `POST /membership-types/<id>/edit`, `POST /class-types/<id>/edit`, `POST /schedules/<id>/edit`, `POST /equipment/<id>/edit`, `POST /maintenance/<id>/edit`, `POST /assessments/<id>/edit` | Input Validation Prescriptions: no rows for these 6 edit routes | WARN | Six edit routes in Route Table have no Input Validation Prescriptions rows. The spec operating contract requires coverage of every POST route. Edit routes presumably follow same rules as corresponding create routes, but this is not stated. |
| 24 | Export Names vs Wiring | Export Names: `search_members` consumed by `member_routes` | Wiring Table: `members/routes.py` import includes `search_members` | PASS | Search function is present in the wiring import (line 1361). |
| 25 | Route Table vs Model | `search_members` wired to `member_routes` | No `GET /members/search` or similar route in Route Table | WARN | Function is imported but no dedicated search route is defined. May be used as query-param filter on `GET /members/`. Not a contradiction, but the route is absent. Same applies to `get_members_by_status`, `get_schedules_by_date_range`, `get_schedules_by_trainer`. |
| 26 | Template Render Context vs Model Return Type | `dashboard/index.html`: `active_members=count_active_members(conn)` | `count_active_members` docstring: "Returns int" | PASS | Integer return used as integer template variable. Consistent. |
| 27 | Template Render Context vs Model Return Type | `members/detail.html`: `latest_assessment=get_latest_assessment(conn, member_id)` | `get_latest_assessment` docstring: "Returns Row or None" | PASS | Template context receives Row or None; template should guard with `if latest_assessment`. Consistent. |
| 28 | Template Render Context vs Model | `schedules/detail.html`: `attendees=get_attendance_by_schedule(conn, schedule_id)` | `get_attendance_by_schedule` defined in `models/attendance.py` | PASS | Function exists in model and is in schedule_routes wiring (line 1365). |
| 29 | Cross-Boundary Wiring vs Export Names | Export Names: `get_latest_assessment` consumed by `member_routes` | Wiring Table: `members/routes.py` import includes `get_latest_assessment` | PASS | Present in wiring (line 1361). |
| 30 | Authorization Matrix coverage | All routes in Route Table | Authorization Matrix: catch-all "ALL other routes: login-required" | PASS | Matrix explicitly covers all routes via catch-all rule. |

## Summary

- **Total checks:** 30
- **PASS:** 17
- **FAIL:** 12
- **WARN:** 2
- **N/A (section absent):** 1 -- Mock/Fixture Data vs Schema Fields (no mock data in spec)

---

## FAIL Details (Root Cause Analysis)

### Root Cause A: ON DELETE behavior (FAILs #4–#9, #10–#12)

Nine of the twelve FAILs share a single root cause: the model function docstrings and acceptance tests describe IntegrityError-raising behavior, but the SQL schema uses CASCADE or SET NULL for those FK constraints. The two are directly contradictory.

**Affected DELETE behaviors by ON DELETE type:**

| Function | FK Constraint | Actual Behavior | Docstring Claims |
|----------|--------------|-----------------|------------------|
| `delete_member` (attendance) | `attendance.member_id ON DELETE CASCADE` | Attendance rows deleted silently | IntegrityError |
| `delete_member` (assessments) | `fitness_assessments.member_id ON DELETE CASCADE` | Assessment rows deleted silently | IntegrityError |
| `delete_trainer` (schedules) | `class_schedules.trainer_id ON DELETE SET NULL` | trainer_id set to NULL | IntegrityError |
| `delete_trainer` (assessments) | `fitness_assessments.trainer_id ON DELETE SET NULL` | trainer_id set to NULL | IntegrityError |
| `delete_membership_type` | `members.membership_type_id ON DELETE SET NULL` | membership_type_id set to NULL | IntegrityError |
| `delete_schedule` | `attendance.class_schedule_id ON DELETE CASCADE` | Attendance rows deleted silently | IntegrityError |
| `delete_equipment` | `maintenance_log.equipment_id ON DELETE CASCADE` | Maintenance rows deleted silently | IntegrityError |
| `delete_invoice` | `payments.invoice_id ON DELETE CASCADE` | Payment rows deleted silently | IntegrityError |

**Fix options (spec author must choose one and apply consistently):**
- Option A: Change the FK constraints to RESTRICT for the cases where "cannot delete if referenced" is the desired UX behavior. This makes the docstrings and acceptance tests correct.
- Option B: Change the docstrings, acceptance tests, and Coordinated Behavior #8 to reflect that CASCADE/SET NULL FKs do NOT raise IntegrityError. The UX would be "silently deletes or nulls out children" rather than "blocked."

The Acceptance Test error cases for member/equipment/invoice deletes (FAILs #10–12) indicate Option A is the intended design -- the spec author wants the user to be blocked from deleting these records. If so, the FK constraints for those cases must be changed to RESTRICT.

### Root Cause B: Wiring Table omissions (FAILs #1–#3)

Three functions are declared in the Export Names Table as consumed by a route agent but are missing from that agent's Cross-Boundary Wiring import line:

| Function | Declared Consumer | Missing From Wiring Line |
|----------|------------------|--------------------------|
| `get_invoices_by_member` | `billing_routes` | `app/blueprints/billing/routes.py` import |
| `get_attendance_by_member` | `attendance_routes` | `app/blueprints/attendance/routes.py` import |
| `get_attendance` | `attendance_routes` | `app/blueprints/attendance/routes.py` import |

**Fix:** Add the three function names to their respective Wiring Table import strings.

---

STATUS: FAIL -- 12 contradictions found
