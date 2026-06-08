---
title: "Film Production PM Tool — Run 070 (16-Agent Swarm + Orchestration Hardening Validation)"
date: 2026-06-08
run_id: "070"
project: film-production-pm
tags: [flask, sqlite, jinja2, bootstrap5, sortablejs, swarm, callsheets, fts5, fc51, fc50, spec-convergence, validate-on-real-build, orchestration-hardening]
build_method: swarm
agents: 16
files: ~94
loc: ~7600
status: complete
branch: feat/film-production-pm
related_solutions:
  - 2026-06-02-film-production-pm-swarm-build.md
  - 2026-06-07-autopilot-orchestration-hardening.md
  - 2026-04-30-spec-convergence-loop.md
---

# Film Production PM Tool — Run 070 (16-Agent Swarm + Orchestration Hardening Validation)

## What Was Built

A full rebuild of the Film Production PM Tool — the same 16-agent vertical swarm from Run 063
(same spec, same domain), but this time executed as the **validate-on-real-build vehicle** for
the frozen orchestration-hardening branch (Tracks A, B, C). Smoke: 18/18 PASS. Tests: 10/10 PASS.

This run is primarily significant for what it proved about the infrastructure, not just what it
delivered as an application.

---

## Application: What Was Delivered

The same 7 MVP features as Run 063, now rebuilt with the converged 2295-line spec:

- **Project Dashboard** — phase state machine (development→pre_production→production→post_production→distribution), budget gauge, scene completion stats
- **Crew & Cast Database** — role-based access, department-head ownership enforcement (F-H6 exact-code pattern)
- **Scene Breakdown** — INT/EXT/INT-EXT, day/night/dawn/dusk, page-count-in-eighths, 6-state status machine, element tagging
- **Shooting Schedule** — SortableJS drag-and-drop reorder, TOCTOU-safe schedule entries
- **Call Sheet Generator** — idempotent generation (DELETE-then-INSERT with ON DELETE CASCADE), 6 cross-module imports, TOCTOU-safe
- **Budget Tracker** — department allocations with atomic overspend guard, line items
- **Reports: DOOD Grid + Production Progress** — Day Out of Days matrix

**Stack:** Python 3.14, Flask + Flask-WTF (CSRF), SQLite (WAL, autocommit=True, busy_timeout=5000), Jinja2, Bootstrap 5.3.3 dark theme, SortableJS CDN, FTS5 full-text search.

---

## Orchestration Hardening: What Was Validated

This run was the real-build proof for three infrastructure tracks frozen in the
orchestration-hardening branch (`docs/solutions/2026-06-07-autopilot-orchestration-hardening.md`).

### Track A — FC51 Cherry-Pick Base Consistency (Per-Worker Merge-Base)

**Proof artifact:** `docs/reports/070/assembly-summary.md` Commits Assembled table.

All 16 worker worktrees rooted on `f90aed8` (master HEAD at spawn time). The assembly-invariant
merge (9w.9) merged master into feat BEFORE spawning workers, making `f90aed8` both an ancestor
of feat and the merge-base for all workers. Cherry-pick range `f90aed8..<worker-branch>` produced
exactly each worker's own commit. Zero conflicts across 16 agents. **FC51 base-divergence
cherry-pick assembly confirmed working on a real 16-agent build.**

### Track B — FC50 Orchestration Entrypoint Presence Guard (Spec-Completeness Check 1b)

**Proof artifact:** `docs/reports/070/spec-completeness-check.md`, Surface 2.

10 orchestration entrypoint rows with `Type = orchestration entrypoint` — all 10 had non-empty
Full Signature cells. **Check 1b FIRED (found rows) + PASSED (all had full sigs).** This is the
first real-build activation of the FC50 guard. Prior runs either had no entrypoint rows or the
guard hadn't been deployed.

### Track C — Spec-Eval Advisory Demotion

**Proof artifact:** `docs/reports/070/spec-eval-1780926640/spec-eval-gate.json`

Spec-eval ran, logged, and emitted FAIL (ADVISORY) — 15/277 claims failed, all due to
single-shot-agent scorer artifacts (eval emitted SQLAlchemy+REST stack vs spec's sqlite3+blueprints,
plus output truncations). **Did NOT block spawn.** Track C confirmed: spec-eval is an advisory
log, not a spawn gate.

---

## Validate-on-Real-Build: NEW FINDING (FC51 Extended)

### Worktree-Base SPEC FILE Divergence — A New FC51 Facet

**Prior FC51 understanding:** Worker worktrees root on an older commit → they see old CODE, causing
merge conflicts or stale function signatures.

**New finding (Run 070):** The spec FILE itself (`docs/plans/film-production-pm-plan.md`) is part
of the worktree, and it diverged. Workers rooted on master `f90aed8`, which had the STALE
pre-convergence 2010-line spec. The converged 2295-line spec lived only on `feat` HEAD.

Workers were missing 4 spec sections:
1. Transition Maps (`VALID_PHASE_TRANSITIONS`, `VALID_SCENE_TRANSITIONS`)
2. Orchestration Entrypoints (FC50 full-signature table)
3. Dept-Head exact-code (F-H6)
4. Call Sheet Generation Algorithm (idempotent pattern, TOCTOU)

**Mitigation used:** The orchestrator's agent briefs injected the convergence fixes directly
(verbatim contract text: no-FTS-triggers, `create_expense` returns `int|None`, `department_head`
role string, money suffix-free fields, `get_scenes_by_ids` keys, idempotent callsheet, FC50
signature discipline). Worker reports confirmed compliance. Contract check PASSED.

**Why it held:** The 4 missing sections were all in the injected brief text, which workers
prioritized over the stale plan. Brief injection was the mitigation. It worked — but it's fragile.

**The fragility:** Brief injection is manual. If the orchestrator forgets to inject a convergence
section, workers silently read the stale spec. There is no gate that detects "brief contains newer
spec than worktree spec." The risk is invisible until a contract check or review catches it.

---

## Risk Resolution (Feed-Forward)

**Feed-Forward risk (from plan frontmatter):**
> "Call sheet Cross-Boundary Wiring — 6 cross-module imports is the densest coupling surface
> attempted. A single name mismatch or wrong return type crashes the call sheet page."

**What actually happened:**
The callsheet wiring was clean. Flow-trace review verified all 6 imports end-to-end:

| Import | Producer | Consumer | Return Keys Used |
|--------|---------|---------|-----------------|
| `get_schedule_entries` | schedule_models | callsheet_models | `scene_id`, `location_id` |
| `get_scenes_by_ids` | scene_models | callsheet_models | `id`, `scene_number`, `int_ext`, `day_night`, `page_count_eighths` |
| `get_cast_for_scenes` | cast_models | callsheet_models | `id` (as cast_member_id) |
| `get_location` | location_models | callsheet_models | `name`, `address`, `nearest_hospital` |
| `get_crew_by_department` | crew_models | callsheets routes | `department_name`, `members[{id, name, role_title, phone}]` |
| `get_departments` | department_models | callsheets routes, expenses routes, crew routes | `id`, `name`, `head_id` |

No name mismatches. No wrong return types. The FC50 full-signature table in the spec was the
key enabler — it gave both producing and consuming agents exact contracts to implement against.

**What was learned (delta between expectation and reality):**
The risk was real but pre-empted by two layers: (1) the spec's FC50 Orchestration Entrypoints
table gave agents exact signatures; (2) the spec-completeness check (Check 1b) verified the
table was present and fully specified before workers spawned. The wiring worked because the spec
made the contract explicit, not because agents guessed correctly.

**The deeper risk that materialized:** Spec-file divergence (FC51 extended) was riskier than
the callsheet wiring. The 4 missing spec sections included the callsheet generation algorithm
itself. Brief injection saved this run — but the mitigation is fragile. See the new lesson below.

---

## What Went Right

### Spec-Completeness Check (9w.6) as a real pre-spawn gate

The spec-completeness checker (Check 1b) fired on the 10 orchestration entrypoint rows and
verified all had full signatures. This is Track B's validation that the gate works in production.
The gate caught missing signatures in prior builds; here it confirmed completeness before spawning.

### Zero assembly conflicts across 16 workers

FC51 base-divergence cherry-pick assembly: 16 workers, 16 single-commit cherry-picks, zero
conflicts. The vertical ownership split (one blueprint per agent) remained the key enabler.

### TOCTOU-safe write patterns throughout

Every model write function implemented the pattern correctly:
- `generate_call_sheet`: reads-outside-lock, writes-inside-BEGIN-IMMEDIATE
- `create_schedule_entry`: TOCTOU duplicate check inside lock
- `reorder_schedule`: full ID set validation inside lock
- `allocate_budget`: rechecks total allocation inside lock
- `create_expense`: re-checks overspend inside lock

### FTS5 single-writer pattern preserved

`schema.sql` has zero TRIGGER definitions. `index_entity`/`remove_entity` called explicitly from
4 route blueprints in the same transaction as the source-row write (FC52). Search sanitization
with `_sanitize_query` → phrase-wrap pattern from Run 061 applied correctly.

### Prior P1 from Run 063 closed

Run 063 P1: missing DATE_RE validation in callsheets.generate. Run 070: DATE_RE applied at
callsheets/routes.py:33+65 — confirmed in review. Fix carried into the converged spec.

### dept-head ownership (F-H6) correctly implemented

Both crew and expenses routes implement the `_allowed_dept_ids`/`_is_head()` pattern. The spec
provided the exact-code section (F-H6) which gave workers a template to implement — no guesswork.

### SQLite `:memory:` shared connection (assembly fix)

The inline assembly fix (shared `_MEMORY_DB` connection in `app.config`) correctly solves the
cross-request isolation problem for in-memory databases. Production file-based databases unaffected.

---

## What Went Wrong

### P2-1: Budget allocate form — departments list missing from GET /budget render context

`budget.index` route rendered `budget/index.html` without `departments` in the template context.
The allocate form needs a `<select name="department_id">` dropdown.

**Root cause:** Budget agent wrote the allocate POST handler correctly (validates department_id
against `get_departments`), but the GET route didn't pass the departments list for the form
dropdown. The spec's route table for GET /budget didn't explicitly state to pass `departments`.

**Fix applied:** Added `departments = get_departments(conn, project_id)` to `budget.index` route
and passed to template. Commit `a09a725`.

**Prevention:** Spec's Route Table should explicitly list render-context variables for any route
that drives a POST form with a database-backed dropdown. Add a "Render Context" column to Route
Tables for GET routes that feed forms.

### P2-2 (deferred): Double `get_schedule_entries` in callsheets.generate

`callsheets.generate` pre-checks entries at the route level, then `generate_call_sheet` calls
`get_schedule_entries` again internally. The route-level guard provides useful UX ("No scenes
scheduled for that day"), but it's a second identical SQL query.

**Root cause:** Run 063 fixed this by removing the route-level guard. The fix was not carried into
the converged spec (the spec section describes the model behavior but doesn't prescribe the route).

**Status:** Deferred (todo #070). The double query is non-critical at indie scale. Clean fix is to
pass pre-fetched entries as an optional parameter to `generate_call_sheet`.

**Prevention:** When a review fixes an anti-pattern, the fix should be reflected in the spec's
Input Validation Prescriptions or Coordinated Behaviors (e.g., "route-level checks that duplicate
model-internal checks should pass data through, not re-query").

---

## Learnings

### NEW LESSON: FC51 Worktree-Base Divergence Extends to Spec Files

**Class:** FC51 variant / Orchestration anti-pattern

**Pattern:** Worker worktrees root on an earlier commit. If the spec file (`docs/plans/*.md`) was
updated AFTER the worktree root commit (e.g., during spec convergence on a feature branch), workers
read the stale spec. This is different from code-file divergence — stale code causes merge conflicts
(visible), but stale spec causes behavioral divergence (invisible until review).

**Key insight:** Code-file divergence surfaces at assembly time (merge conflict). Spec-file
divergence surfaces at review time (behavioral mismatch vs converged spec). The latter is harder
to catch automatically.

**The current mitigation (brief injection) is fragile because:**
1. It's manual — the orchestrator must know which spec sections changed and inject them.
2. There is no validation that brief content matches the current spec — workers could receive
   a stale or incomplete brief with no error.
3. Brief content is not version-controlled alongside the spec changes.

**The correct fix (orchestrator rule):** Before spawning workers, ensure the converged spec is
present at the worktree base. Concretely:
- Option A: Cherry-pick or merge the spec-only commit into each worktree before spawning.
- Option B: Pass the spec file path as a symlink to the feat branch version (requires FS support).
- Option C (current, stopgap): Inject verbatim spec sections into every worker brief. Works but
  requires manual curation.

**Impact rating:** HIGH. On this build, brief injection saved the run. On a future build where
the orchestrator forgets to update the injected sections, the failure is invisible until review
or testing catches it.

**Fold into agent-pitfalls.md:** FC51 update: "Worktree-base divergence extends to the SPEC FILE.
If the converged spec lives on feat but worktrees root on master, workers read the stale spec.
Orchestrator MUST ensure the converged spec is present at the worktree base before spawning —
either by cherry-picking the spec update commit into each worktree, or by injecting all changed
spec sections verbatim into every worker brief."

### CONFIRMED LESSON: FC50 Full-Signature Table is Load-Bearing for Cross-Boundary Wiring

Run 070 is the second build (after Run 069) confirming that the FC50 Orchestration Entrypoints
table is the primary defense against cross-boundary wiring failures. When the table exists and
has full signatures:
- Producers know exactly what to implement.
- Consumers know exactly what to call and what keys to expect.
- The spec-completeness checker (Check 1b) can automatically verify the table is complete.
- Flow-trace review has ground truth to compare against.

The callsheet 6-import wiring had zero mismatches in Run 070 — the same surface that fails in
naive multi-agent builds. The table is the differentiator.

### CONFIRMED LESSON: Spec Convergence Loop Prevents Cross-Section P0s

The Spec Convergence Loop (Codex + Claude + NotebookLM + human structural verification) ran
before this build and caught 2 P0s before implementation. The human structural verification pass
(cross-section field matching, type consistency, fixtures) is non-optional — AI tools miss
cross-section contradictions that are obvious to a human reading section N against section M.

Run 070 zero P1s at review confirms that the convergence loop works end-to-end.

---

## Validate-on-Real-Build Assessment (Orchestration Hardening)

| Track | Proof Artifact | Result |
|-------|---------------|--------|
| Track A: FC51 cherry-pick assembly | assembly-summary.md (16 workers, all f90aed8 base) | CONFIRMED |
| Track B: FC50 Check 1b guard | spec-completeness-check.md (Check 1b FIRED+PASSED) | CONFIRMED |
| Track C: spec-eval advisory | spec-eval-1780926640/ (FAIL ADVISORY, did not block) | CONFIRMED |

All three tracks confirmed. The orchestration-hardening branch is validated on a real 16-agent
build. Branch may be merged after this run's tail completes.

---

## Key Metrics

| Metric | Value |
|--------|-------|
| Agents | 16 |
| Worker commits | 16 (cherry-picked from f90aed8) + 1 assembly fix (38714db) + 1 P2 fix (a09a725) |
| FC37 commit failures | 0 |
| Merge conflicts | 0 |
| Smoke tests | 18/18 PASS |
| Critical-flow tests | 10/10 PASS |
| Review P1 findings | 0 |
| Review P2 findings | 2 (1 fixed, 1 deferred) |
| Track A/B/C proofs | All 3 confirmed |
| Worktree base | f90aed8 (master HEAD, now ancestor of feat) |
| Assembly method | cherry-pick (range f90aed8..<branch> per worker) |
| Ghost file cleanup | 9w.9 (28 run-068 files removed before spawn) |

---

## Prevention Strategies

1. **Pre-spawn: verify spec file is current in worktrees.** Before spawning workers, confirm that
   `docs/plans/<spec>.md` at the worktree base matches the latest converged spec on the feature
   branch. If they differ, cherry-pick the spec update commit into each worktree, or inject all
   changed sections verbatim into worker briefs.

2. **Route Table should list render-context variables for form-driving GETs.** Add a "Render
   Context" column or subsection to Route Tables for GET routes that feed POST forms with
   database-backed dropdowns. This prevents the P2-1 "missing departments in context" class of bug.

3. **Review pass: compare assembled code against converged spec, not worktree spec.** The review
   reviewer's reference document should be the feat-branch plan, not the file in the assembled
   worktree (which may be stale).

4. **Brief injection checklist: list all injected spec sections explicitly.** When the orchestrator
   injects spec sections into worker briefs, log the list of injected section titles in the
   orchestration notes. This creates an audit trail and helps reviewers know what to scrutinize.

---

## Related Documents

- `docs/solutions/2026-06-02-film-production-pm-swarm-build.md` — Run 063 (same project, prior build)
- `docs/solutions/2026-06-07-autopilot-orchestration-hardening.md` — The infrastructure being validated
- `docs/solutions/2026-04-30-spec-convergence-loop.md` — Spec convergence loop process
- `docs/reports/070/assembly-summary.md` — Track A proof (per-worker cherry-pick table)
- `docs/reports/070/spec-completeness-check.md` — Track B proof (Check 1b FC50 guard)
- `docs/reports/070/spec-eval-1780926640/` — Track C proof (advisory log)
- `docs/reports/070/review-summary.md` — Full review findings (0 P1, 2 P2, 3 P3)

---

## Feed-Forward

- **Hardest decision:** Whether to treat the spec-file divergence (FC51 new facet) as a run failure
  or a managed risk. Decided to treat as managed risk because brief injection worked and all gates
  passed. But the fragility is real and must be addressed in the orchestrator before the next
  build with a spec convergence gap.

- **Rejected alternatives:** Stopping the run at 9w when spec divergence was detected and re-syncing
  all worktrees. This would have required respawning all 16 workers. The brief-injection path was
  chosen as the lower-disruption mitigation. Correct choice for this run, not repeatable in general.

- **Least confident:** Whether the FC50 full-signature table alone is sufficient to prevent
  callsheet wiring failures on the next build, or whether a build without spec convergence (or with
  a larger cross-boundary surface) would still fail. Track B proves the gate works; but the gate
  only checks presence and non-emptiness of signature cells — it does not validate that the
  signatures match the actual implementation. A future check could compare spec signatures against
  AST-extracted signatures from the code.
