# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | Film Production PM Tool |
| Spec | docs/plans/film-production-pm-plan.md |
| Date | 2026-06-02 |
| Phases | 1 (swarm) |
| Total Agents | 16 |
| Build Method | swarm |

---

## AGENT_STATUS

| # | Agent | Commit | Status |
|---|-------|--------|--------|
| 1 | database | 4cc4722 | PASS |
| 2 | scaffold | 3b3908c | PASS |
| 3 | auth | merged | PASS |
| 4 | projects | merged | PASS |
| 5 | scenes | merged | PASS |
| 6 | cast | merged | PASS |
| 7 | crew | merged | PASS |
| 8 | departments | merged | PASS |
| 9 | locations | merged | PASS |
| 10 | schedule | merged | PASS |
| 11 | callsheets | merged | PASS |
| 12 | budget | merged | PASS |
| 13 | expenses | merged | PASS |
| 14 | reports | merged | PASS |
| 15 | search | merged | PASS |
| 16 | tests | ec5e6ea | PASS |
### Ownership Gate: PASS (16 agents)
### Assembly: 16 worktree merges, 0 conflicts
### Contract Check: FAIL → PASS (6 mismatches fixed by assembly-fix)
### Smoke Test: PASS (18/18)
### Review: 1 P1, 3 P2 | Fix commits: b783e3a

---

## FAILURES

| # | Severity | Finding | Resolution | Failure Class |
|---|---------|---------|-----------|--------------|
| 056 | P1 | callsheets.generate missing YYYY-MM-DD date validation — schedule agent had re.match pattern; callsheets agent did not copy it | Fixed in b783e3a: added `import re` + `re.match(r'^\d{4}-\d{2}-\d{2}$', shoot_date)` to callsheets.generate | FC4 + FC27 |
| 057 | P2 | SESSION_COOKIE_SECURE=True unconditional breaks all local HTTP dev sessions | Fixed in b783e3a: `os.environ.get('FLASK_ENV') == 'production'` | Security misconfiguration |
| 058 | P2 | Redundant double get_schedule_entries query in generate route — called before transaction and again inside generate_call_sheet | Fixed in b783e3a: removed 6-line pre-check block; generate_call_sheet already returns None on empty entries | FC17 |
| 059 | P2 | 42 ghost files from BrewOps project shipped in film PM app (app/db.py, app/routes/ x10, app/models/ x7, app/templates/ x21) | Fixed in b783e3a: deleted all 42 ghost files; smoke test re-run 18/18 PASS | FC48 (new) |
| 060 | P3 | generate_call_sheet stores nearest_hospital in weather_note column — cosmetically wrong but data not lost | DEFERRED — todo 060. Fix: move to general_notes with label prefix. callsheet_models.py:113 | N/A |

---

## RUN_METRICS

### Final Build Metrics

| Metric | Value |
|--------|-------|
| Agent count | 16 |
| FC37 rate (agents failing to commit) | 0% (0/16) |
| Merge conflicts | 0 |
| File count (post ghost-file cleanup) | 89 |
| LOC estimate | ~7,458 |
| Smoke tests | 18/18 PASS |
| Review: P1 findings | 1 (all fixed) |
| Review: P2 findings | 3 (all fixed) |
| Review: P3 findings | 1 (deferred — todo 060) |
| Contract check mismatches (pre-swarm) | 6 (all fixed by assembly-fix agent) |
| New failure classes | 1 (FC48: ghost file contamination) |

### Agent Performance Summary

| Agent | Status | Notable |
|-------|--------|---------|
| database | PASS | Schema complete, all FKs with ON DELETE |
| scaffold | PASS | SESSION_COOKIE_SECURE bug (P2, FC4) — fixed post-review |
| auth | PASS | Login/logout/admin auth working |
| projects | PASS | Project CRUD + dashboard |
| scenes | PASS | Scene breakdown with script pages |
| cast | PASS | Cast management with roles |
| crew | PASS | Crew by department |
| departments | PASS | Department registry |
| locations | PASS | Location management |
| schedule | PASS | SortableJS drag-drop, date validation present |
| callsheets | PASS (post-fix) | Missing date validation (P1, FC4+FC27) — fixed in b783e3a |
| budget | PASS | Budget tracking with categories |
| expenses | PASS | Expense logging against budget |
| reports | PASS | DOOD grid + production progress |
| search | PASS | FTS5 with sanitize+phrase-wrap pattern |
| tests | PASS | 18 smoke tests, all green |

## Template Version

v1.0 — 2026-05-03 (created after WRC Build #7)
