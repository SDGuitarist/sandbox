# Codex Final Review Resubmission: Autopilot Context Death Solution (R3 -> R4)

## Start Here

Read only:
1. `docs/brainstorms/2026-06-03-autopilot-context-death-solution-brainstorm.md` -- **the brainstorm (status: brainstorm-revised-r3)**
2. `docs/reports/spike-nested-worktree-delegation.md` -- the completed spike report

You have already read CLAUDE.md, SKILL.md, and tail-runner.md in prior reviews. Do not re-read unless a specific check requires it.

## Why This Is a Second Resubmission

You returned NO PASS on R3 with one P0:

> Stale full-delegation wording in Candidate 3, Layer 2, SKILL.md changes,
> and drift-control text contradicts the completed REDUCED DELEGATION spike.

All four stale locations have been fixed. Three P1s have also been addressed.

## Exact Fixes Applied (R3 -> R4)

### P0: Stale Full-Delegation Wording (4 locations)

| Location | Was | Now |
|----------|-----|-----|
| Candidate 3 line ~207 (swarm-runner description) | "runs swarm planner, spawns workers" | "Reads the assembly branch after worker spawn completes... Scope reduced to Steps 11w-16w." |
| Layer 2 line ~459 (intro paragraph) | "untested assumption... must be validated by a spike" | "pre-plan spike confirmed sub-agents lack the Agent tool... swarm-runner owns only Steps 11w-16w" |
| Layer 2 line ~486 (SKILL.md changes) | "Steps 10w-16w become: spawn swarm-runner" | "Steps 11w-16w become: spawn swarm-runner" + "Steps 7w-10.5w remain inline" |
| Drift-control line ~519 | "worker spawn... moves to agent files" | "assembly merge, contract checks... has no solo equivalent. Worker spawn and swarm planner remain in the orchestrator." |

### P1: BUILD_TRACKING Schema Missing Tier 2 Fields

The `swarm:` and `tail:` sections in the schema example now explicitly include all Tier 2 fields using the same keys as the summary contract: `counts`, `merge_status`, `preserved_branches`, `cleanup_status`, `failure_report_path`, `artifact_paths`. Comments mark them as "Tier 2 fields (written by swarm-runner/tail-runner before returning)."

### P1: 30% Target Too Aggressive for Reduced Scope

Updated in three places:
- **Measurement plan:** "Stages 2+3 combined must stay below 60% (fallback), 30% stretch target."
- **Hard Success Gate 2:** "Target: under 30%. Fallback: under 60% (accounts for reduced swarm-runner scope)."
- **Stage 3 success criterion:** "If the metric improves materially but does not hit 30%, the stage still ships. Plan must define fallback threshold (e.g., under 60%)."
- **Layer 2 estimated context:** Now explicitly notes worker spawn remains inline and explains why 30% is a stretch target.

### P1: No-Duplication Invariant Too Literal

Changed from "no step exists in both an agent file AND SKILL.md inline" to "no same-path implementation logic exists in both places." Explains that Step 6 can appear in both (solo = skill invocation, swarm = agent with sub-agents) because the implementations are architecturally different, not duplicated.

## What You're Deciding

**PASS or NO PASS.** Is the P0 resolved? Are there any remaining cross-section contradictions involving the REDUCED DELEGATION decision?

## Focused Checks

### Check 1: Full-Delegation Wording Eliminated

Search the brainstorm for any remaining references to swarm-runner owning worker spawn, Steps 7w-10.5w, or "untested" nested delegation. There should be zero. The only acceptable mentions of full delegation are in the historical spike tests reference section and the "Originally proposed" parenthetical.

### Check 2: Tier 2 Field Name Alignment

Verify that the Tier 2 fields in the bounded summary contract (Candidate 2) use the same keys as the BUILD_TRACKING schema's `swarm:` and `tail:` sub-sections. Mismatched keys between contract and schema would cause agents to write fields the orchestrator can't find.

### Check 3: 30% / 60% Consistency

Verify that all three places referencing the context reduction target (measurement plan, Hard Success Gate 2, Stage 3 criterion) agree on 30% stretch / 60% fallback. No remaining references to a hard 30% requirement.

### Check 4: No-Duplication Invariant Consistency

Verify the invariant wording in the drift-control section matches the regression gate wording. Both should say "same-path implementation logic," not "step exists in both."

## Constraints

- Do not propose new candidates or re-test the spike.
- If you find another P0, the brainstorm gets one final revision.
- P1/P2 findings become plan-phase inputs.

## Output Format

```
## Verdict: PASS | NO PASS

## P0 Findings
- [finding, or "None"]

## P1 Findings
- [finding, or "None"]

## P2 Findings
- [finding, or "None"]

## Single Most Likely Failure Mode
[One sentence]
```
