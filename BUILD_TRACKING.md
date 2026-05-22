# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | BrewOps (Craft Brewery Manager) |
| Spec | docs/plans/brewops-plan.md |
| Date | 2026-05-22 |
| Phases | 6 (brainstorm, plan, deepen, swarm, review, compound) |
| Total Agents | 21 |
| Build Method | swarm |

---

## AGENT_STATUS

| # | Agent | Commit | Status |
|---|-------|--------|--------|
| 1 | core | f97b556 | PASS |
| 2 | layout | merged | PASS |
| 3 | auth | merged | PASS |
| 4 | recipe_models | merged | PASS |
| 5 | recipe_ingredient_models | merged | PASS |
| 6 | batch_models | merged | PASS |
| 7 | ingredient_models | merged | PASS |
| 8 | tank_models | merged | PASS |
| 9 | tap_models | merged | PASS |
| 10 | sale_models | merged | PASS |
| 11 | staff_models | merged | PASS |
| 12 | recipe_routes | merged | PASS |
| 13 | batch_routes | merged | PASS |
| 14 | ingredient_routes | merged | PASS |
| 15 | tank_routes | merged | PASS |
| 16 | tap_routes | merged | PASS |
| 17 | sale_routes | merged | PASS |
| 18 | staff_routes | merged | PASS |
| 19 | dashboard_routes | merged | PASS |
| 20 | seed | merged | PASS |
| 21 | tests | merged | PASS |

### Ownership Gate: PASS (21 agents)
### Assembly: 21/21 merged, 0 conflicts

---

## FAILURES

| # | Phase | Agent/Step | Failure Class | Description | Resolution |
|---|-------|-----------|---------------|-------------|------------|
| 1 | review | batch_models (agent 6) | FC45 | VALID_TRANSITIONS allowed tapped->empty bypassing create_sale tap-clear | Removed 'empty' from VALID_TRANSITIONS['tapped'] |
| 2 | review | core (agent 1) | FC46 | tanks.current_batch_id had no REFERENCES to batches | Added FK with ON DELETE SET NULL |
| 3 | review | core (agent 1) | FC29 | recipe_ingredients missing UNIQUE(recipe_id, ingredient_id) | Added UNIQUE constraint |
| 4 | review | core (agent 1) | FC40 | isolation_level=None makes conn.commit() no-op (3rd recurrence) | Removed isolation_level=None |
| 5 | review | tank_routes (15), staff_routes (18) | FC5 | Delete routes missing IntegrityError guard | Added try/except + occupied-check |
| 6 | review | core (agent 1) | dead-code | app/app.py + app/routes.py from prior project (162 LOC) | Deleted both files |
| 7 | review | recipe_routes (12) | FC35 | remove_recipe_ingredient lacks ownership check (ri_id not validated against recipe_id) | Added AND recipe_id = ? |

---

## RUN_METRICS

| Metric | Value |
|--------|-------|
| Total agents | 21 |
| Files created | 54 |
| Lines of code | ~4,343 |
| Smoke tests | 61/61 PASS |
| FC37 failures | 0 |
| Merge conflicts | 0 |
| Assembly fixes | 0 |
| Review agents | 10 |
| Review findings (total) | 17 |
| P1 findings | 7 (all resolved) |
| P2 findings | 6 (deferred) |
| P3 findings | 4 (deferred) |
| New failure classes | 2 (FC45, FC46) |
| Known pattern recurrences | 1 (isolation_level=None) |
| Validation targets | 3/3 PASS (Concurrency, Defense-in-Depth, Derived State) |

## Template Version

v1.0 — 2026-05-03 (created after WRC Build #7)
