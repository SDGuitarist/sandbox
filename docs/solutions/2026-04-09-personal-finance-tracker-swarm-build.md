---
title: "Personal Finance Tracker Swarm Build"
date: 2026-04-09
category: swarm-build
tags: [flask, sqlite, swarm, cents-conversion, on-delete-set-default, budget-upsert, batch-form]
module: finance-tracker
symptom: "Need to build a multi-blueprint Flask app with money handling, monthly budgets, and category-based spending tracking"
root_cause: "Standard CRUD + aggregate dashboard pattern with integer cents storage and ON DELETE SET DEFAULT for category reassignment"
key_lesson: "ON DELETE SET DEFAULT works correctly in SQLite for reassigning orphaned rows, but requires PRAGMA foreign_keys=ON per connection and DEFAULT on the column definition"
agents: 3
merge_conflicts: 0
post_assembly_fixes: 1
mismatch_count: 1
---

# Personal Finance Tracker -- Swarm Build

## Problem

Build a personal finance tracker with spending categories, transactions stored
as integer cents, monthly budgets per category, and a dashboard showing
budget-vs-actual. Three-agent swarm (core, routes, templates), 23 files.

## Solution

23 source files built by 3 swarm agents. All verification gates passed:
ownership (0 violations), contract check (1 fix applied -- doubled route
prefixes), smoke test (15/15 + 9/9 post-fix).

## Key Lessons

### 1. ON DELETE SET DEFAULT Works in SQLite (Feed-Forward Verified)

The brainstorm flagged ON DELETE SET DEFAULT as the "least confident" area.
The plan required it for reassigning transactions to "Uncategorized" (id=1)
when a category is deleted. Smoke test confirmed: deleting category id=2
correctly set all its transactions to category_id=1.

**Requirements for ON DELETE SET DEFAULT to work:**
- Column must have `DEFAULT 1` in the CREATE TABLE statement
- `PRAGMA foreign_keys=ON` must be set on every connection (not persistent)
- The default value (category id=1) must exist in the referenced table
- Seed the fallback row (INSERT OR IGNORE) in schema.sql

**Lesson:** ON DELETE SET DEFAULT is a reliable alternative to CASCADE when
you need to preserve child rows. Trust it, but always verify with a smoke
test since it's uncommon.

### 2. Cents Conversion Layer Needs Defense in Depth

The plan correctly identified cents conversion as the highest-risk area.
The deepening phase added critical guards to `dollars_to_cents`:
- Reject NaN and Inf (via `math.isnan`/`math.isinf`)
- Reject amounts that round to 0 cents
- Cap at $999,999.99
- Validate with `float()` then `int(round(value * 100))`

Review found an additional gap: the transaction edit form must prefill the
dollar amount (`'%.2f' % (txn['amount'] / 100)`), not raw cents. The Jinja2
`|dollars` filter handles display, but form inputs need manual conversion.

**Lesson:** Money conversion has TWO surfaces: display (use a filter) and
form prefill (manual division). Both must be correct. The `|dollars` filter
is not enough -- form inputs are a separate path.

### 3. Route Prefix Doubling is a Swarm-Specific Bug Pattern

The routes agent created decorators with full paths (`@bp.route("/categories/")`)
while the app factory sets `url_prefix="/categories"`. Result: doubled URLs
(`/categories/categories/`). This is the first time this bug appeared in
sandbox swarm builds because prior apps either used single-level routes or
the spec was explicit about relative paths.

**Root cause:** The spec said "paths" in the endpoint registry but didn't
clarify whether they were absolute or relative to the blueprint prefix.

**Fix:** Spec contract checker caught it. One-line fix per route decorator.

**Lesson:** The shared interface spec must explicitly state: "Route decorator
paths are RELATIVE to the blueprint url_prefix. Use `/` not `/categories/`."
Add this to the spec template.

### 4. Budget Batch Form is Simpler Than Per-Budget CRUD

The brainstorm rejected per-budget CRUD routes (4 extra routes) in favor of
a single batch form. This was the right call:
- 1 GET + 1 POST route vs 4 routes
- Single page shows all categories for a month
- Empty field = remove budget, non-empty = upsert
- `ON CONFLICT DO UPDATE` handles the upsert pattern cleanly

**Lesson:** When the entity (budget) is always viewed in the context of a
parent (month), a batch form is simpler than individual CRUD routes.

### 5. Deepening Caught 11 Issues Before Any Code Was Written

The 6 deepening agents (architecture, security, performance, simplicity,
pattern, specflow) produced 11 improvements that were applied to the plan:
- Moved dashboard/budget routes from `__init__.py` to a views blueprint
- Extracted utils.py for pure conversion functions
- Replaced N+1 budget queries with batch `get_budgets_for_month`
- Added composite index for category+date filtering
- Changed LIKE to date range predicates for index use
- Cut `get_monthly_total` (derive from dashboard data)
- Added max amount cap and NaN/Inf rejection
- Added year_month format validation
- Added delete confirmation for categories
- Budget POST flashes errors instead of silent skip

**Lesson:** Run simplicity + security + performance review during planning,
not just after implementation. The deepening phase is the highest-ROI step
for preventing post-build fixes.

## Swarm Path Results

| Metric | Value |
|--------|-------|
| Agents | 3 (core: 7 files, routes: 6 files, templates: 10 files) |
| Total files | 23 |
| Total LOC | ~1,592 |
| Merge conflicts | 0 |
| Ownership violations | 0 |
| Contract check | 1 fail (route prefix doubling), fixed |
| Smoke tests | 15/15 pass |
| Review findings | 1 P1, 4 P2, 2 P3 |
| P1 fixes applied | 1/1 (transaction_date validation) |
| P2 fixes applied | 4/4 |
| P3 fixes applied | 1/2 (color hex; deferred render helper) |

## Risk Resolution

**Brainstorm risk:** "Cents conversion layer -- every form input must multiply
by 100, every display must divide by 100."

**What actually happened:** The conversion layer worked correctly on first
build. The `|dollars` Jinja2 filter and `dollars_to_cents()` function covered
all paths. However, the security review found edge cases (NaN, Inf, amounts
rounding to 0 cents) that the deepening phase had already addressed.

**Plan risk:** "ON DELETE SET DEFAULT behavior in SQLite is uncommon."

**What actually happened:** It works exactly as documented. The smoke test
verified category_id 2->1 on deletion. The key requirement is PRAGMA
foreign_keys=ON per connection AND a DEFAULT value on the column.

**Lesson:** The Feed-Forward framework correctly identified both risk areas.
Both were verified in the smoke test. Trust the uncertainty signal from
brainstorm -- when you flag something as "least confident," it deserves
explicit verification.

## What Could Be Better

1. Route prefix spec should explicitly say "relative to blueprint prefix"
2. Transaction routes have ~40 lines of duplicated fetch-and-rerender logic
3. `get_available_months` does a full-table scan with substr() -- add a
   `year_month` column to transactions if scale matters
