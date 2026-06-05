---
title: "Review: Autopilot Context-Death Solution"
date: 2026-06-05
branch: master
commits_reviewed: 40d6e64..f091760 (6 work commits) + c8aff8f, bbcab41 (2 fix commits)
plan: docs/plans/2026-06-03-autopilot-context-death-solution-plan.md
reviewers:
  - codex (round 1)
  - claude-code-explore (round 2)
---

# Review Summary: Autopilot Context-Death Solution

## Scope

Meta-build modifying autopilot infrastructure (SKILL.md + 2 new agent files).
Three stages: (1) no-read discipline + output contracts, (2) deepening merge
delegation (swarm-only), (3) swarm-runner agent (Steps 11w-16w).

Files reviewed:
- `.claude/skills/autopilot/SKILL.md` (Steps 5.5, 6-6.08, 9w.5-9w.7, 10w-17w)
- `.claude/agents/swarm-runner.md`
- `.claude/agents/deepen-merge-runner.md`
- `.claude/agents/spec-completeness-checker.md`
- `.claude/agents/spec-consistency-checker.md`

## Findings

### Codex (Round 1): 2 P1, 0 P2, 0 P3

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 1 | P1 | worker_status never serialized — Step 10w doesn't define how to build the `{ role, branch, status }` list before swarm-runner consumes it | Added explicit serialization step with COMPLETED/TIMED_OUT/FAILED mapping (commit c8aff8f) |
| 2 | P1 | 20+ agent claim not proven — deepening + worker spawn remain inline (require Agent tool), so context savings are limited to post-spawn tail | Added context budget note acknowledging limitation; first 20+ build must be monitored (commit c8aff8f) |

### Claude Code (Round 2): 0 P1, 3 P2, 2 P3

| # | Severity | Finding | Fix |
|---|----------|---------|-----|
| 3 | P2 | STATUS normalization ambiguous ("start and end" vs iterative) | Clarified as iterative stripping from both ends (commit bbcab41) |
| 4 | P2 | tail-runner has no auto-checkpoint — 20+ agent review could exhaust context | Documented at context budget note as intentional design + manual recovery path (commit bbcab41) |
| 5 | P2 | Step 10.5w doesn't state Step 7w PASS as prerequisite | Added explicit prerequisite (commit bbcab41) |
| 6 | P3 | Assembly summary template shows `<PASS>` placeholder | No fix — template clarity, correct at runtime |
| 7 | P3 | deepen-merge-runner "best effort" language ambiguous | No fix — behavior is clear in Steps 1-2 |

## Critical Invariant Checks

| Check | Result |
|-------|--------|
| contract-check FAIL aborts pipeline | PASS |
| merge-conflict FAIL aborts pipeline | PASS |
| smoke/test FAIL continues (non-blocking) | PASS |
| No-Duplication Invariant (solo vs swarm paths) | PASS |
| Step 6.1 references eliminated | PASS |
| swarm-runner never spawns assembly-fix | PASS |
| Superseded agents not referenced | PASS |
| Output contracts in checker agents | PASS |
| worker_status serialization defined | PASS |

## Verdict on 20+ Agent Context Sufficiency

**Not proven sufficient by design alone.** The delegation saves the post-spawn
tail (assembly, verification, merge, cleanup) from the orchestrator's context.
But deepening (Step 6) and worker spawn (Steps 7w-10.5w) remain inline because
they require the Agent tool. The first 20+ agent build must be monitored to
confirm the orchestrator stays under budget.

Additionally, the tail-runner has no auto-checkpoint mechanism (intentional).
If a 20+ agent review phase exhausts tail-runner context, recovery is manual.

## What This Review Did NOT Cover

- Runtime behavior (no build was executed)
- Whether the 30-minute tail-runner timeout is sufficient for 20+ agents
- Whether BUILD_TRACKING.md Edit tool writes remain stable under heavy concurrent edits
- Accuracy of context_proxy_chars metric (observability-only, rough manual tally)

## Feed-Forward

- **Hardest decision:** Whether P1-2 (20+ agent claim) is a code fix or a documentation fix. Chose documentation — the design limitation is architectural (Agent tool requirement), not fixable without a fundamentally different approach.
- **Rejected alternatives:** Refactoring deepening to run in a sub-agent (impossible — needs Agent tool for research sub-agents). Moving worker spawn to swarm-runner (impossible — needs Agent tool for worktree spawning).
- **Least confident:** Whether the tail-runner can complete review + compound + learnings for a 20+ agent build within its fresh context window. The 30-minute timeout and lack of auto-checkpoint make this the riskiest gap. First real build will calibrate.
