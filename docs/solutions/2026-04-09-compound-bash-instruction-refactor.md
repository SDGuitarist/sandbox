---
title: "Compound Bash Instruction Refactor"
category: agent-instruction-design
tags: [bash, security-heuristics, autopilot, agent-instructions, permissions]
module: autopilot-pipeline
symptom: "Permission prompts during unattended autopilot runs despite dangerouslySkipPermissions"
root_cause: "Agent instruction files used ambiguous language that let Claude generate compound bash commands triggering non-overridable security heuristics"
date: 2026-04-09
---

# Compound Bash Instruction Refactor

## Problem

The autopilot pipeline (5 successful builds) still required human intervention
because Claude generated compound bash commands when interpreting high-level
instructions like "merge each branch" or "install dependencies." Claude Code
has a security heuristic layer that fires ABOVE `dangerouslySkipPermissions`
and cannot be disabled via allowlist or config. The only fix is to stop
generating the triggering patterns.

## Root Cause

Agent instruction files (SKILL.md and 3 agents) described operations at a
high level ("install dependencies," "merge each branch," "run the test suite")
without specifying exact command syntax. Claude interpreted these as compound
bash commands:

| Instruction | Claude generated | Heuristic triggered |
|-------------|-----------------|---------------------|
| "install dependencies" | `source .venv/bin/activate && pip install -r requirements.txt` | source evaluates args as shell code |
| "merge each branch" | `for b in branch1 branch2; do git merge $b; done` | contains expansion / unhandled node |
| "run in project dir" | `cd /path && git merge --no-ff branch` | compound commands with cd |

## Solution

Two-layer defense applied to 4 instruction files:

1. **Bash Command Rules block** -- a bullet list of 6 forbidden patterns with
   safe replacements, placed at the top of the Rules section in each file.
   Uses consistent ordering across all files: cd&&, source, for, python3-c,
   echo, chaining.

2. **Prescriptive step rewrites** -- Steps 10.5w, 11w, 15w, 16w in SKILL.md
   rewritten with exact single-command syntax and explicit "SEPARATE Bash call"
   reminders. Agent rules rewritten with hardcoded venv paths and `curl --retry`
   for polling.

### Key Patterns

| Forbidden | Safe Replacement |
|-----------|-----------------|
| `cd /path && git merge` | `git -C /path merge` |
| `source .venv/bin/activate && pip install` | `.venv/bin/pip install` |
| `for x in ...; do ... done` | Multiple individual Bash calls |
| `python3 -c "code"` | Write tool to create .py file, then run it |
| `echo "${variable}"` | Use Write tool for variable content |
| `&&` or `;` chaining | One command per Bash call |

### Retry/Polling Solution

The smoke-test-runner needed to poll for server readiness. Loop-based polling
(while/for) would trigger heuristics. Solution: `curl --retry 12 --retry-delay 5
--retry-connrefused` -- a single command that retries automatically for ~60
seconds. `--retry-connrefused` handles the "server not yet up" case natively.

## Files Changed

| File | Change |
|------|--------|
| `.claude/skills/autopilot/SKILL.md` | Added Bash Command Rules section. Rewrote Steps 10.5w, 11w, 15w, 16w with explicit single-command sub-steps. |
| `.claude/agents/smoke-test-runner.md` | Added rules block. Rewrote Rule 1 (venv path), Rule 2 (curl --retry), Rule 6 (kill PID). |
| `.claude/agents/test-suite-runner.md` | Added rules block. Rewrote Rule 2 (venv path), Rule 3 (pytest venv path). |
| `.claude/agents/assembly-fix.md` | Added rules block. No existing rules needed rewriting. |

## What We Learned

1. **Claude Code security heuristics are a separate, non-overridable layer.**
   No config option disables them. The only fix is to avoid the patterns entirely.

2. **Prescriptive instructions beat prohibitive rules.** Saying "don't use
   for-loops" is less effective than saying "run each as a SEPARATE Bash call."
   Claude follows positive instructions more reliably than negative constraints.

3. **`git -C` is universally safe.** Works with all git subcommands (merge,
   checkout, branch -D, worktree remove, diff) with no gotchas. Relative paths
   resolve relative to the -C directory, not cwd.

4. **`curl --retry-connrefused` eliminates loop-based polling.** A single
   command that handles the "server not yet up" pattern natively. Added in
   curl 7.71.0 (2020) -- available on all modern systems.

5. **Bullet lists prevent double-numbering.** When adding a rules block before
   an existing numbered list, use bullets for the rules block. Two numbered
   lists starting at 1 in the same section confuses both humans and LLMs.

6. **Consistency across files matters for maintenance.** Same rule ordering in
   all files means when a new pattern is discovered, you add it at the same
   position everywhere. Inconsistent ordering creates drift.

## Risk Resolution

**What was flagged:** "Whether the 5 known patterns are ALL the patterns. The
security heuristics are undocumented -- there may be triggers we haven't hit yet."

**What actually happened:** During the work phase, all 5 patterns were
successfully replaced with safe alternatives across all 4 files. The up-front
audit grep confirmed zero executable forbidden patterns remain in instruction
text. The `curl --retry` discovery resolved the retry/polling sub-risk that
was flagged as the Feed-Forward's "least confident" item.

**What was learned:** The instruction-text refactor is complete, but the runtime
verification (full autopilot build with zero prompts) is still pending. The
instruction text is clean -- the remaining uncertainty is whether Claude's
runtime interpretation of the rewritten instructions will stay within the safe
patterns. This is the correct point to document and iterate: run the build,
catalog any new patterns, fix in a follow-up session.

**Status:** Instruction refactor complete. Verification build deferred to
next session.

## Prevention

For future agent instruction files:
- Always include a Bash Command Rules block at the top of any agent with
  Bash tool access
- Use prescriptive "run this exact command" instructions instead of
  "do this task" descriptions
- Use bullets (not numbers) for rules blocks that precede numbered lists
- Test with a full pipeline run before declaring zero-prompt success
