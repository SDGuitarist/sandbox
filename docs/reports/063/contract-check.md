# Spec Contract Check — Run 063

STATUS: FAIL -- 6 mismatches

## FAIL Items

1. **expenses/routes.py**: Handler `list_expenses` creates endpoint `expenses.list_expenses` but spec requires `expenses.list`. base.html calls url_for('expenses.list') — BuildError at runtime.
2. **cast/routes.py:155**: UPDATE cast_members SQL in route handler — data ownership violation (owned by cast_models).
3. **locations/routes.py:114**: UPDATE locations SQL in route handler — data ownership violation (owned by location_models).
4. **projects/routes.py:116**: UPDATE projects SQL in route handler — data ownership violation (owned by project_models).
5. **crew/routes.py:128,246**: index_entity called with 4 args, needs 5 (missing body) — TypeError at runtime.
6. **cast/routes.py + crew/routes.py**: entity_type 'cast_member'/'crew_member' but search_models expects 'cast'/'crew' — silent search failure.
