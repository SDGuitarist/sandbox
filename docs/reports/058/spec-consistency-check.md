# Pre-Swarm Spec Consistency Check

**Plan:** client-intake-dashboard-plan.md
**Checked:** 2026-05-22 (re-check after 5-FAIL fix pass)

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Route Handler vs Model Function Name | Sec 10: handler `list_view` in blueprint `submissions` | Sec 13: `from app.models.submissions import list_submissions` | PASS | Previous FAIL fixed. Handler is now `list_view`, model function is `list_submissions`. No name collision. |
| 2 | Route Handler vs Model Function Name | Sec 10: handler `change_status` in blueprint `status` | Sec 13: `from app.models.submissions import ... update_status ...` | PASS | Previous FAIL fixed. Handler is now `change_status`, model function is `update_status`. No name collision. |
| 3 | Route Handler vs Model Function Name | Sec 10: handler `toggle_fit` in blueprint `status` | Sec 13: `from app.models.submissions import ... toggle_audit_fit ...` | PASS | Previous FAIL fixed. Handler is now `toggle_fit`, model function is `toggle_audit_fit`. No name collision. |
| 4 | Export Names Table vs Cross-Boundary Wiring Table | Sec 12: `VALID_STATUSES` used by `status_routes` | Sec 13: `from app.models.submissions import get_submission, update_status, toggle_audit_fit, VALID_STATUSES, TERMINAL_STATUSES` | PASS | Previous FAIL fixed. VALID_STATUSES is now present in the status_routes import line in Sec 13. |
| 5 | Authorization Matrix vs Route Handler Code | Sec 18: POST /logout mode `public`, check `N/A (unauthenticated logout is safe)` | Sec 7: `@auth_bp.route('/logout', methods=['POST'])` with no `@login_required` | PASS | Previous FAIL fixed. Sec 18 now says `public`, consistent with Sec 7 prescriptive code. |
| 6 | Route Table vs Export Names (url_for names) | Sec 10: url_for `submissions.list_view`, `status.change_status`, `status.toggle_fit` | Sec 12: same endpoint names listed as type `endpoint`; base.html in Sec 16 uses `url_for('submissions.list_view')` | PASS | All renamed endpoint references are consistent across Sec 10, Sec 12, and the prescriptive base.html in Sec 16. |
| 7 | Cross-Boundary Wiring vs Export Names (Missing Wire: register_filters) | Sec 12: `register_filters` defined by `filters`, used by `core (__init__.py)` | Sec 13 line 912: `app/filters.py -> app/__init__.py` with `from app.filters import register_filters` | PASS | Previous WARN resolved. Wire is now present in Sec 13. |
| 8 | Cross-Boundary Wiring vs Export Names (Missing Wires: blueprint registrations) | Sec 12: 7 blueprint objects listed as used by `core (__init__.py)` | Sec 13: no rows for any blueprint -> core registration imports | WARN | Seven blueprint imports (`from app.auth import auth_bp`, `from app.blueprints.*.routes import *_bp`) are declared in Sec 12 but absent from Sec 13. Since Sec 5 provides full prescriptive `create_app()` code with all imports, the core agent will not be blocked. However, Sec 13 cannot serve as a standalone reference for blueprint wiring. |
| 9 | Schema Field Names vs Input Validation Form Fields | Sec 3 schema: all 11 non-system columns | Sec 14: form field names match exactly | PASS | All field names match between schema definitions and input validation prescriptions. |
| 10 | Schema Field Names vs Model Function Parameters | Sec 3 schema: 11 intake columns | Sec 9.1 `create_submission` INSERT: same 11 columns in same order | PASS | All 11 field names match between schema and model INSERT statement. |
| 11 | SQL Types vs App-Layer Types | Sec 3: `id INTEGER`, `submission_id INTEGER`, `is_audit_fit INTEGER` | Sec 9 model signatures: `submission_id: int`, `assessment_id: int`; functions return `int` for IDs | PASS | INTEGER columns map to `int` type hints throughout. No type mismatch. |
| 12 | SQL Types vs App-Layer Types | Sec 3: all non-ID, non-timestamp columns are `TEXT NOT NULL` | Sec 9 model usage: all non-ID parameters are `str` or `dict` with str values | PASS | No type mismatch found. |
| 13 | Route Table vs Export Names (url_for names) | Sec 10: 12 routes with url_for targets | Sec 12: same endpoint names listed as type `endpoint` | PASS | All 12 url_for endpoint names in the Route Table appear verbatim in the Export Names Table. |
| 14 | Route Table vs Authorization Matrix (coverage) | Sec 10: 12 routes defined | Sec 18: all 12 routes covered (some split into GET/POST rows) | PASS | All routes in Sec 10 have a corresponding entry in Sec 18. |
| 15 | Coordinated Behaviors vs App Config (blueprint registration order) | Sec 15: order `auth, intake, dashboard, submissions, detail, status, assessments` | Sec 5 `create_app()`: registers in same order | PASS | Registration order consistent across both sections. |
| 16 | Coordinated Behaviors vs App Config (url_prefixes) | Sec 15: auth=none, intake=/intake, dashboard=/admin, submissions+detail+status+assessments=/admin/submissions | Sec 5 `register_blueprint` calls: match exactly | PASS | All url_prefix assignments match between Sec 15 and Sec 5. |
| 17 | Template Render Context vs Model Return Types | Sec 11: `stats=count_by_status(conn)` described as `dict: {'new': 3, ...}` | Sec 9.1 `count_by_status`: returns `dict[str, int]`, always includes all valid statuses | PASS | Return type and usage context match. |
| 18 | Template Render Context vs Model Return Types | Sec 11: `submissions=list_submissions(...)` described as `list of sqlite3.Row` | Sec 9.1 `list_submissions`: returns `list[sqlite3.Row]` | PASS | Match confirmed. |
| 19 | Template Render Context vs Model Return Types | Sec 11: `assessment=get_assessment_by_submission(...)` described as `sqlite3.Row or None` | Sec 9.2 `get_assessment_by_submission`: returns `sqlite3.Row or None` | PASS | Match confirmed. |
| 20 | Template Render Context vs Model Return Types | Sec 11: `notes=list_notes(conn, submission_id)` described as `list of sqlite3.Row` | Sec 9.3 `list_notes`: returns `list[sqlite3.Row]` | PASS | Match confirmed. |
| 21 | Transaction Contracts vs Model Implementation | Sec 17 table: all 11 functions listed with commit status | Sec 9 model code: all commit/read-only behaviors verified against Sec 17 | PASS | Every function's actual implementation matches what Sec 17 declares. |
| 22 | Cross-Boundary Wiring vs Export Names (VALID_STATUSES in submissions_routes) | Sec 12: `VALID_STATUSES` used by `submissions_routes` | Sec 13: `from app.models.submissions import list_submissions, VALID_STATUSES` | PASS | VALID_STATUSES correctly included in submissions_routes import. |
| 23 | Cross-Boundary Wiring vs Export Names (TERMINAL_STATUSES in status_routes and detail_routes) | Sec 12: `TERMINAL_STATUSES` used by `detail_routes, status_routes` | Sec 13: both routes include TERMINAL_STATUSES in their import lines | PASS | TERMINAL_STATUSES present in both import statements. |
| 24 | Schema FK ON DELETE vs Delete Functions | Sec 3: `assessments.submission_id REFERENCES submissions(id) ON DELETE CASCADE`, `notes.submission_id REFERENCES submissions(id) ON DELETE CASCADE` | No `delete_submission` function defined in spec | N/A | No parent-table delete function exists. Both child tables use ON DELETE CASCADE. No docstring to contradict. |
| 25 | Mock / Fixture Data vs Schema Fields | seed.py agent assigned (Sec 21, agent #14) but no prescriptive seed data content in spec | N/A | N/A | No fixture data content to check against schema fields. |
| 26 | Input Validation Prescriptions vs Schema Constraints | Sec 14: `status` validated as `must be in VALID_STATUSES` (7 values) | Sec 3: `status CHECK (status IN ('new', 'reviewed', 'assessment-ready', 'audit-scheduled', 'completed', 'declined', 'archived'))` | PASS | 7 values in `VALID_STATUSES` match the 7 values in the SQL CHECK constraint exactly. |
| 27 | Input Validation Prescriptions vs Schema Constraints | Sec 14: toggle audit-fit (no direct form input) | Sec 3: `is_audit_fit INTEGER NOT NULL DEFAULT 0 CHECK (is_audit_fit IN (0, 1))` | PASS | Toggle model function flips between 0 and 1, consistent with the CHECK constraint. |
| 28 | Coordinated Behaviors vs Template Contracts (CSRF syntax) | Sec 15: `{{ csrf_token() }}` with parentheses required | Sec 16: same exact syntax prescribed | PASS | Consistent across both sections. |
| 29 | Coordinated Behaviors vs Template Contracts (base template name) | Sec 15: all templates use `{% extends "base.html" %}` | Sec 16: base template filename is `app/templates/base.html` | PASS | No contradiction. |
| 30 | Coordinated Behaviors vs Route Rules (post-action redirect scope) | Sec 15: "Successful POST handlers redirect... Validation failures may re-render the form (intake, login)" | Sec 14: POST /intake on validation error returns `render_template('intake/form.html')` | PASS | Previous WARN resolved. Sec 15 now explicitly scopes the redirect rule to successful handlers and carves out validation-error re-renders. |
| 31 | Export Names Table vs Wiring Table (list_notes in detail_routes) | Sec 12: `list_notes` used by `detail_routes` | Sec 13: `from app.models.notes import create_note, list_notes` | PASS | Both `create_note` and `list_notes` are present in the detail_routes import. |
| 32 | Export Names Table vs Wiring Table (TERMINAL_STATUSES absent from submissions_routes) | Sec 12: `TERMINAL_STATUSES` used by `detail_routes, status_routes` (not submissions_routes) | Sec 13: submissions_routes import has no TERMINAL_STATUSES | PASS | Correct omission -- submissions list view has no need for TERMINAL_STATUSES. |
| 33 | File Assignment Boundaries vs Cross-Boundary Wiring (auth.py owner) | Sec 20: `app/auth.py` owned by agent `auth` | Sec 13: `app/auth.py` is a producer for 5 consumer routes | PASS | Ownership consistent. auth agent writes auth.py; route agents import from it. |
| 34 | Blueprint Names vs url_for Endpoint Prefixes | Sec 10 url_for targets use prefixes: `intake`, `auth`, `dashboard`, `submissions`, `detail`, `status`, `assessments` | Sec 5 imports: blueprints from matching route files; auth_bp explicitly named `'auth'` in Sec 7 | PASS | The url_for endpoint prefixes in Sec 10 match the blueprint names implied by Sec 12 and Sec 7. Agents must name blueprints accordingly. |
| 35 | Smoke Test vs Route Table (path coverage) | Sec 19 smoke test: uses literal URL paths | Sec 10 route table: defines all paths used by smoke test | PASS | All paths in smoke test (`/health`, `/intake`, `/login`, `/admin/`, `/admin/submissions`, `/admin/submissions/<id>`, etc.) match Sec 10 route table. Smoke test uses paths, not endpoint names, so handler renames do not affect it. |

---

## Summary

- **Total checks:** 35
- **PASS:** 33
- **FAIL:** 0
- **WARN:** 1
- **N/A (section absent):** 2

---

## WARN Details (Recommended Fix; Will Not Block Swarm)

### WARN #8: Cross-Boundary Wiring Table Missing Blueprint Registration Wires

Sec 13 is missing 7 import relationships that are declared in Sec 12 and present in Sec 5 code:

- `app/auth.py -> app/__init__.py` (`from app.auth import auth_bp`)
- `app/blueprints/intake/routes.py -> app/__init__.py` (`from app.blueprints.intake.routes import intake_bp`)
- `app/blueprints/dashboard/routes.py -> app/__init__.py` (`from app.blueprints.dashboard.routes import dashboard_bp`)
- `app/blueprints/submissions/routes.py -> app/__init__.py` (`from app.blueprints.submissions.routes import submissions_bp`)
- `app/blueprints/detail/routes.py -> app/__init__.py` (`from app.blueprints.detail.routes import detail_bp`)
- `app/blueprints/status/routes.py -> app/__init__.py` (`from app.blueprints.status.routes import status_bp`)
- `app/blueprints/assessments/routes.py -> app/__init__.py` (`from app.blueprints.assessments.routes import assessments_bp`)

Since Sec 5 provides the complete prescriptive `create_app()` code including all imports, the core agent will not be blocked. However, Sec 13 cannot serve as a standalone cross-reference for blueprint wiring. Recommended fix: add the 7 missing rows to Sec 13.

---

## All 5 Previous FAILs Confirmed Resolved

| Previous FAIL | Fix Applied | Verification |
|---------------|-------------|--------------|
| Handler `list_submissions` shadowed model import | Handler renamed to `list_view` | Sec 10, Sec 12, Sec 16 all show `list_view` / `submissions.list_view` |
| Handler `update_status` shadowed model import | Handler renamed to `change_status` | Sec 10, Sec 12 all show `change_status` / `status.change_status` |
| Handler `toggle_audit_fit` shadowed model import | Handler renamed to `toggle_fit` | Sec 10, Sec 12 all show `toggle_fit` / `status.toggle_fit` |
| `VALID_STATUSES` missing from status_routes wiring | Added to Sec 13 import line | Sec 13 line: `import get_submission, update_status, toggle_audit_fit, VALID_STATUSES, TERMINAL_STATUSES` |
| Logout auth contradiction (`login-required` vs no decorator) | Sec 18 changed to `public` | Sec 18 mode=`public`, check=`N/A (unauthenticated logout is safe)` |

---

STATUS: PASS
