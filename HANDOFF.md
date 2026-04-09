# HANDOFF — Sandbox

**Date:** 2026-04-08
**Branch:** master
**Phase:** Work — ready to implement swarm-enabled autopilot

## Current State

Brainstorm and deepened plan complete for swarm-enabled autopilot with assembly
verification. 8 research/review agents ran during deepening. Plan scored 9/10
across all criteria. Ready for implementation.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-04-08-swarm-autopilot-assembly-verification.md |
| Plan | docs/plans/2026-04-08-feat-swarm-autopilot-assembly-verification-plan.md |

## What to Build

6 new project-level agents + 1 new skill, replacing the static `/autopilot`
command. See plan for full details.

### Files to Create
- `.claude/agents/brainstorm-refinement.md`
- `.claude/agents/swarm-planner.md`
- `.claude/agents/spec-contract-checker.md`
- `.claude/agents/smoke-test-runner.md`
- `.claude/agents/test-suite-runner.md`
- `.claude/agents/assembly-fix.md`
- `.claude/skills/autopilot/SKILL.md`

### Files to Delete
- `.claude/commands/autopilot.md` (replaced by skill)

### 5 Implementation Phases
1. Foundation (agents + skill skeleton, solo path first)
2. Pre-build agents (brainstorm refinement + swarm planner)
3. Swarm execution (parallel agents + git worktree assembly)
4. Post-build verification agents (contract checker, smoke test, test suite, fix)
5. Integration (wire everything, end-to-end test)

## Feed-Forward Risk

**From plan:** Whether the skill format supports spawning background agents,
waiting for all to complete, then reading their output to branch. This is the
first thing to verify in Phase 1.

**Recommended:** Start Phase 1 with a worktree spike test — spawn one background
agent in a worktree, wait, read output — before creating any agent files.
Hard-gate Phase 2 on this.

**Also:** Add a circuit breaker after step 9 (Spec Contract Checker) — if
unfixable mismatches exist, abort before smoke testing.

## Deferred Items

- Auto-generate prescriptive spec code blocks during plan deepening
- Auto-detect swarm suitability in `/workflows:plan`
- Archive sandbox-auto (validation succeeded — ready)
- Test agent that auto-generates tests from shared spec

## Three Questions

1. **Hardest decision:** Whether skills can orchestrate background agents with
   worktrees and branching. Chose skills over Python scripts to stay in-process.
2. **What was rejected:** Combining verification agents into one (user wants one
   agent per job). Lean specs (prevention > detection). Two separate commands.
3. **Least confident about:** Skill orchestration — can a SKILL.md spawn
   background agents, wait, read output, and branch? First spike test in Phase 1.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, a compound engineering automation lab.
Phase: Work. Plan is at docs/plans/2026-04-08-feat-swarm-autopilot-assembly-verification-plan.md.
Start with Phase 1: worktree spike test first (verify skill can spawn background
agents), then create 6 agent files + 1 skill file. Wire solo path first.
Key files: .claude/commands/autopilot.md (current, to be replaced),
~/.claude/agents/session-kickoff.md (agent format reference).
```
