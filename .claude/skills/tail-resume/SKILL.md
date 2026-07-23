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

### Step 0: Wave-Resume (MULTI-WAVE runs — MANDATORY FIRST; plan §5)

Applies only when the run is multi-wave (`waves: N`, N > 1 in the plan, or
`<reports_dir>/w*/transition-state.json` files exist). Single-wave runs SKIP this step.

- **R0 (ALWAYS FIRST): re-assert the firebreak ACTIVE.** Run
  `python3 .claude/hooks/firebreak-activate.py status --root <MAIN>`. Exit 3 ⇒ ABORT
  (wrong root). `INACTIVE` ⇒ `activate <run-id> --root <MAIN>` then re-read; still not
  `ACTIVE` ⇒ ABORT. Only proceed once ACTIVE.
- **R1: stop ALL run-scoped tasks — including pre-persist spawns.** Query `TaskList`
  for every task whose name matches `swarm-<run-id>-*` (NOT only the ids recorded in
  transition-state — a crash during `spawn_in_progress` may have spawned workers whose
  ids were never written). `TaskStop` + confirm each; prove zero live before anything
  else. Unprovable ⇒ ABORT.
- **Route per wave:** for each `w<k>/transition-state.json`, follow the plan §5
  resume machine (absent ⇒ start wave; `roster_prepared`/`spawn_in_progress`/
  `workers_terminal` ⇒ prove-zero-live then resume; `assembly_started` ⇒
  ambiguous-assembly recovery, never re-assemble onto an advanced branch;
  `merge_completed` ⇒ resume at provenance; `artifact_emitted` ⇒ compare-and-reuse
  vs conflicting-abort; `wave_verified`/`readback_ok` ⇒ wave complete; `abort` ⇒ stay
  aborted). If waves remain incomplete, hand control back to the autopilot SKILL's
  Multi-Wave Barrier Loop at the resolved wave; only once ALL N waves are
  `wave_verified` do you continue to the tail steps below.

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

### Step 2b: Wave Reconcile (MULTI-WAVE runs — MANDATORY GATE, fail-closed; plan §7)

Multi-wave runs only (single-wave SKIP). Run the tail reconcile gate:

`python3 tools/verify_wave.py --reconcile --plan <plan_path> --spec-path <spec_path>
--reports-dir <reports_dir> --root <MAIN> --run-id <run_id> --run-start-ts <epoch>
--original-branch <feature> --default-branch <default>`

It re-verifies every wave (waves `1..N-1` `assembled_output_sha` must be ANCESTORS of
`<original_branch>` HEAD, only wave N EQUALS HEAD) and the end-to-end SHA chain.
**Fail-closed:** if it is not `STATUS: PASS`, FAIL the run with
`"WAVE RECONCILE FAILED: [reason]"` — do NOT proceed to self-audit with a passing claim.

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
