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
This includes the pre-swarm gate agents (spec-consistency-checker,
spec-completeness-checker), the delegation runners (deepen-merge-runner,
swarm-runner, tail-runner), review agents (brainstorm-refinement,
flow-trace-reviewer), and the self-audit agent -- not just swarm workers.
Without this, spawned agents inherit the session's permission mode and may
prompt for tool approval, breaking the zero-prompt guarantee.

(The swarm-runner inlines the former contract/smoke/test checks and merge-conflict
resolution; spec-contract-checker, smoke-test-runner, test-suite-runner, and
assembly-fix are no longer spawned — sub-agents lack the Agent tool.)

## Interactive Skill Prohibition (MANDATORY)

NEVER invoke a skill via the Skill tool during autopilot execution. Skills
like `/compound-engineering:document-review`, `/workflows:brainstorm`, and
`/workflows:plan` use `AskUserQuestion` which blocks the pipeline waiting
for user input. Instead:

- For document review: use the inline self-review steps (6.05/6.07)
- For brainstorm: pass "Autopilot Mode: pick simplest option" in args
- For plan: the plan workflow has a "Pipeline mode" clause — but prefer
  passing the full brief inline to avoid any interactive prompts
- For any other skill: read its SKILL.md for assessment criteria and
  apply them inline

The only skills safe to invoke are non-interactive ones (e.g.,
`/verify-self-audit`, `/update-learnings-noninteractive`).

## Bash Command Rules (MANDATORY -- read before any Bash call)

Security heuristics fire on compound commands regardless of permissions. One command per Bash call. Always.

1. `cd /path && command` -- use `git -C /path` or full paths instead
2. `source .venv/bin/activate` -- use full path: `.venv/bin/pip`, `.venv/bin/python`
3. `for x in ...; do ... done` -- use multiple individual Bash calls or Glob tool
4. `python3 -c "code"` -- use Write tool to create .py file, then run it
5. `echo "${variable}"` -- use Write tool for variable content
6. `&&` or `;` to chain commands -- one command per Bash call. Always.

## Phase Report Standardization (MANDATORY)

Phase reports MUST NOT have YAML frontmatter. Line 1 is always the STATUS
line: `STATUS: PASS` or `STATUS: FAIL -- <reason>`. No markdown formatting
around the STATUS value (no `**bold**`, no `#` heading).

This lets the orchestrator read only line 1 (`limit: 1`) of a report to learn
the outcome on PASS, instead of pulling the whole report into context. The
orchestrator reads the full report ONLY when line 1 says FAIL.

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
6. **Both paths -- insert the Phase Status section.** The global template is
   NOT modified; insert this into the local BUILD_TRACKING.md instead. Use the
   Edit tool to insert it immediately before the `## AGENT_STATUS` line (i.e.,
   between Run Info and AGENT_STATUS):
   ```markdown
   ## Phase Status

   | Phase | Status | Report Path |
   |-------|--------|-------------|

   **Run State:**
   - run_id: [TBD]
   - run_start_ts: [TBD]
   - plan_path: [TBD]
   - branch: [TBD]
   - context_proxy_chars: 0
   - manual_resume: false
   - final_status: null
   ```
7. Fill the Run State fields where known (plan_path, branch). Leave `run_id` and
   `run_start_ts` as `[TBD]` -- both are populated later in Step 5.5. Phase agents
   append rows to the Phase Status table as they complete.

If the template file doesn't exist, create a minimal BUILD_TRACKING.md with
Run Info + Phase Status section + AGENT_STATUS table header + empty FAILURES +
empty RUN_METRICS.

### Step 1.55: Advisory Baseline Capture (non-blocking)

Run `/advisory-audit baseline`

This captures the git SHA and filesystem snapshot for the post-run audit.
Best-effort -- if it fails, continue to Step 1.6. The post-run audit will
run in degraded mode (git-diff only) if the baseline is missing.

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

### Step 3: Brainstorm

Run `/workflows:brainstorm` with the expanded brief from Step 2 appended to
`$ARGUMENTS`. If the brainstorm workflow asks clarifying questions, pick the
simplest option and continue. Do not wait for user input.

**Feed-Forward check:** After the brainstorm doc is written, verify it ends
with a `## Feed-Forward` section containing all three questions (hardest
decision, rejected alternatives, least confident). If missing, append the
section before proceeding.

### Step 4: Brainstorm Refinement

Use the **brainstorm-refinement** agent. Pass the path to the brainstorm doc
just created in `docs/brainstorms/`. Read its output and check for STATUS: PASS.

### Step 5: Plan

Run `/workflows:plan $ARGUMENTS`

**Feed-Forward check:** After the plan doc is written, verify:
1. YAML frontmatter contains `feed_forward:` with `risk:` and `verify_first:`
2. Doc ends with `## Feed-Forward` section (three questions)
3. The plan addresses the brainstorm's "least confident" item

If any are missing, add them before proceeding.

### Step 5.5: Generate Run ID and Reports Directory (MANDATORY)

Count the files in `docs/solutions/` and add 1. Zero-pad to 3 digits. This is
the `run-id` (e.g., 21 solutions = run `022`). Create `docs/reports/<run-id>/`.

This step runs before deepening so `run_id` and `docs/reports/<run-id>/` exist
before the merge step needs them. Both solo and swarm paths use this run-id --
the duplicate generation in Steps 7s.0 and 8w/9w is removed.

After creating the directory, update BUILD_TRACKING.md Run State: replace
`- run_id: [TBD]` with `- run_id: <run-id>` (Edit tool).

Then capture the run-start timestamp: run `date +%s` and replace
`- run_start_ts: [TBD]` with `- run_start_ts: <epoch-seconds>` (Edit tool). This
is the freshness reference the terminal-gate disk-verify uses in Steps 11w-16w and
18w (a delegated artifact with `mtime < run_start_ts` is a stale leftover from a
prior aborted run at the same reused run-id, not this run's output). Save the value
as `run_start_ts` for those steps.

### Step 6: Deepen Plan (INLINE)

Run `/compound-engineering:deepen-plan` inline. The deepen-plan skill spawns
research sub-agents via the Agent tool, which only the orchestrator has, so
deepening MUST run in the orchestrator (both solo and swarm).

After deepening completes, read the plan document in `docs/plans/` and extract
the `swarm:` field from its YAML frontmatter (used at the Branch Point and by
Steps 6.03/6.03s).

Then extract a compressed correction summary from the deepening outputs: for
each section that changed, note the section name, the change, and the
rationale. Use this format, one block per correction:

  ### <Section Name>
  **Change:** <old text → new text, or addition>
  **Rationale:** <why the deepening agent recommended this>

### Step 6.03: Merge Deepening (DELEGATED — SWARM ONLY)

If `swarm: true` in the plan frontmatter:

Spawn the **deepen-merge-runner** agent with `mode: "bypassPermissions"`. Pass:
`plan_path`, `reports_dir` (`docs/reports/<run-id>/`), `run_id`,
`build_tracking_path` (BUILD_TRACKING.md), and the correction summary from
Step 6. Wait for the result.

Search backward in the agent's output for a line starting with `STATUS:`.
- If `STATUS: PASS`: proceed to Step 6.05. DO NOT read the full report.
- If `STATUS: FAIL`: find the `report_path:` line in the output and read the
  full report. Re-spawn once (max 1 retry). On a second FAIL, abort.

### Step 6.03s: Merge Deepening (INLINE — SOLO ONLY)

If `swarm: false` or `swarm:` is missing:

Merge all accepted corrections into the plan file in-place. The orchestrator
already has the plan and amendment outputs in context.

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

Proceed to Step 6.05. All downstream steps (swarm planner, agents, contract
check) read the rewritten plan. No agent should see raw amendment notes.

### Step 6.05: Plan Self-Review Pass 1 (INLINE — do NOT invoke document-review skill)

Read the plan document. Assess against these 4 criteria:

1. **Clarity**: Any vague language? ("probably", "consider", "try to", "maybe")
2. **Completeness**: All 6 mandatory spec sections present and non-empty?
   (Export Names, Cross-Boundary Wiring, Input Validation, Coordinated
   Behaviors, Transaction Contracts, Authorization Matrix)
3. **Specificity**: Concrete enough for agents to implement without asking
   questions? Every function has a signature + return type? Every route has
   method + path + auth?
4. **YAGNI**: Any hypothetical features, over-engineering, or Phase 2 items
   leaking into Phase 1?

Identify the single most impactful issue and fix it inline (Edit tool).
If no issues found, proceed. Do NOT invoke `/compound-engineering:document-review`
— that skill uses AskUserQuestion which blocks the autopilot pipeline.

### Step 6.07: Plan Self-Review Pass 2 (INLINE — do NOT invoke document-review skill)

Re-read the plan. Check whether pass 1's fix introduced new inconsistencies
(e.g., a renamed function in one section but not updated in another). Fix any
found. After 2 passes, diminishing returns — proceed to Step 6.08.

**Why inline?** The document-review skill is designed for interactive use
(AskUserQuestion at the end of each pass). In autopilot, this stalls the
pipeline. The 4-criteria check above captures the same value without the
interactive prompt. The pre-swarm gates (Steps 9w.5/9w.6) handle the deeper
cross-section contradiction checks that Codex would do in manual flow.

### Step 6.08: Commit Self-Review Edits (MANDATORY)

If Steps 6.05/6.07 produced any plan edits, commit them:
  `git add docs/plans/<plan-file>`
  `git commit -m "chore: plan self-review edits"`

If no edits were made, skip. This ensures self-review changes are not left
uncommitted after the deepening merge commit (Step 6.03/6.03s).

---

## Branch Point

Read the plan's YAML frontmatter. Check the `swarm:` field.

- If `swarm: false` or `swarm:` is missing -> follow **Solo Path** below
- If `swarm: true` -> follow **Swarm Path** below

---

## Solo Path

### Step 7s.0: (Removed -- run-id now generated in Step 5.5)

Use the `run-id` and `docs/reports/<run-id>/` created in Step 5.5.

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

### Step 8w: (Removed -- run-id now generated in Step 5.5)

Use the `run-id` from Step 5.5 for branch naming.

### Step 9w: (Removed -- reports directory now created in Step 5.5)

Use `docs/reports/<run-id>/` created in Step 5.5. All report paths in
subsequent steps use `docs/reports/<run-id>/`.

### Pre-Swarm Structural Gates (Steps 9w.5 and 9w.6)

These gates run after run-id generation and before swarm agent spawn.
Step 9w.5 checks for contradictions. Step 9w.6 checks for omissions.
Both must PASS for the swarm to launch.

### Step 9w.5: Pre-Swarm Spec Consistency Gate (MANDATORY -- SWARM ONLY)

Use the **spec-consistency-checker** agent. Pass:
1. The path to the plan document
2. `docs/reports/<run-id>/` (the reports directory created in Step 5.5)
3. BUILD_TRACKING.md is at: BUILD_TRACKING.md (for the agent's Phase Status row)

The agent writes its report to `docs/reports/<run-id>/spec-consistency-check.md`.
Read that file with `limit: 1` and check the STATUS line (line 1).
- If `STATUS: PASS`: continue to Step 9w.6. DO NOT read the full report.
- If `STATUS: FAIL`: read the full report to understand the failure, then abort
  the swarm path. Output the contradiction list. The spec author must fix the
  contradictions and re-run. Do not proceed.

### Step 9w.6: Spec Completeness Gate (MANDATORY -- SWARM ONLY)

Use the **spec-completeness-checker** agent. Pass:
1. The path to the plan document
2. `docs/reports/<run-id>/` (the reports directory created in Step 5.5)
3. BUILD_TRACKING.md is at: BUILD_TRACKING.md (for the agent's Phase Status row)

The agent writes its report to `docs/reports/<run-id>/spec-completeness-check.md`.
Read that file with `limit: 1` and check the STATUS line (line 1).
- If `STATUS: PASS`: continue to Step 9w.7. DO NOT read the full report.
- If `STATUS: FAIL`: read the full report's Details section. Fix the spec omissions
  identified in the report (add missing entries to the coverage tables). Commit the fix:
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

1. Read `docs/reports/<run-id>/spec-consistency-check.md` with `limit: 1`
   (STATUS is line 1 per Phase Report Standardization). Copy that line
   verbatim. Then normalize it by stripping all leading instances of `*`,
   `_`, `#`, and whitespace from the start of the line, and all trailing
   instances of `*`, `_`, `#`, and whitespace from the end of the line.
   Repeat until no more of these characters remain at either end.
   Do NOT strip backticks, brackets, or other characters.
   Example: `**STATUS: PASS**` → `STATUS: PASS`.
   Example: `### STATUS: FAIL -- 3 contradictions` → `STATUS: FAIL -- 3 contradictions`.
2. Read `docs/reports/<run-id>/spec-completeness-check.md` with `limit: 1`
   (STATUS is line 1). Same procedure: copy verbatim, normalize by
   iteratively stripping `*`, `_`, `#`, and whitespace from both ends.
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
5. If CLEARED: proceed to Step 9w.8.

### Step 9w.8: Spec Eval Gate (MANDATORY -- SWARM ONLY)

Test whether agents can actually follow this spec's concrete instructions.
This gate catches specs that are structurally complete (9w.6 passed) but
too vague for agents to implement correctly.

Run the spec eval gate from the project root:

1. Run: `eval-harness/.venv/bin/python3 eval-harness/spec_eval_gate.py <plan_path> --output-dir docs/reports/<run-id> --cost-cap 1.0`
2. Check exit code:
   - Exit 0 (PASS): all HIGH-confidence claims passed. Proceed to Step 9w.9.
   - Exit 1 (FAIL): read `docs/reports/<run-id>/spec-eval-*/spec-eval-gate.json`.
     The `failed_details` array lists which spec instructions agents couldn't
     follow. For each failed claim: tighten the spec instruction to be more
     concrete (e.g., "validate email" becomes "validate email with regex
     `^[\w.-]+@[\w.-]+\.\w+$`"). Commit:
     `git add docs/plans/<plan-file>`
     `git commit -m "fix: tighten vague spec instructions (spec eval gate)"`
     Re-run Step 9w.8. Max 1 retry.
   - Exit 1 (WARN_UNSCORABLE): too few testable claims extracted. The spec
     may lack concrete instructions. Proceed with caution -- log the warning
     in BUILD_TRACKING.
   - Exit 1 (RETRY): transient API errors. Re-run once.
   - Exit 2 (ENV_ERROR): environment misconfiguration (e.g., missing
     ANTHROPIC_API_KEY). Do NOT retry or attempt to fix the spec. Abort with:
     `"SPEC EVAL GATE ENV ERROR: <stderr message>"`
3. If still FAIL after retry: abort with
   `"SPEC EVAL GATE FAILED: <N> claims failed. See report for details."`

**What this catches that other gates don't:** Spec completeness (9w.6) checks
that sections exist. Spec eval gate checks that the instructions in those
sections are precise enough for agents to follow. Example: "validate email"
passes completeness but fails spec eval because it doesn't say how.

### Step 9w.9: Ghost-File Cleanup (MANDATORY -- SWARM ONLY)

Before launching swarm agents, check for files left over from prior builds
in the same repo (FC48). Ghost files from prior projects silently ship with
the new build and create import landmines.

1. Read the File Assignment Boundaries section from the plan. Collect ALL
   prescribed file paths into a set.
2. Check for unexpected files in `app/`:
   - Run: `find app/ -name "*.py" -type f` (use Bash, not Glob — need recursive)
   - Compare against the prescribed set.
   - Any `.py` file NOT in the prescribed set is a ghost file.
3. Check for unexpected directories:
   - Run: `ls app/routes/ 2>/dev/null` (common ghost from prior builds)
   - Run: `ls app/db.py 2>/dev/null` (common ghost from prior builds)
4. If ghost files found:
   - List them with: `"GHOST FILES DETECTED: [list]"`
   - Delete each one (separate Bash call per file/directory).
   - Commit: `git add -A app/` then
     `git commit -m "chore: remove ghost files from prior build (FC48)"`
5. If no ghost files: proceed to Step 10w.

**Why this matters:** Run 063 shipped 42 ghost files from BrewOps (prior build).
`app/db.py` defined a second `get_db()` pointing to `brewops.db` — a landmine.
The review caught it as P2, but it should have been caught before agents launched.

### Step 10w: Parallel Swarm Work

**PRECONDITION:** Before reading the agent assignment table, verify BOTH:
1. `docs/reports/<run-id>/gate-verification.md` exists AND contains
   `STATUS: CLEARED`.
2. `docs/reports/<run-id>/spec-eval-*/spec-eval-verification.md` exists
   AND contains `STATUS: PASS`.

If gate-verification.md is missing or BLOCKED, abort with:
`"CANNOT SPAWN: gate-verification.md missing or BLOCKED. Run Step 9w.7 first."`
If spec-eval-verification.md is missing, abort with:
`"CANNOT SPAWN: spec-eval-verification.md missing. Run Step 9w.8 first."`
These file-based checks prevent the orchestrator from skipping gates
(the exact pattern that caused Run 054's gate bypass).

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

Spawn ALL agents in a single message (parallel launch).

**Write the worker roster (write-only insurance) — BEFORE waiting for any
completion.** Immediately after the parallel spawn returns the agent ids/branches,
use the Write tool to create `docs/reports/<run-id>/worker-roster.md` mapping each
spawned worker. Worktree branches are named `worktree-agent-<agentId>`, not by role,
so this role→agentId→branch mapping otherwise lives only in volatile orchestrator
context and is lost on a mid-spawn context death. Format:

```markdown
# Worker Roster — run <run-id>
| Role | Agent ID | Branch | Worktree Path |
|------|----------|--------|---------------|
| <role> | <agentId> | worktree-agent-<agentId> | <worktree-path> |
```

One row per spawned agent. This is write-only insurance — no step consumes it in
the current pipeline; it exists so a human can reconstruct swarm state after a
mid-spawn context death. Do NOT wait for completions before writing it.

Then wait for all agents to complete. You will be notified as each finishes.

**Timeout:** If any agent has not completed after 10 minutes, report it as
a failure and proceed with the agents that did complete. Do not wait
indefinitely.

**Build worker_status list:** After all agents complete or time out, build
the `worker_status` list that will be passed to swarm-runner in Steps 11w-16w.
For each spawned agent, record one entry:

```
{ role: "<role-name>", branch: "<branch-name>", status: "COMPLETED|TIMED_OUT|FAILED" }
```

- **COMPLETED:** agent notification returned successfully
- **TIMED_OUT:** agent did not complete within 10 minutes
- **FAILED:** agent returned an error or its output contains an error status

Keep this list in memory — it is passed verbatim to the swarm-runner spawn
in Step 11w-16w. The swarm-runner skips merging TIMED_OUT or FAILED branches.

### Step 10.5w: Pre-Merge Ownership Gate

**Prerequisite:** Step 7w (swarm-planner) must have PASSED. The agent
assignments used below come from the swarm-planner output. If Step 7w
FAILed, this step is never reached (7w FAIL aborts the pipeline).

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
6. **Incremental BUILD_TRACKING:** After writing ownership-gate.md, use
   Edit tool to insert `### Ownership Gate: PASS ([N] agents)` into
   BUILD_TRACKING.md. Target: the line immediately before the `---`
   separator that follows the AGENT_STATUS section.
   If the Edit fails (old_string not found): read BUILD_TRACKING.md,
   find the correct anchor, retry once. If retry fails: FAIL with
   "BUILD_TRACKING EDIT FAILED: could not locate AGENT_STATUS separator."

### Steps 11w-16w: Assembly + Verification (DELEGATED)

The assembly merge, contract/smoke/test verification, merge-to-main, and
cleanup all run inside the **swarm-runner** agent in a fresh context window.
The orchestrator does NOT read the contract/smoke/test report files — the
swarm-runner inlines those checks and reports a single STATUS line.

**Context budget note:** This delegation saves the post-spawn tail (assembly,
verification, merge, cleanup) from loading into the orchestrator's context.
Deepening (Step 6) and worker spawn (Steps 7w-10.5w) remain inline because
they require the Agent tool. The 20+ agent context budget is NOT proven by
this design alone — the first 20+ agent build must be monitored to confirm
the orchestrator stays under budget through the inline phases. Note: the
tail-runner has NO auto-checkpoint mechanism (by design — it runs in fresh
~60K context post-swarm). If a 20+ agent review phase exhausts tail-runner
context, recovery is manual completion of remaining steps.

First capture the current branch: run `git branch --show-current` and save it
as `original_branch`.

Spawn the **swarm-runner** agent with `mode: "bypassPermissions"`. Pass:
- `plan_path`, `run_id`, `reports_dir` (`docs/reports/<run-id>/`),
  `build_tracking_path` (BUILD_TRACKING.md)
- `assembly_branch`: `swarm-<run-id>-assembly`
- `original_branch`: the branch captured above
- `worker_branches`: the list of worktree branch names
- `agent_assignments`: the `{ role, branch, files }` list from the swarm planner
- `worker_status`: per-worker completion status `{ role, branch, status }`
  where status is COMPLETED, TIMED_OUT, or FAILED (from the Step 10w spawn
  results). The swarm-runner skips merging TIMED_OUT or FAILED branches.
- `agent_pitfalls`: the pitfalls text captured in Step 1.6

Wait for the result. Search backward in the agent's output for a line starting
with `STATUS:` — this **wire STATUS is a hint, not the verdict.** The verdict comes
from disk-verifying the artifact (below), so a swarm-runner that completed the merge
but was cut off before echoing its STATUS does not fail a genuinely good run.

- If `STATUS: FAIL` and the reason starts with `contract-check:` or
  `merge-conflict:`: the swarm-runner has already aborted (no merge to main, no
  cleanup) and set `final_status` in BUILD_TRACKING.md Run State. Do NOT proceed
  to Step 17w, and do NOT disk-verify (these blocking classes abort BEFORE writing
  `assembly-summary.md`, and a stale prior-run summary must not mask the abort). The
  run ends. (These are the two blocking failure classes — see CLAUDE.md Escalation
  Rules.)
- **Otherwise — for EVERY other outcome — DO NOT abort on the wire. Disk-verify first.**
  The blocking classes above are the ONLY wire-driven aborts in this handler. All of
  the following wire outcomes route identically to the disk-verify below — none of them
  aborts the run by itself:
  - wire `STATUS: PASS` → disk-verify (no abort here)
  - a non-blocking wire `STATUS: FAIL` (any reason other than the two blocking classes)
    → disk-verify (no abort here)
  - wire STATUS missing, truncated, or garbled → disk-verify (no abort here)

  **Disk-verify the assembly summary as the authoritative verdict.** Run as a single
  Bash call:
  ```
  python3 tools/verify_delegated_status.py \
    --artifact docs/reports/<run-id>/assembly-summary.md --artifact-kind assembly \
    --run-start-ts <run_start_ts> --run-id <run-id> --wire-status "<wire status or 'none'>"
  ```
  - **Exit 0:** the merge genuinely completed → proceed to Step 17w. DO NOT read the
    full report. (Smoke/test failures, if any, are noted in `assembly-summary.md` and
    reviewed by the tail.)
  - **Any non-zero exit → the run fails.** This abort is driven by the SCRIPT's exit
    code (the DISK verdict: missing/stale/run-id mismatch/FAIL status), NOT by the wire
    STATUS. Output the script's printed reason. Trust the exit code; do not re-decide
    from the wire STATUS.

The swarm-runner agent file is the single source of truth for
assembly/verification logic. Do NOT reintroduce inline Steps 11w-16w here.

### Step 17w: Delegate Shared Tail (SWARM ONLY)

Use the **tail-runner** agent to execute the entire Shared Tail in a
fresh context window.

Pass these parameters in the prompt:
- run_id, plan_path, reports_dir, build_tracking_path
- project_name, date, branch
- feed_forward_risk (from plan frontmatter)

Spawn with `mode: "bypassPermissions"`. Do NOT set `isolation` or
`run_in_background` — the agent operates on the current branch and
the orchestrator must wait for its result.

**Branch precondition:** Before spawning, verify that HEAD is on
`original_branch` — the swarm-runner merged the assembly branch into it on
success. Smoke/test failures are non-blocking: the swarm-runner still merges to
main and returns `STATUS: PASS` with failures noted in `assembly-summary.md`, so
the tail-runner reviews the merged code on the main branch. Any worker branches
the swarm-runner preserved (TIMED_OUT/FAILED workers) exist only for manual
inspection and are NOT the review target.

A blocking failure (`contract-check:` or `merge-conflict:`) means the
swarm-runner aborted WITHOUT merging to main. In that case the orchestrator
already ended the run at the Steps 11w-16w handler and never reaches Step 17w.

Wait for the agent to complete. Read its output and note its terminal STATUS line
if present — but treat it as a **hint, not the verdict.**

### Step 18w: Verify Tail Result (SWARM ONLY — MANDATORY GATE)

The verdict is the **on-disk `self-audit.md`**, not the tail-runner's echoed wire
STATUS. The tail-runner finishes its work and writes `self-audit.md` (via
`/verify-self-audit`) but can be cut off before echoing its Output Contract; a
"no STATUS line → FAIL" reading would fail a genuinely complete run. So disk-verify
the artifact. Run as a single Bash call:

```
python3 tools/verify_delegated_status.py \
  --artifact docs/reports/<run-id>/self-audit.md --artifact-kind self-audit \
  --run-start-ts <run_start_ts> --run-id <run-id> --wire-status "<wire status or 'none'>"
```

- **Exit 0:** the tail genuinely completed → output `<promise>DONE</promise>` and stop.
- **Any non-zero exit:** the run fails. The script prints the specific reason
  (missing/unreadable artifact, stale leftover from a prior aborted run at this reused
  run-id, run-id mismatch, or a `PIPELINE_FAIL` status). Output that reason. Trust the
  exit code; do NOT second-guess it from the wire STATUS, and do NOT fail merely because
  the wire STATUS line was absent.

The script confirms only existence + freshness + run-id + non-FAIL terminal status.
Deferred-risk adjudication stays owned by `/verify-self-audit` (already run inside the
tail-runner); `PIPELINE_PASS_WITH_DEFERRED_RISK` is a pass and the script treats it as
such — do not re-adjudicate WARN dispositions here.

---

## Shared Tail (SOLO ONLY — swarm path delegates via Step 17w)

**Swarm builds:** Do NOT run the Shared Tail inline. Instead, proceed to
Step 17w (Delegate Shared Tail) which spawns the tail-runner agent.
The steps below only run inline for solo builds.

<!-- TAIL_SYNC_POINT: The Shared Tail STEPS below (review/compound/learnings) are
duplicated in .claude/agents/tail-runner.md (swarm path). Changes to those steps MUST
be mirrored there, and vice versa.
NOTE (Plan A, 2026-06-06): terminal-gate VERIFICATION authority now differs by path and
is intentionally NOT symmetric. The SWARM tail is verified by disk-verifying self-audit.md
(Step 18w, via tools/verify_delegated_status.py). The SOLO tail below runs inline and
produces self-audit.md itself, so there is no delegated wire STATUS to verify — solo
verification is unchanged. Do not "sync" the disk-verify into the solo path. -->

### Review

Run `/workflows:review`

The review agents should scrutinize any areas flagged in the plan's
Feed-Forward "least confident" item. After review completes, verify that
review findings reference the Feed-Forward risk if applicable.

**Incremental BUILD_TRACKING:** After review completes, use Edit tool to
insert `### Review: [P1_count] P1, [P2_count] P2 | Fix commits: [hashes]`
into BUILD_TRACKING.md. Target: the line immediately before the `---`
separator that follows the AGENT_STATUS section. If the Edit fails: read
BUILD_TRACKING.md, find the correct anchor, retry once. If retry fails:
FAIL with "BUILD_TRACKING EDIT FAILED."

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

**Swarm builds skip this step** — BUILD_TRACKING is filled by the
tail-runner agent (Step 17w, tail-runner Step 6).

For solo builds: fill AGENT_STATUS, FAILURES, and RUN_METRICS sections
now. Read plan, review findings, and report files to populate all three
sections.

### Context-Budget Checkpoint -- Pre-Audit (SOLO ONLY)

**Swarm builds skip this step** — the tail already runs in a fresh
agent context via Step 17w.

Calculate orchestration load:
- `swarm_agents` = number of agents spawned in Step 10w (count from assignment table; 0 for solo)
- `deepening_agents` = number of agents spawned in Step 6 (count from deepen-plan output, default 4)
- `review_agents` = number of review agents spawned during Review
- `fix_retries` = number of inline verification fix retries during the work phase (0 for solo — assembly-fix is not used in the solo path; swarm inlines fixes inside swarm-runner)
- `load = swarm_agents + (deepening_agents * 2) + (review_agents * 1.5) + (fix_retries * 3)`

If `load > 30`:

1. Identify the solution doc written by Compound (most recent file in `docs/solutions/`).
2. Use Write tool to create CHECKPOINT.md with all paths from current run state:

```yaml
---
status: PAUSED_FOR_CONTEXT
run_id: "<run-id from Step 5.5>"
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
1. The run-id (from Step 5.5)
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

### Advisory Audit (non-blocking, best-effort)

Run `/advisory-audit report <run-id>`

This generates the post-run advisory report comparing current state against
the baseline captured in Step 1.55. Cannot fail the run -- if anything
errors, it logs what it can and proceeds to Done.

### Done

Output `<promise>DONE</promise>` -- all phases complete.
