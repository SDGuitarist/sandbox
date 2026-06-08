STATUS: PASS

# Contract Check — Run 070

## FC50 Orchestration Entrypoints

All 6 callsheet cross-boundary calls verified:

| Entrypoint | Defined In | Called By | Signature Match |
|---|---|---|---|
| get_schedule_entries | schedule_models.py | callsheet_models.py | PASS — (conn, project_id, shoot_date) -> list[dict] with strip_color_class |
| get_scenes_by_ids | scene_models.py | callsheet_models.py | PASS — (conn, scene_ids) -> list[dict] |
| get_cast_for_scenes | cast_models.py | callsheet_models.py | PASS — (conn, scene_ids) -> list[dict] |
| get_location | location_models.py | callsheet_models.py | PASS — (conn, location_id) -> dict | None |
| get_crew_by_department | crew_models.py | callsheets/routes.py | PASS — (conn, project_id) -> list[dict] |
| get_departments | department_models.py | callsheets/routes.py, expenses/routes.py, crew/routes.py | PASS — (conn, project_id) -> list[dict] |

Auth decorators: login_required, require_project_member, require_role all defined in auth/routes.py, consumed by all route agents. PASS.

get_db: defined in database.py, consumed by all routes. PASS.

## Blueprint Registration

All 13 blueprints registered in create_app() with correct url_prefix values:
- auth (/auth), projects (/projects), scenes (/scenes), cast (/cast), crew (/crew),
  departments (/departments), locations (/locations), schedule (/schedule),
  callsheets (/call-sheets), budget (/budget), expenses (/expenses),
  reports (/reports), search (/search)

Root `index` endpoint defined. auth.login_post redirects to url_for('index'). PASS.

All blueprint files export `bp` variable. PASS.

## FTS5 Single-Writer

schema.sql: no TRIGGER definitions. FTS5 virtual table only.
search_models.py: index_entity() and remove_entity() are the only writers.
Scenes, cast, crew, locations routes call index_entity(conn, entity_type, entity_id, title, body) — correct 5-arg signature. PASS.

## Money Conventions (FC55)

budget/routes.py: _parse_cents('amount') reads suffix-free form field 'amount' -> cents. PASS.
expenses/routes.py: int(round(float(request.form['amount']) * 100)) -> amount_cents. PASS.
projects/routes.py uses 'total_budget' field. PASS.

## DATABASE env->config Mapping

app/__init__.py: app.config['DATABASE'] = os.environ.get('DATABASE', 'filmpm.db'). PASS.
Smoke tests can set DATABASE=:memory: and it is picked up.

## Cross-Boundary Wiring

expenses/routes.py imports get_department_allocation from budget_models. PASS.
reports/routes.py imports get_expenses from expense_models, get_budget_summary from budget_models, get_dood_grid/get_production_progress from report_models, get_shoot_dates from schedule_models. PASS.
scenes/routes.py imports index_entity from search_models. PASS.

## Minor Deviation (non-blocking)

SESSION_COOKIE_SECURE is env-conditional (True only in production env) rather than hardcoded True as in spec. This is acceptable and safer for testing.

## Result: PASS (no blocking failures)
