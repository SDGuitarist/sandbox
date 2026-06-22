# Claude Code Handoff — G1 Firebreak Plan GO/NO-GO

**Date:** 2026-06-21  
**Phase:** Plan Review (post-deepening, pre-work)  
**Repo:** `~/Projects/sandbox`  
**Plan:** `docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md`  
**Reviewer:** Codex  
**Verdict:** `NO-GO`

## Summary

The plan is close, but it is not implementation-ready yet.

I verified the revised v1 against the live source:

- `.claude/skills/autopilot/SKILL.md`
- `.claude/agents/swarm-runner.md`
- `.claude/agents/tail-runner.md`
- `.claude/agents/deepen-merge-runner.md`
- `CLAUDE.md`

I did **not** find a hidden shared-remote push inside the claimed worker window.
The remaining blockers are plan-honesty / cross-section-consistency issues.

## Blocking Findings

### P0 — F10 active-window contradiction

The plan still defines the firebreak boundary two different ways.

- The Threat Model, Plan Quality Gate, and hook/sentinel section say the active
  window is `worker-spawn -> run-end`, with the sentinel written after the
  provenance gate and before worker spawn.
- But the Architecture component map marks the firebreak active window as
  beginning before sentinel write and before the positive-control probe.

That is a cross-section contradiction on the plan's core safety boundary.

**Exact fix required:**

Make one definition win everywhere.

- Either move the component-map "active window begins" marker to `worker spawn`
- Or rename the pre-spawn segment so it is clearly a setup/probe interval where
  the hook is live for validation but still outside the governed worker window

**Sections to change:**

- `Threat Model` / `F10`
- `Architecture (v1) -> Component map`
- `The hook + sentinel`
- `Q2`

### P0 — `resolve-todos` guard still overclaims F1 protection

The `resolve-todos` guard section still says:

> "With F1 also blocking subagent writes to the dir..."

That is no longer honest under the revised threat model.

- `F5` explicitly allows trusted subagents (`swarm-runner`, `tail-runner`)
- `F6/F11` explicitly declare that an allowlisted interpreter can still
  overwrite `todos/approvals/` in-process

So "blocking subagent writes" is still too absolute.

**Exact fix required:**

Rewrite that line so it says F1 blocks **worker direct tool-call writes** to the
directory, and point back to the declared interpreter residual instead of
claiming blanket subagent-write protection.

**Sections to change:**

- `resolve-todos` guard
- Any nearby queue-protection wording that still says "subagent writes" or
  otherwise overclaims beyond direct worker tool calls

## Non-Blocking Polish

### P1 — Shared-`master` wording is still loose

`System-Wide Impact & Edge Cases` says:

> "Shared-`master` merge target: deferred like any other RED action"

That is sloppy next to the F5/Q2 rule:

- local `git merge --no-ff` onto `master` is GREEN
- only shared-remote `git push` / force-push is RED

**Fix requested:**

Replace "shared-`master` merge target" with explicit "shared-remote push to
`master`" wording.

## Checks That Held

- The provenance push is real, but pre-spawn, and I did not find another
  shared-remote push inside `worker-spawn -> run-end`.
- I did not find a third undeclared **direct-call** escape beyond the two named
  residuals.
- The trusted-identity model is acceptably honest as a harness-contract
  assumption, and the blanket-deny fallback's sentinel-removal invariant is
  sound as written.

## Claude Code Fix Prompt

```text
Read docs/plans/2026-06-21-feat-g1-risk-tiered-firebreak-plan.md

Apply these plan fixes:

1. Fix the F10 boundary contradiction.
   The plan still defines the firebreak active window two different ways.
   Threat Model / Plan Quality Gate / hook+sentinel say the active window is
   worker-spawn -> run-end, with the sentinel written after the provenance gate
   and before worker spawn. But the Architecture component map shows the
   firebreak active window beginning earlier, before sentinel write and before
   the positive-control probe.

   Make one definition win everywhere.
   Either:
   - move the component-map "active window begins" marker to worker spawn, or
   - rename the pre-spawn region so it is clearly a setup/probe interval where
     the hook is live for validation but still outside the governed worker window.

   Update all dependent wording so F10 is internally consistent across:
   - Threat Model
   - Plan Quality Gate
   - Architecture component map
   - The hook + sentinel
   - Q2

2. Fix the remaining F1/F5/F6/F11 overclaim in the resolve-todos guard section.
   The plan still says "With F1 also blocking subagent writes to the dir..."
   That is not honest anymore:
   - F5 allows trusted subagents
   - F6/F11 declare that an allowlisted interpreter can still overwrite
     todos/approvals/ in-process

   Rewrite that line so it says F1 blocks worker direct tool-call writes to the
   dir, and explicitly point back to the declared interpreter residual instead of
   claiming blanket subagent-write protection.

3. Tighten the F5 wording in System-Wide Impact.
   "Shared-master merge target: deferred like any other RED action" is too loose.
   Local git merge --no-ff onto master is GREEN; only shared-remote git push /
   force-push is RED. Rewrite that line to say exactly that.

4. Re-run the whole v1 body for consistency after those edits.
   Check:
   - Threat Model
   - Plan Quality Gate
   - Architecture component map
   - approvals queue
   - resolve-todos guard
   - hook + sentinel ordering
   - Q1 / Q2
   - System-Wide Impact & Edge Cases
   - Acceptance Tests
   - Dependencies & Risks

   The result should make no claim stronger than:
   - direct worker tool-call protection, with the two declared residuals
   - provenance push exists, is pre-spawn, and is scoped out by ordering

Then do a second review of your own revised plan and report any remaining risks
before considering Plan Review complete.
```
