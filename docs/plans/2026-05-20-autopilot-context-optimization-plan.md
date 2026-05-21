---
title: "feat: Autopilot Context Window Optimization"
type: feat
status: active
date: 2026-05-20
origin: docs/brainstorms/2026-05-20-autopilot-context-optimization-brainstorm.md
swarm: false
feed_forward:
  risk: "Orchestration-load heuristic may false-positive on run 048-like builds (score 40.5 vs >30 threshold) -- cost is brief manual resume after compound, not a full rebuild"
  verify_first: true
---

# feat: Autopilot Context Window Optimization

## Overview

Harden the autopilot skill so 31+ agent swarm builds don't lose mandatory tail artifacts to context death. Run 050 (GigSheet) completed all code phases but hit 0% context during the shared tail -- BUILD_TRACKING, self-audit, and learnings propagation were lost.

Three changes: incremental BUILD_TRACKING writes, context-budget checkpoint gates, and post-deepening canonical spec rewrite. Plus a new `tail-resume` skill for manual recovery and argument extensions in `update-learnings-noninteractive`.

(see brainstorm: docs/brainstorms/2026-05-20-autopilot-context-optimization-brainstorm.md for full analysis, 3 Codex review rounds, and all design decisions)

## Problem Statement

The autopilot treats context as unlimited. At 31 agents, orchestration overhead (spawn prompts, agent outputs, plan re-reads, tail artifact synthesis) exceeds the context window. The build was mechanically perfect (0 FC37, 0 conflicts, 46/46 smoke tests) but the mandatory tail (BUILD_TRACKING, learnings, self-audit) was lost because the orchestrator carried all state in-context instead of persisting it to disk.

## What Must Not Change

- The swarm architecture (vertical blueprint split, ownership gates, assembly merge)
- The shared interface spec pattern
- Review thoroughness (5-agent review for large swarms)
- The mandatory artifact contract (CLAUDE.md:34)
- Normal autopilot flow for builds that don't trigger checkpoint thresholds
- Existing update-learnings-noninteractive behavior when called without new flags

## Proposed Solution

Five implementation tasks, ordered by dependency:

### Phase 1: Extend update-learnings-noninteractive argument parsing

**File:** `.claude/skills/update-learnings-noninteractive/SKILL.md`

**Current behavior (lines 24-31):** Accepts `$ARGUMENTS` as a solution doc path. If blank, finds most recently modified file in `docs/solutions/`. Step 0 discovers plan via solution doc frontmatter or "most recent" and review summary via branch-derived path.

**Change:** Add two optional flags to the argument parser:

```markdown
## Arguments

<update_target> #$ARGUMENTS </update_target>

Parse arguments:
- Extract positional argument as solution doc path (if given)
- If `--plan <path>` is present, extract plan path
- If `--review-summary <path>` is present, extract review summary path
- If no positional argument, find the most recently modified file in `docs/solutions/`

Store parsed values:
- `solution_doc_path`: from positional arg or auto-detected
- `plan_path`: from `--plan` flag or null
- `review_summary_path`: from `--review-summary` flag or null
```

**Step 0 change (lines 33-45):** Add conditional logic at the top:

```markdown
## Step 0: Load Context

- Read the solution doc at `solution_doc_path`
- If `plan_path` was provided: read the plan at that path
  Otherwise: find via solution doc's `related_prs` or most recent in `docs/plans/`
- If `review_summary_path` was provided: read the review summary at that path
  Otherwise: find from `docs/reviews/<branch>/REVIEW-SUMMARY.md`
```

Steps 1-6 are unchanged -- they use paths established in Step 0.

**Lines affected:** ~8 lines changed in Arguments section (lines 24-31), ~6 lines changed in Step 0 (lines 33-38). Net: ~14 lines modified. No new sections.

### Phase 2: Incremental BUILD_TRACKING writes in autopilot

**File:** `.claude/skills/autopilot/SKILL.md`

**Current behavior:** BUILD_TRACKING.md created at Step 1.5 (line 64), filled in bulk at shared tail (lines 465-475). The entire build runs between creation and filling.

**Change (swarm path):** Add inline Bash appends at 5 points. Each is a single `echo` command (one Bash call, per FC8). Values derived as follows:
- `N` = sequential counter (1, 2, 3...) maintained by the orchestrator during the merge loop
- `role` = agent name from the swarm-planner assignment table
- `commit` = output of `git log -1 --format=%h` after each merge
- `file_count` = line count of `git diff --name-only HEAD~1` output after merge

**AGENT_STATUS row shape (exact format):**
```
| <N> | <role> | <commit_hash> | PASS |
```
Where `N` is the sequential agent number (1-based), `role` is the agent name from the assignment table, `commit_hash` is the short SHA after merge. No `file_count` column -- it adds complexity for minimal value.

**Insert point 1: After each agent merge in Step 11w (line 331)**
After each successful `git merge --no-ff <branch-name>`, run two Bash calls:
1. `git log -1 --format=%h` (capture as `commit_hash`)
2. `echo "| <N> | <role> | <commit_hash> | PASS |" >> BUILD_TRACKING.md`

**Insert point 2: After ownership gate in Step 10.5w (line 318)**
After writing `ownership-gate.md`:
`echo "### Ownership Gate: PASS (<N> agents)" >> BUILD_TRACKING.md`

**Insert point 3: After contract check in Step 12w (line 342)**
After reading `contract-check.md` STATUS:
`echo "### Contract Check: <STATUS>" >> BUILD_TRACKING.md`

**Insert point 4: After smoke test in Step 13w (line 352)**
After reading `smoke-test.md` STATUS:
`echo "### Smoke Test: <STATUS>" >> BUILD_TRACKING.md`

**Insert point 5: After review in shared tail (line 404)**
After `/workflows:review` completes:
`echo "### Review: <P1_count> P1, <P2_count> P2 | Fix commits: <hashes>" >> BUILD_TRACKING.md`

**Change (solo path):** Solo builds do NOT have incremental writes (no merge loop, no gates). Keep the existing bulk fill step for solo builds only. Make the shared tail BUILD_TRACKING step conditional:

```markdown
### Fill BUILD_TRACKING.md (MANDATORY -- SOLO ONLY)

If this is a solo build (not swarm): fill AGENT_STATUS, FAILURES, and
RUN_METRICS sections now (same behavior as current lines 465-475).

If this is a swarm build: skip this step (sections already populated
incrementally).
```

**Replace the current "Verify BUILD_TRACKING.md Completeness" step (lines 477-485):**

```markdown
### Verify BUILD_TRACKING.md Completeness (MANDATORY GATE)

Read BUILD_TRACKING.md. Verify:
1. AGENT_STATUS section has at least one agent row
2. FAILURES section exists (may contain "None" if no failures)
3. RUN_METRICS section exists with at least one metric row

If any section is missing or empty, FAIL with:
"BUILD_TRACKING INCOMPLETE: [section name] is missing or empty."
```

**FAILURES and RUN_METRICS for swarm builds:** Add one more append after review (shared tail) to populate these sections:

```markdown
### Fill FAILURES and RUN_METRICS (MANDATORY -- SWARM ONLY)

After review completes and all P1 fixes are committed:

1. Read all report files in `docs/reports/<run-id>/` to compile failure data.
2. Use Edit tool to replace the `<!-- Append a block for each error. -->`
   placeholder under the existing `## FAILURES` heading (created by template
   in Step 1.5) with one row per finding: severity, detail, resolution,
   failure class. Do NOT add a duplicate `## FAILURES` heading.
3. Use Edit tool to replace the `<!-- Generated by orchestrator ... -->`
   placeholder under the existing `## RUN_METRICS` heading with: agent count,
   FC37 rate, merge conflicts, file count, LOC estimate, smoke test results,
   review finding counts. Do NOT add a duplicate `## RUN_METRICS` heading.

This fills the existing template sections, not appends new ones. The
self-audit agent reads FAILURES and RUN_METRICS as canonical sources --
duplicate headings would confuse it.
```

**Lines affected:** +20 lines (5 append sites + value derivation), +12 (solo conditional), +15 (FAILURES/RUN_METRICS fill), -10 (removed unconditional bulk fill) = net +37 lines.

**Also change Step 1.5 (line 72):** Remove the line "Each swarm agent will append to AGENT_STATUS after completing" -- ownership is now the orchestrator's.

### Phase 3: Checkpoint gates in autopilot

**File:** `.claude/skills/autopilot/SKILL.md`

**Add one new step to the autopilot (post-compound only):**

The brainstorm's validated Tier 1 contract covers post-compound resume only. `/workflows:compound` is unverified for artifact-only resume (it may depend on in-context build experience). By placing the checkpoint after Compound, the solution doc exists when the checkpoint is written, and tail-resume never needs to run Compound.

**Step: Context-Budget Checkpoint -- Post-Compound (insert after "### Compound" and before "### Update Learnings")**

```markdown
### Context-Budget Checkpoint -- Post-Compound (MANDATORY)

Calculate orchestration load:
- `swarm_agents` = number of agents spawned in Step 10w (count from assignment table)
- `deepening_agents` = number of agents spawned in Step 6 (count from deepen-plan output, default 4)
- `review_agents` = number of review agents spawned during Review
- `fix_retries` = number of assembly-fix agent invocations in Steps 12w-14w (count from report files)
- `load = swarm_agents + (deepening_agents * 2) + (review_agents * 1.5) + (fix_retries * 3)`

If `load > 30`:

1. Identify the solution doc just written by Compound (most recent file in `docs/solutions/`).
2. Use Write tool to create CHECKPOINT.md with the schema below, filling all paths from current run state.
3. Commit CHECKPOINT.md: `git add CHECKPOINT.md` then `git commit -m "chore: context checkpoint for tail resume"`
4. Output: `PAUSED_FOR_CONTEXT: Orchestration load is [load] (threshold 30). CHECKPOINT.md written and committed. Resume with /tail-resume.`
5. Output: `<promise>PAUSED_FOR_CONTEXT</promise>`
6. STOP. Do not proceed to Update Learnings.

If `load <= 30`: proceed to Update Learnings normally.
```

**Placement rationale:** After Compound, before Update Learnings. Compound has completed, so `solution_doc_path` is populated. The checkpoint captures the complete post-compound state. Resume starts at Update Learnings -- the brainstorm's validated Tier 1 boundary.

**CHECKPOINT.md schema template (include in SKILL.md as a reference block):**

```yaml
---
status: PAUSED_FOR_CONTEXT
run_id: "<run-id>"
date: "<today>"
branch: "<current branch>"
project_name: "<project name from Step 2>"
---

plan_path: <path to plan>
solution_doc_path: <path to solution doc -- Compound has completed>
review_summary_path: <path to review summary -- review has completed>
reports_dir: docs/reports/<run-id>/
build_tracking_path: BUILD_TRACKING.md
handoff_path: HANDOFF.md

last_completed_step: "Compound"
next_step: "Update Learnings"

completed_artifacts:
  <list of completed artifact paths>

pending_mandatory_artifacts:
  <list of remaining mandatory artifacts>

review_findings:
  p1_fixed: <count>
  p2_deferred: <count>
  fix_commits: [<hashes>]
```

**Lines added:** ~24 lines (checkpoint gate) + ~20 lines (schema template) = ~44 lines total.

### Phase 4: Post-deepening canonical spec rewrite

**File:** `.claude/skills/autopilot/SKILL.md`

**Move run-id generation earlier:** Currently run-id is generated at Step 8w (swarm) or Step 7s.0 (solo), AFTER deepening. Move it to a new Step 6.1 so the reports directory exists for Step 6.5.

```markdown
### Step 6.1: Generate Run ID and Reports Directory (MANDATORY)

Count the files in `docs/solutions/` and add 1. Zero-pad to 3 digits.
This is the `run-id`. Create `docs/reports/<run-id>/`.

This step runs before deepening merge so `docs/reports/<run-id>/` exists
for the audit trail. Remove the duplicate run-id generation from Step 8w
and Step 7s.0 -- they now use the run-id established here.
```

**Insert after Step 6.1, before the Branch Point:**

```markdown
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
   `git add docs/plans/<plan-file> docs/reports/<run-id>/deepening-applied.md`
   `git commit -m "chore: merge deepening corrections into plan"`

All downstream steps (swarm planner, agents, contract check) read the
rewritten plan. No agent should see raw amendment notes.
```

**Lines added:** ~25 lines (Step 6.1 + expanded Step 6.5). Lines removed: ~8 (duplicate run-id gen from Steps 8w and 7s.0).

### Phase 5: Create tail-resume skill

**File:** `.claude/skills/tail-resume/SKILL.md` (new file)

```markdown
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
   "ABORT: No CHECKPOINT.md found at [path]. Nothing to resume."
2. Verify `status: PAUSED_FOR_CONTEXT` in frontmatter. If different, abort:
   "ABORT: CHECKPOINT.md status is [status], not PAUSED_FOR_CONTEXT."
3. Extract all fields from CHECKPOINT.md into local variables.

## Steps

Execute steps in order. The only valid `next_step` value is "Update Learnings"
(post-compound). Compound has already completed -- `solution_doc_path` is populated.

### Step 1: Validate Resume Point

Read `next_step` from CHECKPOINT.md.
- If "Update Learnings": proceed to Step 2.
- Any other value: abort with "ABORT: tail-resume only supports next_step='Update Learnings'. Got: [value]."

### Step 2: Update Learnings

Run `/update-learnings-noninteractive` with explicit paths from CHECKPOINT.md:

`<solution_doc_path> --plan <plan_path> --review-summary <review_summary_path>`

### Step 3: Verify Learnings Artifacts (MANDATORY GATE)

Same 4 gates as autopilot SKILL.md lines 436-462:
1. Learnings Propagated summary table output
2. HANDOFF.md date matches today
3. Agent-pitfalls Update Log has entry for this build
4. No duplicate failure class IDs

### Step 4: Verify BUILD_TRACKING.md Completeness (MANDATORY GATE)

Read BUILD_TRACKING.md. Verify:
1. AGENT_STATUS section has at least one agent row
2. FAILURES section exists
3. RUN_METRICS section exists with at least one metric row

### Step 5: Self-Audit (MANDATORY)

Use the self-audit-reviewer agent with 6 args from CHECKPOINT.md:
1. run_id
2. reports_dir
3. plan_path
4. solution_doc_path
5. build_tracking_path
6. handoff_path

### Step 6: Verify Self-Audit (MANDATORY GATE)

Run `/verify-self-audit <run_id> <reports_dir>`

### Step 7: Done

Output: `<promise>DONE</promise> (resumed from CHECKPOINT.md)`
```

**Lines:** ~90-100 lines estimated.

## Technical Considerations

- **Bash safety:** All BUILD_TRACKING appends are single `echo` commands (one per Bash call). No compound commands, no loops. Per FC8 and compound-bash-instruction-refactor.
- **Step format:** All new steps use `### Step N.N: Name (MANDATORY)` format. Per autopilot-skips-non-step-instructions, prose rules are not executed.
- **Argument parsing:** update-learnings-noninteractive uses the existing `<update_target> #$ARGUMENTS </update_target>` XML tag pattern. tail-resume uses the same pattern with `<checkpoint_path>`.
- **Backwards compatibility:** update-learnings-noninteractive's new flags are optional. Existing callers (autopilot without checkpoint) pass only the solution doc path and behavior is unchanged.
- **SKILL.md growth:** Autopilot goes from ~522 to ~610 lines (+88). This exceeds the 500-line budget by ~110 lines. The growth comes from: incremental appends (+20), solo/swarm conditional (+12), FAILURES/RUN_METRICS fill (+15), checkpoint gate (+24), Step 6.1 run-id (+8), Step 6.5 deepening merge (+17), minus removed duplicate run-id gen (-8). Future extraction can happen once the pattern stabilizes.
- **CHECKPOINT.md durability:** CHECKPOINT.md is committed to git immediately after writing. Survives `git clean` and session death.
- **Solo path unchanged except BUILD_TRACKING:** Solo builds keep the existing bulk fill step. Only swarm builds get incremental writes. The verify step checks the same sections for both paths.
- **Pre-review checkpoint deferred:** The brainstorm classifies pre-review resume as "Tier 2: unverified." Only the pre-tail checkpoint is implemented. Pre-review checkpoint is future work after `/workflows:review` and `/workflows:compound` are audited for artifact-only resumability.

## Acceptance Tests

### Happy Path

- WHEN the autopilot completes a 31-agent swarm build THE SYSTEM SHALL have BUILD_TRACKING.md populated with all agent status rows and gate results before the shared tail begins
- WHEN the orchestration load exceeds 30 before the shared tail THE SYSTEM SHALL write CHECKPOINT.md with all explicit paths, commit it, and exit with PAUSED_FOR_CONTEXT
- WHEN a user runs `/tail-resume` with a valid CHECKPOINT.md THE SYSTEM SHALL complete all remaining mandatory tail artifacts (learnings, self-audit) using explicit paths from CHECKPOINT.md without re-running any code phases
- WHEN deepening agents return corrections THE SYSTEM SHALL merge them into the plan file in-place and commit before swarm launch
- WHEN update-learnings-noninteractive receives `--plan` and `--review-summary` flags THE SYSTEM SHALL use those explicit paths instead of discovery heuristics

### Error Cases

- WHEN orchestration load is 30 (boundary, not exceeding) THE SYSTEM SHALL NOT write CHECKPOINT.md and SHALL proceed normally
- WHEN CHECKPOINT.md does not exist and user runs `/tail-resume` THE SYSTEM SHALL abort with a clear error message
- WHEN update-learnings-noninteractive receives no flags THE SYSTEM SHALL use existing "most recent" discovery (backwards compatible)
- WHEN update-learnings-noninteractive receives `--plan` with a nonexistent path THE SYSTEM SHALL abort with a file-not-found error instead of silently falling back to discovery
- WHEN a solo build reaches the BUILD_TRACKING verify step THE SYSTEM SHALL have populated AGENT_STATUS via the solo-only bulk fill step (not incremental writes)
- WHEN two deepening agents modify the same plan section THE SYSTEM SHALL synthesize a consistent merged edit and document the conflict in deepening-applied.md
- WHEN BUILD_TRACKING is populated incrementally for a swarm build THE SYSTEM SHALL still contain non-empty FAILURES and RUN_METRICS sections from the post-review fill step
- WHEN tail-resume receives `next_step` other than "Update Learnings" THE SYSTEM SHALL abort with an unsupported resume point error

### Verification Commands

```bash
# After a swarm build, verify BUILD_TRACKING has agent rows:
grep -c "^|" BUILD_TRACKING.md  # should be >= agent_count + header rows

# Verify CHECKPOINT.md schema is complete:
grep "plan_path:" CHECKPOINT.md
grep "next_step:" CHECKPOINT.md
grep "run_id:" CHECKPOINT.md

# Verify update-learnings-noninteractive accepts new flags:
# (run with explicit paths -- should not use discovery)
/update-learnings-noninteractive docs/solutions/test.md --plan docs/plans/test.md --review-summary docs/reviews/master/REVIEW-SUMMARY.md

# Verify deepening commits the rewritten plan:
git log --oneline -1 docs/plans/  # should show "chore: merge deepening corrections"
```

## Implementation Order

| Order | Task | File | Depends On | Lines Changed |
|-------|------|------|------------|---------------|
| 1 | Extend argument parsing | update-learnings-noninteractive/SKILL.md | None | ~14 modified |
| 2 | Move run-id generation (Step 6.1) | autopilot/SKILL.md | None | ~8 added, ~8 removed |
| 3 | Post-deepening spec rewrite (Step 6.5) | autopilot/SKILL.md | Task 2 (same Step 6 region) | ~17 added |
| 4 | Incremental BUILD_TRACKING (swarm) | autopilot/SKILL.md | None | ~20 added |
| 5 | Solo BUILD_TRACKING conditional | autopilot/SKILL.md | Task 4 | ~12 added |
| 6 | FAILURES/RUN_METRICS fill step | autopilot/SKILL.md | Task 4 | ~15 added |
| 7 | Checkpoint gate (post-compound) | autopilot/SKILL.md | Tasks 4, 6 | ~24 added |
| 8 | tail-resume skill | tail-resume/SKILL.md (new) | Tasks 1, 7 | ~80 new |

**Ordering constraints:**
- Task 1 is independent (different file).
- Tasks 2 → 3 are sequential (both touch Step 6 region in autopilot/SKILL.md, Task 3 needs the run-id from Task 2).
- Task 4 is independent of Tasks 2-3 (different region: Steps 10w-14w and shared tail).
- Tasks 5, 6 depend on Task 4 (same shared tail region).
- Task 7 depends on Tasks 4 and 6 (checkpoint assumes BUILD_TRACKING is incrementally filled).
- Task 8 depends on Tasks 1 and 7 (tail-resume uses the learnings flags and checkpoint schema).

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-05-20-autopilot-context-optimization-brainstorm.md](docs/brainstorms/2026-05-20-autopilot-context-optimization-brainstorm.md)
- Key decisions carried forward: checkpoint over phase shedding, overwrite plan in-place, orchestrator-owned BUILD_TRACKING, agent-count heuristic with known run 048 false positive, manual resume only (no auto-resume)

### Internal References

- Autopilot skill: `.claude/skills/autopilot/SKILL.md` (522 lines, target of changes)
- Learnings skill: `.claude/skills/update-learnings-noninteractive/SKILL.md` (293 lines, argument extension)
- Verify-self-audit extraction pattern: `.claude/skills/verify-self-audit/SKILL.md` (248 lines)
- Self-audit agent: `.claude/agents/self-audit-reviewer.md` (324 lines)
- Run 050 self-audit: `docs/reports/050/self-audit.md`
- Run 050 BUILD_TRACKING: `BUILD_TRACKING.md`

### Prior Lessons Applied

- autopilot-skips-non-step-instructions (2026-05-06): all new logic is numbered steps with MANDATORY labels
- compound-bash-instruction-refactor (2026-04-09): BUILD_TRACKING appends are single echo commands
- sandbox-autonomy-hardening (2026-05-13): extraction pattern for verify-self-audit informs tail-resume structure
- swarm-scale-shared-spec (2026-03-30): spec size grows linearly, canonical rewrite compresses amendments

## Feed-Forward

- **Hardest decision:** Keeping >30 threshold despite the known run 048 false positive (score 40.5). With post-compound checkpoint placement, the cost of a false positive is lower: compound has already run, so the paused session has produced all synthesis artifacts. Resume only runs learnings + self-audit -- the cheapest tail steps. A false checkpoint costs ~5 minutes of manual resume vs context death costing ~30 minutes of artifact reconstruction.
- **Rejected alternatives:** Phase shedding (silent drift), `/compact` as dependency (unverified), auto-resume in Phase 1 (premature), spec size in heuristic (unmeasurable), separate canonical-spec.md (dual source of truth), pre-compound checkpoint (compound resumability unverified).
- **Least confident:** The orchestration-load heuristic. Concrete falsifiers: (1) run 048-like builds false-positive at 40.5 -- cost is a brief manual resume after compound, not a full rebuild, (2) a 28-agent build with 0 deepening scores 37 and could die without triggering checkpoint, (3) assembly-fix retries may underweight plan re-reads. First build validates.
