---
title: "Tail Delegation for Context-Resilient Swarm Orchestration"
date: 2026-06-01
category: architecture
severity: P0
problem_type: resource-exhaustion/context-death
tags:
  - context-management
  - swarm-orchestration
  - tail-delegation
  - autopilot
  - agent-spawning
  - context-death
  - build-reliability
components:
  - .claude/agents/tail-runner.md
  - .claude/skills/autopilot/SKILL.md
  - docs/reports/061/skill-invocation-spike.md
root_cause: >
  Orchestrator context window saturated (~98%) by accumulating 10 agent
  spawn prompts, 10 result payloads, pre-swarm gate outputs, assembly
  merges, and cleanup logs — leaving insufficient context for the
  Shared Tail (review, compound, learnings, self-audit).
resolution: >
  Introduced tail delegation: after Step 16w, the orchestrator spawns a
  fresh tail-runner agent that executes the entire Shared Tail in its own
  context window. Also replaced all echo >> BUILD_TRACKING.md patterns
  with Edit tool instructions to prevent misplaced rows.
review_findings:
  p1_count: 2
  p2_count: 5
  all_fixed: true
related_runs:
  - "061"
failure_class: context-exhaustion
recurrence_risk: low
---

# Tail Delegation for Context-Resilient Swarm Orchestration

## Problem

Run 061 (Prompting Dashboard Engine, 10-agent swarm) completed the entire
build phase successfully — all 10 agents merged, contract check fixed,
smoke tests 13/13 PASS — then stopped before the review tail started.
The orchestrator wrote a CHECKPOINT.md at `next_step: "Shared Tail: Review"`
and exited, leaving 9 of 9 tail steps unfinished.

The orchestrator's context window scales with the number of agents spawned,
not the work each agent does. Run 061 accumulated context from:

| Source | Context cost | Count |
|--------|-------------|-------|
| Agent spawn prompts | Full spec + pitfalls + rules per agent | 10 |
| Agent completion results | Result payload per agent | 10 |
| Pre-swarm gate agents | Consistency + completeness checkers | 2 |
| Verification agents | Contract check, smoke test, assembly fix | 3 |
| Ownership gate diffs | git diff per branch | 10 |
| Assembly merges | Merge output per branch | 10 |
| BUILD_TRACKING writes | Incremental appends + gate results | ~14 |
| Cleanup | Worktree removes + branch deletes | ~21 |

Total at Step 16w: ~98% context. Remaining for 9 tail steps: ~2%.

The existing Tier 1 checkpoint was positioned post-compound (too late).
The "Tier 2 pre-review resume" was identified in the 2026-05-20 solution
doc as future work but never implemented. Run 061 is the first real-world
occurrence of the scenario it was meant to prevent.

## Root Cause

The orchestrator's context accumulation is structural, not tunable. Agent
prompts, deepening sub-agents, pre-swarm gates, and BUILD_TRACKING writes
all compound before the tail starts. The heuristic (`load = swarm_agents +
2x deepening + 1.5x review + 3x retries`) missed run 061 because it
doesn't account for pre-swarm work density (15 P1/P2 deepening fixes,
2 consistency rounds, 6 spec surfaces, 2 document-review passes).

Secondary issue: all 5 `echo >> BUILD_TRACKING.md` patterns appended to
the file end instead of inserting into the AGENT_STATUS table, causing
misplaced rows after the Template Version section.

## Solution

Delegate the entire Shared Tail to a fresh-context agent instead of
executing it inline within the orchestrator.

### Verify-First Spike

Before building anything, spawned a minimal test agent to confirm the
Skill tool works from inside a spawned agent. Tested `/workflows:review`,
`/workflows:compound`, and `/update-learnings-noninteractive`. Result:
ALL_PASS. This removed the main technical risk (the plan's Feed-Forward
"least confident" item) before any design work began.

### New Agent: tail-runner.md

A 10-step agent definition that receives run metadata and executes the
full Shared Tail:

1. Review (`/workflows:review`)
2. Resolve TODOs (`/compound-engineering:resolve_todo_parallel`)
3. Compound (`/workflows:compound`)
4. Update learnings (`/update-learnings-noninteractive`)
5. Verify learnings artifacts (4 checks)
6. Fill BUILD_TRACKING FAILURES and RUN_METRICS
7. Verify BUILD_TRACKING completeness
8. Self-audit (spawns self-audit-reviewer agent)
9. Verify self-audit (`/verify-self-audit`)
10. Update HANDOFF.md

The agent includes an Inputs table, Internal Variables section, Bash
Command Rules, and an Output Contract requiring `solution_doc_path` and
a parseable `STATUS: PASS/FAIL` line.

### Autopilot SKILL.md Changes

- **Change A:** All 5 `echo >> BUILD_TRACKING.md` patterns replaced with
  Edit tool instructions targeting the AGENT_STATUS table separator
- **Change B:** Step 17w spawns tail-runner with run metadata, includes
  branch precondition check
- **Change C:** Step 18w parses STATUS line from tail-runner output
  (collapsed from 43 to 8 lines during review — trust agent STATUS like
  all other pipeline agents)
- **Change D:** Shared Tail heading updated to "SOLO ONLY" with
  delegation note for swarm builds
- **Change E:** Context-Budget Checkpoint marked SOLO ONLY

### Review Fixes (2 P1, 5 P2)

| ID | Severity | Fix |
|----|----------|-----|
| P1-1 | Critical | Added `Agent` tool to tail-runner frontmatter (needed to spawn self-audit-reviewer) |
| P1-2 | Critical | Removed dead "SWARM ONLY" section from inside solo-only Shared Tail |
| P2-1 | Important | Collapsed Step 18w from 43 to 8 lines (trust agent STATUS) |
| P2-2 | Important | Added Bash Command Rules to tail-runner.md |
| P2-3 | Important | Removed unused `swarm_results` parameter |
| P2-4 | Important | Added TAIL_SYNC_POINT markers for drift prevention |
| P2-5 | Important | Added Glob fallback for solution_doc_path discovery |

## Key Design Decisions

**Delegation over checkpointing.** Checkpointing requires state
serialization/deserialization and introduces resume-path complexity.
Delegation preserves uninterrupted execution — the tail-runner starts
fresh and runs straight through.

**Agent invokes skills directly.** The spike proved spawned agents can
call compound engineering skills via the Skill tool. This means the
tail-runner reuses existing skill definitions rather than duplicating
their logic inline.

**Trust agent STATUS line.** The orchestrator treats the tail-runner
identically to every other pipeline agent (spec-completeness-checker,
smoke-test-runner, self-audit-reviewer): parse STATUS, pass on PASS,
fail on FAIL. No re-verification.

**No checkpoint inside tail-runner.** Explicit choice. The tail sequence
is bounded (10 steps with known context cost). Adding a checkpoint would
re-introduce the complexity this solution eliminates.

**Solo path unchanged.** Solo builds don't spawn enough agents to exhaust
context. The Tier 1 checkpoint and inline Shared Tail stay active.

## What Changed

| File | Change |
|------|--------|
| `.claude/agents/tail-runner.md` | NEW — 10-step agent with Inputs, Internal Variables, Bash Rules, Output Contract |
| `.claude/skills/autopilot/SKILL.md` | Steps 17w-18w added, 5x echo >> replaced with Edit tool, Shared Tail marked SOLO ONLY, checkpoint guarded |

## Risk Resolution

**Brainstorm/Plan Feed-Forward risk:** "Whether /workflows:review and
/workflows:compound work when invoked from inside a spawned agent."

**What actually happened:** The verify-first spike (commit `2e5e988`)
confirmed ALL_PASS before any implementation began. All three skills
loaded their full instruction sets and were invocable from the nested
context. The fallback architecture (orchestrator runs skills, tail-runner
handles artifacts only) was never needed.

**What was learned:** The Skill tool has no depth restriction — spawned
agents can invoke skills that themselves spawn sub-agents. This validates
the delegation pattern for any future phase-boundary delegation.

## Prevention

### What this fixes

Tail delegation eliminates orchestrator context exhaustion during the
Shared Tail by making it structurally independent of the build phase.
Even at 95% context after a 20-agent swarm, the orchestrator only needs
enough headroom for one agent spawn call. The tail-runner starts at zero.

### Remaining risks NOT solved

1. **Pre-Step 16w context death** — if the orchestrator dies during the
   build itself, there is no tail to delegate. A separate "build
   continuation" agent would be needed.
2. **Tail-runner context limits** — 10 steps including multi-agent review
   and compound. No mid-tail checkpoint. If context fills, run fails.
3. **Dual maintenance drift** — tail-runner.md and SKILL.md Shared Tail
   contain the same logic. TAIL_SYNC_POINT markers added but no
   automated enforcement.

### Monitoring (next 3-5 swarm runs)

- Track tail-runner context consumption at completion (flag if >60%)
- Diff tail-runner.md against SKILL.md Shared Tail after edits to either
- Verify handoff payload accuracy (compare tail-runner input vs BUILD_TRACKING)
- Measure orchestrator context at delegation point (flag if >90%)
- Watch self-audit quality for degradation signals

### Extension patterns

The delegation pattern applies to any phase boundary where prior context
is needed only as a summary, not as full history. Candidates:
- Build-phase checkpointing (spawn continuation agent mid-build)
- Review decomposition (separate review-runner from compound-runner)
- Single-source tail definition (extract shared steps to one file)

## Related Documentation

### Direct predecessors
- [autopilot-context-window-optimization](2026-05-20-autopilot-context-window-optimization.md) — Tier 1 checkpoint + heuristic. "Tier 2 pre-review resume" listed as future work; this solution implements a stronger alternative.
- [sandbox-autonomy-hardening](2026-05-13-sandbox-autonomy-hardening.md) — BUILD_TRACKING gates, self-audit layer, artifact verification pattern.
- [autopilot-swarm-orchestration](2026-04-09-autopilot-swarm-orchestration.md) — Foundational solo/swarm branching, worktree isolation, assembly pipeline.

### Contributing context
- [compound-bash-instruction-refactor](2026-04-09-compound-bash-instruction-refactor.md) — One-command-per-call rule (FC8). The echo >> fix extends this principle.
- [autopilot-skips-non-step-instructions](2026-05-06-autopilot-skips-non-step-instructions.md) — Mandatory actions must be numbered steps.
- [spec-completeness-checker](2026-05-21-spec-completeness-checker-pre-swarm-gate.md) — Pre-swarm gate agent whose output consumes orchestrator context.
- [spec-convergence-loop](2026-04-30-spec-convergence-loop.md) — Multi-round spec validation that generates deepening corrections.

### Run 061 artifacts
- [context-death-analysis](../reports/061/context-death-analysis.md) — Root cause analysis
- [skill-invocation-spike](../reports/061/skill-invocation-spike.md) — Spike confirming skill accessibility from spawned agents
- [prompting-dashboard-engine](2026-06-01-prompting-dashboard-engine.md) — The build that triggered this work

## Feed-Forward

- **Hardest decision:** Delegation over checkpointing. Both solve context
  death, but only delegation preserves uninterrupted execution without
  state serialization complexity.
- **Rejected alternatives:** Heuristic expansion (unreliable — run 061
  had fewer agents than calibration runs), split tail into two agents
  (YAGNI), auto-checkpoint (unnecessary file handoff), remove Tier 1
  (unsafe for solo builds).
- **Least confident:** Whether dual maintenance between tail-runner.md
  and SKILL.md Shared Tail will cause silent drift. TAIL_SYNC_POINT
  markers are procedural, not automated. First drift incident will be
  silent — a missing gate nobody notices until a bad build ships.
