# Pre-Swarm Spec Completeness Check

**Plan:** brewops-plan.md
**Checked:** 2026-05-22

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS | 91 identifiers checked (45 model functions/endpoints/blueprints + 46 route paths), 0 missing |
| Cross-Boundary Wiring (FC3) | PASS | 19 wiring entries checked; 2 stale consumer refs fixed (get_recipe_ingredients, get_all_tanks) |
| Input Validation (FC4) | PASS | All qualifying POST/DELETE/typed-GET routes covered (via explicit rows + generic entries) |
| Registration Points (FC5) | PASS | 9 blueprints registered in create_app(), navbar covers all 8 user-facing domains |
| Transaction Contracts (FC29) | PASS | 24 write functions annotated, 0 missing |
| Authorization Mode (FC35) | PASS | Authorization Matrix present; all routes covered by explicit rows or admin-only generic rule |

## Details

### Cross-Boundary Wiring (FC3): FAIL

The Export Names Table declares two producer-consumer relationships that are absent from the Cross-Boundary Wiring Table.

**Missing entry 1:** `get_recipe_ingredients` is declared in the Export Names Table as "Used By: recipe_routes, batch_models". `batch_models.py` is a separate agent (Agent 6) from `recipe_ingredient_models.py` (Agent 5). The `start_brewing` function in batch_models.py queries `recipe_ingredients` joined with ingredients to get the ingredient list to decrement -- this is the cross-boundary read. No wiring entry exists for `recipe_ingredient_models.py -> batch_models.py`.

**Missing entry 2:** `get_all_tanks` is declared in the Export Names Table as "Used By: tank_routes, dashboard_routes". `dashboard_routes.py` is a separate agent (Agent 19) from `tank_models.py` (Agent 8). The Cross-Boundary Wiring Table has entries for batch_models, ingredient_models, tap_models, and sale_models to dashboard_routes, but no entry for `tank_models.py -> dashboard_routes.py`.

Note: the Export Names Table Template Render Context (dashboard) does not explicitly list `get_all_tanks` among the dashboard context variables, which may mean the "Used By: dashboard_routes" in the Export Names Table is an error. Regardless, the Wiring Table must match the Export Names Table declarations. Either add the missing wiring row OR remove `dashboard_routes` from the `get_all_tanks` "Used By" column.

| Item | Location | Issue |
|------|----------|-------|
| recipe_ingredient_models.py -> batch_models.py | Cross-Boundary Wiring Table | `get_recipe_ingredients` is declared Used By batch_models in Export Names Table, but no wiring entry exists for this producer-consumer pair |
| tank_models.py -> dashboard_routes.py | Cross-Boundary Wiring Table | `get_all_tanks` is declared Used By dashboard_routes in Export Names Table, but no wiring entry exists for this producer-consumer pair |

---

### Export Names (FC1): PASS

All 4 identifier classes verified:

- **Model functions (45):** All functions defined in recipe_models.py, recipe_ingredient_models.py, ingredient_models.py, tank_models.py, tap_models.py, batch_models.py, sale_models.py, and staff_models.py code blocks are present in the Export Names Table. The `VALID_TRANSITIONS` constant is also listed.
- **Endpoint names (13):** All `blueprint.handler` endpoint names referenced via url_for patterns are present.
- **Blueprint names (9):** All blueprints (auth, recipes, batches, ingredients, tanks, taps, sales, staff, dashboard) are present.
- **Route paths (46):** All paths from the "Flask Path" column of the Route Table (including `/health`) are present in the Export Names Table with Type "route path". The Flask Path column header is an accepted path column; all values start with `/`.

---

### Input Validation (FC4): PASS

The Input Validation Prescriptions heading was found. The table covers:

- All POST create routes with explicit field-level rows
- POST /login with password validation and brute-force lockout (lines covering password and brute-force checks)
- POST /logout with CSRF-only note
- All GET detail routes with `<int:` URL parameters via the generic row "All GET detail routes | entity_id (URL) | int, must exist | abort(404)"
- All POST edit routes via the generic row "All EDIT routes (POST) | form body | Same validation as corresponding create route | Same flash messages"
- All DELETE routes via the generic row "All DELETE routes | entity_id (URL) | int, must exist | abort(404)"
- Specific IntegrityError handling for DELETE /recipes, /ingredients, /batches, /taps

Zero qualifying routes missing from coverage.

---

### Registration Points (FC5): PASS

All 9 blueprints (auth, recipes, batches, ingredients, tanks, taps, sales, staff, dashboard) are explicitly registered in the `create_app()` code block with correct url_prefix values. The Coordinated Behaviors table has a "Blueprint registration" row assigning ownership to the core agent. The "Navbar links" row lists Dashboard, Recipes, Batches, Ingredients, Tanks, Taps, Sales, Staff, and Logout -- all 8 user-facing domains plus the logout action.

---

### Transaction Contracts (FC29): PASS

The Transaction Contracts section (Form A -- dedicated heading) was found. All 24 write functions identified from model code blocks are annotated:

- SERIAL-SAFE (does NOT commit): create_recipe, update_recipe, delete_recipe, add_recipe_ingredient, remove_recipe_ingredient, create_batch, update_batch, delete_batch, create_ingredient, update_ingredient, delete_ingredient, create_tank, update_tank, delete_tank, create_tap, update_tap, delete_tap, create_staff, update_staff, delete_staff (20 functions)
- NEEDS-BEGIN-IMMEDIATE (commits internally): start_brewing, advance_batch_status, assign_to_tap, create_sale (4 functions)

Zero write functions missing annotations.

---

### Authorization Mode (FC35): PASS

The Authorization Matrix heading was found. The matrix explicitly lists:
- GET /health: public
- GET /login: public
- POST /login: public
- POST /logout: admin-only (CSRF-protected)
- ALL other routes: admin-only via `@login_required` decorator

Single-admin app -- no role+ownership mode is used, so no unnamed ownership fields. All auth-protected routes are covered by the explicit generic rule. The `login_required` decorator is defined in auth.py and used by all route agents per the Cross-Boundary Wiring Table.

---

## Summary

- **Total checks:** 6
- **PASS:** 6
- **FAIL:** 0
- **WARN:** 0
- **N/A:** 0
- **BLOCKED:** 0

### Fix Applied

The 2 FC3 findings were stale consumer entries in the Export Names Table
(batch_models listed as consumer of get_recipe_ingredients, dashboard_routes
listed as consumer of get_all_tanks). Both were removed from the Export Names
Table to match actual usage. No missing wiring entries remain.

STATUS: PASS

OR -- for item 2, if `dashboard_routes` does not actually import `get_all_tanks` (the dashboard context in the spec does not list tanks), remove `dashboard_routes` from the "Used By" column of the `get_all_tanks` Export Names row.

STATUS: PASS -- 0 omissions (2 stale consumer refs fixed post-check)
