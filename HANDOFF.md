# HANDOFF -- Sandbox

**Date:** 2026-04-09
**Branch:** refactor/eliminate-compound-bash
**Phase:** Compound complete -- verification build pending

## Current State

Compound bash instruction refactor is code-complete and reviewed. 4 instruction
files modified (SKILL.md + 3 agents) with Bash Command Rules blocks and
prescriptive step rewrites. 0 P1, 4 P2 (all fixed), 4 P3 (accepted/deferred).
Solution doc written. The remaining gate is a full autopilot swarm build to
verify zero permission prompts at runtime.

### Build History

| # | App | Type | Agents | Files | Result |
|---|-----|------|--------|-------|--------|
| 1 | habit-tracker | solo | 1 | 1 | PASS |
| 2 | task-tracker-categories | swarm | 4 | 19 | PASS |
| 3 | bookmark-manager | swarm | 3 | 17 | PASS |
| 4 | recipe-organizer | swarm | 3 | 24 | PASS |
| 5 | finance-tracker | swarm | 3 | 23 | PASS |

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-04-09-compound-bash-refactor-brainstorm.md |
| Plan | docs/plans/2026-04-09-refactor-compound-bash-commands-plan.md |
| Solution | docs/solutions/2026-04-09-compound-bash-instruction-refactor.md |

## Deferred Items

- **Verification build:** Full autopilot swarm build to confirm zero permission
  prompts. This is the true gate -- instruction text is clean but runtime
  behavior is unverified.
- **Error injection testing:** Deliberately trigger failure paths (merge conflicts,
  smoke test failures) to verify failure-path bash commands are also clean.
- **assembly-fix.md over-delivery:** Has 5 rules (plan said 2). Accepted as
  more defensive, but plan acceptance criteria not updated.

## Three Questions

1. **Hardest decision?** Whether to keep assembly-fix.md in scope or defer it.
   Codex review pushed back on dropping it. Restored with full rules block.
2. **What was rejected?** While loops with simple bodies (heuristics flag syntax),
   external wrapper scripts (lose context), rewriting rules that don't contain
   forbidden patterns (unnecessary duplication).
3. **Least confident about?** Whether the 5 known patterns are ALL the patterns.
   curl --retry resolved retry/polling risk. Up-front audit catches instruction
   text issues. But runtime behavior could still surprise.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, a compound engineering automation lab.
Compound bash refactor is code-complete (branch: refactor/eliminate-compound-bash).
Run a full autopilot swarm build to verify zero permission prompts. If prompts
appear, catalog the new pattern and fix. Then merge to master.
```
