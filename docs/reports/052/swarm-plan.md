---
report: swarm-plan-validation
plan: docs/plans/2026-05-21-restaurant-kitchen-mgmt-plan.md
date: 2026-05-21
run: "051"
---

# Swarm Agent Assignment Validation Report

**Plan:** `docs/plans/2026-05-21-restaurant-kitchen-mgmt-plan.md`
**Validator:** swarm-planner agent
**Date:** 2026-05-21

---

## Summary

STATUS: FAIL

Three findings: one P0 (duplicate file assignment), one P1 (agent count mismatch), one P1 (path format inconsistency in the table).

---

## Check 1 + 2: Every file appears exactly once / No file assigned to two agents

### FAIL -- P0: dashboard files are double-assigned

The plan contains two distinct sections that assign files:

**Section A: File Assignment Boundaries (lines 1894-2044)**
This section defines 28 agents. The `dashboard` agent owns all four files:
- `restaurantops/app/models/dashboard_models.py`
- `restaurantops/app/blueprints/dashboard/__init__.py`
- `restaurantops/app/blueprints/dashboard/routes.py`
- `restaurantops/app/templates/dashboard/index.html`

**Section B: Swarm Agent Assignment table (lines 2083-2115)**
The table defines 29 agents and splits the dashboard work across **three rows**:

| Row | Agent | Files listed |
|-----|-------|-------------|
| 3 | dashboard | blueprints/dashboard/*, templates/dashboard/* |
| 16 | dashboard_models | models/dashboard_models.py |
| 29 | dashboard_routes | blueprints/dashboard/*, templates/dashboard/* |

Row 3 (`dashboard`) and row 29 (`dashboard_routes`) both claim the same blueprint and template files:
- `restaurantops/app/blueprints/dashboard/__init__.py`
- `restaurantops/app/blueprints/dashboard/routes.py`
- `restaurantops/app/templates/dashboard/index.html`

This is a direct duplicate assignment. Two different agents would attempt to write the same three files.

**Root cause:** The table was revised (see lines 2051-2081) to split `dashboard` into `dashboard_models` (row 16) and `dashboard_routes` (row 29), but row 3 (`dashboard`) was not removed from the table. All three rows coexist.

**Fix required:** Remove row 3 (`dashboard`) from the Swarm Agent Assignment table. The split into `dashboard_models` (row 16) and `dashboard_routes` (row 29) is the intended final state, and together they cover all four dashboard files exactly once.

---

## Check 3: Swarm Agent Assignment table matches File Assignment Boundaries

### FAIL -- P1: agent count contradiction

The File Assignment Boundaries section defines **28 agents** (lines 1894-2044).

The Swarm Agent Assignment table defines **29 agents** (lines 2083-2115) by splitting the `dashboard` agent into `dashboard_models` + `dashboard_routes`, which is reflected in the revised count note at line 2117.

However, the File Assignment Boundaries section was never updated to reflect this split: it still shows a single `dashboard` agent (line 1908) owning all four files.

After the fix, the two sections must agree:

**Option A (recommended):** Keep the 29-agent split in the table. Update the File Assignment Boundaries section by replacing:

```
#### Agent: dashboard (models + routes + templates)
- restaurantops/app/models/dashboard_models.py
- restaurantops/app/blueprints/dashboard/__init__.py
- restaurantops/app/blueprints/dashboard/routes.py
- restaurantops/app/templates/dashboard/index.html
```

with:

```
#### Agent: dashboard_models
- restaurantops/app/models/dashboard_models.py

#### Agent: dashboard_routes
- restaurantops/app/blueprints/dashboard/__init__.py
- restaurantops/app/blueprints/dashboard/routes.py
- restaurantops/app/templates/dashboard/index.html
```

**Option B:** Collapse back to 28 agents by removing rows 16 and 29 from the table and restoring a single `dashboard` row that lists all four files. Also remove row 3 (`dashboard`) from the current table since it is incomplete.

---

## Check 4: Dependencies are correct

### PASS

All cross-boundary dependencies checked against the Cross-Boundary Wiring Table (lines 1869-1890):

| Dependency path | Table row | Listed dependency | Verdict |
|----------------|-----------|------------------|---------|
| orders.prepare -> deduct_order_inventory (inventory_models) | row 11 (order_models) | inventory_models | PASS |
| orders.cancel -> restore_order_inventory (inventory_models) | row 18 (order_routes) | order_models (which depends on inventory_models) | PASS |
| purchase_orders.receive -> receive_purchase_order -> record_stock_movement (inventory_models) | row 15 (po_models) | inventory_models | PASS |
| menu.detail -> calculate_recipe_cost (recipe_models) | row 20 (menu_routes) | recipe_models | PASS |
| menu.detail -> get_menu_item_allergens (menu_models) | row 20 (menu_routes) | menu_models | PASS |
| menu.detail -> get_menu_item_avg_rating (review_models) | row 20 (menu_routes) | review_models | PASS |
| orders.form -> get_all_menu_items (menu_models) | row 24 (order_routes) | menu_models | PASS |
| orders.form -> get_all_tables (table_models) | row 24 (order_routes) | table_models | PASS |
| reservations.seat/complete/cancel/no_show -> update_table_status (table_models) | row 23 (reservation_routes) | table_models | PASS |
| dashboard.index -> get_dashboard_stats / get_todays_specials (dashboard_models) | row 29 (dashboard_routes) | dashboard_models | PASS |
| dashboard.index -> get_low_stock_items (inventory_models) | row 29 (dashboard_routes) | inventory_models | PASS |
| dashboard.index -> get_all_orders (order_models) | row 29 (dashboard_routes) | order_models | PASS |
| dashboard.index -> get_all_reservations (reservation_models) | row 29 (dashboard_routes) | reservation_models | PASS |
| recipe_routes: get_all_ingredients (ingredient_models) | row 19 (recipe_routes) | ingredient_models | PASS |
| inventory_routes: get_ingredient (ingredient_models) | row 21 (inventory_routes) | ingredient_models | PASS |
| specials_routes: get_all_menu_items (menu_models) | row 27 (specials_routes) | menu_models | PASS |
| reviews_routes: get_reviews_for_menu_item / get_menu_item_avg_rating | row 28 (review_routes) | menu_models | PASS |
| po_routes: get_all_suppliers / get_all_ingredients | row 25 (po_routes) | supplier_models, ingredient_models | PASS |

One note: the `reservation_models` spec (lines 902-923) calls `update_table_status` from `table_models`. Row 10 (`reservation_models`) in the table lists `table_models` as a dependency. PASS.

No missing or incorrect dependency entries found.

---

## Check 5: All paths relative to project root (restaurantops/)

### FAIL -- P1: table uses two different path conventions

The **File Assignment Boundaries** section (lines 1894-2044) uses full paths prefixed with `restaurantops/`:
- Example: `restaurantops/app/models/dashboard_models.py`

The **Swarm Agent Assignment table** (lines 2083-2115) uses paths that are relative to `restaurantops/` but without the prefix:
- Row 1 (core): `app/__init__.py, app/db.py, ...`
- Row 17 (ingredient_routes): `blueprints/ingredients/*, templates/ingredients/*`

The plan's own note at line 2119 states: "All file paths are relative to `restaurantops/`."

This ambiguity means an agent reading only the table cannot determine the full path without also reading the note. Glob patterns like `blueprints/dashboard/*` also do not enumerate specific files, making it impossible to confirm coverage without cross-referencing the boundaries section.

**Fix required:** Expand all wildcard globs to explicit file paths in the table, and apply a consistent prefix (either all paths start with `restaurantops/` or the note at line 2119 is kept and the table uses `app/` prefix consistently).

---

## Complete File Inventory (from File Assignment Boundaries)

Total distinct files listed: **87**

| # | File (as written in boundaries) | Agent |
|---|--------------------------------|-------|
| 1 | restaurantops/app/__init__.py | core |
| 2 | restaurantops/app/db.py | core |
| 3 | restaurantops/app/filters.py | core |
| 4 | restaurantops/app/schema.sql | core |
| 5 | restaurantops/app/init_db.py | core |
| 6 | restaurantops/run.py | core |
| 7 | restaurantops/requirements.txt | core |
| 8 | restaurantops/.gitignore | core |
| 9 | restaurantops/app/templates/base.html | layout |
| 10 | restaurantops/app/static/style.css | layout |
| 11 | restaurantops/app/models/dashboard_models.py | dashboard |
| 12 | restaurantops/app/blueprints/dashboard/__init__.py | dashboard |
| 13 | restaurantops/app/blueprints/dashboard/routes.py | dashboard |
| 14 | restaurantops/app/templates/dashboard/index.html | dashboard |
| 15 | restaurantops/app/blueprints/auth/__init__.py | auth |
| 16 | restaurantops/app/blueprints/auth/routes.py | auth |
| 17 | restaurantops/app/templates/auth/login.html | auth |
| 18 | restaurantops/app/models/menu_models.py | menu_models |
| 19 | restaurantops/app/models/category_models.py | menu_models |
| 20 | restaurantops/app/blueprints/menu/__init__.py | menu_routes |
| 21 | restaurantops/app/blueprints/menu/routes.py | menu_routes |
| 22 | restaurantops/app/templates/menu/list.html | menu_routes |
| 23 | restaurantops/app/templates/menu/form.html | menu_routes |
| 24 | restaurantops/app/templates/menu/detail.html | menu_routes |
| 25 | restaurantops/app/templates/menu/categories.html | menu_routes |
| 26 | restaurantops/app/models/recipe_models.py | recipe_models |
| 27 | restaurantops/app/blueprints/recipes/__init__.py | recipe_routes |
| 28 | restaurantops/app/blueprints/recipes/routes.py | recipe_routes |
| 29 | restaurantops/app/templates/recipes/list.html | recipe_routes |
| 30 | restaurantops/app/templates/recipes/form.html | recipe_routes |
| 31 | restaurantops/app/templates/recipes/detail.html | recipe_routes |
| 32 | restaurantops/app/models/ingredient_models.py | ingredient_models |
| 33 | restaurantops/app/models/core_models.py | ingredient_models |
| 34 | restaurantops/app/blueprints/ingredients/__init__.py | ingredient_routes |
| 35 | restaurantops/app/blueprints/ingredients/routes.py | ingredient_routes |
| 36 | restaurantops/app/templates/ingredients/list.html | ingredient_routes |
| 37 | restaurantops/app/templates/ingredients/form.html | ingredient_routes |
| 38 | restaurantops/app/templates/ingredients/detail.html | ingredient_routes |
| 39 | restaurantops/app/models/inventory_models.py | inventory_models |
| 40 | restaurantops/app/blueprints/inventory/__init__.py | inventory_routes |
| 41 | restaurantops/app/blueprints/inventory/routes.py | inventory_routes |
| 42 | restaurantops/app/templates/inventory/index.html | inventory_routes |
| 43 | restaurantops/app/templates/inventory/low_stock.html | inventory_routes |
| 44 | restaurantops/app/templates/inventory/movements.html | inventory_routes |
| 45 | restaurantops/app/models/supplier_models.py | supplier_models |
| 46 | restaurantops/app/blueprints/suppliers/__init__.py | supplier_routes |
| 47 | restaurantops/app/blueprints/suppliers/routes.py | supplier_routes |
| 48 | restaurantops/app/templates/suppliers/list.html | supplier_routes |
| 49 | restaurantops/app/templates/suppliers/form.html | supplier_routes |
| 50 | restaurantops/app/templates/suppliers/detail.html | supplier_routes |
| 51 | restaurantops/app/models/purchase_order_models.py | po_models |
| 52 | restaurantops/app/blueprints/purchase_orders/__init__.py | po_routes |
| 53 | restaurantops/app/blueprints/purchase_orders/routes.py | po_routes |
| 54 | restaurantops/app/templates/purchase_orders/list.html | po_routes |
| 55 | restaurantops/app/templates/purchase_orders/form.html | po_routes |
| 56 | restaurantops/app/templates/purchase_orders/detail.html | po_routes |
| 57 | restaurantops/app/models/order_models.py | order_models |
| 58 | restaurantops/app/blueprints/orders/__init__.py | order_routes |
| 59 | restaurantops/app/blueprints/orders/routes.py | order_routes |
| 60 | restaurantops/app/templates/orders/list.html | order_routes |
| 61 | restaurantops/app/templates/orders/form.html | order_routes |
| 62 | restaurantops/app/templates/orders/detail.html | order_routes |
| 63 | restaurantops/app/templates/orders/kitchen.html | order_routes |
| 64 | restaurantops/app/models/table_models.py | table_models |
| 65 | restaurantops/app/blueprints/tables/__init__.py | table_routes |
| 66 | restaurantops/app/blueprints/tables/routes.py | table_routes |
| 67 | restaurantops/app/templates/tables/list.html | table_routes |
| 68 | restaurantops/app/templates/tables/form.html | table_routes |
| 69 | restaurantops/app/templates/tables/board.html | table_routes |
| 70 | restaurantops/app/models/reservation_models.py | reservation_models |
| 71 | restaurantops/app/blueprints/reservations/__init__.py | reservation_routes |
| 72 | restaurantops/app/blueprints/reservations/routes.py | reservation_routes |
| 73 | restaurantops/app/templates/reservations/list.html | reservation_routes |
| 74 | restaurantops/app/templates/reservations/form.html | reservation_routes |
| 75 | restaurantops/app/templates/reservations/detail.html | reservation_routes |
| 76 | restaurantops/app/models/staff_models.py | staff_models |
| 77 | restaurantops/app/blueprints/staff/__init__.py | staff_routes |
| 78 | restaurantops/app/blueprints/staff/routes.py | staff_routes |
| 79 | restaurantops/app/templates/staff/list.html | staff_routes |
| 80 | restaurantops/app/templates/staff/form.html | staff_routes |
| 81 | restaurantops/app/templates/staff/detail.html | staff_routes |
| 82 | restaurantops/app/templates/staff/schedule.html | staff_routes |
| 83 | restaurantops/app/templates/staff/shift_form.html | staff_routes |
| 84 | restaurantops/app/models/specials_models.py | specials_models |
| 85 | restaurantops/app/blueprints/specials/__init__.py | specials_routes |
| 86 | restaurantops/app/blueprints/specials/routes.py | specials_routes |
| 87 | restaurantops/app/templates/specials/list.html | specials_routes |
| 88 | restaurantops/app/templates/specials/form.html | specials_routes |
| 89 | restaurantops/app/templates/specials/detail.html | specials_routes |
| 90 | restaurantops/app/models/review_models.py | review_models |
| 91 | restaurantops/app/blueprints/reviews/__init__.py | review_routes |
| 92 | restaurantops/app/blueprints/reviews/routes.py | review_routes |
| 93 | restaurantops/app/templates/reviews/list.html | review_routes |
| 94 | restaurantops/app/templates/reviews/form.html | review_routes |
| 95 | restaurantops/app/templates/reviews/detail.html | review_routes |
| 96 | restaurantops/app/templates/reviews/summary.html | review_routes |

**Duplicate check result (boundaries section):** No file appears twice in the File Assignment Boundaries section. All 96 files are unique across the 28 agents listed there.

---

## Findings Summary

| # | Severity | Check | Description |
|---|----------|-------|-------------|
| 1 | P0 | Check 2 | dashboard blueprint + template files assigned to both row 3 (`dashboard`) AND row 29 (`dashboard_routes`) in the Swarm Agent Assignment table |
| 2 | P1 | Check 3 | File Assignment Boundaries lists 28 agents; Swarm Agent Assignment table lists 29 agents; the boundaries section was not updated to reflect the dashboard split |
| 3 | P1 | Check 5 | Path format inconsistency: boundaries section uses `restaurantops/app/...` prefix; table uses abbreviated paths and glob wildcards instead of explicit file lists |

---

## Required Fixes Before Launch

### Fix 1 (P0 -- must fix before launch)

In the Swarm Agent Assignment table, **delete row 3** (the `dashboard` row). The intended split is already in rows 16 and 29. Leaving row 3 causes two agents to claim the same files and will produce write conflicts on:
- `restaurantops/app/blueprints/dashboard/__init__.py`
- `restaurantops/app/blueprints/dashboard/routes.py`
- `restaurantops/app/templates/dashboard/index.html`

### Fix 2 (P1 -- must fix before launch)

Update the **File Assignment Boundaries** section to match the 29-agent split. Replace the single `dashboard` entry with two entries:

```
#### Agent: dashboard_models
- restaurantops/app/models/dashboard_models.py

#### Agent: dashboard_routes
- restaurantops/app/blueprints/dashboard/__init__.py
- restaurantops/app/blueprints/dashboard/routes.py
- restaurantops/app/templates/dashboard/index.html
```

Update the total agent count from "28 agents" to "29 agents" in the boundaries section.

### Fix 3 (P1 -- recommended before launch)

Expand all wildcard glob entries in the Swarm Agent Assignment table to explicit file paths. Example:

Current (ambiguous):
```
blueprints/dashboard/*, templates/dashboard/*
```

Required (explicit):
```
restaurantops/app/blueprints/dashboard/__init__.py,
restaurantops/app/blueprints/dashboard/routes.py,
restaurantops/app/templates/dashboard/index.html
```

Apply the `restaurantops/app/` prefix consistently to all paths in the table, matching the boundaries section format.

---

STATUS: FAIL

**Blocking issue:** `restaurantops/app/blueprints/dashboard/__init__.py`, `restaurantops/app/blueprints/dashboard/routes.py`, and `restaurantops/app/templates/dashboard/index.html` are assigned to both `dashboard` (row 3) and `dashboard_routes` (row 29) in the Swarm Agent Assignment table.
