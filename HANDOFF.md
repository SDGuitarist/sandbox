# HANDOFF — Sandbox

**Date:** 2026-04-08
**Branch:** master
**Phase:** Work — Phases 1-4 implemented, Phase 5 (integration) next

## Current State

Swarm-enabled autopilot is implemented. 6 agents created, skill replaces the
old static command, solo path wired, swarm path wired. Spike test confirmed
skills can spawn background agents in worktrees.

## What Was Built

### Phase 1: Foundation (DONE)
- Spike test: background agent in worktree works (PASS)
- 6 agent files created in `.claude/agents/`
- Skill created at `.claude/skills/autopilot/SKILL.md`
- Old command `.claude/commands/autopilot.md` deleted
- Commits: `dac64f9`, `039e036`

### Phase 2: Pre-build Agents (DONE)
- brainstorm-refinement and swarm-planner agents fully implemented in Phase 1

### Phase 3: Swarm Execution (DONE)
- Swarm path wired in skill: planner -> parallel worktree agents -> assembly
  merge -> circuit breaker -> smoke test -> test suite -> fix retry -> cleanup

### Phase 4: Post-build Verification Agents (DONE)
- spec-contract-checker, smoke-test-runner, test-suite-runner, assembly-fix
  agents fully implemented in Phase 1

### Phase 5: Integration (NEXT)
- End-to-end test: run `/autopilot` with a solo build
- End-to-end test: run `/autopilot` with a swarm build (`swarm: true`)
- Verify all verification agents catch and report issues

## Key Artifacts

| Artifact | Location |
|----------|----------|
| Brainstorm | docs/brainstorms/2026-04-08-swarm-autopilot-assembly-verification.md |
| Plan | docs/plans/2026-04-08-feat-swarm-autopilot-assembly-verification-plan.md |
| Skill | .claude/skills/autopilot/SKILL.md |
| Agents | .claude/agents/{brainstorm-refinement,swarm-planner,spec-contract-checker,smoke-test-runner,test-suite-runner,assembly-fix}.md |

## Design Decisions Made During Implementation

1. **No `disable-model-invocation`** on the skill. Existing skills (compound-start,
   post-phase) don't use it. Skills need Claude's interpretation for conditional
   logic and agent spawning.
2. **Bash denied in worktree agents** by default. Agents adapted using Write tool.
   For swarm agents, `mode: "bypassPermissions"` is set explicitly.
3. **Absolute paths in worktrees** write to main repo, not worktree. Swarm agents
   use relative paths and commit to their worktree branch, so this is not an issue.

## Feed-Forward Risk Resolution

**Risk:** Whether skills can spawn background agents in worktrees.
**Result:** CONFIRMED working. Spike test passed. No Python fallback needed.

## Deferred Items

- Auto-generate prescriptive spec code blocks during plan deepening
- Auto-detect swarm suitability in `/workflows:plan`
- Archive sandbox-auto (validation succeeded)
- Test agent that auto-generates tests from shared spec
- End-to-end integration testing (Phase 5)

## Feed-Forward

- **Hardest decision:** Not using `disable-model-invocation` despite the plan
  recommending it. Confirmed by existing skill patterns that this is correct.
- **Rejected alternatives:** Nothing beyond plan's rejected alternatives.
  Considered testing all 6 agents but the 3 verification agents need a real
  assembled codebase, so deferred to first real swarm run.
- **Least confident:** Whether the swarm path's sequential merge + circuit
  breaker flow handles all edge cases in practice. The brainstorm-refinement
  agent surfaced 5 gaps (data ownership checks, spec ambiguity blind spots,
  security gap pre-review, spec size limits) that may need addressing before
  a production swarm run succeeds cleanly.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, a compound engineering automation lab.
Phase: Work (Phase 5 integration testing). All agents and skill are implemented.
Run end-to-end tests: first a solo build, then a swarm build with swarm: true.
Key files: .claude/skills/autopilot/SKILL.md, .claude/agents/*.md
```
