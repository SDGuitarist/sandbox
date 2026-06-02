---
status: pending
priority: p2
issue_id: "059"
tags: [code-review, cleanup, dead-code, run-063]
dependencies: []
---

# 059 — Ghost files from BrewOps shipped in film PM app

## Problem Statement

The film PM app contains 9+ files from the prior BrewOps project that were
never cleaned up from the sandbox repo root:

**`app/db.py`** — BrewOps database module using `brewops.db` as default path.
Not used by any film PM blueprint. Conflicts conceptually with `app/database.py`.

**`app/routes/`** (8 files):
- `auth_routes.py`, `batch_routes.py`, `dashboard_routes.py`,
- `ingredient_routes.py`, `recipe_routes.py`, `sale_routes.py`,
- `staff_routes.py`, `tank_routes.py`

**`app/models/` (8 leftover models):**
- `batch_models.py`, `ingredient_models.py`, `recipe_ingredient_models.py`,
- `recipe_models.py`, `sale_models.py`, `staff_models.py`, `tank_models.py`,
- `tap_models.py`

**`app/templates/`** (leftover dirs): `batches/`, `ingredients/`, `recipes/`,
`sales/`, `staff/`, `tanks/`, `taps/`

## Findings

- None of the BrewOps files are imported by any film PM blueprint.
- `app/db.py` could confuse new developers — it defines `get_db()` but
  connects to `brewops.db`, not `filmpm.db`.
- The leftover templates inflate the template directory and could cause
  render_template to find wrong templates in edge cases.
- Ghost models import `sqlite3` and define SQL against BrewOps schema tables
  that don't exist in `schema.sql`.

## Proposed Solutions

### Option A: Delete all BrewOps remnants (Recommended)
```
rm app/db.py
rm -rf app/routes/
rm app/models/{batch,ingredient,recipe_ingredient,recipe,sale,staff,tank,tap}_models.py
rm -rf app/templates/{batches,ingredients,recipes,sales,staff,tanks,taps}/
```
Effort: Small. Risk: Low (none of these are imported by film PM).

### Option B: Move to /tmp or archive directory
Retain for reference but move out of the app package.
Effort: Small. Less clean.

## Recommended Action

Option A — delete them. They were never part of the film PM spec.

## Technical Details

- **Safety check:** Run `grep -r "from app.db import\|from app.routes\|batch_models\|recipe_models\|sale_models\|staff_models\|tank_models\|tap_models" app/blueprints/` to confirm no blueprint imports them before deleting.

## Acceptance Criteria

- [ ] `app/db.py` deleted
- [ ] `app/routes/` directory deleted
- [ ] BrewOps model files deleted from `app/models/`
- [ ] BrewOps template directories deleted from `app/templates/`
- [ ] All 18/18 smoke tests still pass after deletion

## Work Log

- 2026-06-02: Identified during Run 063 review — ghost files from previous project in same sandbox repo
