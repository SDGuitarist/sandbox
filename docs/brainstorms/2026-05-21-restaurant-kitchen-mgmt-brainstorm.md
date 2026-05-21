---
project: restaurant-kitchen-mgmt
date: 2026-05-21
run: "051"
status: complete
feed_forward:
  risk: "30+ agent swarm at this feature breadth may produce inconsistent UX patterns across 12 blueprints"
  verify_first: true
---

# Brainstorm: Restaurant & Kitchen Management System (RestaurantOps)

## What Are We Building?

A single-location, single-restaurant management system for internal operations staff.
Flask + SQLite + Jinja2. Server-rendered, no JS frameworks. Operational workflows
over customer-facing polish.

**Target user:** Restaurant manager / kitchen staff / front-of-house staff.
**Single role model:** Admin (full access). No multi-role auth for MVP — simplest
role model that works. One shared password protects all routes.

## Domain Scope

### In Scope (MVP)

1. **Menu Management** — CRUD menu items, assign to categories, set prices,
   mark available/unavailable, link to recipes
2. **Recipes** — CRUD recipes with step-by-step instructions, link ingredients
   with quantities, auto-calculate cost from ingredient prices
3. **Ingredients** — CRUD ingredients with unit cost, unit of measure, supplier
   link, allergen tags
4. **Inventory & Stock Movements** — Track current stock levels per ingredient,
   record stock receipts (from purchase orders) and manual adjustments,
   low-stock threshold alerts
5. **Supplier Management** — CRUD suppliers with contact info
6. **Purchase Orders** — Create POs against suppliers with line items (ingredients
   + quantities), receive POs to update inventory, track PO status
   (draft → submitted → received → closed)
7. **Customer Orders** — In-house order entry (table + items), kitchen prep
   status workflow (pending → preparing → ready → served → closed),
   auto-deduct inventory on order confirmation
8. **Table Reservations** — Book tables with date/time/party size/name,
   table status board (available → reserved → occupied → needs cleaning)
9. **Dining Room / Tables** — CRUD tables with capacity and location/zone
10. **Staff Scheduling** — CRUD staff members, create weekly shifts with
    role/start/end times, view schedule by day/week
11. **Allergen Tracking** — Tag ingredients with allergens, auto-rollup to
    recipes and menu items, display warnings on menu
12. **Daily Specials** — Create daily specials linked to menu items or
    standalone, set date range, display on dashboard
13. **Customer Reviews** — Simple review entry (rating 1-5, comment, date),
    display average rating per menu item, operational summary view

### Out of Scope

- Payments / POS hardware — orders track lifecycle, not money collection
- Delivery platform integrations
- Payroll — staff scheduling is shift planning only
- Multi-location support
- Customer loyalty programs
- Third-party APIs
- Real-time kitchen display (SSE/WebSocket) — use page refresh
- Customer-facing ordering portal
- Multi-role auth with granular permissions

## Key Design Decisions

### Decision 1: Single Admin Password vs. User Accounts

**Chosen:** Single shared admin password (environment variable `ADMIN_PASSWORD`).
Login sets a session cookie. All routes require login.

**Why:** The spec says "prefer the smallest role model that still works."
A single-location restaurant doesn't need per-user permissions for MVP.
Staff scheduling tracks staff as data entities, not as app users.

**Rejected:** Per-user accounts with roles. Adds complexity (registration,
password hashing per user, role decorators, IDOR checks) without MVP value.

### Decision 2: Money Storage

**Chosen:** Integer cents everywhere. All cost/price columns are INTEGER
(cents). Jinja `|dollars` filter for display. Form inputs accept decimal,
multiply by 100 on save.

**Why:** Proven pattern from personal-finance-tracker and invoice-crm.
Avoids floating-point rounding errors.

### Decision 3: Order → Inventory Deduction Timing

**Chosen:** Deduct inventory when order status moves to "preparing" (not
on initial order entry). This allows order corrections before kitchen starts.

**Why:** Restaurant ops reality — orders get modified between entry and
kitchen handoff. Deducting on "preparing" is the commitment point.

**Rejected:** Deduct on order creation (too early, corrections cause negative
adjustments). Deduct on "served" (too late, inventory doesn't reflect what's
being used).

### Decision 4: Allergen Rollup Strategy

**Chosen:** Compute allergen rollup on read (JOIN through recipe_ingredients
→ ingredients → ingredient_allergens). No denormalized allergen cache.

**Why:** Ingredient count is small enough (<500) that JOIN performance is fine.
Denormalized cache creates staleness bugs when ingredients are updated.

### Decision 5: Recipe Cost Calculation

**Chosen:** Compute on read. `recipe_cost = SUM(ingredient.unit_cost_cents *
recipe_ingredient.quantity)`. Display alongside menu item price for margin
visibility.

**Why:** Same reasoning as allergens — small dataset, computed is simpler
and always fresh. No background jobs needed.

### Decision 6: Blueprint Organization

**Chosen:** One blueprint per feature domain (12 total):

| Blueprint | Prefix | Domain |
|-----------|--------|--------|
| auth | /auth | Login/logout |
| dashboard | / | Home dashboard with summary stats |
| menu | /menu | Menu items and categories |
| recipes | /recipes | Recipes with ingredients |
| ingredients | /ingredients | Ingredient CRUD |
| inventory | /inventory | Stock levels, movements, alerts |
| suppliers | /suppliers | Supplier CRUD |
| purchase_orders | /purchase-orders | PO lifecycle |
| orders | /orders | Customer order lifecycle |
| tables | /tables | Table/dining room management |
| reservations | /reservations | Table reservations |
| staff | /staff | Staff members and scheduling |
| specials | /specials | Daily specials |
| reviews | /reviews | Customer reviews |

Plus: core (app factory, db, models) and layout (base template, static).

### Decision 7: State Machines

Two explicit state machines:

**Order status:** `pending → preparing → ready → served → closed`
- `pending → preparing`: triggers inventory deduction
- Any state can → `cancelled` (restores inventory if was preparing+)

**Purchase order status:** `draft → submitted → received → closed`
- `received`: triggers stock receipt (inventory increase)

**Table status:** `available → reserved → occupied → needs_cleaning → available`
- Driven by reservation times and manual staff updates

### Decision 8: Database Structure

Single `restaurant.db` file. All tables in one database. No table prefixing.
Foreign keys ON. WAL mode. busy_timeout=5000.

Junction tables for M2M:
- `recipe_ingredients` (recipe_id, ingredient_id, quantity, unit)
- `ingredient_allergens` (ingredient_id, allergen_id)
- `order_items` (order_id, menu_item_id, quantity, unit_price_cents)
- `purchase_order_items` (purchase_order_id, ingredient_id, quantity, unit_cost_cents)

### Decision 9: No JavaScript Framework

Server-rendered everything. Page refreshes for state changes. No HTMX, no
Alpine.js, no React. Bootstrap 5 via CDN for styling only.

**Why:** Spec says "favor simple, server-rendered workflows." No interaction
in this app requires client-side state management.

### Decision 10: Staff as Data, Not Users

Staff members are database records (name, role, phone, email). They are NOT
app users. The staff scheduling feature creates shift records linked to staff
member IDs. No staff login, no per-staff permissions.

## Cross-Boundary Flows (Must Get Right)

### Flow 1: Recipe → Cost → Menu Pricing
```
ingredients.unit_cost_cents → recipe_ingredients.quantity → computed recipe cost
→ displayed alongside menu_item.price_cents for margin visibility
```

### Flow 2: Recipe → Allergen Rollup → Menu Display
```
ingredient_allergens → JOIN recipe_ingredients → computed allergen set per recipe
→ displayed as warnings on menu item detail and order entry
```

### Flow 3: Purchase Order → Stock Receipt → Inventory
```
purchase_order status → 'received' → create stock_movements (type='receipt')
→ update inventory current_stock += received quantity
```

### Flow 4: Order Entry → Kitchen Prep → Inventory Consumption
```
order created (pending) → status changed to 'preparing'
→ create stock_movements (type='consumption') per order item per recipe ingredient
→ update inventory current_stock -= consumed quantity
```

### Flow 5: Reservation → Table Status
```
reservation created → table status = 'reserved' (at reservation time)
→ guest arrives → table status = 'occupied'
→ guest leaves → table status = 'needs_cleaning'
→ cleaned → table status = 'available'
```

## Swarm Agent Strategy (Target: 30+ Agents)

Vertical split by feature domain. Each agent owns one blueprint + its models
+ its templates. Core infrastructure agents handle shared concerns.

Estimated agent count: 32-35 agents (14 blueprint agents + core-infra +
layout + database schema + tests + static assets + potential splits for
large blueprints like orders and purchase_orders).

## Risks and Concerns

1. **Inventory deduction atomicity** — Order with 5 items touching 15
   ingredients needs to be atomic. Must prescribe BEGIN IMMEDIATE in spec.
2. **30+ agent consistency** — Flash messages, error display, form styling
   must be in Coordinated Behaviors table.
3. **Recipe cost as computed value** — If ingredient prices change, all
   recipe costs change retroactively. Acceptable for MVP (no historical
   cost tracking).
4. **Table status driven by reservations** — Automatic status transitions
   at reservation time require either a cron job or manual "mark arrived"
   button. Choosing manual for MVP simplicity.

## Feed-Forward

- **Hardest decision:** Order → inventory deduction timing. "Preparing" is
  the right commitment point but adds complexity to the cancellation flow
  (must restore inventory). Simpler alternatives (deduct on creation, deduct
  on served) have worse operational semantics.
- **Rejected alternatives:** Per-user accounts with roles (too complex for
  single-location MVP), denormalized allergen cache (staleness risk),
  JavaScript framework for kitchen display (spec says server-rendered),
  deduct inventory on order creation (premature commitment).
- **Least confident:** Whether 30+ agents at this feature breadth will
  produce consistent UX patterns across 14 blueprints. The Coordinated
  Behaviors table must be extremely prescriptive (flash messages, form
  styling, error display, pagination, table styling, empty states) or
  we'll get 14 different UX dialects.

## Refinement Findings

**Gaps found:** 5 | **STATUS: PASS**

1. **CSP-CDN mismatch** — Bootstrap 5 via CDN + scaffold agent adding
   `script-src 'self'` = silently broken JS. Spec must prescribe CSP
   domains or explicitly omit CSP. (Source: gigsheet-31-agent)

2. **PRAGMA per-connection** — `busy_timeout=5000` is per-connection, not
   per-database. Must be in Coordinated Behaviors table, not just startup
   config. 5+ agents write to inventory. (Source: gigsheet-31-agent)

3. **Context checkpoint expected** — 32-35 agents scores ~49.5 on
   orchestration-load heuristic (threshold 30). `PAUSED_FOR_CONTEXT` is
   the expected exit. Plan must acknowledge tail-resume is required.
   (Source: autopilot-context-window-optimization)

4. **zip() truncation on parallel arrays** — `recipe_ingredients`,
   `order_items`, `purchase_order_items` all use `getlist()` parallel
   arrays. Must prescribe length equality check before `zip()`.
   (Source: recipe-organizer-swarm-build)

5. **Pre-swarm spec consistency gate** — Mandatory at 30+ agents. Catches
   cross-section contradictions (CHECK constraints, template entries, URL
   patterns) before all agents build against broken spec.
   (Source: venueconnect-25-agent)
