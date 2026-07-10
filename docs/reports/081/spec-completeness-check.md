STATUS: PASS

# Pre-Swarm Spec Completeness Check

**Plan:** 2026-07-09-feat-lesson-studio-scale-validation-plan.md
**Checked:** 2026-07-10

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS | 4 identifier classes checked (model functions, blueprints, route paths, url_for targets); all covered across §1a, §1b, §1c, §1d |
| Orchestration Entrypoints (FC50) | PASS | 8 orchestration entrypoint rows; all have non-empty Full Signature |
| Cross-Boundary Wiring (FC3) | PASS | 16 producer modules enumerated from §1b; all present in §2 wiring table |
| Input Validation (FC4) | PASS | 23 qualifying mutating routes + typed GET params covered; all present in §3; global typed-param rule covers <int:> GET params |
| Registration Points (FC5) | PASS | 14 blueprints enumerated; all registered in §4 with explicit registration order and role-aware nav coverage |
| Transaction Contracts (FC29) | PASS | ~32 write functions annotated across 3 classes (A commit-internally, B owns-transaction, C in-tx-no-commit); all covered in §5 |
| Authorization Mode (FC35) | PASS | All 31 routes/route groups have an explicit mode in §6; role+own entries name the ownership field (student_id / actor_id / lesson instructor_id) and comparison method (SQL WHERE predicate in getter) |

## Details

No FAILs or WARNs.

### Export Names (FC1): PASS

The spec uses a multi-table Export Names structure (§1a infrastructure, §1b model functions, §1c blueprints/routes, §1d orchestration entrypoints) rather than a single flat table. All 4 identifier classes are covered:

- **Model functions:** §1b lists all functions from every `*_models.py` file grouped by model. Verified against the "Model Functions" prose section — all functions present.
- **Blueprint names:** §1c explicitly lists all 14 blueprint names (`auth`, `students`, `instructors`, `rooms`, `instruments`, `courses`, `enrollments`, `lessons`, `attendance`, `invoices`, `practice`, `announcements`, `dashboard`, `search`).
- **Route paths:** Declared in the Route Table section (Method/Path/View/Auth columns); §1c cross-references the Route Table for url_prefix data. Global typed-param rule (`<int:...>` → Flask 404) documented in §3.
- **url_for targets:** §1c names `<blueprint>.<view>` pattern with examples (`students.view_student`, `dashboard.index`, `dashboard.audit_log_view`).

### Orchestration Entrypoints (FC50): PASS

Section §1d contains 8 orchestration entrypoint rows, all with non-empty Full Signature:

| Entrypoint | Full Signature Present |
|------------|----------------------|
| `audit_models.record` | yes |
| `invoice_models.add_item_in_tx` | yes |
| `invoice_models.get_or_create_draft_invoice_in_tx` | yes |
| `instrument_models.set_instrument_status` | yes |
| `dashboard_models.*_summary` (3 variants) | yes |
| `lesson_models.check_conflicts` | yes |
| `course_models.count_enrolled / get_course` | yes |
| `search_models.search_all` | yes |

### Cross-Boundary Wiring (FC3): PASS

Section §2 lists 16 producer→consumer wiring rows covering all model modules and infrastructure files. Every cross-boundary function from §1b appears as a producer. Dense coupling nodes explicitly noted (dashboard imports 5 model modules; lessons imports 4).

### Input Validation (FC4): PASS

Section §3 covers all 23 qualifying route groups. Key entries:

- All POST/DELETE routes to mutating endpoints present with: what input, how validated, error response.
- TOCTOU-sensitive guards (checkout availability, enroll capacity/UNIQUE, enroll active-course) are documented as authoritative inside `BEGIN IMMEDIATE` (not duplicate route pre-checks) — correctly noted in §3.
- GET routes with `<int:>` typed URL params covered by the global note: "Typed URL params (`<int:...>`) → Flask 404 on non-int."
- Global CSRF rule documented: every POST/PUT/PATCH/DELETE validates `_csrf` → 400.

### Registration Points (FC5): PASS

Section §4 names all 14 blueprints with their registration order in `studio/__init__.py`. Two exceptions are documented: `dashboard` has no url_prefix (owns `/`), and `rooms` is owned by the scaffold agent. Role-aware nav coverage: admin/instructor/student nav links enumerated, covering all user-facing blueprints.

### Transaction Contracts (FC29): PASS

Section §5 annotates all DB writers into 3 classes:

- **Class A (commits internally):** ~29 functions listed including all `create_*`, `update_*`, `set_*_active`, `mark_attendance`, `set_invoice_status`, `delete_*`, `record`.
- **Class B (owns one BEGIN IMMEDIATE):** exactly 3 — `checkout_instrument`, `return_instrument`, `enroll`.
- **Class C (in-tx helpers, no commit):** exactly 3 — `set_instrument_status`, `add_item_in_tx`, `get_or_create_draft_invoice_in_tx`.

Audit rule is explicit: `audit_models.record` is Class A and is always called post-commit by the route, never nested inside a Class B transaction.

### Authorization Mode (FC35): PASS

Section §6 covers all 31 route entries/groups with modes (public, auth, role:admin,instructor, role+own, admin). For every `role+own` entry:

- `/students/<sid>`: ownership field = `students.user_id` matched to `actor_id`; comparison in SQL WHERE predicate via `get_student_for(sid, actor)`.
- `/lessons` list and `/<lid>`: dual ownership (student_id OR instructor_id); comparison documented in Ownership-Scoped Getter Contract.
- `/invoices/<iid>`: `student_id = (SELECT id FROM students WHERE user_id=:actor_id)`.
- `/practice` list/new/delete: `student_id = (SELECT id FROM students WHERE user_id=:actor_id)`; `practice/new` additionally documented as student-self-service-only (staff → 403).

404-not-403 rule documented and consistent across all role+own read routes.

## Summary

- **Total checks:** 7
- **PASS:** 7
- **FAIL:** 0
- **WARN:** 0
- **N/A:** 0
- **BLOCKED:** 0
