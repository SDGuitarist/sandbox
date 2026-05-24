---
name: autopilot
description: Full autonomous compound engineering loop with swarm support. Reads plan frontmatter to branch between solo and swarm paths. Use to build apps end-to-end unattended.
argument-hint: "[app description]"
allowed-tools: Read Edit Write Glob Grep Bash Agent
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

## Agent Permission Mode (MANDATORY)

ALL agents spawned during this pipeline MUST use `mode: "bypassPermissions"`.
This includes verification agents (spec-consistency-checker, spec-completeness-checker, spec-contract-checker),
test runners (smoke-test-runner, test-suite-runner), fix agents (assembly-fix),
review agents (brainstorm-refinement, flow-trace-reviewer), and the self-audit
agent -- not just swarm workers. Without this, spawned agents inherit the
session's permission mode and may prompt for tool approval, breaking the
zero-prompt guarantee.

## Bash Command Rules (MANDATORY -- read before any Bash call)

Security heuristics fire on compound commands regardless of permissions. One command per Bash call. Always.

1. `cd /path && command` -- use `git -C /path` or full paths instead
2. `source .venv/bin/activate` -- use full path: `.venv/bin/pip`, `.venv/bin/python`
3. `for x in ...; do ... done` -- use multiple individual Bash calls or Glob tool
4. `python3 -c "code"` -- use Write tool to create .py file, then run it
5. `echo "${variable}"` -- use Write tool for variable content
6. `&&` or `;` to chain commands -- one command per Bash call. Always.

## Steps

Execute these steps in order. Do not stop between steps.

### Step 1: Compound Start + Capture Lessons

Run `/compound-start $ARGUMENTS`

The solution-doc-searcher agent will return relevant lessons from prior builds.
**Capture these findings** -- they feed into Step 2. Note which solution docs
were found and their key lessons (e.g., "CSRF missing in Flask builds,"
"scalar returns need usage examples," "data ownership required in spec").

### Step 1.5: Create BUILD_TRACKING.md

Copy the tracking template into the project root. This is MANDATORY -- do not
skip. The template is at `~/.claude/docs/autopilot-tracking-template.md`.

1. Read `~/.claude/docs/autopilot-tracking-template.md`
2. Write it to `BUILD_TRACKING.md` in the project root
3. Fill in the Run Info section (project name, spec path, date, build method)
4. **Swarm builds only -- clean template scaffold for incremental writes:**
   - Use Edit tool to replace everything between `## AGENT_STATUS` and `---`
     (the section divider before `## FAILURES`) with a table header:
     ```
     | # | Agent | Commit | Status |
     |---|-------|--------|--------|
     ```
   - Use Edit tool to replace everything between `## FAILURES` and `---`
     (the section divider before `## RUN_METRICS`) with:
     `<!-- Filled after review -->`
   - Use Edit tool to replace everything between `## RUN_METRICS` and
     `## Template Version` with:
     `<!-- Filled after review -->`
5. Solo builds: skip step 4. Keep the original template scaffold for bulk fill.

If the template file doesn't exist, create a minimal BUILD_TRACKING.md with
Run Info + AGENT_STATUS table header + empty FAILURES + empty RUN_METRICS.

### Step 1.6: Inject Agent Pitfalls

Read `~/.claude/docs/agent-pitfalls.md`. These pitfalls MUST be injected into
every agent brief in Step 10w (swarm) or referenced in Step 7s (solo).
Capture the full document content for injection later.

### Step 2: Expand Brief + Roadmap

Expand the user's app description into a structured brief, informed by the
solution doc findings from Step 1. This prevents the brainstorm workflow from
asking interactive questions and ensures past lessons are baked in from the start.

Generate the following from `$ARGUMENTS` + solution doc findings (do not
create a file -- pass it inline to Step 3):

```
## App Brief

**Name:** [inferred from description]
**Target user:** [single user / team / public -- pick the simplest]
**Tech stack:** [detect from description or default to Flask + SQLite + Jinja2]
  - If description mentions "node", "express", "javascript", or "api":
    Node/Express + SQLite (better-sqlite3) + Jest
    Spec template: docs/templates/shared-spec-node.md
  - Otherwise: Flask + SQLite + Jinja2 (sandbox standard)
    Spec template: docs/templates/shared-spec-flask.md
**Core features:** [3-5 bullet points extracted from description]
**Explicitly out of scope for MVP:** [list obvious v2 features]

## Roadmap

**Phase 1 (MVP -- this build):**
- [feature 1]
- [feature 2]
- [feature 3]

**Phase 2 (future):**
- [deferred feature 1]
- [deferred feature 2]

**Phase 3 (if needed):**
- [nice-to-have 1]

## Lessons Applied from Prior Builds

[For each relevant solution doc found in Step 1, list what it taught
and how it influences this brief. Examples:]
- CSRF protection required on all POST forms (from: autopilot-swarm-orchestration)
- Scalar-return functions need usage examples in spec (from: task-tracker-categories)
- Data ownership table required in spec (from: chain-reaction-contracts)
- SECRET_KEY must read from environment (from: autopilot-swarm-orchestration)
```

Make all decisions yourself. Do not ask the user. Pick the simplest, most
focused interpretation of the app description. If a solution doc lesson
applies, include it in core features or roadmap constraints -- don't just
list it, act on it.

### Step 2.5: Persist Brief + Clean Stale Manifests

1. Write the expanded brief to `docs/reports/expanded-brief.md` so all
   phase agents can read it from disk.
2. Delete `docs/reports/phase-brainstorm.manifest.yaml` if it exists.
3. Delete `docs/reports/phase-plan.manifest.yaml` if it exists.
   (Prevents stale manifest collision from prior runs.)

### Step 3: Brainstorm (Delegated)

1. Read agent-pitfalls from Step 1.6.
2. Spawn the **phase-brainstorm** agent:
   - `mode: "bypassPermissions"`
   - `run_in_background: false` (sequential -- need result before plan)
   - Prompt includes: expanded brief path (`docs/reports/expanded-brief.md`),
     applied lessons from Step 1, agent-pitfalls.
     (No prior manifest -- brainstorm is the first phase.)
3. After agent completes, read `docs/reports/phase-brainstorm.manifest.yaml`.
4. Verify:
   - `phase_status` is `PASS`
   - `brainstorm_path` exists on disk
   - `feed_forward_*` fields are present
5. If `FAIL` or `IN_PROGRESS`: retry once. If still fails, abort pipeline.
6. Extract `feed_forward_*` fields from manifest for injection into plan phase.

### Step 5: Plan

Run `/workflows:plan $ARGUMENTS`

**Feed-Forward check:** After the plan doc is written, verify:
1. YAML frontmatter contains `feed_forward:` with `risk:` and `verify_first:`
2. Doc ends with `## Feed-Forward` section (three questions)
3. The plan addresses the brainstorm's "least confident" item

If any are missing, add them before proceeding.

### Step 6: Deepen Plan

Run `/compound-engineering:deepen-plan`

After deepening completes, read the plan document in `docs/plans/`. Extract the
`swarm:` field from its YAML frontmatter.

### Step 6.05: Plan Review and Refine (Pass 1)

Run `/compound-engineering:document-review` on the plan document in `docs/plans/`.

This is the first review pass -- it assesses clarity, completeness, specificity,
and YAGNI compliance, then fixes issues inline. The skill will identify the
single most impactful improvement and apply it.

If the skill asks whether to refine again or mark as complete, choose
**refine again** (this feeds into Step 6.07).

### Step 6.07: Plan Review and Refine (Pass 2)

Run `/compound-engineering:document-review` on the same plan document again.

This second pass catches issues introduced or exposed by the first refinement.
After this pass, the skill will recommend completion (diminishing returns after
2 passes). Accept completion and proceed.

### Step 6.1: Generate Run ID and Reports Directory (MANDATORY)

Count the files in `docs/solutions/` and add 1. Zero-pad to 3 digits. This is
the `run-id` (e.g., 21 solutions = run `022`). Create `docs/reports/<run-id>/`.

This step runs before the deepening merge so `docs/reports/<run-id>/` exists
for the audit trail. Both solo and swarm paths use this run-id -- the duplicate
generation in Steps 7s.0 and 8w/9w is removed.

### Step 6.5: Merge Deepening Into Plan (MANDATORY)

After deepening completes, merge all accepted corrections into the plan file
in-place. The orchestrator already has the plan and amendment outputs in context.

1. Read all deepening agent outputs. Identify changes per plan section.
2. If multiple agents modified the same section: synthesize a single merged
   edit. Document conflicts in the audit trail.
3. Use Write tool to overwrite the plan file with the merged version.
4. Use Write tool to create `docs/reports/<run-id>/deepening-applied.md` with
   a summary of what changed and why (audit trail only, not execution input).
5. Commit the rewritten plan:
   `git add docs/plans/<plan-file>`
6. Commit the audit trail:
   `git add docs/reports/<run-id>/deepening-applied.md`
7. Create the commit:
   `git commit -m "chore: merge deepening corrections into plan"`

All downstream steps (swarm planner, agents, contract check) read the
rewritten plan. No agent should see raw amendment notes.

---

## Branch Point

Read the plan's YAML frontmatter. Check the `swarm:` field.

- If `swarm: false` or `swarm:` is missing -> follow **Solo Path** below
- If `swarm: true` -> follow **Swarm Path** below

---

## Solo Path

### Step 7s.0: (Removed -- run-id now generated in Step 6.1)

Use the `run-id` and `docs/reports/<run-id>/` created in Step 6.1.

### Step 7s: Work

Run `/workflows:work`

**FC8 Smoke Test Rule (MANDATORY):** When running smoke tests during or after
the work phase, NEVER use `python3 -c "..."` with inline code. Instead:

1. Write smoke tests to a file (e.g., `test_smoke.py` in the app directory)
2. Add `test_smoke.py` to `.gitignore` BEFORE writing it
3. Set secrets via `os.environ.setdefault()` INSIDE the script, not as
   command-line env prefixes (e.g., `SECRET_KEY=x python ...` triggers
   security heuristics even with `dangerouslySkipPermissions`)
4. Run with a single Bash call: `.venv/bin/python test_smoke.py`
5. Do NOT use `#` comments, multi-line strings, or `&&` chaining in Bash

**Why this matters:** Security heuristics fire above `dangerouslySkipPermissions`.
Three known triggers: (1) "SECRET" in command strings, (2) newline + `#` in
quoted args (hidden argument detection), (3) multi-line Python in `-c` flag.
All three cause permission prompts that break the zero-prompt guarantee.

Then follow the **Shared Tail** below.

---

## Swarm Path

### Step 7w: Swarm Planner

Use the **swarm-planner** agent. Pass the path to the plan document.

Read the agent's output. Check for STATUS: PASS. If STATUS: FAIL, abort the
swarm path and output the error. Do not proceed.

### Step 8w: (Removed -- run-id now generated in Step 6.1)

Use the `run-id` from Step 6.1 for branch naming.

### Step 9w: (Removed -- reports directory now created in Step 6.1)

Use `docs/reports/<run-id>/` created in Step 6.1. All report paths in
subsequent steps use `docs/reports/<run-id>/`.

### Pre-Swarm Structural Gates (Steps 9w.5 and 9w.6)

These gates run after run-id generation and before swarm agent spawn.
Step 9w.5 checks for contradictions. Step 9w.6 checks for omissions.
Both must PASS for the swarm to launch.

### Step 9w.5: Pre-Swarm Spec Consistency Gate (MANDATORY -- SWARM ONLY)

Use the **spec-consistency-checker** agent. Pass:
1. The path to the plan document
2. `docs/reports/<run-id>/` (the reports directory created in Step 6.1)

The agent writes its report to `docs/reports/<run-id>/spec-consistency-check.md`.
Read that file and check STATUS.
- If PASS: continue to Step 9w.6.
- If FAIL: abort the swarm path. Output the contradiction list. The spec
  author must fix the contradictions and re-run. Do not proceed.

### Step 9w.6: Spec Completeness Gate (MANDATORY -- SWARM ONLY)

Use the **spec-completeness-checker** agent. Pass:
1. The path to the plan document
2. `docs/reports/<run-id>/` (the reports directory created in Step 6.1)

The agent writes its report to `docs/reports/<run-id>/spec-completeness-check.md`.
Read that file and check STATUS.
- If PASS: continue to Step 10w (Parallel Swarm Work).
- If FAIL: read the Details section. Fix the spec omissions identified in the
  report (add missing entries to the coverage tables). Commit the fix:
  `git add docs/plans/<plan-file>`
  `git commit -m "fix: add missing spec coverage entries (completeness gate)"`
  Re-run Step 9w.6. Max 1 retry.
- If still FAIL after retry: abort with
  "SPEC INCOMPLETE: <N> omissions across <M> surfaces. See report."

This gate catches spec-author omissions (missing export names, missing
authorization annotations, unannotated transactions) that produce predictable
P1s at swarm scale. It is separate from Step 9w.5 (consistency) which catches
contradictions.

### Step 9w.7: Pre-Swarm Gate Verification (MANDATORY -- SWARM ONLY)

Before spawning ANY agents, re-read BOTH gate reports and write a gate
verification artifact. This step exists because the orchestrator has
historically proceeded past failed gates (Run 054 -- both gates FAIL,
swarm launched anyway). The artifact is a hard precondition for Step 10w.

1. Read `docs/reports/<run-id>/spec-consistency-check.md`. Find the line
   containing `STATUS:`. Copy the full line verbatim. Then normalize it
   by stripping these specific characters from the start and end of the
   line: `*` (bold), `_` (italic), `#` (heading), and leading/trailing
   whitespace. Do NOT strip backticks, brackets, or other characters.
   Example: `**STATUS: PASS**` → `STATUS: PASS`.
   Example: `### STATUS: FAIL -- 3 contradictions` → `STATUS: FAIL -- 3 contradictions`.
2. Read `docs/reports/<run-id>/spec-completeness-check.md`. Same procedure:
   copy verbatim, normalize by stripping `*`, `_`, `#`, and whitespace
   from start and end.
3. Write `docs/reports/<run-id>/gate-verification.md` with this exact format:
   ```
   STATUS: [CLEARED or BLOCKED]
   consistency_raw: "[verbatim STATUS line from consistency report]"
   consistency_normalized: "[after stripping markdown formatting]"
   completeness_raw: "[verbatim STATUS line from completeness report]"
   completeness_normalized: "[after stripping markdown formatting]"
   ```
   The `STATUS:` value in gate-verification.md MUST be derived from the
   two NORMALIZED lines. It is CLEARED only if both normalized lines
   start with `STATUS: PASS`. Any other content means BLOCKED.
   Do NOT write CLEARED speculatively or without reading both reports.
4. If BLOCKED: output `"PRE-SWARM GATE BLOCKED"` with the two quoted
   status lines. Do NOT proceed to Step 10w. This is a hard abort.
5. If CLEARED: proceed to Step 10w.

### Step 10w: Parallel Swarm Work

**PRECONDITION:** Before reading the agent assignment table, verify that
`docs/reports/<run-id>/gate-verification.md` exists AND contains
`STATUS: CLEARED`. If the file does not exist or contains `STATUS: BLOCKED`,
abort with: `"CANNOT SPAWN: gate-verification.md missing or BLOCKED.
Run Step 9w.7 first."` This check is non-negotiable -- it prevents the
orchestrator from skipping the gate verification step entirely.

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
assigned files. For each worktree branch, run these as SEPARATE Bash calls
(one per branch -- do NOT use a for-loop):

1. Run: `git -C <project-root> diff --name-only main...<branch-name>`
2. Compare the output against the agent's assigned files using Read tool.
3. If ANY file in the diff is NOT in the agent's assignment, **abort the merge
   for that branch**. Use Write tool to create `docs/reports/<run-id>/ownership-violation.md`:
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
6. **Incremental BUILD_TRACKING:** After writing ownership-gate.md, run:
   `echo "### Ownership Gate: PASS ([N] agents)" >> BUILD_TRACKING.md`

### Step 11w: Assembly Merge

After all swarm agents pass the ownership gate, run each as a SEPARATE Bash
call (do NOT chain with && or use for-loops):

1. Run: `git branch --show-current`
   Save the output as `original-branch` for use in Step 15w.
2. Run: `git checkout -b swarm-<run-id>-assembly`
3. For each worktree agent that made changes, run ONE merge at a time
   (separate Bash call for each -- do NOT use a for-loop):
   `git merge --no-ff <branch-name>`
   **Incremental BUILD_TRACKING:** After each successful merge, run two Bash calls:
   - `git log -1 --format=%h` (capture as commit_hash)
   - `echo "| [N] | [role] | [commit_hash] | PASS |" >> BUILD_TRACKING.md`
   Where N is the sequential agent number (1-based) and role is from the assignment table.
4. If a merge fails (exit code != 0), use Write tool to save the conflict
   output to `docs/reports/<run-id>/merge-conflict.md`, then invoke the
   **assembly-fix** agent with the conflict report, plan path, and project root.
   Check its STATUS. If FIXED, continue merging. If FAIL, abort and report.
5. After all merges succeed, the assembly branch has the combined code.

### Step 12w: Circuit Breaker -- Spec Contract Check

Use the **spec-contract-checker** agent. Pass the plan path and project root.

Read `docs/reports/<run-id>/contract-check.md`. Check STATUS.
**Incremental BUILD_TRACKING:** `echo "### Contract Check: [STATUS]" >> BUILD_TRACKING.md`
- If PASS: continue to smoke test.
- If FAIL: use the **assembly-fix** agent with the contract check report,
  plan path, and project root (max 1 retry). Re-run spec contract check
  after fix. If still FAIL, abort the pipeline and report.

### Step 13w: Smoke Test

Use the **smoke-test-runner** agent. Pass the plan path and project root.

Read `docs/reports/<run-id>/smoke-test.md`. Check STATUS.
**Incremental BUILD_TRACKING:** `echo "### Smoke Test: [STATUS]" >> BUILD_TRACKING.md`
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
back into the branch recorded in Step 11w. Run each as a SEPARATE Bash call:

1. Run: `git checkout <original-branch>`
2. Run: `git merge --no-ff swarm-<run-id>-assembly`

### Step 16w: Cleanup

On success (all checks passed), run each as a SEPARATE Bash call
(do NOT use a for-loop -- run each removal as its own Bash call):

1. `git worktree remove <path>` (one call per worktree)
2. `git branch -D swarm-<run-id>-<role>` (one call per branch)
3. `git branch -D swarm-<run-id>-assembly`

On failure (unresolved issues), run each as a SEPARATE Bash call:

1. `git worktree remove <path>` (one call per worktree)

Do NOT delete branches on failure -- they are preserved for inspection.
Report which branches are kept and why.

Then follow the **Shared Tail** below.

---

## Shared Tail (both paths end here)

### Review

Run `/workflows:review`

The review agents should scrutinize any areas flagged in the plan's
Feed-Forward "least confident" item. After review completes, verify that
review findings reference the Feed-Forward risk if applicable.

**Incremental BUILD_TRACKING:** After review completes, run:
`echo "### Review: [P1_count] P1, [P2_count] P2 | Fix commits: [hashes]" >> BUILD_TRACKING.md`

### Resolve TODOs

Run `/compound-engineering:resolve_todo_parallel`

### Compound

Run `/workflows:compound`

**Feed-Forward chain closure:** The solution doc MUST include a
`## Risk Resolution` section that traces:
1. What was flagged as a risk (from brainstorm/plan Feed-Forward)
2. What actually happened during implementation
3. What was learned (the delta between expectation and reality)

If the compound workflow doesn't produce this section, add it before
proceeding.

### Update Learnings (MANDATORY -- DO NOT SKIP)

**WARNING: This is FC11 from agent-pitfalls.md. The orchestrator has skipped
this step in 2 of 3 recent builds. It is a SEPARATE step from Compound.**

Run `/update-learnings-noninteractive`

This is the sandbox-local non-interactive variant. It runs Steps 0-6 of
the global update-learnings command without the code-explainer prompt.
See: docs/reports/spike-update-learnings-noninteractive.md

### Verify Learnings Artifacts (MANDATORY GATE)

After `/update-learnings-noninteractive` completes, verify these artifacts
exist. If ANY check fails, the run fails with the specific error shown.

1. **Learnings Propagated table:** The skill must have output the
   "Learnings Propagated" summary table. If it did not appear, FAIL with:
   `"LEARNINGS PROPAGATION FAILED: Summary table not output. Re-run /update-learnings-noninteractive manually."`

2. **HANDOFF.md timestamp:** Read the project root `HANDOFF.md`. The
   `**Date:**` line must contain today's date. If missing or stale, FAIL with:
   `"LEARNINGS PROPAGATION INCOMPLETE: HANDOFF.md not updated (date mismatch)."`

3. **Agent-pitfalls Update Log:** Read the last row of the Update Log
   table at the bottom of `~/.claude/docs/agent-pitfalls.md`. It must
   contain today's date AND the current build name. If missing, FAIL with:
   `"LEARNINGS PROPAGATION INCOMPLETE: agent-pitfalls.md Update Log missing entry for this build."`
   Recovery: run the agent-pitfalls update manually:
   - Read the solution doc's review findings
   - Trace each finding to existing failure class or create new one
   - Update per-agent-type rules
   - Add Update Log entry
   Then re-check.

4. **Agent-pitfalls ID uniqueness:** Run this check:
   `grep -o '## Failure Class [0-9]*' ~/.claude/docs/agent-pitfalls.md | sed 's/## Failure Class //' | sort -n | uniq -d`
   If this returns ANY output, FAIL with:
   `"DUPLICATE FAILURE CLASS IDs DETECTED: [list]. Fix before proceeding."`

Do NOT proceed to BUILD_TRACKING until ALL four checks pass.

### Fill BUILD_TRACKING.md (MANDATORY -- SOLO ONLY)

If this is a solo build (not swarm): fill AGENT_STATUS, FAILURES, and
RUN_METRICS sections now (same bulk-fill behavior as before -- read plan,
review findings, and report files to populate all three sections).

If this is a swarm build: skip this step. AGENT_STATUS is already populated
from incremental writes in Steps 10.5w-11w. Proceed to the swarm-only fill.

### Fill FAILURES and RUN_METRICS (MANDATORY -- SWARM ONLY)

After review completes and all P1 fixes are committed:

1. Read all report files in `docs/reports/<run-id>/` to compile failure data.
2. Use Edit tool to replace `<!-- Filled after review -->` under `## FAILURES`
   with a structured table: one row per finding (severity, detail, resolution,
   failure class). If no failures, replace with "None".
3. Use Edit tool to replace `<!-- Filled after review -->` under `## RUN_METRICS`
   with the Final Build Metrics table: agent count, FC37 rate, merge conflicts,
   file count, LOC estimate, smoke test results, review finding counts, plus
   Agent Performance Summary table (agent, findings caused, failure classes).

These edits target the cleaned placeholders written during Step 1.5 template
cleanup. No duplicate headings. The self-audit agent reads FAILURES and
RUN_METRICS as canonical sources.

### Context-Budget Checkpoint -- Pre-Audit (MANDATORY)

Calculate orchestration load:
- `swarm_agents` = number of agents spawned in Step 10w (count from assignment table; 0 for solo)
- `deepening_agents` = number of agents spawned in Step 6 (count from deepen-plan output, default 4)
- `review_agents` = number of review agents spawned during Review
- `fix_retries` = number of assembly-fix agent invocations in Steps 12w-14w (count from report files; 0 for solo)
- `load = swarm_agents + (deepening_agents * 2) + (review_agents * 1.5) + (fix_retries * 3)`

If `load > 30`:

1. Identify the solution doc written by Compound (most recent file in `docs/solutions/`).
2. Use Write tool to create CHECKPOINT.md with all paths from current run state:

```yaml
---
status: PAUSED_FOR_CONTEXT
run_id: "<run-id from Step 6.1>"
date: "<today>"
branch: "<current branch>"
project_name: "<project name from Step 2>"
---

plan_path: <path to plan>
solution_doc_path: <path to solution doc>
review_summary_path: <path to review summary>
reports_dir: docs/reports/<run-id>/
build_tracking_path: BUILD_TRACKING.md
handoff_path: HANDOFF.md

last_completed_step: "Fill BUILD_TRACKING"
next_step: "Verify BUILD_TRACKING"

completed_artifacts:
  - <list all completed artifact paths>

pending_mandatory_artifacts:
  - Verify BUILD_TRACKING.md completeness
  - Self-audit report (docs/reports/<run-id>/self-audit.md)
  - Verify self-audit (9 gates)

review_findings:
  p1_fixed: <count>
  p2_deferred: <count>
  fix_commits: [<hashes>]
```

3. Commit CHECKPOINT.md:
   `git add CHECKPOINT.md`
4. Create commit:
   `git commit -m "chore: context checkpoint for tail resume"`
5. Output: `PAUSED_FOR_CONTEXT: Orchestration load is [load] (threshold 30). CHECKPOINT.md written and committed. Resume with /tail-resume.`
6. Output: `<promise>PAUSED_FOR_CONTEXT</promise>`
7. STOP. Do not proceed to Verify BUILD_TRACKING.

If `load <= 30`: proceed to Verify BUILD_TRACKING normally.

### Verify BUILD_TRACKING.md Completeness (MANDATORY GATE)

Read BUILD_TRACKING.md and verify these sections are non-empty:
- `## AGENT_STATUS` -- must have at least one agent row (table row for swarm, block for solo)
- `## FAILURES` -- must exist (can say "None" if no failures)
- `## RUN_METRICS` -- must have at least one metric row

If any section is missing or empty, FAIL with:
`"BUILD_TRACKING INCOMPLETE: [section name] is missing or empty."`

### Self-Audit (MANDATORY -- DO NOT SKIP)

**WARNING: This is the final honesty gate. It catches documentation gaps,
undisposed warnings, and false success claims before the run is marked done.**

Use the **self-audit-reviewer** agent. Pass these six arguments:
1. The run-id (from Step 6.1)
2. The reports directory path (`docs/reports/<run-id>/`)
3. The plan document path
4. The solution doc path (the file created during Compound)
5. `BUILD_TRACKING.md`
6. `HANDOFF.md`

The agent writes `docs/reports/<run-id>/self-audit.md`. Read that file and
check STATUS.

- If STATUS: PASS -- proceed to the self-audit verification gate.
- If STATUS: FAIL -- the agent could not produce a complete report. FAIL the
  run with: `"SELF-AUDIT AGENT FAILED: <reason from agent output>"`

### Verify Self-Audit (MANDATORY GATE)

Run `/verify-self-audit <run-id> docs/reports/<run-id>/`

This helper skill runs 9 hard gates on the self-audit report: report exists,
WARN keys valid and dispositions correct, deferred items tracked by key in
HANDOFF.md, source reconciliation complete, honest success claim,
section completeness (What Was Missed, skeptical questions, promotions),
and run quality grading (6 scored dimensions with artifact-backed evidence).

Check its output. If STATUS: FAIL, the run fails. Do NOT proceed to Done.

### Done

Output `<promise>DONE</promise>` -- all phases complete.
