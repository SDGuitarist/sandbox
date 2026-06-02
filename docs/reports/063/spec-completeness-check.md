# Pre-Swarm Spec Completeness Check

**Plan:** film-production-pm-plan.md
**Checked:** 2026-06-02

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS | 56 model functions, 15 endpoint names, 14 blueprint names checked; all present. Route paths intentionally omitted (agents use url_for). |
| Cross-Boundary Wiring (FC3) | FAIL | 4 cross-boundary functions in Export Names table absent from Wiring table |
| Input Validation (FC4) | FAIL | 27 qualifying POST routes checked; 2 missing from Validation Prescriptions table |
| Registration Points (FC5) | PASS | 13 blueprints; all registered in create_app() with correct url_prefix; navbar entries prescribed in Coordinated Behaviors |
| Transaction Contracts (FC29) | PASS | 25 write functions; all annotated in Transaction Contracts table |
| Authorization Mode (FC35) | PASS | 74 routes checked; all present in Authorization Matrix |

---

## Details

### Cross-Boundary Wiring (FC3): FAIL

The Export Names table identifies 4 functions where the producer module belongs to a different agent than the consumer module, but no corresponding row exists in any sub-table of the Cross-Boundary Wiring Table.

**`get_active_project`:** Defined by `app/models/project_models.py` (Agent 3: projects). Used by `app/__init__.py` (Agent 1: scaffold) in the index route (`from app.models.project_models import get_active_project` at line 99). This is a cross-agent import with no wiring row.

**`add_cast_to_scene`, `remove_cast_from_scene`, `get_scene_cast`:** All three are defined by `app/models/cast_models.py` (Agent 5: cast). The Export Names table lists their consumer as "scenes routes" (`app/blueprints/scenes/routes.py`, Agent 4: scenes). None of the nine wiring sub-tables contains a row for `cast_models.py → scenes/routes.py`.

| Item | Location | Issue |
|------|----------|-------|
| `get_active_project` | Export Names line 1117 ("Used By: app factory (index route)") | No wiring row for `project_models.py → app/__init__.py` |
| `add_cast_to_scene` | Export Names line 1130 ("Used By: scenes routes") | No wiring row for `cast_models.py → scenes/routes.py` |
| `remove_cast_from_scene` | Export Names line 1131 ("Used By: scenes routes") | No wiring row for `cast_models.py → scenes/routes.py` |
| `get_scene_cast` | Export Names line 1132 ("Used By: scenes routes") | No wiring row for `cast_models.py → scenes/routes.py` |

---

### Input Validation (FC4): FAIL

The Input Validation Prescriptions table (line 1272) covers 26 entries (all 8 previously missing routes were added). However, 2 qualifying POST routes remain absent.

**`POST /auth/logout`:** Listed in the Route Table (auth section, line 914). Method is POST, so it qualifies. No row in the Input Validation Prescriptions table. The handler takes no body fields beyond the CSRF token, but the pattern for such routes (see `POST /expenses/<pid>/<eid>/delete` at line 1290 with Input `--`) should be applied here too.

**`POST /schedule/<pid>/<eid>/delete`:** Listed in the Route Table (schedule section, line 986). Method is POST. No row in the Input Validation Prescriptions table. The only input is the URL-embedded `entry_id` (int type-converted). Same `--` / existence-check pattern applies.

| Item | Location | Issue |
|------|----------|-------|
| `POST /auth/logout` | Route Table, auth section (line 914) | Missing from Input Validation Prescriptions; no body input beyond CSRF — add row with Input `--`, Validation `login_required`, Error Response `redirect to login` |
| `POST /schedule/<pid>/<eid>/delete` | Route Table, schedule section (line 986) | Missing from Input Validation Prescriptions; entry_id is URL param (int type-converted); add row with Input `--`, Validation `entry.project_id == pid`, Error Response `404` |

---

## Summary

- **Total checks:** 6
- **PASS:** 4
- **FAIL:** 2
- **WARN:** 0
- **N/A:** 0
- **BLOCKED:** 0

STATUS: FAIL -- 6 omissions found across 2 surfaces
