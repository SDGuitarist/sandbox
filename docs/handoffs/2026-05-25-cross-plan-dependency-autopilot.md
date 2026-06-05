# Cross-Plan Dependency: Autopilot SKILL.md

**Date:** 2026-05-25
**Affects:** `.claude/skills/autopilot/SKILL.md`

Two plans are in-flight that both modify the autopilot pipeline. This note
documents what each touches so neither session introduces a conflict.

## Plan A: Phase Agent Delegation

**Branch:** `refactor/autopilot-agent-delegation`
**Worktree:** `~/Projects/sandbox-autopilot-delegation`
**Plan:** `docs/plans/2026-05-23-refactor-autopilot-phase-agent-delegation-plan.md`

Refactors the autopilot so each major phase runs in its own spawned agent
instead of inline in the orchestrator's context window. Reduces orchestrator
context from ~80-150k tokens to ~15-20k.

**What it changes in SKILL.md:**

| Section | Change | Status |
|---------|--------|--------|
| Step 2.5 | NEW -- persist brief + clean stale manifests | DONE |
| Step 3 (Brainstorm) | Replaced with phase-brainstorm agent spawn | DONE |
| Step 5 (Plan) | Replaced with phase-plan agent spawn | DONE |
| Step 6 (Deepen) | Replaced with phase-deepen agent spawn | DONE |
| Step 7s (Solo Work) | Will replace with phase-work agent spawn | TODO |
| Shared Tail (Review/Resolve/Compound) | Will replace with phase-review agent spawn | TODO |
| Context-budget formula | Will remove `review_agents * 1.5` term | TODO |
| Phase 6 cleanup | Will renumber steps, remove dead inline logic | TODO |

**What it does NOT touch:**

- Steps 7w-16w (Swarm Path) -- explicitly preserved, "hard V1 non-goal"
- Steps 9w.5, 9w.6, 9w.7 (pre-swarm gates) -- unchanged
- Step 10w-16w (parallel swarm work, assembly, verification) -- unchanged

**New files created:** `.claude/agents/phase-brainstorm.md`, `phase-plan.md`,
`phase-deepen.md` (done), `phase-work.md`, `phase-review.md` (todo).

## Plan B: Spec Eval Gate

**Branch:** `feat/pitfall-eval-harness`
**Plan:** `eval-harness/docs/plans/2026-05-24-feat-spec-eval-gate-plan.md`

Adds a pre-swarm gate (step 9w.8) that tests whether agents can follow a
spec's concrete instructions before launching a swarm.

**What it changes in SKILL.md:**

| Section | Change |
|---------|--------|
| Swarm Path, between 9w.7 and 10w | NEW step 9w.8 -- spec eval gate |

That's it. One new step in the swarm path. Everything else is new Python
files in `eval-harness/`.

**What it does NOT touch:**

- Solo Path (Step 7s)
- Shared Tail (Review/Resolve/Compound)
- Steps 1-6 (Setup, Brainstorm, Plan, Deepen)
- Context-budget formula

## Overlap Analysis

The two plans touch **different sections** of SKILL.md:

```
SKILL.md structure:
  Steps 1-2.5   -- Delegation modifies (DONE)
  Step 3        -- Delegation modifies (DONE)
  Step 5        -- Delegation modifies (DONE)
  Step 6        -- Delegation modifies (DONE)
  Step 7s       -- Delegation modifies (TODO)     <-- Solo Path
  Steps 7w-9w.7 -- Neither modifies
  Step 9w.8     -- Spec Eval Gate ADDS (TODO)     <-- Swarm Path
  Steps 10w-16w -- Neither modifies
  Shared Tail   -- Delegation modifies (TODO)
```

**No direct line-level merge conflict.** They never edit the same lines.

## Risks and Coordination Points

### 1. Step renumbering (LOW risk)

Delegation's Phase 6 says "Renumber remaining steps for clarity." If the
renumbering changes swarm step numbers (e.g., 9w.7 -> something else),
the spec eval gate's reference to its position changes.

**Mitigation:** Delegation's plan explicitly says swarm steps 7w-16w stay
unchanged. The renumbering targets dead inline logic in the solo path and
shared tail, not swarm steps. But the session doing Phase 6 should verify
it doesn't accidentally shift swarm step numbers.

### 2. Report file awareness (LOW risk)

Spec Eval Gate writes results to `reports/spec-eval-<run-id>/spec-eval-gate.json`.
Delegation's phase-review agent reads report files during review. If the
review agent should mention spec eval gate results in the solution doc,
it needs that path.

**Mitigation:** Not urgent for V1. The spec eval gate runs pre-swarm;
the review runs post-swarm. The review agent already reads all files in
`docs/reports/<run-id>/` -- the spec eval report would be found naturally
IF it's written under that directory. Currently it's not (separate naming
convention). This is a V2 coordination item.

### 3. Context-budget formula (NO risk)

Delegation updates the formula to `load = swarm_agents + (fix_retries * 3)`.
The spec eval gate is a pre-swarm gate with zero orchestrator context
contribution (it runs and exits before the swarm). No interaction.

## Recommended Merge Order

Either order works. Preference: **Spec Eval Gate first** because:
- Its SKILL.md change is purely additive (insert one new step)
- Delegation's Phase 6 cleanup then naturally sees and preserves 9w.8
- If delegation lands first, spec eval gate just needs to verify step
  numbers haven't shifted in the swarm path (they shouldn't have)

## For the Spec Eval Gate Session

When you add step 9w.8 to SKILL.md, be aware:

1. Steps 3, 5, and 6 in SKILL.md have already been rewritten (on the
   delegation branch) to spawn phase agents instead of running inline.
   Your step 9w.8 is in the swarm path (7w-16w) which is untouched.
2. The delegation branch will eventually modify the Shared Tail too.
   Your step 9w.8 has no interaction with the tail.
3. If you need the spec eval gate result available during review, write
   it under `docs/reports/<run-id>/` (not a separate path) so the
   phase-review agent picks it up automatically.

## For the Delegation Session

When you do Phase 6 (cleanup/renumber):

1. Step 9w.8 may already exist in SKILL.md (if spec eval gate merged first).
   Preserve it during renumbering.
2. The phase-review agent should be told to read all `docs/reports/<run-id>/`
   files, which will include spec eval gate results if present.
3. The context-budget formula has no interaction with the spec eval gate.
