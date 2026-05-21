---
title: Autopilot Context Exhaustion at Scale -- 31-Agent Swarm Tail Loss Prevention
date: 2026-05-20
status: complete
problem_type: context-management
component: autopilot-skill
symptoms:
  - Shared tail phase hit 0% context at 31-agent scale
  - BUILD_TRACKING.md not populated (lost)
  - Self-audit report not generated (lost)
  - Learnings propagation not completed (lost)
  - All tail artifacts required manual recovery after session exit
root_cause: Autopilot skill assumes unlimited context; at 31 agents, orchestration overhead (spawn prompts, agent outputs, plan re-reads, tail synthesis) exceeds the context window before tail phase begins
solution_type: hardening
tags:
  - autopilot
  - context-management
  - swarm
  - tail-artifacts
  - checkpoint
  - build-tracking
  - resilience
related_runs:
  - run-050
  - run-049
  - run-048
  - run-047
related_solutions:
  - docs/solutions/2026-05-06-autopilot-skips-non-step-instructions.md
  - docs/solutions/2026-04-09-compound-bash-instruction-refactor.md
  - docs/solutions/2026-05-13-sandbox-autonomy-hardening.md
  - docs/solutions/2026-04-09-autopilot-swarm-orchestration.md
  - docs/solutions/2026-03-30-swarm-scale-shared-spec.md
  - docs/solutions/2026-05-20-gigsheet-31-agent-swarm-build.md
  - docs/solutions/2026-05-20-venueconnect-25-agent-swarm-build.md
feed_forward:
  risk: "Orchestration-load heuristic (>30 threshold) is calibrated on 4 data points (runs 047-050); known false positive on run 048 (score 40.5). First real build validates."
  verify_first: true
---

# Autopilot Context Exhaustion at Scale -- 31-Agent Swarm Tail Loss Prevention

## Problem

Run 050 (GigSheet, 31-agent swarm build) hit 0% context during the shared tail phase. The build completed all code phases successfully -- 0 FC37 errors, 0 merge conflicts, 46/46 smoke tests passing -- but BUILD_TRACKING, self-audit, and learnings propagation were lost. The orchestrator carried all accumulated state in-context instead of persisting it to disk, and the tail phase exhausted remaining context before mandatory artifacts could be written.

Symptom: PIPELINE_PASS on code quality, PIPELINE_FAIL on run completeness. All three mandatory tail artifacts missing simultaneously.

## Root Cause

Five compounding factors:

1. **Prompt accumulation**: The full spec was passed as prompt text to approximately 42-50 subagents and gates across the run. Each spawn call retained that text in the orchestrator's context window.
2. **No state persistence**: The orchestrator carried all agent status, gate results, and run metadata in-context. Nothing was written to disk incrementally.
3. **Uncollapsed spec**: Post-deepening amendments lived alongside the original plan. Downstream agents received original text plus corrections rather than a single canonical spec, doubling the per-agent prompt overhead.
4. **Tail re-reads everything**: The tail phase (BUILD_TRACKING fill, self-audit, learnings) reads plan, review summary, and all agent outputs again at the moment context is tightest.
5. **Deferred BUILD_TRACKING fill**: All 31 agent status rows were reconstructed from memory at run end instead of being written after each merge. A 31-agent reconstruction is maximally expensive at exactly the wrong moment.

## Solution

Seven tasks implemented across three files (`.claude/skills/autopilot/SKILL.md`, `.claude/skills/update-learnings-noninteractive/SKILL.md`, `.claude/skills/tail-resume/SKILL.md`).

### Task 1: update-learnings-noninteractive argument extensions

Added `--plan <path>` and `--review-summary <path>` optional flags. When called from tail-resume, all three paths are explicit from CHECKPOINT.md. When called normally without flags, existing "most recent" discovery behavior is unchanged. ~14 lines modified.

### Task 2: Incremental BUILD_TRACKING writes (swarm only)

Orchestrator appends agent status rows immediately after each merge. Five insert points:

- After each agent merge: one row appended to the AGENT_STATUS table
- After ownership gate: gate result appended
- After contract check: gate result appended
- After smoke test: gate result appended
- After review: gate result appended

Step 1.5 template cleanup replaces block-format scaffolding with clean table headers suitable for incremental appends. Solo builds retain existing bulk-fill behavior.

### Task 3: Run-id generation moved earlier (Step 6.1)

Run-id and `docs/reports/<run-id>/` created before deepening merge so the reports directory exists for the audit trail.

### Task 4: Post-deepening canonical spec rewrite (Step 6.5)

Merges all accepted deepening corrections into the plan file in-place. Audit trail written to `docs/reports/<run-id>/deepening-applied.md`. All downstream agents read only the rewritten plan, eliminating dual-source overhead.

### Task 5: Context-budget checkpoint gate

Weighted orchestration-load heuristic placed after Compound and after swarm BUILD_TRACKING fill, before Update Learnings:

```
load = swarm_agents + (deepening_agents * 2) + (review_agents * 1.5) + (fix_retries * 3)
```

If `load > 30`: writes CHECKPOINT.md with explicit artifact paths, commits, exits with `PAUSED_FOR_CONTEXT`.

### Task 6: tail-resume skill (new, 85 lines)

Manual-only skill that reads CHECKPOINT.md, validates `PAUSED_FOR_CONTEXT` status, then runs the tail sequence using explicit paths: Update Learnings, Verify Learnings, Verify BUILD_TRACKING, Self-Audit, Verify Self-Audit.

### Task 7: Solo/swarm BUILD_TRACKING conditional

Solo builds use existing bulk fill. Swarm builds use incremental appends. Both paths feed into the same completeness gate.

### Review findings resolved

- **P1-1**: Dangling reference to removed heuristic component -- fixed.
- **P1-2**: Checkpoint was placed post-compound but before swarm BUILD_TRACKING FAILURES/RUN_METRICS fill -- moved to after fill.
- **P2s (4, all LOW)**: Mixed table/heading formats, verbose CHECKPOINT template, template file not updated, slightly shorter error messages in tail-resume. Deferred.

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Phase shedding vs checkpoint | Checkpoint (hard stop) | Tail artifacts are mandatory per CLAUDE.md. Shedding = silent process drift -- the exact failure mode of run 050. |
| Separate canonical spec vs overwrite | Overwrite in-place | Dual source of truth causes drift. Git preserves history. |
| BUILD_TRACKING ownership | Orchestrator writes, not agents | Agents run in worktrees -- can't access main branch BUILD_TRACKING.md. |
| Checkpoint trigger | Weighted heuristic, not raw agent count | Deepening, review, and retries contribute context pressure beyond raw count. |
| Checkpoint placement | Post-compound, post-BUILD_TRACKING fill | All synthesis artifacts exist. Resume only runs learnings + self-audit (cheapest tail steps). |
| Auto-resume | Out of scope | Prove the artifact contract works manually before automating. |

## Code Examples

### Incremental BUILD_TRACKING append (swarm path)

```bash
echo "| <N> | <role> | <commit_hash> | PASS |" >> BUILD_TRACKING.md
```

Called immediately after each successful agent merge. One Bash call per append (per FC8).

### Weighted load heuristic

```
load = swarm_agents + (deepening_agents * 2) + (review_agents * 1.5) + (fix_retries * 3)
threshold = 30
```

Run 050 example: 31 + (4 * 2) + (5 * 1.5) + (2 * 3) = 31 + 8 + 7.5 + 6 = 52.5 -- checkpoint fires.
Run 047 example: 16 + (0 * 2) + (4 * 1.5) + (1 * 3) = 16 + 0 + 6 + 3 = 25 -- no checkpoint.

### CHECKPOINT.md schema

```yaml
---
status: PAUSED_FOR_CONTEXT
run_id: "<run-id>"
date: "<today>"
branch: "<current branch>"
project_name: "<project name>"
---

plan_path: <path to plan>
solution_doc_path: <path to solution doc>
review_summary_path: <path to review summary>
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

## Validation

### Against historical runs (047-050)

| Run | Agents | Deep | Review | Retries | Score | Context died? | Checkpoint fires? |
|-----|--------|------|--------|---------|-------|---------------|-------------------|
| 047 | 16 | 0 | 4 | 1 | 25 | No | No (correct) |
| 048 | 20 | 5 | 5 | 1 | 40.5 | No | Yes (false positive) |
| 049 | 25 | 0 | 4 | 2 | 37 | No | Yes (conservative) |
| 050 | 31 | 4 | 5 | 2 | 52.5 | Yes | Yes (correct) |

The >30 threshold correctly identifies run 050 but false-positives on run 048. Cost of false positive: brief manual resume (~5 min) after compound. Cost of false negative: full artifact reconstruction (~30 min).

## Prevention & Best Practices

### Immediate Prevention (implemented)

- **Context death during tail:** Heuristic gate fires before the shared tail begins, writing CHECKPOINT.md and exiting cleanly. Prevents the run 050 failure mode.
- **State loss mid-run:** Incremental BUILD_TRACKING writes mean even a mid-run crash leaves a recoverable record.
- **Redundant context inflation:** Canonical spec rewrite collapses plan + deepening notes into one document before work agents launch.
- **Manual tail recovery:** tail-resume gives a deterministic entry point using explicit paths from CHECKPOINT.md.

### Monitoring & Calibration

- Record actual post-compound context percentage alongside heuristic score for the next 2 large swarm runs.
- Track false positive rate: any run that triggers PAUSED_FOR_CONTEXT but would have finished cleanly.
- If 2 consecutive large swarm runs (25+ agents) complete without checkpoint and post-compound context stays above 15%, consider lowering threshold.
- If any run below threshold hits context death, raise threshold by 5 points.

### Future Hardening (not yet implemented)

- **Tier 2 pre-review resume:** Add a second gate after work phase completes, before review launches.
- **Auto-resume:** Detect PAUSED_FOR_CONTEXT exit code and spawn fresh session automatically.
- **Per-agent context telemetry:** Sample context usage after every N agents during work phase and project forward.
- **Weight learning from run history:** Replace hand-tuned constants with data-derived weights once run history reaches 8-10 points.

### Design Pattern: Disk as Working Memory

Long-running orchestrators that spawn many sub-agents face a structural problem: the orchestrating context window accumulates a summary of every agent's output, and this growth is proportional to swarm size, not to the work remaining.

The generalized lesson: **disk is the working memory of the orchestrator, not the context window.**

- Write state to disk incrementally at the granularity of individual agent completions, not at phase boundaries.
- Treat the context window as a read-through cache: recent state for speed, durable record on disk.
- Before any high-cost operation, check whether the context budget can absorb the full operation. If not, flush and exit cleanly.
- Design every phase to be resumable from disk state alone.
- Compact aggressively at phase boundaries: the canonical spec rewrite converts accumulated drift into a single authoritative file.

## Related Documentation

### Direct References (lessons applied in this solution)

- [Autopilot Skips Non-Step Instructions](docs/solutions/2026-05-06-autopilot-skips-non-step-instructions.md) -- all new logic encoded as numbered skill steps, not prose
- [Compound Bash Instruction Refactor](docs/solutions/2026-04-09-compound-bash-instruction-refactor.md) -- one-command-per-Bash-call rule for all skill steps
- [Sandbox Autonomy Hardening](docs/solutions/2026-05-13-sandbox-autonomy-hardening.md) -- enforcement-in-skill principle; checkpoint is extension of gate model
- [Swarm-Enabled Autopilot Skill](docs/solutions/2026-04-09-autopilot-swarm-orchestration.md) -- original skill architecture that context gates build on
- [Swarm Scale -- Shared Spec](docs/solutions/2026-03-30-swarm-scale-shared-spec.md) -- spec size grows with agent count, motivating context budget awareness

### Related Builds (swarm runs that informed the heuristic)

- [GigSheet: 31-Agent Swarm](docs/solutions/2026-05-20-gigsheet-31-agent-swarm-build.md) -- 31 agents, 46/46 smoke tests, 0% context at tail; primary evidence base
- [VenueConnect: 25-Agent Swarm](docs/solutions/2026-05-20-venueconnect-25-agent-swarm-build.md) -- 25 agents, grade B; prior largest swarm
- [Client Music Planner: 20-Agent Swarm](docs/solutions/2026-05-19-client-music-planner-20-agent-swarm-build.md) -- 20 agents, run 048; false positive calibration point
- [Solopreneur Command Center: 16-Agent Swarm](docs/solutions/2026-05-19-solopreneur-command-center-swarm-build.md) -- 16 agents, grade A; baseline for no-checkpoint case
- [Invoice & CRM: 15-Agent Swarm](docs/solutions/2026-05-19-invoice-crm-15-agent-swarm-build.md) -- 15 agents, run 046; established assembly-fix patterns

### Cross-References

- [Swarm Build Alignment -- Shared Interface Spec Pattern](docs/solutions/2026-03-30-swarm-build-alignment.md) -- origin of shared spec discipline
- [Spec Convergence Loop](docs/solutions/2026-04-30-spec-convergence-loop.md) -- multi-round spec validation that generates the deepening corrections this solution collapses
- [Error Injection -- Pipeline Recovery](docs/solutions/2026-04-12-error-injection-pipeline-recovery.md) -- proved contract-check/assembly-fix/re-verify cycle; the recovery path checkpoint gates protect

## Feed-Forward

- **Hardest decision:** Keeping >30 threshold despite the known run 048 false positive (score 40.5). With post-compound checkpoint placement, the cost of a false positive is ~5 minutes of manual resume vs context death costing ~30 minutes of artifact reconstruction.
- **Rejected alternatives:** Phase shedding (silent drift), `/compact` as dependency (unverified), auto-resume in Phase 1 (premature), spec size in heuristic (unmeasurable section vs file), separate canonical-spec.md (dual source of truth), pre-compound checkpoint (compound resumability unverified).
- **Least confident:** The orchestration-load heuristic. Known false positive on run 048 (40.5). A 28-agent build with 0 deepening scores 37 and could die without triggering checkpoint. First real build validates.
