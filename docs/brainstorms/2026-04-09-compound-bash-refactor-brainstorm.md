# Brainstorm: Compound Bash Command Refactor

**Date:** 2026-04-09
**Status:** Complete
**Related:** HANDOFF.md, feedback_compound-bash-permissions.md, docs/solutions/2026-04-09-autopilot-swarm-orchestration.md

## What We're Building

Refactor the autopilot SKILL.md and 3 agents (smoke-test-runner, test-suite-runner,
assembly-fix) to eliminate compound bash commands that trigger Claude Code's
non-overridable security heuristics. Goal: zero permission prompts during
unattended autopilot runs.

## Why This Matters

The autopilot pipeline is functionally complete (5 successful builds) but still
requires human intervention to approve bash commands that trigger security
heuristics. These heuristics fire ABOVE the permission allowlist -- they cannot
be disabled via dangerouslySkipPermissions or allowlist entries. The only fix is
to stop generating the patterns that trigger them.

## The Problem: 5 Trigger Patterns

| # | Pattern | Example | Why it triggers |
|---|---------|---------|-----------------|
| 1 | cd && command | `cd /path && git merge` | Compound commands with cd |
| 2 | for loops | `for f in ...; do ... done` | Contains expansion / unhandled node |
| 3 | python -c with newlines | `python3 -c "...\n#..."` | Newline followed by # |
| 4 | source activate | `source .venv/bin/activate` | Source evaluates args as shell code |
| 5 | echo with brace+quote | `echo "${var}"` | Contains brace with quote character |

## Files to Change

**Must change (have Bash tool access):**
- `.claude/skills/autopilot/SKILL.md` -- orchestrator, Steps 10w-16w have git ops
- `.claude/agents/smoke-test-runner.md` -- installs deps, starts app, runs curl
- `.claude/agents/test-suite-runner.md` -- installs deps, runs pytest
- `.claude/agents/assembly-fix.md` -- has Bash tool, used for diagnostics (precautionary -- confirm during planning)

**Safe (no Bash tool):**
- `.claude/agents/brainstorm-refinement.md` -- Read, Glob, Grep only
- `.claude/agents/spec-contract-checker.md` -- Read, Grep, Glob only
- `.claude/agents/swarm-planner.md` -- Read, Grep, Write only

## Why This Approach

**Chosen: Rules + Exact Commands + Hardcoded Stack**

1. Add a "Bash Command Rules" section to SKILL.md and each Bash-enabled agent
   with the 5 forbidden patterns and their safe replacements
2. Rewrite Steps 10w-16w in SKILL.md with exact command syntax (git -C, etc.)
3. Hardcode `.venv/bin/pip` and `.venv/bin/python` paths in agents (sandbox
   always uses Flask + SQLite + venv)

**Why not rules-only?** Claude might still chain commands when interpreting
ambiguous high-level instructions. Exact commands remove ambiguity.

**Why not external scripts?** Loses context visibility, harder to debug.
Rejected in HANDOFF.md Feed-Forward.

## Key Decisions

1. **Rules + exact commands** -- both layers, belt and suspenders
2. **Hardcode Flask + venv paths** -- sandbox standard, no need for stack detection
3. **Full autopilot build for verification** -- only a real end-to-end run proves zero prompts
4. **Fallback: document and iterate** -- if new heuristic patterns surface, catalog
   them and fix in follow-up sessions. Accept this may take 2-3 rounds.

## Replacement Patterns

| Trigger | Safe Replacement |
|---------|-----------------|
| `cd /path && git merge` | `git -C /path merge` (path = project root, passed as argument) |
| `cd /path && git checkout` | `git -C /path checkout` (path = project root, passed as argument) |
| `for f in ...; do ... done` | Multiple individual commands or Glob/Read tools |
| `python3 -c "code"` | Write to temp file, then `python3 /tmp/script.py` |
| `source .venv/bin/activate && pip install` | `.venv/bin/pip install` |
| `source .venv/bin/activate && python` | `.venv/bin/python` |
| `echo "${var}"` | Use Write tool (never shell echo/printf for variable content) |

## Open Questions

None -- all questions resolved in dialogue.

## Feed-Forward

- **Hardest decision:** Whether to hardcode Flask + venv paths vs. detect
  dynamically. Chose hardcoded because sandbox is single-stack and dynamic
  detection could itself generate compound commands.
- **Rejected alternatives:** Rules-only (too trusting), external scripts (loses
  context), dynamic stack detection (adds complexity, could trigger heuristics).
- **Least confident:** Whether the 5 known patterns are ALL the patterns. The
  security heuristics are undocumented -- there may be triggers we haven't hit
  yet. The fallback is to document and iterate.
