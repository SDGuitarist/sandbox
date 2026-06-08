---
title: "Autopilot Orchestration Hardening (Post-Run-069): cherry-pick assembly, orchestration-entrypoint gate, spec-eval demotion"
date: 2026-06-07
type: solution
project: sandbox
phase: compound
tags: [autopilot, swarm, swarm-runner, assembly, cherry-pick, worktree-base, spec-gate, spec-eval, spec-completeness, FC50, FC51, verify-first-spike, safe-skill-edit]
related_plan: docs/plans/2026-06-07-refactor-autopilot-orchestration-hardening-plan.md
supersedes_stance:
  - doc: docs/solutions/2026-06-01-spec-eval-gate-pre-swarm-validation.md
    field: "spec-eval (9w.8) should be a hard pre-swarm gate"
    reason: "design-time calibration overridden by 2-for-2 field waivers (runs 068, 069) = ~0% observed precision; re-promotion path documented"
failure_classes: [FC50, FC51]
feed_forward:
  risk: "validate-on-real-build is the only remaining completion gate; until a real swarm exercises all three tracks in one run, the cherry-pick assembly + advisory spec-eval + 9w.6 entrypoint guard are reviewed-but-not-field-proven on a live build"
  verify_first: false
---

# Autopilot Orchestration Hardening (Post-Run-069)

## Problem

Run 069 (24-agent CPAA swarm) succeeded, but its retrospective exposed three
places where the autopilot pipeline **looked deterministic but was backstopped by
human/LLM improvisation**:

- **A (FC51):** worker worktrees were rooted on the repo default branch
  (`master`, `f90aed8`), NOT on the orchestrator's feature HEAD. The swarm-runner
  applied a *merge-designed* inline conflict-resolution step to a *divergent*
  base, and the ownership gate diffed against a hardcoded `main`. The clean
  recovery (24/24, 0 conflicts) was luck — ownership happened to be 100% disjoint.
- **B (FC50):** the spec pins model-layer **nouns** but not orchestration
  **verbs**; 2/2 unpinned route→engine calls diverged (4 review P1s — import name
  B2/B3, arity C1/C6 — all knowable pre-spawn).
- **C:** the spec-eval gate (9w.8) was **WAIVED_BY_HUMAN 2-for-2** (runs 068, 069)
  for the same false-FAIL cause via a hand-authored verification file — a blocking
  gate whose only "pass" path was an improvised artifact = governance theater.

## Solution

A manual (non-swarm) refactor of `.claude/` autopilot infrastructure, in three
tracks, each its own commit, lowest-blast-radius first, Track A spike-gated.

### Track C — spec-eval (9w.8) → advisory (`0acd660`)
- 9w.8 never aborts/waives: records an advisory result and always proceeds to
  9w.9. RETRY retries once then logs advisory; ENV_ERROR records a **distinct**
  advisory naming an environment fault (so a broken harness can't masquerade as a
  clean run).
- Step 10w precondition: the `spec-eval-verification.md STATUS: PASS` requirement
  is **removed**. `gate-verification.md CLEARED` stays, so the structural gates
  9w.5/9w.6 remain blocking — the high-precision signals.
- No `spec_eval_gate.py` change; the harness still writes the file on a genuine
  PASS (now harmless/unused). Regression-grep: **zero** coded readers remain.

### Track B — orchestration-entrypoint signature-presence guard (FC50) (`3185f22`)
- Template (`shared-spec-flask.md`): "Orchestration Entrypoints" is now a required
  Export Names row-class (`Type = orchestration entrypoint`) with a populated
  `Full Signature` column — route→non-model calls AND tool→constants imports.
- CLAUDE.md item 1: entrypoints added as the 5th machine-checked class.
- `spec-completeness-checker` Check 1b: reuses Check 1's parsed table; **FAIL** any
  entrypoint row with an empty/placeholder Full Signature; **N/A** when zero such
  rows. It is a **signature-PRESENCE guard, NOT a call-site classifier** — building
  the classifier would risk a second 0-precision gate. Accepted blind spot: a
  *wholly-omitted* entrypoint is caught downstream by the assembly contract-check.
- Backtest (real checker agent): unpinned fixture → FAIL (names symbol),
  model-only → N/A, pinned → PASS.

### Track A — base-divergence-aware cherry-pick assembly (FC51) (`97acabe` spike, `ed38378` impl, `1f4c5bd` fix)
- Ownership gate: diff base `main...` → `<original_branch>...` (one token; the
  three-dot operator already attributes `merge-base(original_branch, branch)` — the
  worker's true fork point, the SAME base the cherry-pick uses: the **O3 invariant**).
- Assembly: per COMPLETED worker, `git cherry-pick $(git merge-base
  <original_branch> <branch>)..<branch>` onto an assembly branch cut from
  `original_branch` HEAD. **Strategy (i) uniform cherry-pick** chosen (see below).
  `<branch>^` is forbidden (silently drops earlier commits = the FC51 data-loss
  class). Zero-commit workers are a clean no-op ("empty delta").
- A cherry-pick conflict = ownership-gate **escape** (ownership was enforced
  disjoint at 10.5w): inline spec-resolution is NOT invoked (it would mask the
  violation); `git cherry-pick --abort`, preserve all worker branches, leave
  `original_branch` untouched, record new blocking class
  `assembly-ownership-conflict:`.
- Blocking classes stay at **2**: `merge-conflict:` retired (per-worker merge gone;
  the merge-back never used it and can't conflict since the assembly branch
  descends from `original_branch`) → replaced by `assembly-ownership-conflict:`.
  Propagated to swarm-runner Rule 2 + Output Contract + the orchestrator wire-abort
  handler.

## Key Lessons

1. **Field precision beats design-time calibration.** The spec-eval gate's
   2026-06-01 solution doc reported 81% pass + "24 genuine failures" and argued
   false-negatives are cheaper than false-positives at pre-swarm. But the two real
   swarm runs since (068, 069) produced ONLY false-FAILs that humans waived —
   **~0% observed precision in the field**. When a gate's field record contradicts
   its bench calibration, trust the field and demote (with a documented
   re-promotion path), don't keep enforcing a gate everyone overrides. *This
   reconciles the contradiction flagged against
   `2026-06-01-spec-eval-gate-pre-swarm-validation.md`: that doc is not wrong about
   the gate's intent; it predates the field counter-evidence.*

2. **Strengthen the high-precision gate, demote the low-precision one — in the same
   change.** Track B added the verb-coverage that was the ACTUAL 069 gap to the
   9w.6 completeness gate (100% P1 correlation, runs 047-052) at the same time
   Track C demoted the 0-precision 9w.8. Demotion didn't reduce coverage; it moved
   coverage to where precision is high.

3. **A guard you "validated" can still be unwireable.** The detached-HEAD
   pre-flight passed the spike (`rev-parse --abbrev-ref HEAD` *inside a checkout*)
   but was **dead code** in the runtime: the swarm-runner gets branch *names*, not
   worktree paths, and a branch name never resolves to `HEAD`. Codex caught it.
   **Lesson: a spike proving a mechanism is necessary but not sufficient — confirm
   the mechanism is wireable into the actual runtime contract (same inputs).** The
   fix dropped the unfireable check; a detached worker's lost commits now surface
   as a visible "empty delta" no-op rather than a silent success.

4. **Ground the strategy choice in field evidence, not the plan's default.** The
   plan defaulted to strategy (ii) keep-merge-fork. The spike PLUS the 069
   assembly-summary showed uniform cherry-pick (i) is literally what ran clean
   (24/24, 0 conflicts) and reproduces the `merge --no-ff` tree for is-ancestor +
   empty workers. (ii)'s per-worker merge is dead code in the divergent-base
   reality. Chose (i): simpler, one path.

5. **Verify-first spike before touching a working pipeline.** Track A touched the
   assembly path of a pipeline that had just run clean at 24 agents. The Phase-0
   spike (throwaway repos, 16/16 + 1 + 5 assertions) resolved the riskiest
   assumption (is merge-base always the true fork point?) BEFORE any SKILL.md edit.

6. **Don't rewrite history to make a backtest pass.** The frozen Run 069 plan
   honestly returns N/A for the new entrypoint guard (it predates the row-class).
   Rather than retrofit a completed-run plan (contraindicated by the operating
   contract), a dedicated positive fixture proves the PASS path.

## Validation

- Phase-0 spike: 16/16 + ownership(1) + conflict(5) assertions PASS.
- Track B backtest via the real `spec-completeness-checker` agent: FAIL / N/A / PASS.
- Track C regression: 0 functional readers of `spec-eval-verification`.
- Codex binding review: **GO ×3** (round 1: B/C GO, A NO-GO → fixed; round 2: A GO).
- Constraints verified: solo path ≤ `SKILL.md:354` untouched; `original_branch`
  merge-back (swarm-runner Step 7) byte-for-byte untouched; ownership-base ==
  cherry-pick-base.

## Remaining gate

**Validate-on-real-build (NOT YET DONE):** the next real feature-branch swarm must
exercise all three tracks in ONE run; complete ONLY if its reports contain the
9w.6 PASS, the advisory spec-eval log, AND a per-worker cherry-pick base in
`assembly-summary.md`. A 9w.6 false-FAIL that aborts before Track A = validation
incomplete, not pass.

## Feed-Forward

- **Hardest decision:** demoting a gate (spec-eval) whose own design-time solution
  doc argues it should stay hard. Resolved by weighting field precision (2-for-2
  waive) over bench calibration, with a re-promotion path — not by deleting the
  gate (it still runs for data).
- **Rejected alternatives:** keep-merge-fork assembly (dead code in divergent-base
  reality); a call-site classifier for entrypoint coverage (second 0-precision
  gate); retrofitting the frozen 069 plan; passing worktree paths into the runtime
  just to detect detached-HEAD (scope creep — deferred).
- **Least confident:** validate-on-real-build hasn't run. The detached-HEAD
  residual (empty-delta path) is bounded but not field-observed. First real swarm
  on this branch is the proof.

## Follow-ups

- **Deferred:** first-class detached-HEAD detection via `git worktree list
  --porcelain` (needs worktree paths in the runtime contract).
- **Cosmetic:** `SKILL.md:40` intro parenthetical still says swarm-runner "inlines
  ... merge-conflict resolution" (now inaccurate); left because it is above the
  solo/swarm branch point (354), out of the work-phase edit constraint.
- **Re-promotion path:** if `spec_eval_gate.py` precision is fixed, restore the
  9w.8 abort.
