---
title: Autopilot Context Window Optimization
date: 2026-05-20
status: brainstorm-complete
trigger: Run 050 (GigSheet, 31-agent swarm) hit 0% context during shared tail
scope: .claude/skills/autopilot/SKILL.md + .claude/agents/
feed_forward:
  risk: "Context budget checkpoint may trigger too early or too late -- threshold calibration is uncertain"
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

Three hardening measures for the autopilot skill, plus continuous lean-context optimization:

### 1. Incremental BUILD_TRACKING

Write to BUILD_TRACKING.md after each merge/gate, not in a single pass at the end.

**What changes:**
- After each agent merge: append agent status row (commit hash, PASS/FAIL, file count)
- After each gate (contract check, smoke test, ownership): append gate result
- After review: append P1/P2 counts and fix commit hashes
- BUILD_TRACKING becomes a live log, not a retrospective reconstruction

**Why:** If context dies at any point, BUILD_TRACKING already has everything up to the last completed step. The manual follow-up session doesn't need to reverse-engineer agent status from git log.

### 2. Context-Budget Checkpoint

A hard safety gate at two points: before review and before shared tail.

**Checkpoint behavior:**
- At each gate: call `/compact` to reclaim context proactively
- If agent count exceeds threshold (>25 before review, >20 before tail): write checkpoint
- Write CHECKPOINT.md to disk with:
  - Run ID
  - Last completed phase and step
  - Next exact step to run
  - Completed artifacts (paths)
  - Pending mandatory artifacts
  - Pending review findings / deferred keys
  - Report files to trust as source of truth
- Exit with status `PAUSED_FOR_CONTEXT` (not success, not failure)

**Why this instead of phase shedding:** The tail phases (BUILD_TRACKING, HANDOFF, learnings, self-audit) are all mandatory per CLAUDE.md:34. Shedding mandatory artifacts turns context pressure into silent process drift. A hard stop with resumable state is deterministic recovery.

**Trigger:** Agent-count heuristic (>25 before review, >20 before tail) plus proactive `/compact` at every phase boundary. Calibrate thresholds after next 2 large swarm builds.

### 3. Post-Deepening Canonical Spec Rewrite

After deepening agents return corrections, merge all accepted changes back into the plan file in-place.

**What changes:**
- Deepening ends with a new step: the orchestrator merges all accepted corrections into the plan file (it already has the plan and amendment outputs in context at this point, so no additional read cost)
- Add a `## Deepening Applied` summary section listing what changed
- Commit the rewritten plan before swarm launch
- All downstream agents read only the rewritten plan, never raw amendment notes
- Amendment artifacts persist in docs/reports/<run-id>/ as audit trail, not execution input

**Why overwrite instead of separate file:** A separate canonical-spec.md creates dual source of truth. This repo has learned (repeatedly) that dual source of truth causes drift: review updates one file, agent briefs reference the other, orchestrator has to decide which wins. Git preserves the pre-deepening version. One live spec, git for history.

### 4. Continuous Lean-Context Optimization

Not an emergency response -- these are normal operating practices:

- **Persist immediately:** Write state to disk instead of carrying it in context. Agent results → BUILD_TRACKING row. Gate results → report file. Don't summarize in-context.
- **Shorten in-session summaries:** The orchestrator doesn't need verbose agent output. Status + commit hash + file count is sufficient.
- **Avoid re-reads:** Once a report file is written, reference it by path. Don't re-read the plan after it's been read for agent briefs.
- **Collapse deepening:** The canonical spec rewrite (#3) eliminates the biggest re-read offender.

## Design Principle

Use disk as working memory, context only for the current step. The autopilot should be resumable at any point -- if the session dies after step N, a fresh session reads artifacts from disk and continues from step N+1.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Phase shedding vs checkpoint | Checkpoint (hard stop) | Tail artifacts are mandatory per CLAUDE.md. Shedding = silent drift. |
| Separate canonical spec vs overwrite | Overwrite in-place | Dual source of truth causes drift. Git preserves history. |
| Scope | Project-local (sandbox) first | Test on a real build before promoting to global. |
| BUILD_TRACKING timing | Incremental after each merge/gate | If context dies, BUILD_TRACKING is already complete up to that point. |
| Checkpoint trigger | Agent-count heuristic + proactive /compact | No programmatic context API exists. Agent count is the best observable proxy. |
| Checkpoint data format | CHECKPOINT.md with structured fields | Must be readable by a fresh session with no prior context. |
| Checkpoint exit status | PAUSED_FOR_CONTEXT | Distinct from success (misleading) and failure (wrong -- build is fine). |

## Resumability Test

The brainstorm includes this validation criterion: **Can the tail be resumed from artifacts alone if the main session dies immediately after compound?**

For this to pass:
- BUILD_TRACKING.md must have all agent statuses and gate results (written incrementally)
- HANDOFF.md must be written during compound (already happens)
- Solution doc must be written during compound (already happens)
- CHECKPOINT.md must record exactly which tail steps remain
- A fresh session reading CHECKPOINT.md + existing artifacts must be able to complete learnings + self-audit without re-reading the plan or re-running any code phase

## Resolved Question (context measurement -- researched 2026-05-20)

**No programmatic context measurement exists.** The `ctx: N%` in the status bar is client-side only (fed to statusline.sh via JSON stdin). No tool, API, env var, or system variable exposes this to skills or agents at runtime. `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` controls compaction threshold but doesn't expose a measurement.

**Design consequence:** The checkpoint gates cannot use percentage-based triggers. The design falls back to two mechanisms:

1. **Proactive `/compact` calls** between major phases (post-deepening, post-assembly, pre-review, pre-tail). This is a real command that skills can invoke to reclaim context before it's critical.
2. **Agent-count heuristic** as checkpoint trigger. Data from runs 047-050 shows context death correlates with agent count: 16 (OK), 20 (OK), 25 (OK), 31 (died). Threshold: if agent count > 25, checkpoint before review. If > 20, checkpoint before tail.

This is a deliberate fallback, not an assumption. The heuristic is less precise than a percentage gate but is implementable today.

## Resolved Questions

1. **Context threshold:** See "Resolved Question" section above. Agent-count heuristic + proactive `/compact`. Guardrails on from day one, calibrated with evidence from next 2 large swarms.

2. **Checkpoint resume mechanism:** Hybrid -- manual resume first, auto-resume later. Phase 1: add checkpoint writing with strict CHECKPOINT.md schema. Phase 2: require manual resume for next 1-2 large swarms. Phase 3: after successful manual resumes prove the artifact contract works, add auto-resume mode to the autopilot skill. Success criterion for manual resume: new session reads CHECKPOINT.md, needs no prior conversational context, completes remaining mandatory artifacts, produces identical final repo state.

3. **`/compact` invocation:** Needs verification during planning -- can the autopilot skill call `/compact` while running in bypass-permissions mode? If not, the plan must prescribe an equivalent mechanism (e.g., explicit instructions to "summarize and discard prior phase context").

## Prior Lessons Applied

- **autopilot-skips-non-step-instructions** (2026-05-06): Prose rules get skipped. The checkpoint must be a numbered step, not a "when context is low" guideline.
- **compound-bash-instruction-refactor** (2026-04-09): Prescriptive syntax > prohibitive rules. The incremental BUILD_TRACKING writes should use exact Bash commands, not "update BUILD_TRACKING after each merge."
- **swarm-scale-shared-spec** (2026-03-30): Spec size grows linearly with agents. The canonical spec rewrite compresses amendments but won't shrink the base spec.

## Feed-Forward

- **Hardest decision:** Checkpoint as hard stop vs phase shedding. Shedding is more adaptive but violates the operating contract. Checkpoint is rigid but honest.
- **Rejected alternatives:** Phase shedding (silent process drift), separate canonical-spec.md (dual source of truth), git tag for pre-deepening (solves recoverability, not execution clarity).
- **Least confident:** Agent-count heuristic as checkpoint trigger. No programmatic context measurement exists, so we're using agent count as a proxy. The >25/>20 thresholds are based on runs 047-050 but the correlation between agent count and context pressure depends on spec size, deepening depth, and review volume -- all of which vary per build. The first build after this change will validate or invalidate the thresholds.
