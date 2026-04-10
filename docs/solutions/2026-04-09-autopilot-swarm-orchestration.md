---
title: "Swarm-Enabled Autopilot Skill with Assembly Verification"
date: 2026-04-09
status: solved
category: automation
tags:
  - swarm
  - autopilot
  - parallel-agents
  - compound-engineering
  - assembly-verification
  - shared-interface-spec
modules:
  - .claude/skills/autopilot/SKILL.md
  - .claude/agents/brainstorm-refinement.md
  - .claude/agents/swarm-planner.md
  - .claude/agents/spec-contract-checker.md
  - .claude/agents/smoke-test-runner.md
  - .claude/agents/test-suite-runner.md
  - .claude/agents/assembly-fix.md
  - habit-tracker/habit_tracker.py
  - task-tracker-categories/
severity: medium
root_cause: "Static markdown autopilot command lacked runtime branching and had no mechanism for parallel agent coordination or post-assembly verification"
origin_plan: docs/plans/2026-04-08-feat-swarm-autopilot-assembly-verification-plan.md
origin_brainstorm: docs/brainstorms/2026-04-08-swarm-autopilot-assembly-verification.md
key_lesson: "4 agents can build 19 files in parallel with zero merge conflicts when given a shared interface spec, but scalar return types must include usage examples to prevent post-assembly mismatches"
feed_forward_risk: "Git permission prompts in main session break unattended execution; spec ambiguity on scalar returns causes post-assembly mismatches"
feed_forward_resolution: "Git prompts confirmed as blocker for true unattended mode (needs permission pre-grant or assembly-merge agent); scalar return ambiguity caused exactly 1 fix, validating that specs need usage-level precision not just type-level"
---

# Swarm-Enabled Autopilot Skill with Assembly Verification

## Problem Statement

The sandbox autopilot command was a static markdown file that always ran a
single-agent sequential build. It could not inspect a plan's metadata to
decide whether to run one agent or many in parallel. There was no assembly
verification pipeline for multi-agent output, no brainstorm refinement step
to catch gaps before planning, and no failure recovery when post-assembly
issues arose.

## Root Cause Analysis

- **Static command limitation:** Markdown-based commands execute linearly.
  They cannot read YAML frontmatter from a plan doc and branch behavior at
  runtime. A skill (with embedded logic and conditional steps) was needed.
- **No assembly verification:** When multiple agents write code in parallel
  git worktrees, there is no guarantee their outputs compose correctly.
  Without a verification pipeline, broken assemblies would silently land.
- **No brainstorm refinement:** The original flow went straight from
  brainstorm to plan. Gaps in the brainstorm survived into plans and then
  into implementation.
- **No failure recovery:** If assembled code failed tests, the process
  stopped. There was no retry mechanism or dedicated fix agent.

## Solution

### Architecture

The autopilot skill reads the plan's YAML frontmatter for a `swarm: true/false`
flag and branches into one of two paths:

- **Solo path:** Sequential single-agent build (brainstorm, plan, work,
  review, compound).
- **Swarm path:** Parallel multi-agent build in git worktrees, followed by
  assembly and a verification pipeline.

### Swarm Pipeline Stages

1. **Brainstorm Refiner Agent** -- cross-references brainstorm against all
   solution docs, finds gaps.
2. **Swarm Planner Agent** -- reads the plan's shared interface spec,
   generates per-agent file assignments, validates no file overlap.
3. **N Worker Agents** -- each spawned in its own git worktree with
   `mode: "bypassPermissions"`, scoped to specific files via the spec.
4. **Pre-Merge Ownership Gate** -- runs `git diff --name-only` against each
   agent's declared file list to verify no cross-agent contamination.
5. **Assembly Merge** -- worker branches merge sequentially into
   `swarm-<run-id>-assembly` (never into main directly).
6. **Verification Pipeline** -- four sequential checks:
   - Spec Contract Check (grep for exact names, auto-fix mismatches)
   - Smoke Test (start app, hit routes, verify status codes)
   - Test Suite (run full test suite)
   - Assembly Fix Agent (1 retry per failure type, then escalate)
7. **Merge to Main** -- assembly branch merges into main only after all
   verification passes.

### File-Based Contracts

Every agent writes a structured report with an explicit `STATUS: PASS/FAIL`
signal. The skill reads these signals to decide the next step. Agents
communicate through the filesystem, not through function calls or shared
memory. This is the simplest cross-process communication that works with
the agent spawning model.

### Agent Inventory

| Agent | Job | Tools | Output |
|-------|-----|-------|--------|
| brainstorm-refinement | Cross-reference brainstorm against solution docs | Read, Glob, Grep | Appends `## Refinement Findings` |
| swarm-planner | Generate file-to-agent assignments | Read, Grep, Write | Appends `## Swarm Agent Assignment` |
| spec-contract-checker | Verify code matches spec, auto-fix | Read, Grep, Glob, Edit | `docs/reports/contract-check.md` |
| smoke-test-runner | Start app, hit routes | Bash, Read, Grep, Write | `docs/reports/smoke-test.md` |
| test-suite-runner | Detect framework, run tests | Bash, Read, Write | `docs/reports/test-results.md` |
| assembly-fix | Read error report, make targeted fixes | Read, Grep, Edit, Bash | Appends `## Fix Attempt` |

## Key Decisions

1. **Skill over command** -- A skill can contain conditional logic and read
   plan metadata. A markdown command cannot. Minimum viable change for
   runtime branching.
2. **YAML frontmatter as branch signal** -- `swarm: true/false` in the plan
   keeps the decision co-located with plan content. No separate config.
3. **Assembly branch isolation** -- Merging into `swarm-<run-id>-assembly`
   instead of main means a failed assembly never pollutes main. Disposable.
4. **Pre-merge ownership gate** -- Simple `git diff --name-only` check. If
   an agent touched a file outside its contract, the diff reveals it before
   merge.
5. **One retry via fix agent** -- Unlimited retries risk infinite loops.
   Zero retries mean any small issue kills the run. One retry balances
   reliability and safety.
6. **One agent, one job** -- Brainstorm explicitly rejected combining
   verification agents. Each agent has clear trigger, input, and output
   contracts. Debuggable.

## Results

| Metric | Solo Path (habit-tracker) | Swarm Path (task-tracker) |
|--------|--------------------------|--------------------------|
| Agents | 1 | 4 parallel + 2 pipeline |
| Files produced | 1 (201 LOC) | 19 files |
| Merge conflicts | N/A | 0 |
| Post-assembly fixes | 1 (date dedup) | 1 (scalar return type) |
| Verification agents | N/A | 3 ran (contract, smoke, test suite) |
| End-to-end | PASS | PASS |

## Bugs Encountered

### Bug 1: `create_project()` Returns int, Not Row

- **Symptom:** Agent 2 wrote `project = create_project(...)` then accessed
  `project.id`. Runtime error: `int` has no attribute `id`.
- **Root cause:** Spec said "returns int" but had no usage example showing
  the return value is a plain integer (the project ID), not a Row object.
- **Fix:** Rename variable to `project_id = create_project(...)` and use
  `project_id` directly. 1-line change, caught by smoke test.
- **Lesson:** Shared specs must include usage examples for every function
  that returns a scalar. The type alone is not enough.

### Bug 2: Git Permission Prompts in Main Session

- **Symptom:** Git commands (checkout, merge, branch -D) in the main session
  triggered interactive permission prompts, blocking automation.
- **Root cause (initial):** Permissions are split between agent spawn level
  (bypassed via `mode: "bypassPermissions"`) and main session level (restricted).
- **Fix attempt 1:** Added git checkout, branch -D/-d, rm, sed to global
  allowlist. Did not fully resolve.
- **Fix attempt 2:** Fixed `allowed-tools` YAML syntax (commas -> spaces).
  Skill now registers properly. Did not fully resolve.
- **Root cause (final, 2026-04-09):** Claude Code has **security heuristics**
  that fire ABOVE the permission allowlist. Compound bash commands trigger
  them regardless of allowlist or dangerouslySkipPermissions:
  - `cd /path && git ...` -- "Compound commands with cd and git"
  - `for f in ...; do ... done` -- "Contains expansion"
  - `python3 -c "...\n#..."` -- "Newline followed by #"
  - `source .venv/bin/activate` -- "'source' evaluates arguments"
  - `echo "${var}"` -- "Contains brace with quote character"
- **Fix attempt 3 (2026-04-09):** Added "Bash Command Rules" blocks to
  SKILL.md and 3 agent files. Rules: one command per Bash call, `git -C`
  instead of `cd &&`, full venv paths, Write tool for scripts.
- **Result of fix 3:** Agents achieved ZERO prompts (rules fully effective
  in separate agent contexts). Orchestrator still ~5 prompts per run.
- **Root cause (refined):** Bash Command Rules work for agents because each
  agent gets a fresh context where the rules are prominent. The orchestrator
  runs in the main session where the rules are one section in a long skill
  file and Claude sometimes reverts to natural patterns (heredocs, `cd &&`)
  under context pressure. Additionally, `git -C <path>` commands don't
  match allowlist patterns like `Bash(git diff*)` because `-C` changes
  the prefix.
- **Current state:** ~5 orchestrator prompts per swarm run is the floor
  with instruction-based mitigation. Further reduction requires either
  adding `-C` patterns to the allowlist (`Bash(git -C *)`) or a Claude Code
  "trust this skill" mechanism.
- **Lesson:** Instruction-based rules are effective for agents (isolated
  context, fresh prompt) but only partially effective for orchestrators
  (long context, competing patterns). The permission system has three
  layers: allowlist (prefix matching), dangerouslySkipPermissions
  (project-level override), and security heuristics (non-overridable,
  pattern-based). True zero-prompt requires satisfying all three.

## Risk Resolution

**Feed-Forward risk from brainstorm:** "Whether git worktree merges will be
clean when swarm agents touch shared files."

**What actually happened:** Zero merge conflicts. The Swarm Planner Agent's
exclusive file assignment worked perfectly. The pre-merge ownership gate
confirmed all 4 agents stayed in scope. The risk was mitigated by design.

**Feed-Forward risk from plan:** "Whether the skill format supports spawning
background agents, waiting for all to complete, then reading their output."

**What actually happened:** Skills fully support this pattern. The Claude
Code Agent tool with `isolation: "worktree"` and `run_in_background: true`
worked exactly as designed. The real blocker was the permission model, not
the skill format.

**Unexpected risk:** The permission split between agent spawn level and main
session level was not anticipated in the plan. Git operations in the
orchestrator are a different permission domain than git operations inside
spawned agents.

**Deeper unexpected risk (discovered across 5 builds):** Even after fixing
the allowlist and skill registration, compound bash commands still trigger
security heuristics. This is a non-overridable layer in Claude Code. The
only fix is to avoid compound command patterns entirely -- use `git -C`
instead of `cd && git`, write scripts to files instead of inline, use
full paths instead of `source activate`. This is the final blocker for
true zero-prompt automation.

## Prevention Strategies

### 1. Spec Return Type Contracts with Usage Examples

Add a mandatory `usage_example` field to every function in the spec template.
Format: `returns: int  # usage: project_id = create_project("name")`. Add
to plan quality gate as question 5: "Does every function spec include a
usage example?"

### 2. Permission Preflight Check

Before the skill runs, attempt a dry-run of each required git operation. If
any would prompt, fail fast with: "Permission not pre-approved for `git
branch -D`. Add to allowlist before running unattended."

### 3. Verification Report Persistence

Write reports to `docs/reports/<run-id>/` instead of clearing `docs/reports/`
each run. Preserves audit trail across runs.

### 4. Flask Spec Template Hardening

Add mandatory sections to Flask spec template:
- CSRF setup (flask-wtf, CSRFProtect, tokens in forms)
- Secret handling (`os.environ.get('SECRET_KEY', 'dev-fallback')`)
- Input validation rules inline with route specs
- Color/hex validation regex

### 5. Shared Tail Extraction

When a skill has parallel execution paths, extract common tail logic into a
named section. Prevents maintenance traps from copy-paste duplication.

## Review Findings Summary

7-agent review found 4 P1, 6 P2, 4 P3:

| Priority | Count | Key Issues |
|----------|-------|------------|
| P1 | 4 | Git permissions, reports not persisted, no CSRF, spec template gap |
| P2 | 6 | Duplicated tail, contract checker blind spot, CSS injection, WAL pragma, dead code, hardcoded secret |
| P3 | 4 | Brainstorm agent can't fail, no swarm timeout, dead CSS, missing FK indexes |

Todos created in `todos/` directory for all 14 findings.

## Related Solutions

| Doc | Relevance |
|-----|-----------|
| [task-tracker-categories-swarm](2026-04-09-task-tracker-categories-swarm.md) | The demo app built by this pipeline; documents the scalar return bug |
| [flask-swarm-acid-test](2026-04-07-flask-swarm-acid-test.md) | Foundational proof that shared spec works in Python/Flask |
| [swarm-scale-shared-spec](2026-03-30-swarm-scale-shared-spec.md) | Proved pattern holds at 6 agents; identified spec bloat as scaling cost |
| [chain-reaction-inter-service-contracts](2026-03-30-chain-reaction-inter-service-contracts.md) | Data ownership lesson; same class of ambiguity as the return-type bug |
| [swarm-build-alignment](2026-03-30-swarm-build-alignment.md) | Origin doc; first discovery that parallel agents need a shared spec |
| [cross-project-knowledge-merge](2026-04-05-cross-project-knowledge-merge.md) | Governance pattern for consolidating swarm learnings |

### Knowledge Chain

```
swarm-build-alignment (Mar 30) -- "agents need a shared spec"
  -> swarm-scale-shared-spec (Mar 30) -- "pattern holds at 6 agents"
    -> chain-reaction-contracts (Mar 30) -- "spec needs data ownership"
      -> flask-swarm-acid-test (Apr 7) -- "pattern is stack-agnostic"
        -> task-tracker-categories-swarm (Apr 9) -- "second Flask validation"
          -> autopilot-swarm-orchestration (Apr 9) -- THIS DOC
             "Automated the entire pipeline"
```

## Feed-Forward

- **Hardest decision:** Whether to run assembly git operations in the main
  session or spawn a dedicated assembly agent. Chose main session for
  simplicity, but this is where the permission bug lives.
- **Rejected alternatives:** Python orchestration wrapper (loses context),
  two separate commands (maintenance burden), single verification agent
  (gets off task).
- **Least confident:** Whether the permission model can be fixed without
  adding a 7th agent. The cleanest fix might be an assembly-merge agent
  with bypassed permissions, but that adds coordination overhead.
