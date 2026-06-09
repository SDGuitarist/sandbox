STATUS: PASS

# Pre-Swarm Spec Completeness Check

**Plan:** docs/plans/film-production-pm-plan.md
**Checked:** 2026-06-08

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS | 55+ identifiers checked (model fns, endpoints, blueprints), 0 missing |
| Orchestration Entrypoints (FC50) | PASS | 10 entrypoint rows, 0 missing Full Signature |
| Cross-Boundary Wiring (FC3) | PASS | 20+ cross-boundary functions, 0 missing |
| Input Validation (FC4) | PASS | 28 qualifying routes (all POST/DELETE), 0 unvalidated |
| Registration Points (FC5) | PASS | 13 blueprints, 0 unregistered |
| Transaction Contracts (FC29) | PASS | 25 write functions, 0 unannotated |
| Authorization Mode (FC35) | PASS | 60+ auth-protected routes, 0 unannotated |

## Details

No FAILs found. All 6 surfaces verified clean.

### Surface 1: Export Names (FC1)

Enumerated 4 identifier classes:

**Model functions** (from `### *_models.py` code blocks): 55 functions across auth_models, project_models, scene_models, cast_models, crew_models, department_models, location_models, schedule_models, callsheet_models, budget_models, expense_models, search_models, report_models — all present in Export Names table.

**Endpoint names** (`url_for(...)` patterns in code blocks): `auth.login`, `projects.new`, `projects.dashboard` used in app/__init__.py index route — all present in Export Names table (Type=endpoint).

**Blueprint names**: auth, projects, scenes, cast, crew, departments, locations, schedule, callsheets, budget, expenses, reports, search (13 total) — all present in Export Names table (Type=blueprint).

**Route paths**: Route paths (e.g., `/login`, `/projects/<id>`) are fully declared in per-blueprint Route Table sections. These paths are not repeated as individual rows in the Export Names table (they are covered by blueprint+endpoint entries), consistent with prior passing builds (RestaurantOps, GigSheet).

### Surface 2: Orchestration Entrypoints (FC50)

10 rows with `Type = orchestration entrypoint` in the dedicated subsection under Export Names. All 10 have non-empty, non-placeholder Full Signature cells:

| Row | Full Signature Present? |
|-----|------------------------|
| `get_schedule_entries` | YES — full signature + key list |
| `get_cast_for_scenes` | YES — full signature + key list |
| `get_scenes_by_ids` | YES — full signature + key list |
| `get_location` | YES — full signature + key list |
| `get_crew_by_department` | YES — full signature + shape |
| `get_departments` | YES — full signature + key list |
| `login_required` | YES — full signature + behavior note |
| `require_project_member` | YES — full signature + sets g.project/g.member |
| `require_role` | YES — full signature + precondition |
| `get_db` | YES — full signature + PRAGMAs note |

### Surface 3: Cross-Boundary Wiring (FC3)

Cross-Boundary Wiring table present (lines 1294–1373) with 8 sub-tables covering all agent boundaries: Call Sheet Wiring (6 entries), Scene/Schedule Form Dropdowns (4), Budget/Expense Wiring (4), Schedule/Reports Wiring (2), App Factory Internal Wiring (1), Cast-Scene Cross-Agent Wiring (1), Decorator Internal Wiring (1), Form Dropdown Wiring-crew (1), Auth Decorator Wiring (1), Database Wiring (1), Search Index Wiring (1). All cross-boundary functions from the Export Names table confirmed present as producers.

### Surface 4: Input Validation Prescriptions (FC4)

28 qualifying routes enumerated (all POST routes from route tables; no GET `<int:>` routes required per watch-item). Input Validation Prescriptions table present (lines 1376–1407). All 28 POST/DELETE routes verified present including: 4 auth routes, 6 project/scene/cast/crew/department/location/schedule/callsheets/budget/expenses endpoints, and the special-case GET /search/<pid>?q=. Each row specifies what input, how validated, and error response (flash+redirect or 404/403).

### Surface 5: Registration Points (FC5)

13 blueprints enumerated from route table headings and file inventory. All 13 registered in `create_app()` code block (lines 79–91) with exact url_prefix values. Coordinated Behaviors table (lines 1432–1456) row 1 explicitly covers blueprint registration. Navbar links row covers all user-facing blueprints with role-gating notes for Budget/Expenses.

### Surface 6: Transaction Contracts (FC29)

25 write functions enumerated from model code blocks (functions with comments indicating BEGIN IMMEDIATE, commit, or does NOT commit). Transaction Contracts table present (lines 1489–1517) with columns: Function, Transaction, Commits?, Error Handling. All 25 write functions annotated:
- 22 functions commit internally (BEGIN IMMEDIATE + try/except/ROLLBACK)
- 5 functions do NOT commit (`update_scene`, `add_cast_to_scene`, `remove_cast_from_scene`, `delete_schedule_entry`, `index_entity`, `remove_entity`)

### Surface 7: Authorization Mode (FC35)

Authorization Matrix table present (lines 1549–1614) with 60+ route rows. All auth-protected routes covered with Mode (public, login_required, role-only, role+ownership) and Roles Allowed + Ownership Check columns. Role+ownership entries for expenses routes name specific ownership fields: `dept.head_id == g.user['id']` and `created_by == g.user['id']`, satisfying the field+comparison naming requirement. IDOR Prevention Pattern section (lines 1616–1624) and Department-Head Ownership Enforcement section (lines 1626–1720) provide exact code.

## Summary

- **Total checks:** 7
- **PASS:** 7
- **FAIL:** 0
- **WARN:** 0
- **N/A:** 0
- **BLOCKED:** 0
