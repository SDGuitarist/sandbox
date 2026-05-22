---
run: "057"
plan: "docs/plans/brewops-plan.md"
date: 2026-05-22
status: PASS
---

# Swarm Agent Assignment -- Run 057 (BrewOps)

## Validation Summary

**Total agents:** 21 (matches frontmatter `agents: 21`)
**Total files:** 53
**Duplicate check:** No file appears in multiple assignments -- PASS
**Spec coverage check:** All files referenced in the Cross-Boundary Wiring Table are assigned -- PASS
**Agent count check:** Plan frontmatter says 21, table has 21 rows -- PASS

### Notes

- `app/routes/__init__.py` and `app/models/__init__.py` (the latter IS listed): `app/routes/__init__.py`
  is not in the plan's file list. It is an empty init file that Python requires but the spec never
  references. It is excluded from the table by design. If agents need it, the `core` agent or each
  route agent should create an empty one inside their own directory. Recommendation: assign it to
  `core` (Agent 1) since core owns `app/models/__init__.py` by the same pattern.
- All 4 NEEDS-BEGIN-IMMEDIATE functions (`start_brewing`, `advance_batch_status`, `assign_to_tap`,
  `create_sale`) are each owned by a single model agent. No cross-agent write conflict.
- The declared derived-state exception (sale_models writes to batches + taps; batch_models writes to
  tanks + ingredients) is within single agents' file scopes -- no merge conflict risk.

---

## Swarm Agent Assignment

**Total agents:** 21
**Total files:** 53
**Validation:** No file appears in multiple assignments

---

### Agent 1: core

**Files:**
- `app/__init__.py`
- `app/db.py`
- `app/auth.py`
- `app/filters.py`
- `app/models/__init__.py`
- `schema.sql`
- `requirements.txt`
- `.gitignore`
- `run.py`

**Responsibility:** Creates the Flask app factory, registers all blueprints, configures CSRF, DB, security headers, and session lifetime; writes the database schema and connection layer.

---

### Agent 2: layout

**Files:**
- `app/templates/base.html`
- `app/static/style.css`

**Responsibility:** Writes the shared base template with Bootstrap 5 CDN, navbar links to all 8 domains, flash message rendering, block definitions (`title`, `content`), and the project-wide stylesheet.

---

### Agent 3: auth

**Files:**
- `app/routes/auth_routes.py`
- `app/templates/auth/login.html`

**Responsibility:** Implements the login/logout routes, brute-force protection using `app.login_attempts`, sets `session['logged_in']` and `session.permanent`, and renders the login form template.

---

### Agent 4: recipe_models

**Files:**
- `app/models/recipe_models.py`

**Responsibility:** Implements all SERIAL-SAFE recipe CRUD model functions (`get_all_recipes`, `get_recipe`, `create_recipe`, `update_recipe`, `delete_recipe`) exactly matching the shared interface spec signatures.

---

### Agent 5: recipe_ingredient_models

**Files:**
- `app/models/recipe_ingredient_models.py`

**Responsibility:** Implements all SERIAL-SAFE recipe_ingredients model functions (`get_recipe_ingredients`, `add_recipe_ingredient`, `remove_recipe_ingredient`) with the JOIN query returning `ingredient_name` and `ingredient_unit`.

---

### Agent 6: batch_models

**Files:**
- `app/models/batch_models.py`

**Responsibility:** Implements batch CRUD and the three NEEDS-BEGIN-IMMEDIATE transaction functions (`start_brewing`, `advance_batch_status`, `assign_to_tap`), plus the `VALID_TRANSITIONS` constant, managing all derived state updates across batches, tanks, and ingredients.

---

### Agent 7: ingredient_models

**Files:**
- `app/models/ingredient_models.py`

**Responsibility:** Implements all SERIAL-SAFE ingredient model functions including `get_low_stock_ingredients` which returns rows where `stock_qty <= low_stock_threshold`.

---

### Agent 8: tank_models

**Files:**
- `app/models/tank_models.py`

**Responsibility:** Implements all SERIAL-SAFE tank model functions including `get_available_tanks` (returns tanks where `current_batch_id IS NULL`).

---

### Agent 9: tap_models

**Files:**
- `app/models/tap_models.py`

**Responsibility:** Implements all SERIAL-SAFE tap model functions including `get_all_taps` (JOIN with batches + recipes), `get_tap` (same JOIN), and `get_available_taps` (taps where `batch_id IS NULL`).

---

### Agent 10: sale_models

**Files:**
- `app/models/sale_models.py`

**Responsibility:** Implements `get_all_sales`, `get_sale`, `get_today_sales_total`, and the NEEDS-BEGIN-IMMEDIATE `create_sale` function which decrements `remaining_volume_oz` and handles the derived state chain (batch -> empty, tap -> clear).

---

### Agent 11: staff_models

**Files:**
- `app/models/staff_models.py`

**Responsibility:** Implements all SERIAL-SAFE staff model functions (`get_all_staff`, `get_staff_member`, `create_staff`, `update_staff`, `delete_staff`).

---

### Agent 12: recipe_routes

**Files:**
- `app/routes/recipe_routes.py`
- `app/templates/recipes/list.html`
- `app/templates/recipes/form.html`
- `app/templates/recipes/detail.html`

**Responsibility:** Implements the `recipes` blueprint (13 routes), all input validation per the Input Validation Prescriptions, CSRF tokens, `@login_required`, and three recipe templates including the inline ingredient add/remove form on the detail page.

---

### Agent 13: batch_routes

**Files:**
- `app/routes/batch_routes.py`
- `app/templates/batches/list.html`
- `app/templates/batches/form.html`
- `app/templates/batches/detail.html`

**Responsibility:** Implements the `batches` blueprint (11 routes), calling NEEDS-BEGIN-IMMEDIATE model functions and mapping their error return strings to flash messages; the detail page exposes start-brewing, advance, and assign-tap forms with VALID_TRANSITIONS guard.

---

### Agent 14: ingredient_routes

**Files:**
- `app/routes/ingredient_routes.py`
- `app/templates/ingredients/list.html`
- `app/templates/ingredients/form.html`
- `app/templates/ingredients/detail.html`

**Responsibility:** Implements the `ingredients` blueprint (7 routes) with category enum validation, stock quantity validation, and IntegrityError catch for unique name constraint.

---

### Agent 15: tank_routes

**Files:**
- `app/routes/tank_routes.py`
- `app/templates/tanks/list.html`
- `app/templates/tanks/form.html`
- `app/templates/tanks/detail.html`

**Responsibility:** Implements the `tanks` blueprint (7 routes) with tank_type enum validation, capacity validation, and IntegrityError catch for unique name constraint.

---

### Agent 16: tap_routes

**Files:**
- `app/routes/tap_routes.py`
- `app/templates/taps/list.html`
- `app/templates/taps/form.html`
- `app/templates/taps/detail.html`

**Responsibility:** Implements the `taps` blueprint (7 routes) with position integer validation, IntegrityError catch for unique name/position constraints, and a link to `sales.new` from the tap detail page.

---

### Agent 17: sale_routes

**Files:**
- `app/routes/sale_routes.py`
- `app/templates/sales/list.html`
- `app/templates/sales/form.html`
- `app/templates/sales/detail.html`

**Responsibility:** Implements the `sales` blueprint (4 routes), including the money parsing pattern for `price_cents`, sale_type enum validation, and the sales form which filters `get_all_taps()` to only taps with a `batch_id`.

---

### Agent 18: staff_routes

**Files:**
- `app/routes/staff_routes.py`
- `app/templates/staff/list.html`
- `app/templates/staff/form.html`
- `app/templates/staff/detail.html`

**Responsibility:** Implements the `staff` blueprint (7 routes) with role enum validation, optional email format validation, and IntegrityError catch for unique email constraint.

---

### Agent 19: dashboard_routes

**Files:**
- `app/routes/dashboard_routes.py`
- `app/templates/dashboard/index.html`

**Responsibility:** Implements the `dashboard` blueprint (1 route at `/`) with the exact `render_template` context defined in the spec (active_batches, ready_batches, tapped_batches, low_stock, taps, today_sales); the template displays all six data sections using the `|dollars` and `|format_date` filters.

---

### Agent 20: seed

**Files:**
- `seed.py`

**Responsibility:** Writes a seed script that inserts representative sample data (recipes, ingredients, batches, tanks, taps, staff) using the same `get_db()` pattern and calling `init_db()` first if the DB does not exist.

---

### Agent 21: tests

**Files:**
- `test_smoke.py`

**Responsibility:** Writes the smoke test suite covering all 8 blueprints, the start_brewing transaction flow, and the sale-causes-empty derived state chain, using a temporary SQLite DB and the Flask test client.

---

STATUS: PASS
