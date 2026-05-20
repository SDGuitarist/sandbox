---
title: Autopilot Context Window Optimization
date: 2026-05-20
status: brainstorm-revised
trigger: Run 050 (GigSheet, 31-agent swarm) hit 0% context during shared tail
scope: .claude/skills/autopilot/SKILL.md + .claude/agents/ + new helper skill(s)
feed_forward:
  risk: "Agent-count heuristic is a proxy, not a measurement -- context pressure depends on spec size, deepening depth, and review volume, not just agent count"
  verify_first: true
---

# Autopilot Context Window Optimization

## What We're Solving

Run 050 completed all code phases (brainstorm, plan, deepen, 31-agent swarm, contract check, smoke tests, review, compound) but hit 0% context during the shared tail. BUILD_TRACKING, self-audit, and learnings propagation were lost and had to be completed manually.

This is a **context-management failure, not a code-quality failure.** The build was the best ever mechanically (0 FC37, 0 merge conflicts, 46/46 smoke tests). The autopilot's orchestration overhead scaled past the context window.

### Root Causes (from analysis)

1. **Plan passed to ~42-50 subagents/gates** across the run. Each spawn call includes the full 15KB spec as prompt text, which stays in the orchestrator's context. Subagent internal work uses separate context, but the orchestrator pays the prompt cost for each spawn.
2. **No state persistence** -- the orchestrator carries all state in-context instead of writing it to disk incrementally.
3. **Post-deepening amendments live alongside original plan** -- agents get original + corrections, not a collapsed canonical spec.
4. **Tail phase reads everything again** -- self-audit reads all reports + BUILD_TRACKING + HANDOFF + solution doc + plan (~70KB) at the end when context is tightest.
5. **BUILD_TRACKING filled at end** -- 31 agent statuses reconstructed from memory instead of written incrementally.

## What We're Building

Three hardening measures for the autopilot skill, plus continuous lean-context optimization. All new logic lives in helper skills/agents -- not inlined into the already-500-line SKILL.md.

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
---

plan_path: docs/plans/2026-05-20-gigsheet-plan.md
solution_doc_path: docs/solutions/2026-05-20-gigsheet-31-agent-swarm-build.md
review_summary_path: docs/reviews/master/REVIEW-SUMMARY.md
reports_dir: docs/reports/050/
build_tracking_path: BUILD_TRACKING.md
handoff_path: HANDOFF.md

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
| Spec size (KB) | 0.5x per KB above 10KB | Larger specs amplify the per-agent prompt cost |

**Initial guardrails (calibrate after next 2 large swarms):**
- Before review: if weighted load > 35, write checkpoint
- Before tail: if weighted load > 25, write checkpoint
- Example: 31 agents (31) + 4 deepening (8) + 5 review (7.5) + 1 fix retry (3) + 15KB spec (2.5) = 52 → checkpoint before review

These thresholds are initial guardrails, not the final model. The first build after this change will calibrate them.

**Why this instead of phase shedding:** The tail phases (BUILD_TRACKING, HANDOFF, learnings, self-audit) are all mandatory per CLAUDE.md:34. Shedding mandatory artifacts turns context pressure into silent process drift. A hard stop with resumable state is deterministic recovery.

### 3. Post-Deepening Canonical Spec Rewrite

After deepening agents return corrections, merge all accepted changes back into the plan file in-place.

**What changes:**
- Deepening ends with a new step: the orchestrator merges all accepted corrections into the plan file (it already has the plan and amendment outputs in context at this point, so no additional read cost)
- Commit the rewritten plan before swarm launch
- All downstream agents read only the rewritten plan, never raw amendment notes
- Deepening audit notes (what changed and why) are written to `docs/reports/<run-id>/deepening-applied.md` as audit trail, not kept in the plan itself

**Why overwrite instead of separate file:** A separate canonical-spec.md creates dual source of truth. This repo has learned (repeatedly) that dual source of truth causes drift: review updates one file, agent briefs reference the other, orchestrator has to decide which wins. Git preserves the pre-deepening version. One live spec, git for history.

**Why audit notes in reports/ instead of the plan:** The plan is an execution document. `## Deepening Applied` would be metadata that agents never use but carry in every brief. Putting the audit trail in `docs/reports/<run-id>/deepening-applied.md` keeps the plan lean and the audit accessible.

### 4. Continuous Lean-Context Optimization

Not an emergency response -- these are normal operating practices:

- **Persist immediately:** Write state to disk instead of carrying it in context. Agent results → BUILD_TRACKING row. Gate results → report file. Don't summarize in-context.
- **Shorten in-session summaries:** The orchestrator doesn't need verbose agent output. Status + commit hash + file count is sufficient.
- **Avoid re-reads:** Once a report file is written, reference it by path. Don't re-read the plan after it's been read for agent briefs.
- **Collapse deepening:** The canonical spec rewrite (#3) eliminates the biggest re-read offender.

## Extraction Strategy

The autopilot skill is already ~522 lines -- past the repo's ~500-line complexity budget. The new checkpoint/BUILD_TRACKING/resume logic must NOT be inlined into SKILL.md.

**Proposed extraction:**

| New artifact | Type | Responsibility |
|-------------|------|----------------|
| `checkpoint-writer` | Agent (.claude/agents/) | Receives run state, writes CHECKPOINT.md with the full schema above |
| `build-tracking-writer` | Helper skill (.claude/skills/) | Appends a single row to BUILD_TRACKING.md. Called by orchestrator after each merge/gate with structured arguments |
| `tail-resume` | Skill (.claude/skills/) | Reads CHECKPOINT.md, validates disk artifacts, runs remaining mandatory tail steps. Manual invocation only (Phase 1) |

The autopilot SKILL.md changes are minimal:
1. Add a call to `build-tracking-writer` after each merge/gate (~5 lines per call site)
2. Add checkpoint evaluation + `checkpoint-writer` call at two gates (~10 lines)
3. Add post-deepening spec rewrite step (~8 lines)
4. Remove the end-of-run BUILD_TRACKING fill step (net reduction)

Estimated net change to SKILL.md: +15 lines (additions) - 12 lines (removed BUILD_TRACKING fill) = +3 lines.

## Design Principle

Use disk as working memory, context only for the current step. The autopilot should be resumable at any point -- if the session dies after step N, a fresh session reads artifacts from disk and continues from step N+1.

## Resumability Analysis

Resumability is not uniform across the pipeline. Two tiers:

### Tier 1: Post-Compound Tail Resume (artifact-only -- validated)

If the session dies after Compound, a fresh session can complete the remaining tail from CHECKPOINT.md + disk artifacts alone.

**Validation against actual tail steps:**

| Tail Step | Needs In-Context State? | Disk Artifacts Sufficient? | Notes |
|-----------|------------------------|---------------------------|-------|
| Update Learnings | No | Yes | Reads solution doc, plan, review summary -- all on disk. Step 0 of update-learnings-noninteractive loads context from files, not from prior conversation. |
| Verify Learnings | No | Yes | Checks HANDOFF.md date, agent-pitfalls Update Log, ID uniqueness -- all file reads. |
| Update BUILD_TRACKING | No | Yes | With incremental writes, BUILD_TRACKING is already complete. This step becomes a verification, not a reconstruction. |
| Verify BUILD_TRACKING | No | Yes | Reads BUILD_TRACKING sections -- file check only. |
| Self-Audit | No | Yes | Agent receives 6 explicit paths (all in CHECKPOINT.md schema). Reads reports + BUILD_TRACKING + HANDOFF + solution doc. |
| Verify Self-Audit | No | Yes | Reads self-audit report and cross-references against HANDOFF.md. File checks only. |

**Result: Post-compound tail is fully resumable from artifacts.** Every step loads its own context from disk. No step depends on orchestrator memory from earlier phases.

### Tier 2: Pre-Review Resume (unverified -- future work)

If the session dies before review, resumability depends on:
- Whether `/workflows:review` can be invoked on an already-assembled codebase without in-context knowledge of the build
- Whether `/workflows:compound` can produce a solution doc without having seen the review output in-context

These are unverified. The review and compound workflows may depend on conversational context (e.g., the review skill may expect to find prior phase output in-context). Auditing these workflows is out of scope for this brainstorm -- it's a future work item after post-compound resume is proven.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Phase shedding vs checkpoint | Checkpoint (hard stop) | Tail artifacts are mandatory per CLAUDE.md. Shedding = silent drift. |
| Separate canonical spec vs overwrite | Overwrite in-place | Dual source of truth causes drift. Git preserves history. |
| Deepening audit trail | docs/reports/<run-id>/deepening-applied.md | Plan is an execution doc, not a changelog. Keep it lean. |
| Scope | Project-local (sandbox) first | Test on a real build before promoting to global. |
| BUILD_TRACKING ownership | Orchestrator writes (not agents) | Agents run in worktrees -- they can't access main branch BUILD_TRACKING. |
| BUILD_TRACKING timing | Incremental after each merge/gate | If context dies, BUILD_TRACKING is already complete up to that point. |
| Checkpoint trigger | Weighted orchestration-load heuristic | Agent count alone is insufficient -- spec size, deepening, review, and retries all contribute. |
| Checkpoint data format | CHECKPOINT.md with explicit paths | No "most recent" discovery. Every artifact path is declared. |
| Checkpoint exit status | PAUSED_FOR_CONTEXT | Distinct from success (misleading) and failure (wrong -- build is fine). |
| New logic location | Helper skills/agents (not inlined into SKILL.md) | SKILL.md is already at ~500 lines. Extraction keeps it maintainable. |
| Auto-resume | Out of scope | Manual resume first. Prove the artifact contract works before automating. |
| `/compact` | Unverified -- not part of the design | May be callable from skills, may not. The checkpoint design works correctly without it. If `/compact` later proves callable, it becomes an optional optimization. |

## Resolved Questions

1. **Context measurement:** No programmatic context API exists. The `ctx: N%` in the status bar is client-side only. The design uses a weighted orchestration-load heuristic instead.

2. **Checkpoint resume:** Manual resume only (Phase 1). Success criterion: new session reads CHECKPOINT.md, needs no prior conversational context, completes remaining mandatory artifacts, produces identical final repo state. Auto-resume is explicitly out of scope until 1-2 successful manual resumes prove the artifact contract.

3. **`/compact` invocation:** Unverified. Not part of the checkpoint design. If it works, it's a bonus optimization. The design must work without it.

## Prior Lessons Applied

- **autopilot-skips-non-step-instructions** (2026-05-06): Prose rules get skipped. The checkpoint and incremental BUILD_TRACKING writes must be numbered steps with explicit Bash commands, not guidelines.
- **compound-bash-instruction-refactor** (2026-04-09): Prescriptive syntax > prohibitive rules. The build-tracking-writer skill should use exact Bash commands (e.g., `echo "| 5 | lead-list | b909a5c | PASS |" >> BUILD_TRACKING.md`).
- **swarm-scale-shared-spec** (2026-03-30): Spec size grows linearly with agents. The canonical spec rewrite compresses amendments but won't shrink the base spec -- this is why spec size is a factor in the orchestration-load heuristic.

## Feed-Forward

- **Hardest decision:** Checkpoint as hard stop vs phase shedding. Shedding is more adaptive but violates the operating contract. Checkpoint is rigid but honest.
- **Rejected alternatives:** Phase shedding (silent process drift), separate canonical-spec.md (dual source of truth), `## Deepening Applied` in plan (execution doc bloat), `/compact` as design dependency (unverified), auto-resume in Phase 1 (premature).
- **Least confident:** Agent-count heuristic as checkpoint trigger. No programmatic context measurement exists, so we're using a weighted proxy. The weights (1x, 2x, 1.5x, 3x, 0.5x) and thresholds (35/25) are based on run 050's failure profile but have not been validated on other builds. The first build after this change will calibrate. The heuristic may need to become a simple lookup table (agent count + spec size → checkpoint yes/no) if the weighted formula proves too noisy.
