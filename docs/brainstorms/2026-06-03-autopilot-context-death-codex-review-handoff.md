# Codex Review: Autopilot Context Death Solution Brainstorm

## Start Here

Read these files in order:
1. `CLAUDE.md` -- operating contract (autonomy classes, required artifacts, bash rules)
2. `HANDOFF.md` -- current project state
3. `.claude/skills/autopilot/SKILL.md` -- the autopilot skill being redesigned (835 lines)
4. `.claude/agents/tail-runner.md` -- existing delegation pattern that works
5. `docs/brainstorms/2026-06-03-autopilot-context-death-solution-brainstorm.md` -- **the brainstorm under review**

For additional context on prior thinking (read only if needed to answer a specific question):
- `docs/brainstorms/2026-05-20-autopilot-context-optimization-brainstorm.md` -- Tier 1 checkpoint design (implemented)
- `docs/brainstorms/2026-06-01-tail-delegation-brainstorm.md` -- tail-runner design (implemented)
- `docs/brainstorms/codex-handoff-context-death-solution.md` -- your prior review that informed this brainstorm
- `docs/solutions/2026-06-02-prompting-dashboard-engine-run-064.md` -- most recent build (context death near-miss)

## What You're Reviewing

A brainstorm document proposing a layered solution to autopilot context death:
- **Layer 1a:** No-read orchestrator discipline (SKILL.md-only changes)
- **Layer 1b:** Bounded agent summary contracts (agent file edits)
- **Layer 2:** Hybrid delegation (new deepen-runner + swarm-runner agents, keeping existing tail-runner)

The brainstorm was refined once already to address: Layer 1 contradiction split, nested delegation spike requirement, measurable targets, maintenance drift, BUILD_TRACKING.md as single state file, deterministic STATUS extraction, and hard regression gates.

## Review For Plan Readiness

This is a brainstorm-to-plan gate review. The question is: **is this brainstorm ready to become a plan, or does it have gaps that will cause problems during planning or implementation?**

### 1. Architecture Gaps

- Does the 3-agent delegation model (deepen-runner, swarm-runner, tail-runner) have any failure modes not addressed in the Risks section?
- Is the BUILD_TRACKING.md YAML frontmatter approach sound, or does it create parsing fragility (e.g., agents writing malformed YAML that breaks subsequent reads)?
- The brainstorm says "single source of truth" is the recommended maintenance drift mitigation. Does this hold up? What happens to solo builds if the inline SKILL.md steps are removed?

### 2. Spike Design Adequacy

- Stage 0 tests nested worktree delegation. Is the spike design sufficient to determine swarm-runner scope? Are there edge cases the spike should test that it doesn't (e.g., nested agent timeout, nested agent crash recovery, worktree cleanup on failure)?
- The spike has 3 possible outcomes. Are the architecture impacts for each outcome correctly mapped?

### 3. Measurement Plan Validity

- The brainstorm defines a proxy metric: cumulative character count of Read/Agent tool outputs * 0.25. Is this a valid proxy for actual context consumption? What does it miss (e.g., system prompts, skill loading, tool definitions)?
- Success thresholds are defined relative to a baseline run. Is "below 30% of baseline" the right target, or is it too aggressive / too conservative?

### 4. Contract Completeness

- The bounded summary contract specifies STATUS, report_path, counts, next_action. Is anything missing that the orchestrator needs to make decisions (e.g., error details on partial success, retry eligibility)?
- The BUILD_TRACKING.md frontmatter schema has fields for each phase. Is the schema complete for all phases, or are there phases whose state needs more fields?

### 5. Cross-Section Contradictions

Check for internal contradictions across sections. Known P0 pattern: each section looks correct in isolation but is incompatible with another section. Specifically check:
- Does the "What Must Not Change" section conflict with any proposed change?
- Does the "Staged Roadmap" ordering match the dependency graph in the Risks section?
- Do the "Hard Success Gates" reference the same metrics and thresholds as the "Staged Roadmap" success criteria?
- Does the maintenance drift section's "single source of truth" recommendation conflict with the "solo build parity" regression gate?

### 6. Feed-Forward Quality

- Does the Feed-Forward section accurately capture the hardest decision, rejected alternatives, and least confident items?
- Is the "least confident" item (nested worktree delegation) adequately addressed by Stage 0, or does the plan need additional fallback design before starting?

### 7. Readiness Verdict

After reviewing all sections, answer:
1. Is this brainstorm ready for planning? (YES / NO / YES WITH CONDITIONS)
2. If NO or YES WITH CONDITIONS: what specific gaps must be filled before planning starts?
3. Are there any assumptions that should be tested by the Stage 0 spike that aren't currently included?
4. What is the single most likely way the plan derived from this brainstorm will fail?

## Constraints For Your Review

- The solution must remain fully unattended. No manual pause, no human checkpoint, no `/tail-resume` as the primary solution.
- The solution must be incremental (stages, not all-or-nothing).
- The 6-phase compound engineering loop must be preserved.
- Do not propose replacing the entire autopilot system unless you find a fundamental flaw in the delegation approach.

## Output Format

```
## Findings

### P0 (blocks planning)
- [finding]

### P1 (should fix before planning)
- [finding]

### P2 (note for plan phase)
- [finding]

## Readiness Verdict
[YES / NO / YES WITH CONDITIONS]

## Conditions (if applicable)
- [condition 1]
- [condition 2]

## Updated Claude Code Handoff Prompt (if changes needed)
[prompt for Claude Code to apply fixes before planning]
```
