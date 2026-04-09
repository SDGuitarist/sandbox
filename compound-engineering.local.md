# Review Context -- Sandbox (Recipe Organizer Swarm Build)

## Risk Chain

**Brainstorm risk:** "Ingredient linking UX on recipe form -- adding multiple
ingredients with quantities via plain HTML could be clunky."

**Plan mitigation:** Minimal JS (clone/remove rows), parallel arrays via
getlist(), try/except on parsing, deduplication by ingredient_id.
Added `verify_first: true` to feed_forward frontmatter.

**Work risks (from Feed-Forward):**
1. form.getlist() parallel array desync via zip() truncation.
   Fixed post-review: added length equality check before zip().
2. Missing created_at index causing full table scan on recipe list.
   Fixed post-review: added idx_recipes_created_at.

**Review resolution:** 2 P1, 5 P2, 5 P3 across 5 review agents.
- P1: parallel array desync (fixed), missing created_at index (fixed)
- P2: two-connection race in edit routes, validation duplication, no ingredient_id existence check, correlated subquery, unbounded dropdown
- P3: type annotations, unit validation, integer upper bounds, delete existence check, executemany
- Zero critical security vulnerabilities. SQL injection and XSS properly handled.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| recipe-organizer/app/blueprints/recipes/routes.py | 5 routes, validation, ingredient parsing | Form parsing, transaction boundaries |
| recipe-organizer/app/models.py | 18 model functions, search | SQL construction, batch fetching |
| recipe-organizer/app/db.py | Context manager, init_db | Transaction semantics |

## Deferred P2/P3 Items

- Two-connection race in edit routes (ingredient + recipe)
- Duplicated validation logic (~80 LOC between create/edit)
- No ingredient_id existence check before INSERT
- Correlated subquery in get_all_ingredients
- Unbounded ingredient dropdown (limit=1000 with subquery)
- Missing type annotations in models.py
- No unit length validation in form parsing
- No integer upper bounds on servings/times
- Delete without existence check
- executemany optimization for set_recipe_ingredients
