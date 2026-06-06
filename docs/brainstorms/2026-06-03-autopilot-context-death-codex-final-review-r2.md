# Codex Final Review Resubmission: Autopilot Context Death Solution (R3)

## Start Here

Read these files in order:
1. `CLAUDE.md` -- operating contract
2. `.claude/skills/autopilot/SKILL.md` -- the autopilot skill being redesigned
3. `docs/brainstorms/2026-06-03-autopilot-context-death-solution-brainstorm.md` -- **the brainstorm (status: brainstorm-revised-r3)**
4. `docs/reports/spike-nested-worktree-delegation.md` -- **the completed spike report**

## Why This Is a Resubmission

You returned NO PASS on R2 with one P0:

> The brainstorm makes docs/reports/spike-nested-worktree-delegation.md a hard
> pre-plan dependency, but that report does not exist.

That P0 is resolved. The spike has been run. The report exists. Additionally, all 5 P1s and 3 P2s from your review have been addressed in R3.

## What Changed Since Your NO PASS (R2 -> R3)

### P0 Resolution: Spike Completed

The nested worktree delegation spike ran 3 independent tests:
1. General-purpose sub-agent: Agent tool not available.
2. General-purpose sub-agent (direct check, no ToolSearch): Agent tool not available.
3. Typed sub-agent (tail-runner type with explicit `tools: Agent`): Agent tool not available.

**Verdict: REDUCED DELEGATION.** Sub-agents do not have the Agent tool. This is a platform limitation. swarm-runner scope is fixed at Steps 11w-16w (assembly + verification). The orchestrator keeps worker spawn (Steps 7w-10.5w).

The brainstorm's Pre-Plan Spike section is now marked COMPLETED with the result summary and architecture impact inlined.

### P1 Resolutions

| Your P1 Finding | Fix Applied |
|-----------------|-------------|
| Bounded summary may not fit under 500 chars | Split into two tiers. Tier 1: pipe-delimited decision line, under 200 chars, always returned. Tier 2: detail fields written to BUILD_TRACKING.md frontmatter, not returned inline. 500-char gate replaced with 200-char gate on Tier 1. |
| Spike parallel test (3 agents) doesn't validate swarm scale | Spike is moot (nested spawn impossible). Stage 3 roadmap requires validation on a 12+ agent build where the orchestrator spawns workers and swarm-runner handles assembly. |
| bypassPermissions spike test underspecified | Spike is moot (nested spawn impossible). Finding recorded in spike report. |
| BUILD_TRACKING frontmatter fragile under repeated Edit | Added write-frequency table. Most fields are write-once. Only 3 fields edited frequently (phase, status, context_proxy_chars), all top-level. Rule: orchestrator edits only top-level fields; phase agents write their sub-section once. |
| Plan should include later scale validation at 10-12 agents | Stage 3 success criterion requires validation on a 12+ agent build. |

### P2 Resolutions

| Your P2 Finding | Fix Applied |
|-----------------|-------------|
| Absence of CHECKPOINT.md is weak proof of unattended completion | Hard Success Gate 1 now uses `manual_resume: false` AND `final_status: "DONE"` from BUILD_TRACKING frontmatter. |
| Context proxy metric is incomplete | Acknowledged in measurement plan as a proxy, not sole proof. Plan will use it for relative comparison only. |
| Timeout spike test should use short threshold | Spike is moot (nested spawn impossible). |

### Additional Changes

- **swarm-runner scope updated throughout:** Architecture diagram, Layer 2 description, Stage 3 roadmap, Risk 2, Feed-Forward all reflect confirmed 11w-16w scope.
- **Risk 2 marked RESOLVED** with spike report reference.
- **Feed-Forward updated:** Least confident items changed from nested delegation (resolved) to BUILD_TRACKING frontmatter reliability and reduced swarm-runner context savings.
- **Latent bug noted:** tail-runner Step 8 assumes Agent tool access that sub-agents don't have. Flagged for separate investigation, not blocking this brainstorm.

## What You're Deciding

**PASS or NO PASS.** Same gate as before. Is this brainstorm ready to become a plan?

## Specific Checks

### Check 1: P0 Resolution Verification

Read `docs/reports/spike-nested-worktree-delegation.md`. Verify:
- The report exists and is complete (test results, architecture recommendation, constraints).
- The brainstorm's Pre-Plan Spike section accurately reflects the report's verdict.
- The swarm-runner scope (Steps 11w-16w) is consistent throughout the brainstorm.

### Check 2: Two-Tier Summary Contract Consistency

The original 500-char contradiction is replaced by a two-tier design:
- Tier 1 decision line (< 200 chars) returned inline to orchestrator
- Tier 2 detail fields written to BUILD_TRACKING.md frontmatter

Verify:
- Hard Success Gate 5 references the 200-char Tier 1 limit, not the old 500-char limit.
- Stage 1b success criterion matches the two-tier design.
- The BUILD_TRACKING schema includes fields that Tier 2 writes to.
- Layer 1b description references the two-tier contract correctly.

### Check 3: Cross-Section Consistency (Repeat)

Re-check the pairs from your first review, now with R3 content:
- Pre-Plan Spike outcomes vs. Stage 3 scope: both should say 11w-16w.
- Solo-Build Strategy vs. Regression Gates: no-duplication invariant should hold.
- Hard Success Gates vs. Staged Roadmap success criteria: metrics and thresholds should match.
- What Must Not Change vs. frontmatter approach: should be consistent.

### Check 4: Remaining Ambiguity

Is there any section where the brainstorm says "the plan phase must decide" without providing enough constraints? The solo-build strategy and maintenance drift sections previously deferred decisions -- verify they now contain firm decisions.

## Constraints

- Do not propose new candidates or alternative architectures.
- The spike result (REDUCED DELEGATION) is final. Do not suggest re-testing.
- If you find a P0, the brainstorm gets one more revision. If only P1/P2, those become plan-phase inputs.

## Output Format

```
## Verdict: PASS | NO PASS

## P0 Findings (blocks planning)
- [finding, or "None"]

## P1 Findings (plan phase must address)
- [finding, or "None"]

## P2 Findings (notes for plan phase)
- [finding, or "None"]

## Cross-Section Contradiction Report
[For each pair in Check 3: "CONSISTENT" or "CONTRADICTION: <explanation>"]

## Single Most Likely Failure Mode
[One sentence]
```
