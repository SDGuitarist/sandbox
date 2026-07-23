---
title: "P1/P2 — Encode the unattended multi-wave swarm barrier loop"
date: 2026-07-22
status: draft
phase: plan
revision: 3  # resolves Codex re-review NO-GO (liveness/resume, spike falsifiability, assembly base, verifier authority, idempotence, total schema, executable EARS)
branch: feat/p1p2-unattended-swarm-wave-barrier
relates_to:
  - unattended-big-run-trust-gate (MEMORY)
  - swarmlimit-run-083 (harvest H5/H7; solution doc)
  - fc68-firebreak-cwd-root-anchor (merged 4da3eff)
feed_forward:
  risk: "Design X (no per-wave CODE push; workers write+commit only, integration + all self-verification deferred to per-wave assembly) is the ONLY design compatible with the firm no-master-push policy. Its load-bearing premise — that a dependent worker never needs a prior wave's actual files present at authoring — is contradicted on its face by Run 083's documented mechanic (it pushed each wave's code to origin/master so later workers 'saw' it). Spike 0a must FALSIFY this; if it fails, dependent-runtime cross-wave edges are declared INFEASIBLE unattended and the pre-spawn validator rejects them executably."
  verify_first: true
---

# P1/P2 — Encode the unattended multi-wave swarm barrier loop

## Context

The trust gate (`unattended-big-run-trust-gate`) blocks launching a ≥20-agent swarm fully
hands-off. Run 083 succeeded only because a human hand-ran the wave barriers, approved every
push, and cat-verified the firebreak after a live fail-open. This plan targets criteria (2)
firebreak needs no *manual* toggling and (3) the wave-barrier / push mechanic runs from the
SKILL, not live judgment. P1 (FC68/083-W6) is already merged (`4da3eff`); the H5 toggle is
documented (SKILL 803-814) and the per-wave firebreak read-back already exists (SKILL 1b,
763-766), but no deterministic multi-wave loop, verifier, or resume machine exists.

## Accepted decisions (from Codex re-review — treated as fixed constraints)
- The two exact file-path additions to `TRUSTED_PIPELINE_SCRIPT_PATHS`
  (`tools/wave_artifact.py`, `tools/verify_wave.py`) are approved.
- `wave_artifact.py` / `verify_wave.py` do NOT move into the open toggle window.
- No name-based or module-mode `-m` carve-out.
- No unattended CODE push to `origin/<default>`.
- TaskStop failure is fail-closed: always abort on timeout when termination cannot be proven.

## Codex re-review resolution map (revision 3)

| Codex re-review blocker | Resolution |
|---|---|
| P0 resume/liveness hole | §3.1 + §5 durable per-wave transition-state (phases, task ids) written BEFORE waiting; resume stops every recorded task + proves zero live before any respawn/assembly/deactivation; unprovable ⇒ abort firebreak-ACTIVE |
| Spike 0a must be falsifiable; reconcile Run 083 | §0 + §3.2 — 0a runs the REAL worker-local import/compileall/typecheck with prior-wave files absent; machine-checkable spec-only vs runtime-dependent edge classification; 083 reconciliation; executable fallback (validator rejects runtime-dependent edges) |
| Assembly-base assumption wrong | §3.3 — no assumption; blocking ancestry proof (`merge-base --is-ancestor origin/<default> original_branch`) via the existing Run-070 pre-flight merge; pinned repair when it fails; verifier proves no base commit is replayed as a worker delta |
| verify_wave not authoritative | §7 — full pinned CLI (every truth source is an explicit arg); `prev_wave_artifact_sha` defined; blocking vs non-blocking gate verdicts; live-history ancestry checks; `--spec-path` on every provenance call |
| Idempotent recovery across every crash boundary | §5 resume machine — durable before/after state; the after-assembly-before-emit boundary handled; no duplicate spawn/cherry-pick/merge/verify/overwrite |
| Total, deterministic schema | §4 — exact `Wave`/`Required` columns + values; forward-ref detection algorithm from the Export Names table; wave-scoped report DIRECTORIES (no prefix alternative); validator location + CLI pinned |
| §8 executable EARS | §8 — every case WHEN/SHALL with a named test/fixture or live spike; orchestration-level spikes; corrected 282→284 classifier baseline |

## 0. Verify-first spike (BLOCKING — gate 0, before ANY SKILL/tool code)

Both spikes below run in the work-phase branch and their outcome is recorded before the first
SKILL/tool edit. A pinned failure outcome is NOT a work-phase judgment call.

- **0a — falsify the spec-only premise (§3.2).** Build a minimal 2-wave fixture where a Wave-2
  worker's assigned file imports a Wave-1 spec'd export (per the Export Names table). Provision
  it EXACTLY as the harness will: Wave-2 worker rooted on `origin/<default>` (carrying only the
  one-time spec commit), **Wave-1's code files ABSENT from its worktree.** Then have the Wave-2
  worker perform the **real dependent-worker self-verification a quality brief would run**:
  `python -m compileall <its files>`, an import smoke of its module, and a typecheck. Record
  which of {author+commit, compileall, import, typecheck} SUCCEED with Wave-1 absent.
  - **PASS criterion:** author+commit succeeds (writing imports from the spec). If compileall/
    import/typecheck of a cross-wave symbol FAIL with Wave-1 absent, that is EXPECTED and
    CONFIRMS the design constraint: workers must be write+commit-only (self-verification deferred
    to assembly). Proceed with Design X + the §4 enforcement that worker briefs contain no
    cross-module execution step.
  - **FAIL criterion:** author+commit itself cannot be produced correctly without the prior
    files ⇒ dependent unattended waves are INFEASIBLE; scope drops to independent-waves-only and
    the §4 validator rejects every runtime-dependent cross-wave edge (executable fallback).
- **0b — TaskStop observability (§3.1).** Spawn one long-running background worker; `TaskStop`
  it; confirm `TaskList`/`TaskGet` reports it terminated within a bounded poll. PASS ⇒ the
  prove-zero-live gate is viable. FAIL ⇒ the gate is always-abort-on-timeout (already the
  accepted fail-closed rule) — documented, no design change.

### Run 083 reconciliation (why the premise is testable, not already disproven)
Run 083's solution doc says it pushed each wave's CODE to origin/master so Wave N+1 "saw" Wave
N, and that model workers "need Wave-0's auth/database exports." Reconciliation: a worker needs
the export **names** (from the spec's Export Names table) to WRITE `from swarmlimit.database
import query`; it needs the export **files present** only if it EXECUTES that import at author
time. The SKILL worker contract (Step 10w rules 1-10) is write-and-commit-only — no execution
step — so on its face the 083 per-wave code push was **sufficient but not necessarily
necessary**; the necessary channel (the converged SPEC at every worktree base) is served by the
ONE-TIME pre-Wave-0 provenance repair (SKILL 9w.9.5, which pushes a spec-only commit to
origin/<default>; §3.3). Spike 0a settles empirically whether code-file presence was necessary.
This plan does NOT assert the premise as established — it gates the whole design on 0a.

## 1. What exactly is changing?

Deliverables (work phase, AFTER §0 passes). All additive; none touch firebreak *logic*.

1. **SKILL.md "Multi-Wave Barrier Loop (Path B)"** wrapping Step 10w, encoding the §5 sequence
   + the §5 resume machine deterministically.
2. **Wave schema** (§4): `waves: N` frontmatter + required `Wave` and `Required` columns; a
   pre-spawn validator (`verify_wave.py --validate-schema`, §4/§7) that FAILs on every malformed
   case AND on any runtime-dependent cross-wave edge (executable 0a fallback).
3. **`tools/wave_artifact.py`** — `emit` writes the §6 artifact atomically (temp + `os.rename`)
   from explicit args; `state` writes/updates the durable transition-state file atomically.
   Ships `tools/test_wave_artifact.py`.
4. **`tools/verify_wave.py`** — three pinned modes: `--validate-schema` (pre-spawn), `--wave K`
   (immediate, blocks next spawn), `--reconcile` (tail). Full CLI + reject-set in §7. Ships
   `tools/test_verify_wave.py`.
5. **firebreak-classify.py — two file-path allowlist additions** (`tools/wave_artifact.py`,
   `tools/verify_wave.py`) to `TRUSTED_PIPELINE_SCRIPT_PATHS`. Data-only, TRUSTED-only, still
   deferred for workers; no logic change, no `-m` carve-out (approved).
6. **CLAUDE.md + SKILL.md** — narrowed default-branch policy (§3.5).
7. **Tail + resume integration**: `--reconcile` runs in the Shared Tail (fail-closed);
   `CHECKPOINT.md`/tail-resume gains the §5 wave-resume state.
8. **Per-run artifacts** under `docs/reports/<run-id>/w<k>/`: `transition-state.json`,
   `worker-roster.md`, swarm-runner reports, and `wave.md` (the verifier input).

## 2. What must NOT change
- **Firebreak carve-out logic.** No `-m`/name-based module carve-out; `-m` still yields no
  path-pinnable script; `TRUSTED_PIPELINE_SCRIPT_PATHS` stays file paths only (item 1.5 adds two
  paths, no logic). **All 282 existing classifier cases stay green; no new `-m` allow-case.**
- **Single-wave behavior.** `waves` absent or `1` ⇒ EXACTLY today's path: one Step 10w spawn,
  one 10.5w ownership gate, one swarm-runner assembly, no toggle window, no wave artifacts, no
  `verify_wave` invocation.
- **Worker governance invariant.** Firebreak never off across a worker spawn; the toggle window
  is a barrier with *proven* zero live workers (§3.1).
- **Worker base ref.** Workers keep rooting on `origin/<default>` (baseRef=fresh); no worktree
  re-rooting (unverified harness capability).
- **swarm-runner's merge target.** Assembly merges to `original_branch` (feature branch) locally,
  never origin.
- **The pre-spawn provenance gate (9w.9.5).** Unchanged; `check_spec_provenance.py` takes
  `--repo`/`--default-branch`/`--original-branch`/`--spec-path` — no invented `--root`.

## 3. Design resolutions

### 3.1 P0 — prove zero live workers before any deactivation; durable across resume
Per wave, a durable **transition-state file** `w<k>/transition-state.json` is written (atomic)
BEFORE waiting for completions and updated at each phase: `spawned` → `assembled` → `verified`,
or `abort`. It records, per worker: `task_id`, `agent_id`, `role`, `branch`, `required`,
`status`. The toggle window (deactivate → `-m` gate → reactivate) may be entered ONLY after
every worker of the wave is **authoritatively terminal**:
- **COMPLETED** (completion notification) = terminal.
- **FAILED** (error result) = terminal; a REQUIRED FAILED worker ⇒ verifier FAIL.
- **TIMED_OUT** ⇒ `TaskStop` it and confirm terminated via `TaskList`/`TaskGet`
  (`TIMED_OUT_STOPPED`); a REQUIRED such worker ⇒ verifier FAIL.
- **OPTIONAL** worker terminal in any state may be skipped (recorded, non-fatal).
If ANY worker cannot be proven stopped, **ABORT with the firebreak ACTIVE** (no deactivation, no
next spawn); write the transition-state `abort` + a `wave.md` STATUS `ABORT` (§6). On resume
(§5), the transition-state's recorded `task_id`s are queried/stopped and zero-live is re-proven
BEFORE any respawn/assembly/deactivation.

### 3.2 P1 — the spec-only premise (Design X), stated as a gated hypothesis
Design X: workers WRITE+COMMIT only (SKILL Step 10w rules 1-10, no execution step); cross-wave
integration AND all cross-module self-verification are deferred to per-wave assembly (swarm-
runner runs contract/compileall/smoke on the assembled tree). Under Design X a later-wave worker
authors against the spec's Export Names table and never needs a prior wave's files present. A
cross-wave edge is:
- **spec-only** — the consumer only *references* a producer export name (write+commit). Supported.
- **runtime-dependent** — the consumer's assignment/brief requires *executing* code that imports
  a prior-wave module at author time (a local test, package-wide compileall, or typecheck across
  modules). NOT supported unattended.
**Machine-checkable classification (§4 validator):** the multi-wave worker-brief template is the
fixed write+commit template; the validator FAILs if any wave's brief/assignment adds a
cross-module execution directive (a test command, `compileall` beyond the worker's own files, or
a package typecheck). Default runs have none ⇒ all edges spec-only. This is the executable form
of the 0a fallback: runtime-dependent edges are rejected pre-spawn with a specific error, not a
judgment call. The SPEC (not code) must be at every worktree base — served by the ONE-TIME
pre-Wave-0 provenance repair (§3.3); static across waves, so no per-wave push.

### 3.3 P1 — assembly base: ancestry proof + no replay (no origin/<default> assumption)
The worker base is `origin/<default>` tip AFTER the one-time pre-Wave-0 spec repair (SKILL
9w.9.5 may push a spec-only commit to `origin/<default>`); it is then INVARIANT across waves (no
per-wave push). Do NOT assume `merge-base(original_branch, worker) == origin/<default>` tip.
Instead, before EACH wave's assembly, run the **blocking ancestry proof**: assert
`git merge-base --is-ancestor <origin/<default>-tip> <original_branch>`. This makes the worker's
true fork point `origin/<default>` tip, so the cherry-pick range `merge-base..worker` is
worker-only (prior-wave and base/spec commits are already on `original_branch` and never in
range → never replayed). If the assertion FAILS (e.g. the spec-repair commit is on
`origin/<default>` but not yet on the feature branch), apply the **pinned repair = the existing
Run-070 pre-flight merge**: `git merge origin/<default>` into `original_branch`, then re-assert;
if it still fails, ABORT (do not assemble). `verify_wave` proves no replay by re-asserting the
ancestry proof (`origin/<default>` tip is an ancestor of `expected_base_sha`, so the worker
cherry-pick range excludes all base/default commits) AND that the commit count of
`expected_base_sha..assembled_output_sha` equals the number of COMPLETED workers' non-empty
deltas (no base/default commit re-authored as an extra worker commit). Per-wave
assembly reuses swarm-runner unchanged (only `reports_dir`=`w<k>/`, `assembly_branch`=
`swarm-<run-id>-w<k>-assembly`, and this wave's branches differ); its cleanup removes only this
wave's worktrees/branches.

### 3.4 P1 — verification with teeth (authoritative, not prose/count)
Three layers: (1) the structured per-wave artifact (§6), atomic; (2) the immediate authoritative
verifier `verify_wave.py --wave K` (full pinned CLI §7) that must exit 0 BEFORE the next spawn;
(3) the tail `--reconcile`. Freshness (`run_id`+`run_start_ts` on every artifact), SHA chaining,
live-history ancestry, and immediate placement give the teeth; the verifier derives every truth
from explicit args + live git, never from the artifact alone (§7).

### 3.5 P2 — narrowed default-branch policy
CLAUDE.md + SKILL.md: **"During an unattended autopilot run, no phase pushes CODE to
`origin/<default>`. Build code accumulates on the local feature branch; the master merge is
deferred to a human post-review (a HANDOFF deferred item). The SOLE sanctioned
`origin/<default>` write is the pre-existing spec-provenance repair (SKILL 9w.9.5), a
spec-file-only commit made ONCE before Wave 0."** Governs only the unattended autopilot run
modes; does not touch manual sessions or the provenance-repair path. Single-wave behavior is
unchanged (swarm-runner already merges only to the feature branch). The multi-wave loop performs
ZERO remote-ref writes → the remote-ref-update checklist (old/new SHA, FF-only, read-back, race,
human-auth, recovery) applies to NONE of it; the one pre-Wave-0 provenance push retains its
existing pre-check + cleanup contract (SKILL 9w.9.5 step 4).

## 4. Wave schema (P2) — total + deterministic; enforced by `verify_wave.py --validate-schema`
- `waves` absent or `waves: 1` ⇒ current single-wave behavior (no loop, no artifacts, validator
  is a no-op).
- `waves` MUST be a positive integer; `0`/non-integer ⇒ FAIL.
- For `waves > 1`, `## Swarm Agent Assignment` MUST carry exactly two added columns:
  - **`Wave`** — integer in `1..N`.
  - **`Required`** — exactly `yes` or `no` (any other value ⇒ FAIL). No default.
- Every agent belongs to exactly one wave. Wave numbers contiguous (all of `1..N` present).
  **Empty waves forbidden** (declared wave with zero agents ⇒ FAIL).
- **Forward-reference detection (machine algorithm):** from the spec's Export Names table, build
  `producer_wave[name]` = the Wave of the row whose `Defined By` agent owns `name`, and for each
  `Used By` agent build the consumer's Wave. FAIL if any edge has `consumer_wave < producer_wave`
  (a consumer needing an export produced in a later wave) or `consumer_wave == producer_wave` for
  a cross-agent edge that the spec marks build-order-sensitive. (Same-wave cross-agent edges are
  allowed only when spec-only; §3.2.)
- **Runtime-dependent edge rejection (0a fallback):** FAIL if any wave's worker brief/assignment
  includes a cross-module execution directive (test command, package-wide `compileall`, or
  typecheck spanning other agents' files). Specific error naming the agent + directive.
- Validator location/CLI: `python3 tools/verify_wave.py --validate-schema --plan <plan_path>
  --spec-path <spec_path> --root <MAIN>`; exit 0 = CLEARED, non-zero = FAIL with a specific
  message. Run at Step 9w.7 time (pre-spawn), under the active firebreak (pinned tool).

## 5. Per-wave transition sequence (P2) — encoded in SKILL, per wave k = 1..N
1. `verify_wave.py --validate-schema` passed (Step 9w.7); record `expected_base_sha` = current
   `original_branch` HEAD.
2. Firebreak read-back ACTIVE at `<MAIN>` (SKILL 1b, `status --root <MAIN>`); else abort.
3. Write `w<k>/transition-state.json` phase `spawned` with the wave roster placeholders (atomic).
4. Spawn ONLY wave k's roster (existing Step 10w spawn); capture each `task_id`/`agent_id`/
   `branch`; update `transition-state.json` (atomic) with them BEFORE waiting; also Write
   `w<k>/worker-roster.md`.
5. Wait for terminal results (Step 10w wait).
6. Terminal handling per §3.1/§4 (TIMED_OUT ⇒ TaskStop+verify; REQUIRED FAILED/TIMED_OUT ⇒
   verifier will FAIL; OPTIONAL may be skipped). Update `status` per worker in transition-state.
7. **Prove zero live workers (§3.1)** before ANY deactivation; unprovable ⇒ abort firebreak-ACTIVE
   (transition-state `abort`, `wave.md` STATUS ABORT).
8. Ownership gate (Step 10.5w) against `original_branch`.
9. **Ancestry proof (§3.3)**; apply the pinned Run-070 pre-flight merge if needed, else abort.
10. Assemble the wave once via swarm-runner (`reports_dir=w<k>/`, `assembly_branch=
    swarm-<run-id>-w<k>-assembly`); update transition-state phase `assembled` +
    `assembled_output_sha` = new `original_branch` HEAD (atomic).
11. Firebreak stays ACTIVE for everything it permits; only step 12 may deactivate.
12. Deactivate ONLY for the smallest blocked `python -m` gate window: `deactivate --root <MAIN>`
    → gate(s).
13. **Unconditional finally:** `activate <run-id> --root <MAIN>` + read-back, whether the gate
    PASSED/FAILED/timed out/crashed.
14. Hard-abort if reactivation read-back ≠ ACTIVE (never spawn ungoverned).
15. Re-run provenance (invariant base; fail-closed insurance): `check_spec_provenance.py --repo
    <MAIN> --default-branch <default> --original-branch <feature> --spec-path <spec_path>`.
16. `propagated_next_base_sha` = `original_branch` HEAD; read it back live.
17. `wave_artifact.py emit` writes `w<k>/wave.md` atomically (§6).
18. `verify_wave.py --wave <k>` (full CLI §7) — the blocking gate.
19. On verifier exit 0, update transition-state phase `verified`; spawn wave k+1. After the final
    wave, proceed to **Step 17w (Shared Tail delegation)** — per-wave assemblies already did all
    11w-16w work; the tail runs `verify_wave.py --reconcile` fail-closed.

### Resume-after-context-death (§5, idempotent across every crash boundary)
On resume (tail-resume/CHECKPOINT), for each wave read `w<k>/transition-state.json`:
- **absent** ⇒ wave not started ⇒ start at step 3.
- **`spawned`** (workers may be live) ⇒ read recorded `task_id`s, `TaskStop`+verify EVERY one,
  **prove zero live before anything else** (§3.1). Then: if the workers committed and no assembly
  ran (`original_branch` HEAD == `expected_base_sha`), resume at step 8; if zero-live unprovable,
  abort firebreak-ACTIVE.
- **`assembled`** (assembly done, artifact not emitted — the dangerous boundary) ⇒ do NOT
  re-spawn or re-assemble; `original_branch` HEAD already == `assembled_output_sha`; resume at
  step 15 (provenance → emit → verify). Idempotence key `(run_id, wave_index,
  assembled_output_sha)`; a re-run that would advance `original_branch` again is refused.
- **`verified`** ⇒ wave complete; skip to wave k+1.
- **`abort`** ⇒ terminal; the run stays aborted (no silent resume).
Duplicate prevention: spawn guarded by transition-state presence; cherry-pick/merge guarded by
the `assembled` phase + HEAD==`assembled_output_sha`; verifier is deterministic (safe to re-run);
artifact overwrite prevented by atomic emit keyed on `assembled_output_sha`.

## 6. Per-wave artifact + transition-state schema (atomic)
`w<k>/wave.md` (STATUS line 1 ∈ {PASS-EMITTED, ABORT}, then a fenced JSON block), written by
`wave_artifact.py emit` via temp + `os.rename` (same-dir, atomic on POSIX). Fields: `run_id`,
`wave_count`, `wave_index`, `run_start_ts`, `emit_ts`, `expected_base_sha`,
`actual_worker_base_sha` (=`origin/<default>` tip), `roster` (list of `{task_id, agent_id, role,
branch, required, status, terminal_evidence}` where `terminal_evidence` ∈ {completion-notified,
TaskStop-verified}), `ownership_gate` (PASS/FAIL + path), `assembled_output_sha`, `gate_results`
(`contract` verdict+path [blocking]; `smoke`,`test` verdict+path [non-blocking]),
`firebreak_readback` (ACTIVE + ts), `propagated_next_base_sha`, `provenance` (STATUS + path),
`prev_wave_output_sha` (= wave `k-1` `assembled_output_sha`; null for k=1), `prev_wave_artifact_sha`
(= sha256 of the bytes of `w<k-1>/wave.md`; null for k=1; the verifier recomputes and compares —
tamper-evidence), `abort_reason` (null unless STATUS ABORT). **Within-wave invariant:** nothing
advances `original_branch` between steps 10 and 16 ⇒ `assembled_output_sha ==
propagated_next_base_sha` (verifier asserts). **Continuity:** `wave[k].propagated_next_base_sha ==
wave[k+1].expected_base_sha` and `wave[k+1].prev_wave_output_sha == wave[k].assembled_output_sha`.
`transition-state.json` mirrors `run_id/wave_index/phase/roster/expected_base_sha/
assembled_output_sha` and is the resume source of truth.

## 7. `verify_wave.py` — authoritative CLI + reject-set
**CLI (every truth source explicit; nothing derived from the artifact alone):**
`--wave K --reports-dir <dir> --root <MAIN> --plan <plan_path> --spec-path <spec_path> --run-id
<id> --run-start-ts <epoch> --original-branch <feature> --default-branch <default>
--expected-roster <path|inline> --required-map <path|inline>`. It re-derives the declared wave
count from `--plan` frontmatter, the expected roster + required/optional from `--expected-roster`/
`--required-map`, the worker base from `git rev-parse origin/<default>`, and live HEADs from
`--root`, then checks the artifact against them.

**Immediate `--wave K` rejects if ANY:** artifact missing/extra/duplicate/non-contiguous;
`run_id`≠`--run-id` or `run_start_ts` older than `--run-start-ts` (stale/wrong-run); roster ≠
`--expected-roster` (missing/extra worker); any worker non-terminal; any REQUIRED worker FAILED
or TIMED_OUT(-STOPPED) per `--required-map`; `ownership_gate`≠PASS; **contract gate verdict ≠
PASS** (blocking) or missing (smoke/test verdicts recorded, non-blocking, but must be PRESENT);
`expected_base_sha` ≠ prior wave's `propagated_next_base_sha`; `assembled_output_sha` not a
descendant of `expected_base_sha` in live history; **`origin/<default>` tip is NOT an ancestor of
`expected_base_sha`** (the §3.3 ancestry proof was violated → base/default commits would enter the
worker cherry-pick range and be replayed as new worker deltas); the commit count of
`expected_base_sha..assembled_output_sha` ≠ the number of COMPLETED workers' non-empty deltas
(unexpected commits introduced); `assembled_output_sha` ≠ live `original_branch` HEAD at
verify time OR ≠ `propagated_next_base_sha`; `firebreak_readback`≠ACTIVE; `provenance`≠
PROVENANCE_OK; `prev_wave_artifact_sha` ≠ recomputed sha256 of `w<k-1>/wave.md`. `--validate-schema`
enforces §4. `--reconcile` re-runs `--wave` checks across ALL waves 1..N and additionally FAILs
if verified-artifact count ≠ declared `waves`, the SHA chain (`prev_wave_output_sha` →
`expected_base_sha`) breaks anywhere, any `assembled_output_sha` is not an ancestor of the live
`original_branch` HEAD, or the final wave's `assembled_output_sha` ≠ live `original_branch` HEAD.

## 8. Acceptance Tests (executable EARS) + Verification Commands
Unit fixtures live in `tools/test_verify_wave.py` / `tools/test_wave_artifact.py` (materialize
artifacts + a temp git repo). Orchestration behaviors that unit tests cannot cover get a live
spike (grep-for-prose is NOT accepted).

### Happy path
- WHEN a plan declares `waves: 3` with a valid `Wave`/`Required` table THE SYSTEM SHALL pass
  `--validate-schema` and run 3 waves with cross-wave SHA continuity.
  - Verify: `python3 tools/test_verify_wave.py::test_three_wave_continuity`.
- WHEN `waves` is absent or `1` THE SYSTEM SHALL behave as the current single-wave path (no
  artifacts, no `verify_wave` invocation).
  - Verify: `python3 tools/test_verify_wave.py::test_single_wave_noop` + live spike
    `spike_single_wave_regression` (a 1-wave run emits no `w*/` artifacts and calls no verifier).

### Error cases (each a named test/fixture)
- WHEN the wave count is invalid or the grouping malformed THE SYSTEM SHALL FAIL `--validate-schema`
  with a specific message. → `test_schema_invalid_count`, `test_schema_forward_ref`,
  `test_schema_runtime_dependent_edge_rejected`.
- WHEN a wave artifact is missing/duplicate/stale/wrong-run THE SYSTEM SHALL FAIL `--wave`. →
  `test_artifact_missing`, `_duplicate`, `_stale_ts`, `_wrong_runid`.
- WHEN a REQUIRED worker is FAILED/TIMED_OUT THE SYSTEM SHALL FAIL `--wave`; an OPTIONAL one SHALL
  PASS. → `test_required_worker_failed`, `test_optional_worker_skipped`.
- WHEN a worker times out and cannot be proven stopped THE SYSTEM SHALL abort with the firebreak
  ACTIVE (no deactivation). → live spike `spike_timeout_unstoppable_aborts_active`.
- WHEN zero-live cannot be proven THE SYSTEM SHALL refuse the toggle. → `spike_no_live_proof_no_toggle`.
- WHEN a between-waves gate FAILS or times out THE SYSTEM SHALL still reactivate + read-back
  before any next step. → live spike `spike_finally_reactivation`.
- WHEN reactivation read-back ≠ ACTIVE THE SYSTEM SHALL hard-abort with no next spawn. →
  `spike_reactivation_fail_aborts`.
- WHEN ownership fails THE SYSTEM SHALL FAIL `--wave`. → `test_ownership_fail`.
- WHEN a base/default commit would be replayed as a worker delta THE SYSTEM SHALL FAIL `--wave`. →
  `test_base_commit_replay_rejected` (fixture: `origin/<default>` has a commit the feature branch
  lacks; assert no-replay + ancestry check).
- WHEN provenance drifts after a wave THE SYSTEM SHALL FAIL `--wave`. → `test_provenance_drift`.
- WHEN a resume finds an `assembled`-phase wave THE SYSTEM SHALL emit+verify without re-spawn/
  re-assembly. → `spike_resume_after_assembly_no_dup` (crash injected between steps 10 and 17).
- WHEN a resume finds `spawned` with live tasks THE SYSTEM SHALL stop them + prove zero live
  before proceeding. → `spike_resume_spawned_stops_tasks`.
- WHEN the tail runs THE SYSTEM SHALL FAIL `--reconcile` on artifact-count mismatch or a broken
  SHA chain. → `test_reconcile_count_mismatch`, `test_reconcile_chain_break`.

### Regression / invariants
- WHEN the classifier suite runs THE SYSTEM SHALL report **284/284** — the **282** existing cases
  stay green plus 2 new file-path allow-cases (`tools/wave_artifact.py`, `tools/verify_wave.py`),
  each TRUSTED-only and STILL DENIED for workers, with **no new `-m` allow-case**.
  - Verify: `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → `284/284 passed`; plus
    `test_wave_tools_denied_for_worker` and `test_no_m_allow_case`.

### Verification Commands (summary)
- `python3 tools/test_verify_wave.py` — all wave-verifier + schema cases green.
- `python3 tools/test_wave_artifact.py` — schema + atomic-emit + transition-state cases green.
- `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → `284/284 passed`, no `-m` allow-case.
- Live spikes `spike_*` above executed in the work-phase branch (orchestration-level).
- `python3 tools/verify_wave.py --reconcile ...` on a real multi-wave run → `STATUS: PASS`.

## 9. Most likely way this plan is wrong
1. **The spec-only premise (§3.2 / spike 0a).** Run 083's documented per-wave code push is prima
   facie counter-evidence; if 0a shows dependent workers genuinely need prior-wave files at
   author time, Design X collapses to independent-waves-only and the validator rejects the very
   layered builds (models→routes) this is meant to enable — a large scope cut, but pinned and
   executable, not a surprise.
2. **TaskStop observability (§3.1 / 0b).** If background tasks can't be reliably stopped/verified,
   the liveness gate is always-abort-on-timeout (safe, possibly over-conservative).
3. **Reusing swarm-runner per wave.** It was authored for one whole-run assembly; per-wave reuse
   (different `reports_dir`/`assembly_branch`/branch set) is assumed side-effect-clean beyond the
   report-path scoping — a work-phase spike (`spike_per_wave_swarm_runner`) must confirm no
   run-level state leaks between wave invocations.

## Feed-Forward
- **Hardest decision:** Not asserting the spec-only premise away. Run 083's solution doc says it
  pushed code per wave; rev3 treats that as *sufficient-not-proven-necessary* and gates the whole
  design on a falsifiable spike with a pinned, executable fallback.
- **Rejected alternatives:** (a) per-wave FF `origin/<default>` code push (Run-083 mechanic /
  Codex option B) — violates the firm no-master-push policy. (b) harness re-rooting worktrees on
  an integration branch — unverified capability. (c) letting workers self-verify cross-module —
  requires code presence ⇒ (a); instead self-verification is deferred to assembly (Design X).
- **Least confident:** §3.2 premise, TaskStop observability, and per-wave swarm-runner cleanliness
  — all three are BLOCKING work-phase spikes (§0 + `spike_per_wave_swarm_runner`) that must pass
  before any SKILL/tool code is written.
