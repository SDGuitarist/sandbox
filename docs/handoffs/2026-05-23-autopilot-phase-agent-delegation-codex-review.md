# Codex Review: Autopilot Phase Agent Delegation Plan

**Date:** 2026-05-23
**Phase:** Plan Review (post-brainstorm, post-deepening, pre-work)
**Repo:** ~/Projects/sandbox
**Reviewer:** Codex

## What I Need From You

Read docs/plans/2026-05-23-refactor-autopilot-phase-agent-delegation-plan.md.

This plan is close, but it is not clean yet. Two issues block implementation
readiness, and a few follow-up concerns need cleanup so the work phase has one
clear target.

Please revise the plan so it is internally consistent and ready for work.

## Findings

1. **P1 -- Bundle 4 is internally contradictory**

   The plan currently says:
   - Bundle 4 is a V1 non-negotiable bundle implemented as `phase-review.md`
   - But Phase 4.0 says that if the compound disk-isolation measurement passes,
     Bundle 4 should be split into `phase-review.md` + `phase-compound.md`

   That creates two different implementation targets inside the same plan.
   There is no matching file inventory, deliverable list, or acceptance
   criteria for `phase-compound.md`.

   **Fix required:**
   Pick one clear V1 path:
   - Either keep Bundle 4 monolithic in this plan and move the compound split
     experiment to a follow-up plan, or
   - Fully spec the split path in this plan, including file changes,
     deliverables, acceptance criteria, and autopilot modifications.

   My recommendation: keep V1 strictly monolithic and move the split
   experiment to follow-up work. The brainstorm least-confident item is already
   acknowledged; it does not need to become an in-plan branch.

2. **P1 -- Retry/recovery semantics are wrong**

   The plan says retries should use:

   - `git reset --soft <recovery_point>`

   and claims this makes the next retry start clean.

   That is incorrect. `--soft` moves `HEAD` only. It leaves index and working
   tree changes intact, so partial edits remain staged or present on disk.
   That directly undermines the phase-agent recovery model.

   **Fix required:**
   Rewrite the retry/recovery section so the repo state after failure is
   actually well-defined. At minimum, the plan must:
   - stop claiming `--soft` gives a clean retry
   - specify whether retries preserve or discard partial uncommitted edits
   - make the chosen recovery rule consistent with the “disk is working memory”
     design and the repo’s safety constraints

   If you choose a conservative retry model, say exactly what survives and what
   the orchestrator reuses (`deepen-raw/`, manifest sentinel, committed state,
   etc.).

3. **P2 -- Manifest contract is not fully consistent across sections**

   The Enhancement Summary says the schema removed commit-related and
   deterministic-path fields as YAGNI, but the plan still depends on
   deterministic manifest paths and later bundle sections still mention commit
   hashes / fix commits as output data.

   **Fix requested:**
   Make one canonical manifest contract and align all sections to it:
   - Enhancement Summary
   - Manifest Schema
   - Bundle-specific implementation steps
   - Acceptance tests

   Clarify which fields are truly canonical, which are derived, and which are
   intentionally omitted.

4. **P2 -- `phase-plan.md` is under-specified relative to `/workflows:plan`**

   The plan removes `Agent` from `phase-plan.md`, but still says it will do
   repo-pattern research, learnings research, framework-doc research, and
   similar planning logic. The current `/workflows:plan` command uses research
   agents and conditional external/framework-doc research.

   **Fix requested:**
   State explicitly which behavior V1 preserves and which behavior V1 scopes
   down:
   - Does `phase-plan.md` run local-only research?
   - Does it still invoke research agents indirectly?
   - Does it intentionally skip conditional external research in autopilot?

   An implementer should not have to infer this from the source workflow.

5. **P3 -- Acceptance tests need a slightly tighter measurement story**

   The acceptance criteria and EARS tests say:
   - orchestrator peak context stays below 30k
   - full pipeline completes without hitting context limits

   Those are good outcomes, but the plan does not say what artifact or
   measurement method proves them.

   **Improvement requested:**
   Add one short note defining how context-budget success is observed during
   rollout. Keep it simple; do not add new product scope.

## What Is Already Good

- The plan does answer the main quality-gate questions overall:
  - what is changing
  - what must not change
  - how we know it worked
  - most likely way it is wrong
- The brainstorm least-confident item (Bundle 4 compound coupling) is carried
  forward into plan frontmatter and Phase 4.
- The non-interactive phase-agent direction is clear.
- The deterministic on-disk manifest direction is clear.
- The phased rollout structure is reasonable once the Bundle 4 ambiguity is removed.

## Revision Goal

After your revision, the plan should have:

1. One unambiguous V1 implementation target for Bundle 4
2. A technically correct retry/recovery model
3. One canonical manifest contract used everywhere
4. A clear statement of what `phase-plan.md` actually preserves from
   `/workflows:plan`
5. Slightly tighter verification language for the context-budget success claim

When done, the plan should be ready to commit and proceed to work.
