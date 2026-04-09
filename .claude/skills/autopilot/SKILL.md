---
name: autopilot
description: Full autonomous compound engineering loop with swarm support. Reads plan frontmatter to branch between solo and swarm paths. Use to build apps end-to-end unattended.
argument-hint: "[app description]"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, Agent
---

# Autopilot

Run the full compound engineering pipeline unattended. After planning and
deepening, read the plan's YAML frontmatter. If `swarm: true`, take the swarm
path (parallel agents + assembly verification). Otherwise, take the solo path.

## Prerequisites

This skill requires unattended execution. Before running, verify:

1. **Run from inside the project directory** (`cd ~/Projects/sandbox`).
   Project-level skills and settings are only loaded when cwd is the project.
2. **dangerouslySkipPermissions** must be `true` in `.claude/settings.local.json`.
   Without this, git operations (checkout, merge, branch -D) will prompt
   interactively and block the pipeline.

If either condition is not met, abort with:
```
ABORT: Autopilot requires unattended permissions. Run from the project
directory with dangerouslySkipPermissions enabled in settings.local.json.
```

## Steps

Execute these steps in order. Do not stop between steps.

### Step 1: Start Ralph Loop

Run `/ralph-loop:ralph-loop "finish all slash commands" --completion-promise "DONE"`

### Step 2: Compound Start

Run `/compound-start $ARGUMENTS`

### Step 3: Brainstorm

Run `/workflows:brainstorm $ARGUMENTS`

### Step 4: Brainstorm Refinement

Use the **brainstorm-refinement** agent. Pass the path to the brainstorm doc
just created in `docs/brainstorms/`. Read its output and check for STATUS: PASS.

### Step 5: Plan

Run `/workflows:plan $ARGUMENTS`

### Step 6: Deepen Plan

Run `/compound-engineering:deepen-plan`

After deepening completes, read the plan document in `docs/plans/`. Extract the
`swarm:` field from its YAML frontmatter.

---

## Branch Point

Read the plan's YAML frontmatter. Check the `swarm:` field.

- If `swarm: false` or `swarm:` is missing -> follow **Solo Path** below
- If `swarm: true` -> follow **Swarm Path** below

---

## Solo Path

### Step 7s: Work

Run `/workflows:work`

Then follow the **Shared Tail** below.

---

## Swarm Path

### Step 7w: Swarm Planner

Use the **swarm-planner** agent. Pass the path to the plan document.

Read the agent's output. Check for STATUS: PASS. If STATUS: FAIL, abort the
swarm path and output the error. Do not proceed.

### Step 8w: Generate Run ID

Count the files in `docs/solutions/` and add 1. Zero-pad to 3 digits. This is
the `run-id` (e.g., 21 solutions = run `022`). Use this for branch naming.

### Step 9w: Create Reports Directory

Create `docs/reports/<run-id>/` for this run's verification reports. Do NOT
delete prior run directories -- they serve as audit trail. All report paths
in subsequent steps use `docs/reports/<run-id>/` instead of `docs/reports/`.

### Step 10w: Parallel Swarm Work

Read the `## Swarm Agent Assignment` section from the plan. Before spawning
any agents, validate ALL file paths in the assignment table:

- Reject any absolute path (starts with `/`)
- Reject any path containing `..`
- Reject any symlink target outside the repo root
- Every path must be relative to the project root

If any path fails validation, abort with an error listing the invalid paths.
Do not spawn any agents until all paths pass.

For each agent in the assignment table:

1. Build a prompt that includes:
   - The full shared interface spec from the plan
   - The agent's specific file assignments
   - These strict rules:
     1. Create ONLY the files in your assignment. No other files.
     2. Use EXACT names from the spec for all functions, routes, classes, and variables.
     3. Do not make design decisions. The spec decides everything.
     4. Do not import from files assigned to other agents unless the spec defines the import.
     5. Follow the spec's directory structure exactly.
     6. If the spec is ambiguous, pick the simplest interpretation.
     7. Do not add features, comments, or extras beyond what the spec requires.
     8. Write production-quality code. No TODOs, no placeholders.
     9. Create any directories needed for your files.
     10. When done, commit all your files with a descriptive message.

2. Spawn an Agent with:
   - `isolation: "worktree"`
   - `run_in_background: true`
   - `name: "swarm-[run-id]-[role-name]"` (e.g., `swarm-022-routes`)
   - `mode: "bypassPermissions"`

Spawn ALL agents in a single message (parallel launch). Then wait for all
agents to complete. You will be notified as each finishes.

**Timeout:** If any agent has not completed after 10 minutes, report it as
a failure and proceed with the agents that did complete. Do not wait
indefinitely.

### Step 10.5w: Pre-Merge Ownership Gate

Before merging any worktree branch, validate that each agent only touched its
assigned files. For each worktree branch:

1. Run `git diff --name-only main...[branch]` to get the list of changed files.
2. Compare against the agent's assigned files from the Swarm Agent Assignment.
3. If ANY file in the diff is NOT in the agent's assignment, **abort the merge
   for that branch**. Write the violation to `docs/reports/<run-id>/ownership-violation.md`:
   ```
   OWNERSHIP VIOLATION: Agent [role] modified [file] which is not in its assignment.
   Assigned files: [list]
   Actual changes: [list]
   STATUS: FAIL
   ```
4. If all agents pass the ownership check, write a summary to
   `docs/reports/<run-id>/ownership-gate.md`:
   ```
   OWNERSHIP GATE: All [N] agents passed. Each agent only modified assigned files.
   STATUS: PASS
   ```
5. Proceed to assembly merge.

### Step 11w: Assembly Merge

After all swarm agents pass the ownership gate:

1. Record the current branch name: `git branch --show-current` (save as
   `original-branch` for use in Step 15w).
2. Create an assembly branch: `git checkout -b swarm-[run-id]-assembly`
3. For each worktree agent that made changes, merge its branch into the
   assembly branch sequentially using `git merge --no-ff [branch]`
4. If any merge fails (exit code != 0):
   - Write the merge conflict output to `docs/reports/<run-id>/merge-conflict.md`
   - Use the **assembly-fix** agent with `docs/reports/<run-id>/merge-conflict.md`,
     the plan path, and the project root
   - Check its STATUS. If FIXED, continue merging. If FAIL, abort and report.
5. After all merges succeed, the assembly branch has the combined code.

### Step 12w: Circuit Breaker -- Spec Contract Check

Use the **spec-contract-checker** agent. Pass the plan path and project root.

Read `docs/reports/<run-id>/contract-check.md`. Check STATUS.
- If PASS: continue to smoke test.
- If FAIL: use the **assembly-fix** agent with the contract check report,
  plan path, and project root (max 1 retry). Re-run spec contract check
  after fix. If still FAIL, abort the pipeline and report.

### Step 13w: Smoke Test

Use the **smoke-test-runner** agent. Pass the plan path and project root.

Read `docs/reports/<run-id>/smoke-test.md`. Check STATUS.
- If PASS: continue to test suite.
- If FAIL: use the **assembly-fix** agent with the smoke test report, plan
  path, and project root (max 1 retry). Re-run smoke test after fix. If still
  FAIL, continue to review with the failure noted.

### Step 14w: Test Suite

Use the **test-suite-runner** agent. Pass the project root.

Read `docs/reports/<run-id>/test-results.md`. Check STATUS.
- If PASS: continue to review.
- If FAIL: use the **assembly-fix** agent with the test report, plan path,
  and project root (max 1 retry). Re-run tests after fix. If still FAIL,
  continue to review with the failure noted.

### Step 15w: Merge Assembly to Main

If all verification passed (or failures were fixed), merge the assembly branch
back into the branch recorded in Step 11w:

```
git checkout [original-branch recorded in Step 11w]
git merge --no-ff swarm-[run-id]-assembly
```

### Step 16w: Cleanup

On success (all checks passed):
- Remove worktree directories: `git worktree remove [path]` for each
- Delete worktree branches: `git branch -D swarm-[run-id]-[role]` for each
- Delete assembly branch: `git branch -D swarm-[run-id]-assembly`

On failure (unresolved issues):
- Remove worktree directories but KEEP branches for inspection
- Report which branches are preserved and why

Then follow the **Shared Tail** below.

---

## Shared Tail (both paths end here)

### Review

Run `/workflows:review`

### Resolve TODOs

Run `/compound-engineering:resolve_todo_parallel`

### Compound + Learnings

Run `/workflows:compound`
Run `/update-learnings`

### Done

Output `<promise>DONE</promise>` -- all phases complete.
