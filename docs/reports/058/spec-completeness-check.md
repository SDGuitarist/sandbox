# Pre-Swarm Spec Completeness Check

**Plan:** client-intake-dashboard-plan.md
**Checked:** 2026-05-22 (re-check after FC3 fix)

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS | 50 identifiers checked, 0 missing |
| Cross-Boundary Wiring (FC3) | PASS | 7 cross-boundary blueprint producers, 0 missing wiring rows |
| Input Validation (FC4) | PASS | 8 qualifying routes, 0 unvalidated |
| Registration Points (FC5) | PASS | 7 blueprints, 0 unregistered |
| Transaction Contracts (FC29) | PASS | 6 write functions, 0 unannotated |
| Authorization Mode (FC35) | PASS | 12 routes, 0 unannotated |

## Details

### Export Names (FC1): PASS

**Class A -- Model functions (11 found):**
`create_submission`, `get_submission`, `list_submissions`, `update_status`,
`toggle_audit_fit`, `count_by_status`, `create_assessment`,
`get_assessment_by_submission`, `update_assessment`, `create_note`,
`list_notes` -- all present in Section 12.

**Class B -- Endpoint names (12 found):**
`intake.intake_form`, `intake.thank_you`, `auth.login`, `auth.logout`,
`dashboard.index`, `submissions.list_view`, `detail.view_submission`,
`detail.add_note`, `status.change_status`, `status.toggle_fit`,
`assessments.assessment_form`, `health` -- all present in Section 12.

**Class C -- Blueprint names (7 found):**
`auth_bp`, `intake_bp`, `dashboard_bp`, `submissions_bp`, `detail_bp`,
`status_bp`, `assessments_bp` -- all present in Section 12.

**Class D -- Route paths (12 found):**
Extracted from Section 10 route table, Path column (cells start with `/`).
`/intake`, `/intake/thank-you`, `/login`, `/logout`, `/admin/`,
`/admin/submissions`, `/admin/submissions/<int:submission_id>`,
`/admin/submissions/<int:submission_id>/notes`,
`/admin/submissions/<int:submission_id>/status`,
`/admin/submissions/<int:submission_id>/audit-fit`,
`/admin/submissions/<int:submission_id>/assessment`, `/health` --
all 12 present in Section 12 (lines 870-881). PASS.

---

### Cross-Boundary Wiring (FC3): PASS

**Dependency:** Export Names table (Section 12) is parseable. Proceeding.

**Cross-boundary producers enumerated from Export Names table** (Defined By agent != Used By agent):

The following blueprint objects are listed in Section 12 as cross-boundary
(defined by route agents, consumed by `core`):

| Name | Defined By | Used By |
|------|-----------|---------|
| `auth_bp` | auth | core (__init__.py) |
| `intake_bp` | intake_routes | core (__init__.py) |
| `dashboard_bp` | dashboard_routes | core (__init__.py) |
| `submissions_bp` | submissions_routes | core (__init__.py) |
| `detail_bp` | detail_routes | core (__init__.py) |
| `status_bp` | status_routes | core (__init__.py) |
| `assessments_bp` | assessment_routes | core (__init__.py) |

**Verification against Section 13 (lines 914-920):**

All 7 blueprint-to-core wiring rows are now present:

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/auth.py | app/__init__.py | `from app.auth import auth_bp` |
| app/blueprints/intake/routes.py | app/__init__.py | `from app.blueprints.intake.routes import intake_bp` |
| app/blueprints/dashboard/routes.py | app/__init__.py | `from app.blueprints.dashboard.routes import dashboard_bp` |
| app/blueprints/submissions/routes.py | app/__init__.py | `from app.blueprints.submissions.routes import submissions_bp` |
| app/blueprints/detail/routes.py | app/__init__.py | `from app.blueprints.detail.routes import detail_bp` |
| app/blueprints/status/routes.py | app/__init__.py | `from app.blueprints.status.routes import status_bp` |
| app/blueprints/assessments/routes.py | app/__init__.py | `from app.blueprints.assessments.routes import assessments_bp` |

All 7 cross-boundary blueprint producers are now covered. PASS.

Previously present wiring rows (29 rows, unchanged):
- `app/db.py` to intake/submissions/detail/status/assessments/dashboard routes.py (6 rows, get_db)
- `app/db.py` to seed.py (get_db)
- `app/__init__.py` to intake_routes (limiter)
- `app/auth.py` to submissions/detail/status/assessments/dashboard routes.py (5 rows, login_required)
- `app/models/submissions.py` to intake/submissions/detail/status/assessments/dashboard routes.py (6 rows)
- `app/models/assessments.py` to detail/assessments routes.py (2 rows)
- `app/models/notes.py` to detail_routes (1 row)
- `app/models/submissions.py` to seed.py (1 row)
- `app/models/assessments.py` to seed.py (1 row)
- `app/models/notes.py` to seed.py (1 row)
- `app/filters.py` to app/__init__.py (1 row)
- `app/db.py` to app/__init__.py (1 row)

Total wiring rows: 36. All cross-boundary functions covered.

---

### Input Validation (FC4): PASS

**Qualifying routes (8 total):** Routes with Method POST/PUT/PATCH/DELETE or
path containing `<int:`.

| Route | Qualifying Reason | In Prescriptions (Section 14)? |
|-------|-------------------|-------------------------------|
| POST /intake | POST | YES (12 rows covering all fields + honeypot) |
| GET/POST /login | POST | YES (2 rows) |
| POST /logout | POST | YES (N/A row -- no user inputs beyond CSRF) |
| GET /admin/submissions/<int:submission_id> | contains `<int:` | YES (abort(404) row) |
| POST /admin/submissions/<int:submission_id>/notes | POST + `<int:` | YES (content field row) |
| POST /admin/submissions/<int:submission_id>/status | POST + `<int:` | YES (2 rows: new_status allowlist + terminal check) |
| POST /admin/submissions/<int:submission_id>/audit-fit | POST + `<int:` | YES (N/A row -- no user inputs, abort(404) if not found) |
| GET/POST /admin/submissions/<int:submission_id>/assessment | POST + `<int:` | YES (6 rows for all assessment fields) |

All 8 qualifying routes are documented in Section 14. PASS.

---

### Registration Points (FC5): PASS

**7 blueprints enumerated:** `auth`, `intake`, `dashboard`, `submissions`,
`detail`, `status`, `assessments`.

Section 15 "Coordinated Behaviors" heading found. The "Blueprint registration"
row explicitly lists all 7 in registration order. The "Blueprint prefixes" row
confirms url_prefix values. Section 5 (create_app) shows `app.register_blueprint()`
called for all 7. The "Navbar links" row covers all user-facing blueprints.
All 7 blueprints registered. PASS.

---

### Transaction Contracts (FC29): PASS

**6 write functions enumerated** (INSERT/UPDATE operations in model code blocks):
`create_submission`, `update_status`, `toggle_audit_fit`, `create_assessment`,
`update_assessment`, `create_note`.

Section 17 "Transaction Contracts" heading found. All 11 model functions
(including read-only) appear in the table with annotations:

| Function | Annotation |
|----------|-----------|
| `create_submission` | commits internally (`conn.commit()`) |
| `get_submission` | does NOT commit (read-only) |
| `list_submissions` | does NOT commit (read-only) |
| `update_status` | commits internally with BEGIN IMMEDIATE |
| `toggle_audit_fit` | commits internally (`conn.commit()`) |
| `count_by_status` | does NOT commit (read-only) |
| `create_assessment` | commits internally (`conn.commit()`) |
| `get_assessment_by_submission` | does NOT commit (read-only) |
| `update_assessment` | commits internally (`conn.commit()`) |
| `create_note` | commits internally (`conn.commit()`) |
| `list_notes` | does NOT commit (read-only) |

All 6 write functions annotated. PASS.

---

### Authorization Mode (FC35): PASS

**Auth-protected routes identified:** All `/admin/*` routes use `@login_required`
(confirmed by Section 7 auth.py decorator definition and Section 15 "Login redirect" rule).

Section 18 "Authorization Matrix" heading found. All 12 routes from Section 10
appear with mode:

| Route | Mode |
|-------|------|
| GET /intake | public |
| POST /intake | public (rate limited) |
| GET /intake/thank-you | public |
| GET /login | public |
| POST /login | public |
| POST /logout | public |
| GET /admin/ | login-required |
| GET /admin/submissions | login-required |
| GET /admin/submissions/<id> | login-required |
| POST /admin/submissions/<id>/notes | login-required |
| POST /admin/submissions/<id>/status | login-required |
| POST /admin/submissions/<id>/audit-fit | login-required |
| GET/POST /admin/submissions/<id>/assessment | login-required |
| GET /health | public |

Note: Single admin, no role+ownership checks needed (per Section 18 note).
All login-required routes use the `@login_required` decorator; no ownership
field applies. PASS.

---

## Summary

- **Total checks:** 6
- **PASS:** 6
- **FAIL:** 0
- **WARN:** 0
- **N/A:** 0
- **BLOCKED:** 0

STATUS: PASS
