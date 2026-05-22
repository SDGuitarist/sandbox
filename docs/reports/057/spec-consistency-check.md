# Pre-Swarm Spec Consistency Check

**Plan:** brewops-plan.md
**Checked:** 2026-05-22

STATUS: FAIL -- 9 contradictions found

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Export vs Import | Export Names: `get_recipe` Used By `batch_routes` | Cross-Boundary Wiring: batch_routes imports only `get_all_recipes` from recipe_models | FAIL | `get_recipe` appears as a batch_routes consumer in Export Names Table but is absent from the batch_routes import line in Cross-Boundary Wiring Table |
| 2 | Export vs Import | Export Names: `get_all_sales` Used By `dashboard_routes` | Cross-Boundary Wiring: dashboard_routes imports only `get_today_sales_total` from sale_models | FAIL | `get_all_sales` is listed as a dashboard_routes consumer in Export Names but is not in the Cross-Boundary Wiring import for dashboard_routes |
| 3 | Export vs Import | Export Names: `get_tap` Used By `sale_routes` | Cross-Boundary Wiring: sale_routes imports only `get_all_taps` from tap_models | FAIL | `get_tap` is listed as consumed by sale_routes in Export Names but the Cross-Boundary Wiring import for sale_routes omits it |
| 4 | Export vs Template Context | Export Names: `get_all_batches` Used By `dashboard_routes` | Template Render Context for dashboard uses only `get_batches_by_status` (3 calls) | FAIL | `get_all_batches` appears in the Export Names consumer list and in the Cross-Boundary Wiring import, but the Template Render Context never calls it. One of these three sections is wrong: either dashboard does not need `get_all_batches` (remove from Export Names + Wiring) or the Template Render Context is incomplete |
| 5 | File Assignment Boundaries vs Agent Detail | File Assignment Boundaries table (row 1): `app/__init__.py, app/db.py, app/auth.py, app/filters.py, app/models/__init__.py, schema.sql, requirements.txt, .gitignore, run.py` | Agent 1 (core) detailed Files section also lists `app/routes/__init__.py` | FAIL | `app/routes/__init__.py` is present in the Agent 1 detailed brief but absent from the File Assignment Boundaries table. This file will either be built by Agent 1 (boundary table is wrong) or not built at all (detailed brief is wrong) |
| 6 | ON DELETE vs Agent Responsibility (delete_ingredient) | `recipe_ingredients.ingredient_id REFERENCES ingredients(id) ON DELETE RESTRICT` -- delete_ingredient WILL raise IntegrityError if ingredient is in any recipe | Agent 14 (ingredient_routes) brief: "IntegrityError catch for unique name constraint" -- no mention of delete IntegrityError | FAIL | Agent 14 is not told to catch IntegrityError on DELETE /ingredients/<id>/delete. With RESTRICT in place, deleting an ingredient that is referenced by any recipe will raise sqlite3.IntegrityError. The Input Validation Prescriptions also do not prescribe this catch |
| 7 | ON DELETE vs Agent Responsibility (delete_tap) | `sales.tap_id REFERENCES taps(id) ON DELETE RESTRICT` -- delete_tap WILL raise IntegrityError if tap has any sales | Agent 16 (tap_routes) brief: "IntegrityError catch for unique name/position constraints" -- no mention of delete IntegrityError | FAIL | Agent 16 is not told to catch IntegrityError on DELETE /taps/<id>/delete. With RESTRICT in place, deleting a tap with sales records will raise sqlite3.IntegrityError. The Input Validation Prescriptions do not prescribe this catch |
| 8 | ON DELETE vs Agent Responsibility (delete_recipe) | `batches.recipe_id REFERENCES recipes(id) ON DELETE RESTRICT` (and recipe_ingredients.recipe_id ON DELETE CASCADE -- mix). delete_recipe CAN raise IntegrityError if the recipe is used in any batch | Agent 12 (recipe_routes) brief describes input validation and templates; no mention of IntegrityError catch on DELETE /recipes/<id>/delete | FAIL | Agent 12 is not told to catch IntegrityError on the recipe delete route. If a recipe has associated batches (RESTRICT child), the delete raises sqlite3.IntegrityError. The Input Validation Prescriptions do not prescribe this catch |
| 9 | ON DELETE vs Agent Responsibility (delete_batch) | `sales.batch_id REFERENCES batches(id) ON DELETE RESTRICT` (and taps.batch_id ON DELETE SET NULL -- mix). delete_batch CAN raise IntegrityError if the batch has any sales | Agent 13 (batch_routes) brief mentions only NEEDS-BEGIN-IMMEDIATE error handling via return strings; no mention of IntegrityError catch on DELETE /batches/<id>/delete | FAIL | Agent 13 is not told to catch IntegrityError on the batch delete route. If a batch has sales records (RESTRICT child), delete raises sqlite3.IntegrityError. The Input Validation Prescriptions do not prescribe this catch |
| 10 | Export vs Import | Export Names: `get_batch` Used By `batch_routes, tap_routes, sale_routes` | Cross-Boundary Wiring: sale_routes imports have no entry for `get_batch` from batch_models | WARN | `get_batch` is declared as consumed by sale_routes in Export Names but is not in the Cross-Boundary Wiring import. If sale_routes validates the tap's batch assignment via `get_all_taps` filter or the model internal check, `get_batch` may not be needed -- but the Export Names table claims it is |
| 11 | ON DELETE vs delete_tank | `batches.tank_id REFERENCES tanks(id) ON DELETE SET NULL` -- only child, so delete_tank CANNOT raise IntegrityError | Agent 15 (tank_routes) mentions "IntegrityError catch for unique name constraint" only -- correct for delete | PASS | delete_tank has no RESTRICT children; Agent 15 correctly omits delete IntegrityError handling |
| 12 | Schema field names vs Route param names | All schema columns use snake_case (recipe_id, batch_id, tank_id, tap_id, sale_id, staff_id, ri_id) | All route path params use the same names (`<int:recipe_id>`, `<int:batch_id>`, etc.) | PASS | Exact match |
| 13 | SQL types vs App-layer types | INTEGER columns (id, recipe_id, batch_id, etc.) | Model function signatures use `int` | PASS | All integer columns map to Python int |
| 14 | SQL types vs App-layer types | REAL columns (stock_qty, volume_gallons, remaining_volume_oz, quantity, quantity_oz, capacity_gallons) | Model signatures use `float` | PASS | All real columns map to Python float |
| 15 | SQL types vs App-layer types | TEXT columns (name, style, notes, status, role, email, phone, etc.) | Model signatures use `str` or `str | None` | PASS | Consistent |
| 16 | SQL types vs App-layer types | price_cents: SQL INTEGER | Model parameter type: `int`; Input Validation: `round(float*100)` producing int | PASS | Consistent |
| 17 | Transaction Contracts vs Model Code | All SERIAL-SAFE functions tagged in Transaction Contracts table | Model code: none of the SERIAL-SAFE functions call conn.commit() internally | PASS | Consistent |
| 18 | Transaction Contracts vs Model Code | All NEEDS-BEGIN-IMMEDIATE functions (start_brewing, advance_batch_status, assign_to_tap, create_sale) | Model code: all use explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK via conn.execute() | PASS | Consistent |
| 19 | Concurrency Contract vs Transaction Contracts | Concurrency Contract NEEDS-BEGIN-IMMEDIATE list: start_brewing, advance_batch_status, assign_to_tap, create_sale | Transaction Contracts NEEDS-BEGIN-IMMEDIATE list: same 4 functions | PASS | Exact match |
| 20 | Derived State vs Data Ownership | Derived State: sale_models writes to batches.remaining_volume_oz, batches.status, taps.batch_id | Data Ownership exception: "sale_models writes to batches and taps as derived state -- ONLY cross-table write exception" | PASS | Consistent and explicitly declared |
| 21 | Derived State vs Data Ownership | Derived State: batch_models writes to tanks.current_batch_id and ingredients.stock_qty | Data Ownership exception: "batch_models writes to tanks and ingredients as derived state during start_brewing" | PASS | Consistent and explicitly declared |
| 22 | Route Table vs App Configuration (url_prefix) | Route Table paths: /recipes/, /batches/, /ingredients/, /tanks/, /taps/, /sales/, /staff/ | App Configuration: url_prefix='/recipes', '/batches', '/ingredients', '/tanks', '/taps', '/sales', '/staff' | PASS | All prefixes match |
| 23 | Export Names vs Cross-Boundary Wiring (VALID_TRANSITIONS) | Export Names: `VALID_TRANSITIONS` Used By `batch_routes` | Cross-Boundary Wiring: batch_routes imports `VALID_TRANSITIONS` from batch_models | PASS | Consistent |
| 24 | create_sale signature vs Input Validation | Model: create_sale(conn, tap_id, quantity_oz, sale_type, price_cents) | Input Validation: POST /sales/ prescribes tap_id, quantity_oz, sale_type, price_cents | PASS | Exact field name match |
| 25 | Route Table completeness | Route Table lists 56 routes across 8 blueprints + auth + dashboard | App Configuration registers 9 blueprints; all handler names in table match blueprint dot-notation | PASS | No routes listed without a blueprint registration |
| 26 | Mock/Fixture Data vs Schema | No mock data or fixtures defined in spec (seed.py responsibility is generic) | N/A | N/A | Section not present -- seed script content not prescribed in spec |
| 27 | Defense-in-Depth Matrix vs Schema (delete_tank) | Defense-in-Depth: no entry for delete_tank IntegrityError | Schema: tanks has no RESTRICT children (batches.tank_id ON DELETE SET NULL) | PASS | Correctly omitted |
| 28 | Export Names (blueprints) vs App Configuration | Export Names: blueprints recipes, batches, ingredients, tanks, taps, sales, staff, dashboard, auth | App Configuration: registers all 9 matching blueprints | PASS | Exact match |

---

## Detailed Notes on FAILs

### FAIL 1: `get_recipe` -- Export Names vs Cross-Boundary Wiring

Export Names Table says `get_recipe` is Used By `recipe_routes, batch_routes`. The Cross-Boundary Wiring import for batch_routes is:

```
from app.models.recipe_models import get_all_recipes
```

`get_recipe` is absent. If batch_routes needs to look up a single recipe by ID, it must be added to the import. If batch_routes does not need `get_recipe`, it must be removed from the Export Names consumer list. One of the two must be corrected.

### FAIL 2: `get_all_sales` -- Export Names vs Cross-Boundary Wiring

Export Names says dashboard_routes consumes `get_all_sales`. Cross-Boundary Wiring for dashboard_routes only imports `get_today_sales_total` from sale_models. The Template Render Context for dashboard confirms only `today_sales=get_today_sales_total(conn)` is passed. Remove `get_all_sales` from the dashboard_routes consumer in Export Names, or add it to the wiring and template context.

### FAIL 3: `get_tap` -- Export Names vs Cross-Boundary Wiring

Export Names says sale_routes consumes `get_tap`. Cross-Boundary Wiring shows sale_routes imports only `get_all_taps` from tap_models. If sale_routes needs to look up a specific tap (e.g. for detail page or validation), `get_tap` must be added to the wiring. If not needed, remove from Export Names consumer list.

### FAIL 4: `get_all_batches` -- Export Names + Wiring vs Template Render Context

Three sections are in conflict:
- Export Names: `get_all_batches` Used By `batch_routes, dashboard_routes`
- Cross-Boundary Wiring: dashboard_routes imports `get_all_batches, get_batches_by_status`
- Template Render Context (dashboard): passes `active_batches`, `ready_batches`, `tapped_batches` all via `get_batches_by_status()` -- `get_all_batches` is never called

Resolution: remove `get_all_batches` from the dashboard_routes consumer in Export Names and from the dashboard_routes import in Cross-Boundary Wiring, OR add a use of `get_all_batches` to the Template Render Context.

### FAIL 5: `app/routes/__init__.py` -- File Assignment Boundaries vs Agent 1 Detail

The File Assignment Boundaries table (the canonical swarm boundary reference) omits `app/routes/__init__.py`. The Agent 1 detailed brief includes it. The swarm gate checker uses the Boundaries table; Agent 1 will build the file but it will be absent from the ownership record. Either add it to the table or remove it from the Agent 1 brief.

### FAILs 6-9: ON DELETE RESTRICT vs Agent Delete Responsibility

Four parent tables have RESTRICT children that generate IntegrityError on delete, but the corresponding agent briefs and Input Validation Prescriptions do not tell agents to catch IntegrityError on their delete routes:

| Route | RESTRICT Child | Missing Catch In |
|-------|---------------|-----------------|
| DELETE /ingredients/\<id\>/delete | recipe_ingredients.ingredient_id RESTRICT | Agent 14 brief + Input Validation |
| DELETE /taps/\<id\>/delete | sales.tap_id RESTRICT | Agent 16 brief + Input Validation |
| DELETE /recipes/\<id\>/delete | batches.recipe_id RESTRICT | Agent 12 brief + Input Validation |
| DELETE /batches/\<id\>/delete | sales.batch_id RESTRICT | Agent 13 brief + Input Validation |

For each: the route agent needs a `try/except sqlite3.IntegrityError` around the delete call with a flash message (e.g. "Cannot delete -- referenced by existing records") and redirect back to the detail page. Add prescriptions to both the Input Validation Prescriptions table and the relevant agent briefs.

Note: delete_tank is correctly handled -- `batches.tank_id ON DELETE SET NULL` means no IntegrityError is possible.

---

## Summary

- **Total checks:** 28
- **PASS:** 18
- **FAIL:** 9
- **WARN:** 1
- **N/A (section absent):** 1

STATUS: FAIL -- 9 contradictions found
