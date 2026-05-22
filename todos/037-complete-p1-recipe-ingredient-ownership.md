---
status: pending
priority: p1
issue_id: "037"
tags: [code-review, security, data-integrity, brewops]
---

# Recipe Ingredient Removal Lacks Ownership Verification

## Problem Statement
`recipe_routes.py` `remove_ingredient` route (lines 200-213) verifies the recipe exists but does NOT verify that `ri_id` belongs to `recipe_id`. A user can craft a POST to `/recipes/1/ingredients/999/delete` where ri_id=999 belongs to recipe 5, and it would be deleted.

## Findings
- Security reviewer: H3
- Data-integrity reviewer: M1

## Proposed Solution
Change the delete query to include both IDs:
```python
ri = conn.execute(
    'SELECT * FROM recipe_ingredients WHERE id = ? AND recipe_id = ?',
    (ri_id, recipe_id)
).fetchone()
if ri is None:
    abort(404)
```

## Affected Files
- `app/routes/recipe_routes.py` lines 200-213
- `app/models/recipe_ingredient_models.py` (remove_recipe_ingredient function)

## Acceptance Criteria
- [ ] Cannot delete recipe_ingredient belonging to a different recipe
- [ ] Returns 404 when ri_id doesn't belong to recipe_id
