# BUILD_TRACKING.md

## Run Info

| Field | Value |
|-------|-------|
| Project | Film Production PM Tool |
| Spec | docs/plans/film-production-pm-plan.md |
| Date | 2026-06-08 |
| Phases | swarm (pre-gates → 16-agent swarm → assembly → tail) |
| Total Agents | 16 |
| Build Method | swarm |

> Run 069 (CPAA Event-Replay Simulator) final tracking archived at
> `docs/reports/069/BUILD_TRACKING-final.md`. Self-audit at
> `docs/reports/069/self-audit.md`.
> Run 070 is the validate-on-real-build vehicle for the FROZEN
> orchestration-hardening branch (Tracks A/B/C: FC51 cherry-pick assembly,
> FC50 entrypoint guard, spec-eval advisory demotion).

---

## Phase Status

| Phase | Status | Report Path |
|-------|--------|-------------|
| brainstorm | PRE-COMPLETE (attended) | docs/brainstorms/2026-06-02-film-production-pm-brainstorm.md |
| plan + deepen + spec convergence | CONVERGED + human-verified, zero P0s (attended, pre-run) | docs/plans/film-production-pm-plan.md ; docs/reports/film-production-pm/convergence-catches.md |
| swarm-planner (file assignment) | PASS — 16 agents, 94 files, zero duplicates | docs/plans/film-production-pm-plan.md §Swarm Agent Assignment |
| gates-consistency (9w.5) | PASS (1 retry; fixed dept_head→department_head, get_expense purpose cell, FC55 _cents note; 3 non-blocking WARNs) | docs/reports/070/spec-consistency-check.md |
| gates-completeness (9w.6) | PASS — Check 1b FC50 guard FIRED+PASSED (10 orch-entrypoint rows w/ full sigs = Track B proof); GET `<int:>` watch-item did NOT false-FAIL | docs/reports/070/spec-completeness-check.md |
| gate-verification (9w.7) | CLEARED | docs/reports/070/gate-verification.md |
| spec-eval (9w.8) | FAIL (ADVISORY — Track C; 15/277 claims failed, all single-shot-agent/scorer artifacts: eval emitted SQLAlchemy+REST stack ≠ spec sqlite3+blueprints, plus output truncations. ~0% precision pattern, NOT a spec defect, no spawn gate. Track C proof: ran + logged + did not block.) | docs/reports/070/spec-eval-1780926640/spec-eval-gate.json |
| assembly-invariant merge | DONE — merged master (orphan f90aed8 docs commit) into feat so worktree-root f90aed8 == merge-base == gate-base (FC51 O3 invariant; restores run-069 topology) | commit (merge) |
| ghost-file cleanup (9w.9) | DONE — removed 28 non-prescribed run-068 ghosts; kept 5 prescribed-path overlap files for clean worker overwrite (FC48) | commit 5094324 |
| swarm work (10w) | 16/16 COMPLETED, 0 FC37 commit failures | docs/reports/070/worker-roster.md |
| ownership gate (10.5w) | PASS — 16/16 disjoint | docs/reports/070/ownership-gate.md |
| swarm | PASS | docs/reports/070/assembly-summary.md |

**Run State:**
- run_id: 070
- run_start_ts: 1780924092
- plan_path: docs/plans/film-production-pm-plan.md
- branch: feat/film-production-pm
- swarm: true
- total_agents: 16
- context_proxy_chars: 0
- manual_resume: false
- final_status: PASS — assembly complete, 16/16 workers, contract PASS, smoke 18/18, tests 10/10

---

## AGENT_STATUS

| # | Agent | Commit | Status |
|---|-------|--------|--------|
| 1 | scaffold | 15112de | COMPLETED |
| 2 | database | f95eb29 | COMPLETED |
| 3 | auth | 39eaf4f | COMPLETED |
| 4 | projects | a4ddbdb | COMPLETED |
| 5 | scenes | 7e62d6c | COMPLETED |
| 6 | cast | 3b08dfc | COMPLETED |
| 7 | crew | 647d156 | COMPLETED |
| 8 | departments | 0b21995 | COMPLETED |
| 9 | locations | 9f493ac | COMPLETED |
| 10 | schedule | 6315a7b | COMPLETED |
| 11 | callsheets | 36e3ee9 | COMPLETED |
| 12 | budget | 3d99f33 | COMPLETED |
| 13 | expenses | 7395432 | COMPLETED |
| 14 | reports | 1753ae5 | COMPLETED |
| 15 | search | 8e24747 | COMPLETED |
| 16 | tests | e445a79 | COMPLETED |

| 1 | scaffold | 6655b25 | PASS |
| 2 | database | 30eea47 | PASS |
| 3 | auth | fa095ee | PASS |
| 4 | projects | 2db778a | PASS |
| 5 | scenes | 4eecc4b | PASS |
| 6 | cast | 5b05eb2 | PASS |
| 7 | crew | 45989ff | PASS |
| 8 | departments | 301f169 | PASS |
| 9 | locations | 920b92a | PASS |
| 10 | schedule | f703e60 | PASS |
| 11 | callsheets | 3546c2c | PASS |
| 12 | budget | 0fabcb5 | PASS |
| 13 | expenses | cd4c80b | PASS |
| 14 | reports | af00e66 | PASS |
| 15 | search | e46c0c1 | PASS |
| 16 | tests | 49fc1d5 | PASS |

### Ownership Gate: PASS (16 agents) — each worker commit touched only assigned files (docs/reports/070/ownership-gate.md). Disjoint ownership → FC51 cherry-pick clean. Worktrees rooted on f90aed8 (now ancestor of feat → merge-base == worktree-root, O3 invariant).

### KNOWN ISSUE (HIGH) — worktree-base SPEC divergence (new FC51 facet): Worker worktrees rooted on master f90aed8, whose docs/plans/film-production-pm-plan.md is the STALE pre-convergence 2010-line spec (feat HEAD has the converged 2295-line spec). Workers read the stale plan (missing 4 sections: Transition Maps, Orchestration Entrypoints/FC50 full-sig table, Dept-Head exact-code, Call Sheet Generation Algorithm). MITIGATED: the orchestrator's agent briefs injected the convergence fixes directly (no-FTS-triggers single-writer, create_expense->int|None, department_head role string, money suffix-free fields, get_scenes_by_ids keys, idempotent callsheet, FC50 signature discipline) — worker reports confirm compliance. Residual risk (callsheet algorithm details, exact transition sets, signature formalization) deferred to contract-check + flow-trace review. LESSON: FC51 worktree-base divergence extends to the SPEC FILE, not just code; mitigation here was the briefs, which is fragile — orchestrator must ensure the converged spec is present at the worktree base before spawning.

### Review: 0 P1, 2 P2 | Fix commits: a09a725 (budget departments context P2-1); P2-2 deferred (todo 070)

---

## FAILURES

| Severity | Detail | Resolution | Failure Class |
|----------|--------|-----------|--------------|
| P2 | Budget allocate form: `GET /budget/<pid>` did not pass `departments` list to render context. Allocate form dropdown had no data source. | Fixed in commit a09a725: added `get_departments(conn, project_id)` to `budget.index` route and passed to template. | FC4 variant (spec Route Table did not prescribe render-context variables for form-driving GETs) |
| P2 | Double `get_schedule_entries` call: `callsheets.generate` route calls it at line 70 as guard, then `generate_call_sheet` calls it again at line 32 internally. Two identical SQL queries per generate request. | Deferred — todo #070. Fix: pass pre-fetched entries as optional parameter to `generate_call_sheet`. Route-level guard provides useful UX flash message. | FC27 variant (regression from run 063 fix; fix not carried into converged spec) |
| P3 | DOOD grid N+1 query pattern: `get_dood_grid` executes 1 SQL per cast member in a Python loop. | Advisory only — acceptable at indie/mid-budget scale (≤40 cast). | Performance advisory |
| P3 | `sort_order` TOCTOU in `schedule.create`: MAX read outside lock before `create_schedule_entry`. | Advisory — non-data-loss (reorder resolves duplicates). Acceptable for single-producer scope. | FC43 advisory |
| P3 | `VALID_PHASE_TRANSITIONS` uses sets (impl) vs lists (spec). | No action — sets are strictly better for `in` checks (O(1)). | No class — spec/impl acceptable divergence |

---

## RUN_METRICS

### Final Build Metrics

| Metric | Value |
|--------|-------|
| Total agents | 16 |
| FC37 commit failures | 0 (100% commit rate) |
| Merge conflicts at assembly | 0 |
| Python source files | ~44 |
| HTML templates | ~37 |
| Total files | ~94 |
| LOC estimate | ~7,600 |
| Smoke tests | 18/18 PASS |
| Critical-flow tests | 10/10 PASS |
| Review P1 findings | 0 |
| Review P2 findings | 2 (1 fixed, 1 deferred) |
| Review P3 findings | 3 (all advisory) |
| Assembly method | cherry-pick (f90aed8..<branch> per worker) |
| Assembly fixes | 2 (database.py :memory: fix + test fixture fixes: 38714db; budget departments: a09a725) |
| Worktree base | f90aed8 (master HEAD = ancestor of feat, O3 invariant) |
| Track A proof | assembly-summary.md Commits Assembled table |
| Track B proof | spec-completeness-check.md Check 1b FIRED+PASSED (10 entrypoint rows) |
| Track C proof | spec-eval-1780926640/spec-eval-gate.json (ADVISORY, did not block) |
| Spec-file divergence | MITIGATED via brief injection (4 sections missing from stale master spec) |

### Agent Performance Summary

| # | Agent | Commit | Status | Notable |
|---|-------|--------|--------|---------|
| 1 | scaffold | 6655b25 | PASS | app factory, base template, CSP headers |
| 2 | database | 30eea47 | PASS | schema.sql, database.py, models barrel |
| 3 | auth | fa095ee | PASS | decorators (login_required, require_project_member, require_role) |
| 4 | projects | 2db778a | PASS | create_project with atomic creator enrollment |
| 5 | scenes | 4eecc4b | PASS | 6-state status machine, TOCTOU-safe transition |
| 6 | cast | 5b05eb2 | PASS | get_cast_for_scenes FC50 export |
| 7 | crew | 45989ff | PASS | F-H6 dept-head ownership, inline UPDATE+FTS5 txn |
| 8 | departments | 301f169 | PASS | get_departments FC50 export, assign_department_head |
| 9 | locations | 920b92a | PASS | get_location FC50 export |
| 10 | schedule | f703e60 | PASS | SortableJS reorder, get_schedule_entries FC50 export |
| 11 | callsheets | 3546c2c | PASS | 6-import aggregation, idempotent generation |
| 12 | budget | 0fabcb5 | PASS | allocate with TOCTOU guard; render context P2 fixed post-assembly |
| 13 | expenses | cd4c80b | PASS | F-H6 expenses, create_expense returns None on overspend |
| 14 | reports | af00e66 | PASS | DOOD grid, production progress |
| 15 | search | e46c0c1 | PASS | FTS5 single-writer, contentless index, rowid encoding |
| 16 | tests | 49fc1d5 | PASS | 18 smoke + 10 critical-flow tests |

## Advisory Baseline
baseline_sha: d6794d32d1eac0607720246ab54094e1b1ca2bd8

## Template Version

v1.0 — 2026-05-03 (created after WRC Build #7)
