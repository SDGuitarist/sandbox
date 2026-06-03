---
title: "Autopilot Context Death Solution"
date: 2026-06-03
status: plan
type: plan
swarm: false
brainstorm: docs/brainstorms/2026-06-03-autopilot-context-death-solution-brainstorm.md
spike: docs/reports/spike-nested-worktree-delegation.md
feed_forward:
  risk: "Reduced swarm-runner scope (Steps 11w-16w only) may not save enough context for 20+ agent builds; Tier 1 output contract compliance depends on agent instruction-following"
  verify_first: true
---

# Autopilot Context Death Solution -- Plan

## Deepening Summary

**Deepened on:** 2026-06-03
**Research agents used:** 6 (frontmatter reliability, agent output contracts, skill invocation viability, architecture review, simplicity review, Edit tool failure patterns)

### Key Changes From Deepening

1. **Dropped YAML frontmatter from BUILD_TRACKING.md.** Research found zero
   precedent for programmatic YAML editing in this codebase. All BUILD_TRACKING
   state uses markdown tables and section-based appends. YAML frontmatter
   would introduce parsing complexity, concurrent edit hazards, and a
   validation burden that doesn't exist today. Replaced with structured
   markdown sections that match the proven pattern.

2. **Simplified Tier 1 decision line.** Research found all 7 existing agents
   use plain-text `STATUS: PASS/FAIL` lines, not pipe-delimited formats.
   The pipe-delimited line was overengineered. Replaced with multi-line
   key-value output matching the tail-runner's proven 2-line pattern.

3. **Redesigned deepen-runner after Agent tool gap confirmed.** The spike
   (`docs/reports/spike-nested-worktree-delegation.md`) proved sub-agents do
   NOT have the Agent tool. The deepen-plan skill requires the Agent tool to
   spawn research sub-agents. Fix: keep deepening inline in the orchestrator,
   delegate only merge/commit/audit to a `deepen-merge-runner` agent (swarm
   only — solo merges inline per "What Must Not Change #9"). The swarm-runner
   performs verification inline (Bash/Read/Grep) — no Agent tool needed for
   contract checks, smoke tests, or test suites.

4. **Removed frontmatter validation protocol.** Since BUILD_TRACKING no longer
   uses YAML frontmatter, the V1-V4 validation steps are unnecessary. State
   is stored in markdown sections that use the same Edit patterns already
   proven reliable across 15+ builds.

## What Is Changing

Three changes to the autopilot system, shipped in three stages:

1. **No-read orchestrator discipline** -- SKILL.md instructions that prevent
   the orchestrator from reading full phase reports on PASS (Stage 1a).
2. **Bounded agent summary contracts** -- Agent files return 2 lines
   (`report_path` + `STATUS`) and write one Phase Status table row to
   BUILD_TRACKING.md instead of returning full reports (Stage 1).
3. **Hybrid delegation** -- Two new agents (deepen-merge-runner, swarm-runner)
   run heavy phases in fresh context for swarm builds. Deepening research
   stays inline (needs Agent tool). Solo builds remain fully inline.
   Context savings come primarily from Stage 1 and Stage 3. Stage 2 is a
   structural consistency choice for swarm only.

### Files Modified

| File | Change | Stage |
|------|--------|-------|
| `.claude/skills/autopilot/SKILL.md` | Add `limit: 1` after phase report reads (9w.5-9w.7); add Step 1.5 Phase Status insertion; move run-id to Step 5.5; add Step 6.03 (swarm-only deepen-merge-runner) + Step 6.03s (solo inline merge) + Step 6.08 (self-review commit); replace Steps 11w-16w with swarm-runner spawn; pass `build_tracking_path` to gate agents; update all "Step 6.1" refs to "Step 5.5" | 1, 2, 3 |
| `.claude/agents/spec-consistency-checker.md` | Add Tier 1/Tier 2 output contract | 1 |
| `.claude/agents/spec-completeness-checker.md` | Add Tier 1/Tier 2 output contract | 1 |
| `.claude/agents/deepen-merge-runner.md` | **New file.** Merges deepening corrections into plan, commits, writes audit trail. | 2 |
| `.claude/agents/swarm-runner.md` | **New file.** Runs assembly + verification in fresh context (Steps 11w-16w). | 3 |

### Files NOT Modified (solo path preserved)

| File | Why untouched |
|------|---------------|
| Solo path in SKILL.md (Step 7s, Shared Tail) | Solo builds don't hit context limits. Inline execution unchanged. |
| `.claude/agents/tail-runner.md` | Already works. No changes in this plan. (Latent Agent-tool bug is a separate investigation.) |
| `.claude/agents/self-audit-reviewer.md` | Unchanged. |
| `.claude/agents/brainstorm-refinement.md` | Unchanged. |
| `.claude/agents/spec-contract-checker.md` | Superseded by Stage 3: swarm-runner inlines contract check. Agent file stays for potential future solo use but is not invoked in swarm path. |
| `.claude/agents/smoke-test-runner.md` | Superseded by Stage 3: swarm-runner inlines smoke test. Same rationale. |
| `.claude/agents/test-suite-runner.md` | Superseded by Stage 3: swarm-runner inlines test suite. Same rationale. |
| `.claude/agents/assembly-fix.md` | Not invokable from swarm-runner: sub-agents lack the Agent tool (spike confirmed). swarm-runner resolves merge conflicts inline instead. Agent file stays for potential future solo use but is not spawned in the swarm path. |

## What Must Not Change

1. Required artifacts: BUILD_TRACKING, solution doc, learnings, HANDOFF, self-audit.
2. Compound engineering phases: brainstorm, plan, work, review, compound, learnings.
3. Swarm worktree isolation: workers in isolated worktrees, spawned by orchestrator.
4. Tail delegation: tail-runner owns review through self-audit.
5. Agent pitfalls injection in every agent brief.
6. Pre-swarm gates (consistency + completeness) must pass before swarm launch.
7. Ghost file cleanup (Step 9w.8).
8. Incremental BUILD_TRACKING: agent status rows via Edit tool after each merge.
9. Solo build inline execution path.

## Orchestration State: Markdown Sections, Not YAML Frontmatter

### Deepening Research Finding

The brainstorm proposed YAML frontmatter in BUILD_TRACKING.md. Research
found this is a risky departure: zero precedent for programmatic YAML
editing in this codebase. All BUILD_TRACKING edits use markdown tables
and section-based appends. The validation protocol was solving a problem
we'd be creating.

### The Revised Approach

Orchestration state lives in a dedicated `## Phase Status` section in
BUILD_TRACKING.md, using the same markdown table format already proven
across 15+ builds:

```markdown
## Phase Status

| Phase | Status | Report Path |
|-------|--------|-------------|
| deepen | PASS | docs/reports/065/deepening-applied.md |
| gates | CLEARED | docs/reports/065/gate-verification.md |
| swarm | IN_PROGRESS | -- |
| tail | NOT_STARTED | -- |

**Run State:**
- run_id: 065
- plan_path: docs/plans/2026-06-03-context-death-plan.md
- branch: master
- context_proxy_chars: 142000
- manual_resume: false
- final_status: null
```

**Why markdown over YAML:**
1. Markdown tables are the proven state format in this codebase (15+ builds).
2. Edit tool anchor mismatches are the known failure mode. Markdown sections
   use the same `---` separator anchors already reliable in SKILL.md.
3. No YAML parser needed. Agents read the table rows directly.
4. Phase agents append rows to the Phase Status table (same pattern as
   AGENT_STATUS rows). No concurrent edits on the same field.
5. Run State fields are key-value lines that agents can grep for.

**Edit pattern:** Each phase writes one new table row using the Edit tool,
targeting the line before the blank line after the table. Same anchor
pattern as the AGENT_STATUS table inserts. On anchor failure: read the
file, find the correct insertion point, retry once.

### Phase Reports: STATUS on Line 1

Phase reports (gate checks, smoke tests, contract checks) MUST NOT have
YAML frontmatter. Line 1 is always the STATUS line: `STATUS: PASS` or
`STATUS: FAIL -- <reason>`. No markdown formatting around the STATUS value.
This rule is unchanged from the brainstorm.

## Two-Tier Summary Contract

### Research Insights

1. All 7 existing agents use plain-text `STATUS: PASS/FAIL` lines. The
   tail-runner's 2-line contract (path + STATUS) is the most reliable.
2. `blocking`, `retry`, and `next_step` fields are unnecessary -- the
   orchestrator already knows retry policy from SKILL.md step definitions.
   Encoding them in the agent's return value creates a second source of
   truth that can drift from SKILL.md. (Simplicity review finding.)
3. The orchestrator should search backward for `STATUS:` in the agent's
   output, not rely on "last line." Agents sometimes append trailing text.
   This matches how gate-verification already parses report files.
   (Architecture review finding.)

### Agent Return Contract (Follows Tail-Runner Pattern)

Every agent that returns results to the orchestrator follows the same
2-field pattern the tail-runner already uses in production:

```
report_path: docs/reports/065/smoke-test.md
STATUS: PASS
```

Or on failure:
```
report_path: docs/reports/065/smoke-test.md
STATUS: FAIL -- 3 routes returned 500
```

**Rules:**
- `STATUS` line contains `PASS` or `FAIL -- <reason>`.
- `report_path` is the full report on disk (always written by the agent).
- The orchestrator searches backward from the end of the agent's output
  for a line starting with `STATUS:`. This is robust against trailing text.
- On PASS, the orchestrator proceeds to the next SKILL.md step. It does
  NOT read the report file.
- On FAIL, the orchestrator reads the full report at `report_path` and
  follows the step's existing retry policy in SKILL.md.
- No `blocking`, `retry`, or `next_step` fields. The orchestrator owns
  retry logic -- agents just report outcomes.

### Phase Status Row (Written to BUILD_TRACKING.md)

Before returning, the agent writes one row to the Phase Status table in
BUILD_TRACKING.md using the Edit tool. Same append pattern as AGENT_STATUS
rows -- proven across 15+ builds.

| Column | Description |
|--------|-------------|
| Phase | Phase name (e.g., deepen, swarm, tail) |
| Status | PASS or FAIL |
| Report Path | Path to the full report file |

All detail (counts, merge_status, preserved_branches, cleanup_status)
goes into the report file on disk, NOT into BUILD_TRACKING.md. This
minimizes Edit operations and avoids anchor-mismatch failures.

## Stage 1: No-Read Discipline + Output Contracts (Merged)

Stages 1a and 1b from the brainstorm are merged into a single stage.
Research found most agents already emit STATUS on line 1 -- the
"standardize" and "add contracts" changes are small enough to ship together.

### No-Read Discipline

### Changes to SKILL.md

For each step that reads a phase report, add these instructions immediately
after the Read call:

```
Read `<report-path>` with `limit: 1`. Check the STATUS line.
- If `STATUS: PASS`: proceed to Step [next]. DO NOT read the full report.
- If `STATUS: FAIL`: read the full report to understand the failure.
```

**Steps that need this change:**

| Step | Report File | Current Behavior | New Behavior |
|------|------------|-----------------|-------------|
| 9w.5 | spec-consistency-check.md | Reads full file, checks STATUS | `limit: 1`, proceed on PASS |
| 9w.6 | spec-completeness-check.md | Reads full file, checks STATUS | `limit: 1`, proceed on PASS |
| 9w.7 | gate-verification.md | Reads full file, checks STATUS | `limit: 1`, proceed on PASS |

Steps 12w-14w (contract check, smoke test, test suite) are removed from this
table. Stage 3 moves those checks inside swarm-runner, which performs them
inline — the orchestrator never reads those report files.

### Phase Report Standardization

Add a rule to the top of SKILL.md (in the Rules section):

```
Phase reports MUST NOT have YAML frontmatter. Line 1 is always the STATUS
line: `STATUS: PASS` or `STATUS: FAIL -- <reason>`. No markdown formatting
around the STATUS value.
```

Update each agent that writes reports to follow this rule (spec-consistency-checker,
spec-completeness-checker). The STATUS line is already line 1 in most agents --
verify and fix any that have preamble text before STATUS. The three verification
agents (spec-contract-checker, smoke-test-runner, test-suite-runner) are superseded
by Stage 3 inline checks and are not modified.

### Agent Output Contracts

For each agent in the table below, add an `## Output Contract` section:

```markdown
## Output Contract

1. Write the full report to `<report-path>` with STATUS on line 1.
2. Write one row to the Phase Status table in BUILD_TRACKING.md via Edit tool.
3. End your output with: `report_path: <path>` then `STATUS: PASS` or `STATUS: FAIL -- <reason>`.
```

| Agent | Phase Status Row | Detail in Report |
|-------|-----------------|------------------|
| spec-consistency-checker | `gates-consistency \| PASS \| <path>` | Contradiction count, per-section findings |
| spec-completeness-checker | `gates-completeness \| PASS \| <path>` | Omission count, per-surface findings |

**Not in scope:** spec-contract-checker, smoke-test-runner, and test-suite-runner
are superseded by Stage 3 (swarm-runner inlines their checks). assembly-fix is
also not modified: it cannot be spawned from swarm-runner (sub-agents lack the
Agent tool), so swarm-runner resolves merge conflicts inline. All four agent
files are unchanged and are not invoked in the swarm path after Stage 3.

### Phase Status Insertion (added to SKILL.md Step 1.5)

The global template (`~/.claude/docs/autopilot-tracking-template.md`) is NOT
modified. Instead, after Step 1.5 writes BUILD_TRACKING.md from the template,
a new sub-step inserts the Phase Status section into the local copy:

6. Use Edit tool to insert the Phase Status section between Run Info and
   AGENT_STATUS. Target: the line immediately before `## AGENT_STATUS`:

```markdown
## Phase Status

| Phase | Status | Report Path |
|-------|--------|-------------|

**Run State:**
- run_id: [TBD]
- plan_path: [TBD]
- branch: [TBD]
- context_proxy_chars: 0
- manual_resume: false
- final_status: null
```

7. Fill Run State fields where known (plan_path, branch). run_id is populated
   later in Step 5.5; leave as [TBD] until then.

Phase agents append rows to the Phase Status table as they complete. The
orchestrator updates `context_proxy_chars` at each phase boundary:
1. Read BUILD_TRACKING.md. Find the line starting with `- context_proxy_chars:`.
2. Use Edit tool with old_string set to the exact current line content and
   new_string set to the updated value.
This avoids hardcoding the previous value (which changes after each update).

### SKILL.md Agent Invocation Updates

Every agent invocation in SKILL.md that involves an agent with a Phase Status
row contract must pass `build_tracking_path` (the path to BUILD_TRACKING.md)
in its prompt. Steps affected:

| Step | Agent | Addition |
|------|-------|----------|
| 9w.5 | spec-consistency-checker | Add: "BUILD_TRACKING.md is at: BUILD_TRACKING.md" |
| 9w.6 | spec-completeness-checker | Add: "BUILD_TRACKING.md is at: BUILD_TRACKING.md" |

Steps 12w-14w are removed (superseded by Stage 3 inline checks inside
swarm-runner, which already receives `build_tracking_path` as an input).
assembly-fix is out of scope (not spawned in the swarm path — see Files NOT
Modified), so it needs no changes.

## Stage 2: Deepening Merge (swarm-only delegation)

### Why swarm-only?

The `/compound-engineering:deepen-plan` skill spawns research sub-agents via
the Agent tool. The spike (`docs/reports/spike-nested-worktree-delegation.md`)
proved sub-agents do NOT have the Agent tool. Therefore deepening MUST run
inline in the orchestrator (both solo and swarm).

After deepening, the merge/commit/audit work is a structural choice:
- **Solo:** Runs merge inline. Solo builds don't hit context limits, and
  delegating a ~5-step merge adds spawn overhead for zero benefit. This
  preserves "What Must Not Change #9: Solo build inline execution path."
- **Swarm:** Delegates merge to deepen-merge-runner. This saves no
  meaningful context (the orchestrator already carries the deepening outputs),
  but keeps a consistent delegation pattern: every swarm phase beyond gates
  runs in a fresh context window. The real context savings come from
  Stage 1 (no-read discipline) and Stage 3 (swarm-runner).

### Step Reordering

Move Step 6.1 (Generate Run ID and Reports Directory) before Step 6 so that
`run_id` and `reports_dir` exist before the merge agent needs them:

- **Step 5.5:** Generate Run ID and Reports Directory (was Step 6.1, content
  identical). Also update Run State in BUILD_TRACKING.md: fill `run_id` field.
- **Step 6:** Deepen Plan (runs inline -- orchestrator invokes
  `/compound-engineering:deepen-plan`). After deepening completes, the
  orchestrator extracts a compressed summary of corrections.
- **Step 6.03:** Merge Deepening (DELEGATED — SWARM ONLY. Solo uses 6.03s.)
- **Step 6.03s:** Merge Deepening (INLINE — SOLO ONLY. Same as current 6.5.)
- **Step 6.05:** Plan Self-Review Pass 1 (unchanged).
- **Step 6.07:** Plan Self-Review Pass 2 (body unchanged; closing pointer
  "proceed to Step 6.1" → "proceed to Step 6.08").
- **Step 6.08:** Commit self-review edits (new -- see below).
- **Step 6.5:** REMOVED (replaced by 6.03/6.03s).

**Cross-reference updates for Step 6.1 → Step 5.5:** Run
`grep -n "Step 6.1" .claude/skills/autopilot/SKILL.md` and update ALL hits.
The following SKILL.md locations reference "Step 6.1":
- Step 6.1 heading itself (becomes Step 5.5)
- Step 7s.0: "run-id now generated in Step 6.1" → "Step 5.5"
- Step 8w: "run-id from Step 6.1" → "Step 5.5"
- Step 9w: "created in Step 6.1" → "Step 5.5"
- Step 9w.5: "the reports directory created in Step 6.1" → "Step 5.5"
- Step 9w.6: "the reports directory created in Step 6.1" → "Step 5.5"
- CHECKPOINT.md template (solo Shared Tail): `run_id: "<run-id from Step 6.1>"`
  → "Step 5.5"
- Self-Audit step (solo Shared Tail): "The run-id (from Step 6.1)" → "Step 5.5"

**SPECIAL CASE — not a rename:** Step 6.07's closing line currently reads
"proceed to Step 6.1" (a control-flow pointer, not a run-id citation). Because
run-id now runs at Step 5.5 (before Step 6), after self-review pass 2 the
orchestrator must continue to the new self-review commit step. Change this line
to **"proceed to Step 6.08"** — NOT to Step 5.5.

### Agent Spec: `.claude/agents/deepen-merge-runner.md`

```yaml
---
name: deepen-merge-runner
description: Merges deepening corrections into the plan file, commits, writes audit trail and Phase Status row. Swarm-only.
tools: Bash, Read, Write, Edit
model: sonnet
---
```

**Inputs (passed in orchestrator's prompt):**
- `plan_path` -- path to the plan document
- `reports_dir` -- path to reports directory (for deepening-applied.md)
- `run_id` -- for commit messages and audit trail
- `build_tracking_path` -- path to BUILD_TRACKING.md
- `corrections` -- structured list of corrections in this format:

```markdown
### <Section Name>
**Change:** <what to edit — old text → new text, or addition>
**Rationale:** <why the deepening agent recommended this>
```

One `### <Section Name>` block per correction. The agent uses Edit tool to
apply each change, matching the section heading as anchor. On Edit failure
(anchor not found): read the plan file, find the correct location, retry once.

**Steps:**
1. Read the plan at `plan_path`.
2. For each correction in `corrections`, apply the edit to the relevant
   section using the Edit tool.
3. Write `<reports_dir>/deepening-applied.md` with a summary of what changed
   and why (audit trail).
4. Commit the rewritten plan and audit trail:
   `git add docs/plans/<plan-file> docs/reports/<run-id>/deepening-applied.md`
   `git commit -m "chore: merge deepening corrections into plan"`
5. Write one row to the Phase Status table in BUILD_TRACKING.md:
   `| deepen | PASS | <reports_dir>/deepening-applied.md |`
6. Return Tier 1 key-value lines:

**Output contract:**
```
report_path: <reports_dir>/deepening-applied.md
STATUS: PASS
```

### SKILL.md Changes for Stage 2

```
### Step 5.5: Generate Run ID and Reports Directory (MANDATORY)

(Content identical to current Step 6.1. Moved here so run_id and reports_dir
exist before deepening.)

Count the files in `docs/solutions/` and add 1. Zero-pad to 3 digits. This is
the `run-id` (e.g., 21 solutions = run `022`). Create `docs/reports/<run-id>/`.

After creating the directory, update BUILD_TRACKING.md Run State: replace
`- run_id: [TBD]` with `- run_id: <run-id>`.

### Step 6: Deepen Plan (INLINE)

Run `/compound-engineering:deepen-plan`. After deepening completes, extract
a compressed correction summary from the deepening outputs: for each section
that changed, note the section name, the change, and the rationale. Use this
format for each correction:

  ### <Section Name>
  **Change:** <old text → new text>
  **Rationale:** <why>

### Step 6.03: Merge Deepening (DELEGATED — SWARM ONLY)

If `swarm: true` in plan frontmatter:

Spawn the **deepen-merge-runner** agent. Pass: plan_path, reports_dir, run_id,
build_tracking_path, and the correction summary from Step 6. Spawn with
`mode: "bypassPermissions"`. Wait for result.

Search backward in the agent's output for a line starting with `STATUS:`.
- If STATUS: PASS, proceed to Step 6.05.
- If STATUS: FAIL, find `report_path:` in the output. Read the full report.
  Re-spawn once (max 1 retry). On second FAIL, abort.

### Step 6.03s: Merge Deepening (INLINE — SOLO ONLY)

If `swarm: false` or `swarm:` is missing:

Merge all accepted corrections into the plan file in-place (same logic as
current Step 6.5). Write `docs/reports/<run-id>/deepening-applied.md` with
the audit trail. Commit the rewritten plan and audit trail. Proceed to 6.05.

### Step 6.05: Plan Self-Review Pass 1 (unchanged)

### Step 6.07: Plan Self-Review Pass 2 (exit pointer updated)

Body unchanged EXCEPT the closing line "proceed to Step 6.1" becomes
"proceed to Step 6.08" (run-id moved to Step 5.5; the next step is now the
self-review commit).

### Step 6.08: Commit Self-Review Edits (MANDATORY)

If Steps 6.05/6.07 produced any plan edits, commit them:
  `git add docs/plans/<plan-file>`
  `git commit -m "chore: plan self-review edits"`

If no edits were made, skip. This ensures self-review changes are not left
uncommitted after the deepening merge commit (Step 6.03/6.03s).
```

Remove inline Step 6.1 (now Step 5.5) and Step 6.5 (now 6.03/6.03s).

## Stage 3: swarm-runner Agent

### Agent Spec: `.claude/agents/swarm-runner.md`

```yaml
---
name: swarm-runner
description: Runs assembly merge, verification (contract + smoke + test), merge to main, and cleanup in a fresh context window. Spawned after workers complete.
tools: Bash, Read, Write, Edit, Grep, Glob, Skill
model: sonnet
---
```

**Inputs (passed in orchestrator's prompt):**
- `plan_path` -- path to the deepened plan
- `run_id` -- for branch names and reports
- `reports_dir` -- for report outputs
- `build_tracking_path` -- path to BUILD_TRACKING.md
- `assembly_branch` -- name of the assembly branch to create
- `original_branch` -- branch to merge assembly back into
- `worker_branches` -- list of worktree branches to merge (names only)
- `agent_assignments` -- list of `{ role, branch, files }` for each worker
- `worker_status` -- per-worker completion status: `{ role, branch, status }`
  where status is COMPLETED, TIMED_OUT, or FAILED. The swarm-runner skips
  merging branches marked TIMED_OUT or FAILED. (Architecture review finding:
  the orchestrator knows this from spawn results but must serialize it for
  the swarm-runner.)
- `agent_pitfalls` -- pitfalls text for injection into sub-agent briefs

**Derived from `plan_path`:** The swarm-runner reads the plan to extract:
- Prescribed route list (for smoke testing -- method + path + expected status)
- Test command (for test suite -- e.g., `.venv/bin/pytest`)
- Export names, cross-boundary wiring, import paths (for contract checking)

**Scope: Steps 11w-16w only.** The orchestrator has already completed:
- Steps 7w-9w.8 (swarm planner, gates, ghost cleanup)
- Step 10w (worker spawn -- orchestrator keeps this, sub-agents lack Agent tool)
- Step 10.5w (ownership gate -- orchestrator runs this before spawning swarm-runner)

**Steps:**
1. Read the plan and worker branch list.
2. Create the assembly branch: `git checkout -b <assembly_branch>`.
3. For each worker branch, merge it: `git merge --no-ff <branch>`.
   After each merge, write an AGENT_STATUS row to BUILD_TRACKING.md body
   via Edit tool. **On conflict, resolve INLINE** — do NOT spawn assembly-fix
   (swarm-runner is a sub-agent and lacks the Agent tool; spike confirmed).
   Read the conflicted files, resolve the conflict markers using the plan's
   spec as the source of truth, `git add` the resolved files, and complete the
   merge. If a conflict cannot be resolved inline after one attempt, treat it
   as a blocking failure: write the conflict to `<reports_dir>/merge-conflict.md`,
   set `final_status: "FAIL -- merge-conflict: <branch>"` in BUILD_TRACKING.md
   Run State, and return `STATUS: FAIL -- merge-conflict: <branch>`.
4. **Contract check (CIRCUIT BREAKER).** Read the plan's spec. Grep
   assembled code for prescribed names/routes/imports. Write results to
   `<reports_dir>/contract-check.md` (STATUS on line 1).
   On FAIL: attempt fixes inline, re-run once. On second FAIL: **abort
   immediately** — do NOT merge to main, do NOT clean up branches. Set
   `final_status: "FAIL -- contract-check: <reason>"` in BUILD_TRACKING.md
   Run State. Return `STATUS: FAIL -- contract-check: <reason>`.
   (CLAUDE.md Escalation Rule: "If the spec contract check fails after one
   retry, abort the pipeline.")
5. Smoke test (non-blocking). Start the app via Bash, curl each route
   prescribed in the plan, record status codes. Write results to
   `<reports_dir>/smoke-test.md` (STATUS on line 1).
   On FAIL: attempt fixes inline, re-run once. On second FAIL: **continue**
   with failure noted in the report. Do NOT abort.
6. Test suite (non-blocking). Execute test runner via Bash, capture results.
   Write to `<reports_dir>/test-results.md` (STATUS on line 1).
   On FAIL: attempt fixes inline, re-run once. On second FAIL: **continue**
   with failure noted. Do NOT abort.
7. Merge assembly to main: `git checkout <original_branch>`,
   `git merge --no-ff <assembly_branch>`.
8. Cleanup worktrees and branches (one Bash call per worktree/branch).
9. Write a summary report to `<reports_dir>/assembly-summary.md` with
   merge_status, preserved_branches, cleanup_status, counts, and
   per-phase report paths. STATUS on line 1.
10. Write one row to the Phase Status table in BUILD_TRACKING.md:
    `| swarm | PASS | <reports_dir>/assembly-summary.md |`
    (Or `| swarm | FAIL | ... |` if contract check aborted — but in that
    case the agent already returned at step 4.)
11. Return Tier 1 key-value lines:

**Output contract:**
```
report_path: <reports_dir>/assembly-summary.md
STATUS: PASS
```
Or on contract-check abort:
```
report_path: <reports_dir>/contract-check.md
STATUS: FAIL -- contract-check: <reason>
```

Smoke/test failures do NOT produce STATUS: FAIL. The swarm-runner
completes steps 7-11 and returns STATUS: PASS with failures noted in
`assembly-summary.md`. The tail-runner reviews those failures.

**Why inline, not sub-agents?** spec-contract-checker, smoke-test-runner,
test-suite-runner, and assembly-fix are agent types (`.claude/agents/`),
not skills. Sub-agents lack the Agent tool (spike confirmed), so swarm-runner
cannot spawn any of them. The work is straightforward to inline: grep for spec
names (contract), curl routes (smoke), run pytest (test), and resolve conflict
markers against the spec (merge). All use Bash, Read, Edit, and Grep — tools
the swarm-runner has. This is the same constraint that flagged the tail-runner
Step 8 latent bug; the plan avoids reintroducing it in swarm-runner.

### SKILL.md Changes for Stage 3

After Step 10.5w (ownership gate PASS), replace Steps 11w-16w with:

```
### Steps 11w-16w: Assembly + Verification (DELEGATED)

Spawn the **swarm-runner** agent. Pass: plan_path, run_id, reports_dir,
build_tracking_path, assembly_branch, original_branch, worker_branches,
agent_assignments, agent_pitfalls. Spawn with `mode: "bypassPermissions"`.
Wait for result.

Search backward in the agent's output for a line starting with `STATUS:`.
- If STATUS: PASS, proceed to Step 17w. (Smoke/test failures, if any, are
  noted in assembly-summary.md and reviewed by the tail.)
- If STATUS: FAIL and the reason starts with `contract-check:` or
  `merge-conflict:`, the swarm-runner has already aborted and set
  `final_status` in BUILD_TRACKING.md Run State. Do NOT proceed to Step 17w.
  The run ends. (These are the two blocking failure classes.)
- If STATUS: FAIL for any other reason, read the full report and abort.
```

Remove inline Steps 11w-16w from SKILL.md. The swarm-runner agent file is
the single source of truth for assembly/verification logic.

## No-Duplication Invariant

**Rule:** No same-path implementation logic exists in both an agent file
and SKILL.md inline.

**How this holds:**
- Step 6 (deepening): Both solo and swarm run `/compound-engineering:deepen-plan`
  inline (orchestrator needs Agent tool for research sub-agents). Solo merges
  inline (Step 6.03s — same as current Step 6.5). Swarm delegates merge to
  deepen-merge-runner (Step 6.03). Different paths — solo is inline SKILL.md,
  swarm is the agent file. No same-path duplication.
- Steps 11w-16w (assembly): Only exist in swarm-runner.md. SKILL.md's swarm
  path says "spawn swarm-runner." Solo path has no assembly (Step 7s is
  `/workflows:work`).
- Shared Tail: Solo runs inline in SKILL.md. Swarm delegates to tail-runner.
  TAIL_SYNC_POINT marks the ~30 lines of shared logic. This pre-exists and
  is unchanged by this plan.

## Success Measurement

**Primary gate (binary):** The build finishes unattended. `final_status: DONE`
in BUILD_TRACKING.md Run State. No `PAUSED_FOR_CONTEXT`, no manual resume.
This is what actually matters. (Simplicity review finding: binary outcome
is more honest than a proxy metric with known measurement gaps.)

**Secondary metric (observability, not a gate):** `context_proxy_chars` in
BUILD_TRACKING.md Run State is a rough manual tally of cumulative character
count from Read and Agent tool outputs. It helps diagnose HOW MUCH context
was saved but is not a pass/fail criterion. The metric has known gaps: it
misses system prompts, tool schemas, and compaction effects. There is no
reliable programmatic introspection for actual context usage. It is useful
for comparing runs, not for setting absolute thresholds.

**Where savings come from:** Stage 1 (no-read discipline on PASS reports)
and Stage 3 (swarm-runner runs assembly + verification in fresh context)
provide the real context savings. Stage 2 (deepen-merge-runner) is a
structural consistency choice with no meaningful context benefit — the
orchestrator already carries the deepening outputs before spawning the agent.

## Acceptance Tests

### Happy Path

- WHEN a 12-agent swarm build runs with all 3 stages applied THE SYSTEM
  SHALL complete fully unattended with `final_status: "DONE"` and
  `manual_resume: false` in BUILD_TRACKING.md Run State.
- WHEN the deepen-merge-runner agent completes THE SYSTEM SHALL return a
  Tier 1 decision line under 200 characters and the deepened plan shall
  commit cleanly.
- WHEN the swarm-runner agent completes THE SYSTEM SHALL return a Tier 1
  decision line under 200 characters and all worker branches shall be
  merged to the assembly branch.
- WHEN the orchestrator reads a phase report on PASS THE SYSTEM SHALL read
  only 1 line (the STATUS line) and not read the full report.
- WHEN a phase agent completes THE SYSTEM SHALL write one row to the
  Phase Status table in BUILD_TRACKING.md using the Edit tool.

### Error Cases

- WHEN the swarm-runner's inline contract check fails after one retry THE
  SYSTEM SHALL have the swarm-runner abort (no merge to main, no cleanup),
  set `final_status: "FAIL -- contract-check: <reason>"` in Run State, and
  return `STATUS: FAIL -- contract-check: <reason>`. The orchestrator SHALL
  NOT proceed to Step 17w (tail). The run ends.
  Verify: `grep "final_status" BUILD_TRACKING.md` -- shows `FAIL -- contract-check`.
- WHEN the swarm-runner's inline smoke test or test suite fails after one
  retry THE SYSTEM SHALL have the swarm-runner continue through merge-to-main
  and cleanup, returning `STATUS: PASS` with failures noted in
  `assembly-summary.md`. The orchestrator SHALL proceed to Step 17w (tail),
  which reviews the noted failures.
  Verify: `grep "FAIL" docs/reports/<run-id>/assembly-summary.md` -- failure
  noted; `grep "final_status" BUILD_TRACKING.md` -- not set to FAIL.
- WHEN a Phase Status table Edit fails (anchor not found) THE SYSTEM SHALL
  read BUILD_TRACKING.md, find the correct insertion point, and retry once.
  On second failure, FAIL with `"BUILD_TRACKING EDIT FAILED"`.
- WHEN a solo build (swarm: false) runs after all stages are applied THE
  SYSTEM SHALL complete using the existing inline path (including inline
  deepening merge at Step 6.03s) without delegated agents and produce all
  5 mandatory artifacts.

### Verification Commands

- `head -1 docs/reports/<run-id>/smoke-test.md` -- returns `STATUS: PASS` or `STATUS: FAIL` (no frontmatter, no markdown formatting)
- `grep -c "^STATUS:" docs/reports/<run-id>/*.md` -- every report file has exactly 1 STATUS line on line 1
- `grep "Phase Status" BUILD_TRACKING.md` -- Phase Status section exists
- `grep -c "| PASS |" BUILD_TRACKING.md` -- count completed phase rows

## Most Likely Way This Plan Is Wrong

The reduced swarm-runner scope (Steps 11w-16w only) may not save enough
orchestrator context for 20+ agent builds. Worker spawn (Steps 7w-10.5w)
stays inline and scales linearly with agent count. On a 25-agent build,
spawn prompts alone could consume significant context even with no-read
discipline. If builds still fail after all 3 stages,
the fallback is an external orchestrator (Candidate 7/8 from brainstorm) --
a significantly larger effort. The first 20+ agent build will validate.

## Feed-Forward

- **Hardest decision:** Dropping YAML frontmatter from BUILD_TRACKING.md
  after the brainstorm committed to it. Deepening research found zero
  precedent for programmatic YAML editing in this codebase. All 15+ builds
  use markdown tables. The brainstorm's validation protocol was solving a
  self-created problem. Replacing with markdown Phase Status table aligns
  with the proven pattern and eliminates the #1 risk.

- **Rejected alternatives:**
  - YAML frontmatter in BUILD_TRACKING.md (deepening research: zero
    precedent, risky departure from proven markdown table pattern)
  - Pipe-delimited Tier 1 line (deepening research: all 7 agents use
    multi-line key-value; pipe format has no precedent)
  - Separate PHASE_STATE.json (dual-source-of-truth risk)
  - Hard 30% context target (spike reduced swarm-runner scope; 60% was
    initially proposed as a hard gate but downgraded to observability-only
    because the metric misses system prompts, tool schemas, and compaction)
  - Stage 2 as a context-saving mechanism (review found the orchestrator
    already carries deepening outputs; delegating only merge saves ~0 context.
    Kept for swarm-only as structural consistency, dropped for solo.)

- **Least confident:** Whether the reduced swarm-runner scope (Steps 11w-16w
  only) saves enough context for 20+ agent builds. Worker spawn (Steps
  7w-10.5w) remains inline. The `context_proxy_chars` metric on the first
  real build will show how much context was saved (observability, not a gate).

---

## Codex Handoff Prompt

```
Read these files first for project context:
  - HANDOFF.md
  - CLAUDE.md (Escalation Rules + Forbidden Actions)
  - docs/plans/2026-06-03-autopilot-context-death-solution-plan.md

Review this plan for:
1. Gaps -- anything missing that will cause problems during implementation
2. Wrong assumptions -- does the plan assume something that isn't true?
3. Scope creep -- anything in the plan that wasn't in the brainstorm
4. The Feed-Forward "least confident" item -- is reduced swarm-runner scope sufficient?
5. Plan Quality Gate:
   - What's changing? (3 layers across 3 stages)
   - What must not change? (9 items listed)
   - How we'll know it worked? (EARS acceptance tests + binary completion gate)
   - Most likely way it's wrong? (20+ agent spawn still inline)

Key files to check:
  - .claude/skills/autopilot/SKILL.md (Steps 6-6.5, 9w.5-9w.7, 11w-16w)
  - .claude/agents/tail-runner.md (delegation pattern reference)
  - docs/reports/spike-nested-worktree-delegation.md (Agent tool gap)

Items to verify from prior reviews:
  - No edits to ~/.claude/docs/autopilot-tracking-template.md
  - Step 5.5 (run_id) appears before Step 6 (deepen)
  - deepen-merge-runner does NOT invoke /compound-engineering:deepen-plan
  - Step 6.03 is swarm-only; solo uses 6.03s inline merge
  - Contract-check FAIL in swarm-runner aborts pipeline (CLAUDE.md escalation)
  - Smoke/test FAIL in swarm-runner continues to tail (non-blocking)
  - spec-contract-checker, smoke-test-runner, test-suite-runner superseded
  - Stage 2 rationale states structural choice, not context savings
  - Step 6.08 commits self-review edits after 6.05/6.07
  - context_proxy_chars framed as observability-only rough manual tally

Output: findings + updated Claude Code handoff prompt if plan needs changes.
```

---

## Revision Changelog (2026-06-03, review round 2)

**P1-1 (circuit breaker):** Rewrote swarm-runner steps 4-6 to distinguish
contract-check FAIL (abort pipeline, set final_status, return STATUS: FAIL)
from smoke/test FAIL (continue, return STATUS: PASS with failures noted).
Updated SKILL.md Stage 3 replacement to route FAIL to pipeline abort, not
to tail. Updated acceptance test error cases to match.

**P1-2 (Stage 1↔3 reconciliation):** Removed spec-contract-checker,
smoke-test-runner, test-suite-runner from Stage 1 scope (output contracts,
no-read discipline, agent invocation updates). Added them to Files NOT
Modified table as superseded by Stage 3. Removed Steps 12w-14w from the
no-read table. Removed their build_tracking_path entries.

**P1-3 (solo inline):** Gated Step 6.03 (deepen-merge-runner) to swarm-only.
Added Step 6.03s for solo inline merge (same as current Step 6.5). Updated
No-Duplication Invariant, acceptance tests, and Deepening Summary.

**P1-4 (Stage 2 rationale):** Rewrote "Why" section to state Stage 2 is a
structural consistency choice for swarm only, with no meaningful context
savings. Updated Success Measurement to credit savings to Stage 1 + 3 only.
Added Stage 2 to Feed-Forward rejected alternatives.

**P2-5 (self-review commit):** Added Step 6.08 to commit self-review edits
from 6.05/6.07, preventing uncommitted changes after the merge commit.

**P2-6 (Step 6.1→5.5 refs):** Added explicit enumeration of all 6 SKILL.md
locations that reference "Step 6.1" and need updating to "Step 5.5".

**P2-7 (corrections format):** Prescribed markdown format for deepen-merge-runner
corrections input (`### Section / **Change:** / **Rationale:**`) plus
anchor-failure fallback.

**P2-8 (acceptance tests):** Rewrote error cases to reference swarm-runner's
internal retry policy and clarify that the swarm-runner (not the orchestrator)
sets final_status on contract-check abort.

**P2-9 (context_proxy_chars):** Added note that the metric is a rough manual
tally with no reliable programmatic introspection.

**P3 (smoke routes source):** Added "Derived from plan_path" note to
swarm-runner inputs documenting that routes, test command, and export names
come from the plan.

## Revision Changelog (2026-06-03, review round 3)

**Item 4 (Step 6.1 references):** Completed the enumeration of "Step 6.1"
locations. Added three that were missing: CHECKPOINT.md template (solo tail),
the Self-Audit step (solo tail), and Step 6.07's closing control-flow pointer.
The 6.07 pointer is a SPECIAL CASE — it becomes "proceed to Step 6.08" (next
step), NOT "Step 5.5" (the run-id rename). Added a `grep` instruction so the
implementer catches all hits. Marked Step 6.07 as not fully unchanged.

**Finding B (assembly-fix unspawnable):** swarm-runner is a sub-agent and lacks
the Agent tool, so it cannot spawn assembly-fix — the same latent-bug class the
spike flagged for tail-runner Step 8. Changed swarm-runner step 3 to resolve
merge conflicts INLINE (read conflict markers, resolve against the spec, git add,
complete the merge), with a blocking `merge-conflict:` FAIL if unresolvable after
one attempt. Moved assembly-fix from Files Modified to Files NOT Modified
(superseded). Removed it from the Output Contracts table. Updated the Stage 3
SKILL.md handler to treat `merge-conflict:` as a second blocking failure class
alongside `contract-check:`. Updated the "Why inline" rationale.
