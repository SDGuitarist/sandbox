---
title: "feat: Recipe Organizer with Ingredient Search"
type: feat
status: active
date: 2026-04-09
origin: docs/brainstorms/2026-04-09-recipe-organizer-brainstorm.md
swarm: true
agents: 3
feed_forward:
  risk: "Ingredient linking UX on recipe form -- adding multiple ingredients with quantities via plain HTML could be clunky. Form submission flow for add/remove ingredient rows is unverified."
  verify_first: true
deepened: 2026-04-09
---

# feat: Recipe Organizer with Ingredient Search

## Enhancement Summary

**Deepened on:** 2026-04-09
**Review agents used:** 7 (quality-gate, architecture, security, performance, pattern, simplicity, specflow)

### Key Improvements from Deepening
1. Removed sort system (YAGNI -- personal app, <500 recipes)
2. Dropped ingredient detail page (search already covers this)
3. Dropped `default_unit` column (unused by UX)
4. Fixed `get_db()` to always commit/rollback (match gold standard)
5. Composite PK on junction table (match gold standard)
6. Models use `limit`/`offset` not `page` (match gold standard)
7. Capped search terms at 10 (DoS prevention)
8. Added error handlers (404, 403) and empty states
9. Added `updated_at` update in `update_recipe`
10. Added try/except on form int/float parsing
11. Added duplicate ingredient deduplication in form parsing

---

## Overview

Personal recipe organizer with ingredient-based search. Store recipes, manage a
shared ingredient pool, link ingredients to recipes with quantities, and find
recipes by ingredient name. Flask + SQLite + Jinja2, following the
bookmark-manager pattern exactly.

(see brainstorm: docs/brainstorms/2026-04-09-recipe-organizer-brainstorm.md)

## Problem Statement

No centralized place to store and search personal recipes. The core value
proposition is answering "what can I make with X?" -- searching recipes by
ingredient rather than just by title.

## Proposed Solution

Two-domain Flask app (recipes + ingredients) with a search blueprint, shared
ingredient pool, and junction table. LIKE-based multi-term AND search across
ingredient names. Manual session-based CSRF. SQLite with WAL mode. Follows
bookmark-manager architecture verbatim.

---

## Plan Quality Gate

1. **What exactly is changing?** New `recipe-organizer/` directory with ~15 files: app factory, db layer, models, 3 blueprints (recipes, ingredients, search), templates, static CSS, schema, run.py.
2. **What must not change?** No files outside `recipe-organizer/` are modified. No changes to other sandbox apps. No new pip dependencies beyond `flask>=3.0`.
3. **How will we know it worked?** Smoke test: create recipe, add ingredients, search by ingredient name, edit recipe, delete recipe. All CRUD operations work. Search returns correct results. CSRF blocks forged requests.
4. **Most likely way this plan is wrong?** The ingredient linking form UX -- adding/removing ingredient rows on the recipe form without JS may require a form-resubmission pattern that's awkward. Plan defines the exact flow below.

---

## File Structure

```
recipe-organizer/
    run.py
    requirements.txt
    app/
        __init__.py              # App factory + CSRF + error handlers
        db.py                    # DB connection context manager
        models.py                # All SQL queries as pure functions
        schema.sql               # DDL for all tables + indexes
        static/
            style.css            # Complete CSS
        templates/
            layout.html          # Base template
            errors/
                404.html         # Not found page
                403.html         # CSRF forbidden page
            recipes/
                list.html        # Recipe index with pagination
                detail.html      # Single recipe view with ingredients
                form.html        # Create/edit form with ingredient rows
            ingredients/
                list.html        # Ingredient index with recipe counts
                form.html        # Create/edit ingredient form
            search/
                results.html     # Search results
        blueprints/
            recipes/
                __init__.py      # Blueprint registration
                routes.py        # Recipe CRUD routes
            ingredients/
                __init__.py      # Blueprint registration
                routes.py        # Ingredient CRUD routes
            search/
                __init__.py      # Blueprint registration
                routes.py        # Search route
```

---

## Database Schema

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK(length(title) <= 200),
    description TEXT CHECK(length(description) <= 2000),
    instructions TEXT NOT NULL CHECK(length(instructions) <= 10000),
    servings INTEGER NOT NULL CHECK(servings > 0),
    prep_time_min INTEGER CHECK(prep_time_min >= 0),
    cook_time_min INTEGER CHECK(cook_time_min >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(name) <= 100),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
    quantity REAL NOT NULL CHECK(quantity > 0),
    unit TEXT CHECK(length(unit) <= 50),
    PRIMARY KEY (recipe_id, ingredient_id)
);

CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient_id
    ON recipe_ingredients(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_recipes_title
    ON recipes(title);
CREATE INDEX IF NOT EXISTS idx_ingredients_name
    ON ingredients(name);
```

### Key Schema Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Ingredient name uniqueness | `UNIQUE COLLATE NOCASE` | Prevents "Chicken" vs "chicken" duplicates |
| Ingredient deletion | `ON DELETE RESTRICT` | Blocks deletion if ingredient is used in any recipe |
| Recipe deletion | `ON DELETE CASCADE` on junction | Deleting a recipe removes its ingredient links |
| Junction PK | `PRIMARY KEY (recipe_id, ingredient_id)` | Composite PK, matches gold standard -- no surrogate ID needed |
| Quantity type | `REAL` | Supports fractional amounts (1.5 cups) |
| Length constraints | `CHECK(length(...))` | DB-level validation, enforced even outside the app |
| No `default_unit` | Dropped | Junction table has its own `unit` per link; `default_unit` was unused by UX |

---

## Models Layer (`app/models.py`)

All functions are pure, taking `conn: sqlite3.Connection` as the first argument.
Models are thin SQL wrappers -- pagination math stays in routes.

### Constants

```python
ITEMS_PER_PAGE: Final[int] = 20
MAX_SEARCH_TERMS: Final[int] = 10
```

### Function Signatures + Return Types + Usage Examples

| Function | Parameters | Returns | Usage Example |
|----------|-----------|---------|---------------|
| `get_all_recipes` | `conn, limit, offset` | `list[Row]` | `recipes = get_all_recipes(conn, limit=20, offset=0)` |
| `get_recipe_count` | `conn` | `int` | `total = get_recipe_count(conn)` |
| `get_recipe` | `conn, recipe_id` | `Row \| None` | `recipe = get_recipe(conn, 42); if recipe is None: abort(404)` |
| `create_recipe` | `conn, title, description, instructions, servings, prep_time_min, cook_time_min` | `int` | `recipe_id = create_recipe(conn, ...); redirect(url_for('recipes.detail', recipe_id=recipe_id))` |
| `update_recipe` | `conn, recipe_id, title, description, instructions, servings, prep_time_min, cook_time_min` | `None` | `update_recipe(conn, 42, ...)  # also sets updated_at` |
| `delete_recipe` | `conn, recipe_id` | `None` | `delete_recipe(conn, 42)` |
| `get_all_ingredients` | `conn, limit, offset` | `list[Row]` | `ingredients = get_all_ingredients(conn, limit=20, offset=0)  # includes recipe_count subquery` |
| `get_ingredient_count` | `conn` | `int` | `total = get_ingredient_count(conn)` |
| `get_ingredient` | `conn, ingredient_id` | `Row \| None` | `ing = get_ingredient(conn, 5); if ing is None: abort(404)` |
| `create_ingredient` | `conn, name` | `int` | `ing_id = create_ingredient(conn, "Chicken")` |
| `update_ingredient` | `conn, ingredient_id, name` | `None` | `update_ingredient(conn, 5, "Chicken breast")` |
| `delete_ingredient` | `conn, ingredient_id` | `None` | `delete_ingredient(conn, 5)  # raises IntegrityError if used` |
| `set_recipe_ingredients` | `conn, recipe_id, ingredients_data` | `None` | `set_recipe_ingredients(conn, 42, [{"ingredient_id": 5, "quantity": 2.0, "unit": "cups"}])` |
| `get_ingredients_for_recipe` | `conn, recipe_id` | `list[Row]` | `ings = get_ingredients_for_recipe(conn, 42)  # Row has: ingredient_id, name, quantity, unit` |
| `get_ingredients_for_recipes` | `conn, recipe_ids` | `dict[int, list[Row]]` | `ings_map = get_ingredients_for_recipes(conn, [1,2,3]); ings_map[1]  # list of Row` |
| `search_recipes_by_ingredients` | `conn, query, limit, offset` | `list[Row]` | `results = search_recipes_by_ingredients(conn, "chicken garlic", 20, 0)` |
| `search_recipe_count` | `conn, query` | `int` | `total = search_recipe_count(conn, "chicken garlic")` |
| `_escape_like` | `term` | `str` | `escaped = _escape_like("100%")  # returns "100\\%"` |
| `_build_ingredient_search_where` | `query` | `tuple[str, list]` | `where, params = _build_ingredient_search_where("chicken garlic")` |

### `get_all_ingredients` with Inline Recipe Count

```python
def get_all_ingredients(conn, limit, offset):
    """Returns ingredients with recipe_count as a computed column."""
    return conn.execute("""
        SELECT i.*,
            (SELECT COUNT(*) FROM recipe_ingredients ri
             WHERE ri.ingredient_id = i.id) AS recipe_count
        FROM ingredients i
        ORDER BY i.name COLLATE NOCASE
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()
```

### `update_recipe` Sets `updated_at`

```python
def update_recipe(conn, recipe_id, title, description, instructions,
                  servings, prep_time_min, cook_time_min):
    conn.execute("""
        UPDATE recipes SET title=?, description=?, instructions=?,
            servings=?, prep_time_min=?, cook_time_min=?,
            updated_at=strftime('%Y-%m-%d %H:%M:%S', 'now')
        WHERE id=?
    """, (title, description, instructions, servings,
          prep_time_min, cook_time_min, recipe_id))
```

### Search Implementation

Multi-term AND search. Space-separated terms, capped at 10. Each term must
match at least one ingredient linked to the recipe via EXISTS subquery with LIKE.
Empty query returns all recipes.

```python
def _build_ingredient_search_where(query):
    terms = query.strip().split()[:MAX_SEARCH_TERMS]
    if not terms:
        return "", []
    clauses = []
    params = []
    for term in terms:
        escaped = _escape_like(term)
        clauses.append("""
            EXISTS (
                SELECT 1 FROM recipe_ingredients ri
                JOIN ingredients i ON ri.ingredient_id = i.id
                WHERE ri.recipe_id = recipes.id
                AND i.name LIKE ? ESCAPE '\\'
            )
        """)
        params.append(f"%{escaped}%")
    return " AND ".join(clauses), params

def search_recipes_by_ingredients(conn, query, limit, offset):
    where, params = _build_ingredient_search_where(query)
    if not where:
        return get_all_recipes(conn, limit, offset)
    return conn.execute(f"""
        SELECT * FROM recipes WHERE {where}
        ORDER BY created_at DESC LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()

def search_recipe_count(conn, query):
    where, params = _build_ingredient_search_where(query)
    if not where:
        return get_recipe_count(conn)
    return conn.execute(f"""
        SELECT COUNT(*) FROM recipes WHERE {where}
    """, params).fetchone()[0]
```

### Batch Fetch (N+1 Prevention)

```python
def get_ingredients_for_recipes(conn, recipe_ids):
    if not recipe_ids:
        return {}
    placeholders = ",".join("?" * len(recipe_ids))
    rows = conn.execute(f"""
        SELECT ri.recipe_id, i.id AS ingredient_id, i.name, ri.quantity, ri.unit
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id IN ({placeholders})
        ORDER BY i.name
    """, recipe_ids).fetchall()
    result = {rid: [] for rid in recipe_ids}
    for row in rows:
        result[row["recipe_id"]].append(row)
    return result
```

### `set_recipe_ingredients` (Replace Pattern)

Delete all existing links, then insert new ones. Runs inside the caller's
transaction (the route uses `get_db(immediate=True)`):

```python
def set_recipe_ingredients(conn, recipe_id, ingredients_data):
    conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    for item in ingredients_data:
        conn.execute("""
            INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit)
            VALUES (?, ?, ?, ?)
        """, (recipe_id, item["ingredient_id"], item["quantity"], item["unit"]))
```

---

## Endpoint Registry

| Blueprint | Function | Method | Path | `url_for` Name |
|-----------|----------|--------|------|----------------|
| recipes | `index` | GET | `/recipes/` | `recipes.index` |
| recipes | `create` | GET, POST | `/recipes/new` | `recipes.create` |
| recipes | `detail` | GET | `/recipes/<int:recipe_id>` | `recipes.detail` |
| recipes | `edit` | GET, POST | `/recipes/<int:recipe_id>/edit` | `recipes.edit` |
| recipes | `delete` | POST | `/recipes/<int:recipe_id>/delete` | `recipes.delete` |
| ingredients | `index` | GET | `/ingredients/` | `ingredients.index` |
| ingredients | `create` | GET, POST | `/ingredients/new` | `ingredients.create` |
| ingredients | `edit` | GET, POST | `/ingredients/<int:ingredient_id>/edit` | `ingredients.edit` |
| ingredients | `delete` | POST | `/ingredients/<int:ingredient_id>/delete` | `ingredients.delete` |
| search | `search` | GET | `/search/` | `search.search` |

Home page (`/`) redirects to `recipes.index`.

**Intentional deviation from gold standard:** Combined GET/POST handlers per
route (e.g., `create` handles both form display and submission) instead of
separate `new_*` / `create_*` functions. This is simpler for the ingredient form
UX where create and edit share a template.

---

## Template Render Context

| Template | Route Function | Variables | Types |
|----------|---------------|-----------|-------|
| `recipes/list.html` | `recipes.index` | `recipes`, `ingredients_map`, `page`, `total_pages` | `list[Row]`, `dict[int, list[Row]]`, `int`, `int` |
| `recipes/detail.html` | `recipes.detail` | `recipe`, `ingredients` | `Row`, `list[Row]` |
| `recipes/form.html` | `recipes.create`, `recipes.edit` | `recipe` (None for create), `all_ingredients`, `selected_ingredients`, `is_edit` | `Row\|None`, `list[Row]`, `list[dict]`, `bool` |
| `ingredients/list.html` | `ingredients.index` | `ingredients`, `page`, `total_pages` | `list[Row]` (with `recipe_count` column), `int`, `int` |
| `ingredients/form.html` | `ingredients.create`, `ingredients.edit` | `ingredient` (None for create), `is_edit` | `Row\|None`, `bool` |
| `search/results.html` | `search.search` | `recipes`, `ingredients_map`, `query`, `page`, `total_pages` | `list[Row]`, `dict[int, list[Row]]`, `str`, `int`, `int` |
| `errors/404.html` | error handler | `message` | `str` |
| `errors/403.html` | error handler | `message` | `str` |

### Empty States

Each list template must handle the empty case with `.empty-state` div:
- `recipes/list.html`: "No recipes yet. Create your first recipe!"
- `ingredients/list.html`: "No ingredients yet. Add some ingredients to get started!"
- `search/results.html`: "No recipes found matching '[query]'. Try different ingredients."
- `recipes/form.html` (no ingredients in pool): "No ingredients available. Create some ingredients first."

### `selected_ingredients` format (for recipe form)

```python
# List of dicts representing current ingredient links on the recipe
selected_ingredients = [
    {"ingredient_id": 5, "name": "Chicken", "quantity": 2.0, "unit": "lb"},
    {"ingredient_id": 12, "name": "Garlic", "quantity": 3.0, "unit": "cloves"},
]
```

---

## Ingredient Linking UX (Feed-Forward Risk Area)

This is the least-confident area from the brainstorm. Here is the exact flow:

### Recipe Create/Edit Form

The form includes a "Ingredients" section with rows. Each row is:
```html
<div class="ingredient-row">
    <select name="ingredient_id">
        <option value="">-- Select ingredient --</option>
        {% for ing in all_ingredients %}
        <option value="{{ ing.id }}" {% if ing.id == row.ingredient_id %}selected{% endif %}>
            {{ ing.name }}
        </option>
        {% endfor %}
    </select>
    <input type="number" name="quantity" step="0.1" min="0.1"
           value="{{ row.quantity if row else '' }}" required>
    <input type="text" name="unit" maxlength="50"
           value="{{ row.unit if row else '' }}" placeholder="e.g., cups">
    <button type="button" class="btn-remove-row">Remove</button>
</div>
```

### Adding/Removing Rows

**Minimal JS approach** (12 lines):
- "Add Ingredient" button clones the first `.ingredient-row` template and
  appends it to the form
- Each row has a "Remove" button that removes its parent `.ingredient-row`
- No server round-trip needed

### Form Submission Parsing

The route receives parallel arrays: `ingredient_id[]`, `quantity[]`, `unit[]`.
Flask provides these via `request.form.getlist()`. Includes try/except for
type conversion and deduplication:

```python
ingredient_ids = request.form.getlist("ingredient_id")
quantities = request.form.getlist("quantity")
units = request.form.getlist("unit")

ingredients_data = []
seen_ids = set()
for ing_id, qty, unit in zip(ingredient_ids, quantities, units):
    if not ing_id or not qty:
        continue  # skip empty rows
    try:
        parsed_id = int(ing_id)
        parsed_qty = float(qty)
    except (ValueError, TypeError):
        flash("Invalid ingredient data. Check quantities.", "error")
        # re-render form with current values
        return render_template(...)
    if parsed_qty <= 0:
        flash("Quantity must be greater than zero.", "error")
        return render_template(...)
    if parsed_id in seen_ids:
        continue  # skip duplicate ingredient
    seen_ids.add(parsed_id)
    ingredients_data.append({
        "ingredient_id": parsed_id,
        "quantity": parsed_qty,
        "unit": unit.strip(),
    })
```

### Ingredient Delete Error Handling

When deleting an ingredient that is used in recipes, the route catches
`sqlite3.IntegrityError` and flashes an error:

```python
try:
    delete_ingredient(conn, ingredient_id)
    flash("Ingredient deleted.", "success")
except sqlite3.IntegrityError:
    flash("Cannot delete -- this ingredient is used in recipes. "
          "Remove it from all recipes first.", "error")
return redirect(url_for("ingredients.index"))
```

---

## Input Validation

| Field | Required | Max Length | Constraints |
|-------|----------|-----------|-------------|
| Recipe title | Yes | 200 | Non-empty after strip |
| Recipe description | No | 2000 | - |
| Recipe instructions | Yes | 10000 | Non-empty after strip |
| Recipe servings | Yes | - | Integer > 0 |
| Recipe prep_time_min | No | - | Integer >= 0 if provided |
| Recipe cook_time_min | No | - | Integer >= 0 if provided |
| Ingredient name | Yes | 100 | Non-empty after strip, unique (case-insensitive) |
| Junction quantity | Yes | - | Float > 0 |
| Junction unit | No | 50 | - |

Validation happens in route handlers before calling model functions. Flash error
message and re-render form on failure. DB CHECK constraints are the last line of
defense. All int/float conversions wrapped in try/except.

---

## App Factory (`app/__init__.py`)

```python
import secrets
from flask import Flask, session, request, abort, redirect, url_for, render_template

def create_app(db_path=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = secrets.token_hex(24)

    if db_path is None:
        db_path = "recipes.db"
    app.config["DB_PATH"] = db_path

    from .db import init_db
    with app.app_context():
        init_db(app)

    # CSRF protection
    @app.before_request
    def csrf_protect():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        if request.method == "POST":
            token = request.form.get("csrf_token")
            if not token or token != session.get("csrf_token"):
                abort(403)

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": session.get("csrf_token", "")}

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html",
                               message="Page not found."), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html",
                               message="Request forbidden. Your session may "
                                       "have expired. Please go back and try "
                                       "again."), 403

    # Register blueprints
    from .blueprints.recipes import recipes_bp
    from .blueprints.ingredients import ingredients_bp
    from .blueprints.search import search_bp
    app.register_blueprint(recipes_bp, url_prefix="/recipes")
    app.register_blueprint(ingredients_bp, url_prefix="/ingredients")
    app.register_blueprint(search_bp, url_prefix="/search")

    @app.route("/")
    def home():
        return redirect(url_for("recipes.index"))

    return app
```

## DB Layer (`app/db.py`)

```python
import os
import sqlite3
from contextlib import contextmanager
from flask import current_app

@contextmanager
def get_db(immediate=False):
    db_path = current_app.config["DB_PATH"]
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Usage (READ):
#   with get_db() as conn:
#       recipe = get_recipe(conn, 42)
#
# Usage (WRITE):
#   with get_db(immediate=True) as conn:
#       recipe_id = create_recipe(conn, ...)

def init_db(app):
    """Initialize database schema. Uses raw connection, NOT get_db()."""
    db_path = app.config["DB_PATH"]
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
```

### Key `get_db` Decisions (from deepening)

- **Always commit/rollback** regardless of `immediate` flag (matches gold standard).
  Prevents silent write loss if a read-only path accidentally writes.
- **No WAL pragma** in `get_db()` -- WAL is persistent and already set by `init_db()`.
  Saves one round-trip per request.
- **`foreign_keys=ON`** must be per-connection (not persistent in SQLite).

---

## Swarm Agent Assignment

Three agents, following bookmark-manager's proven 3-agent split.
22 files total. Every file assigned to exactly one agent. No overlaps.

### Validation Summary

| Check | Result |
|-------|--------|
| Files in plan structure | 22 |
| Files assigned | 22 |
| Duplicate assignments | 0 |
| Unassigned files | 0 |

---

### Agent: core (6 files)

**Role:** App factory, DB layer, models, schema, entrypoint, dependencies.

**Files:**
1. `recipe-organizer/run.py`
2. `recipe-organizer/requirements.txt`
3. `recipe-organizer/app/__init__.py`
4. `recipe-organizer/app/db.py`
5. `recipe-organizer/app/models.py`
6. `recipe-organizer/app/schema.sql`

**Shared Interface Spec (core must follow):**

- `get_db(immediate=False)` is a context manager. Always use `with get_db() as conn:`.
- `create_recipe(...)` returns `int` (the new ID), not a Row.
- `get_recipe(conn, recipe_id)` returns `Row | None`.
- `init_db(app)` uses raw connection, NOT `get_db()`.
- `get_db()` always commits on success, rollbacks on exception -- regardless of `immediate` flag.
- `foreign_keys=ON` set per connection inside `get_db()`.
- WAL mode set only in `init_db()`, not in `get_db()`.
- Models use `limit`/`offset` parameters, not `page`.
- Constants: `ITEMS_PER_PAGE = 20`, `MAX_SEARCH_TERMS = 10`.
- Blueprint variables exported: `recipes_bp`, `ingredients_bp`, `search_bp`.
- All model functions take `conn: sqlite3.Connection` as first argument.
- `set_recipe_ingredients(conn, recipe_id, ingredients_data)` -- `ingredients_data` is `list[dict]` with keys: `ingredient_id` (int), `quantity` (float), `unit` (str).
- `get_ingredients_for_recipes(conn, recipe_ids)` returns `dict[int, list[Row]]`.

---

### Agent: routes (6 files)

**Role:** All blueprint registration and route handlers for recipes, ingredients, and search.

**Files:**
1. `recipe-organizer/app/blueprints/recipes/__init__.py`
2. `recipe-organizer/app/blueprints/recipes/routes.py`
3. `recipe-organizer/app/blueprints/ingredients/__init__.py`
4. `recipe-organizer/app/blueprints/ingredients/routes.py`
5. `recipe-organizer/app/blueprints/search/__init__.py`
6. `recipe-organizer/app/blueprints/search/routes.py`

**Shared Interface Spec (routes must follow):**

- `get_db(immediate=False)` is a context manager. Always use `with get_db() as conn:`.
- `create_recipe(...)` returns `int` (the new ID), not a Row. Use: `recipe_id = create_recipe(conn, ...); redirect(url_for('recipes.detail', recipe_id=recipe_id))`.
- `get_recipe(conn, recipe_id)` returns `Row | None`. Check for None and `abort(404)`.
- Read paths: `with get_db() as conn:`. Write paths: `with get_db(immediate=True) as conn:`.
- Models use `limit`/`offset` parameters, not `page`. Pagination math in routes: `offset = (page - 1) * ITEMS_PER_PAGE`.
- Constants imported from models: `ITEMS_PER_PAGE`, `MAX_SEARCH_TERMS`.
- Blueprint variables: `recipes_bp = Blueprint("recipes", __name__)`, `ingredients_bp = Blueprint("ingredients", __name__)`, `search_bp = Blueprint("search", __name__)`.
- Endpoint registry (url_for names): `recipes.index`, `recipes.create`, `recipes.detail`, `recipes.edit`, `recipes.delete`, `ingredients.index`, `ingredients.create`, `ingredients.edit`, `ingredients.delete`, `search.search`.
- Form parsing for ingredients uses `request.form.getlist()` with parallel arrays: `ingredient_id`, `quantity`, `unit`. Wrap int/float conversion in try/except. Deduplicate by ingredient_id.
- Ingredient delete catches `sqlite3.IntegrityError` and flashes error.
- Template render context must match the Template Render Context table exactly.

---

### Agent: templates (10 files)

**Role:** All Jinja2 templates, error pages, and static CSS.

**Files:**
1. `recipe-organizer/app/templates/layout.html`
2. `recipe-organizer/app/templates/errors/404.html`
3. `recipe-organizer/app/templates/errors/403.html`
4. `recipe-organizer/app/templates/recipes/list.html`
5. `recipe-organizer/app/templates/recipes/detail.html`
6. `recipe-organizer/app/templates/recipes/form.html`
7. `recipe-organizer/app/templates/ingredients/list.html`
8. `recipe-organizer/app/templates/ingredients/form.html`
9. `recipe-organizer/app/templates/search/results.html`
10. `recipe-organizer/app/static/style.css`

**Shared Interface Spec (templates must follow):**

- Template render context variables (exact names and types from plan):
  - `recipes/list.html`: `recipes` (list[Row]), `ingredients_map` (dict[int, list[Row]]), `page` (int), `total_pages` (int)
  - `recipes/detail.html`: `recipe` (Row), `ingredients` (list[Row])
  - `recipes/form.html`: `recipe` (Row|None), `all_ingredients` (list[Row]), `selected_ingredients` (list[dict]), `is_edit` (bool)
  - `ingredients/list.html`: `ingredients` (list[Row] with recipe_count), `page` (int), `total_pages` (int)
  - `ingredients/form.html`: `ingredient` (Row|None), `is_edit` (bool)
  - `search/results.html`: `recipes` (list[Row]), `ingredients_map` (dict[int, list[Row]]), `query` (str), `page` (int), `total_pages` (int)
  - `errors/404.html`: `message` (str)
  - `errors/403.html`: `message` (str)
- `csrf_token` is injected globally via context processor. All forms must include: `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`
- Endpoint names for url_for: `recipes.index`, `recipes.create`, `recipes.detail`, `recipes.edit`, `recipes.delete`, `ingredients.index`, `ingredients.create`, `ingredients.edit`, `ingredients.delete`, `search.search`.
- CSS classes: `.container`, `.nav-links`, `.flash-success`, `.flash-error`, `.recipe-list`, `.recipe-card`, `.recipe-meta`, `.ingredient-list`, `.ingredient-row`, `.btn-remove-row`, `.search-form`, `.search-results`, `.form-group`, `.form-actions`, `.btn`, `.btn-danger`, `.btn-secondary`, `.pagination`, `.page-link`, `.page-current`, `.empty-state`, `.badge`, `.error-page`.
- Empty states: each list template handles empty case with `.empty-state` div.
- Recipe form ingredient rows use minimal JS (clone/remove pattern). Each row has: select (name="ingredient_id"), input number (name="quantity"), input text (name="unit"), remove button (.btn-remove-row).
- `selected_ingredients` format: `[{"ingredient_id": int, "name": str, "quantity": float, "unit": str}]`.

---

## Shared Interface Spec

This is the contract all three swarm agents must follow. Every function name,
route path, template variable, and CSS class must match exactly.

### Anti-Patterns (DO NOT DO THIS)

```python
# WRONG: bare call, not context manager
db = get_db()
recipe = get_recipe(db, 42)

# WRONG: treating int return as Row
recipe = create_recipe(conn, ...)
redirect(url_for('recipes.detail', recipe_id=recipe.id))  # AttributeError

# WRONG: executescript inside get_db context
with get_db() as conn:
    conn.executescript(schema)  # implicit COMMIT breaks transaction

# WRONG: conditional commit (old pattern)
if immediate:
    conn.commit()  # ALWAYS commit, not just when immediate
```

### Blueprint Registration

Each blueprint file exports a descriptively named variable:
- `recipes/__init__.py`: `recipes_bp = Blueprint("recipes", __name__)`
- `ingredients/__init__.py`: `ingredients_bp = Blueprint("ingredients", __name__)`
- `search/__init__.py`: `search_bp = Blueprint("search", __name__)`

### CSS Classes (templates agent owns)

```
.container, .nav-links, .flash-success, .flash-error,
.recipe-list, .recipe-card, .recipe-meta,
.ingredient-list, .ingredient-row, .btn-remove-row,
.search-form, .search-results,
.form-group, .form-actions, .btn, .btn-danger, .btn-secondary,
.pagination, .page-link, .page-current,
.empty-state, .badge, .error-page
```

---

## Acceptance Criteria

- [ ] Create a recipe with title, description, instructions, servings, prep/cook time
- [ ] Add ingredients to a recipe with quantity and unit
- [ ] Edit a recipe and its ingredients (updated_at is set)
- [ ] Delete a recipe (cascades to junction table)
- [ ] Create, edit, delete standalone ingredients
- [ ] Deleting an ingredient used in a recipe is blocked with flash error message
- [ ] Duplicate ingredient on same recipe is deduplicated in form parsing
- [ ] Search recipes by ingredient name (single term)
- [ ] Search recipes by multiple ingredients (AND logic, capped at 10 terms)
- [ ] Empty search shows all recipes
- [ ] Pagination on recipe list, ingredient list, and search results
- [ ] CSRF token present on all forms, POST without token returns custom 403 page
- [ ] Custom 404 error page for missing recipes/ingredients
- [ ] Input validation with flash error messages on invalid data (including int/float parsing)
- [ ] Recipe list shows ingredient names per recipe (batch fetched)
- [ ] Ingredient list shows recipe count per ingredient (computed via subquery)
- [ ] Empty states shown when no recipes, no ingredients, or no search results
- [ ] All links use correct `url_for` names from Endpoint Registry
- [ ] No dependencies beyond `flask>=3.0`

---

## Sources & References

### Origin

- **Brainstorm:** [docs/brainstorms/2026-04-09-recipe-organizer-brainstorm.md](docs/brainstorms/2026-04-09-recipe-organizer-brainstorm.md) -- key decisions: shared ingredient pool, LIKE search, bookmark-manager pattern, no FTS5, no Flask-WTF

### Solution Docs Applied

- Bookmark Manager Swarm Build -- endpoint registry, batch queries, CSRF, LIKE search, composite PK on junction
- Task Tracker Categories Swarm -- scalar return values, Template Render Context
- Flask Swarm Acid Test -- context manager usage examples, anti-patterns in spec
- URL Shortener API -- WAL mode, timeout, init_db pattern
- Chat Room API -- executescript footgun, atomic transactions
- Swarm Scale Shared Spec -- spec structure for 3+ agents

### Deepening Review Agents

7 agents reviewed this plan. Key changes applied:
- **Architecture:** Fixed get_db commit semantics, composite PK, limit/offset
- **Security:** Capped search terms, added try/except on parsing, sort validation N/A (removed)
- **Performance:** Removed redundant WAL pragma from get_db
- **Simplicity:** Removed sort system, ingredient detail page, default_unit, batch counts function
- **SpecFlow:** Added error handlers, empty states, updated_at, duplicate dedup, delete error UX
- **Pattern:** Blueprint naming, SECRET_KEY, db_path alignment with gold standard

---

## Feed-Forward

- **Hardest decision:** The ingredient linking form UX. Chose minimal JS (clone row / remove row) over pure HTML resubmission (too clunky) and full autocomplete (YAGNI). This is the simplest approach that doesn't degrade the experience.
- **Rejected alternatives:** (1) Sort system with 4 options -- YAGNI for personal app, hardcode newest-first. (2) Ingredient detail page -- search already covers "find recipes by ingredient." (3) `default_unit` column -- junction table has its own unit. (4) Separate batch function for ingredient recipe counts -- inline subquery is simpler. (5) Conditional commit in get_db -- gold standard always commits, prevents silent data loss.
- **Least confident:** Whether `request.form.getlist()` with parallel arrays (ingredient_id[], quantity[], unit[]) will parse correctly across all edge cases (empty rows, missing values, reordered fields). The work phase should verify this with a manual test immediately after implementing the recipe form route.
