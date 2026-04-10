---
title: "refactor: Eliminate compound bash commands from autopilot pipeline"
type: refactor
status: implemented
date: 2026-04-09
swarm: false
origin: docs/brainstorms/2026-04-09-compound-bash-refactor-brainstorm.md
feed_forward:
  risk: "The 5 known trigger patterns may not be exhaustive -- undocumented heuristics could surface during verification build"
  verify_first: true
---

# refactor: Eliminate Compound Bash Commands from Autopilot Pipeline

## Enhancement Summary

**Deepened on:** 2026-04-09
**Sections enhanced:** 4 (Technical Approach, Risks, Smoke-Test-Runner, Step 16w)
**Research agents used:** git-C edge cases, retry patterns, architecture strategist, code simplicity reviewer

### Key Improvements
1. `curl --retry 12 --retry-delay 5 --retry-connrefused` resolves the retry/polling Feed-Forward risk as a single command
2. Compact rules format (7 lines instead of 19) -- one list, no NEVER/ALWAYS split
3. Added failure-path cleanup to Step 16w (was missing from original plan)
4. assembly-fix.md restored to scope (low-cost 2-line rules block for completeness)
5. Concrete verification method: swarm path, operator-monitored, with up-front audit
6. File-by-file sections verified against actual file contents with exact line numbers

### Research Confirmations
- `git -C` works with ALL subcommands (merge, checkout, branch -D, worktree remove, diff) -- no gotchas
- Relative paths after `-C` resolve relative to the `-C` directory, not cwd
- `curl --retry-connrefused` retries on connection refused (server not yet up) -- exactly the smoke-test use case

## Overview

Refactor the autopilot SKILL.md and 3 agents to stop generating compound bash
commands that trigger Claude Code's non-overridable security heuristics. This
is the final blocker for true zero-prompt unattended autopilot runs.

## Problem Statement / Motivation

The autopilot pipeline (5 successful builds) still requires human intervention
because Claude generates compound bash commands when interpreting high-level
instructions. These heuristics fire ABOVE `dangerouslySkipPermissions` and
cannot be disabled. The only fix is to stop generating the triggering patterns.

(see brainstorm: docs/brainstorms/2026-04-09-compound-bash-refactor-brainstorm.md)

## Proposed Solution

Two-layer defense: (1) a "Bash Command Rules" section in SKILL.md and each
Bash-enabled agent with forbidden patterns and safe replacements, plus
(2) rewritten steps with exact command syntax so Claude never needs to
improvise.

### The 5 Forbidden Patterns

| # | Pattern | Why it triggers |
|---|---------|-----------------|
| 1 | `cd /path && git ...` | Compound commands with cd |
| 2 | `for f in ...; do ... done` | Contains expansion / unhandled node |
| 3 | `python3 -c "...\n#..."` | Newline followed by # |
| 4 | `source .venv/bin/activate` | Source evaluates args as shell code |
| 5 | `echo "${var}"` | Contains brace with quote character |

### Safe Replacements

| Forbidden | Safe Alternative |
|-----------|-----------------|
| `cd /path && git merge` | `git -C /path merge` |
| `cd /path && git checkout` | `git -C /path checkout` |
| `for f in ...; do ... done` | Multiple individual Bash calls, or Glob/Read tools |
| `python3 -c "code"` | Write tool to create temp file, then `python3 /tmp/script.py` |
| `source .venv/bin/activate && pip install` | `/path/to/.venv/bin/pip install` |
| `source .venv/bin/activate && python` | `/path/to/.venv/bin/python` |
| `echo "${var}"` | Use Write tool for variable content |

## Technical Approach

### File-by-File Changes

**Format note:** SKILL.md gets a standalone H2 section (it is the orchestrator).
Agent files get a bold sub-block inside their existing `## Rules` section
(agents have a single rules section by convention). This difference is intentional.

#### 1. `.claude/skills/autopilot/SKILL.md`

**Add new section** after "## Prerequisites" (before "## Steps"):

```markdown
## Bash Command Rules (MANDATORY)

Security heuristics fire on compound commands regardless of permissions. One command per Bash call. Always.

1. `cd /path && command` -- use `git -C /path` or full paths instead
2. `for x in ...; do ... done` -- use multiple individual Bash calls or Glob tool
3. `python3 -c "code"` -- use Write tool to create .py file, then run it
4. `source .venv/bin/activate` -- use full path: `.venv/bin/pip`, `.venv/bin/python`
5. `echo "${variable}"` -- use Write tool for variable content
```

**Rewrite Step 10.5w** (Pre-Merge Ownership Gate, currently line ~215):

Change from:
> Run `git diff --name-only main...[branch]` to get the list of changed files.

To explicit sub-steps:
```markdown
For each worktree branch, run these as SEPARATE Bash calls (one per branch):
1. `git -C <project-root> diff --name-only main...<branch-name>`
2. Compare the output against the agent's assigned files using Read tool
3. If violation found, use Write tool to create the report file
```

**Rewrite Step 11w** (Assembly Merge, currently line ~239):

Change from prose describing multiple git operations to numbered sub-steps:
```markdown
1. Run: `git branch --show-current`
   Save the output as `original-branch`.
2. Run: `git checkout -b swarm-<run-id>-assembly`
3. For each worktree agent that made changes, run ONE merge at a time
   (separate Bash call for each):
   `git merge --no-ff <branch-name>`
4. If a merge fails (exit code != 0), use Write tool to save the conflict
   output to `docs/reports/<run-id>/merge-conflict.md`, then invoke the
   assembly-fix agent.
```

**Rewrite Step 15w** (Merge Assembly to Main, currently line ~286):

Change from:
```
git checkout [original-branch recorded in Step 11w]
git merge --no-ff swarm-[run-id]-assembly
```

To two explicit separate steps:
```markdown
1. Run: `git checkout <original-branch>`
2. Run: `git merge --no-ff swarm-<run-id>-assembly`
```

**Rewrite Step 16w** (Cleanup, currently line ~294):

Change from prose implying loops to explicit individual commands:
```markdown
On success (all checks passed), run each as a SEPARATE Bash call:
1. `git worktree remove <path>` (one call per worktree)
2. `git branch -D swarm-<run-id>-<role>` (one call per branch)
3. `git branch -D swarm-<run-id>-assembly`

Do NOT use a for-loop. Run each removal as its own Bash call.

On failure (unresolved issues), run each as a SEPARATE Bash call:
1. `git worktree remove <path>` (one call per worktree)
Do NOT delete branches on failure -- they are preserved for inspection.
Report which branches are kept and why.
```

#### 2. `.claude/agents/smoke-test-runner.md`

**Current file structure** (verified 2026-04-09):
- `## Rules` header at line 24
- Rule 1 at line 25: `"Install dependencies first (pip install, npm install, etc. based on the project)."`
- Rule 2 at line 26: `"Start the app in the background. Wait up to 60 seconds for it to become responsive."`
- Rule 3 at line 27: `"Hit each route from the spec's route table using curl or the appropriate tool."`
- Rule 4 at line 28: `"Check the HTTP status code against the expected value from the spec."`
- Rule 5 at line 29: `"If a route returns HTML, check for key content markers from the spec (e.g., page title, element IDs)."`
- Rule 6 at line 30: `"Always kill the app process when done, whether tests pass or fail."`
- Rule 7 at line 31: `"Do not modify any source code. This agent only reads and tests."`
- Rule 8 at line 32: `"If the app fails to start, report the error and set STATUS: FAIL immediately."`
- Rule 9 at line 33: `"If the report file already exists, overwrite it entirely."`

**Add Bash Command Rules** after `## Rules` header (line 24), before rule 1 (line 25):

```markdown
**Bash Command Rules (MANDATORY -- read before any Bash call):**
1. `cd /path && command` -- use full paths instead
2. `source .venv/bin/activate` -- use `.venv/bin/pip`, `.venv/bin/python`
3. `for x in ...; do ... done` -- use multiple individual Bash calls
4. `&&` or `;` to chain commands -- one command per Bash call. Always.
5. Retry/poll with while/until loops -- use `curl --retry` flags instead
```

**Change Rule 1** (line 25) from:
> Install dependencies first (pip install, npm install, etc. based on the project).

To:
> Install dependencies using the full venv path: `.venv/bin/pip install -r requirements.txt`. Do not use `source activate`. Do not chain with other commands.

**Change Rule 2** (line 26) from:
> Start the app in the background. Wait up to 60 seconds for it to become responsive.

To:
> Start the app with `.venv/bin/python app.py &` (or `.venv/bin/flask run &`). Then check readiness in a separate Bash call: `curl --retry 12 --retry-delay 5 --retry-connrefused -s -o /dev/null -w "%{http_code}" http://localhost:5000/`. This retries automatically for ~60 seconds with no loops.

**Rules 3-9 unchanged** -- none contain forbidden bash patterns. The Bash
Command Rules block at the top of `## Rules` handles compound command prevention.

#### 3. `.claude/agents/test-suite-runner.md`

**Current file structure** (verified 2026-04-09):
- `## Rules` header at line 22
- Rule 1 at line 24: `"Auto-detect the test framework. Check in order: pytest, unittest, jest, mocha. Use the first one found."`
- Rule 2 at line 25: `"Install test dependencies if needed (e.g., \`pip install pytest\` if not installed)."`
- Rule 3 at line 26: `"Run the full test suite. Capture all output."`
- Rule 4 at line 27: `"Do not modify any source code or test files. This agent only runs tests."`
- Rule 5 at line 28: `"If no test files exist, report that and set STATUS: PASS with a note."`
- Rule 6 at line 29: `"If tests fail, include the full failure output so the Assembly Fix Agent can diagnose."`
- Rule 7 at line 30: `"Set a timeout of 120 seconds for the test run."`
- Rule 8 at line 31: `"If the report file already exists, overwrite it entirely."`

**Add Bash Command Rules** after `## Rules` header (line 22), before rule 1 (line 24):

```markdown
**Bash Command Rules (MANDATORY -- read before any Bash call):**
1. `cd /path && command` -- use full paths instead
2. `source .venv/bin/activate` -- use `.venv/bin/pip`, `.venv/bin/python`
3. `for x in ...; do ... done` -- use multiple individual Bash calls
4. `&&` or `;` to chain commands -- one command per Bash call. Always.
```

**Change Rule 2** (line 25) from:
> Install test dependencies if needed (e.g., `pip install pytest` if not installed).

To:
> Install test dependencies using the full venv path: `.venv/bin/pip install pytest`. Do not use `source activate`. Do not chain with other commands.

**Rules 1, 3-8 unchanged** -- none contain forbidden bash patterns.

#### 4. `.claude/agents/assembly-fix.md`

This agent primarily uses Read, Grep, and Edit. Bash usage is rare (diagnostics
only), but it has the Bash tool and could generate compound commands during
merge conflict resolution. Low-cost addition for completeness.

**Add Bash Command Rules** after `## Rules` header (line 25), before rule 1 (line 26):

```markdown
**Bash Command Rules (MANDATORY -- read before any Bash call):**
1. `cd /path && command` -- use full paths or `git -C` instead
2. `&&` or `;` to chain commands -- one command per Bash call. Always.
```

**No existing rules need rewriting** -- the current 9 rules (lines 26-34)
describe read/edit workflows and do not reference any forbidden bash patterns.

## What Must NOT Change

- Pipeline flow and step ordering (Steps 1-16w sequence is correct)
- Agent behavior and output contracts (STATUS: PASS/FAIL format)
- Swarm agent spawning (isolation: "worktree", run_in_background: true)
- Non-Bash agents (brainstorm-refinement, spec-contract-checker, swarm-planner)
- Solution docs, brainstorm docs, plan docs, report templates

## Acceptance Criteria

- [x] SKILL.md has "Bash Command Rules" section after Prerequisites
- [x] Steps 10.5w, 11w, 15w, 16w rewritten with explicit single-command sub-steps
- [x] Step 16w includes both success-path AND failure-path cleanup
- [x] smoke-test-runner.md has Bash Command Rules + hardcoded venv paths
- [x] smoke-test-runner.md Rule 2 uses `curl --retry` instead of loop-based polling
- [x] test-suite-runner.md has Bash Command Rules + hardcoded venv paths
- [x] assembly-fix.md has Bash Command Rules (2-line block)
- [x] No step in any file describes a compound bash pattern (cd &&, for loop, source, python -c)
- [x] **Up-Front Audit (before verification build):** Run grep across all 4 modified files for forbidden patterns -- all matches are in rules sections (examples of what NOT to do), zero executable forbidden patterns
- [ ] Full autopilot swarm build completes with zero permission prompts (operator monitors terminal for any pause)

## Success Metrics

**Primary:** Zero permission prompts during a full autopilot build (end-to-end test).

**Secondary:** Every Bash instruction in SKILL.md and agents is a single-purpose
command -- grep for `&&`, `for `, `source `, `python3 -c` returns zero matches.

### Verification Method

**Path tested:** Swarm path (exercises Steps 10.5w-16w where most git operations
live). Swarm builds also spawn smoke-test-runner and test-suite-runner agents,
so all 4 modified files are exercised in a single run. Solo path is a subset of
swarm -- if swarm passes, solo is implicitly covered.

**How prompts are observed:** Run the autopilot build with
`dangerouslySkipPermissions: true` in `.claude/settings.local.json`. If a
security heuristic fires, Claude Code will pause and display a permission prompt
in the terminal regardless of this setting. The operator monitors the terminal
for any pause/prompt during the build. A fully unattended run that completes
without intervention = zero prompts.

**Failure paths:**
- Step 16w failure-path cleanup (worktree removal without branch deletion) is
  IN SCOPE -- the instruction rewrite covers both success and failure paths.
- Merge conflict resolution via assembly-fix agent is IN SCOPE -- the agent now
  has Bash Command Rules.
- Smoke test retry (server not yet up) is IN SCOPE -- `curl --retry` handles it.
- Deliberate error injection (forcing failures to test failure-path bash
  commands) is DEFERRED to a follow-up session. This plan verifies the
  happy-path end-to-end and the instruction text of failure paths.

**Pre-build audit step:** Before running the verification build, grep all
modified instruction files for the 5 forbidden patterns to confirm they were
eliminated. See "Up-Front Audit" in Acceptance Criteria.

## Dependencies & Risks

**Dependencies:**
1. **Verification environment:** Working sandbox repo with `dangerouslySkipPermissions: true` in `.claude/settings.local.json`
2. **Swarm infrastructure:** git worktree support, sufficient disk space for parallel worktrees (4-5 simultaneous)
3. **Python/Flask stack:** Python 3, pip, venv available at system level (for `.venv/bin/pip` paths to work)
4. **Operator availability:** One human to monitor the terminal during verification build and confirm zero prompts (cannot be fully automated -- prompts are visual)

**Risks:**
1. **Unknown heuristics (Feed-Forward risk):** The 5 patterns may not be exhaustive.
   Mitigation: document and iterate -- catalog any new patterns found during
   verification build.
2. **Overly prescriptive instructions reduce flexibility:** Hardcoding `.venv/bin/pip`
   means agents can't handle projects without venv. Acceptable for sandbox
   (single-stack) but would need revisiting for multi-stack support.
3. **Retry patterns in smoke-test-runner:** RESOLVED. Using `curl --retry 12
   --retry-delay 5 --retry-connrefused` as a single command. No loops needed.
   Confirmed: `--retry-connrefused` handles "server not yet up" case natively.

## Plan Quality Gate

1. **What exactly is changing?** 4 markdown instruction files: SKILL.md + 3 agents.
   Adding Bash Command Rules sections and rewriting steps with exact commands.
2. **What must not change?** Pipeline flow, agent output contracts, non-Bash agents,
   all docs and templates.
3. **How will we know it worked?** Full autopilot build with zero permission prompts.
   Secondary: grep for forbidden patterns returns zero matches.
4. **What is the most likely way this plan is wrong?** The 5 known patterns may not
   cover all heuristic triggers. The retry/polling risk is now mitigated by
   `curl --retry` flags, but other unknown patterns could surface.

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-04-09-compound-bash-refactor-brainstorm.md](docs/brainstorms/2026-04-09-compound-bash-refactor-brainstorm.md) -- key decisions: rules + exact commands, hardcoded Flask + venv, full build verification, document-and-iterate fallback
- **Root cause doc:** feedback_compound-bash-permissions.md -- 5 trigger patterns catalog
- **Solution doc:** docs/solutions/2026-04-09-autopilot-swarm-orchestration.md -- prescriptive specs prevent agents from reinventing unsafe patterns

## Feed-Forward

- **Hardest decision:** Whether to keep assembly-fix.md in scope or defer it.
  Codex review pushed back on dropping it -- the agent has Bash access and
  participates in failure paths. Restored it with a minimal 2-line rules block.
- **Rejected alternatives:** Allowing `while` loops with simple bodies (risky --
  heuristics may flag the loop syntax itself). Creating a retry helper script
  (loses context, same problem as external scripts). Rewriting agent rules
  that don't contain forbidden patterns (unnecessary duplication). Dropping
  assembly-fix.md entirely (Codex flagged unverified failure paths as a gap).
- **Least confident:** Whether the 5 known patterns are ALL the patterns.
  `curl --retry` resolved the retry/polling risk, and the up-front audit step
  catches any remaining forbidden patterns in instruction text. But runtime
  behavior (what Claude actually generates) could still surprise. Fallback:
  document and iterate. Deliberate error injection testing is deferred.
