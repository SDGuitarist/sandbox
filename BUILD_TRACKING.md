# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | Restaurant Kitchen Management System (RestaurantOps) |
| Spec | docs/plans/2026-05-21-restaurant-kitchen-mgmt-plan.md |
| Date | 2026-05-21 |
| Phases | 6 |
| Total Agents | 29 |
| Build Method | swarm |

---

## AGENT_STATUS

| # | Agent | Commit | Status |
|---|-------|--------|--------|
| 1 | core | b29d057 | PASS |
| 2 | layout | 8a3cf3e | PASS |
| 3 | auth | da33180 | PASS |
| 4 | ingredient_models | 73cb885 | PASS |
| 5 | supplier_models | 7f77e08 | PASS |
| 6 | recipe_models | 59e503a | PASS |
| 7 | menu_models | dc77911 | PASS |
| 8 | inventory_models | 0458df0 | PASS |
| 9 | table_models | 1e0ac07 | PASS |
| 10 | reservation_models | 369a366 | PASS |
| 11 | order_models | 00599f3 | PASS |
| 12 | staff_models | 44b6a83 | PASS |
| 13 | specials_models | 9ffc0c7 | PASS |
| 14 | review_models | 421b13f | PASS |
| 15 | po_models | 20aeff3 | PASS |
| 16 | dashboard_models | 1c39473 | PASS |
| 17 | ingredient_routes | 6f15bcc | PASS |
| 18 | supplier_routes | 7b72214 | PASS (naming fix needed) |
| 19 | recipe_routes | 4d422a0 | PASS |
| 20 | menu_routes | 7ba0078 | PASS |
| 21 | inventory_routes | 22fc0a5 | PASS |
| 22 | table_routes | 74111d9 | PASS |
| 23 | reservation_routes | 36c292f | PASS |
| 24 | order_routes | bbb5d14 | PASS |
| 25 | po_routes | 3805ad9 | PASS |
| 26 | staff_routes | e2fb07e | PASS |
| 27 | specials_routes | b9393c4 | PASS |
| 28 | review_routes | 0cd1790 | PASS |
| 29 | dashboard_routes | 71066f9 | PASS |

### Ownership Gate: PASS (29 agents)
### Smoke Test: PASS (34/34)
### Contract Check: Implicit (smoke test covers route existence)
### Review: 8 P1, 16 P2 | Fix commits: 7e49918, d9dc2e9

---

## FAILURES

| Severity | Detail | Resolution | Failure Class |
|----------|--------|------------|---------------|
| P1 | Logout via GET allows CSRF session kill | Changed to POST + CSRF form | FC27 (neighbor pattern skip) |
| P1 | Default admin password 'admin' no blocklist | Added ADMIN_PASSWORD_BLOCKLIST | Spec template gap |
| P1 | SESSION_COOKIE_SECURE not set | Added = not app.debug | Spec template gap |
| P1 | Supplier routes /new vs /create, supplier_id vs id | Fixed naming to match spec | FC1 (naming divergence) |
| P1 | Menu int() without try/except on category_id/recipe_id | Added safe parsing | FC4 (validation gap) |
| P1 | Menu/supplier/ingredient delete with ON DELETE RESTRICT no handler | Added try/except/rollback | FC4 (validation gap) |
| P1 | Order ready/serve/close used BEGIN not BEGIN IMMEDIATE | Changed to BEGIN IMMEDIATE | FC29 (transaction boundary) |
| P1 | order_models conn.execute("COMMIT") vs conn.commit() | Changed to conn.commit()/rollback() | Code style |

---

## RUN_METRICS

### Final Build Metrics

| Metric | Value |
|--------|-------|
| Total agents | 29 |
| Total files | 98 |
| Total lines | ~8,178 |
| Merge conflicts | 0 |
| FC37 failures | 0 (0%) |
| Assembly fixes | 1 (supplier naming) |
| Smoke tests | 34/34 PASS |
| P1 findings (review) | 8 |
| P2 findings (review) | 16 |
| All P1s fixed | yes |
| All P2s fixed | no (deferred) |

### Agent Performance Summary

| Agent | Findings Caused | Failure Classes Hit | Notes |
|-------|----------------|--------------------|----|
| core | 3 P1 | Spec gap (auth security) | Security patterns not in spec |
| supplier_routes | 1 P1, 1 P2 | FC1, FC4 | Naming divergence + no truncation |
| menu_routes | 2 P1 | FC4 x2 | Unsafe int(), delete RESTRICT |
| order_routes | 1 P1 | FC29 | BEGIN vs BEGIN IMMEDIATE |
| order_models | 1 P1 | Code style | conn.execute("COMMIT") |

### Lessons for Next Build

1. Add auth security checklist to shared-spec-flask.md template (logout POST, password blocklist, SESSION_COOKIE_SECURE)
2. Change Coordinated Behaviors #8 to prescribe BEGIN IMMEDIATE for ALL status transitions, not just multi-table ops
3. Model/route split validated at 29 agents -- use for all future builds above 14 agents

## Template Version

v1.0 -- 2026-05-03 (created after WRC Build #7)
