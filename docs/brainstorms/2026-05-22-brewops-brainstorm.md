---
date: 2026-05-22
topic: brewops-craft-brewery-manager
---

# BrewOps -- Craft Brewery Manager

## What We're Building

A single-admin craft brewery management tool for a small brewery/taproom.
Track recipes, brew batches, manage ingredient inventory, assign tanks/
fermenters, run a taproom with tap assignments and pour sales, and manage
staff. Built in Flask + SQLite + Jinja2 with Bootstrap 5 for UI.

This is Run 057 -- the validation build for 3 new mandatory spec sections
proposed in Run 056 (CoWorkFlow Deferred Fixes):

1. **Concurrency Contract** -- tag every write function as SERIAL-SAFE,
   NEEDS-BEGIN-IMMEDIATE, or TRIGGER-BACKED
2. **Defense-in-Depth Matrix** -- map every constraint to app-level and
   DB-level enforcement with error translation
3. **Derived State** -- declare every field computed from other tables with
   an explicit owning agent

Admin-only tool -- no customer-facing pages, no online ordering, no
distribution. The admin (head brewer / owner) logs in and manages everything.

## Why This Approach

**Approach chosen: 7 domain modules (recipes, batches, ingredients, tanks,
taps, sales, staff) with simple CRUD plus targeted business rules.**

Considered alternatives:
1. **Full brewery ERP (recipes + batches + inventory + QC + distribution +
   financials)** -- rejected because the complexity far exceeds CoWorkFlow
   scale and the extra modules (QC labs, distribution chains, purchase orders)
   don't exercise the 3 new spec sections any more than the simpler domains.
   The concurrency/derived-state validation targets are in batch lifecycle,
   inventory, tanks, and sales -- not in supply chain.
2. **Minimal 4-module (recipes + batches + inventory + tanks only)** --
   rejected because it removes the taproom/sales domain, which is the richest
   source of derived state (sales decrement batch volume, tap status tracks
   remaining volume) and concurrency (concurrent sales on same tap). Without
   sales, there's only one TOCTOU scenario (tank assignment) instead of three.
3. **Multi-role RBAC (brewer, server, manager)** -- rejected because RBAC
   adds IDOR complexity (FC35) that was already validated in VenueConnect
   (Run 049). Single-admin keeps focus on the 3 new spec sections rather than
   auth machinery.

## Key Decisions

### 1. Single Admin Auth (No Roles)
One admin user. Login with password from environment variable
(`ADMIN_PASSWORD`). No user table, no registration, no roles. Session-based
auth with `@login_required` decorator. Logout via POST (CSRF-protected).

**Rationale:** Same proven pattern as CoWorkFlow/GymFlow/RestaurantOps. The
admin manages all brewery operations. Staff table is for reference/scheduling
only (staff don't log in).

### 2. Recipe + Ingredient Relationship
Recipes have a many-to-many relationship with ingredients via a
`recipe_ingredients` join table. Each entry specifies the ingredient, quantity,
and unit. Recipes also store target_abv, style, and notes.

**Rationale:** The join table is the natural schema for "a recipe uses N
ingredients with specific quantities." This creates a derived-state opportunity:
when a batch starts brewing, inventory levels auto-decrement based on the
recipe's ingredient list.

### 3. Batch Lifecycle (7 statuses)
Batches progress through: planned -> brewing -> fermenting -> conditioning ->
ready -> tapped -> empty. Status transitions are admin-initiated (no automatic
time-based advancement). Each batch links to a recipe and optionally to a
tank/fermenter.

Key business rules:
- **planned -> brewing**: Requires tank assignment + sufficient ingredient
  inventory. Inventory auto-decrements. Uses BEGIN IMMEDIATE.
- **brewing -> fermenting**: Manual status change. No side effects.
- **fermenting -> conditioning**: Manual. No side effects.
- **conditioning -> ready**: Manual. Tank becomes available for reassignment.
- **ready -> tapped**: Requires tap assignment. Tap's batch_id is set.
- **tapped -> empty**: Batch volume reaches 0 (via sales) or manual.
  Tap is cleared.

**Rationale:** 7 statuses exercise the derived-state section (status auto-
updates from events) and concurrency contract (tank assignment, inventory
decrement). Only the transitions with side effects (planned->brewing,
ready->tapped, empty) need BEGIN IMMEDIATE.

### 4. Tank Assignment Concurrency
Tanks have a capacity (in gallons) and a current_batch_id. Assigning a batch
to a tank requires:
1. Tank must be available (current_batch_id IS NULL)
2. Tank capacity >= batch volume
3. BEGIN IMMEDIATE transaction to prevent two batches claiming same tank

When a batch transitions from conditioning -> ready, the tank is released
(current_batch_id set to NULL).

**Rationale:** This is the primary TOCTOU scenario. Two simultaneous
planned->brewing requests could both see the tank as available. BEGIN
IMMEDIATE + check inside transaction prevents the race.

### 5. Inventory Management
Ingredients have a `stock_qty` field tracking current stock in standard units.
When a batch starts brewing (planned -> brewing), the recipe's ingredient
quantities are decremented from stock. This happens inside the same BEGIN
IMMEDIATE transaction as the batch status change.

**Defense-in-depth:**
- App level: Route checks all ingredients have sufficient stock before
  transition (UX gate with friendly flash messages)
- Model level: Re-checks inside BEGIN IMMEDIATE (authoritative, TOCTOU-safe)
- DB level: CHECK constraint `stock_qty >= 0` prevents negative stock

**Rationale:** The classic TOCTOU Fence pattern from Run 056. Route-level
check prevents unnecessary transaction overhead. Model-level check prevents
races. DB-level CHECK is the last-resort safety net.

### 6. Taproom and Pour Sales
Taps are named positions (e.g., "Tap 1", "Tap 2"). Each tap can be assigned
to one batch. The batch has a `remaining_volume_oz` field that decrements
with each sale.

Sales record: tap_id, quantity_oz, sale_type (pint/half-pint/growler/case),
price_cents, timestamp. Creating a sale decrements the batch's
remaining_volume_oz.

**Concurrency:** Two concurrent sales on the same tap could overdraw the
batch volume. Uses BEGIN IMMEDIATE to prevent negative remaining volume.

**Derived state:**
- Tap `is_active` is derived from: has a batch AND batch remaining_volume > 0
- When remaining_volume hits 0, batch status auto-updates to "empty" and
  tap's batch_id is cleared

**Rationale:** Sales-to-volume decrement is the most frequent TOCTOU scenario
in a taproom. BEGIN IMMEDIATE serializes concurrent sales. The auto-status
update on empty exercises the derived-state spec section.

### 7. Staff Management (Simple CRUD)
Staff members have name, role (brewer/server/manager -- informational only,
no auth), phone, email, hire_date, status (active/inactive). No login, no
permissions -- purely for record-keeping and reference.

**Rationale:** Staff is the simplest domain. It exercises standard CRUD with
no concurrency, derived state, or defense-in-depth needs. Useful as a
"control group" to keep agent count in range without adding complexity.

### 8. Dashboard
A single dashboard page showing:
- Active batches (in-progress across all statuses)
- Low-stock ingredients (below a threshold)
- Active taps with current beer and remaining volume
- Today's sales total

**Rationale:** Dashboard gives a summary view without adding new business
logic. It's a read-only blueprint -- no write operations, no concurrency
risks.

## MVP Domains (7 + dashboard)

| Domain | Tables | Agent Split |
|--------|--------|-------------|
| Recipes | recipes, recipe_ingredients | recipe_models + recipe_routes |
| Batches | batches | batch_models + batch_routes |
| Ingredients | ingredients | ingredient_models + ingredient_routes |
| Tanks | tanks | tank_models + tank_routes |
| Taps | taps | tap_models + tap_routes |
| Sales | sales | sale_models + sale_routes |
| Staff | staff | staff_models + staff_routes |
| Dashboard | (reads from all) | dashboard_routes |
| Core | (schema, db, auth, app) | core agent |
| Layout | (base template, CSS) | layout agent |
| Auth | (login/logout) | auth agent |

**Total: 19 agents** (7 domain x 2 [model + route] + core + layout + auth +
dashboard_routes = 19). This is at the low end of the 20-25 target. Could add
a recipe_ingredients model agent (split from recipe_models) and a tests agent
to reach 21.

### Agent Count Adjustment

To reach 22 agents:
1. **recipe_models** -> split into recipe_models + recipe_ingredient_models (the
   join table operations are complex enough to warrant separation)
2. **tests agent** -> writes smoke test / integration test file
3. **seed agent** -> writes seed data for development

**Final count: 22 agents**

## Concurrency Contract (New Spec Section -- Validation Target)

Every write function tagged with its concurrency requirement:

| Function | Tag | Reason |
|----------|-----|--------|
| create_recipe | SERIAL-SAFE | Pure INSERT, no race risk |
| update_recipe | SERIAL-SAFE | Single-row UPDATE by PK |
| delete_recipe | SERIAL-SAFE | CASCADE handles FK cleanup |
| create_batch | SERIAL-SAFE | Pure INSERT |
| start_brewing (planned->brewing) | NEEDS-BEGIN-IMMEDIATE | Tank assignment + inventory decrement (TOCTOU) |
| advance_batch_status | SERIAL-SAFE | Single-row status UPDATE (no side effects) |
| release_tank (conditioning->ready) | SERIAL-SAFE | Single-row NULL update |
| assign_tap (ready->tapped) | NEEDS-BEGIN-IMMEDIATE | Tap availability check (TOCTOU) |
| clear_tap (tapped->empty) | SERIAL-SAFE | Single-row NULL update + status change |
| create_ingredient | SERIAL-SAFE | Pure INSERT |
| update_stock | SERIAL-SAFE | Single-row UPDATE |
| create_tank | SERIAL-SAFE | Pure INSERT |
| assign_batch_to_tank | NEEDS-BEGIN-IMMEDIATE | Availability + capacity check (TOCTOU) |
| release_batch_from_tank | SERIAL-SAFE | Single-row NULL update |
| create_tap | SERIAL-SAFE | Pure INSERT |
| assign_batch_to_tap | NEEDS-BEGIN-IMMEDIATE | Tap availability check (TOCTOU) |
| create_sale | NEEDS-BEGIN-IMMEDIATE | Remaining volume decrement (TOCTOU) |
| create_staff | SERIAL-SAFE | Pure INSERT |
| update_staff | SERIAL-SAFE | Single-row UPDATE |

Functions tagged NEEDS-BEGIN-IMMEDIATE must include the full pattern:
```python
try:
    conn.execute('BEGIN IMMEDIATE')
    # re-check constraint inside transaction (authoritative)
    # perform write(s)
    # update derived state in same transaction
    conn.execute('COMMIT')
except Exception:
    conn.execute('ROLLBACK')
    raise
```

## Defense-in-Depth Matrix (New Spec Section -- Validation Target)

| Constraint | App Level (Route) | App Level (Model) | DB Level | Error Translation |
|-----------|-------------------|-------------------|----------|-------------------|
| Tank available for assignment | Flash "Tank is occupied" | Re-check in BEGIN IMMEDIATE, return None | CHECK(current_batch_id unique per non-null) | Route: flash. Model: return None triggers flash. |
| Tank capacity >= batch volume | Flash "Batch volume exceeds tank capacity" | Re-check in BEGIN IMMEDIATE | CHECK(capacity > 0) | Route: flash. Model: return None. |
| Sufficient ingredient stock | Flash "Insufficient {ingredient} stock" | Re-check each ingredient in BEGIN IMMEDIATE | CHECK(stock_qty >= 0) | Route: flash per ingredient. DB: IntegrityError -> generic "stock constraint violated" |
| Tap available for assignment | Flash "Tap already has a batch" | Re-check in BEGIN IMMEDIATE, return None | N/A (NULL check, not constraintable) | Route: flash. Model: return None. |
| Sale doesn't overdraw batch volume | Flash "Insufficient remaining volume" | Re-check in BEGIN IMMEDIATE | CHECK(remaining_volume_oz >= 0) | Route: flash. DB: IntegrityError -> "volume constraint violated" |
| Unique recipe name | Flash "Recipe name already exists" | N/A (single INSERT) | UNIQUE(name) | Route: catch IntegrityError -> flash |
| Unique staff email | Flash "Email already in use" | N/A (single INSERT) | UNIQUE(email) | Route: catch IntegrityError -> flash |
| Valid batch status transition | Flash "Invalid status transition" | Validate transition map | N/A (no CHECK on status flow) | Route: flash |

## Derived State (New Spec Section -- Validation Target)

| Derived Field | Source Table | Owning Agent | Trigger Event | Update Logic |
|--------------|-------------|--------------|---------------|-------------|
| batch.status (-> 'brewing') | batches | batch_models | start_brewing() | Set status='brewing' in same txn as inventory decrement |
| batch.status (-> 'empty') | sales | sale_models | create_sale() when remaining_volume_oz hits 0 | UPDATE batch status='empty', clear tap assignment |
| batch.remaining_volume_oz | sales | sale_models | create_sale() | Decrement by sale quantity in same txn |
| ingredient.stock_qty | recipe_ingredients | batch_models | start_brewing() | Decrement each ingredient by recipe qty in same txn |
| tank.current_batch_id | batches | batch_models | start_brewing() / release | Set on assign, NULL on release |
| tap.batch_id | batches | batch_models / sale_models | assign_tap() / batch empty | Set on assign, NULL when batch empties |

**Key rule:** The agent that writes the SOURCE data owns the derived state
update. Both writes happen in the same BEGIN IMMEDIATE transaction. No
cross-agent derived state is left implicit.

## Schema Sketch

### recipes
- id, name (UNIQUE), style, target_abv, notes, created_at, updated_at

### recipe_ingredients
- id, recipe_id (FK recipes), ingredient_id (FK ingredients),
  quantity, unit, created_at

### batches
- id, recipe_id (FK recipes), name, brew_date, status
  (planned/brewing/fermenting/conditioning/ready/tapped/empty),
  volume_gallons, remaining_volume_oz, tank_id (FK tanks, nullable),
  notes, created_at, updated_at

### ingredients
- id, name (UNIQUE), category (grain/hops/yeast/adjunct/other),
  stock_qty, unit, low_stock_threshold, created_at, updated_at

### tanks
- id, name (UNIQUE), capacity_gallons, tank_type (fermenter/brite/conditioning),
  current_batch_id (FK batches, nullable), notes, created_at, updated_at

### taps
- id, name (UNIQUE), position (integer), batch_id (FK batches, nullable),
  created_at, updated_at

### sales
- id, tap_id (FK taps), batch_id (FK batches), quantity_oz, sale_type
  (pint/half_pint/growler/case), price_cents, created_at

### staff
- id, name, role (brewer/server/manager), email (UNIQUE), phone,
  hire_date, status (active/inactive), created_at, updated_at

## Cross-Domain Dependencies

```
recipes ---[recipe_ingredients]---> ingredients
batches ---[recipe_id]---> recipes
batches ---[tank_id]---> tanks
taps ---[batch_id]---> batches
sales ---[tap_id]---> taps
sales ---[batch_id]---> batches
tanks ---[current_batch_id]---> batches
```

### Critical Flows (require TOCTOU guards)

1. **Start Brewing Flow:** batch(planned->brewing) + assign tank +
   decrement all recipe ingredients. Single BEGIN IMMEDIATE transaction.
   Checks: tank available, tank capacity, all ingredients in stock.

2. **Create Sale Flow:** INSERT sale + decrement batch.remaining_volume_oz.
   If remaining hits 0: set batch status='empty', clear tap.batch_id.
   Single BEGIN IMMEDIATE transaction.

3. **Assign Tap Flow:** Set tap.batch_id + set batch status='tapped'.
   Check: tap not already assigned. BEGIN IMMEDIATE transaction.

## Agent Ownership Map

| Agent | Files Owned | Cross-Agent Dependencies |
|-------|------------|------------------------|
| core | app/__init__.py, app/db.py, app/auth.py, app/filters.py, schema.sql | None (foundation) |
| layout | app/templates/base.html, app/static/style.css | Depends on: core |
| auth | app/templates/auth/*.html, app/auth_routes.py | Depends on: core |
| recipe_models | app/models/recipe_models.py | Depends on: core (db) |
| recipe_ingredient_models | app/models/recipe_ingredient_models.py | Depends on: core (db), recipe_models, ingredient_models |
| batch_models | app/models/batch_models.py | Depends on: core (db), recipe_ingredient_models (for inventory decrement) |
| ingredient_models | app/models/ingredient_models.py | Depends on: core (db) |
| tank_models | app/models/tank_models.py | Depends on: core (db) |
| tap_models | app/models/tap_models.py | Depends on: core (db) |
| sale_models | app/models/sale_models.py | Depends on: core (db), batch_models (derived state update) |
| staff_models | app/models/staff_models.py | Depends on: core (db) |
| recipe_routes | app/routes/recipe_routes.py, app/templates/recipes/*.html | Depends on: recipe_models, recipe_ingredient_models, ingredient_models |
| batch_routes | app/routes/batch_routes.py, app/templates/batches/*.html | Depends on: batch_models, recipe_models, tank_models, tap_models |
| ingredient_routes | app/routes/ingredient_routes.py, app/templates/ingredients/*.html | Depends on: ingredient_models |
| tank_routes | app/routes/tank_routes.py, app/templates/tanks/*.html | Depends on: tank_models |
| tap_routes | app/routes/tap_routes.py, app/templates/taps/*.html | Depends on: tap_models, batch_models |
| sale_routes | app/routes/sale_routes.py, app/templates/sales/*.html | Depends on: sale_models, tap_models |
| staff_routes | app/routes/staff_routes.py, app/templates/staff/*.html | Depends on: staff_models |
| dashboard_routes | app/routes/dashboard_routes.py, app/templates/dashboard/*.html | Depends on: batch_models, ingredient_models, tank_models, tap_models, sale_models |
| seed | seed.py | Depends on: all models |
| tests | test_smoke.py | Depends on: core (app factory) |

## Risks

1. **batch_models is the most complex agent.** It owns start_brewing() which
   touches 3 tables (batches, tanks, ingredients) in one transaction. If the
   spec doesn't prescribe the exact import paths for recipe_ingredient_models
   functions, the agent will invent names (FC1).

2. **sale_models owns batch status transition to 'empty'.** This is a cross-
   domain derived state update. If the spec doesn't explicitly declare this in
   the Derived State section, the sale_models agent won't know it's responsible
   (FC44).

3. **recipe_ingredient_models is a supporting agent** that provides utility
   functions consumed by both recipe_routes and batch_models. Its API surface
   must be precisely prescribed in the Export Names Table.

## Feed-Forward
- **Hardest decision:** Where to put the start_brewing() function. It touches
  batches, tanks, and ingredients -- could live in batch_models, tank_models,
  or a shared module. Chose batch_models because the batch is the primary
  entity being modified (status change). The tank and ingredient updates are
  side effects owned by the batch transition.
- **Rejected alternatives:** Multi-role RBAC (adds IDOR complexity without
  exercising the 3 new spec sections), separate "brewing_operations" module
  (adds artificial abstraction), time-based automatic status transitions
  (adds cron complexity beyond scope).
- **Least confident:** Whether the sale_models agent will correctly implement
  the derived state chain (sale -> decrement volume -> check if empty ->
  update batch status -> clear tap). This is a 4-step side effect chain inside
  one transaction. If ANY step is missing, data integrity breaks silently.
  The Derived State spec section must prescribe this chain explicitly.
