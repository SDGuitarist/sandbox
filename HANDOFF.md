# HANDOFF -- Sandbox

**Date:** 2026-04-09
**Branch:** master
**Phase:** Ready for next cycle

## Current State

5 successful autopilot builds completed (1 solo, 4 swarm). Pipeline is
functionally complete. The remaining blocker for true zero-prompt automation
is compound bash commands triggering Claude Code security heuristics.

### Build History

| # | App | Type | Agents | Files | Result |
|---|-----|------|--------|-------|--------|
| 1 | habit-tracker | solo | 1 | 1 | PASS |
| 2 | task-tracker-categories | swarm | 4 | 19 | PASS |
| 3 | bookmark-manager | swarm | 3 | 17 | PASS |
| 4 | recipe-organizer | swarm | 3 | 24 | PASS |
| 5 | finance-tracker | swarm | 3 | 23 | PASS |

### Pipeline Components

| Component | Location | Status |
|-----------|----------|--------|
| Autopilot skill | .claude/skills/autopilot/SKILL.md | Working (with prompts) |
| Resolve-todos skill | .claude/skills/resolve-todos/SKILL.md | Working |
| 6 agents | .claude/agents/*.md | Working |
| Flask spec template | docs/templates/shared-spec-flask.md | Working |
| Solution docs | docs/solutions/ (25 total) | Growing |

### Remaining Blocker: Compound Bash Permissions

Claude Code security heuristics fire on compound bash commands regardless
of allowlist or dangerouslySkipPermissions. Patterns that prompt:
- `cd /path && git ...`
- `for f in ...; do ... done`
- `python3 -c "...\n#..."` 
- `source .venv/bin/activate`

Fix: refactor skill + agents to use simple single-purpose commands.
See feedback_compound-bash-permissions.md and solution doc Bug 2.

## Recommended Next Session

Refactor the autopilot skill and agents to eliminate compound bash commands.
This is the final blocker for true zero-prompt unattended automation.

### Approach
1. Brainstorm: catalog every compound bash pattern in SKILL.md and agents
2. Plan: map each pattern to a simple alternative (git -C, temp files, full paths)
3. Work: refactor, test with a fresh build
4. Verify: count permission prompts -- target is zero

### Alternatives (if not doing the refactor)
- Node/Express swarm build (stack-agnostic test)
- 5-agent Flask app (scale test)

## Key Artifacts

| Artifact | Location |
|----------|----------|
| Autopilot solution doc | docs/solutions/2026-04-09-autopilot-swarm-orchestration.md |
| Compound bash finding | ~/.claude/projects/.../memory/feedback_compound-bash-permissions.md |
| Build reports | docs/reports/{024,025,026}/ |

## Feed-Forward

- **Hardest decision:** Whether to keep building apps or fix the permission
  blocker. Chose to document the root cause first, fix next session.
- **Rejected alternatives:** Wrapping everything in a shell script (loses
  context), accepting prompts as permanent (breaks the promise).
- **Least confident:** Whether simple command refactoring will fully eliminate
  prompts, or if there are deeper heuristics we haven't hit yet.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, a compound engineering automation lab.
5 successful autopilot builds done. The remaining blocker for zero-prompt automation
is compound bash commands triggering Claude Code security heuristics. Refactor
SKILL.md and agents to use simple single-purpose commands (git -C instead of
cd && git, temp files instead of python -c, full paths instead of source activate).
Key files: .claude/skills/autopilot/SKILL.md, .claude/agents/*.md
See: feedback_compound-bash-permissions.md for the full pattern catalog.
```
