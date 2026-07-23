---
title: "P1/P2 — Encode the unattended multi-wave swarm barrier loop"
date: 2026-07-22
status: draft
phase: plan
revision: 4  # resolves Codex re-review #2 NO-GO: falsifiable end-to-end 2-wave spike, per-wave-swarm-runner blocking spike, single executable gate architecture (firebreak stays ACTIVE — no toggle), write-ahead resume phases, assembly-base proof with --no-ff accounting, self-authoritative verify_wave, wave schema matched to swarm-planner reality, valid EARS commands, honest scope
branch: feat/p1p2-unattended-swarm-wave-barrier
relates_to:
  - unattended-big-run-trust-gate (MEMORY)
  - swarmlimit-run-083 (harvest H2/H5/H6/H9; solution doc)
  - fc68-firebreak-cwd-root-anchor (merged 4da3eff)
feed_forward:
  risk: "Design X (workers write+commit only; ALL cross-module integration and self-verification deferred to per-wave assembly) is the only design compatible with the firm no-master-push policy. Its load-bearing premise — a dependent worker never needs a prior wave's files PRESENT at authoring — must be proven, not assumed, and the FIRST integrated compile/import happens only at assembly (Run 083 H6/H9 show the integrated tree frequently does NOT boot until an assembly-fix). Spike 0a is now a genuine end-to-end two-wave spike: Wave 2 authors with Wave 1 ABSENT, then BOTH waves are assembled and the integrated tree must pass a pinned compile+import gate. A failure that invalidates dependent waves STOPS the run for plan revision + Codex review — it is NOT a silent independent-waves-only scope cut."
  verify_first: true
---

# P1/P2 — Encode the unattended multi-wave swarm barrier loop

## Context

The trust gate (`unattended-big-run-trust-gate`) blocks launching a ≥20-agent swarm fully
hands-off. Run 083 succeeded only because a human hand-ran the wave barriers, approved every
push, and cat-verified the firebreak after a live fail-open. This plan targets criteria (2)
firebreak needs no *manual* toggling and (3) the wave-barrier / push mechanic runs from the
SKILL, not live judgment. P1 (FC68/083-W6) is already merged (`4da3eff`); the per-wave firebreak
read-back already exists (SKILL 1b, lines 749-766), but no deterministic multi-wave loop,
verifier, resume machine, or wave schema exists.

## Accepted decisions (fixed constraints — do not relitigate in the work phase)
- The two exact file-path additions to `TRUSTED_PIPELINE_SCRIPT_PATHS`
  (`tools/wave_artifact.py`, `tools/verify_wave.py`) are approved.
- No name-based or module-mode (`-m`) carve-out in the firebreak classifier.
- No unattended CODE push to `origin/<default>`.
- TaskStop failure is fail-closed: always abort on timeout when termination cannot be proven.
- **Chosen gate architecture (§3.4, rev4): the firebreak stays ACTIVE for the ENTIRE
  multi-wave run — there is NO deactivation and NO toggle window in the loop.** The single
  per-wave integrated dependency gate is executed inside the (TRUSTED) swarm-runner using only
  firebreak-legal invocations. This is the one executable architecture; the alternative
  (deactivate/reactivate toggle around a `python -m compileall` orchestrator gate) is REJECTED.

## Codex re-review #2 resolution map (revision 4)

| Codex re-review #2 blocker | Resolution |
|---|---|
| 0a not falsifiable end-to-end | §0.0a — genuine two-wave spike: Wave 2 authors with Wave 1 ABSENT, then BOTH waves assembled; PASS requires the INTEGRATED tree to pass the pinned compile+import gate. A dependent-wave-invalidating failure STOPS for plan revision + review (§0 "STOP, do not scope-cut"). |
| spike_per_wave_swarm_runner not blocking | §0.0c — moved into blocking §0 with fixture, commands, PASS criteria, firebreak expectations, report isolation, cleanup expectations, and a two-sequential-invocation no-leak proof. |
| gate-order contradiction (swarm-runner runs gates before the toggle; `python -m` deferred) | §3.4 — ONE architecture: firebreak stays ACTIVE all run; the blocking integrated dependency gate = swarm-runner contract-check (grep) **+ a new blocking integrated import-smoke run as `pytest`** (firebreak-legal, identity-agnostic); NO `python -m compileall`, NO deactivation. §5 removes the toggle steps entirely. |
| resume machine incomplete | §5 — nine write-ahead transition phases; every resume re-asserts firebreak ACTIVE first; enumerate+stop ALL run-scoped tasks incl. pre-persist spawns (by name prefix); recovery for assembly-exists / branch-advanced-before-merge_completed; compare-and-reuse vs conflicting artifact. |
| assembly-base proof wrong | §3.3 + §7 — ancestry repair BEFORE base is finalized; `worker_base_sha` pinned pre-spawn; per-worker head/merge-base/delta-count captured before cleanup (cleanup DEFERRED until after verify in wave mode); fork-point == pinned base proven per worker; commit count = Σ(worker deltas)+1 (`--no-ff` merge); stale-fork fixture must FAIL. |
| verify_wave not authoritative | §7 — Wave/Required/roster DERIVED from `--plan` (not caller-supplied); every referenced evidence file re-read and cross-checked (forged verdicts FAIL); exact run identity; full CLIs for all three modes; mode-sensitive HEAD checks; evidence preserved until verify. |
| wave schema ≠ swarm-planner reality | §4 + §7 — `.claude/agents/swarm-planner.md` ADDED to scope with a pinned per-agent `**Wave:**`/`**Required:**` format; Export-Names→file→agent normalization defined; duplicate/missing/unresolved/ambiguous/aggregate/out-of-roster all rejected (aggregate only via explicit member list); build-order-sensitive marker defined; worker prompt EXPLICITLY prohibits cross-module execution. |
| EARS commands invalid | §8 — `python3 tools/test_*.py --case <name>` (matches the repo's plain-stdlib test convention); every listed crash-boundary/forgery/reconcile/parse case has a named test or live spike; classifier baseline 282→284 (verified 282 current). |
| scope dishonest | §1 — swarm-planner.md, swarm-runner.md, tail-resume/SKILL.md all added with the exact change each needs. |

## 0. Verify-first spikes (BLOCKING — gate 0, before ANY SKILL/tool code)

All spikes below run in the work-phase branch; their outcomes are recorded BEFORE the first
SKILL/tool edit. **A spike failure is a STOP-for-plan-revision, not a work-phase judgment call
and NOT a silent scope cut.** If any spike fails in a way that invalidates dependent waves,
halt the work phase, record the outcome in `docs/reports/p1p2-spikes/`, and return to plan +
Codex review.

### 0a — Falsify the spec-only premise with a genuine END-TO-END two-wave spike

**Fixture (temp git repo, built by a pinned setup script `tools/spike_two_wave_setup.py`):**
- A throwaway repo at `$(mktemp -d)/twowave` with a branch `main` (the "default branch") and a
  feature branch `feat-spike` forked from `main`.
- Package `pkgspike/` with `__init__.py` (empty) committed to BOTH branches at fork.
- Export Names contract (spec fragment committed to `main`): `pkgspike.database.query() -> list`
  produced by Wave-1 agent `database`; consumed by Wave-2 agent `routes` in
  `pkgspike/routes.py` via `from pkgspike.database import query`.
- **Wave-1 file `pkgspike/database.py` is ABSENT from the Wave-2 worktree** (this is the whole
  point): the Wave-2 worker is rooted on `origin/main`, which carries only the spec + empty
  `__init__.py`.

**Environment (pinned, exact):**
- Interpreter: `/Users/alejandroguillen/Projects/sandbox/.venv/bin/python` (Python 3.14.6).
- Test runner: `/Users/alejandroguillen/Projects/sandbox/.venv/bin/pytest`.
- Static type-checker: **none is installed** (`.venv` has no `mypy`/`pyright`). The "typecheck"
  gate is therefore PINNED as the import-smoke below (which performs real cross-module name
  resolution at import time — a strict superset of `compileall` syntax checking). The spike
  records `typecheck: N/A (no checker configured; substituted by import-smoke)` explicitly; it
  does NOT silently skip a gate.

**Step 1 — Wave-2 authoring with Wave-1 ABSENT.** In the Wave-2 worktree (Wave-1 file absent),
have the Wave-2 worker write `pkgspike/routes.py` (importing `query` from the spec's Export
Names table) and `git add -A && git commit`. Then, in that SAME worktree, run and RECORD the
outcome of each, one Bash call each:
- author+commit: expected SUCCEED.
- `.venv/bin/python -m compileall pkgspike/routes.py` — expected FAIL/undetermined only if it
  imports; `compileall` compiles syntax without importing, so it should SUCCEED even absent →
  record actual.
- import: `.venv/bin/python -c "import pkgspike.routes"` — expected **FAIL** (ModuleNotFoundError:
  pkgspike.database) with Wave-1 absent.
- typecheck (== import-smoke): same as import above; record N/A-substituted result.

**Step 2 — Assemble BOTH waves and gate the integrated tree.** On `feat-spike`, cherry-pick the
Wave-1 delta (author `pkgspike/database.py`) THEN the Wave-2 delta (`pkgspike/routes.py`) onto an
assembly branch cut from `feat-spike` HEAD (both files now present). Then run the PINNED
integrated gate on the assembled tree, one Bash call each:
- `.venv/bin/python -m compileall pkgspike` → must exit 0.
- `.venv/bin/pytest tools/spike_two_wave_importsmoke.py` — a pytest test that `importlib`-imports
  every module under `pkgspike/` (incl. `pkgspike.routes`, which now resolves `pkgspike.database`)
  → must exit 0.

**PASS criterion (BOTH required):**
1. Step-1 author+commit SUCCEEDS with Wave-1 absent (a worker can WRITE `from pkgspike.database
   import query` from the spec's export NAMES without the file present), AND
2. Step-2 INTEGRATED tree passes `compileall` + import-smoke.
If Step-1's import/typecheck of a cross-wave symbol FAILS with Wave-1 absent, that is EXPECTED
and CONFIRMS the design constraint (workers must be write+commit-only; self-verification deferred
to assembly). Proceed with Design X + the §4 enforcement that worker briefs contain no
cross-module execution step.

**FAIL criterion (either ⇒ STOP for plan revision + Codex review; do NOT auto-scope-cut):**
- (a) Step-1 author+commit cannot be produced correctly without the prior files present, OR
- (b) Step-2's integrated tree cannot be made to pass the compile+import gate (i.e. per-wave
  assembly cannot integrate a dependent wave at all).
Either outcome means dependent unattended waves are not merely "reduced in scope" — the design's
core mechanic is broken. Record the failure and STOP. The §4 static validator's
runtime-dependent-edge rejection is a PRE-SPAWN guard for well-formed plans; it is NOT the
recovery path for a 0a spike failure.

### 0b — TaskStop observability
Spawn one long-running background worker; `TaskStop` it; confirm `TaskList`/`TaskGet` reports it
terminated within a bounded poll (record the bound). PASS ⇒ the prove-zero-live gate (§3.1) is
viable. FAIL ⇒ the gate is always-abort-on-timeout (the accepted fail-closed rule) — documented,
no design change, but recorded before proceeding.

### 0c — `spike_per_wave_swarm_runner` (BLOCKING — swarm-runner is safe to reuse per wave)
swarm-runner was authored for ONE whole-run assembly. Per-wave reuse must be proven side-effect
clean BEFORE the SKILL loop is written.

**Fixture:** a temp git repo with two independent, single-wave assemblies (`w1`, `w2`), each with
its own disjoint COMPLETED worker branch set, built by `tools/spike_per_wave_runner_setup.py`.

**Commands / procedure:**
1. Spawn the `swarm-runner` agent (mode `bypassPermissions`) for wave 1 with
   `reports_dir=docs/reports/SPIKE/w1/`, `assembly_branch=swarm-SPIKE-w1-assembly`,
   `original_branch=feat-spike`, and w1's worker branches. Wait for its terminal STATUS.
2. Spawn the `swarm-runner` agent AGAIN (fresh context) for wave 2 with
   `reports_dir=docs/reports/SPIKE/w2/`, `assembly_branch=swarm-SPIKE-w2-assembly`, and w2's
   worker branches.

**PASS criteria (ALL):**
- Each invocation writes its OWN `w<k>/assembly-summary.md` with line-1 `STATUS: PASS`; w2 does
  NOT overwrite any w1 report (report isolation proven by distinct `reports_dir`).
- After w2: `git branch --list 'swarm-SPIKE-*'` is EMPTY (both assembly branches deleted) and
  `git worktree list --porcelain` shows no leftover spike worktrees (cleanup complete).
- No run-level state leak: w2's `assembly-summary.md` references ONLY w2 branches/bases; the two
  summaries share no assembly-branch name, no temp file, and w2's cherry-pick bases are computed
  from w2 branches alone (grep the two summaries — zero cross-references).

**Firebreak expectations:** the firebreak is ACTIVE throughout the spike. swarm-runner runs as
the TRUSTED `swarm-runner` identity, so its pinned-tool and `pytest` calls are GREEN; its
app-boot smoke behaves exactly as in a single-wave run (documented — no toggling occurs).

**Failure action:** FAIL ⇒ STOP for plan revision. swarm-runner then needs explicit
wave-parameterization work (a run-level-state leak, e.g. a hardcoded `swarm-<run-id>-assembly`
name or a shared temp path) BEFORE any multi-wave loop is encoded — do not proceed on the
assumption of cleanliness.

### Run 083 reconciliation (why the premise is testable, not already disproven)
Run 083 pushed each wave's CODE to `origin/master` so Wave N+1 "saw" Wave N, and its harvest (H2)
notes an orchestrator "Wave-1 import check (all 12 modules) PASSED." Reconciliation: a worker
needs the export **names** (Export Names table) to WRITE `from swarmlimit.database import query`;
it needs the export **files present** only if it EXECUTES that import at author time. The SKILL
worker contract (Step 10w rules) is write-and-commit-only (rev4 adds an explicit rule 11
prohibiting cross-module execution), so the 083 per-wave code push was **sufficient but not
proven necessary**. The necessary channel — the converged SPEC at every worktree base — is served
by the ONE-TIME pre-Wave-0 provenance repair (§3.3). Run 083's per-wave "import check" is exactly
what rev4 relocates INTO per-wave assembly as the swarm-runner integrated import-smoke (§3.4).
Spike 0a settles empirically whether code-file presence was necessary at author time; the whole
design is gated on it.

## 1. What exactly is changing?

Deliverables (work phase, AFTER §0 passes). All additive; none touch firebreak *classifier
logic*.

1. **`.claude/skills/autopilot/SKILL.md`** — a new "Multi-Wave Barrier Loop (Path B)" section
   wrapping Step 10w, encoding the §5 sequence + the §5 write-ahead resume machine
   deterministically. Also the §3.5 narrowed default-branch policy note.
2. **`.claude/agents/swarm-planner.md`** *(NEW to scope)* — in wave mode (`waves > 1`) it MUST
   emit `**Wave:**` and `**Required:**` in every `### Agent:` section (§4/§7 exact format). Its
   duplicate-file validation is unchanged.
3. **`.claude/agents/swarm-runner.md`** *(NEW to scope)* — wave-mode changes only: (a) a BLOCKING
   integrated import-smoke (`pytest`) after the contract check and before the merge (§3.4); (b)
   record a per-worker "Worker Deltas" table (`worker_head_sha`, `merge_base_sha`, `delta_count`)
   into the assembly summary BEFORE any cleanup; (c) DEFER worktree/branch cleanup in wave mode
   until the orchestrator's `verify_wave --wave K` passes (evidence preservation, item 6).
   Single-wave behavior is byte-for-byte unchanged.
4. **`.claude/skills/tail-resume/SKILL.md`** *(NEW to scope)* — CHECKPOINT/tail-resume gains the
   §5 wave-resume state: on resume it first re-asserts firebreak ACTIVE, reads each
   `w<k>/transition-state.json`, and routes per §5. `--reconcile` runs fail-closed in the tail.
5. **`tools/wave_artifact.py`** (+ `tools/test_wave_artifact.py`) — `emit` writes the §6 `wave.md`
   atomically (temp + `os.rename`) from explicit args; `state` writes/updates the durable
   `transition-state.json` atomically.
6. **`tools/verify_wave.py`** (+ `tools/test_verify_wave.py`) — three pinned modes:
   `--validate-schema` (pre-spawn), `--wave K` (immediate, blocks next spawn), `--reconcile`
   (tail). Full CLIs + reject-sets in §7. All truth is derived from `--plan`/`--spec-path` + live
   git + re-read evidence files, never from a caller-supplied roster.
7. **`.claude/hooks/firebreak-classify.py`** — the two file-path allowlist additions
   (`tools/wave_artifact.py`, `tools/verify_wave.py`) to `TRUSTED_PIPELINE_SCRIPT_PATHS`.
   Data-only, TRUSTED-only, still deferred for workers; NO logic change, NO `-m` carve-out.
8. **`CLAUDE.md`** — the §3.5 narrowed default-branch policy line.
9. **Per-run artifacts** under `docs/reports/<run-id>/w<k>/`: `transition-state.json`,
   `worker-roster.md`, swarm-runner reports, and `wave.md` (the verifier input).

## 2. What must NOT change
- **Firebreak classifier logic.** No `-m`/name-based module carve-out; `-m` still yields no
  path-pinnable script; `TRUSTED_PIPELINE_SCRIPT_PATHS` stays file paths only (item 7 adds two
  paths, no logic). **All 282 existing classifier cases stay green; no new `-m` allow-case.**
- **Single-wave behavior.** `waves` absent or `1` ⇒ EXACTLY today's path: one Step 10w spawn,
  one 10.5w ownership gate, one swarm-runner assembly (with its existing inline cleanup), no wave
  artifacts, no `verify_wave` invocation, no import-smoke gate change.
- **Worker governance invariant.** The firebreak is ACTIVE across every worker spawn AND for the
  whole run (rev4: no deactivation at all).
- **Worker base ref.** Workers keep rooting on `origin/<default>` (baseRef=fresh); no worktree
  re-rooting (unverified harness capability).
- **swarm-runner's merge target.** Assembly merges to `original_branch` (feature branch) locally,
  never origin.
- **The pre-spawn provenance gate (9w.9.5).** Unchanged; `check_spec_provenance.py` takes
  `--repo`/`--default-branch`/`--original-branch`/`--spec-path` (verified CLI — no `--root`).

## 3. Design resolutions

### 3.1 P0 — prove zero live workers before spawning the next wave; durable across resume
Per wave, a durable **transition-state file** `w<k>/transition-state.json` is written (atomic)
and advanced through the §5 write-ahead phases. Because the firebreak now stays ACTIVE for the
whole run (§3.4), "prove zero live" is no longer a firebreak-deactivation precondition — it is a
**correctness precondition for spawning the NEXT wave** (a wave's workers must all be terminal
before the dependent next wave is authored). Terminal states:
- **COMPLETED** (completion notification) = terminal.
- **FAILED** (error result) = terminal; a REQUIRED FAILED worker ⇒ verifier FAIL.
- **TIMED_OUT** ⇒ `TaskStop` it and confirm terminated via `TaskList`/`TaskGet`
  (`TIMED_OUT_STOPPED`); a REQUIRED such worker ⇒ verifier FAIL.
- **OPTIONAL** worker terminal in any state may be skipped (recorded, non-fatal).
If ANY worker of wave k cannot be proven stopped, **ABORT** (firebreak already ACTIVE; no next
spawn); write transition-state `abort` + `wave.md` STATUS `ABORT` (§6). On resume (§5), the
recorded `task_id`s AND any tasks matching the run's name prefix are queried/stopped and
zero-live is re-proven BEFORE any respawn/assembly.

### 3.2 P1 — the spec-only premise (Design X), stated as a gated hypothesis
Design X: workers WRITE+COMMIT only (SKILL Step 10w rules 1-11; rule 11 explicitly PROHIBITS
running tests, executing cross-module imports, or running package-wide `compileall`/typechecks —
see §4); cross-wave integration AND all cross-module self-verification are deferred to per-wave
assembly (swarm-runner runs contract + a blocking integrated import-smoke on the assembled tree,
§3.4). A cross-wave edge is:
- **spec-only** — the consumer only *references* a producer export name (write+commit). Supported.
- **runtime-dependent** — the consumer's assignment/brief requires *executing* code that imports
  a prior-wave module at author time. NOT supported unattended; rejected pre-spawn (§4).
The SPEC (not code) must be at every worktree base — served by the ONE-TIME pre-Wave-0 provenance
repair (§3.3); static across waves, so no per-wave push. Spike 0a proves the premise end-to-end.

### 3.3 P1 — assembly base: ancestry repair BEFORE the base is finalized, then no replay
**Ordering fix (rev4):** the ancestry repair happens ONCE at run start, BEFORE `expected_base_sha`
and `worker_base_sha` are pinned — not lazily per wave.
1. Run the pre-Wave-0 provenance gate (9w.9.5); it may push a spec-only commit to
   `origin/<default>`.
2. **Immediately** merge `origin/<default>` into `original_branch`
   (`git merge origin/<default>`, the existing Run-070 pre-flight merge) and assert
   `git merge-base --is-ancestor origin/<default> original_branch`. If the assertion still fails,
   ABORT (do not spawn).
3. **Pin the durable base AFTER repair:** `worker_base_sha = git rev-parse origin/<default>`
   (the ref worktrees root on under baseRef=fresh) and `expected_base_sha = original_branch HEAD`.
   Both are recorded in `w1/transition-state.json` before Wave-1 spawn and are INVARIANT across
   all waves (no per-wave push, so `origin/<default>` never moves).
Because `origin/<default>` is an ancestor of `original_branch`, each worker's true fork point is
`origin/<default>` tip = `worker_base_sha`, so the cherry-pick range `merge-base..worker` is
worker-only (base/spec commits are already on `original_branch` and never in range → never
replayed). Per wave, `expected_base_sha` is re-read as the CURRENT `original_branch` HEAD (which
advances by exactly the prior wave's assembled output).

Evidence capture (before any cleanup): swarm-runner records, per COMPLETED worker,
`worker_head_sha`, `merge_base_sha = git merge-base expected_base_sha worker_head`, and
`delta_count = git rev-list --count expected_base_sha..worker_head`. In wave mode swarm-runner
DEFERS worktree/branch deletion until `verify_wave --wave K` passes (item 6), so verify runs
against LIVE branches.

### 3.4 P1 — ONE executable gate architecture: firebreak ACTIVE all run; no toggle
**Decision.** The firebreak is activated once (9w.9.6) and stays ACTIVE until Step 18w teardown.
The multi-wave loop performs **zero** `firebreak-activate.py deactivate` calls. The per-wave
**integrated dependency gate** — the thing that must PASS before Wave k+1 is spawned — is executed
inside the TRUSTED swarm-runner during assembly and consists of:
1. **Contract check** (grep for prescribed names/routes/imports) — blocking, as today.
2. **Integrated import-smoke** *(new, blocking in wave mode)* — a `pytest` invocation
   (`.venv/bin/pytest <reports-or-gitignored import-smoke test>`) that `importlib`-imports every
   module present in the assembled package and boots `create_app()` once. This is what proves the
   integrated tree actually resolves cross-wave imports — contract grep alone is NOT sufficient
   for Design X (Run 083 H6/H9: the integrated tree did not boot until an assembly-fix). On the
   first failure swarm-runner applies its one inline fix and re-runs; a second failure aborts the
   wave (`STATUS: FAIL -- integrated-import:`), which `verify_wave --wave K` also enforces.
3. Smoke (route curls) and the full test suite remain as today (non-blocking, recorded).

**Why this is firebreak-legal with the firebreak ACTIVE and needs no toggle:** every gate call is
either a pinned TRUSTED tool (`verify_wave.py`, `wave_artifact.py`, `check_spec_provenance.py`,
`firebreak-activate.py`) or a framework in `KNOWN_TEST_FRAMEWORKS` (`pytest`, `python -m pytest`,
`python -m unittest`) which the classifier allows for ANY identity (verified: classifier
`_matches_known_test_framework`). **`python -m compileall` and `python -m <pkg>.smoke` are NOT
used anywhere** — they were the only reason Run 083 needed a toggle (H5). The import-smoke via
`pytest` is a strict superset of `compileall` (it imports, not just compiles).

**Constraints preserved (explicit):**
- No unattended CODE push to `origin/<default>` — swarm-runner still merges only to the local
  feature branch.
- No name-based or `-m` carve-out — `pytest` is already framework-allowlisted (not new); the only
  new allowlist entries are the two approved tool PATHS.
- Only the two approved trusted tool-path additions.
- "Zero live workers before any firebreak deactivation" — satisfied vacuously: there is NO
  deactivation. Zero-live is still required before the NEXT spawn (§3.1) for correctness.

The H5 toggle protocol remains DOCUMENTED in SKILL 803-814 as a general capability, but the
multi-wave loop does NOT exercise it (noted in the SKILL). Any plan that would force a module-mode
orchestrator gate is rejected pre-spawn by the §4 validator's module-mode-gate rejection.

### 3.5 P2 — narrowed default-branch policy
CLAUDE.md + SKILL.md: **"During an unattended autopilot run, no phase pushes CODE to
`origin/<default>`. Build code accumulates on the local feature branch; the master merge is
deferred to a human post-review (a HANDOFF deferred item). The SOLE sanctioned
`origin/<default>` write is the pre-existing spec-provenance repair (SKILL 9w.9.5), a
spec-file-only commit made ONCE before Wave 0."** Governs only unattended autopilot run modes;
does not touch manual sessions or the provenance-repair path. Single-wave behavior is unchanged.
The multi-wave loop performs ZERO remote-ref writes → the remote-ref-update checklist applies to
NONE of it; the one pre-Wave-0 provenance push retains its existing pre-check + cleanup contract
(SKILL 9w.9.5 step 4).

## 4. Wave schema (P2) — total, deterministic, and matched to swarm-planner's real output

The swarm-planner emits repeated `### Agent: <role>` sections (NOT a table — verified in
`.claude/agents/swarm-planner.md`). rev4 extends THAT format rather than inventing a table.

**Pinned per-agent format (wave mode, `waves > 1`), emitted by swarm-planner:**
```markdown
### Agent: models
**Wave:** 1
**Required:** yes
**Files:**
- `swarmlimit/models/product.py`
**Responsibility:** [one sentence]
```
- `**Wave:**` — integer in `1..N`. Missing/non-integer/out-of-range ⇒ FAIL.
- `**Required:**` — exactly `yes` or `no` (any other value ⇒ FAIL). No default.

**Frontmatter:** `waves: N`. `waves` absent or `waves: 1` ⇒ current single-wave behavior
(no loop, no artifacts, validator is a no-op, swarm-planner omits Wave/Required). `waves` MUST be
a positive integer; `0`/non-integer ⇒ FAIL. Every agent belongs to exactly one wave; wave numbers
are contiguous (all of `1..N` present); an empty declared wave ⇒ FAIL.

**Export-Names → file → agent normalization (deterministic algorithm, run by
`verify_wave.py --validate-schema`):**
1. From the assignment sections, build `owner[file] = agent` (swarm-planner already guarantees
   each file maps to exactly one agent; a file in two sections ⇒ FAIL `duplicate`).
2. From the spec's **Cross-Boundary Wiring Table**, map each export symbol to its
   `producer_file` and each consumer to its `consumer_file`.
3. `producer_agent = owner[producer_file]`; `consumer_agent = owner[consumer_file]`.
   `producer_wave/consumer_wave = agent's **Wave:**`.
4. **Rejections (each a specific error naming the offending symbol/agent):**
   - `duplicate` — a file owned by two agents.
   - `missing` — an Export row's producer/consumer file is not owned by any agent.
   - `unresolved` — a Used-By / consumer value that cannot be mapped through the wiring table to a
     file→agent.
   - `ambiguous` — a symbol whose producer file resolves to more than one agent.
   - `aggregate` — a Used-By value naming a class ("all routes", `*`). Rejected UNLESS the spec's
     Coordinated Behaviors defines an explicit member list for that token; then it expands to
     exactly those agents. No implicit wildcard expansion.
   - `out-of-roster` — a producer/consumer agent name not present in the assignment roster.
5. **Forward-reference FAIL:** any edge with `consumer_wave < producer_wave`, OR
   `consumer_wave == producer_wave` for a cross-agent edge whose Export row carries
   `Build-Order-Sensitive: yes`. (Same-wave cross-agent edges are allowed only when spec-only,
   §3.2.) `Build-Order-Sensitive` is an optional Export Names column; absent ⇒ `no`.

**Runtime-dependent / module-mode-gate rejection (deterministic; replaces prose scanning):** the
multi-wave worker-brief template is the FIXED write+commit template (Step 10w rules 1-11). The
validator FAILs if any agent's assignment section contains a `**Commands:**` or `**Run:**` field,
or if the plan prescribes any orchestrator/worker gate using `python -m compileall`,
`python -m <pkg>.smoke`, or a package-wide typecheck (matched as literal directive tokens). This
is the executable form of the 0a constraint: such edges/gates are rejected pre-spawn with a
specific error, not a judgment call.

**Validator CLI:** `python3 tools/verify_wave.py --validate-schema --plan <plan_path>
--spec-path <spec_path> --root <MAIN>`; exit 0 = CLEARED, non-zero = FAIL with a specific message.
Run at Step 9w.7 (pre-spawn), under the active firebreak (pinned tool).

## 5. Per-wave transition sequence + write-ahead resume machine (encoded in SKILL)

**Durable phases (write-ahead — each written to `w<k>/transition-state.json` BEFORE the action it
guards):**

| # | phase | written before | records |
|---|-------|----------------|---------|
| 1 | `roster_prepared` | spawning any worker | wave roster placeholders, `expected_base_sha`, `worker_base_sha` |
| 2 | `spawn_in_progress` | the parallel spawn call | partial roster (updated with task/agent/branch ids AS they return) |
| 3 | `workers_terminal` | leaving the wait loop | per-worker terminal `status` + `terminal_evidence` |
| 4 | `assembly_started` | spawning swarm-runner | `assembly_branch` |
| 5 | `merge_completed` | (written AFTER swarm-runner returns PASS) | `assembled_output_sha` = new `original_branch` HEAD, Worker-Deltas table |
| 6 | `provenance_reverified` | emitting the artifact | provenance STATUS |
| 7 | `artifact_emitted` | running the verifier | `wave.md` path + content sha |
| 8 | `wave_verified` | spawning the next wave | verifier exit 0 |
| 9 | `readback_ok` | the next wave's spawn | firebreak `status` ACTIVE read-back |
| — | `abort` | (terminal) | `abort_reason` |

**Forward sequence, per wave k = 1..N:**
1. (k=1 only) run the §3.3 ancestry repair and pin `worker_base_sha`/`expected_base_sha`.
   For k>1, `expected_base_sha` = current `original_branch` HEAD.
2. `verify_wave.py --validate-schema` passed (Step 9w.7).
3. Firebreak read-back ACTIVE at `<MAIN>` (SKILL 1b, `status --root <MAIN>`); else abort.
4. Write phase `roster_prepared` (atomic).
5. Write phase `spawn_in_progress`; spawn ONLY wave k's roster (existing Step 10w spawn); capture
   each `task_id`/`agent_id`/`branch` and update transition-state (atomic) AS they return —
   BEFORE waiting. Write `w<k>/worker-roster.md`.
6. Wait for terminal results (Step 10w wait). Handle terminals per §3.1/§4; write phase
   `workers_terminal` with per-worker status.
7. **Prove zero live workers (§3.1)** before authoring wave k+1; unprovable ⇒ abort.
8. Ownership gate (Step 10.5w) against `original_branch`.
9. Write phase `assembly_started`; assemble wave k via swarm-runner
   (`reports_dir=w<k>/`, `assembly_branch=swarm-<run-id>-w<k>-assembly`). swarm-runner runs
   contract + the blocking integrated import-smoke (§3.4), merges `--no-ff` to `original_branch`,
   records the Worker-Deltas table, and DEFERS cleanup (wave mode).
10. Disk-verify swarm-runner's summary (existing `verify_delegated_status.py` gate); on PASS write
    phase `merge_completed` + `assembled_output_sha` = new `original_branch` HEAD (atomic).
11. Re-run provenance (invariant base; fail-closed insurance): `check_spec_provenance.py --repo
    <MAIN> --default-branch <default> --original-branch <feature> --spec-path <spec_path>`; write
    phase `provenance_reverified`.
12. `wave_artifact.py emit` writes `w<k>/wave.md` atomically (§6); write phase `artifact_emitted`.
13. `verify_wave.py --wave <k>` (full CLI §7) — the blocking gate. On exit 0, write phase
    `wave_verified`.
14. Clean up wave k's deferred worktrees/branches (orchestrator: `git worktree remove` +
    `git branch -D` per branch/worktree — local git ops, firebreak-legal for the orchestrator).
15. Re-assert firebreak read-back ACTIVE; write phase `readback_ok`; spawn wave k+1.
After the final wave, proceed to **Step 17w (Shared Tail delegation)**; the tail runs
`verify_wave.py --reconcile` fail-closed. There is NO firebreak toggle anywhere in this sequence.

**Resume-after-context-death (idempotent across every crash boundary).** On resume
(tail-resume/CHECKPOINT), FIRST re-assert the firebreak, THEN route per phase:
- **Step R0 (ALWAYS FIRST): restore/read back firebreak ACTIVE.** Run
  `firebreak-activate.py status --root <MAIN>`. Exit 3 ⇒ abort (wrong root). `INACTIVE` ⇒
  `activate <run-id> --root <MAIN>` + re-read; still not ACTIVE ⇒ abort. Only proceed once ACTIVE.
- **Step R1: enumerate and stop ALL run-scoped tasks — including tasks spawned before their IDs
  were persisted.** Query `TaskList` for every task whose name matches `swarm-<run-id>-*` (NOT only
  the ids recorded in transition-state — a crash during `spawn_in_progress` may have spawned
  workers whose ids were never written). `TaskStop` + verify each; prove zero live before anything
  else. Unprovable ⇒ abort.
- Then, for each wave read `w<k>/transition-state.json`:
  - **absent** ⇒ wave not started ⇒ start at forward-step 2.
  - **`roster_prepared` / `spawn_in_progress` / `workers_terminal`** ⇒ (after R1 proved zero live)
    if `original_branch` HEAD == `expected_base_sha` (no assembly ran) resume at forward-step 8;
    else go to the ambiguous-assembly check below.
  - **`assembly_started`** (assembly may be partway; the dangerous boundary) ⇒ do NOT re-spawn.
    **Ambiguous-assembly recovery:** if `swarm-<run-id>-w<k>-assembly` exists OR `original_branch`
    HEAD != `expected_base_sha` while `merge_completed` was never written, recompute the expected
    assembled output from the recorded Worker-Deltas (count = Σδ+1). If live HEAD matches that
    expected shape, write `merge_completed` + `assembled_output_sha` = HEAD and resume at
    forward-step 11 (provenance → emit → verify). If it does NOT match, abort (manual) — never
    re-assemble onto an advanced branch.
  - **`merge_completed`** (assembly done, artifact maybe not emitted) ⇒ do NOT re-spawn/re-assemble;
    `original_branch` HEAD already == `assembled_output_sha`; resume at forward-step 11.
  - **`artifact_emitted`** ⇒ **compare-and-reuse:** if `w<k>/wave.md` exists and its
    `assembled_output_sha` == live HEAD and a re-emit would produce byte-identical content →
    REUSE it (no overwrite), resume at forward-step 13. If it CONFLICTS (different
    `assembled_output_sha` or roster) → abort; never overwrite a conflicting artifact.
  - **`wave_verified` / `readback_ok`** ⇒ wave complete; skip to wave k+1.
  - **`abort`** ⇒ terminal; the run stays aborted (no silent resume).
Duplicate prevention: spawn guarded by transition-state presence + name-prefix task scan;
cherry-pick/merge guarded by `merge_completed` + HEAD==`assembled_output_sha`; verifier is
deterministic (safe to re-run); artifact overwrite prevented by atomic emit keyed on
`assembled_output_sha` + the compare-and-reuse/conflict rule above.

## 6. Per-wave artifact + transition-state schema (atomic)
`w<k>/wave.md` (STATUS line 1 ∈ {PASS-EMITTED, ABORT}, then a fenced JSON block), written by
`wave_artifact.py emit` via temp + `os.rename` (same-dir, atomic on POSIX). Fields: `run_id`,
`wave_count`, `wave_index`, `run_start_ts`, `emit_ts`, `expected_base_sha`, `worker_base_sha`
(=`origin/<default>` tip, pinned §3.3), `roster` (list of `{task_id, agent_id, role, branch,
required, status, terminal_evidence}` where `terminal_evidence` ∈ {completion-notified,
TaskStop-verified}), `worker_deltas` (list of `{role, worker_head_sha, merge_base_sha,
delta_count}` — captured before cleanup, §3.3), `ownership_gate` (PASS/FAIL + path),
`assembled_output_sha`, `gate_results` (`contract` verdict+path [blocking];
`integrated_import` verdict+path [blocking]; `smoke`,`test` verdict+path [non-blocking]),
`firebreak_readback` (ACTIVE + ts), `provenance` (STATUS + path), `prev_wave_output_sha`
(= wave `k-1` `assembled_output_sha`; null for k=1), `prev_wave_artifact_sha` (= sha256 of the
bytes of `w<k-1>/wave.md`; null for k=1; the verifier recomputes and compares — tamper-evidence),
`abort_reason` (null unless STATUS ABORT). **Within-wave invariant:** nothing advances
`original_branch` between forward-steps 9 and 12 ⇒ `assembled_output_sha` == live HEAD at emit
time (verifier asserts). **Continuity:** `wave[k].assembled_output_sha == wave[k+1].expected_base_sha`
and `wave[k+1].prev_wave_output_sha == wave[k].assembled_output_sha`. `transition-state.json`
mirrors `run_id/wave_index/phase/roster/expected_base_sha/worker_base_sha/assembled_output_sha`
and is the resume source of truth.

## 7. `verify_wave.py` — authoritative CLIs + reject-sets

**Truth derivation (all modes): Wave, Required, and the expected roster are DERIVED from `--plan`
(the swarm-planner assignment sections, §4) + `--spec-path`, NOT from any caller-supplied roster.**
There is no `--expected-roster`/`--required-map` argument. The worker base is read live
(`git rev-parse origin/<default>`); HEADs are read live from `--root`.

**`--validate-schema` (pre-spawn):**
`python3 tools/verify_wave.py --validate-schema --plan <plan_path> --spec-path <spec_path>
--root <MAIN>`. Enforces §4 (schema totality, Export-Names normalization, forward-ref,
runtime-dependent/module-mode-gate rejection). Exit 0 = CLEARED.

**`--wave K` (immediate, blocks next spawn):**
`python3 tools/verify_wave.py --wave <K> --plan <plan_path> --spec-path <spec_path>
--reports-dir <w_k_dir> --root <MAIN> --run-id <id> --run-start-ts <epoch_int>
--original-branch <feature> --default-branch <default>`.
Serialization is pinned: `run-id` 3-digit string; `run-start-ts` integer epoch seconds; branches
are git ref strings; `reports-dir` a repo-relative path ending `/w<K>/`.
**Rejects (FAIL) if ANY:**
- artifact missing / a wave-count mismatch / duplicate / non-contiguous vs `--plan` `waves`.
- `run_id` ≠ `--run-id` OR `run_start_ts` ≠ `--run-start-ts` (EXACT equality — stale/wrong-run).
- roster (derived from `--plan` for wave K) ≠ the artifact roster (missing/extra worker).
- any worker non-terminal; any REQUIRED worker FAILED or TIMED_OUT(-STOPPED) per the derived
  Required map.
- **evidence re-read mismatch (forged-verdict guard):** the artifact records a gate verdict whose
  referenced file's line-1 STATUS does not match. verify_wave OPENS and re-reads:
  `ownership-gate.md` (must be PASS), `contract-check.md` (must be PASS), the integrated
  import-smoke report (must be PASS), `smoke-test.md`/`test-results.md` (must be PRESENT), the
  per-wave provenance report (must be PROVENANCE_OK). Any file whose real STATUS ≠ the artifact's
  recorded verdict ⇒ FAIL.
- `ownership_gate` ≠ PASS; **contract verdict ≠ PASS** (blocking); **integrated_import verdict ≠
  PASS** (blocking); smoke/test verdicts absent (they are non-blocking but MUST be present).
- **firebreak not ACTIVE at verify time:** verify_wave independently runs
  `firebreak-activate.py status --root <MAIN>` and requires ACTIVE (not just the artifact's
  recorded `firebreak_readback`).
- `expected_base_sha` ≠ prior wave's `assembled_output_sha` (continuity break).
- `origin/<default>` tip is NOT an ancestor of `expected_base_sha` (the §3.3 ancestry proof was
  violated → base/default commits would enter the worker cherry-pick range and be replayed).
- for each COMPLETED non-empty worker: `git merge-base <worker_head_sha> <expected_base_sha>` ≠
  `worker_base_sha` (a worker forked from a stale/older default commit). If a recorded
  `worker_head_sha` is unresolvable AND its `delta_count > 0` ⇒ FAIL (evidence destroyed before
  verification — must not happen because wave-mode cleanup is deferred).
- commit count `git rev-list --count expected_base_sha..assembled_output_sha` ≠
  `Σ(delta_count over COMPLETED non-empty workers) + 1` (the single `--no-ff` merge commit).
- **HEAD check (mode-sensitive):** for `--wave K`, `assembled_output_sha` ≠ live
  `original_branch` HEAD (immediate verification requires the current wave's output == HEAD).
- `prev_wave_artifact_sha` ≠ recomputed sha256 of `w<k-1>/wave.md`.

**`--reconcile` (tail, all waves):**
`python3 tools/verify_wave.py --reconcile --plan <plan_path> --spec-path <spec_path>
--reports-dir <run_reports_dir> --root <MAIN> --run-id <id> --run-start-ts <epoch_int>
--original-branch <feature> --default-branch <default>`.
Re-runs every `--wave K` check across waves 1..N EXCEPT the HEAD check, which is mode-sensitive:
reconciliation requires waves `1..N-1` `assembled_output_sha` to be ANCESTORS of the live
`original_branch` HEAD (`git merge-base --is-ancestor`) and ONLY wave N's `assembled_output_sha`
to EQUAL HEAD. Additionally FAILs if the verified-artifact count ≠ declared `waves`, or the SHA
chain (`prev_wave_output_sha` → `expected_base_sha`) breaks anywhere.

**Evidence preservation:** because wave-mode swarm-runner defers cleanup until after
`verify_wave --wave K` (§3.3, item 3 scope), all worker branches/worktrees and every `w<k>/*.md`
report are live when the verifier runs. Cleanup (forward-step 14) happens only AFTER verify PASS.

## 8. Acceptance Tests (executable EARS) + Verification Commands

Unit tests are plain-stdlib runners (repo convention — cf. `tools/test_check_compounded_darkness.py`;
NO pytest dependency) exposing a `--case <name>` selector plus a no-arg full-suite run. They
materialize artifacts + a temp git repo as fixtures. Orchestration behaviors that unit tests
cannot cover get a live spike.

### Happy path
- WHEN a plan declares `waves: 3` with a valid `Wave`/`Required` assignment THE SYSTEM SHALL pass
  `--validate-schema` and run 3 waves with cross-wave SHA continuity and the firebreak ACTIVE
  throughout.
  - Verify: `python3 tools/test_verify_wave.py --case test_three_wave_continuity`.
- WHEN `waves` is absent or `1` THE SYSTEM SHALL behave as the current single-wave path (no
  artifacts, no `verify_wave` invocation, swarm-runner cleanup inline as today).
  - Verify: `python3 tools/test_verify_wave.py --case test_single_wave_noop` + live spike
    `spike_single_wave_regression` (a 1-wave run emits no `w*/` artifacts and calls no verifier).

### Error cases (each a named test/fixture or live spike)
- WHEN the wave count is invalid or the grouping malformed THE SYSTEM SHALL FAIL `--validate-schema`.
  → `--case test_schema_invalid_count`, `test_schema_empty_wave`, `test_schema_bad_required`,
  `test_schema_forward_ref`, `test_schema_runtime_dependent_edge_rejected`,
  `test_schema_module_mode_gate_rejected`.
- WHEN an Export-Names mapping is unresolved/ambiguous/aggregate-without-members/out-of-roster THE
  SYSTEM SHALL FAIL `--validate-schema`. → `test_schema_unresolved_mapping`,
  `test_schema_ambiguous_mapping`, `test_schema_aggregate_no_members`, `test_schema_out_of_roster`.
- WHEN the swarm-planner emits Wave/Required sections THE SYSTEM SHALL parse them into a roster.
  → `test_planner_wave_required_parse` (fixture = a swarm-planner-format assignment block).
- WHEN a wave artifact is missing/duplicate/stale/wrong-run THE SYSTEM SHALL FAIL `--wave`. →
  `test_artifact_missing`, `_duplicate`, `_stale_ts`, `_wrong_runid`.
- WHEN an artifact records a PASS verdict but the referenced evidence file's STATUS is not PASS
  THE SYSTEM SHALL FAIL `--wave` (forged-verdict guard). → `test_forged_contract_verdict`,
  `test_forged_ownership_verdict`, `test_forged_import_verdict`.
- WHEN a REQUIRED worker is FAILED/TIMED_OUT THE SYSTEM SHALL FAIL `--wave`; an OPTIONAL one SHALL
  PASS. → `test_required_worker_failed`, `test_optional_worker_skipped`.
- WHEN a worker times out and cannot be proven stopped THE SYSTEM SHALL abort (no next spawn). →
  live spike `spike_timeout_unstoppable_aborts`.
- WHEN a resume runs THE SYSTEM SHALL re-assert the firebreak ACTIVE FIRST, then stop all
  run-scoped tasks (incl. pre-persist spawns) before proceeding. → live spike
  `spike_resume_reasserts_firebreak_then_stops_tasks` (covers "partial spawn" — tasks spawned
  before ids were persisted, found by name-prefix scan).
- WHEN ownership fails THE SYSTEM SHALL FAIL `--wave`. → `test_ownership_fail`.
- WHEN the integrated import-smoke fails on the assembled tree THE SYSTEM SHALL FAIL the wave
  (blocking). → `test_integrated_import_fail` + live spike `spike_integrated_import_blocks_next_wave`.
- WHEN a worker forked from an older `origin/<default>` commit THE SYSTEM SHALL FAIL `--wave`
  (stale fork point). → `test_worker_forked_from_stale_base_rejected` (fixture: `origin/<default>`
  is an ancestor of the feature branch but the worker's merge-base ≠ pinned `worker_base_sha`).
- WHEN a base/default commit would be replayed as a worker delta THE SYSTEM SHALL FAIL `--wave`
  (ancestry proof). → `test_base_commit_replay_rejected`.
- WHEN a wave has multi-commit workers plus the `--no-ff` merge THE SYSTEM SHALL accept
  count == Σδ+1 and reject any other count. → `test_multi_commit_workers_plus_noff`.
- WHEN a crash occurs after merge but before state was written THE SYSTEM SHALL recover without
  re-assembly (ambiguous-assembly recovery). → live spike `spike_merge_before_state_write`.
- WHEN a resume finds an `artifact_emitted` wave with an IDENTICAL artifact THE SYSTEM SHALL reuse
  it; with a CONFLICTING artifact THE SYSTEM SHALL abort (no overwrite). →
  `test_reuse_identical_artifact`, `test_conflicting_artifact_aborts`.
- WHEN provenance drifts after a wave THE SYSTEM SHALL FAIL `--wave`. → `test_provenance_drift`.
- WHEN the tail runs THE SYSTEM SHALL FAIL `--reconcile` on artifact-count mismatch, a broken SHA
  chain, or an earlier wave whose output is not an ancestor of HEAD; and require ONLY wave N ==
  HEAD. → `test_reconcile_count_mismatch`, `test_reconcile_chain_break`,
  `test_reconcile_earlier_wave_ancestor`, `test_reconcile_final_wave_is_head`.
- WHEN the real swarm-runner runs per wave under the active firebreak THE SYSTEM SHALL keep two
  sequential invocations isolated and leak no run-level state. → §0.0c `spike_per_wave_swarm_runner`.

### Regression / invariants
- WHEN the classifier suite runs THE SYSTEM SHALL report **284/284** — the **282** existing cases
  stay green (verified: `282/282 passed` at rev4 authoring) plus 2 new file-path allow-cases
  (`tools/wave_artifact.py`, `tools/verify_wave.py`), each TRUSTED-only and STILL DENIED for
  workers, with **no new `-m` allow-case**.
  - Verify: `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → `284/284 passed`; plus
    `test_wave_tools_denied_for_worker` and `test_no_m_allow_case`.

### Verification Commands (summary)
- `python3 tools/test_verify_wave.py` — all wave-verifier + schema + planner-parse cases green.
- `python3 tools/test_wave_artifact.py` — schema + atomic-emit + transition-state cases green.
- `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → `284/284 passed`, no `-m` allow-case.
- Live spikes `spike_*` above executed in the work-phase branch (orchestration-level), recorded
  under `docs/reports/p1p2-spikes/`.
- `python3 tools/verify_wave.py --reconcile ...` on a real multi-wave run → `STATUS: PASS`.

## 9. Most likely way this plan is wrong
1. **The spec-only premise (§3.2 / spike 0a).** If 0a shows a dependent worker genuinely needs
   prior-wave files at author time, OR per-wave assembly cannot integrate a dependent wave, Design
   X's core mechanic is broken — a STOP-for-revision, not a quiet scope cut.
2. **swarm-runner wave-mode changes (§1 items 3).** The blocking import-smoke, the Worker-Deltas
   recording, and deferred cleanup are three real behavior changes; 0c must confirm the reuse is
   clean and the new gate is faithful before the SKILL loop is written.
3. **The import-smoke as a faithful `compileall`/`<pkg>.smoke` replacement.** If a plan's real
   integration risk lives somewhere `pytest`-import + `create_app()` boot does not exercise, the
   gate could pass a tree that a module-mode gate would have failed. Mitigated by keeping the full
   test suite (non-blocking) + smoke curls, but called out as the load-bearing substitution.

## Feed-Forward
- **Hardest decision:** Collapsing the gate architecture to "firebreak ACTIVE all run, no toggle"
  by relocating the between-wave integration check INTO swarm-runner as a `pytest` import-smoke.
  This removes an entire risk class (toggle window / zero-live-before-deactivate) at the cost of
  three real swarm-runner changes and a substitution (import-smoke for `python -m compileall`).
- **Rejected alternatives:** (a) keep the deactivate/reactivate toggle around a `python -m
  compileall` orchestrator gate — reintroduces the zero-live-before-deactivate hazard and needs
  the firebreak off across a barrier; REJECTED. (b) per-wave FF `origin/<default>` code push
  (Run-083 mechanic) — violates the no-master-push policy. (c) harness re-rooting worktrees on an
  integration branch — unverified capability. (d) caller-supplied roster into verify_wave — makes
  the verifier non-authoritative; REJECTED in favor of plan-derived roster.
- **Least confident:** §3.2 premise (spike 0a), swarm-runner per-wave cleanliness + faithful
  import-smoke (spike 0c), and TaskStop observability (spike 0b) — all BLOCKING §0 spikes that
  must pass before any SKILL/tool code is written.
