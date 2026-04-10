# HANDOFF -- Sandbox

**Date:** 2026-04-09
**Branch:** master
**Phase:** Milestone complete -- fully unattended swarm automation achieved

## Current State

Zero-prompt swarm automation achieved. Build #6 (contact-book) ran the full
autopilot pipeline -- brainstorm through compound -- without a single
permission prompt. The three-layer fix (Bash Command Rules + git -C allowlist +
prescriptive step rewrites) is verified and merged to master.

### Build History

| # | App | Type | Agents | Files | Prompts | Result |
|---|-----|------|--------|-------|---------|--------|
| 1 | habit-tracker | solo | 1 | 1 | ~0 | PASS |
| 2 | task-tracker-categories | swarm | 4 | 19 | ~8 | PASS |
| 3 | bookmark-manager | swarm | 3 | 17 | ~6 | PASS |
| 4 | recipe-organizer | swarm | 3 | 24 | ~12 | PASS |
| 5 | finance-tracker | swarm | 3 | 23 | ~8 | PASS |
| 6 | contact-book | swarm | 3 | 11 | **0** | PASS |

### Pipeline Components

| Component | Location | Status |
|-----------|----------|--------|
| Autopilot skill | .claude/skills/autopilot/SKILL.md | Zero-prompt verified |
| Resolve-todos skill | .claude/skills/resolve-todos/SKILL.md | Working |
| 6 agents | .claude/agents/*.md | Zero-prompt verified |
| Flask spec template | docs/templates/shared-spec-flask.md | Working |
| Solution docs | docs/solutions/ (27 total) | Growing |

### What Made Zero-Prompt Work (three layers, all required)

1. **Bash Command Rules** in SKILL.md + 3 agent files -- instruct Claude
   to use one command per Bash call, `git -C` instead of `cd &&`, full
   venv paths, Write tool for scripts
2. **`Bash(git -C *)` in global allowlist** -- covers all `git -C <path>`
   commands that the rules generate
3. **Prescriptive step rewrites** -- exact command syntax in Steps 10.5w
   through 16w eliminates interpretation

## Key Artifacts

| Artifact | Location |
|----------|----------|
| Autopilot solution doc | docs/solutions/2026-04-09-autopilot-swarm-orchestration.md |
| Compound bash refactor solution | docs/solutions/2026-04-09-compound-bash-instruction-refactor.md |
| Build reports | docs/reports/{024,025,026,028}/ |
| Flask spec template | docs/templates/shared-spec-flask.md |

## Deferred Items

- Node/Express swarm build (stack-agnostic test)
- 5+ agent swarm build (scale test)
- Error injection testing (deliberate merge conflicts, smoke test failures)
- Auto-detect swarm suitability in `/workflows:plan`
- Test agent that auto-generates tests from shared spec
- Archive sandbox-auto

## Feed-Forward

- **Hardest decision:** Whether to keep iterating on permissions or accept
  ~5 prompts as the floor. Kept iterating -- `Bash(git -C *)` was the
  final piece that achieved zero.
- **Rejected alternatives:** External shell scripts (lose context), while
  loops (heuristics flag syntax), single dangerouslySkipPermissions
  (insufficient alone).
- **Least confident:** Whether zero-prompt holds across different app
  complexities and agent counts. Verified with 3-agent swarm; untested
  with 5+ agents or non-Flask stacks.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, a compound engineering automation lab.
Zero-prompt swarm automation achieved (6 builds, milestone on build #6).
Pick next: (A) Node/Express swarm build to test stack-agnostic claim,
(B) 5-agent Flask swarm to test scale, or (C) new feature/experiment.
Key files: .claude/skills/autopilot/SKILL.md, .claude/agents/*.md
```
