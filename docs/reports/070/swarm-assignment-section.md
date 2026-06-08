## Swarm Agent Assignment

**Total agents:** 16
**Total files:** 94
**Validation:** No file appears in multiple assignments. All paths relative to project root. No absolute paths. No `..` components.

**Shared Interface Spec:** Every agent reads the full plan at `docs/plans/film-production-pm-plan.md`. That document IS the shared interface spec — all sections (Export Names Table, Orchestration Entrypoints, Cross-Boundary Wiring Table, Input Validation Prescriptions, Coordinated Behaviors, Transaction Contracts, Authorization Matrix) are authoritative for all agents.

---

### Agent: scaffold
**Branch:** swarm-070-scaffold
**Files:**
- `app/__init__.py`
- `app/templates/base.html`
- `app/static/css/style.css`
- `app/static/js/app.js`
- `run.py`
- `requirements.txt`
- `.gitignore`

**Responsibility:** App factory with blueprint registration, security headers, template filters, base HTML template with Bootstrap 5 dark theme and navbar, shared CSS (strip colors), and shared JS utilities (CSRF token extraction).

---

### Agent: auth
**Branch:** swarm-070-auth
**Files:**
- `app/blueprints/auth/__init__.py`
- `app/blueprints/auth/routes.py`
- `app/models/auth_models.py`
- `app/templates/auth/login.html`
- `app/templates/auth/register.html`

**Responsibility:** Authentication routes (login, register, logout), auth decorators (`login_required`, `require_project_member`, `require_role`) exported for all blueprints, and auth model functions (`create_user`, `authenticate`, `get_user`).

---

### Agent: projects
**Branch:** swarm-070-projects
**Files:**
- `app/blueprints/projects/__init__.py`
- `app/blueprints/projects/routes.py`
- `app/models/project_models.py`
- `app/templates/projects/dashboard.html`
- `app/templates/projects/new.html`
- `app/templates/projects/edit.html`

**Responsibility:** Project CRUD routes, dashboard with stats, phase transition endpoint, and project model functions (`create_project`, `get_project`, `get_active_project`, `get_project_stats`, `transition_project_phase`, `VALID_PHASE_TRANSITIONS`).

---

### Agent: scenes
**Branch:** swarm-070-scenes
**Files:**
- `app/blueprints/scenes/__init__.py`
- `app/blueprints/scenes/routes.py`
- `app/models/scene_models.py`
- `app/templates/scenes/list.html`
- `app/templates/scenes/new.html`
- `app/templates/scenes/detail.html`
- `app/templates/scenes/edit.html`

**Responsibility:** Scene CRUD routes, element tagging, status transitions, cast assignment on scenes, scene model functions (`create_scene`, `get_scenes`, `get_scene`, `get_scenes_by_ids`, `transition_scene_status`, `update_scene`, `VALID_SCENE_TRANSITIONS`), and FTS5 index calls for scenes.

---

### Agent: cast
**Branch:** swarm-070-cast
**Files:**
- `app/blueprints/cast/__init__.py`
- `app/blueprints/cast/routes.py`
- `app/models/cast_models.py`
- `app/templates/cast/list.html`
- `app/templates/cast/new.html`
- `app/templates/cast/detail.html`

**Responsibility:** Cast member CRUD routes and cast model functions (`create_cast_member`, `get_cast_members`, `get_cast_member`, `get_cast_for_scenes`, `add_cast_to_scene`, `remove_cast_from_scene`, `get_scene_cast`) including the cross-boundary `get_cast_for_scenes` consumed by callsheet_models.

---

### Agent: crew
**Branch:** swarm-070-crew
**Files:**
- `app/blueprints/crew/__init__.py`
- `app/blueprints/crew/routes.py`
- `app/models/crew_models.py`
- `app/templates/crew/list.html`
- `app/templates/crew/new.html`
- `app/templates/crew/detail.html`

**Responsibility:** Crew member CRUD routes with department-head ownership enforcement, crew model functions (`create_crew_member`, `get_crew_members`, `get_crew_by_department`, `get_crew_member`) including the cross-boundary `get_crew_by_department` consumed by callsheets routes.

---

### Agent: departments
**Branch:** swarm-070-departments
**Files:**
- `app/blueprints/departments/__init__.py`
- `app/blueprints/departments/routes.py`
- `app/models/department_models.py`
- `app/templates/departments/list.html`
- `app/templates/departments/detail.html`

**Responsibility:** Department list, detail, and head-assignment routes; department model functions (`get_departments`, `get_department`, `assign_department_head`) including the cross-boundary `get_departments` consumed by callsheets, crew, and expenses routes.

---

### Agent: locations
**Branch:** swarm-070-locations
**Files:**
- `app/blueprints/locations/__init__.py`
- `app/blueprints/locations/routes.py`
- `app/models/location_models.py`
- `app/templates/locations/list.html`
- `app/templates/locations/new.html`
- `app/templates/locations/detail.html`

**Responsibility:** Location CRUD routes and location model functions (`create_location`, `get_locations`, `get_location`) including the cross-boundary `get_location` consumed by callsheet_models and `get_locations` consumed by scenes and schedule routes.

---

### Agent: schedule
**Branch:** swarm-070-schedule
**Files:**
- `app/blueprints/schedule/__init__.py`
- `app/blueprints/schedule/routes.py`
- `app/models/schedule_models.py`
- `app/templates/schedule/index.html`
- `app/templates/schedule/day.html`
- `app/templates/schedule/new.html`
- `app/static/js/schedule.js`

**Responsibility:** Schedule CRUD routes, SortableJS drag-and-drop reorder endpoint (JSON), schedule model functions (`create_schedule_entry`, `get_schedule_entries`, `get_shoot_dates`, `reorder_schedule`, `delete_schedule_entry`) including the cross-boundary `get_schedule_entries` and `get_shoot_dates` consumed by callsheet_models and reports routes.

---

### Agent: callsheets
**Branch:** swarm-070-callsheets
**Files:**
- `app/blueprints/callsheets/__init__.py`
- `app/blueprints/callsheets/routes.py`
- `app/models/callsheet_models.py`
- `app/templates/callsheets/list.html`
- `app/templates/callsheets/detail.html`

**Responsibility:** Call sheet generation, detail view, and publish routes; callsheet model functions (`generate_call_sheet`, `get_call_sheet`, `get_call_sheet_scenes`, `get_call_sheet_cast`, `publish_call_sheet`) implementing the prescribed generation algorithm with 6 cross-boundary imports.

---

### Agent: budget
**Branch:** swarm-070-budget
**Files:**
- `app/blueprints/budget/__init__.py`
- `app/blueprints/budget/routes.py`
- `app/models/budget_models.py`
- `app/templates/budget/index.html`
- `app/templates/budget/top_sheet.html`
- `app/templates/budget/new_line_item.html`

**Responsibility:** Budget overview, top sheet, department allocation, and line item routes (producer-only); budget model functions (`get_budget_summary`, `get_budget_categories`, `get_department_allocation`, `allocate_budget`, `create_line_item`, `update_line_item`).

---

### Agent: expenses
**Branch:** swarm-070-expenses
**Files:**
- `app/blueprints/expenses/__init__.py`
- `app/blueprints/expenses/routes.py`
- `app/models/expense_models.py`
- `app/templates/expenses/list.html`
- `app/templates/expenses/new.html`

**Responsibility:** Expense CRUD and approval routes with department-head ownership enforcement; expense model functions (`create_expense`, `delete_expense`, `approve_expense`, `get_expenses`, `get_expense`) with atomic overspend protection and spent_cents rollback.

---

### Agent: reports
**Branch:** swarm-070-reports
**Files:**
- `app/blueprints/reports/__init__.py`
- `app/blueprints/reports/routes.py`
- `app/models/report_models.py`
- `app/templates/reports/index.html`
- `app/templates/reports/budget_summary.html`
- `app/templates/reports/dood.html`
- `app/templates/reports/progress.html`

**Responsibility:** Reports index, budget summary, DOOD grid (prescribed algorithm), and production progress routes; report model functions (`get_dood_grid`, `get_production_progress`).

---

### Agent: search
**Branch:** swarm-070-search
**Files:**
- `app/blueprints/search/__init__.py`
- `app/blueprints/search/routes.py`
- `app/models/search_models.py`
- `app/templates/search/results.html`

**Responsibility:** FTS5 full-text search page with input sanitization; search model functions (`search`, `index_entity`, `remove_entity`) — `index_entity`/`remove_entity` are consumed by scenes, cast, crew, and locations routes (FC52 single-writer pattern).

---

### Agent: database
**Branch:** swarm-070-database
**Files:**
- `schema.sql`
- `app/database.py`
- `app/models/__init__.py`

**Responsibility:** SQLite schema (`schema.sql`), database connection module (`app/database.py` — `get_db`, `close_db`, `init_db`, `seed_data`, `init_app`), and models package init (`app/models/__init__.py`).

---

### Agent: tests
**Branch:** swarm-070-tests
**Files:**
- `test_smoke.py`
- `tests/__init__.py`
- `tests/test_critical_flows.py`
- `tests/conftest.py`

**Responsibility:** FC8-compliant smoke tests (`test_smoke.py`), 10 critical-flow tests per spec (`tests/test_critical_flows.py`), and test fixtures (`tests/conftest.py`).

---

STATUS: PASS
