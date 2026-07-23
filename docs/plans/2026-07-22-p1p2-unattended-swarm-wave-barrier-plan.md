---
title: "P1/P2 — Encode the unattended multi-wave swarm barrier loop"
date: 2026-07-22
status: draft
phase: plan
revision: 2  # revised to resolve Codex Plan Review NO-GO (P0 + P1 + P2 findings)
branch: feat/p1p2-unattended-swarm-wave-barrier
relates_to:
  - unattended-big-run-trust-gate (MEMORY)
  - swarmlimit-run-083 (harvest H5/H7)
  - fc68-firebreak-cwd-root-anchor (merged 4da3eff)
feed_forward:
  risk: "The whole design rests on ONE architectural premise: spec-driven workers never need a prior wave's actual files at spawn (they code against the shared spec; integration is at assembly). If that premise is false for any real dependency (a worker that must execute prior-wave code), dependent unattended waves are infeasible without a remote-base push. This is the verify-first spike gating all other work."
  verify_first: true
---

# P1/P2 — Encode the unattended multi-wave swarm barrier loop

## Context

The trust gate (`unattended-big-run-trust-gate`) blocks launching a ≥20-agent swarm
fully hands-off. Run 083 succeeded only because a human hand-ran the wave barriers,
approved every push, and cat-verified the firebreak after a live fail-open. This plan
targets trust criteria (2) firebreak needs no *manual* toggling and (3) the wave-barrier /
push mechanic runs from the SKILL, not live judgment. P1 (FC68/083-W6) is already merged
(`4da3eff`); the H5 toggle is documented (SKILL 803-814) but not integrated into a loop.

## Codex Plan Review resolution map (revision 2)

| Codex finding | Resolution (section) |
|---|---|
| **P0** toggle can leave a live worker ungoverned | §3.1 — hard "prove zero live workers" precondition on the toggle; TIMED_OUT ⇒ TaskStop + verify-stopped or ABORT with firebreak ACTIVE |
| **P1** base propagation vs no-master-push | §3.2 — dissolved: spec-driven workers need no cross-wave code; integration is per-wave assembly on the *local feature branch*. No origin/default push. Gated by verify-first spike 0a (§0) |
| **P1** per-wave assembly not integrated / commit replay | §3.3 — per-wave swarm-runner invocation; each cuts from advanced `original_branch` HEAD; disjoint per-worker `merge-base..branch` deltas ⇒ no replay |
| **P1** prose/count-only verification insufficient | §3.4 + §5 + §6 — structured per-wave artifact + immediate deterministic verifier (blocks next spawn) + tail reconciliation verifier |
| **P1** provenance not wholly out of scope | §3.2 — worker base is INVARIANT (origin/<default>); provenance re-run per transition with `--repo <MAIN>` as fail-closed insurance |
| **P2** define full wave schema | §4 |
| **P2** define every transition + recovery | §5 (the 19-step sequence) + §5 resume path |
| **P2** narrow default-branch policy | §3.5 — policy scoped to "unattended run pushes no CODE to origin/<default>"; the sole origin/<default> write remains the pre-existing spec-provenance repair |

## 0. Verify-first spike (BLOCKING — gate 0, before ANY SKILL/tool code)

Two spikes must pass (or their failure outcomes are pinned) before any deliverable in §1
is built:

- **0a — spec-driven premise (§3.2).** Build a minimal 2-wave test spec where a wave-2
  worker references a wave-1 spec'd interface (e.g. wave-2 `routes/x.py` imports a wave-1
  `models/y.py` name from the Export Names table). Spawn wave-1 (isolation worktree, rooted
  on `origin/<default>`), assemble to the feature branch. Spawn wave-2 **rooted on
  `origin/<default>` with wave-1's files absent from its worktree**; confirm it authors +
  commits its file against the spec. Assemble wave-2 onto the accumulated feature branch;
  confirm import resolution + `python -m compileall` (and a smoke import) PASS on the
  integrated tree. **PASS ⇒ premise holds, proceed. FAIL ⇒ dependent unattended waves are
  INFEASIBLE; scope drops to independent-waves-only (pinned outcome, not a work-phase decision).**
- **0b — TaskStop observability (§3.1).** Spawn one long-running background worker; `TaskStop`
  it; confirm `TaskList`/`TaskGet` reports it terminated. **PASS ⇒ the prove-zero-live gate is
  viable. FAIL ⇒ the gate degrades to always-abort-on-timeout (pinned, documented).**

Gate 0 outcome is recorded in the work-phase branch before the first SKILL/tool edit.

## 1. What exactly is changing?

Deliverables (work phase, AFTER the §0 spike passes). All are additive; none touch
firebreak *logic*.

1. **SKILL.md — "Multi-Wave Barrier Loop (Path B)" section** wrapping Step 10w, encoding
   the §5 per-wave sequence deterministically (spawn wave → barrier → prove-zero-live →
   ownership → per-wave assembly → toggle-bounded gate → reactivate+read-back → provenance
   → emit artifact → immediate verifier → next wave only on verifier exit 0).
2. **`waves: N` wave schema** (§4): plan frontmatter field + a required `Wave` column in the
   assignment table for `waves > 1`, plus a pre-spawn validator that FAILs on every
   malformed case.
3. **New tool `tools/wave_artifact.py`** — `emit` subcommand writes the §6 structured
   per-wave artifact **atomically** (temp + `os.rename`), from explicit CLI/JSON inputs
   (no self-derived state). Ships with `tools/test_wave_artifact.py`.
4. **New tool `tools/verify_wave.py`** — `--wave K` immediate verifier (the blocking
   between-waves gate) and `--reconcile` tail verifier. Reject-set in §7. Ships with
   `tools/test_verify_wave.py`.
5. **firebreak-classify.py — file-only allowlist additions**: append
   `tools/wave_artifact.py` and `tools/verify_wave.py` to `TRUSTED_PIPELINE_SCRIPT_PATHS`
   so they run under the active firebreak (identical to how `verify_harvest.py` was added
   this session). **This is the ONLY classifier change; it is data-only (two file paths),
   NOT a logic change and NOT an `-m` carve-out.** (Deviation from Codex's "no classifier
   change" note, justified + flagged for re-review — a pinned tool that must run under the
   firebreak has to be on the file-only allowlist.)
6. **CLAUDE.md + SKILL.md — narrowed default-branch policy** (§3.5).
7. **Tail integration**: the `--reconcile` verifier runs in the Shared Tail (fail-closed),
   and `CHECKPOINT.md` / tail-resume gains wave-resume state (§5 resume path).
8. **`docs/reports/<run-id>/wave-<k>.md` artifacts** — one per wave, the audit + verifier input.

## 2. What must NOT change

- **Firebreak carve-out logic.** No `-m`/name-based module carve-out; `-m` still yields no
  path-pinnable script; `TRUSTED_PIPELINE_SCRIPT_PATHS` stays a set of *file paths* only
  (item 1.5 adds two paths, no logic). All **283 existing classifier cases stay green** (zero
  regressions), with **no new `-m` allow-case** — the only additions are 2 file-path allow-cases
  (total 285; see §8).
- **Single-wave behavior.** `waves` absent or `waves: 1` ⇒ EXACTLY today's path: one Step
  10w spawn, one Step 10.5w ownership gate, one swarm-runner assembly, no between-waves gate
  window, no wave artifacts, no `verify_wave` invocation.
- **Worker governance invariant.** The firebreak is never off across a worker spawn; the
  toggle window is a barrier with *proven* zero live workers (§3.1).
- **Worker base ref.** Workers keep rooting on `origin/<default>` (baseRef=fresh). The plan
  does NOT try to re-root worktrees on a branch (unverified harness capability) — see §3.2.
- **swarm-runner's merge target.** It merges assembly → `original_branch` (the *feature*
  branch) locally, never to origin (already true; §3.5 depends on it).
- **The pre-spawn provenance gate (9w.9.5).** Unchanged; `check_spec_provenance.py` takes
  `--repo` (default `.`) — do NOT invent a `--root` flag.

## 3. Design resolutions

### 3.1 P0 — prove zero live workers before any deactivation
The toggle window (deactivate firebreak → run `python -m` gate → reactivate) may be entered
ONLY after every worker of the wave is **authoritatively terminal**:
- **COMPLETED** (harness completion notification received) = terminal.
- **TIMED_OUT** (no notification within the Step-10w window) = NOT terminal. The orchestrator
  MUST `TaskStop` the worker and confirm termination via `TaskList`/`TaskGet` (status
  terminated). Only then is it terminal (recorded as `TIMED_OUT_STOPPED`).
- If ANY worker cannot be proven stopped, **ABORT the run with the firebreak still ACTIVE**:
  do NOT deactivate, do NOT spawn the next wave, write the wave artifact with
  `abort_reason: live-worker-unprovable`, return FAIL.
The deactivate window therefore has zero live workers by construction. The next wave spawns
only after reactivation read-back reports ACTIVE (§5 steps 13–14, 19).

### 3.2 P1 — base propagation dissolved (no origin/default push, no re-rooting)
The premise: **workers are spec-driven.** Each worker writes only its assigned files against
the shared interface spec (Export Names, Cross-Boundary Wiring, Transaction Contracts, …) and
commits; it never imports/executes another worker's actual file. So a later-wave worker does
NOT need a prior wave's code in its worktree — rooting on stale `origin/<default>` is correct.
Cross-wave integration happens at **assembly**, not at spawn:
- Each wave's `original_branch` (feature branch) accumulates prior waves' assembled code
  (swarm-runner Step 7 merges assembly → `original_branch` locally).
- Wave N+1's assembly branch is cut from the **current** `original_branch` HEAD, so its
  workers' deltas land on top of Wave N.
Consequences: no `origin/<default>` update is needed; the worker base is **invariant** across
waves; the "no-master-push" policy is preserved. Provenance is re-run per transition
(`check_spec_provenance.py --repo <MAIN>`) purely as fail-closed insurance that the invariant
worker base still carries the converged spec. **This premise is verify-first spike 0a (§0);
if it fails for a genuine execute-prior-code dependency, dependent unattended waves are
declared INFEASIBLE and only independent waves are supported unattended (stated, not deferred).**

### 3.3 P1 — per-wave assembly without commit replay
Per wave, invoke the existing **swarm-runner** once (a per-wave call, not a new assembler),
with `original_branch` = the feature branch (advanced by prior waves) and only THIS wave's
`worker_branches`/`worker_status`. Because each worker forked from `origin/<default>` and
`merge-base(original_branch, worker) = origin/<default>` tip, the cherry-pick range
`merge-base..worker` contains ONLY that worker's own commits — prior waves' commits (already
on `original_branch`) are never in range, so they are not replayed. Disjoint ownership
(Step 10.5w) keeps cross-wave cherry-picks conflict-free; a conflict = ownership escape
(existing abort). Assembly/integration branch names: `swarm-<run-id>-w<k>-assembly` per wave.
Empty per-worker delta ⇒ existing "empty delta" no-op. Final wave → Shared Tail as today.
**Report-collision pin:** swarm-runner writes run-level reports (`assembly-summary.md`,
`contract-check.md`, `smoke-test.md`, `test-results.md`). Per-wave invocation would clobber
them, so the loop passes a per-wave `reports_dir` subpath `docs/reports/<run-id>/w<k>/` (or a
`w<k>-` filename prefix) and the wave artifact's `gate_artifacts` records the wave-scoped
paths. swarm-runner is invoked as-is (no code change) — only the `reports_dir`/`assembly_branch`
inputs differ per wave; its cleanup (Step 8) removes only that wave's worker worktrees/branches.

### 3.4 P1 — verification with teeth (not prose, not count-only)
Three layers (Codex binding decision): (1) a **structured** per-wave artifact (§6), written
atomically; (2) an **immediate** deterministic verifier `verify_wave.py --wave K` that must
exit 0 **before** the next spawn (reject-set §7); (3) a **tail reconciliation** verifier
`verify_wave.py --reconcile`. Freshness (run_start_ts + run_id on every artifact) defeats
stale/fabricated files; SHA chaining (prev output SHA → next base SHA) defeats fabrication
and discontinuity; the immediate placement defeats "too late to stop an unsafe Wave N+1."

### 3.5 P2 — narrowed default-branch policy
Policy (CLAUDE.md + SKILL.md): **"During an unattended autopilot run, no phase pushes CODE to
`origin/<default>`. Build code accumulates on the local feature branch; the master merge is
deferred to a human post-review (a HANDOFF deferred item). The SOLE sanctioned
`origin/<default>` write is the pre-existing spec-provenance repair (Step 9w.9.5), which is
spec-file-only and already gated."** This governs ONLY the unattended autopilot run modes
(solo + swarm, single- and multi-wave). It does not touch manual sessions and does not alter
the provenance-repair path (resolving the conflict Codex flagged). Single-wave behavior is
unchanged because swarm-runner already merges only to the feature branch. The multi-wave loop
performs **zero** remote-ref writes; therefore the remote-ref-update checklist (old/new SHA,
FF-only, read-back, race, human-auth, recovery) applies to NONE of it. The one pre-loop
provenance push (if any) retains its existing pre-check (local == origin hashes) and gating.

## 4. Wave schema (P2)

- `waves` absent or `waves: 1` ⇒ current single-wave behavior (no loop, no artifacts).
- `waves` MUST be a positive integer; `waves: 0` or non-integer ⇒ pre-spawn validation FAIL.
- For `waves > 1`, the `## Swarm Agent Assignment` table MUST have exactly one required
  `Wave` column; every agent row carries an integer wave in `1..N`.
- Every agent belongs to **exactly one** wave. Wave numbers must be **contiguous** (all of
  `1..N` present). **Empty waves are forbidden** (a declared wave with no agents ⇒ FAIL).
- **Required vs optional workers:** every worker is REQUIRED unless its row is marked
  `optional: true`. A REQUIRED worker ending FAILED or TIMED_OUT(-STOPPED) ⇒ the wave's
  immediate verifier FAILs (the wave's assembled base is incomplete for later waves). An
  OPTIONAL worker may be skipped (recorded, non-fatal).
- **Cross-wave dependency rule:** waves are strictly ordered; wave `k` may depend only on
  waves `1..k-1` (via the spec + accumulated assembly base). Forward references (a `k` agent
  the spec says wave `k+1` provides) ⇒ pre-spawn validation FAIL.
- Every malformed case above FAILs the **pre-spawn** validator with a specific message (no
  silent single-wave fallback).

## 5. Per-wave transition sequence (P2) — encoded in SKILL, run per wave k = 1..N

1. Validate the wave schema (§4) and record `expected_base_sha` = current `original_branch` HEAD.
2. Verify the firebreak is ACTIVE at canonical `<MAIN>` (`firebreak-activate.py status --root <MAIN>`); else abort.
3. Spawn ONLY wave k's roster (existing Step 10w spawn logic, scoped to the wave's rows).
4. Immediately Write `docs/reports/<run-id>/worker-roster.md` for the wave (write-only insurance) BEFORE waiting.
5. Wait for authoritative terminal results (Step 10w wait).
6. Handle FAILED/TIMED_OUT per §4 (TIMED_OUT ⇒ TaskStop + verify-stopped; REQUIRED failure ⇒ verifier will FAIL).
7. **Prove zero live workers (§3.1)** before ANY deactivation; unprovable ⇒ abort firebreak-ACTIVE.
8. Run the wave's ownership gate (Step 10.5w) against `original_branch`.
9. Assemble the wave exactly once via swarm-runner (§3.3); capture `assembled_output_sha` = new `original_branch` HEAD.
10. Record `assembled_output_sha`.
11. Keep the firebreak ACTIVE for everything it permits (only step 12 may deactivate).
12. Deactivate ONLY for the smallest blocked `python -m` gate window: `deactivate --root <MAIN>` → gate(s) → (step 13).
13. **Guarantee** `activate <run-id> --root <MAIN>` + read-back after the gate PASSES, FAILS, times out, or crashes (finally-semantics in the SKILL prose: the reactivate+read-back is unconditional).
14. Hard-abort the run if reactivation read-back ≠ ACTIVE (never spawn ungoverned).
15. Re-run provenance against the next base: `check_spec_provenance.py --repo <MAIN> --default-branch <default> --original-branch <feature>` (invariant base; fail-closed insurance).
16. `propagated_next_base_sha` = `original_branch` HEAD (local accumulation point); read it back.
17. **Atomically** write `docs/reports/<run-id>/wave-<k>.md` via `wave_artifact.py emit` (§6).
18. Run the immediate verifier: `verify_wave.py --wave <k> --reports-dir docs/reports/<run-id> --root <MAIN>`.
19. Spawn wave k+1 ONLY on verifier exit 0; after the final wave, proceed to **Step 17w (Shared Tail delegation)** — the per-wave assemblies already performed all 11w-16w work, so there is no separate whole-run assembly. The tail runs `verify_wave.py --reconcile` as a fail-closed gate.

### Resume-after-context-death (§5, resume path)
On resume (tail-resume/CHECKPOINT), read existing `wave-<k>.md` artifacts; the highest `k`
whose immediate verifier passed is the last completed wave. Resume at `k+1`. A wave whose
artifact exists AND verifies is NEVER re-spawned or re-assembled (idempotence key =
`(run_id, wave_index, assembled_output_sha)`). A half-written artifact is impossible (atomic
rename); a present-but-unverified artifact ⇒ re-run the immediate verifier, do not re-assemble
if `assembled_output_sha` already matches `original_branch` history.

## 6. Per-wave artifact schema + atomicity
`wave-<k>.md` (STATUS line 1, then a fenced JSON block) — written atomically (temp + rename)
by `wave_artifact.py emit`. Required fields:
`run_id`, `wave_count`, `wave_index`, `run_start_ts`, `emit_ts`, `expected_base_sha`,
`actual_worker_base_sha` (origin/<default> tip), `roster` (list of `{agent_id, role, branch,
status, terminal_evidence}`), `ownership_gate` (PASS/FAIL + path), `assembled_output_sha`,
`gate_artifacts` (parse/smoke result paths + verdicts), `firebreak_readback` (ACTIVE + ts),
`propagated_next_base_sha`, `provenance` (STATUS + path), `prev_wave_artifact_sha`,
`prev_wave_output_sha` (continuity; null for k=1). `terminal_evidence` ∈ {completion-notified,
TaskStop-verified}. **Within-wave invariant:** nothing advances `original_branch` between
assembly (step 9) and read-back (step 16), so `assembled_output_sha == propagated_next_base_sha`
(the verifier asserts this). **Continuity invariant:**
`wave[k].propagated_next_base_sha == wave[k+1].expected_base_sha`, and
`wave[k+1].prev_wave_output_sha == wave[k].assembled_output_sha`. Atomicity: `emit` writes
`wave-<k>.md.tmp` then `os.rename` (same-dir, atomic on POSIX).

## 7. Verifier reject-set (immediate, `--wave K`) — exit ≠ 0 blocks the next spawn
Reject if ANY: artifact missing / extra / duplicate / non-contiguous wave index; artifact
`run_id` ≠ current or `run_start_ts` stale (older than run start); any roster worker
non-terminal; any REQUIRED worker FAILED or TIMED_OUT(-STOPPED); ownership_gate ≠ PASS;
`expected_base_sha` ≠ prior wave's `propagated_next_base_sha` (base discontinuity) or
`assembled_output_sha` not a descendant of `expected_base_sha` (output discontinuity); any
gate verdict missing; `firebreak_readback` missing or ≠ ACTIVE; `propagated_next_base_sha`
read-back mismatch vs live `original_branch` HEAD; provenance ≠ PROVENANCE_OK. `--reconcile`
(tail) re-runs the full set across ALL waves 1..N and additionally FAILs if the count of
verified wave artifacts ≠ declared `waves`, or the SHA chain
(`prev_wave_output_sha` → `expected_base_sha`) is broken anywhere.

## 8. Acceptance Tests (EARS) + Verification Commands

Executable tests live in `tools/test_verify_wave.py` and `tools/test_wave_artifact.py`
(fixtures materialize wave artifacts + a temp repo), mirroring `test_verify_harvest.py`.
Grep-for-prose is explicitly NOT accepted as verification.

### Happy path
- WHEN a plan declares `waves: 3` with a valid wave-grouped table THE SYSTEM SHALL run 3
  ordered waves, each gated by an immediate verifier exit 0, with cross-wave SHA continuity
  (`wave-1.output → wave-2.expected_base → wave-2.output → wave-3.expected_base`).
  - Verify: `python3 tools/test_verify_wave.py` includes a 3-wave continuity case → passes.
- WHEN `waves` is absent or `1` THE SYSTEM SHALL behave exactly as the current single-wave
  path (no artifacts, no `verify_wave` call).
  - Verify: `python3 tools/test_verify_wave.py` single-wave regression case → the verifier is a no-op / not invoked.

### Error cases (each an executable test case)
- invalid wave count / malformed grouping ⇒ pre-spawn validation FAIL.
- missing / duplicate / stale / wrong-run wave artifact ⇒ immediate verifier FAIL.
- partial REQUIRED worker failure ⇒ immediate verifier FAIL; OPTIONAL failure ⇒ PASS.
- worker timeout with unsuccessful termination ⇒ run ABORT with firebreak ACTIVE (no deactivation).
- proof-of-no-live-worker absent ⇒ toggle refused (no deactivation).
- gate failure and gate timeout ⇒ firebreak reactivated + read-back before any next step.
- firebreak reactivation failure ⇒ hard abort, no next spawn.
- ownership failure ⇒ immediate verifier FAIL.
- base-propagation read-back mismatch ⇒ immediate verifier FAIL.
- provenance drift after a wave ⇒ immediate verifier FAIL.
- context resume with an already-verified wave ⇒ NO duplicate spawn/assembly.
- final tail reconciliation mismatch (fewer artifacts than `waves`, or broken SHA chain) ⇒ `--reconcile` FAIL.
  - Verify (all): `python3 tools/test_verify_wave.py` + `python3 tools/test_wave_artifact.py` cover each case above.

### Regression
- WHEN the classifier test suite runs THE SYSTEM SHALL report 285/285 — the 283 existing cases stay green (zero regressions) plus 2 new file-path allow-cases (`tools/wave_artifact.py` / `tools/verify_wave.py`), with **no new `-m` allow-case**.
  - Verify: `python3 .claude/hooks/test_firebreak_classify.py | tail -1` → `285/285 passed` (283 existing + 2 file-path allow-cases; zero `-m` allow-cases).

### Verification Commands (summary)
- `python3 tools/test_verify_wave.py` — all wave-verifier cases green.
- `python3 tools/test_wave_artifact.py` — schema + atomic-emit cases green.
- `python3 .claude/hooks/test_firebreak_classify.py | tail -1` — `285/285 passed`, no `-m` allow-case.
- `python3 tools/verify_wave.py --reconcile --reports-dir docs/reports/<run-id> --root <MAIN>` on a real multi-wave run → `STATUS: PASS`.

## 9. Most likely way this plan is wrong

1. **The spec-driven premise (§3.2).** If any legitimate later-wave worker must *execute* a
   prior wave's code at authoring time (not just reference its spec'd interface), rooting on
   stale `origin/<default>` breaks and no-push becomes impossible. Mitigation: verify-first
   spike 0a (§0) is BLOCKING and its failure has a pinned outcome (dependent unattended
   waves = INFEASIBLE; independent-only). Not deferred.
2. **`TaskStop` semantics (§3.1).** If a background worker cannot be reliably stopped/verified
   via the Task tools, the "prove zero live workers" gate degrades to always-abort — safe but
   possibly over-conservative (blocks legitimate runs). The spike must also confirm TaskStop
   observability.
3. **Classifier allowlist deviation (§1.5).** Codex asserted "no classifier change." Two
   file-path additions are the minimum for pinned tools to run under the firebreak; if Codex
   holds firm, the fallback is to run `verify_wave`/`wave_artifact` inside the already-open
   toggle window (uglier, larger window) — flagged for the re-review to rule on.

## Feed-Forward
- **Hardest decision:** Rejecting Codex's A/B/C base-propagation framing in favor of "no
  propagation needed" (§3.2). It's a stronger claim that must be spike-proven; if wrong, the
  fallback (independent-waves-only) is explicit, not hand-wavy.
- **Rejected alternatives:** (a) pinned wrapper script for the gate instead of the toggle —
  would avoid the deactivation window entirely, but needs a new pinned script and reads as
  bypassing Codex's "use the toggle" direction; kept the toggle + made liveness airtight.
  (b) FF-only `origin/default` integration push (Codex option B) — automates master pushes in
  an unattended run, against the owner's exercised master-gate discipline; rejected unless the
  spike disproves §3.2. (c) harness re-rooting worktrees on an integration branch (option A) —
  unverified capability; not relied upon.
- **Least confident:** §3.2's premise and TaskStop observability — both fold into the single
  BLOCKING verify-first spike that must pass before any SKILL/tool code is written.
