# Brainstorm: Recipe Organizer with Ingredient Search

**Date:** 2026-04-09
**Status:** Complete
**Author:** Autopilot (autonomous)

## What We're Building

A personal recipe organizer that lets a single user store recipes, manage a
shared ingredient pool, link ingredients to recipes with quantities, and search
for recipes by ingredient name. Flask + SQLite + Jinja2, following the
bookmark-manager pattern.

### Core Features

1. **Recipe CRUD** - Create, read, update, delete recipes with title,
   description, instructions, servings, prep time, cook time
2. **Ingredient CRUD** - Manage a shared ingredient pool (name, default unit)
3. **Recipe-Ingredient Linking** - Junction table with quantity and unit per
   recipe-ingredient pair. Add/remove ingredients on the recipe edit form.
4. **Ingredient Search** - Find recipes that use a given ingredient. Multi-term
   AND search (e.g., "chicken garlic" finds recipes containing both).
5. **CSRF Protection** - Session-based manual CSRF on all POST forms (no
   Flask-WTF dependency), matching bookmark-manager pattern.

### Explicitly Out of Scope

- Meal planning / weekly menus
- Grocery list generation
- Nutritional information / calorie tracking
- Image uploads for recipes
- User authentication / multi-user
- Recipe sharing / public links
- Import recipes from URLs
- Full-text search (FTS5) - LIKE search is sufficient for personal collection
- Card/grid views - list view only

## Why This Approach

### Architecture: Follow Bookmark-Manager Pattern

The bookmark-manager is the most mature Flask app in the sandbox with proven
patterns for factory app, blueprints, context-manager DB, manual CSRF, models
layer, and LIKE-based search. Recipe organizer has an almost identical shape
(CRUD + tags/ingredients + search), so reusing the same architecture minimizes
risk and maximizes compound learning.

### Search: LIKE-Based Multi-Term AND

Same approach as bookmark-manager's tag search. Each search term must match an
ingredient name linked to the recipe. No FTS5 needed for a personal collection
of likely < 500 recipes. This is the simplest approach that works.

### Data Model: Shared Ingredient Pool + Junction Table

Three tables:
- `recipes` (id, title, description, instructions, servings, prep_time_min,
  cook_time_min, created_at, updated_at)
- `ingredients` (id, name, default_unit, created_at)
- `recipe_ingredients` (id, recipe_id, ingredient_id, quantity, unit)

Ingredients are shared across recipes (not duplicated per recipe). This enables
"search by ingredient" queries via JOIN. Junction table owns the quantity and
unit override.

### Ingredient Widget on Recipe Form

Plain HTML multi-row form. Each row has ingredient name (text input), quantity,
and unit. JavaScript-free for MVP. Add rows via form resubmission or a simple
"add row" button with minimal JS.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| App pattern | Factory + blueprints | Matches bookmark-manager, proven in swarm builds |
| DB access | Context manager with WAL | Prevents "database is locked" (URL shortener lesson) |
| CSRF | Manual session-based | No Flask-WTF dependency, proven pattern |
| Search | LIKE with escape helper | Sufficient for personal use, same as bookmark-manager |
| Ingredient model | Shared pool + junction | Enables cross-recipe search, avoids duplication |
| Counts | Computed, not stored | Habit tracker + bookmark manager lesson |
| Junction ownership | Recipe blueprint owns writes | Chain reaction contracts lesson |
| SECRET_KEY | From environment variable | Autopilot swarm lesson |
| Ingredient widget | Plain HTML rows | YAGNI - no JS autocomplete for MVP |

## Blueprints

1. **recipes** - `/recipes/` routes for recipe CRUD + ingredient linking
2. **ingredients** - `/ingredients/` routes for ingredient CRUD + recipe list per ingredient
3. **search** - `/search/` route for ingredient-based recipe search

## Lessons Applied from Prior Builds

- **WAL mode + timeout=10** on SQLite connection (URL shortener)
- **CSRF in all form contexts** including partials (GigPrep search)
- **Scalar return types with usage examples** in swarm spec (autopilot swarm)
- **Template Render Context** for ingredient widget (Flask acid test)
- **Computed counts** beat stored counters (habit tracker + bookmark manager)
- **Junction table data ownership** explicit in spec (chain reaction contracts)
- **SECRET_KEY from env** (autopilot swarm orchestration)
- **Context manager DB** with auto-commit/rollback (bookmark-manager)
- **`_escape_like()` helper** for safe LIKE queries (bookmark-manager)

## Open Questions

None - all decisions resolved autonomously for MVP scope.

## Feed-Forward

- **Hardest decision:** Whether to use a shared ingredient pool vs per-recipe
  ingredient strings. Shared pool adds junction table complexity but is required
  for the core "search by ingredient" feature. Without it, search would need
  full-text parsing of free-form text, which is fragile.
- **Rejected alternatives:** (1) FTS5 search - overkill for personal collection,
  adds SQLite extension dependency. (2) Per-recipe ingredient text field -
  simpler but defeats the purpose of ingredient search. (3) Flask-WTF for CSRF -
  unnecessary dependency when manual pattern is proven. (4) JavaScript
  autocomplete for ingredient widget - YAGNI for MVP.
- **Least confident:** The ingredient linking UX on the recipe form. Adding
  multiple ingredients with quantities via plain HTML without JS could be clunky.
  The plan phase should define the exact form submission flow (how rows are
  added, how existing ingredients are selected vs new ones created).

## Refinement Findings

**STATUS: PASS**

Cross-referenced against 24 solution docs in `docs/solutions/`. Found 5 gaps
(relevant lessons not mentioned in the brainstorm):

### Gap 1: Endpoint Registry for `url_for` Names
**Source:** `2026-04-09-bookmark-manager-swarm-build.md`

The brainstorm defines 3 blueprints with routes but does not include an Endpoint
Registry table mapping Flask function names to `url_for` names used in templates.
The bookmark-manager swarm build found that templates and routes agents
independently invented different endpoint names, causing `BuildError` on every
page. The plan should include an explicit endpoint registry table listing every
blueprint function name and its corresponding `url_for` name.

### Gap 2: `executescript()` Implicit COMMIT in `init_db`
**Source:** `2026-04-05-db-migration-runner.md`, `2026-04-05-feature-flag-service.md`, `2026-04-07-flask-swarm-acid-test.md`

The brainstorm mentions context-manager DB but does not warn about the
`executescript()` footgun. Multiple solution docs document that `executescript()`
issues an implicit COMMIT, which can release locks and bypass transaction
semantics. `init_db` must use a raw `sqlite3.connect` (not `get_db`), and WAL
pragma must be set before `executescript()`. This should be called out in the
plan's DB setup section.

### Gap 3: Input Validation with Max-Length Caps
**Source:** `2026-04-05-chat-room-api.md`, `2026-04-05-distributed-task-scheduler.md`, `2026-04-05-api-key-manager.md`

The brainstorm specifies no input validation rules for recipe fields (title,
description, instructions, ingredient name, quantity). Multiple solution docs
show that unbounded string inputs cause DoS via large payloads or unexpected
500 errors. The plan should define max-length limits for all user-provided
fields and whitespace-only rejection.

### Gap 4: Batch Fetching to Prevent N+1 Queries
**Source:** `2026-04-09-bookmark-manager-swarm-build.md`

The recipe list view will need to show ingredients per recipe. Without batch
fetching, this creates an N+1 query problem (one query per recipe to get its
ingredients). The bookmark-manager solved this with a
`get_tags_for_bookmarks(conn, bookmark_ids)` function that fetches all tags for
a page of bookmarks in one query, returning `dict[int, list[Row]]`. The plan
should include a similar `get_ingredients_for_recipes` batch function.

### Gap 5: Sort/Filter Parameter Validation
**Source:** `2026-04-09-bookmark-manager-swarm-build.md`

If recipes support sorting (by title, date, prep time), the sort parameter must
be validated against an allowlist in the route. The bookmark-manager found that
an unvalidated `?sort=evil` query parameter caused unhandled 500 errors. Use a
`SORT_OPTIONS` allowlist with a safe default fallback. Even if sorting is not in
MVP, the plan should document the pattern for when it is added.
