# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-05-21-restaurant-kitchen-mgmt-plan.md
**Checked:** 2026-05-21

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs Route Param | `ingredients.unit_cost_cents` (INTEGER) | model param `unit_cost_cents: int` | PASS | Exact match |
| 2 | Schema vs Route Param | `menu_items.price_cents` (INTEGER) | model param `price_cents: int` | PASS | Exact match |
| 3 | Schema vs Route Param | `inventory.current_stock` (REAL) | model `record_stock_movement` param `quantity: float` | PASS | REAL -> float is correct |
| 4 | SQL Types vs App-Layer | `ingredients.low_stock_threshold` REAL | model param `low_stock_threshold: float` | PASS | REAL -> float is correct |
| 5 | SQL Types vs App-Layer | `recipes.prep_time_minutes` INTEGER | model param `prep_time_minutes: int` | PASS | Exact match |
| 6 | SQL Types vs App-Layer | `menu_items.is_available` INTEGER | model param `is_available: int = 1` | PASS | SQLite bool-as-int, consistent |
| 7 | SQL Types vs App-Layer | `staff.is_active` INTEGER | model param `is_active: int` in `update_staff` | PASS | Consistent |
| 8 | CHECK Constraints vs Route/Template | `stock_movements.movement_type` CHECK `('receipt','consumption','adjustment','waste')` | Inventory Adjustment Form: `movement_type` (select: `adjustment/waste`) | WARN | Form only exposes 2 of 4 allowed values. `receipt` and `consumption` are presumably system-generated (PO receive, order prepare). No explicit comment in spec; agents may be confused about which values are user-selectable vs. system-only. |
| 9 | CHECK Constraints vs Route/Template | `orders.status` CHECK `('pending','preparing','ready','served','closed','cancelled')` | Status badge styling section lists all 6 values | PASS | All 6 values covered exactly |
| 10 | CHECK Constraints vs Route/Template | `tables.status` CHECK `('available','reserved','occupied','needs_cleaning')` | Table Status Form: `status` (select: available/reserved/occupied/needs_cleaning) | PASS | All 4 values match exactly |
| 11 | CHECK Constraints vs Route/Template | `reservations.status` CHECK `('confirmed','seated','completed','cancelled','no_show')` | Route table handlers: seat, complete, cancel, no_show (transitions only; no direct status form field) | PASS | Status transitions cover all states |
| 12 | CHECK Constraints vs Route/Template | `purchase_orders.status` CHECK `('draft','submitted','received','closed')` | Status badge styling section lists all 4 values | PASS | All 4 values covered exactly |
| 13 | Route Table vs url_for Registry | Route `POST /inventory/<int:ingredient_id>/adjust` handler `adjust` | url_for registry `url_for('inventory.adjust', ingredient_id=i.id)` | PASS | Path param name `ingredient_id` matches url_for kwarg |
| 14 | Route Table vs url_for Registry | Route `GET /inventory/<int:ingredient_id>/movements` handler `movements` | url_for registry `url_for('inventory.movements', ingredient_id=i.id)` | PASS | Path param name `ingredient_id` matches url_for kwarg |
| 15 | Route Table vs url_for Registry | All other routes: handlers in route table vs functions in url_for registry | (all 14 blueprints checked) | PASS | Every route table handler has a matching url_for entry; no orphans in either direction |
| 16 | Template Context vs Model Functions | `menu/detail.html` context: `cost_cents=get_menu_item_cost(conn, id)` (from `menu_models`) | Cross-Boundary Wiring Table: `menu.detail` calls `calculate_recipe_cost(conn, recipe_id)` from `recipe_models` | **FAIL** | Two sections disagree on which function `menu.detail` calls for cost. Template context says `get_menu_item_cost` (menu_models, takes `menu_item_id`). Wiring table says `calculate_recipe_cost` (recipe_models, takes `recipe_id`). These are different functions with different arguments. Agents that follow the template context will call `get_menu_item_cost`; agents that follow the wiring table will call `calculate_recipe_cost`. |
| 17 | Template Context vs Model Functions | `dashboard/index.html` context key `active_orders` bound to `get_all_orders(conn, status='pending')` | `get_dashboard_stats` returns dict with key `active_orders` (a count, not a list) | WARN | The template will have both `active_orders` (list[Row]) from the top-level context and `stats['active_orders']` (int count). Template authors may accidentally use the wrong one. The spec does not resolve which variable name to use for the list vs. the count. |
| 18 | Template Context vs Model Functions | `dashboard/index.html` context: `get_all_orders(conn, status='pending')` | Wiring table: `get_all_orders(conn, 'pending')` (positional) | WARN | Keyword vs. positional arg style inconsistency between two spec sections. Functionally equivalent in Python but may confuse agents reading one section over the other. |
| 19 | Export vs Import / Cross-Boundary Wiring | Wiring table: `orders.prepare` calls `deduct_order_inventory(conn, order_id)` from `inventory_models` with "BEGIN IMMEDIATE in caller" | Order Models: `start_preparing_order(conn, order_id)` docstring says "BEGIN IMMEDIATE, verify status=pending, set preparing, deduct inventory, commit" -- handles its own transaction | **FAIL** | The wiring table instructs `order_routes` agent to call `deduct_order_inventory` directly (bypassing `start_preparing_order`) and manage BEGIN IMMEDIATE itself. But `start_preparing_order` is designed to own the full transaction including status validation, inventory deduction, and commit. An agent following the wiring table would: (a) skip the status check in `start_preparing_order`, (b) duplicate transaction management, and (c) call a lower-level function the model design did not intend to be called directly from routes. |
| 20 | Export vs Import / Cross-Boundary Wiring | Wiring table: `orders.cancel` calls `restore_order_inventory(conn, order_id)` from `inventory_models` with "BEGIN IMMEDIATE in caller" | Order Models: `cancel_order(conn, order_id)` docstring says "BEGIN IMMEDIATE, set cancelled, restore inventory if needed, commit" | **FAIL** | Same pattern as check #19. The wiring table bypasses `cancel_order` and points the route directly at `restore_order_inventory`. The `cancel_order` function owns the transaction and conditionally restores inventory ("if needed"). Calling `restore_order_inventory` directly from the route skips the conditional logic and duplicates transaction management. |
| 21 | Export vs Import / Cross-Boundary Wiring | Wiring table: `purchase_orders.receive` calls `receive_purchase_order(conn, po_id)` from `purchase_order_models`, which in turn calls `record_stock_movement` | Data Ownership table: `stock_movements` owner is `inventory` module | PASS | The chain is correct. `purchase_orders.receive` route calls `receive_purchase_order` (po_models), which calls `record_stock_movement` (inventory_models). No module writes directly to `stock_movements` except through the `inventory_models` helper. Consistent with the cross-boundary write rule. |
| 22 | Form Fields vs request.form.get() Keys | Ingredient Form field: `unit_cost` (decimal) | Route must call `request.form.get('unit_cost', '0')` and multiply by 100 for `unit_cost_cents` | PASS | Field name `unit_cost` is distinct from the model param `unit_cost_cents`; the conversion is explicit in the Input Validation Rules money pattern. Consistent. |
| 23 | Form Fields vs request.form.get() Keys | Recipe Form parallel arrays: `ingredient_ids[]`, `quantities[]`, `units[]` | Input Validation Rules parallel array example: `getlist('ingredient_ids[]')`, `getlist('quantities[]')`, `getlist('units[]')` | PASS | Exact match |
| 24 | Form Fields vs request.form.get() Keys | Ingredient Form allergens: `allergen_ids` (no `[]` suffix) | Input Validation Rules (ingredient section): `request.form.getlist('allergen_ids')` | PASS | Consistent; no `[]` suffix for checkboxes |
| 25 | Form Fields vs request.form.get() Keys | Purchase Order Form: `unit_costs[]` (text, decimal) | `set_purchase_order_items` model param: `unit_costs: list[int]` | PASS | Form sends strings (decimal dollars), route must convert to int cents per money pattern. Conversion responsibility is on the route, consistent with spec. |
| 26 | Cross-Boundary Wiring vs Exports | All functions listed in Wiring Table as callees | Model Functions section signatures | PASS | Every callee in the wiring table (`deduct_order_inventory`, `restore_order_inventory`, `receive_purchase_order`, `record_stock_movement`, `calculate_recipe_cost`, `get_menu_item_allergens`, `get_menu_item_avg_rating`, `get_all_menu_items`, `get_all_tables`, `update_table_status`, `get_dashboard_stats`, `get_todays_specials`, `get_low_stock_items`, `get_all_orders`, `get_all_reservations`) is defined in the Model Functions section with matching signature. |
| 27 | File Boundaries vs Swarm Assignment | File Assignment Boundaries section (29 named agents) | Swarm Assignment Table (29 rows) | PASS | All 29 agents appear in both sections with the same names. No agent listed in one but absent from the other. |
| 28 | Data Ownership vs Cross-Boundary Wiring | `inventory` table: owner=`inventory`, written by `purchase_orders` via inventory helpers | Cross-boundary write rule explicitly states this is the required pattern | PASS | `purchase_orders` module does not write directly to `inventory`; it calls `record_stock_movement` from `inventory_models`. Consistent. |
| 29 | Data Ownership vs Cross-Boundary Wiring | `stock_movements` table: owner=`inventory`, written by `orders` via inventory helpers | Cross-boundary write rule and wiring table confirm this | PASS | `orders` module calls `deduct_order_inventory`/`restore_order_inventory` from `inventory_models`, which writes to `stock_movements`. No direct write from `orders` module. |
| 30 | Schema vs Route Param | `reservations` table has no `delete` route | Route table has no `DELETE /reservations/<int:id>` handler | PASS | Reservations use status transitions (cancel, no_show) instead of hard delete. Intentional design, internally consistent. |

---

## Detailed FAIL Analysis

### FAIL #1 — Check #16: menu.detail cost function mismatch

**Left side (Template Render Context section, line ~1322):**
```python
render_template('menu/detail.html',
    ...
    cost_cents=get_menu_item_cost(conn, id),   # <-- menu_models function, takes menu_item_id
    ...
)
```

**Right side (Cross-Boundary Wiring Table, line ~1877):**
```
| menu.detail | calculate_recipe_cost(conn, recipe_id) | recipe_models | Read-only |
```

These are two different functions:
- `get_menu_item_cost(conn, menu_item_id)` -- in `menu_models`, takes a menu item ID, returns `int | None`
- `calculate_recipe_cost(conn, recipe_id)` -- in `recipe_models`, takes a recipe ID, returns `int`

The `menu_routes` agent will receive both sections in its brief. The two sections give contradictory instructions. The wiring table entry must be corrected to either:
- Replace with `get_menu_item_cost(conn, menu_item_id)` from `menu_models`, OR
- Remove this row from the wiring table (it is an intra-module call, not a cross-boundary call)

### FAIL #2 — Check #19: orders.prepare wiring bypasses start_preparing_order

**Left side (Cross-Boundary Wiring Table):**
```
| orders.prepare | deduct_order_inventory(conn, order_id) | inventory_models | BEGIN IMMEDIATE in caller |
```

**Right side (Order Models section):**
```python
def start_preparing_order(conn: sqlite3.Connection, order_id: int) -> None:
    """BEGIN IMMEDIATE, verify status=pending, set preparing, deduct inventory, commit."""
```

The wiring table tells the `order_routes` agent to call `deduct_order_inventory` directly, managing BEGIN IMMEDIATE in the route. But `start_preparing_order` is the intended interface: it owns the transaction, validates the current status is `pending`, sets the status to `preparing`, calls `deduct_order_inventory` internally, and commits. Calling `deduct_order_inventory` directly from the route skips the status check and creates double-transaction management.

**Correction:** The wiring table row should read:
```
| orders.prepare | start_preparing_order(conn, order_id) | order_models | Handles own BEGIN IMMEDIATE |
```

### FAIL #3 — Check #20: orders.cancel wiring bypasses cancel_order

**Left side (Cross-Boundary Wiring Table):**
```
| orders.cancel | restore_order_inventory(conn, order_id) | inventory_models | BEGIN IMMEDIATE in caller |
```

**Right side (Order Models section):**
```python
def cancel_order(conn: sqlite3.Connection, order_id: int) -> None:
    """BEGIN IMMEDIATE, set cancelled, restore inventory if needed, commit."""
```

Same pattern as FAIL #2. `cancel_order` conditionally restores inventory only "if needed" (i.e., only if the order was already in `preparing` or later state). Calling `restore_order_inventory` unconditionally from the route would incorrectly attempt to restore inventory even for orders that were never `preparing`.

**Correction:** The wiring table row should read:
```
| orders.cancel | cancel_order(conn, order_id) | order_models | Handles own BEGIN IMMEDIATE and conditional restore |
```

---

## Summary

- **Total checks:** 30
- **PASS:** 25
- **FAIL:** 3
- **WARN:** 2
- **N/A (section absent):** 0

### WARN Dispositions

| # | WARN | Recommended Action |
|---|------|--------------------|
| 8 | Inventory Adjustment Form only lists `adjustment/waste` but schema allows 4 movement types | Add a spec comment clarifying that `receipt` and `consumption` are system-only (not user-selectable in the manual adjustment form). Low risk if agents read the form field spec carefully. |
| 17 | Dashboard context has both `active_orders` (list) and `stats['active_orders']` (count) | Rename the top-level context key to `active_orders_list` or `pending_orders` to avoid template variable shadowing. Medium risk -- template author confusion likely. |
| 18 | `get_all_orders` called with keyword arg in template context, positional in wiring table | Cosmetic; no functional impact. Fix for consistency. |

---

STATUS: FAIL -- 3 contradictions found
