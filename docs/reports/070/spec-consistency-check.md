STATUS: PASS

# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/film-production-pm-plan.md
**Checked:** 2026-06-08 (retry after 3 fixes)

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs Route | `department_head` (schema CHECK, Auth Matrix) | Route Table auth columns for crew + expenses | PASS | All Route Table rows now use `department_head` (lines 1026-1029, 1084-1087). Prior FAIL resolved. |
| 2 | Export Names vs File Assignment | `get_expense` in Model Functions + Export Names Table | Agent 12 expense_models.py purpose cell (line 2190) | PASS | Line 2190 now reads `create_expense, delete_expense, approve_expense, get_expenses, get_expense (ownership/IDOR check)`. Prior FAIL resolved. |
| 3 | Input Validation vs Money Convention | `total_budget_cents` in Input Validation table (line 1384) | FC55 money convention (lines 1409-1417) | PASS | FC55 clarifying note now explicitly enumerates `amount_cents`, `total_budget_cents`, `estimated_cents`, `actual_cents` as parsed-value references -- NOT form field names. The corresponding form fields (no `_cents` suffix) are also enumerated. Prior FAIL resolved. |
| 4 | Cross-Boundary Wiring vs Orchestration Entrypoints | `get_scenes_by_ids` keys in Wiring Table (line 1304): `scene_number, int_ext, day_night, page_count_eighths` | Orchestration Entrypoints (line 1283) and Model Functions (line 651): `id, scene_number, description, int_ext, day_night, page_count_eighths` | WARN | Wiring Table row omits `id` and `description`. The Orchestration Entrypoints table is AUTHORITATIVE. No new change -- pre-existing WARN, retained per instructions. |
| 5 | Model Functions vs Template Render Context | `get_budget_summary` returns dict with `categories` key (line 779) | Template Render Context for budget/index.html passes `categories=get_budget_categories(conn, project_id)` as a separate variable (line 1134) | WARN | Two sources of `categories` data could shadow each other in template scope. No explicit contradiction on what each returns. Pre-existing WARN, retained per instructions. |
| 6 | Cross-Boundary Wiring vs Orchestration Entrypoints | `get_location` keys in Wiring Table (line 1303): `name, address, nearest_hospital` (3 keys) | Orchestration Entrypoints (line 1284) and Model Functions (line 730): `id, name, address, contact_name, contact_phone, permit_status, nearest_hospital` (7 keys) | WARN | Same pattern as WARN 4. Wiring Table lists a subset of keys; Orchestration Entrypoints table is AUTHORITATIVE (7 keys). Callsheet_models consuming only the 3-key listing could miss `contact_name`, `contact_phone`, `permit_status` fields. |
| 7 | SQL Types vs App-Layer Types | All `*_cents` fields: `INTEGER` in SQL | `int` in Python model signatures and Input Validation | PASS | Consistent throughout. |
| 8 | SQL Types vs App-Layer Types | `page_count_eighths INTEGER` in SQL | `page_count_eighths` as `int` in model signatures and Input Validation | PASS | Consistent. |
| 9 | SQL Types vs App-Layer Types | `cast_id_number INTEGER` in SQL | Input Validation: `cast_id int 1-99` | PASS | Consistent. |
| 10 | Route Methods vs Route Table | All POST routes in Route Table | Input Validation Prescriptions | PASS | Every POST route in the Route Table has a corresponding Input Validation entry. |
| 11 | Export Names vs Import References | `get_schedule_entries` signature across all sections | Orchestration Entrypoints, Model Functions, Cross-Boundary Wiring | PASS | All three sections agree: `get_schedule_entries(conn, project_id, shoot_date) -> list[dict]` with same 11 keys. |
| 12 | Export Names vs Import References | `get_cast_for_scenes` signature | Orchestration Entrypoints vs Model Functions | PASS | Both: `get_cast_for_scenes(conn, scene_ids) -> list[dict]` with keys id, name, character_name, cast_id_number. |
| 13 | Export Names vs Import References | `get_location` full signature | Orchestration Entrypoints vs Model Functions | PASS | Both: `get_location(conn, location_id) -> dict | None` with 7 keys including `permit_status`. Wiring Table abbreviates but Orchestration Entrypoints is authoritative. |
| 14 | Export Names vs Import References | `get_crew_by_department` shape | Orchestration Entrypoints vs Model Functions | PASS | Both: `list[dict]` with `{department_name, members: [{id, name, role_title, phone}]}`. |
| 15 | Export Names vs Import References | `get_departments` keys | Orchestration Entrypoints vs Model Functions | PASS | Both: keys id, name, head_id, head_name. |
| 16 | Export Names vs Import References | `create_expense` arity | Model Functions vs usage snippet in F-H6 section (line 1708) | PASS | Both: `(conn, project_id, department_id, amount_cents, vendor, description, expense_date, category_id, created_by)`. |
| 17 | Schema vs Route Parameter Names | Role strings in `require_role(...)` calls | Schema CHECK constraint `role IN ('producer','ad','department_head','crew_member')` | PASS | All role strings in Auth Decorators, Auth Matrix, and Route Table use `department_head` (not `dept_head`). Consistent with schema. |
| 18 | FK ON DELETE vs Function Behavior | Delete functions in Transaction Contracts | FK constraints in schema | PASS | `delete_schedule_entry` and `delete_expense` have no RESTRICT children that would cause undocumented IntegrityErrors. No delete functions exist for users, projects, or departments (the tables with RESTRICT children). No contradiction. |
| 19 | Mock/Fixture vs Schema | `seed_data()` inserts for users, projects, project_members, departments, budget_categories | Schema table definitions | PASS | All seed inserts match column names and types. `departments` uses `(project_id, name)` matching schema. `budget_categories` uses `(project_id, account_number, name, parent_group)` matching schema. `projects` includes `total_budget_cents` matching schema. |
| 20 | Decorator Stacking Order | Auth section: `login_required` → `require_project_member` → `require_role` (lines 966-970) | Used consistently in Auth Matrix and Coordinated Behaviors | PASS | Stacking order defined once and referenced consistently. No contradiction. |
| 21 | Transition Maps | `VALID_PHASE_TRANSITIONS` defined in `project_models.py` | Used by `transition_project_phase()` and `POST /projects/<id>/phase` (same agent, no cross-boundary) | PASS | No cross-boundary import needed. No contradiction. |
| 22 | Transition Maps | `VALID_SCENE_TRANSITIONS` defined in `scene_models.py` | Used by `transition_scene_status()` and `POST /scenes/<pid>/<sid>/status` (same agent, no cross-boundary) | PASS | No cross-boundary import needed. No contradiction. |
| 23 | SortableJS Contract | `request.json['order']`, `request.json['shoot_date']` in Python route | `JSON.stringify({order: ids, shoot_date: currentDate})` in JS (line 1759) | PASS | Key names match exactly across HTML/JS/Python. |
| 24 | Transaction Contracts vs Model Functions | `assign_department_head`: model docstring says "commits internally" (line 717) | Transaction Contracts table (line 1505): BEGIN IMMEDIATE / YES | PASS | Consistent. |
| 25 | Cross-Boundary Wiring Completeness | All 10 Orchestration Entrypoints | Cross-Boundary Wiring Table consumers | PASS | All 10 orchestration entrypoints have at least one declared consumer in the Wiring Table. |
| 26 | Authorization Matrix vs Route Table | `GET /scenes/<pid>/new`: Route Table auth `login+member+producer/ad`, Auth Matrix `producer, ad` | Consistent across both sections (lines 1004, 1605) | PASS | Consistent. |
| 27 | Money Convention Consistency | FC55 form field names: `amount`, `estimated`, `actual`, `total_budget` | Input Validation table `_cents`-suffixed references now clarified as parsed values, not form fields | PASS | FC55 clarifying note covers all four `*_cents` references in the Input Validation table. No ambiguity remains. |
| 28 | Export Names vs File Assignment | Agent 3 `project_models.py` purpose cell lists `create_project, get_project, get_active_project, get_project_stats, transition_project_phase` | Model Functions section defines the same 5 functions | PASS | Complete match. |
| 29 | Schema vs App-Layer Types | `autocommit=True` in `sqlite3.connect()` | Explicit `conn.execute('BEGIN IMMEDIATE')` / `COMMIT` / `ROLLBACK` in all write functions | PASS | Python 3.12+ `autocommit=True` + explicit transaction control is internally consistent. DB agent owns `database.py`; all model agents use explicit BEGIN/COMMIT/ROLLBACK. No contradiction. |

## Detailed Analysis of Retained WARNs

### WARN 4 (pre-existing): `get_scenes_by_ids` key enumeration in Cross-Boundary Wiring Table

The Wiring Table row (line 1304) lists only `scene_number, int_ext, day_night, page_count_eighths`. The Orchestration Entrypoints table (line 1283) and Model Functions section (line 651) both include `id` and `description` as well. Agents reading the Wiring Table alone could implement `get_scenes_by_ids` without `id` (breaking any call-sheet scene lookup by ID) or `description` (breaking call sheet scene text). The Orchestration Entrypoints table is the authoritative source per spec preamble.

### WARN 5 (pre-existing): `get_budget_summary` `categories` key vs separate `get_budget_categories` variable

`get_budget_summary` returns `{total_estimated_cents, total_actual_cents, variance_cents, categories}`. The render context for `budget/index.html` passes both `summary=get_budget_summary(...)` AND `categories=get_budget_categories(...)` as separate template variables. In Jinja2 the `categories` top-level variable would shadow `summary.categories` if both are accessed as `{{ categories }}`. No explicit contradiction on what each returns, but agents could implement the template inconsistently depending on which `categories` source they use.

### WARN 6 (new): `get_location` key enumeration in Cross-Boundary Wiring Table

Same pattern as WARN 4. Cross-Boundary Wiring Table (line 1303) abbreviates the return to `dict with name, address, nearest_hospital`. The authoritative Orchestration Entrypoints table (line 1284) lists 7 keys: `id, name, address, contact_name, contact_phone, permit_status, nearest_hospital`. An agent implementing `callsheet_models.py` by reading only the Wiring Table could omit `contact_name`, `contact_phone`, and `permit_status` from the call sheet view.

## Summary

- **Total checks:** 29
- **PASS:** 26
- **FAIL:** 0
- **WARN:** 3
- **N/A (section absent):** 0

All 3 prior FAILs are resolved. Zero new FAILs. Three WARNs carried forward (2 pre-existing, 1 new): all are incomplete key enumerations in the Wiring Table where the Orchestration Entrypoints table is the authoritative source. These are non-blocking per the retry instructions.
