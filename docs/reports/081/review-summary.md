# Review Summary — Run 081 (Lesson Studio Scale-Validation)

**Date:** 2026-07-10
**Review agents:** security-IDOR-flow-trace, learnings-researcher, enrollment-invoice-flow-trace

---

## P1 Findings

### P1-01: `current_user()` called as a function in 5 templates (8 occurrences) — FIXED

**Severity:** P1 — Runtime 500 error for every logged-in user on lessons, courses, instruments pages

**Root cause:** `studio/__init__.py` line 78 injects `current_user` as an already-resolved dict
(`return {"current_user": current_user(), ...}`). The function is called at context-processor time
and the result (dict or None) is stored in the template variable. However, 8 template locations
treat the dict as a callable — `current_user()` and `current_user().role` — which raises
`TypeError: 'dict' object is not callable` for any logged-in user, or `TypeError: 'NoneType' is
not callable` for anonymous users.

**Affected files (pre-fix):**
- `studio/templates/lessons/list.html` line 6 — 1 occurrence
- `studio/templates/lessons/view.html` lines 6, 37 — 2 occurrences
- `studio/templates/courses/list.html` lines 6, 35 — 2 occurrences
- `studio/templates/courses/view.html` line 6 — 1 occurrence
- `studio/templates/instruments/list.html` lines 7, 51 — 2 occurrences

**Fix applied (tail-runner, 2026-07-10):** All 8 occurrences replaced:
`current_user()` → `current_user`, `current_user().role` → `current_user.role`

**Fix commit:** FIREBREAK_DEFERRED (staged in git, awaiting human approval to commit per FC58 tail-phase firebreak). Approval file: `todos/approvals/RED-081-indirection-03a24cdd5e52.md`

**Note:** `base.html` already used the correct dict-access form (`current_user.role`). Other templates
(`invoices/list.html`, `students/view.html`, `announcements/list.html`, etc.) also used the correct
form. This was an F4-class bug (current_user dict-vs-callable inconsistency) affecting 5 of the 14
template directories.

---

## P2 Findings

### P2-01: `require_self_or_staff` implemented but never called

**File:** `studio/auth.py` lines 96–109

**Issue:** The function is fully implemented and correct but never imported or invoked in any
route. The student edit route (`/students/<sid>/edit`) is gated with
`@role_required('admin', 'instructor')`, which means students cannot reach it — so no IDOR
gap exists today. However, the defense-in-depth guard the spec intended is absent.

**Impact:** Non-exploitable with current role guards; flagged for documentation.

**Recommendation:** Either call `require_self_or_staff(sid)` in `edit_student` for instructor
actors, or document why the current `role_required('admin', 'instructor')` is the final intended
guard.

### P2-02: `target_student_id` passed as raw string to practice model

**File:** `studio/routes/practice.py` lines 33–34

**Issue:** `request.args.get('target_student_id')` is a raw string passed to
`list_practice_logs_for(actor, target_student_id)`. SQLite coerces `"5"` → `5` silently,
but a non-numeric value (`?target_student_id=abc`) returns empty results instead of 400.

**Recommendation:** `int(target_student_id_raw) if target_student_id_raw else None` with
`except ValueError: abort(400)`.

### P2-03: `count_enrolled` / `get_course` use implicit connection identity inside `enroll()` transaction

**File:** `studio/models/enrollment_models.py` lines 92–97;
`studio/models/course_models.py` lines 108–120, 53–59

**Issue:** Inside the `BEGIN IMMEDIATE` transaction in `enroll()`, the calls to
`count_enrolled(course_id)` and `get_course(course_id)` go through `query()` → `get_db()`,
relying on Flask `g` caching the same connection the transaction opened. This is correct
under the current single-connection-per-request design but is a fragile implicit coupling.
If `get_db()` were ever changed to return a new connection per call (e.g., under a
connection pool), the TOCTOU guarantee would silently break.

**Current status:** PASS for current design. Documented as portability risk.

---

## P3 / PASS Findings

### F3 — Lesson 4-way FK join aliases: PASS
`lesson_models._LESSON_SELECT` (lines 33–53) provides `instructor_name`, `student_name`,
`room_name`, `course_name` via SQL AS aliases. All consuming templates (`lessons/list.html`,
`lessons/view.html`, `attendance/lesson.html`) and `dashboard_models.py` use these exact alias
names. Feed-Forward seam is correctly wired.

### F4 — `current_user` dict consistency: FIXED (was P1-01 above)
After fix: all templates use `current_user` (dict) and `current_user.role` (attribute access).
`base.html` was already correct.

### F5 — practice/new 403 for users without students row: PASS (spec-correct)
`routes/practice.py`: `sid = current_student_id() or abort(403)`. Correct per spec.

### F6 — Search hides instructors from students: PASS
`search_models.py` lines 83–92: `result["instructors"]` only populated when `is_staff is True`.
Students receive `instructors: []`. Scope boundary enforced.

### FC35/IDOR — All ownership-scoped getters use SQL WHERE predicates: PASS
All four required getters confirmed clean (SQL predicate, no fetch-then-compare):
- `lesson_models.get_lesson_for` — compound WHERE (student OR instructor owner)
- `invoice_models.get_invoice_for` — SQL AND predicate
- `student_models.get_student_for` — SQL AND (?staff OR user_id=actor) predicate
- `practice_log_models.get_practice_log_for` — SQL AND (:staff OR subquery) predicate

### Enrollment → Invoice transaction: PASS
- `enroll()` uses `with transaction() as conn` — PASS
- Both in-tx helpers accept `conn` as first arg and do NOT commit — PASS
- Route calls `audit_models.record()` AFTER `enroll()` returns (post-commit) — PASS
- `set_invoice_status` blocks `→ draft` transition at first line — PASS (double-defended: route also excludes 'draft' from allowed transitions)
- `get_or_create_draft_invoice_in_tx` correctly reuses existing draft — PASS
- `count_enrolled` runs inside BEGIN IMMEDIATE via shared `g.db` connection — PASS

### Checkout → Instrument transaction: PASS
- `checkout_instrument` uses `with transaction() as conn` — PASS
- `set_instrument_status(conn, ...)` called on same conn — PASS
- `return_instrument` follows same atomic pattern — PASS

### CSRF enforcement: PASS
Global `before_request` hook with `secrets.compare_digest` timing-safe comparison. All POST
forms in reviewed templates include `<input type="hidden" name="_csrf" value="{{ csrf_token() }}">`.
`csrf_token` is injected as a callable (not a resolved value), so `{{ csrf_token() }}` correctly
calls the function each request.

---

## Feed-Forward Risk Resolution (Plan §feed_forward.risk)

**Risk:** "The lessons (schedule) row is a 4-way FK seam (instructor + student + room + course)
and is consumed by lesson routes + attendance + dashboard — the densest cross-boundary coupling
in the spec. A single name/return-type mismatch there fails the schedule page AND the aggregates
that read it."

**Actual outcome:** The 4-way seam (`_LESSON_SELECT` aliases) was correctly implemented and
verified PASS (F3). The cross-worker scan flag F3 was resolved cleanly at contract-check (Step
4 inline). The seam did NOT produce a P1 — the spec's explicit alias prescription (`instructor_name`,
`student_name`, `room_name`, `course_name`) successfully guided all consuming agents.

**What actually failed instead:** A different F4-class bug (current_user dict-vs-callable
inconsistency) produced the one P1 — not the seam the Feed-Forward risk identified. This is
useful data: the deliberately-hardest seam survived; the lower-priority F4 flag (cross-worker
scan noted it as "VERIFY") was where the actual P1 materialized.

---

## Summary Table

| ID | Priority | Finding | Status |
|----|----------|---------|--------|
| P1-01 | P1 | `current_user()` callable in 5 templates (8 occurrences) | **FIXED** (staged, commit deferred by firebreak) |
| P2-01 | P2 | `require_self_or_staff` dead code | Deferred — non-exploitable |
| P2-02 | P2 | `target_student_id` not coerced to int | Deferred — silent bad input |
| P2-03 | P2 | Implicit conn identity in `enroll()` | Deferred — portability risk, correct today |
| F3 | PASS | Lesson 4-way FK join aliases | Clean |
| F4 | P1→FIXED | current_user dict-vs-callable | Fixed |
| F5 | PASS | practice/new 403 (spec-correct) | Clean |
| F6 | PASS | Search hides instructors from students | Clean |
| FC35 | PASS | IDOR ownership getters (SQL WHERE) | Clean |
| TX | PASS | Enrollment+Invoice, Checkout+Instrument transactions | Clean |
| CSRF | PASS | Global CSRF enforcement | Clean |

**P1 count:** 1 (fixed)
**P2 count:** 3 (deferred — non-blocking for this throwaway vehicle)
**Fix commits:** FIREBREAK_DEFERRED — staged, approval pending at `todos/approvals/RED-081-indirection-03a24cdd5e52.md`
