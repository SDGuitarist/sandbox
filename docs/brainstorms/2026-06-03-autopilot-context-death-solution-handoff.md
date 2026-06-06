# Claude Code Handoff: Autopilot Context Death Solution Brainstorm

## Start Here

Read `CLAUDE.md`, `HANDOFF.md`, `docs/brainstorms/codex-handoff-context-death-solution.md`, `.claude/skills/autopilot/SKILL.md`, and `.claude/agents/tail-runner.md` first. Then start the brainstorm phase for a solution to the autopilot context death problem.

## Task

Create a brainstorm document for improving the sandbox autopilot system so complex swarm builds can complete fully unattended without context death.

This is a design/architecture brainstorm, not implementation. Do not edit the autopilot skill yet. Do not start plan or work phases until the brainstorm is complete and reviewed.

## Problem

The current autopilot runs the compound engineering pipeline in one Claude Code session:

brainstorm -> plan -> deepen -> pre-swarm gates -> swarm -> assembly -> smoke/test -> review -> compound -> learnings -> self-audit.

On complex swarm builds with roughly 12-31 agents, the top-level orchestrator accumulates too much context before the run completes. Tail delegation already helps by moving review through self-audit into a fresh `tail-runner` agent, but Run 064 still showed that deepening, pre-swarm gate loops, swarm coordination, and assembly rewrites can consume large amounts of orchestrator context before tail begins.

The key architectural insight: most phase state is already written to disk. The orchestrator usually needs only phase status, artifact paths, counts, and next action. It does not need to carry full deepening reports, full gate reports, worker outputs, or detailed merge logs in conversation history.

## Non-Negotiable Requirements

- Autopilot must remain fully unattended. No mid-run human review pause.
- Context rollover, if needed, must be automatic, not `PAUSED_FOR_CONTEXT` requiring manual `/tail-resume`.
- Existing required artifacts must still be produced: `BUILD_TRACKING.md`, solution doc, learnings propagation, `HANDOFF.md`, self-audit report.
- The 6-phase compound engineering loop must be preserved.
- Solution must work locally for Flask + SQLite apps and local smoke tests.
- Existing swarm worktree isolation must continue to work.
- The solution should be incremental. Prefer changes that can ship in stages.
- Do not replace the whole autopilot system unless the brainstorm makes an exceptionally strong case.

## Recommended Direction To Explore First

Codex recommended a layered approach:

1. **No-Read Orchestrator Discipline**
   - The top-level orchestrator reads only `STATUS`, artifact paths, counts, failure summaries, and next-step fields.
   - Full reports stay on disk.
   - The orchestrator reads full reports only when a phase returns `STATUS: FAIL` or when a gate explicitly requires detailed recovery.

2. **Bounded Phase Summaries**
   - Heavy phases write full reports to disk but return a strict small summary, ideally 1-2K tokens:
     - `STATUS`
     - artifact paths
     - key counts/metrics
     - blocking failures, if any
     - exact next action
   - This applies to deepening, pre-swarm gates, swarm/assembly, smoke/test, and tail.

3. **Hybrid Delegation**
   - Add fresh-context delegated agents for the heavy phases that still run inline today:
     - `deepen-runner`
     - `swarm-runner` or `assembly-runner`
   - Keep existing `tail-runner`.
   - Each delegated agent must operate from disk artifacts and return a bounded summary only.

4. **Automatic Context Budget Gate**
   - Before major phase boundaries, estimate remaining context load from agent count, gate retries, report count, and fix retries.
   - If over threshold, automatically launch or delegate the next phase from `PHASE_STATE.json`.
   - Do not pause for human resume.

The core reframing is: do not ask "how do we survive context death?" Ask "how do we prevent the orchestrator from reading context it does not need?"

## Candidates To Include In Brainstorm

Include and compare at least these candidates:

1. No-read orchestrator discipline
2. Bounded phase summaries
3. Hybrid delegation: `deepen-runner`, `swarm-runner`, existing `tail-runner`
4. Automatic context budget gate
5. Contract-first `PHASE_STATE.json` or upgraded `BUILD_TRACKING.md`
6. Two-run autopilot split: planning/deepening/gates in Run A, swarm/tail in Run B
7. External Agent SDK orchestrator
8. Anthropic-style shell harness loop
9. Stop hook + delegated phase agents + `/goal`
10. Full phase delegation
11. Native compaction or `/goal`-only resilience

For each candidate, evaluate:

- Reliability: does it structurally eliminate context death or only reduce risk?
- Simplicity: how much new code/infrastructure?
- Maintainability: how many moving pieces must stay synchronized?
- Future-proofing: how well does it adapt to model/context/tool changes?
- Incremental adoptability: can it ship in stages?
- Unattended operation: can it complete without human review or manual resume?

## Known Failure Modes To Address

- Orchestrator reads full deepening outputs even though only merged plan and summary are needed.
- Pre-swarm gates may produce multiple FAIL/fix/retry loops and large reports.
- Gate reports can be argued away or overridden; this must be explicit and machine-visible.
- Ownership gate checks file paths, not spec conformance.
- Assembly rewrites can be large and under-recorded in `BUILD_TRACKING.md`.
- Tail delegation works, but it starts late; context may already be exhausted before Step 17w.
- Manual checkpoint recovery is not acceptable as the primary unattended solution.
- Multiple authorities can conflict: stop hook, `/goal`, `BUILD_TRACKING`, `PHASE_STATE.json`, agent status output.

## Preferred Brainstorm Shape

Use the standard brainstorm format for this repo. The output should include:

- Problem summary
- Current system constraints
- Candidate list with tradeoffs
- Recommended MVP solution
- Staged roadmap
- Risks and mitigations
- What must not change
- How we will know it worked
- `## Feed-Forward` section with:
  1. What was the hardest decision?
  2. What alternatives were rejected, and why?
  3. What are you least confident about?

## Suggested MVP Hypothesis

The likely MVP is not a full external orchestrator. The likely MVP is:

1. Add a strict phase-summary return contract.
2. Modify the autopilot instructions so the orchestrator never reads full phase reports on PASS.
3. Add a `PHASE_STATE.json` file that records current phase, required artifacts, status, and next action.
4. Delegate deepening and swarm/assembly into fresh-context agents.
5. Keep tail delegation as-is, but make the transition to tail depend on `PHASE_STATE.json` and bounded summaries.

This should preserve unattended autopilot while eliminating most avoidable context growth.

## Acceptance Criteria For The Brainstorm

- It clearly distinguishes context reduction from context elimination.
- It does not rely on human review, manual checkpoint resume, or interactive prompts.
- It names the minimal viable change that could reduce context pressure by 70-90%.
- It identifies what needs to be machine-readable versus human-readable.
- It recommends a staged path that can be implemented without rewriting the entire autopilot system.
- It explains why any external orchestrator option is or is not worth the migration cost.

## Prompt To Use

```
Read docs/brainstorms/2026-06-03-autopilot-context-death-solution-handoff.md first, then start the brainstorm phase for the autopilot context death solution.

Create a brainstorm document only. Do not implement code. Do not edit .claude/skills/autopilot/SKILL.md yet.

The solution must preserve fully unattended autopilot. Context rollover must be automatic, not a human pause. Focus first on no-read orchestrator discipline, bounded phase summaries, hybrid delegation, and automatic context budget gates. Compare these against external orchestrator and hook-based alternatives.
```
