---
name: tail-resume
description: Resume autopilot tail from CHECKPOINT.md after context death. Manual invocation only.
argument-hint: "[path to CHECKPOINT.md, default: ./CHECKPOINT.md]"
allowed-tools: Read Edit Write Glob Grep Bash Agent
---

# Tail Resume

Resume the autopilot's mandatory tail steps from a CHECKPOINT.md file written
by a context-budget checkpoint gate. This skill reads explicit artifact paths
from CHECKPOINT.md -- no "most recent" discovery heuristics.

## Arguments

<checkpoint_path> #$ARGUMENTS </checkpoint_path>

Parse arguments:
- If a path is given, use it as the CHECKPOINT.md path
- If blank, use `./CHECKPOINT.md`

## Prerequisites

1. Read CHECKPOINT.md at the parsed path. If it doesn't exist, abort:
   `"ABORT: No CHECKPOINT.md found at [path]. Nothing to resume."`
2. Verify `status: PAUSED_FOR_CONTEXT` in frontmatter. If different, abort:
   `"ABORT: CHECKPOINT.md status is [status], not PAUSED_FOR_CONTEXT."`
3. Extract all fields from CHECKPOINT.md into local variables:
   `run_id`, `plan_path`, `solution_doc_path`, `review_summary_path`,
   `reports_dir`, `build_tracking_path`, `handoff_path`

## Bash Command Rules (MANDATORY)

Same rules as autopilot. One command per Bash call. No `cd &&`, no loops,
no `python3 -c`. Use `git -C` for directory switching. Full paths always.

## Steps

Execute steps in order. The only valid `next_step` value is "Verify BUILD_TRACKING"
(post-learnings, post-fill). Compound, Update Learnings, Verify Learnings, and
BUILD_TRACKING fill have all completed before the checkpoint fires.

### Step 1: Validate Resume Point (MANDATORY)

Read `next_step` from CHECKPOINT.md.
- If "Verify BUILD_TRACKING": proceed to Step 2.
- Any other value: abort with:
  `"ABORT: tail-resume only supports next_step='Verify BUILD_TRACKING'. Got: [value]."`

### Step 2: Verify BUILD_TRACKING.md Completeness (MANDATORY GATE)

Read BUILD_TRACKING.md. Verify:
1. `## AGENT_STATUS` section has at least one agent row
2. `## FAILURES` section exists (may contain "None")
3. `## RUN_METRICS` section has at least one metric row

If any section is missing or empty, FAIL with:
`"BUILD_TRACKING INCOMPLETE: [section name] is missing or empty."`

### Step 3: Self-Audit (MANDATORY -- DO NOT SKIP)

Use the **self-audit-reviewer** agent. Pass these six arguments from
CHECKPOINT.md:
1. `run_id`
2. `reports_dir`
3. `plan_path`
4. `solution_doc_path`
5. `build_tracking_path`
6. `handoff_path`

Spawn the agent with `mode: "bypassPermissions"`.

The agent writes `<reports_dir>/self-audit.md`. Read that file and check STATUS.
- If STATUS contains PASS: proceed to Step 6.
- If STATUS contains FAIL: FAIL the run with the agent's error message.

### Step 4: Verify Self-Audit (MANDATORY GATE)

Run `/verify-self-audit <run_id> <reports_dir>`

Check its output. If STATUS: FAIL, the run fails. Do NOT proceed to Done.

### Step 5: Done

Output: `<promise>DONE</promise> (resumed from CHECKPOINT.md)`
