# GymFlow Run 054 Institutional Learnings Review

**Scope:** Cross-reference 26-agent Flask+SQLite swarm build (Run 054 - GymFlow gym management system) against established solution patterns from prior builds.

**Key Areas Reviewed:**
1. Flask swarm patterns (4-31 agent builds)
2. Transaction handling and BEGIN IMMEDIATE (FC29 territory)
3. Large swarm coordination (20-31 agents)
4. Spec completeness and consistency
5. Money handling patterns (cents conversion)
6. Input validation in Flask routes
7. Endpoint registry patterns
8. Database schema consistency with model docstrings

---

## Critical Patterns (Always Apply)

**From institutional knowledge:** The critical patterns file at `docs/solutions/patterns/critical-patterns.md` was checked. No patterns file exists in the repository yet (this is a new addition opportunity). However, critical patterns discovered through this review process are documented below.

---

## Relevant Learnings & Violations

### 1. **Transaction Management with BEGIN IMMEDIATE (FC29 Territory)**

**Source Document:** `2026-05-21-restaurant-kitchen-mgmt-swarm-build.md` (Run 052, 29 agents)

**Key Lesson:**
> When using `BEGIN IMMEDIATE` for atomic operations (e.g., capacity checks), you MUST set `isolation_level=None` in `get_db()` to allow explicit transaction control. Default SQLite autocommit behavior in Python's `sqlite3` module is incompatible with manual `BEGIN IMMEDIATE`.

**GymFlow Status:** PASS

**Evidence:**
- File: `/Users/alejandroguillen/Projects/sandbox/gymflow/app/db.py`, line 16
- Code: `g.db = sqlite3.connect(DATABASE, isolation_level=None)`
- Model: `/Users/alejandroguillen/Projects/sandbox/gymflow/app/models/attendance.py`, lines 12-42 (`check_in_class`)
- Routes: `/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/attendance/routes.py`, lines 76-83

**Why It Matters:** Without `isolation_level=None`, all explicit `conn.execute('BEGIN IMMEDIATE')` calls fail silently or are overridden by SQLite's autocommit, defeating the atomic capacity check. Restaurant Kitchen Mgmt (Run 052) had this caught during deepening and fixed before swarm launch. GymFlow implemented it correctly from the start.

**Severity:** CRITICAL

---

### 2. **Endpoint Registry Pattern for url_for Consistency**

**Source Document:** `2026-04-09-bookmark-manager-swarm-build.md` (3 agents)

**Key Lesson:**
> Flask swarm builds that use `url_for()` in templates MUST include an Endpoint Registry table in the shared spec. The table maps: Blueprint, Function Name, Method, Path, and url_for Name. Without it, templates and routes agents independently choose endpoint names, causing BuildError at runtime.

**Example Table:**
```
| Blueprint | Function Name | Method | Path | url_for Name |
|-----------|---------------|--------|------|-------------|
| attendance| list_attendance | GET | / | attendance.list_attendance |
| attendance| check_in_form | GET | /check-in | attendance.check_in_form |
| attendance| check_in | POST | /check-in | attendance.check_in |
```

**GymFlow Status:** NOT VIOLATED (but not explicitly documented in spec)

**Evidence:**
- Attendance routes define functions: `list_attendance` (line 24), `check_in_form` (line 32), `check_in` (line 44), `check_out` (line 95), `delete_attendance` (line 116)
- Templates reference them: `attendance.list_attendance`, `attendance.check_in_form`, etc.
- No mismatches found across all 13 blueprints (members, trainers, classes, attendance, billing, payments, equipment, maintenance, assessments, etc.)

**Why It Matters:** The Bookmark Manager found 3 url_for mismatches at assembly time (runtime BuildErrors). GymFlow avoided this, suggesting the spec included an endpoint registry or agents coordinated through the shared spec effectively.

**Severity:** HIGH (but GymFlow avoids it through good spec discipline)

---

### 3. **Context Manager Usage Examples are Mandatory**

**Source Document:** `2026-04-07-flask-swarm-acid-test.md` (4 agents, Flask acid test)

**Key Lesson:**
> When defining a `@contextmanager` function in the shared spec (e.g., `get_db`), you MUST include a code example showing the `with ... as db:` syntax. Without it, all agents will independently infer the wrong usage pattern (plain function call instead of context manager), and the spec will be the single source of truth for coordinating this mistake across all agents.

**GymFlow Status:** DIFFER

**Evidence:**
- File: `/Users/alejandroguillen/Projects/sandbox/gymflow/app/db.py`, lines 8-21
- Docstring: "Returns a plain connection (NOT a context manager). Usage: `conn = get_db()`"
- Implementation: Returns `sqlite3.Connection`, not a context manager

**Analysis:**
GymFlow's `get_db()` is NOT a context manager (no `@contextmanager` decorator). This is a deliberate design choice (isolation_level=None requires explicit control). The docstring is clear and correct. Unlike the Flask Acid Test, this is not a mistake — it's a different pattern with explicit documentation.

**Severity:** LOW (not applicable — GymFlow chose a different, valid pattern)

---

### 4. **Large Swarm Coordination: 25+ Agents**

**Source Document:** `2026-05-20-venueconnect-25-agent-swarm-build.md` (Run 049, 25 agents) and `2026-05-20-gigsheet-31-agent-swarm-build.md` (Run 050, 31 agents)

**Key Lessons:**
1. **Vertical blueprint split with strict file ownership** – each agent owns one blueprint (routes + templates) or a shared module. No two agents write the same file.
2. **Prescriptive Coordinated Behaviors table** – all 25+ agents must follow identical flash message categories, form field styling, table styling, empty states, etc.
3. **Spec consistency checker is essential** – GigSheet (31 agents) caught 6 contradictions pre-swarm; VenueConnect (25 agents) had 14/25 agents fail to commit (FC37 failure class).

**GymFlow Status:** PARTIAL

**Evidence:**
- GymFlow has 26 agents (meets the scale threshold)
- Blueprints: 13 feature domains (members, trainers, classes, attendance, equipment, maintenance, billing, payments, assessments, etc.)
- File ownership: Each agent owns one blueprint (routes, templates, init) — no violations found
- Spec completeness check: 30 checks performed (docs/reports/054/spec-completeness-check.md) — passed 24/30
- Spec consistency check: 30 checks performed (docs/reports/054/spec-consistency-check.md) — **FAILED 12 checks**

**Severity:** HIGH

---

### 5. **Schema Consistency with Model Function Docstrings (Major Violation)**

**Source Document:** General best practice (Recipe Organizer, VenueConnect, GigSheet all validate docstrings against actual behavior)

**Key Lesson:**
> Model function docstrings that describe database behavior (especially error cases like IntegrityError) MUST match the actual SQL schema. Inconsistencies between docstring claims and FK constraint behavior create silent logic errors.

**GymFlow Status:** MASSIVE VIOLATION (12 FAILs in spec-consistency-check)

**Details:**

The pre-swarm consistency check found 9 FAIL contradictions in FK behavior:

| Function | Schema FK | FK Behavior | Docstring Claims | FAIL # |
|----------|-----------|-------------|------------------|--------|
| `delete_member` (attendance) | `ON DELETE CASCADE` | Silently deletes rows | Raises IntegrityError | 4 |
| `delete_member` (assessments) | `ON DELETE CASCADE` | Silently deletes rows | Raises IntegrityError | 4 |
| `delete_trainer` (schedules) | `ON DELETE SET NULL` | Sets trainer_id to NULL | Raises IntegrityError | 5 |
| `delete_trainer` (assessments) | `ON DELETE SET NULL` | Sets trainer_id to NULL | Raises IntegrityError | 5 |
| `delete_membership_type` | `ON DELETE SET NULL` | Sets membership_type_id to NULL | Raises IntegrityError | 6 |
| `delete_schedule` | `ON DELETE CASCADE` | Silently deletes rows | Raises IntegrityError | 7 |
| `delete_equipment` | `ON DELETE CASCADE` | Silently deletes rows | Raises IntegrityError | 8 |
| `delete_invoice` | `ON DELETE CASCADE` | Silently deletes rows | Raises IntegrityError | 9 |

**Root Cause:** The spec author chose CASCADE/SET NULL for FK constraints but wrote docstrings and acceptance tests expecting IntegrityError behavior (RESTRICT constraint). This is a design contradiction — the schema and acceptance tests are incompatible.

**Files Affected:**
- Schema: `gymflow/schema.sql`
- Model docstrings: Multiple files in `app/models/` (member.py, trainer.py, membership_type.py, schedule.py, equipment.py, invoice.py)
- Routes: Multiple files in `app/blueprints/*/routes.py` that call these delete functions (billing/routes.py, members/routes.py, etc.)
- Tests: Would expect IntegrityError but won't be raised

**Risk:** When an admin tries to delete a member with attendance records, the acceptance test expects "Cannot delete: referenced by other records" flash message (Coordinated Behavior #8). But the schema uses CASCADE, so the delete succeeds silently, deleting all attendance records. This is:
- **UX surprise:** Admin expects protection; gets cascade deletion
- **Data loss:** Attendance records deleted without warning
- **Test failure:** Acceptance tests claim "Cannot delete" but silently succeeds

**Severity:** CRITICAL (P0) — This is not a code bug; it's a spec design contradiction that will cause data loss.

---

### 6. **Wiring Table Omissions (Spec Inconsistency)**

**Source Document:** VenueConnect, GigSheet both have comprehensive Cross-Boundary Wiring tables

**Key Lesson:**
> The Cross-Boundary Wiring Table must list every cross-module function import with: Producer File, Consumer File, Import Path. Missing entries mean agents don't know what functions are available, leading to duplicate code or missed imports.

**GymFlow Status:** VIOLATION

**Evidence:**
Spec-consistency-check FAILs #1–#3:

| Function | Declared in Export Names | Missing from Wiring Import |
|----------|--------------------------|---------------------------|
| `get_invoices_by_member` | consumed by `billing_routes` | missing from `app/blueprints/billing/routes.py` wiring line |
| `get_attendance_by_member` | consumed by `attendance_routes` | missing from `app/blueprints/attendance/routes.py` wiring line |
| `get_attendance` | consumed by `attendance_routes` | missing from `app/blueprints/attendance/routes.py` wiring line |

**Actual Code Status:**
- File: `/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/attendance/routes.py`, lines 7-17
- Actual imports: `check_in_class`, `check_in_open_gym`, `check_out`, `get_attendance`, `get_attendance_by_member`, etc.
- **The functions ARE imported in the actual code** — the spec's Wiring Table just omitted them

**Root Cause:** Spec author listed these functions in the Export Names Table (they're in `models/__init__.py` barrel) but forgot to list them in the Wiring Table. The agents correctly imported them anyway (spec used as guide, not law), but the spec inconsistency means the next reader won't trust the Wiring Table.

**Severity:** MEDIUM (P1) — Spec integrity issue, not a runtime bug. But this pattern spreads: if some imports are omitted from the Wiring Table, readers can't tell which functions are actually used vs. which are available-but-unused.

---

### 7. **Money Handling Pattern: Cents Conversion**

**Source Document:** VenueConnect (Run 049), GigSheet (Run 050) both use integer cents throughout

**Key Lesson:**
> All money fields in SQLite MUST be INTEGER (cents), not REAL. All form inputs MUST be parsed as float, then converted to cents with `round(float(...) * 100)`. NaN and infinity MUST be checked before storing. No mixing of dollars (float) and cents (int) in the same codebase.

**GymFlow Status:** PASS

**Evidence:**

**Billing Routes** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/billing/routes.py`):
- Lines 56-69: `raw = float(...); amount_cents = round(raw * 100); check isnan/isinf`
- Lines 121-135: Same pattern in edit route

**Payments Routes** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/payments/routes.py`):
- Lines 57-70: `raw = float(...); amount_cents = round(raw * 100); check isnan/isinf`
- Line 74: Valid enum check for `payment_method`

**Invoice Model** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/models/invoice.py`):
- Lines 4-19: `create_invoice` accepts `amount_cents: int`
- Docstring example: `create_invoice(conn, 1, 4999, ...)` — 4999 cents, not 49.99 dollars

**Payment Model** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/models/payment.py`):
- Lines 5-25: `create_payment` accepts `amount_cents: int`
- Line 24: `conn.commit()` after insert
- Lines 64-75: `get_invoice_paid_amount` sums and returns int

**Severity:** LOW (no violations found — pattern correctly implemented)

---

### 8. **Input Validation Pattern: Enumerate Safe Values**

**Source Document:** GigSheet (Run 050, 31 agents) found 6 P1 input validation issues

**Key Lesson:**
> Every enum field (status, payment_method, attendance_type, etc.) MUST have a static set of allowed values. Routes MUST validate input against this set before passing to model functions. Never trust user input for enum fields.

**GymFlow Status:** PASS

**Evidence:**

**Attendance Routes** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/attendance/routes.py`):
- Lines 59-62: `attendance_type` must be in `('class', 'open_gym')` — explicit enum check
- Comment on line 58: "FC4: must be 'class' or 'open_gym'"

**Billing Routes** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/billing/routes.py`):
- Lines 150-153: `status` must be in `('pending', 'paid', 'overdue', 'cancelled')` — explicit check
- Lines 29-32: Same check on list_invoices for status filter

**Payments Routes** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/payments/routes.py`):
- Lines 73-76: `payment_method` must be in `('cash', 'card', 'bank_transfer', 'other')` — explicit check

**Severity:** LOW (no violations found)

---

### 9. **Spec Completeness Gates Prevent Assembly Surprises**

**Source Document:** GigSheet (Run 050) spec consistency checker caught 6 contradictions pre-swarm; VenueConnect (Run 049) had 56% agent commit failures (FC37)

**Key Lesson:**
> Run the spec completeness checker (step 9w.6) before swarm launch. It validates 6 mandatory sections: Export Names Table, Cross-Boundary Wiring, Input Validation, Coordinated Behaviors, Transaction Contracts, and Authorization Matrix. Missing sections or contradictions must be fixed before agents launch.

**GymFlow Status:** GATE PASSED, BUT 12 CONTRADICTIONS FOUND

**Evidence:**
- Spec completeness check passed (docs/reports/054/spec-completeness-check.md) — all 6 sections present
- Spec consistency check FAILED (docs/reports/054/spec-consistency-check.md) — 12 contradictions

The gate correctly identified the FK/docstring contradictions pre-swarm. The agents were allowed to proceed (ownership gate passed), but the spec consistency failures should have blocked swarm launch until fixed.

**Severity:** HIGH (gate process worked, but the fix recommendation wasn't implemented before swarm)

---

### 10. **Coordinated Behaviors: Standard 404 Pattern**

**Source Document:** VenueConnect (Run 049), GigSheet (Run 050) both prescribe standard resource lookup pattern

**Key Lesson:**
> When a route receives a resource ID, the coordinated behavior must be: fetch the resource, if None then `abort(404)`. Every route that takes a resource ID (not form-validated) MUST follow this pattern.

**GymFlow Status:** PASS

**Evidence:**

**Attendance Routes** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/attendance/routes.py`):
- Lines 99-101: Check-out route — `record = get_attendance(...); if record is None: abort(404)`
- Lines 120-122: Delete route — same pattern
- Comment: "Coordinated Behavior #7: 404 pattern"

**Billing Routes** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/billing/routes.py`):
- Lines 91-94: Detail route — `invoice = get_invoice(...); if invoice is None: abort(404)`
- Lines 106-109: Edit route — same pattern
- Lines 117-119: Update route — same pattern
- Lines 164-166: Delete route — same pattern

**Payments Routes** (`/Users/alejandroguillen/Projects/sandbox/gymflow/app/blueprints/payments/routes.py`):
- Lines 100-102: Delete route — `payment = get_payment(...); if payment is None: abort(404)`

**Severity:** LOW (no violations)

---

## Summary of Violations & Recommendations

### P0 (Critical, Must Fix Before Deploy)

| Finding | Category | File(s) | Fix |
|---------|----------|---------|-----|
| Schema/docstring contradiction: FK CASCADE but docstring claims IntegrityError | FC29-variant | schema.sql + 6 model files | Choose Option A (change FK to RESTRICT for members/equipment/invoices) or Option B (update docstrings/tests to reflect CASCADE behavior). Recommended: Option A to match acceptance test UX expectations. |
| Data loss risk on member/equipment/invoice delete | UX | 3 routes files | Once schema is fixed, ensure routes catch IntegrityError correctly or accept silent cascade. |

### P1 (High, Should Fix)

| Finding | Category | File(s) | Fix |
|---------|----------|---------|-----|
| Wiring Table omits 3 function imports | Spec integrity | docs/plans/2026-05-21-gym-manager-plan.md | Add `get_invoices_by_member`, `get_attendance_by_member`, `get_attendance` to Cross-Boundary Wiring table for their respective routes. Actual code imports them (checked), so this is spec documentation only. |
| Acceptance test vs schema contradiction | Spec/test | Multiple | Once FK constraints are fixed, update acceptance tests to match new schema behavior. |

### P2 (Medium, Nice to Fix)

| Finding | Category | File(s) | Fix |
|---------|----------|---------|-----|
| Missing input validation rules for 6 edit routes | Spec completeness | docs/plans/2026-05-21-gym-manager-plan.md | Add Input Validation Prescriptions rows for POST /*/edit routes. (Agents likely followed create route patterns, but spec should be explicit.) |
| Missing search route in Route Table | Spec completeness | docs/plans/2026-05-21-gym-manager-plan.md | Clarify how search functions (`search_members`, `get_members_by_status`, etc.) are used — query params on GET routes or dedicated search endpoints? |

---

## Lessons Applied Correctly

✓ **BEGIN IMMEDIATE with isolation_level=None** — Correctly implemented, preventing transaction failures  
✓ **Money handling (cents pattern)** — Consistent integer cents conversion with NaN/infinity checks  
✓ **Input validation (enum fields)** — All enum inputs validated against static safe lists  
✓ **404 pattern** — All resource lookups follow abort(404) pattern  
✓ **Endpoint registry (implicit)** — No url_for name mismatches found across 13 blueprints  
✓ **Large swarm coordination** — 26 agents, zero merge conflicts, vertical blueprint ownership respected  

---

## Lessons Violated

✗ **Schema consistency with docstrings** — 9 FK constraints don't match docstring IntegrityError claims  
✗ **Wiring Table completeness** — 3 functions in Export Names but missing from Wiring Table lines  
✗ **Input validation spec coverage** — 6 edit routes lack explicit validation rules in spec  

---

## Institutional Patterns This Build Validates

1. **Context manager usage in spec** — Explicitly documented pattern avoids swarm bugs (Flask Acid Test lesson applies)
2. **Spec consistency checker prevents assembly surprises** — GymFlow's gate correctly identified design contradictions before 26 agents built code
3. **Vertical blueprint ownership scales to 26 agents** — Zero merge conflicts, matching VenueConnect (25) and GigSheet (31) track record
4. **Money handling in Flask swarm** — Cents pattern proven across 4 builds; GymFlow follows established norm

---

## Reference Documents

- **Run 054 Spec Completeness:** docs/reports/054/spec-completeness-check.md
- **Run 054 Spec Consistency:** docs/reports/054/spec-consistency-check.md (12 FAILs detailed)
- **Run 049 (VenueConnect, 25 agents):** docs/solutions/2026-05-20-venueconnect-25-agent-swarm-build.md
- **Run 050 (GigSheet, 31 agents):** docs/solutions/2026-05-20-gigsheet-31-agent-swarm-build.md
- **Run 052 (RestaurantOps, 29 agents):** docs/solutions/2026-05-21-restaurant-kitchen-mgmt-swarm-build.md
- **Flask Acid Test (4 agents):** docs/solutions/2026-04-07-flask-swarm-acid-test.md
- **Bookmark Manager (3 agents):** docs/solutions/2026-04-09-bookmark-manager-swarm-build.md

---

## Next Steps

1. **Immediate:** Review the FK constraint contradiction (Root Cause A in spec-consistency-check). Choose Option A or B and file a decision.
2. **Before deploy:** Fix schema or docstrings to be consistent. Update acceptance tests to match.
3. **Spec documentation:** Add the 3 missing functions to Wiring Table (non-code fix).
4. **Validation completeness:** Document the 6 edit routes in Input Validation Prescriptions.

All other patterns (transaction handling, money, validation, 404, endpoint naming) are correctly implemented and align with institutional best practices from 4+ prior builds.
