# Session Brief: Spec Eval Gate Work Phase

**Date:** 2026-05-25
**Branch:** `feat/pitfall-eval-harness`
**Plan:** `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md`
**Brainstorm:** `eval-harness/docs/brainstorms/2026-05-24-spec-eval-gate-brainstorm.md`

## What You're Building

A pre-swarm gate (step 9w.8) that tests whether agents can follow a spec's
concrete instructions before launching a swarm build. Extracts testable
claims from spec tables and prose, generates scenarios, runs them through
the eval harness, and blocks the swarm if agents can't reliably follow
the spec.

## Concurrent Work: Autopilot Delegation (MUST READ)

Another plan is being implemented in parallel on branch
`refactor/autopilot-agent-delegation` (worktree: `~/Projects/sandbox-autopilot-delegation`).
It modifies the same file you'll touch: `.claude/skills/autopilot/SKILL.md`.

**Full dependency analysis:**
`docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md`

**Summary of what matters to you:**

1. The delegation plan touches Steps 3, 5, 6, 7s, and Shared Tail in
   SKILL.md. It does NOT touch the swarm path (Steps 7w-16w).
2. Your step 9w.8 goes in the swarm path between 9w.7 and 10w. No conflict.
3. If the delegation branch merges first, step numbers in the swarm path
   will NOT have changed (swarm steps are explicitly preserved).
4. If you want the spec eval gate result visible during review, write it
   under `docs/reports/<run-id>/` so the new phase-review agent finds it.

**Bottom line:** You can proceed without worrying about the delegation work.
Just add your step 9w.8 to the swarm path and it won't collide.

## Plan Summary (5 phases)

| Phase | What | Est. Lines | Key Files |
|-------|------|-----------|-----------|
| 1 | Data models + exceptions + runner refactor | ~70 | models.py, exceptions.py, runner.py, pitfall_eval.py |
| 2 | Extractor (table parser + prose extraction) | ~180 | extractor.py |
| 3 | Scenario generator | ~80 | spec_scenario_gen.py |
| 4 | Gate scorer | ~120 | spec_scorer.py |
| 5 | CLI + integration | ~100 | spec_eval_gate.py, spec_judge.py, judges/spec-eval-base.txt |

**Phase 2 has a BLOCKING PREREQUISITE:** Test extraction against 2 real
specs (WRC, Ethics Toolkit) with `--dry-run` and check in calibration
artifacts before proceeding to Phase 3.

## Critical Implementation Details

1. **Use `variant="with_rule"`** for all spec-eval scenarios. This is the
   only variant that makes `build_prompt()` inject `rule_text`. Using
   anything else silently tests nothing.
2. **Use `tier="1a"`** for synthetic FCs. `tier: 0` crashes Pydantic.
3. **Refactor `runner.py`** to accept `rule_text: str` instead of
   `fc: FailureClass`. 4-line change, eliminates the synthetic FC hack.
4. **`reasoning` before `verdict`** in judge tool schema (chain-of-thought
   debiasing).
5. **Catch `OverloadedError` (529)** -- not a subclass of `InternalServerError`.

## Key Files to Read First

1. Plan: `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md`
2. Runner interface: `eval-harness/runner.py` (build_prompt + run_scenario)
3. Existing models: `eval-harness/models.py`
4. Existing judge: `eval-harness/judge.py` (check_deterministic to reuse)
5. Cross-plan note: `docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md`

## Start Command

```
Read eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md.
Read docs/handoffs/2026-05-25-cross-plan-dependency-autopilot.md for
concurrent work awareness. Implement Phase 1 (data models + runner refactor).
Relevant files: eval-harness/models.py, eval-harness/runner.py,
eval-harness/pitfall_eval.py.
```
