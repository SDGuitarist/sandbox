# Codex Final Review: Autopilot Context Death Solution Brainstorm (R2)

## Start Here

Read these files in order:
1. `CLAUDE.md` -- operating contract
2. `.claude/skills/autopilot/SKILL.md` -- the autopilot skill being redesigned
3. `.claude/agents/tail-runner.md` -- existing delegation pattern
4. `docs/brainstorms/2026-06-03-autopilot-context-death-solution-brainstorm.md` -- **the brainstorm (status: brainstorm-revised-r2)**

Only read if needed for a specific question:
- `docs/brainstorms/codex-handoff-context-death-solution.md` -- your first review
- `docs/brainstorms/2026-06-03-autopilot-context-death-codex-review-handoff.md` -- your second review prompt (the findings from which drove R2)

## What Changed Since Your Last Review

You reviewed R1 and returned findings. Claude Code applied 8 fixes to produce R2:

1. **Stage 0 contradiction resolved.** The nested worktree spike is now a "Pre-Plan Spike" section, not a roadmap stage. The plan phase is blocked until the spike report exists. No conflicting statements remain.
2. **Branch-only workers removed.** The "works without worktree" outcome is gone. Only two viable architectures: full worktree delegation or orchestrator-managed spawning. Explicit rejection statement added.
3. **STATUS extraction fixed.** Phase reports MUST NOT have YAML frontmatter. STATUS on line 1, always. `limit: 1` (not `limit: 3`). Only BUILD_TRACKING.md has frontmatter.
4. **Solo-build strategy decided.** Solo remains inline. Swarm agent files are the single source of truth for swarm logic. No duplication invariant: no step may exist in both an agent file AND SKILL.md inline.
5. **BUILD_TRACKING frontmatter validation added.** Mandatory validation after every update. Verify `---` delimiters and required fields. On failure: full-file rewrite. On double failure: hard abort.
6. **Bounded summary contract expanded.** Added: `blocking`, `retry_eligible`, `failure_report_path`, `merge_status`, `preserved_branches`, `cleanup_status`, `next_step` (exact step ID). Field definitions included.
7. **BUILD_TRACKING schema expanded.** Added: `context_proxy_chars`, `manual_resume`, `final_status`, `brainstorm_path`, per-phase `summary_path`, all per-phase report paths. Field definitions included.
8. **Pre-plan spike expanded.** Now 7 tests: basic spawn, parallel spawn (3 children), child crash, child timeout, cleanup on failure, bypassPermissions propagation, bounded parent return. Four outcome rows with architecture impacts.

## What You're Deciding

**PASS or NO PASS.** Is this brainstorm ready to become a plan?

This is a final gate, not an exploration. Do not propose new candidates or alternative architectures. The question is narrow: given the brainstorm as written, are there remaining gaps that would cause the plan to be wrong, incomplete, or internally contradictory?

## Specific Checks (All Required)

### Check 1: Cross-Section Consistency

Verify these pairs are not contradictory:
- "Pre-Plan Spike" outcomes table vs. "Staged Roadmap" Stage 3 scope description
- "Solo-Build Strategy" no-duplication invariant vs. "Regression Gates" solo build parity
- "Bounded Summary Contract" field set vs. "BUILD_TRACKING Schema" per-phase fields (do the agent summaries contain the fields that BUILD_TRACKING needs?)
- "Hard Success Gates" bounded summary compliance (< 500 chars) vs. the expanded summary contract (which now has 11 fields -- does it still fit in 500 chars?)
- "What Must Not Change" item 8 (incremental BUILD_TRACKING) vs. the YAML frontmatter approach (does frontmatter introduce a new write pattern that conflicts with the existing Edit-based row insertion?)

### Check 2: Pre-Plan Spike Completeness

The spike now has 7 tests. Are there any remaining gaps that would leave the plan guessing about swarm-runner scope? Specifically:
- Does test 2 (3 parallel children) cover the actual swarm scale (10-31 agents)?
- Is test 4 (timeout) testable without actually waiting 10 minutes?
- Does test 6 (bypassPermissions) verify that the child can run git operations, Write tool, and Edit tool without prompts?

### Check 3: Schema Overengineering

The BUILD_TRACKING frontmatter schema now has ~30 fields. Is this schema too large for agents to maintain reliably via Edit tool? Would a simpler schema (fewer fields, more in the markdown body) be more robust?

### Check 4: Measurement Plan Viability

The proxy metric (cumulative character count of Read/Agent outputs * 0.25) is used for success thresholds. Does this proxy actually measure what matters (orchestrator context consumption), or does it miss significant sources (system prompts, tool schemas, compaction residue)?

### Check 5: Remaining Ambiguity

Is there any section where the brainstorm says "the plan phase must decide" without providing enough constraints for the plan to make a good decision? List any such sections.

## Constraints

- The solution must remain fully unattended.
- The solution must be incremental.
- The 6-phase compound engineering loop must be preserved.
- Do not propose new candidates. Only evaluate what exists.
- If you find a P0, the brainstorm gets one more revision. If you find only P1/P2, those become plan-phase inputs.

## Output Format

```
## Verdict: PASS | NO PASS

## P0 Findings (blocks planning -- NO PASS if any exist)
- [finding, or "None"]

## P1 Findings (plan phase must address)
- [finding]

## P2 Findings (notes for plan phase)
- [finding]

## Cross-Section Contradiction Report
[For each pair in Check 1: "CONSISTENT" or "CONTRADICTION: <explanation>"]

## Single Most Likely Failure Mode
[One sentence: what is the most likely way the plan derived from this brainstorm will fail?]
```
