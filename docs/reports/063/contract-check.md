# Spec Contract Check — Run 063

STATUS: FAIL -- 6 mismatches

## FAIL Items

1. **expenses/routes.py**: Handler `list_expenses` creates endpoint `expenses.list_expenses` but spec requires `expenses.list`. base.html calls url_for('expenses.list') — BuildError at runtime.
2. **cast/routes.py:155**: UPDATE cast_members SQL in route handler — data ownership violation (owned by cast_models).
3. **locations/routes.py:114**: UPDATE locations SQL in route handler — data ownership violation (owned by location_models).
4. **projects/routes.py:116**: UPDATE projects SQL in route handler — data ownership violation (owned by project_models).
5. **crew/routes.py:128,246**: index_entity called with 4 args, needs 5 (missing body) — TypeError at runtime.
6. **cast/routes.py + crew/routes.py**: entity_type 'cast_member'/'crew_member' but search_models expects 'cast'/'crew' — silent search failure.

## Fix Attempt

**Errors addressed:** 6
**Files modified:**
- `app/blueprints/expenses/routes.py` -- renamed `list_expenses` to `list`; updated all three `url_for('expenses.list_expenses', ...)` calls to `url_for('expenses.list', ...)`
- `app/templates/expenses/new.html` -- updated Cancel link url_for from `expenses.list_expenses` to `expenses.list`
- `app/models/cast_models.py` -- added `update_cast_member(conn, cast_member_id, name, character_name, cast_id_number, **kwargs)` function
- `app/blueprints/cast/routes.py` -- imported `update_cast_member`; replaced inline UPDATE SQL with model call; changed both `index_entity` calls from `'cast_member'` to `'cast'`
- `app/models/location_models.py` -- added `update_location(conn, location_id, name, **kwargs)` function
- `app/blueprints/locations/routes.py` -- imported `update_location`; replaced inline UPDATE SQL with model call
- `app/models/project_models.py` -- added `update_project(conn, project_id, title, description, total_budget_cents)` function
- `app/blueprints/projects/routes.py` -- imported `update_project`; replaced inline UPDATE SQL with model call
- `app/blueprints/crew/routes.py` -- changed both `index_entity` calls from `'crew_member'` (4 args) to `'crew'` with explicit `name` and `role_title` args (5 args total)

**Fixes applied:**
1. `expenses/routes.py`: Renamed handler `list_expenses` -> `list` so Flask registers the endpoint as `expenses.list`, matching `url_for('expenses.list')` calls in base.html and updated all internal redirects.
2. `cast_models.py` + `cast/routes.py`: Extracted UPDATE SQL into `update_cast_member()` model function; route calls the model. Also fixed entity_type from `'cast_member'` to `'cast'` in both `index_entity` calls (create and update handlers).
3. `location_models.py` + `locations/routes.py`: Extracted UPDATE SQL into `update_location()` model function; route calls the model.
4. `project_models.py` + `projects/routes.py`: Extracted UPDATE SQL into `update_project()` model function; route calls the model.
5. `crew/routes.py` (create handler, line ~128): Changed `index_entity(conn, 'crew_member', id, f'{name} {role_title}')` to `index_entity(conn, 'crew', id, name, role_title)` -- fixes both entity_type and missing body arg.
6. `crew/routes.py` (update handler, line ~246): Same fix as above -- entity_type `'crew'` and explicit 5th arg.

STATUS: FIXED
