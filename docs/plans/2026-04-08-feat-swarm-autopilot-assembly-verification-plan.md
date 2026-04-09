---
title: "feat: Swarm-Enabled Autopilot with Assembly Verification"
type: feat
status: active
date: 2026-04-08
origin: docs/brainstorms/2026-04-08-swarm-autopilot-assembly-verification.md
swarm: false
feed_forward:
  risk: "Whether git worktree merges will be clean when swarm agents touch shared files. The spec assigns shared files to one agent, but accidental touches could cause merge conflicts."
  verify_first: true
---

# feat: Swarm-Enabled Autopilot with Assembly Verification

## Enhancement Summary

**Deepened on:** 2026-04-08
**Sections enhanced:** 6 (Architecture, Agent Format, Handoff Contracts, Swarm
Execution, Post-build Agents, Error Propagation)
**Research agents used:** agent-native-architecture, create-agent-skills,
orchestrating-swarms, git-worktree, architecture-strategist,
pattern-recognition-specialist, code-simplicity-reviewer, agent-native-reviewer

### Key Improvements
1. Agent system prompt 4-section structure (Role, Inputs, Rules, Output contract)
   ensures reliability and single-job focus
2. Assembly branch strategy (merge into `swarm-<run-id>-assembly`, not main)
   keeps main clean if assembly fails
3. Explicit completion signals (STATUS: PASS/FAIL) eliminate heuristic detection
4. Skill frontmatter (`disable-model-invocation`, `allowed-tools`) enables
   truly unattended runs
5. Idempotency rule for section overwrites prevents accumulation on re-runs

### New Considerations Discovered
- Smoke Test Runner and Test Suite Runner both need Write tool (were missing)
- Agent timeout row removed as YAGNI (never hit in practice)
- Worktree cleanup strategy differs on success vs failure (preserve branches
  for inspection on failure)
- Branch naming convention (`swarm-<run-id>-<agent-role>`) prevents collisions

### Simplicity Review Note
The simplicity reviewer suggested combining 3 verification agents into 1
"Verification Agent." This was **rejected** because the user explicitly decided
one agent per job during the brainstorm (Key Decision 2). The review is noted
for future reconsideration if maintenance burden proves high.

## Overview

Evolve the `/autopilot` command from a static markdown pipeline into a skill
with runtime branching that supports both solo and swarm (parallel agent) builds.
Create 6 new project-level agents, define agent-to-agent handoff contracts, and
wire everything into a single smart autopilot that runs fully unattended.

(see brainstorm: docs/brainstorms/2026-04-08-swarm-autopilot-assembly-verification.md)

## Problem Statement / Motivation

The current `/autopilot` is static markdown -- it runs the same 11-step sequence
regardless of app complexity. Swarm builds (4-6 parallel agents from a shared
spec) have been validated manually (Flask Acid Test: 4 agents, 20 files, 0
mismatches) but cannot run through autopilot because:

1. Static markdown commands cannot branch based on plan content
2. No assembly verification agents exist to check swarm output
3. No brainstorm refinement step catches gaps before planning
4. No failure recovery path exists for post-assembly issues

This means complex apps that would benefit from parallel builds still require
manual orchestration, breaking the unattended promise.

## Proposed Solution

Convert `/autopilot` from a command to a skill with conditional logic. Add 6
project-level agents. The skill reads the plan's YAML frontmatter after
deepening -- if `swarm: true`, it branches to the swarm path (parallel agents +
assembly verification). Otherwise, it follows the enhanced solo path.

Both paths gain brainstorm refinement (step 3). Only the swarm path adds steps
6-11 (swarm planning, parallel work, assembly, verification).

## Technical Approach

### Architecture

**Command format change:** Convert from `.claude/commands/autopilot.md` (static
markdown, `disable-model-invocation: true`) to a skill at
`.claude/skills/autopilot/SKILL.md`. Skills are interpreted by Claude at
runtime, allowing conditional logic (read frontmatter, branch on value). The
skill replaces the command entirely -- the old command file is deleted.

### Research Insights: Skill Frontmatter

The skill MUST include these frontmatter fields (from create-agent-skills):
- `disable-model-invocation: true` -- autopilot has heavy side effects
- `argument-hint: "[app description]"` -- autocomplete guidance
- `allowed-tools: Read, Edit, Write, Glob, Grep, Bash` -- pre-authorize for
  unattended runs so user is not prompted repeatedly

**Agent location:** All 6 agents live at project level in
`.claude/agents/` (not global `~/.claude/agents/`). This keeps
sandbox-specific agents isolated from other projects.

**Agent format:** YAML frontmatter (`name`, `description`, `tools`, `model`) +
system prompt body. Follows the same format as existing global agents (e.g.,
`~/.claude/agents/session-kickoff.md`).

### Research Insights: Agent System Prompt Structure

Each agent's system prompt MUST follow this 4-section structure (from
agent-native-architecture skill):
1. **Role** -- one sentence, one job
2. **Inputs** -- exact file paths it will receive as arguments
3. **Rules** -- hard constraints as a numbered list (the "10 strict rules"
   pattern from Flask Acid Test)
4. **Output contract** -- exact file path, exact format, explicit completion
   signal (PASS/FAIL + summary line)

Agent descriptions must include trigger conditions (from create-agent-skills),
e.g., "Use after assembly merge to verify routes match the plan's interface
spec."

### Agent-to-Agent Handoff Contracts

Every agent writes a structured report to a known location. The next agent in
the pipeline reads the previous agent's report as input.

| Agent | Output Location | Format |
|-------|----------------|--------|
| Brainstorm Refinement | Appends to brainstorm doc | Markdown section: `## Refinement Findings` |
| Swarm Planner | Appends to plan doc | Markdown section: `## Swarm Agent Assignment` + YAML table |
| Spec Contract Checker | `docs/reports/contract-check.md` | Markdown: checklist of PASS/FAIL per contract point + auto-fix log |
| Smoke Test Runner | `docs/reports/smoke-test.md` | Markdown: route-by-route results (status code, expected vs actual) |
| Assembly Fix Agent | Edits source files directly | Markdown summary appended to `docs/reports/smoke-test.md` |
| Test Suite Runner | `docs/reports/test-results.md` | Markdown: test output + pass/fail summary |

**Key principle:** Agents modify docs or source files in-place. No JSON, no
custom formats, no intermediate state files. The codebase and its docs ARE the
shared state.

**Completion signals:** Every agent MUST end its output with an explicit status
line: `STATUS: PASS` or `STATUS: FAIL — [reason]`. The skill checks this signal
to decide the next step. Do not rely on heuristic detection of agent completion
(from agent-native-architecture skill).

**Idempotency:** If an agent's target section already exists (e.g.,
`## Refinement Findings`), the agent MUST overwrite the existing section rather
than appending a duplicate. Use a grep-then-replace pattern: grep for the
section header, delete from header to next `##`, then write the new content
(from architecture-strategist review).

### Merge Conflict Strategy

Git worktrees should produce **zero merge conflicts** because the Swarm Planner
Agent assigns each file to exactly one agent. No two agents touch the same file.

**Enforcement:** The Swarm Planner Agent MUST validate that no file appears in
two agents' assignments before outputting the table. This is a hard rule in its
system prompt.

**If a merge conflict occurs anyway:** The Assembly Fix Agent handles it. Its
job expands slightly: it reads merge conflict markers AND smoke test errors.
Since merge conflicts happen at step 8 (before smoke test), the pipeline
detects them immediately via `git merge` exit code and routes to the fix agent.

**Rollback:** If the fix agent cannot resolve a merge conflict after one attempt,
the pipeline aborts the merge and reports the conflict to the review phase. The
worktree branches are preserved for manual inspection.

### Solo vs Swarm Path

```
Steps 1-5: SHARED (both paths)
  1. Ralph Loop + compound-start
  2. Brainstorm (with solution-doc-searcher)
  3. Brainstorm Refinement Agent (NEW - benefits all builds)
  4. Plan + Spec (with research agents)
  5. Deepen Plan + Quality Gate

--- BRANCH POINT: read plan frontmatter ---

If swarm: false (or missing):
  6s. /workflows:work (solo, current behavior)
  7s. /workflows:review
  8s. resolve_todo_parallel
  9s. /workflows:compound + update-learnings
  10s. DONE

If swarm: true:
  6. Swarm Planner Agent (generate assignment table)
  7. Swarm Work (N parallel agents in git worktrees)
  8. Assembly (git merge worktree branches)
  9. Spec Contract Checker (static verification, auto-fix)
  10. Smoke Test Runner (start app, hit routes)
  10a. Assembly Fix Agent (if smoke test fails, max 1 retry)
  11. Test Suite Runner (run generated tests)
  11a. Assembly Fix Agent (if tests fail, max 1 retry)
  12. /workflows:review (multi-agent)
  13. resolve_todo_parallel
  14. /workflows:compound + update-learnings
  15. DONE
```

### Smoke Test Route Knowledge

The Smoke Test Runner reads the plan's shared interface spec to know which
routes exist and what responses to expect. The spec already defines route tables
with paths, methods, and expected status codes (established in Flask Acid Test
plan). The agent greps the spec for the route table, starts the app, and hits
each route.

### Implementation Phases

#### Phase 1: Foundation (agents + skill skeleton)

Create the 6 agent files and the new skill file. Wire up the solo path first
to verify the skill format works as a drop-in replacement for the command.

**Files to create:**
- `.claude/agents/brainstorm-refinement.md`
- `.claude/agents/swarm-planner.md`
- `.claude/agents/spec-contract-checker.md`
- `.claude/agents/smoke-test-runner.md`
- `.claude/agents/test-suite-runner.md`
- `.claude/agents/assembly-fix.md`
- `.claude/skills/autopilot/SKILL.md`

**Files to delete:**
- `.claude/commands/autopilot.md` (replaced by skill)

**Success criteria:**
- [ ] `/autopilot "CLI todo app"` runs the solo path identically to before
- [ ] All 6 agent files parse correctly (valid YAML frontmatter)
- [ ] Skill reads plan frontmatter and correctly identifies `swarm: false`

#### Phase 2: Pre-build agents (brainstorm refinement + swarm planner)

Implement the two agents that run before swarm work begins.

**Brainstorm Refinement Agent:**
- Tools: Read, Glob, Grep
- Model: sonnet (research task, not creative)
- Input: path to brainstorm doc
- Job: read all solution docs in `docs/solutions/`, cross-reference against
  brainstorm, append `## Refinement Findings` section with gaps found
- Output: modified brainstorm doc with refinement section

**Swarm Planner Agent:**
- Tools: Read, Grep, Write
- Model: sonnet
- Input: path to plan doc (must contain shared interface spec)
- Job: read the plan's file list and spec, generate vertical file splits,
  validate no file appears in two agents' assignments, append
  `## Swarm Agent Assignment` section with agent table
- Output: modified plan doc with assignment table
- Hard rule: abort if any file appears in two assignments

**Success criteria:**
- [ ] Brainstorm Refinement Agent finds at least 1 gap when run against
      a brainstorm with a known omission
- [ ] Swarm Planner Agent generates a valid assignment table from the
      Flask Acid Test plan
- [ ] Swarm Planner Agent rejects a plan where `__init__.py` is assigned
      to two agents

#### Phase 3: Swarm execution (parallel agents + assembly)

Wire up the swarm work step: launch N parallel agents in git worktrees, then
merge their branches.

**Swarm work orchestration (in the skill):**
1. Read the Swarm Agent Assignment table from the plan
2. For each agent assignment, spawn an Agent with `isolation: "worktree"` and
   `run_in_background: true`
3. Each agent's prompt includes: the full shared interface spec, their specific
   file assignments, and the 10 strict rules from the Flask Acid Test pattern
   (no design decisions, exact names from spec, no cross-agent files)
4. Wait for all agents to complete
5. Create an assembly branch (`swarm-<run-id>-assembly`) -- do NOT merge
   directly into main (from git-worktree skill)
6. Merge each worktree branch sequentially into the assembly branch
7. If any merge fails (exit code != 0), route to Assembly Fix Agent
8. After all verification passes, merge assembly branch into main

### Research Insights: Worktree Conventions

- **Branch naming:** `swarm-<run-id>-<agent-role>` (e.g., `swarm-001-routes`,
  `swarm-001-models`). The `run-id` is a zero-padded counter derived from the
  number of existing `docs/solutions/` files + 1 (e.g., 20 solutions = run
  `021`). Simple, deterministic, monotonically increasing. Keeps `git branch`
  output readable, avoids collisions across runs (from git-worktree skill).
- **Assembly branch:** Always merge into a dedicated assembly branch first, not
  main. This keeps main clean if assembly fails (from git-worktree skill).
- **Cleanup:** On success, remove worktrees and delete worktree branches. On
  failure, preserve worktree branches for inspection but still remove the
  worktree directories (from git-worktree skill).

**Success criteria:**
- [ ] 2+ agents spawn in parallel worktrees successfully
- [ ] Worktree branches merge cleanly when agents respect file assignments
- [ ] Merge conflict is detected and reported when agents accidentally overlap
- [ ] Assembly branch is created and used (not merging directly into main)

#### Phase 4: Post-build verification agents

Implement the 4 post-build agents.

**Spec Contract Checker:**
- Tools: Read, Grep, Glob, Edit
- Model: sonnet
- Input: path to plan (contains spec), path to project root
- Job: for each contract point in the spec (imports, routes, CSS classes,
  function signatures, data ownership), grep the assembled code and verify
  match. Auto-fix mismatches. Write report to `docs/reports/contract-check.md`
- Pattern: follow the Flask Acid Test Checkpoint 7 approach (exact grep
  commands with PASS/FAIL)

**Smoke Test Runner:**
- Tools: Bash, Read, Grep, Write
- Model: sonnet
- Input: path to plan (contains route table), path to project root
- Job: install dependencies, start app in background, hit each route from
  the spec's route table, verify status codes and response content. Write
  report to `docs/reports/smoke-test.md`. Kill app process on completion.
- Timeout: 60 seconds for app startup, 5 seconds per route

**Test Suite Runner:**
- Tools: Bash, Read, Write
- Model: sonnet
- Input: path to project root
- Job: detect test framework (pytest, unittest), run test suite, capture
  output. Write report to `docs/reports/test-results.md`

**Assembly Fix Agent:**
- Tools: Read, Grep, Edit, Bash
- Model: sonnet
- Input: error report (merge conflict markers, smoke test failure, or test
  failure) + path to plan (contains spec)
- Job: read error, cross-reference spec, make targeted fixes to source files.
  Append fix summary to the relevant report file.
- Constraint: max 1 invocation per failure type. If fix doesn't resolve the
  issue, escalate to review phase.

**Success criteria:**
- [ ] Contract Checker catches a deliberate class name mismatch and auto-fixes
- [ ] Smoke Test Runner starts a Flask app, hits routes, reports results
- [ ] Test Suite Runner detects pytest and runs tests
- [ ] Assembly Fix Agent reads a smoke test failure and fixes a missing import

#### Phase 5: Integration (wire everything together)

Connect all phases into the skill. Test end-to-end with a real swarm build.

**Integration tasks:**
1. Wire swarm path in skill: steps 6-15
2. Add `docs/reports/` directory creation to skill
3. Add escalation logic: fix agent failure -> review phase gets error context
4. Add DONE promise output at end of both paths
5. End-to-end test: run `/autopilot "task tracker"` with a plan that has
   `swarm: true` and a shared interface spec

**Success criteria:**
- [ ] Solo build runs end-to-end through new skill (regression test)
- [ ] Swarm build runs end-to-end: brainstorm -> refine -> plan -> deepen ->
      swarm plan -> parallel work -> merge -> contract check -> smoke test ->
      test suite -> review -> compound
- [ ] At least one verification agent catches and auto-fixes an issue
- [ ] Failure recovery works: deliberate error -> fix agent -> re-test -> pass

## Alternative Approaches Considered

1. **Two separate commands** (`/autopilot` + `/swarm-autopilot`) -- rejected
   because maintenance burden doubles and intent is unclear at invocation time.
   (see brainstorm: Key Decision 4)

2. **Lean specs + verification-as-primary-defense** -- rejected because Chain
   Reaction build proved ambiguity causes bugs. Prevention > detection.
   (see brainstorm: Key Decision 3)

3. **Wrapper shell script for branching** -- rejected because it would require
   calling Claude Code CLI from bash, losing context and agent state. A skill
   keeps everything in-process.

4. **Single verification agent with multiple jobs** -- rejected per user
   feedback: one agent, one job. Agents with multiple responsibilities get off
   task. (see brainstorm: Key Decision 2)

## System-Wide Impact

### Interaction Graph

Skill invocation -> Ralph Loop -> compound-start (solution-doc-searcher +
session-kickoff agents) -> brainstorm workflow -> Brainstorm Refinement Agent ->
plan workflow -> deepen-plan -> [BRANCH] -> Swarm Planner Agent -> N parallel
Agent spawns (worktrees) -> git merge -> Spec Contract Checker -> Smoke Test
Runner -> (Assembly Fix Agent if failure) -> Test Suite Runner -> review
workflow -> resolve_todo_parallel -> compound workflow -> update-learnings.

Each arrow is a sequential dependency except the N parallel agents at swarm
work.

### Error & Failure Propagation

| Failure Point | Detection | Recovery | Escalation |
|--------------|-----------|----------|------------|
| Merge conflict (step 8) | `git merge` exit code | Assembly Fix Agent (1 try) | Abort merge, preserve branches, report to review |
| Spec mismatch (step 9) | Contract Checker grep | Auto-fix in-place | Report unfixable mismatches to review |
| App won't start (step 10) | Smoke Test Runner timeout | Assembly Fix Agent (1 try) | Report to review with error log |
| Test failure (step 11) | Test Suite Runner exit code | Assembly Fix Agent (1 try) | Report to review with test output |

### State Lifecycle Risks

- **Worktree cleanup:** If an agent fails mid-work, its worktree may contain
  partial files. On success: remove worktree directories AND delete worktree
  branches. On failure: remove worktree directories but preserve branches for
  inspection. Use `git worktree remove <path>` then `git branch -D <branch>`
  only on success (from git-worktree skill).
- **Report directory:** `docs/reports/` is created fresh each run. Stale
  reports from prior runs must not confuse current verification agents.
  Clear the directory at the start of each autopilot run.
- **Plan modification:** Brainstorm Refinement and Swarm Planner agents both
  append to existing docs. If the pipeline re-runs, these sections accumulate.
  Agents should overwrite their section if it already exists.

### API Surface Parity

The `/autopilot` invocation interface stays identical: `/autopilot "description"`.
No user-facing changes. The only difference is internal branching.

## Acceptance Criteria

### Functional Requirements

- [ ] `/autopilot "simple app"` runs the enhanced solo path (with brainstorm
      refinement) and produces the same outputs as before
- [ ] `/autopilot "complex app"` with a plan that sets `swarm: true` runs the
      full swarm path end-to-end
- [ ] 6 agent files exist in `.claude/agents/` with valid frontmatter
- [ ] Skill file exists at `.claude/skills/autopilot/SKILL.md`
- [ ] Old command file `.claude/commands/autopilot.md` is removed
- [ ] Each agent produces output in its defined format and location
- [ ] Swarm Planner rejects plans with duplicate file assignments
- [ ] Assembly Fix Agent gets max 1 retry per failure type
- [ ] All verification reports are written to `docs/reports/`

### Non-Functional Requirements

- [ ] No agent has more than one primary job
- [ ] Agent system prompts are under 200 lines each
- [ ] Skill file is under 300 lines
- [ ] Solo path adds < 2 minutes overhead vs current autopilot (brainstorm
      refinement step)

### Quality Gates

- [ ] Plan Quality Gate passes (4 questions answered below)
- [ ] Feed-Forward risk (worktree merges) is verified in Phase 3
- [ ] End-to-end test in Phase 5 covers both paths

## Plan Quality Gate

1. **What exactly is changing?** The `/autopilot` command becomes a skill with
   conditional logic. 6 new agents are created. The pipeline gains brainstorm
   refinement, swarm planning, assembly verification, smoke testing, test
   running, and assembly fixing. Both solo and swarm paths are enhanced.

2. **What must not change?** Solo build output quality. The compound engineering
   phase loop (brainstorm -> plan -> work -> review -> compound). Existing
   solution docs, brainstorms, and plans. The user invocation interface
   (`/autopilot "description"`).

3. **How will we know it worked?** Run a swarm build through the new autopilot
   and get 0 mismatches with all verification agents reporting clean. Run a
   solo build and verify it produces identical outputs to the current autopilot.

4. **Most likely way this plan is wrong?** The skill format may not support
   the level of orchestration needed (spawning background agents, waiting for
   completion, reading their output, branching on results). If skills are too
   constrained, we may need a Python orchestration script instead.

## Dependencies & Prerequisites

- Git worktree support in Claude Code (`isolation: "worktree"` on Agent tool)
- `run_in_background: true` on Agent tool for parallel spawning
- `docs/reports/` directory (created by skill at runtime)
- Existing solution docs in `docs/solutions/` (for brainstorm refinement)
- A plan with `swarm: true` and a shared interface spec (for end-to-end test)

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Skill format can't orchestrate agents | Medium | High | Fallback: Python script wrapping Claude Code CLI |
| Worktree merges produce conflicts | Low | Medium | Swarm Planner validates no file overlap; Fix Agent handles conflicts |
| Agents drift from single-job focus | Medium | Medium | Keep system prompts short (<200 lines), strict rules |
| Verification agents miss real issues | Low | Low | Belt + suspenders: spec prevention + verification detection + review |
| Stale reports confuse agents | Low | Medium | Clear `docs/reports/` at start of each run |

## Future Considerations

- Auto-generate prescriptive spec code blocks during plan deepening (out of
  scope, see brainstorm Key Decision 9)
- Auto-detect swarm suitability in `/workflows:plan` (currently manual
  `swarm: true` in frontmatter)
- Agent timeout/resource limits for stuck parallel agents
- Metrics collection: time per phase, mismatch rate, fix success rate

## Documentation Plan

- Update HANDOFF.md after implementation
- Solution doc in `docs/solutions/` capturing what was learned
- Update project memory with new agent inventory

## Sources & References

### Origin

- **Brainstorm document:**
  [docs/brainstorms/2026-04-08-swarm-autopilot-assembly-verification.md](docs/brainstorms/2026-04-08-swarm-autopilot-assembly-verification.md)
  Key decisions carried forward: one agent one job, git worktrees for isolation,
  prescriptive specs stay, plan marks swarm in frontmatter

### Internal References

- Flask Acid Test plan (swarm pattern):
  `docs/plans/2026-04-07-feat-flask-swarm-acid-test-plan.md`
- Flask Acid Test solution:
  `docs/solutions/2026-04-07-flask-swarm-acid-test.md`
- Swarm alignment solution:
  `docs/solutions/2026-03-30-swarm-build-alignment.md`
- Swarm scale solution:
  `docs/solutions/2026-03-30-swarm-scale-shared-spec.md`
- Chain Reaction solution:
  `docs/solutions/2026-03-30-chain-reaction-inter-service-contracts.md`
- Current autopilot command:
  `.claude/commands/autopilot.md`
- Agent format example:
  `~/.claude/agents/session-kickoff.md`

## Feed-Forward

- **Hardest decision:** Whether skills can orchestrate the level of agent
  spawning, waiting, and branching this pipeline requires. Chose skills over
  Python scripts because they stay in-process and maintain Claude's context.
  If this assumption is wrong, fallback to a Python orchestration wrapper.
- **Rejected alternatives:** Wrapper shell script (loses context), two separate
  commands (maintenance burden), single verification agent (gets off task).
- **Least confident:** Whether the skill format supports spawning background
  agents, waiting for all to complete, then reading their output files to
  decide the next step. This is the first thing to verify in Phase 1.
