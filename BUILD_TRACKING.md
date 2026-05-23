# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | Client Intake Dashboard |
| Spec | docs/plans/client-intake-dashboard-plan.md |
| Date | 2026-05-22 |
| Phases | 6 |
| Total Agents | 15 |
| Build Method | swarm |

---

## AGENT_STATUS

| # | Agent | Commit | Status |
|---|-------|--------|--------|
| 1 | core | merged | PASS |
| 2 | layout | merged | PASS |
| 3 | auth | merged | PASS |
| 4 | submission_models | merged | PASS |
| 5 | assessment_models | merged | PASS |
| 6 | note_models | merged | PASS |
| 7 | intake_routes | merged | PASS |
| 8 | submissions_routes | e959025 (master-direct) | PASS |
| 9 | detail_routes | merged | PASS |
| 10 | status_routes | e959025 (master-direct) | PASS |
| 11 | assessment_routes | merged | PASS |
| 12 | dashboard_routes | fec989b (master-direct) | PASS |
| 13 | filters | merged | PASS |
| 14 | seed | f817de1 (master-direct) | PASS |
| 15 | tests | merged | PASS |

### Ownership Gate: PASS (15 agents, 1 minor violation: submissions_routes also created status/routes.py)
### Assembly: 11 worktree merges + 4 master-direct commits, 0 conflicts

---

## FAILURES

| # | Failure | Class | Agent | Fixed? | Commit |
|---|---------|-------|-------|--------|--------|
| 1 | CRASH: `audit_fit` -> `is_audit_fit` key mismatch in detail template | FC43 (cross-section name mismatch) | detail_routes | YES | 0af322a |
| 2 | SECRET_KEY had insecure dev fallback | FC15 (secret in source) | core | YES | 0af322a |
| 3 | Login not rate-limited | FC25 (missing rate limit) | auth | YES | 0af322a |
| 4 | XSS: `status_badge` filter did not escape input | FC20 (XSS) | filters | YES | 0af322a |
| 5 | Missing index on `submissions.status` | FC31 (missing index) | core | YES | 0af322a |
| 6 | Dead import in status routes | FC10 (dead code) | status_routes | YES | 0af322a |
| 7 | Same-status transition not rejected | FC44 (missing validation) | status_routes | YES | 0af322a |
| 8 | Assessment form allowed empty summary | FC44 (missing validation) | assessment_routes | YES | 0af322a |
| 9 | Logout used `session.pop` instead of `session.clear()` | FC18 (session fixation) | auth | YES | 0af322a |
| 10 | TOCTOU gap in status change outer 404 guard | FC43 (double-read) | status_routes | DEFERRED (P1 -- no delete endpoint exists) | -- |
| 11 | 11 P2 findings | various | various | DEFERRED | -- |
| 12 | 15 P3 findings | various | various | DEFERRED | -- |

---

## RUN_METRICS

| Metric | Value |
|--------|-------|
| Total agents | 15 |
| Agents passed | 15 |
| Agents failed | 0 |
| Merge conflicts | 0 |
| Smoke tests | 36/36 PASS |
| P1 findings | 9 fixed + 1 deferred (TOCTOU gap, no delete endpoint) |
| P2 findings | 11 deferred |
| P3 findings | 15 deferred |
| Review agents | 5 (security-sentinel, kieran-python-reviewer, performance-oracle, learnings-researcher, flow-trace-reviewer) |
| Fix commits | 1 (0af322a -- 9 P1 fixes) |
| Assembly method | 11 worktree merges + 4 master-direct |
| Ownership violations | 1 minor (submissions_routes also created status/routes.py) |

## Template Version

v1.0 -- 2026-05-03 (created after WRC Build #7)
