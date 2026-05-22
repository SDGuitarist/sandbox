---
status: pending
priority: p2
issue_id: "043"
tags: [code-review, python-quality, consistency, brewops]
---

# Lazy Import in recipe_routes.py + Unused Import in __init__.py

## Problem Statement
1. `recipe_routes.py` line 187 has `from app.models.ingredient_models import get_ingredient` inside a function body, but `get_all_ingredients` is already imported at the top from the same module.
2. `app/__init__.py` line 21 has unused `from app.auth import login_required  # noqa: F401`.

## Findings
- Python reviewer: P1-3, P2-3
- Architecture reviewer: L1
- Simplicity reviewer: confirmed

## Proposed Solution
1. Move `get_ingredient` to the top-level import in recipe_routes.py
2. Remove unused import in __init__.py

## Affected Files
- `app/routes/recipe_routes.py` line 13 and 187
- `app/__init__.py` line 21

## Acceptance Criteria
- [ ] No function-level imports in route files
- [ ] No unused imports with noqa suppression
