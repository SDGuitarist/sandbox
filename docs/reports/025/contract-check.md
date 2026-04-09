# Contract Check: recipe-organizer

**Date:** 2026-04-09
**App:** `/Users/alejandroguillen/Projects/sandbox/recipe-organizer/`
**Plan:** `docs/plans/2026-04-09-feat-recipe-organizer-plan.md`

## STATUS: PASS

All six contracts satisfied. Zero violations found.

---

## 1. Endpoint Registry

Every `url_for()` name used in templates resolves to a real Flask route function.

| Template | url_for() call | Route function | Status |
|----------|---------------|----------------|--------|
| layout.html | `recipes.index` | `recipes/routes.py:index` | PASS |
| layout.html | `ingredients.index` | `ingredients/routes.py:index` | PASS |
| layout.html | `search.search` | `search/routes.py:search` | PASS |
| layout.html | `static` (filename) | Flask built-in | PASS |
| recipes/list.html | `recipes.create` | `recipes/routes.py:create` | PASS |
| recipes/list.html | `recipes.detail` (recipe_id) | `recipes/routes.py:detail` | PASS |
| recipes/detail.html | `recipes.edit` (recipe_id) | `recipes/routes.py:edit` | PASS |
| recipes/detail.html | `recipes.delete` (recipe_id) | `recipes/routes.py:delete` | PASS |
| ingredients/list.html | `ingredients.create` | `ingredients/routes.py:create` | PASS |
| ingredients/list.html | `ingredients.edit` (ingredient_id) | `ingredients/routes.py:edit` | PASS |
| ingredients/list.html | `ingredients.delete` (ingredient_id) | `ingredients/routes.py:delete` | PASS |
| ingredients/form.html | `ingredients.index` | `ingredients/routes.py:index` | PASS |
| search/results.html | `search.search` (q, page) | `search/routes.py:search` | PASS |
| search/results.html | `recipes.detail` (recipe_id) | `recipes/routes.py:detail` | PASS |
| errors/404.html | `recipes.index` | `recipes/routes.py:index` | PASS |
| errors/403.html | `recipes.index` | `recipes/routes.py:index` | PASS |

**No orphan url_for() references.**

---

## 2. Template Render Context

Every `{{ var }}` used in a template is provided by the corresponding `render_template()` call or by the `inject_csrf` context processor.

| Template | Variables used | Source | Status |
|----------|--------------|--------|--------|
| recipes/list.html | recipes, ingredients_map, page, total_pages | `recipes/routes.py:index` | PASS |
| recipes/detail.html | recipe, ingredients, csrf_token | `recipes/routes.py:detail` + context_processor | PASS |
| recipes/form.html | recipe, all_ingredients, selected_ingredients, is_edit, csrf_token | `recipes/routes.py:create` and `edit` + context_processor | PASS |
| ingredients/list.html | ingredients, page, total_pages, csrf_token | `ingredients/routes.py:index` + context_processor | PASS |
| ingredients/form.html | ingredient, is_edit, csrf_token | `ingredients/routes.py:create` and `edit` + context_processor | PASS |
| search/results.html | recipes, ingredients_map, query, page, total_pages | `search/routes.py:search` | PASS |
| errors/404.html | message | `__init__.py:not_found` | PASS |
| errors/403.html | message | `__init__.py:forbidden` | PASS |

**No unbound template variables.**

---

## 3. Model Imports

Every model function imported in route files exists in `models.py` with the correct signature.

### recipes/routes.py imports
| Import | models.py signature | Status |
|--------|-------------------|--------|
| ITEMS_PER_PAGE | constant = 20 | PASS |
| create_recipe | (conn, title, description, instructions, servings, prep_time_min, cook_time_min) | PASS |
| delete_recipe | (conn, recipe_id) | PASS |
| get_all_ingredients | (conn, limit, offset) | PASS |
| get_all_recipes | (conn, limit, offset) | PASS |
| get_ingredients_for_recipe | (conn, recipe_id) | PASS |
| get_ingredients_for_recipes | (conn, recipe_ids) | PASS |
| get_recipe | (conn, recipe_id) | PASS |
| get_recipe_count | (conn) | PASS |
| set_recipe_ingredients | (conn, recipe_id, ingredients_data) | PASS |
| update_recipe | (conn, recipe_id, title, description, instructions, servings, prep_time_min, cook_time_min) | PASS |

### ingredients/routes.py imports
| Import | models.py signature | Status |
|--------|-------------------|--------|
| ITEMS_PER_PAGE | constant = 20 | PASS |
| create_ingredient | (conn, name) | PASS |
| delete_ingredient | (conn, ingredient_id) | PASS |
| get_all_ingredients | (conn, limit, offset) | PASS |
| get_ingredient | (conn, ingredient_id) | PASS |
| get_ingredient_count | (conn) | PASS |
| update_ingredient | (conn, ingredient_id, name) | PASS |

### search/routes.py imports
| Import | models.py signature | Status |
|--------|-------------------|--------|
| ITEMS_PER_PAGE | constant = 20 | PASS |
| get_ingredients_for_recipes | (conn, recipe_ids) | PASS |
| search_recipe_count | (conn, query) | PASS |
| search_recipes_by_ingredients | (conn, query, limit, offset) | PASS |

**All call sites pass arguments matching the function signatures.**

---

## 4. Blueprint Registration

| Blueprint variable | Blueprint name | Registered in app factory | url_prefix | Status |
|-------------------|---------------|--------------------------|------------|--------|
| recipes_bp | "recipes" | `app.register_blueprint(recipes_bp, url_prefix="/recipes")` | /recipes | PASS |
| ingredients_bp | "ingredients" | `app.register_blueprint(ingredients_bp, url_prefix="/ingredients")` | /ingredients | PASS |
| search_bp | "search" | `app.register_blueprint(search_bp, url_prefix="/search")` | /search | PASS |

**No mismatched blueprint names.**

---

## 5. CSRF

Every `<form method="post">` includes `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`.

| Template | Form | CSRF token present | Status |
|----------|------|--------------------|--------|
| recipes/form.html | POST (create/edit recipe) | Yes (line 9) | PASS |
| recipes/detail.html | POST (delete recipe) | Yes (line 48) | PASS |
| ingredients/form.html | POST (create/edit ingredient) | Yes (line 9) | PASS |
| ingredients/list.html | POST (delete ingredient) | Yes (line 23) | PASS |
| search/results.html | GET (search) | N/A (GET form) | PASS |

Server-side enforcement confirmed: `csrf_protect()` in `__init__.py` checks token on every POST request, aborts 403 on mismatch.

**No unprotected POST forms.**

---

## 6. Anti-patterns

| Anti-pattern | Found | Status |
|-------------|-------|--------|
| Bare `get_db()` call (not context manager) | No -- every call uses `with get_db() as conn:` | PASS |
| `create_*` return treated as Row | No -- `create_recipe` returns `cur.lastrowid` (int), used as int in `url_for()` redirect. `create_ingredient` return value is not used at all. | PASS |
| `executescript` inside `get_db` | No -- `executescript` only used in `init_db()` which opens its own raw connection outside `get_db` | PASS |

**No anti-patterns detected.**
