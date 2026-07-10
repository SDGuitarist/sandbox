STATUS: PASS

# Contract Check — Run 081

## Priority Flags (F1-F5)

### F1 — dashboard summary dict key names
FINDING: `instructor_summary()` in `studio/models/dashboard_models.py` returns keys
`courses` (list) and `students_count` (int), but `studio/templates/dashboard/index.html`
was using `summary.my_courses` and `summary.my_students`.

FIX APPLIED (template aligned to model, per F1 instruction):
- `summary.my_courses` → `summary.courses | length`
- `summary.my_students` → `summary.students_count`

Student keys (`balance_cents`, `practice_minutes_this_week`, `attendance_rate`,
`upcoming_lessons`, `enrollments`) match model output exactly. PASS after fix.

### F2 — instruments/checkouts.html expects `student_name`
FINDING: `list_checkouts()` returned `student_first_name` + `student_last_name` separately
but the template expected `checkout.student_name`.

FIX APPLIED (model query updated):
Added `(s.first_name || ' ' || s.last_name) AS student_name` to both `list_checkouts`
and `get_checkout` SQL in `studio/models/checkout_models.py`. PASS after fix.

### F3 — lesson templates expect join aliases
VERIFIED: `lesson_models._LESSON_SELECT` already provides `instructor_name`, `student_name`,
`course_name`, `room_name` via SQL AS aliases. Templates in lessons/, attendance/,
dashboard/ all use these names consistently. PASS (no fix needed).

### F4 — current_user is dict or None
VERIFIED: `studio/__init__.py` line 78 injects `"current_user": current_user()`
(calling the function at request time — returns dict or None). `base.html` uses
`{% if current_user is not none %}` (Jinja lowercase none) and `current_user.role`,
`current_user.name` (dict attribute access). `students/view.html` also uses dict access.
PASS (no fix needed).

### F5 — practice/new 403 for users without students row
INFORMATIONAL (no fix applied per FC59 — tests are read-only oracle).
A freshly registered student user with no `students` row will get `current_student_id()=None`
→ `abort(403)` at `/practice/new`. This is SPEC-CORRECT behavior — it is a smoke test
harness setup issue (seed a students row for the registered user), not an app bug.
Recorded here; tests are NOT weakened.

## Spec Contract Coverage

### Export Names (§1a/§1b)
All model functions verified present via grep:
- `get_db`, `query`, `transaction`, `init_db` ✓ (database.py)
- `login_required`, `role_required`, `current_user`, `current_student_id`, `current_instructor_id`, `require_self_or_staff`, `login_user`, `logout_user` ✓ (auth.py)
- `record`, `list_audit` ✓ (audit_models.py)
- All model-agent functions present in their respective files ✓

### Cross-Boundary Wiring (§2)
- `enrollment_models` imports `get_course`, `count_enrolled` from `course_models` ✓
- `enrollment_models` imports `add_item_in_tx`, `get_or_create_draft_invoice_in_tx` from `invoice_models` ✓
- `checkout_models` imports `set_instrument_status` from `instrument_models` ✓
- `dashboard_models` imports exactly 5 model modules (lesson, invoice, enrollment, attendance, practice_log) ✓
- `search_models` does NOT import lesson/attendance/invoice (scope boundary) ✓

### Blueprint Names / URL Prefixes
All 14 blueprints registered in `__init__.py` in prescribed order ✓
`dashboard` blueprint registered with NO url_prefix (owns `/` and `/audit`) ✓
All view function names match `url_for` targets in base.html ✓

### Block Names (FC54)
`base.html` defines `{% block title %}` and `{% block content %}` only ✓
All child templates extend base.html and override only these two blocks ✓

### Transaction Classes (§5)
Class-B writers (`checkout_instrument`, `return_instrument`, `enroll`) each use
`with transaction() as conn` and thread conn to in-tx helpers ✓
Class-C helpers (`set_instrument_status`, `add_item_in_tx`, `get_or_create_draft_invoice_in_tx`)
take caller-supplied `conn` and do NOT commit ✓

## Result

CONTRACT CHECK: PASS (2 inline fixes applied: F1 template keys, F2 student_name alias)
