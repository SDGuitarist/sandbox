---
title: Autopilot Context Window Optimization
date: 2026-05-20
status: brainstorm-revised-r2
trigger: Run 050 (GigSheet, 31-agent swarm) hit 0% context during shared tail
scope: .claude/skills/autopilot/SKILL.md + .claude/agents/ + new helper skill(s)
feed_forward:
  risk: "Orchestration-load heuristic may false-positive on successful runs or miss future failures"
  verify_first: true
---

# Autopilot Context Window Optimization

## What We're Solving

Run 050 completed all code phases (brainstorm, plan, deepen, 31-agent swarm, contract check, smoke tests, review, compound) but hit 0% context during the shared tail. BUILD_TRACKING, self-audit, and learnings propagation were lost and had to be completed manually.

This is a **context-management failure, not a code-quality failure.** The build was the best ever mechanically (0 FC37, 0 merge conflicts, 46/46 smoke tests). The autopilot's orchestration overhead scaled past the context window.

### Root Causes (from analysis)

1. **Plan passed to ~42-50 subagents/gates** across the run. Each spawn call includes the full spec as prompt text, which stays in the orchestrator's context. Subagent internal work uses separate context, but the orchestrator pays the prompt cost for each spawn.
2. **No state persistence** -- the orchestrator carries all state in-context instead of writing it to disk incrementally.
3. **Post-deepening amendments live alongside original plan** -- agents get original + corrections, not a collapsed canonical spec.
4. **Tail phase reads everything again** -- self-audit reads all reports + BUILD_TRACKING + HANDOFF + solution doc + plan at the end when context is tightest.
5. **BUILD_TRACKING filled at end** -- 31 agent statuses reconstructed from memory instead of written incrementally.

## What We're Building

Three hardening measures for the autopilot skill, plus continuous lean-context optimization.

### 1. Incremental BUILD_TRACKING (Primary Hardening Measure)

Write to BUILD_TRACKING.md after each merge/gate. **Ownership: the orchestrator writes, not agents.**

**What changes:**
- After each agent merge: orchestrator appends agent status row (commit hash, PASS/FAIL, file count)
- After each gate (contract check, smoke test, ownership): orchestrator appends gate result
- After review: orchestrator appends P1/P2 counts and fix commit hashes
- BUILD_TRACKING becomes a live log, not a retrospective reconstruction

**Why orchestrator-owned:** The current design says "each swarm agent will append to AGENT_STATUS after completing" (SKILL.md:72). Agents run in worktrees with separate context -- they don't have access to the main branch's BUILD_TRACKING.md. The orchestrator is the only entity that sees all merge results. Switching to orchestrator writes makes incremental tracking actually work.

**Why this is primary:** If context dies at any point, BUILD_TRACKING already has everything up to the last completed step. A manual follow-up session doesn't need to reverse-engineer agent status from git log. This is the single highest-impact change.

### 2. Context-Budget Checkpoint

A hard safety gate at two points: before review and before shared tail.

**Checkpoint behavior:**
- At each gate: evaluate orchestration load (see heuristic below)
- If load exceeds threshold: write CHECKPOINT.md and exit
- Exit with status `PAUSED_FOR_CONTEXT` (not success, not failure)

**CHECKPOINT.md schema (explicit -- no "most recent" heuristics):**

```yaml
---
status: PAUSED_FOR_CONTEXT
run_id: "050"
date: "2026-05-20"
branch: "master"
project_name: "GigSheet"
---

plan_path: docs/plans/2026-05-20-gigsheet-plan.md
solution_doc_path: docs/solutions/2026-05-20-gigsheet-31-agent-swarm-build.md
review_summary_path: docs/reviews/master/REVIEW-SUMMARY.md
reports_dir: docs/reports/050/
build_tracking_path: BUILD_TRACKING.md
handoff_path: HANDOFF.md
brainstorm_path: docs/brainstorms/2026-05-20-gigsheet-brainstorm.md
compound_engineering_local_path: compound-engineering.local.md
agent_pitfalls_path: ~/.claude/docs/agent-pitfalls.md
lessons_learned_path: ~/Documents/dev-notes/LESSONS_LEARNED.md
journal_path: ~/Documents/dev-notes/2026-05-20.md

last_completed_step: "Compound"
next_step: "Update Learnings"

completed_artifacts:
  - BUILD_TRACKING.md (incremental, complete through review)
  - docs/reports/050/spec-consistency-check.md
  - docs/reports/050/ownership-gate.md
  - docs/reports/050/contract-check.md
  - docs/reports/050/smoke-test.md
  - docs/solutions/2026-05-20-gigsheet-31-agent-swarm-build.md
  - HANDOFF.md

pending_mandatory_artifacts:
  - Learnings propagation (update-learnings-noninteractive)
  - Verify learnings artifacts (4 gates)
  - Self-audit report (docs/reports/050/self-audit.md)
  - Verify self-audit (9 gates)

deferred_items:
  - "050-D1 through 050-D10 (see HANDOFF.md)"

review_findings:
  p1_fixed: 8
  p2_deferred: 10
  fix_commits: ["6af9655"]
```

Every path is explicit. A fresh session reads CHECKPOINT.md and knows exactly where every artifact lives without globbing or "most recent file" discovery.

**Orchestration-load heuristic:**

The trigger is not purely agent count. Context pressure comes from multiple sources:

| Factor | Weight | Rationale |
|--------|--------|-----------|
| Swarm agent count | 1x per agent | Each spawn prompt stays in orchestrator context |
| Deepening agents | 2x per agent | Deepening outputs are read and synthesized in-context |
| Review agents | 1.5x per agent | Review findings require in-context analysis for fix decisions |
| Assembly-fix retries | 3x per retry | Fix agent output + re-run gate = heavy context per retry |

**Note on spec size:** Plans for runs 047-050 are 42-106KB on disk. However, not all of that is the shared interface spec -- plans include brainstorm context, rationale, and acceptance tests that are NOT passed to agents. The relevant metric is the shared interface spec section size, not the full plan file size. This is hard to measure automatically (it's a section within the plan, not a separate file). For now, spec size is excluded from the formula. If future builds show spec section size matters, it can be added as a modifier after the plan is read once.

**Initial guardrails (calibrate after next 2 large swarms):**
- Before review: if weighted load > 40, write checkpoint
- Before tail: if weighted load > 30, write checkpoint

**Validation against runs 047-050:**

| Run | Agents | Deep | Review | Retries | Score | Died? | Checkpoint? |
|-----|--------|------|--------|---------|-------|-------|-------------|
| 047 | 16 | 0 | 4 | 1 | 16+0+6+3 = 25 | No | No (correct) |
| 048 | 20 | 0 | 5 | 1 | 20+0+7.5+3 = 30.5 | No | No (correct) |
| 049 | 25 | 0 | 4 | 2 | 25+0+6+6 = 37 | No | No (correct, under 40) |
| 050 | 31 | 4 | 5 | 2 | 31+8+7.5+6 = 52.5 | Yes | Yes (correct) |

The >40/>30 thresholds correctly separate run 050 (checkpoint) from runs 047-049 (no checkpoint). These are initial guardrails -- calibrate after next 2 large swarms.

**Why this instead of phase shedding:** The tail phases (BUILD_TRACKING, HANDOFF, learnings, self-audit) are all mandatory per CLAUDE.md:34. Shedding mandatory artifacts turns context pressure into silent process drift. A hard stop with resumable state is deterministic recovery.

### 3. Post-Deepening Canonical Spec Rewrite

After deepening agents return corrections, merge all accepted changes back into the plan file in-place.

**What changes:**
- Deepening ends with a new step: the orchestrator merges all accepted corrections into the plan file (it already has the plan and amendment outputs in context at this point, so no additional read cost)
- Commit the rewritten plan before swarm launch
- All downstream agents read only the rewritten plan, never raw amendment notes
- Deepening audit notes (what changed and why) are written to `docs/reports/<run-id>/deepening-applied.md` as audit trail, not kept in the plan itself

**Why overwrite instead of separate file:** A separate canonical-spec.md creates dual source of truth. This repo has learned (repeatedly) that dual source of truth causes drift: review updates one file, agent briefs reference the other, orchestrator has to decide which wins. Git preserves the pre-deepening version. One live spec, git for history.

**Why audit notes in reports/ instead of the plan:** The plan is an execution document. Adding metadata that agents never use but carry in every brief wastes context. Putting the audit trail in `docs/reports/<run-id>/deepening-applied.md` keeps the plan lean and the audit accessible.

### 4. Continuous Lean-Context Optimization

Not an emergency response -- these are normal operating practices:

- **Persist immediately:** Write state to disk instead of carrying it in context. Agent results → BUILD_TRACKING row. Gate results → report file. Don't summarize in-context.
- **Shorten in-session summaries:** The orchestrator doesn't need verbose agent output. Status + commit hash + file count is sufficient.
- **Avoid re-reads:** Once a report file is written, reference it by path. Don't re-read the plan after it's been read for agent briefs.
- **Collapse deepening:** The canonical spec rewrite (#3) eliminates the biggest re-read offender.

## Extraction Strategy

The autopilot skill is already ~522 lines -- past the repo's ~500-line complexity budget. New logic must be extracted, not inlined.

**Proposed extraction:**

| New artifact | Type | Responsibility |
|-------------|------|----------------|
| `tail-resume` | Skill (.claude/skills/) | Reads CHECKPOINT.md, passes explicit paths to update-learnings-noninteractive and self-audit. Manual invocation only (Phase 1). This is the only artifact that requires its own skill file -- it orchestrates the resume sequence. |

**Inline in SKILL.md (simple enough to not extract):**

| Logic | Why inline |
|-------|-----------|
| BUILD_TRACKING row append | Single `echo "..." >> BUILD_TRACKING.md` Bash call per merge/gate. No structured logic, just a formatted append. Extracting to a helper skill adds invocation overhead for a one-liner. |
| CHECKPOINT.md write | Single Write tool call with the schema template filled in. No agent reasoning needed -- the orchestrator already has all the values. Extracting to an agent adds context cost (agent prompt + response) for a straightforward file write. |
| Orchestration-load calculation | Arithmetic on 4 numbers the orchestrator already knows. No external reads. |

**Net change to SKILL.md:**
1. Add BUILD_TRACKING append after each merge/gate (~3 lines per call site, ~15 total for 5 sites)
2. Add checkpoint evaluation + Write at two gates (~12 lines each, ~24 total)
3. Add post-deepening spec rewrite step (~8 lines)
4. Remove end-of-run BUILD_TRACKING fill step (-12 lines)
5. Estimated net: +35 lines → SKILL.md goes from ~522 to ~557 lines

This exceeds the 500-line budget by ~57 lines. Acceptable as a temporary overshoot because: (a) the removed BUILD_TRACKING fill step offsets some growth, (b) the inline logic is simple (no branching, no error handling), and (c) extracting one-liners to helper skills adds more complexity than it saves.

## Design Principle

Use disk as working memory, context only for the current step. The autopilot should be resumable at any point -- if the session dies after step N, a fresh session reads artifacts from disk and continues from step N+1.

## Resumability Analysis

Resumability is not uniform across the pipeline. Two tiers:

### Tier 1: Post-Compound Tail Resume (artifact-only -- validated)

If the session dies after Compound, a fresh session can complete the remaining tail from CHECKPOINT.md + disk artifacts alone.

**Critical dependency change:** update-learnings-noninteractive currently uses "most recent" discovery heuristics in 3 places:
- Line 30: solution doc defaults to "most recently modified file in docs/solutions/"
- Line 36: plan found "via solution doc's related_prs or most recent"
- Line 123: compound-engineering.local.md uses "most recent cycle"

**Fix required for Tier 1:** The `tail-resume` skill must pass explicit paths from CHECKPOINT.md as arguments to update-learnings-noninteractive. Specifically:
- Pass `solution_doc_path` as the `$ARGUMENTS` to update-learnings-noninteractive (it already accepts a path argument -- line 29-30)
- The learnings skill's Step 0 must then derive the plan path from the solution doc's YAML frontmatter (which contains a `plan:` or `related_prs:` field pointing to the plan), NOT from "most recent in docs/plans/"
- If the solution doc lacks a plan reference, `tail-resume` must also pass the plan path (add it as a second argument or write a `.tail-resume-context.md` temp file with both paths)

**Self-audit already works:** The self-audit agent receives 6 explicit path arguments (SKILL.md:492-498). All paths are in the CHECKPOINT.md schema. No discovery heuristics.

**Validation against actual tail steps (with the fix above):**

| Tail Step | Discovery Heuristic? | Fix | Resumable? |
|-----------|---------------------|-----|------------|
| Update Learnings Step 0 | Yes: "most recent" solution doc, "most recent" plan | tail-resume passes solution_doc_path as $ARGUMENTS; plan derived from solution doc frontmatter | Yes (after fix) |
| Update Learnings Steps 1-6 | No: all read from paths established in Step 0 | None needed | Yes |
| Verify Learnings | No: checks HANDOFF.md date, agent-pitfalls log, ID uniqueness | None needed | Yes |
| Update BUILD_TRACKING | No: with incremental writes, already complete | None needed | Yes |
| Verify BUILD_TRACKING | No: reads sections from BUILD_TRACKING.md | None needed | Yes |
| Self-Audit | No: receives 6 explicit path arguments | None needed | Yes |
| Verify Self-Audit | No: reads self-audit report, cross-refs HANDOFF.md | None needed | Yes |

**Result: Post-compound tail is resumable from artifacts, contingent on the tail-resume skill passing explicit paths to update-learnings-noninteractive.**

### Tier 2: Pre-Review Resume (unverified -- future work)

If the session dies before review, resumability depends on:
- Whether `/workflows:review` can be invoked on an already-assembled codebase without in-context knowledge of the build
- Whether `/workflows:compound` can produce a solution doc without having seen the review output in-context

These are unverified. Auditing these workflows is out of scope -- it's a future work item after post-compound resume is proven.

## Resume Contract Validation (Second Pass)

**Scenario:** Main session dies immediately after Compound. CHECKPOINT.md exists with `next_step: "Update Learnings"`. A fresh session reads CHECKPOINT.md.

**Step-by-step walkthrough:**

1. **tail-resume reads CHECKPOINT.md** → gets all explicit paths
2. **tail-resume invokes update-learnings-noninteractive** with `solution_doc_path` as argument
   - Step 0: reads solution doc at explicit path (not "most recent"). Reads plan via solution doc frontmatter. Reads review summary at review_summary_path from CHECKPOINT.md (requires tail-resume to write a context file or the learnings skill to accept it).
   - **Gap identified:** update-learnings-noninteractive Step 0 reads review summary from `docs/reviews/<branch>/REVIEW-SUMMARY.md` which it discovers from the branch name. CHECKPOINT.md carries `review_summary_path` but the learnings skill doesn't accept it as an argument. **Fix: tail-resume must either (a) verify the review summary exists at the expected path before invoking, or (b) write it to the conventional path if it's elsewhere.**
   - Steps 1-6: all read/write from paths established in Step 0. No discovery.
3. **Verify learnings:** reads HANDOFF.md, agent-pitfalls, checks dates. All file-based. ✓
4. **Verify BUILD_TRACKING:** reads BUILD_TRACKING.md sections. File-based. ✓ (already complete from incremental writes)
5. **Self-audit agent:** tail-resume passes 6 args from CHECKPOINT.md: run_id, reports_dir, plan_path, solution_doc_path, build_tracking_path, handoff_path. ✓
6. **Verify self-audit:** reads self-audit report at `reports_dir/self-audit.md`. File-based. ✓

**Gaps found:**
- update-learnings-noninteractive does not accept review_summary_path as an argument. The tail-resume skill must verify the review summary exists at the conventional path (`docs/reviews/<branch>/REVIEW-SUMMARY.md`) before invoking. If it doesn't exist (e.g., review wrote it elsewhere), tail-resume must flag this as a resume failure.
- update-learnings-noninteractive derives plan from "most recent" if solution doc frontmatter lacks a reference. The tail-resume skill must verify the solution doc's frontmatter contains a plan reference before invoking. If missing, pass plan_path from CHECKPOINT.md via a context file.

**Conclusion:** Post-compound tail is resumable with two preconditions enforced by tail-resume: (1) solution doc frontmatter contains plan reference, (2) review summary exists at conventional path. These are verifiable at checkpoint-write time -- if either is missing when CHECKPOINT.md is written, the checkpoint should include them as explicit overrides.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Phase shedding vs checkpoint | Checkpoint (hard stop) | Tail artifacts are mandatory per CLAUDE.md. Shedding = silent drift. |
| Separate canonical spec vs overwrite | Overwrite in-place | Dual source of truth causes drift. Git preserves history. |
| Deepening audit trail | docs/reports/<run-id>/deepening-applied.md | Plan is an execution doc, not a changelog. Keep it lean. |
| Scope | Project-local (sandbox) first | Test on a real build before promoting to global. |
| BUILD_TRACKING ownership | Orchestrator writes (not agents) | Agents run in worktrees -- can't access main branch BUILD_TRACKING. |
| BUILD_TRACKING timing | Incremental after each merge/gate | If context dies, BUILD_TRACKING is already complete up to that point. |
| Checkpoint trigger | Weighted orchestration-load heuristic | Agent count alone is insufficient -- deepening, review, and retries all contribute. Spec size excluded (hard to measure section vs full file). |
| Checkpoint data format | CHECKPOINT.md with explicit paths | No "most recent" discovery. Every artifact path is declared. |
| Checkpoint exit status | PAUSED_FOR_CONTEXT | Distinct from success (misleading) and failure (wrong -- build is fine). |
| Extraction | tail-resume as skill; BUILD_TRACKING append, checkpoint write, load calc inline | Only tail-resume has enough complexity to warrant a separate skill. The rest are one-liners. |
| Auto-resume | Out of scope | Manual resume first. Prove the artifact contract works before automating. |
| `/compact` | Unverified -- not part of the design | The checkpoint design works correctly without it. |

## Resolved Questions

1. **Context measurement:** No programmatic context API exists. The design uses a weighted orchestration-load heuristic instead.

2. **Checkpoint resume:** Manual resume only (Phase 1). tail-resume skill reads CHECKPOINT.md and passes explicit paths. Auto-resume is explicitly out of scope.

3. **`/compact` invocation:** Unverified. Not part of the design.

4. **Spec size in heuristic:** Excluded. Plans are 42-106KB on disk but the relevant metric (shared interface spec section size) is hard to measure automatically. Agent count + deepening + review + retries are sufficient discriminators for runs 047-050.

5. **Discovery heuristics in tail:** update-learnings-noninteractive uses "most recent" in 3 places. tail-resume fixes this by passing explicit paths and verifying preconditions (solution doc frontmatter has plan ref, review summary at conventional path).

## Prior Lessons Applied

- **autopilot-skips-non-step-instructions** (2026-05-06): Prose rules get skipped. The checkpoint and incremental BUILD_TRACKING writes must be numbered steps with explicit Bash commands, not guidelines.
- **compound-bash-instruction-refactor** (2026-04-09): Prescriptive syntax > prohibitive rules. BUILD_TRACKING appends use exact Bash commands (e.g., `echo "| 5 | lead-list | b909a5c | PASS |" >> BUILD_TRACKING.md`).
- **swarm-scale-shared-spec** (2026-03-30): Spec size grows linearly with agents. The canonical spec rewrite compresses amendments but won't shrink the base spec.

## Feed-Forward

- **Hardest decision:** Checkpoint as hard stop vs phase shedding. Shedding is more adaptive but violates the operating contract. Checkpoint is rigid but honest.
- **Rejected alternatives:** Phase shedding (silent process drift), separate canonical-spec.md (dual source of truth), deepening audit in plan (execution doc bloat), `/compact` as design dependency (unverified), auto-resume in Phase 1 (premature), spec size in heuristic (hard to measure section vs file).
- **Least confident:** Orchestration-load heuristic as checkpoint trigger. Concrete falsifiers:
  1. **False positive on prior success:** If run 049 (score 37) had deepening agents (which it didn't), the score would jump to 37+8=45, triggering a checkpoint on a build that completed successfully. Adding deepening to a 25-agent build should not auto-checkpoint.
  2. **False negative on future failure:** A 20-agent build with 4 deepening agents, 5 review agents, and 3 fix retries scores 20+8+7.5+9=44.5 -- above threshold. But a 20-agent build without deepening scores 20+0+7.5+3=30.5 -- below threshold. The heuristic is sensitive to retries (3x weight). If a build has many retries but few agents, it checkpoints when it might not need to.
  3. **Missing factor:** Total plan reads correlate with context usage but aren't captured. A build with unusually many assembly-fix cycles (which re-read the plan each time) would consume more context than the retry weight (3x) accounts for.
  The first build after this change will validate. If the heuristic false-positives on a build that would have completed, lower the weights. If it misses a failure, raise them.
