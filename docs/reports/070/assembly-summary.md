STATUS: PASS

# Assembly Summary — Run 070

- assembly_method: cherry-pick (`merge-base(feat/film-production-pm, <branch>)..<branch>` per COMPLETED worker)
- merge_status: 16 assembled, 0 skipped (all COMPLETED), 0 empty-delta
- preserved_branches: none
- cleanup_status: complete (16 worktrees removed, 16 worker branches deleted, assembly branch deleted)
- contract_check: PASS (docs/reports/070/contract-check.md)
- smoke_test: PASS — 18/18 (docs/reports/070/smoke-test.md)
- test_suite: PASS — 10/10 (docs/reports/070/test-results.md)
- counts: 16 workers assembled, 0 inline conflict resolutions (a cherry-pick conflict aborts as assembly-ownership-conflict)

## Fixes Applied During Assembly

### database.py — :memory: shared connection (FC49 variant)
The original `init_db()` opened a separate SQLite connection, seeded it, then closed it.
For `DATABASE=:memory:`, each `connect(':memory:')` creates an isolated DB destroyed on
close. Fix: `init_app()` now creates ONE persistent `:memory:` connection for the lifetime
of the app object (stored in `app.config['_MEMORY_DB']`); `get_db()` returns it for all
request contexts. Production file-based databases unchanged.

### test_critical_flows.py — 3 test fixture bugs (not implementation bugs)
1. DOOD test asserted H for non-scheduled dates not present in shoot_dates (spec-correct
   behaviour: only scheduled dates appear in grid keys).
2. Budget/expense tests needed `total_budget_cents > 0` on seeded project before allocating.
3. `create_expense` returns None on overspend (not raises) per Transaction Contracts spec.

## Commits Assembled

| Worker | Role | Cherry-pick Base (merge-base) | Cherry-picked Commit(s) |
|---|---|---|---|
| scaffold | app factory, base template, static assets | f90aed8 | 6655b25 |
| database | schema.sql, database.py, models barrel | f90aed8 | 30eea47 |
| auth | auth routes, decorators, auth_models | f90aed8 | fa095ee |
| projects | project CRUD, dashboard, phase transitions | f90aed8 | 2db778a |
| scenes | scene model, routes, templates | f90aed8 | 4eecc4b |
| cast | cast blueprint, models, templates | f90aed8 | 5b05eb2 |
| crew | crew CRUD blueprint, models, templates | f90aed8 | 45989ff |
| departments | list, detail, head assignment, department_models | f90aed8 | 301f169 |
| locations | location_models, routes, templates | f90aed8 | 920b92a |
| schedule | scheduling, SortableJS reorder, schedule_models | f90aed8 | f703e60 |
| callsheets | call sheet generation, detail, publish | f90aed8 | 3546c2c |
| budget | producer budget blueprint, models, templates | f90aed8 | 0fabcb5 |
| expenses | expense ledger blueprint, model, templates | f90aed8 | cd4c80b |
| reports | DOOD grid, progress, budget summary | f90aed8 | af00e66 |
| search | FTS5 search blueprint, model, results page | f90aed8 | e46c0c1 |
| tests | smoke test + 10 critical-flow tests | f90aed8 | 49fc1d5 |

Assembly fix commit: 38714db (database.py :memory: fix + test fixture fixes)

## Track A Validate-on-Real-Build Proof

All 16 workers share merge-base f90aed8 (master HEAD = ancestor of feat HEAD after
the assembly-invariant merge in 9w.9). O3 invariant holds: worktree-root == merge-base
== gate-base for all workers. Cherry-pick range `f90aed8..<branch>` = exactly each
worker's own commit. Zero conflicts. FC51 base-divergence cherry-pick assembly
confirmed working on a real 16-agent build.

## FC50 Entrypoints Verified

All 6 callsheet cross-boundary entrypoints verified by contract check:
get_schedule_entries, get_scenes_by_ids, get_cast_for_scenes, get_location,
get_crew_by_department, get_departments. Arity and return-dict keys match spec.
Search index_entity(conn, entity_type, entity_id, title, body) — 5-arg signature
confirmed in scenes, cast, crew, locations routes. No FTS triggers in schema.sql.
