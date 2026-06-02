# Pre-Swarm Spec Completeness Check

**Plan:** film-production-pm-plan.md
**Checked:** 2026-06-02

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | FAIL | 56 model functions checked (all present); endpoint names present; blueprint names present; route paths (60+ URL paths from 13 blueprints) not listed as rows in Export Names table |
| Cross-Boundary Wiring (FC3) | FAIL | 3 cross-boundary function-to-consumer pairs claimed in Export Names table but absent from Wiring table |
| Input Validation (FC4) | FAIL | 27 qualifying routes total; 8 POST routes missing from Validation Prescriptions table |
| Registration Points (FC5) | PASS | 13 blueprints; all registered in create_app() with correct url_prefix; navbar entries prescribed in Coordinated Behaviors |
| Transaction Contracts (FC29) | PASS | 25 write functions annotated; all present in Transaction Contracts table |
| Authorization Mode (FC35) | FAIL | 74 routes in Route Table; 12 GET routes missing from Authorization Matrix |

---

## Details

### Export Names (FC1): FAIL

The Export Names table (line 1103) correctly lists all 56 model functions, all 15 endpoint names, and all 14 blueprint names. However, the table contains no rows for raw URL route paths, which is the fourth required identifier class per the shared-interface spec mandate.

The Route Table defines 74 routes across 13 blueprints. None of their path values (e.g., `/login`, `/<int:project_id>`, `/<int:project_id>/<int:scene_id>/edit`) appear as rows in the Export Names table.

| Item | Location | Issue |
|------|----------|-------|
| Route paths (all 74) | Route Table, sections auth through search | URL paths are the fourth required class in Export Names; zero path rows exist in Export Names table |

**Note:** Endpoint names (`auth.login`, `projects.dashboard`, etc.) are present and satisfy the url_for cross-boundary use case. The path rows would primarily benefit agents that hardcode URL strings rather than using url_for. The omission is a structural completeness gap, not a functional wiring gap.

---

### Cross-Boundary Wiring (FC3): FAIL

Cross-boundary functions are identified by comparing the "Used By" column in the Export Names table against the "Defined By" column. Three producer-to-consumer relationships are claimed in the Export Names table but have no corresponding row in any Cross-Boundary Wiring sub-table.

| Item | Location | Issue |
|------|----------|-------|
| `get_scenes` → callsheets/routes.py | Export Names line 1121 ("callsheets routes"); Wiring line 1219 only covers schedule routes | No wiring row for `scene_models.py → callsheets/routes.py` importing `get_scenes` |
| `get_departments` → crew/routes.py | Export Names line 1137 ("crew routes"); Wiring line 1212 only covers callsheets routes | No wiring row for `department_models.py → crew/routes.py` importing `get_departments` |
| `get_project` → auth/routes.py (decorators) | Export Names line 1116 ("decorators"); `require_project_member` code at line 877 calls `get_project` | No wiring row for `project_models.py → auth/routes.py` importing `get_project` |

**Additional consistency note (out of scope for this checker):** `get_cast_members` appears in the Wiring table as consumed by `reports/routes.py` (line 1236), but the Export Names table (line 1127) only lists "cast routes" as consumer. This is a cross-section contradiction for the consistency checker.

---

### Input Validation (FC4): FAIL

The Input Validation Prescriptions table (line 1258) covers 18 entries. The Route Table contains 74 routes; qualifying routes are all POST/PUT/PATCH/DELETE methods (35 total) plus any GET routes with `<int:` in the path. The 8 POST routes below are qualifying routes absent from the table.

| Item | Location | Issue |
|------|----------|-------|
| `POST /scenes/<pid>/<sid>/edit` (scenes.update) | Route Table, scenes section | Missing from Input Validation Prescriptions; edit fields (scene_number, int_ext, day_night, page_count_eighths) need validation spec |
| `POST /cast/<pid>/<cid>/edit` (cast.update) | Route Table, cast section | Missing from Input Validation Prescriptions; edit fields (name, character_name, cast_id_number) need validation spec |
| `POST /crew/<pid>/<cid>/edit` (crew.update) | Route Table, crew section | Missing from Input Validation Prescriptions; edit fields (name, role_title, department_id) need validation spec |
| `POST /departments/<pid>/<did>/head` (departments.assign_head) | Route Table, departments section | Missing from Input Validation Prescriptions; user_id input must validate user exists in project |
| `POST /locations/<pid>/<lid>/edit` (locations.update) | Route Table, locations section | Missing from Input Validation Prescriptions; edit fields (name, address, permit_status) need validation spec |
| `POST /budget/<pid>/line-items/<iid>/edit` (budget.update_line_item) | Route Table, budget section | Missing from Input Validation Prescriptions; estimated_cents and actual_cents need int parse + >= 0 check |
| `POST /expenses/<pid>/<eid>/approve` (expenses.approve) | Route Table, expenses section | Missing from Input Validation Prescriptions; expense_id must exist and belong to project |
| `POST /call-sheets/<pid>/<csid>/publish` (callsheets.publish) | Route Table, callsheets section | Missing from Input Validation Prescriptions; call_sheet_id must exist and belong to project |

---

### Authorization Matrix (FC35): FAIL

The Authorization Matrix (line 1413) has 50 rows covering 50 of the 74 routes in the Route Table. The 12 missing routes are all GET method routes — primarily form-display pages (GET `/new`) and detail views (GET `/<id>`). All 12 are auth-protected per the Route Table Auth column, so their absence leaves their auth mode unspecified.

| Item | Location | Issue |
|------|----------|-------|
| `GET /scenes/<pid>/new` (scenes.new) | Route Table line 932, auth: login+member+producer/ad | Missing from Authorization Matrix |
| `GET /scenes/<pid>/<sid>/edit` (scenes.edit) | Route Table line 935, auth: login+member+producer/ad | Missing from Authorization Matrix |
| `GET /cast/<pid>/new` (cast.new) | Route Table line 944, auth: login+member+producer/ad | Missing from Authorization Matrix |
| `GET /cast/<pid>/<cid>` (cast.detail) | Route Table line 946, auth: login+member | Missing from Authorization Matrix |
| `GET /crew/<pid>/new` (crew.new) | Route Table line 954, auth: login+member+producer/ad/dept_head | Missing from Authorization Matrix |
| `GET /crew/<pid>/<cid>` (crew.detail) | Route Table line 956, auth: login+member | Missing from Authorization Matrix |
| `GET /locations/<pid>/new` (locations.new) | Route Table line 972, auth: login+member+producer/ad | Missing from Authorization Matrix |
| `GET /locations/<pid>/<id>` (locations.detail) | Route Table line 974, auth: login+member | Missing from Authorization Matrix |
| `GET /schedule/<pid>/day/<date>` (schedule.day_view) | Route Table line 982, auth: login+member | Missing from Authorization Matrix |
| `GET /schedule/<pid>/new` (schedule.new) | Route Table line 983, auth: login+member+producer/ad | Missing from Authorization Matrix |
| `GET /budget/<pid>/line-items/new` (budget.new_line_item) | Route Table line 1004, auth: login+member+producer | Missing from Authorization Matrix |
| `GET /expenses/<pid>/new` (expenses.new) | Route Table line 1013, auth: login+member+producer/dept_head | Missing from Authorization Matrix |

---

## Summary

- **Total checks:** 6
- **PASS:** 2
- **FAIL:** 4
- **WARN:** 0
- **N/A:** 0
- **BLOCKED:** 0

STATUS: FAIL -- 23 omissions found across 4 surfaces
