# HANDOFF — Sandbox

**Date:** 2026-06-07
**Branch:** feat/cpaa-event-replay-simulator
**Phase:** Orchestration-hardening **COMPOUND COMPLETE** (work + Codex review GO ×3 + solution doc + learnings propagated). Only remaining gate: **validate-on-real-build**.

## Current State

The post-Run-069 autopilot orchestration-hardening refactor is fully implemented (3 tracks, spike-gated), Codex binding-reviewed (**GO ×3**), documented (solution doc), and its lessons propagated to all learning surfaces. 9 commits on `feat/cpaa-event-replay-simulator`. The changes govern **every future swarm run**; they are reviewed-but-not-yet-field-proven on a live build.

Tracks: **A (FC51)** base-divergence-aware cherry-pick assembly + `assembly-ownership-conflict:` class + ownership base `main`→`original_branch`; **B (FC50)** orchestration-entrypoint signature-presence guard; **C** spec-eval (9w.8) demoted to advisory.

## Key Artifacts

| Item | Location |
|------|----------|
| Plan | docs/plans/2026-06-07-refactor-autopilot-orchestration-hardening-plan.md |
| Spike (Phase 0) | docs/reports/orchestration-hardening/spike-worktree-base.{sh,md} (+ spike-ownership.sh, spike-conflict.sh) |
| Solution | docs/solutions/2026-06-07-autopilot-orchestration-hardening.md |
| Fixtures | docs/fixtures/{unpinned,model-only,pinned}-entrypoint-spec.md |

## Open Operator Decisions (NOT done — outward actions, awaiting your call)

- **(a) Push** `feat/cpaa-event-replay-simulator` to remote?
- **(b) Merge to master now, or hold** until validate-on-real-build?
- Recommendation: **push + hold the merge** until validate-on-real-build (these changes govern all future runs; let the next swarm validate from the branch first).

## Remaining Gate — Validate-on-Real-Build

The next real feature-branch swarm must exercise all three tracks in ONE run; complete ONLY if its reports contain the **9w.6 PASS**, the **advisory spec-eval log**, AND a **per-worker cherry-pick base in `assembly-summary.md`**. A 9w.6 false-FAIL that aborts before Track A = validation incomplete, not pass.

## Deferred Items

- First-class detached-HEAD detection via `git worktree list --porcelain` (needs worktree paths in the runtime contract).
- **Cosmetic:** `SKILL.md:40` intro parenthetical ("inlines ... merge-conflict resolution") is now inaccurate; left because it is above the solo/swarm branch point (354), out of work-phase scope.
- Spec-eval re-promotion path if `spec_eval_gate.py` precision is fixed.
- **[069-D1]** GOLDEN_PROJECTION_HASH not frozen (compute_golden.py CSRF token-reuse bug; F1 test skips gracefully). **[069-D2]** F2 worker worktree may remain (`git worktree remove --force`).

## Three Questions

1. **Hardest decision?** Demoting the spec-eval gate whose own design-time solution doc argues it should stay hard — resolved by weighting field precision (2-for-2 waive = ~0%) over bench calibration, with a documented re-promotion path (not deletion).
2. **What was rejected?** keep-merge-fork assembly (dead code in the divergent-base reality); a call-site classifier for entrypoint coverage (a second 0-precision gate); retrofitting the frozen 069 plan; passing worktree paths into the runtime just to detect detached-HEAD.
3. **Least confident about?** validate-on-real-build hasn't run; the detached-HEAD residual (empty-delta path) is bounded but not field-observed. The first real swarm on this branch is the proof.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is Sandbox, the compound-engineering autopilot repo.
Orchestration-hardening is COMPOUND COMPLETE (Codex GO x3, branch feat/cpaa-event-replay-simulator).
Decide: push branch? merge to master? Then the only remaining gate is validate-on-real-build —
run the next real feature-branch swarm and confirm its reports contain the 9w.6 PASS, the advisory
spec-eval log, and a per-worker cherry-pick base in assembly-summary.md.
```
