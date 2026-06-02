---
title: "Run 061 Context Death Analysis"
run_id: "061"
date: 2026-06-01
project: Prompting Dashboard Engine
status: incomplete
---

# Run 061: Why Autopilot Didn't Finish

## What Happened

Run 061 (Prompting Dashboard Engine, 10-agent swarm) completed the entire
build phase successfully — all 10 agents merged, contract check fixed,
smoke tests 13/13 PASS — then stopped before the review tail started.

The orchestrator wrote a CHECKPOINT.md at `next_step: "Shared Tail: Review"`
and exited. This left 9 of 9 tail steps unfinished.

## Did Agents Run in Their Own Context Windows?

**Yes.** The swarm agents all launched correctly with `isolation: "worktree"`
and `run_in_background: true` (autopilot SKILL.md Step 10w, line 401-403).
Each of the 10 agents ran in a separate process with its own context window
and its own git worktree. The agents themselves were not the problem.

## Root Cause: Orchestrator Context Accumulation

The agents run in their own context, but the **orchestrator** (the main
autopilot session) still accumulates context from every interaction with
those agents. Even though agent work happens off-screen, the orchestrator's
context grows from:

### What fills the orchestrator's context

| Source | What it adds to orchestrator context | Count in run 061 |
|--------|--------------------------------------|-------------------|
| **Agent spawn prompts** | Full spec + pitfalls + rules sent as prompt text to each agent | 10 swarm agents |
| **Agent completion results** | Each agent's result/notification returned to orchestrator | 10 results |
| **Deepening sub-agents** | deepen-plan spawns skill agents, learnings agents, research agents, review agents — the skill says "20, 30, 40 parallel agents is fine" | 4+ research agents (plan says 4), likely more |
| **Pre-swarm gate agents** | spec-consistency-checker, spec-completeness-checker, their reports | 2 agents + reports |
| **Verification agents** | contract-checker, assembly-fix, smoke-test-runner | 3 agents + reports |
| **Ownership gate diffs** | `git diff` output for each of 10 branches | 10 diffs |
| **Assembly merges** | Merge output for each of 10 branches | 10 merges |
| **BUILD_TRACKING writes** | 10 incremental appends + gate results | ~14 Bash calls |
| **Cleanup** | 10 worktree removes + 11 branch deletes | ~21 Bash calls |

**The orchestrator's context is proportional to the number of agents, not
the amount of work each agent does.** This is the structural insight from
the existing solution doc (2026-05-20):

> "Disk is the working memory of the orchestrator, not the context window."

### The deepen-plan amplifier

The deepen-plan skill (line 124 of the skill) says:

> "No limit on skill sub-agents. Spawn one for every skill that could
> possibly be relevant."

And Step 5 says:

> "Do NOT filter agents by 'relevance' — run them ALL... 20, 30, 40
> parallel agents is fine."

Each of these sub-agents' results flows back into the orchestrator's
context before the swarm even starts. For run 061, the plan's Enhancement
Summary lists 4 research agents (framework-docs-researcher,
security-sentinel, performance-oracle, architecture-strategist), but the
actual deepening likely spawned many more (skill matchers, learnings
scanners, review agents). These results — plus the subsequent plan
rewrite, two document-review passes, and spec gates — consumed a large
portion of the context window before the 10-agent swarm even launched.

## Why the Checkpoint Didn't Save It

The context-budget checkpoint (autopilot SKILL.md line 618) was designed
to fire **after** Review + Compound + Update Learnings + Fill
BUILD_TRACKING — leaving only 3 cheap steps for `/tail-resume`. The
design rationale (from the 2026-05-20 solution doc):

> "Checkpoint placement: Post-compound, post-BUILD_TRACKING fill — All
> synthesis artifacts exist. Resume only runs learnings + self-audit
> (cheapest tail steps)."

**Run 061's context died 6 steps before that checkpoint location.** The
orchestrator never reached Review, let alone Compound. It improvised an
early checkpoint at `next_step: "Shared Tail: Review"` — a resume point
that `/tail-resume` doesn't support.

### The known gap

The solution doc **already identified this exact failure mode** as future
work (line 206):

> "**Tier 2 pre-review resume:** Add a second gate after work phase
> completes, before review launches."

This was listed under "Future Hardening (not yet implemented)." Run 061
is the first real-world occurrence of the scenario it was meant to prevent.

## Timeline of Context Consumption

```
Steps 1-2:   Compound start, brief expansion          ~5% context
Steps 3-4:   Brainstorm + refinement                   ~8% context
Steps 5-6:   Plan + deepen (4+ research agents)       ~20% context
Steps 6.05-6.07: Two document-review passes            ~5% context
Steps 6.1-6.5: Run ID, deepening merge                 ~3% context
Steps 9w.5-9w.7: Pre-swarm gates (3 agents)           ~10% context
Step 10w:    Spawn 10 swarm agents (prompts)           ~15% context
Step 10w:    Receive 10 agent results                  ~15% context
Steps 10.5w-11w: Ownership gate + assembly merge       ~8% context
Steps 12w-13w: Contract check + smoke test agents      ~6% context
Steps 15w-16w: Merge + cleanup                         ~3% context
                                                  ─────────────────
Total at Step 16w:                                    ~98% context
Remaining for 9 tail steps:                            ~2% context
```

(Percentages are estimates based on relative operation sizes.)

## Why 10 Agents Triggered It but Prior Runs Didn't

The checkpoint heuristic validation table from the solution doc:

| Run | Agents | Score | Context died? |
|-----|--------|-------|---------------|
| 047 | 16 | 25 | No |
| 048 | 20 | 40.5 | No |
| 049 | 25 | 37 | No |
| 050 | 31 | 52.5 | Yes |
| **061** | **10** | **never evaluated** | **Yes (early)** |

Run 061 has fewer swarm agents than all calibration runs, yet still died.
The difference: run 061 had a **heavier pre-swarm phase**. The plan has
15 P1/P2 fixes from deepening, 3 consistency contradictions found across
2 rounds, 6 mandatory spec coverage sections, and 2 document-review
passes. Prior calibration runs may not have had this density of pre-swarm
work.

The heuristic only counts swarm agents, deepening agents, review agents,
and fix retries. It doesn't account for:
- Pre-swarm gate iterations (consistency fix rounds)
- Document review passes
- Spec completeness fix-and-retry cycles
- The actual number of sub-agents spawned by deepen-plan (which can far
  exceed the 4 "research agents" listed in the Enhancement Summary)

## Evidence Summary

| Evidence | Finding |
|----------|---------|
| Autopilot SKILL.md Step 10w | Agents use `isolation: "worktree"` + `run_in_background: true` — confirmed separate context |
| CHECKPOINT.md `next_step` | `"Shared Tail: Review"` — 6 steps before the designed checkpoint |
| CHECKPOINT.md `solution_doc_path` | `TBD` — compound never ran |
| CHECKPOINT.md `review_summary_path` | `TBD` — review never ran |
| Solution doc 2026-05-20 line 206 | "Tier 2 pre-review resume" listed as future work, never implemented |
| deepen-plan SKILL.md line 124 | "No limit on skill sub-agents" — uncapped context consumption |
| BUILD_TRACKING.md | AGENT_STATUS rows misplaced after Template Version section (incremental writes targeted wrong location) |
| Git log | 28 commits, 2074 insertions between run start and checkpoint |

## Recommendations

### 1. Implement "Tier 2 Pre-Review Resume" (the known fix)

Add a second checkpoint gate after Step 16w (swarm cleanup), before the
Shared Tail begins. This was already identified in the solution doc but
never built.

```
### Context-Budget Checkpoint — Pre-Review (SWARM ONLY)

If swarm_agents >= 8 OR deepening round produced > 10 P1/P2 fixes:
  Write CHECKPOINT.md with next_step: "Shared Tail: Review"
  STOP.
```

Update `/tail-resume` to accept `"Shared Tail: Review"` and run all 9
tail steps from that point.

### 2. Cap deepen-plan sub-agent count

The instruction "20, 30, 40 parallel agents is fine" in deepen-plan is
at odds with context conservation in long pipelines. Add a cap when
running inside autopilot (e.g., max 8 sub-agents total) or have
deepen-plan write findings to disk instead of returning them in-context.

### 3. Expand the heuristic

Add pre-swarm work to the load formula:

```
load = swarm_agents
     + (deepening_agents * 2)
     + (review_agents * 1.5)
     + (fix_retries * 3)
     + (pre_swarm_gate_rounds * 2)    # NEW
     + (document_review_passes * 1.5) # NEW
```

### 4. Fix BUILD_TRACKING structure

The AGENT_STATUS rows ended up after the Template Version section. The
incremental `echo >>` writes appended to the file end instead of
inserting into the table. Consider using Edit tool instead of echo
for row insertion.
