---
status: pending
priority: p1
issue_id: "033"
tags: [code-review, data-integrity, schema, brewops]
---

# No UNIQUE Constraint on recipe_ingredients(recipe_id, ingredient_id)

## Problem Statement
The `recipe_ingredients` table allows the same ingredient to be added to the same recipe multiple times. Neither the schema, model, nor route layer prevents this. When `start_brewing` reads recipe_ingredients to decrement stock, it decrements once per row -- duplicate entries cause double stock decrement.

## Findings
- Data-integrity reviewer: HIGH -- double ingredient rows cause over-decrement of inventory
- Pattern reviewer: confirmed no dedup check in add_recipe_ingredient route

## Proposed Solution
Add `UNIQUE(recipe_id, ingredient_id)` to schema.sql, and catch IntegrityError in the route handler with a flash message "This ingredient is already in the recipe."

## Affected Files
- `schema.sql` lines 22-29 (recipe_ingredients table)
- `app/routes/recipe_routes.py` lines 160-197 (add_ingredient handler)

## Acceptance Criteria
- [ ] Adding the same ingredient to a recipe twice is rejected with a clear error
- [ ] DB constraint prevents duplicates even if app-level check is bypassed
