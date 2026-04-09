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

### Step 8s: Review

Run `/workflows:review`

### Step 9s: Resolve TODOs

Run `/compound-engineering:resolve_todo_parallel`

### Step 10s: Compound + Learnings

Run `/workflows:compound`
Run `/update-learnings`

### Step 11s: Done

Output `<promise>DONE</promise>` -- all phases complete.

---

## Swarm Path

### Step 7w: Swarm Planner

Use the **swarm-planner** agent. Pass the path to the plan document.

Read the agent's output. Check for STATUS: PASS. If STATUS: FAIL, abort the
swarm path and output the error. Do not proceed.

### Step 8w: Generate Run ID

Count the files in `docs/solutions/` and add 1. Zero-pad to 3 digits. This is
the `run-id` (e.g., 21 solutions = run `022`). Use this for branch naming.

### Step 9w: Clear Reports Directory

Delete all files in `docs/reports/` if the directory exists. Then recreate it
empty. This prevents stale reports from prior runs.

### Step 10w: Parallel Swarm Work

Read the `## Swarm Agent Assignment` section from the plan. For each agent in
the assignment table:

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

### Step 11w: Assembly Merge

After all swarm agents complete:

1. Create an assembly branch: `swarm-[run-id]-assembly`
2. For each worktree agent that made changes, merge its branch into the
   assembly branch sequentially using `git merge --no-ff [branch]`
3. If any merge fails (exit code != 0):
   - Use the **assembly-fix** agent with the merge conflict output, the plan
     path, and the project root
   - Check its STATUS. If FIXED, continue merging. If FAIL, abort and report.
4. After all merges succeed, the assembly branch has the combined code.

### Step 12w: Circuit Breaker -- Spec Contract Check

Use the **spec-contract-checker** agent. Pass the plan path and project root.

Read `docs/reports/contract-check.md`. Check STATUS.
- If PASS: continue to smoke test.
- If FAIL: check if mismatches are fixable. If unfixable mismatches exist,
  abort the pipeline and report. Do not proceed to smoke testing.

### Step 13w: Smoke Test

Use the **smoke-test-runner** agent. Pass the plan path and project root.

Read `docs/reports/smoke-test.md`. Check STATUS.
- If PASS: continue to test suite.
- If FAIL: use the **assembly-fix** agent with the smoke test report, plan
  path, and project root (max 1 retry). Re-run smoke test after fix. If still
  FAIL, continue to review with the failure noted.

### Step 14w: Test Suite

Use the **test-suite-runner** agent. Pass the project root.

Read `docs/reports/test-results.md`. Check STATUS.
- If PASS: continue to review.
- If FAIL: use the **assembly-fix** agent with the test report, plan path,
  and project root (max 1 retry). Re-run tests after fix. If still FAIL,
  continue to review with the failure noted.

### Step 15w: Merge Assembly to Main

If all verification passed (or failures were fixed), merge the assembly branch
into the current working branch:

```
git checkout [original-branch]
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

### Step 17w: Review

Run `/workflows:review`

### Step 18w: Resolve TODOs

Run `/compound-engineering:resolve_todo_parallel`

### Step 19w: Compound + Learnings

Run `/workflows:compound`
Run `/update-learnings`

### Step 20w: Done

Output `<promise>DONE</promise>` -- all phases complete.
