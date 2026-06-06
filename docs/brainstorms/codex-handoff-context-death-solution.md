# Codex Handoff: Autopilot Context Death — Solution Design Review

## Context for Codex

We are designing a solution to a recurring problem in our compound engineering autopilot system. The autopilot runs a multi-phase build pipeline (brainstorm → plan → deepen → pre-swarm gates → swarm → assembly → smoke → review → compound → tail) in a single Claude Code session. On complex builds (12-31 agent swarms), the orchestrator runs out of context before the pipeline completes. We call this "context death."

### The Problem in Numbers

- **Context window:** 1M tokens (Opus 4.6 with [1m])
- **Heaviest inline phases (in orchestrator context):**
  - Deepening (Step 3): ~90K tokens — spawns 4-5 research agents, integrates results back into plan
  - Pre-swarm gates (Step 9w): ~50K cumulative — spec consistency + completeness checks
  - Swarm spawn coordination (Step 10w-12w): ~40-60K — worktree creation, agent briefing, merge coordination
- **Current mitigation:** Tail-runner agent (Step 17w) delegates the entire "shared tail" (review, compound, learnings, self-audit) to a fresh-context subagent. Saves ~200K tokens.
- **Current recovery:** CHECKPOINT.md + `/tail-resume` skill for manual recovery after context death
- **Builds affected:** Runs 050 (31 agents), 061 (10 agents, dense pre-swarm), 064 (12 agents) all hit context death or required checkpointing

### What We've Already Built

- **BUILD_TRACKING.md** — disk-based state file tracking agent status, failures, and metrics
- **HANDOFF.md** — project state for session handoffs
- **CHECKPOINT.md** — explicit artifact paths for resume after context death
- **tail-runner agent** — fresh-context subagent for the entire shared tail (review → self-audit)
- **self-audit-reviewer agent** — independent verification in fresh context
- **Swarm worker agents** — 10-31 parallel agents in isolated worktrees (already use fresh context)
- **Phase state on disk** — plans, brainstorms, solution docs, reports all written to disk
- All inter-phase communication ALREADY uses disk files, not conversation history

### Key Architectural Insight

The autopilot already writes state to disk between phases. The problem is that the ORCHESTRATOR accumulates context from all phases even though it technically only needs file paths and pass/fail results from each phase. The conversation history carries the full output of deepening research, gate reports, and merge coordination — none of which is needed after the phase completes.

---

## Candidates We've Identified

### Candidate 4: Hybrid Delegation (2 new agents)
Delegate only the 3 heaviest phases to subagents:
- **deepen-agent** (new) — runs research agents, rewrites plan. Saves ~90K from orchestrator.
- **swarm-orchestrator-agent** (new) — launches workers, assembly, smoke. Saves ~40-60K.
- **tail-agent** (exists) — review, compound, self-audit.
- Orchestrator handles brainstorm, plan, gates, and coordination inline (~25% of 1M).
- **Pros:** Fewest new components (2 agents). Incremental change. Each agent independently testable.
- **Cons:** Still has an orchestrator accumulating some context. May need more delegation later.

### Candidate 7: Agent SDK External Orchestrator
A Python/TypeScript script calls `query()` for each phase. Each call creates a completely fresh session. The script captures output and passes it to the next phase. The orchestrator lives outside any context window.
- **Pros:** Context death structurally impossible. Full programmatic control. Each phase gets 100% of context.
- **Cons:** Requires machine to stay running. You build orchestration logic yourself. New dependency (Agent SDK).

### Candidate 9: Anthropic's Three-Agent Harness (External Loop)
A shell script loop checks a contract file (BUILD_TRACKING.md). While phases remain incomplete, it spawns a coding agent. A separate evaluator agent grades work.
```bash
while grep -q '"passes": false' test-results.json; do
    claude -p "Read PROGRESS.md and build the next unfinished feature"
done
```
- **Pros:** Proven by Anthropic's engineering team. Simple (~50 lines). Context death eliminated.
- **Cons:** Less Claude-native. Orchestration is manual code.

### Candidate 10: Stop Hook + Delegated Phase Agents + /goal
Combined approach:
- **Stop hook** reads `PHASE_STATE.json` from disk after every turn. Drives phase transitions deterministically.
- **Phase agents** handle heavy work in fresh context (deepen, swarm, tail).
- **`/goal`** sets the overall completion condition ("self-audit passes, HANDOFF updated").
- **Pros:** Deterministic transitions + fresh context + verified completion. Best of all three mechanisms.
- **Cons:** Most moving parts. Stop hook + 2 agents + /goal condition all need to work together.

### Other Candidates Considered but Not Shortlisted

| # | Candidate | Why not shortlisted |
|---|-----------|-------------------|
| 1 | /goal + compaction-resilient autopilot | Compaction is lossy (~12%). Skill descriptions vanish. May still hit limits. |
| 2 | Custom Stop Hook state machine alone | Same session = still accumulates context. Doesn't solve the fundamental problem. |
| 3 | Agent Teams (experimental) | Experimental feature. Can't nest teams. Higher token cost. |
| 5 | Full phase delegation (7 agents) | 7 new agents is high maintenance cost. Candidate 4 solves 80% of the problem with 20% of the work. |
| 6 | Dynamic Workflows (JS) | Full rewrite of autopilot as JavaScript. High effort for uncertain gain. |
| 8 | Routines /fire chain (cloud) | Can't test local Flask+SQLite apps. Research preview. No local file access. |

---

## What We Need From Codex

### 1. Critique These Candidates
For each of the 4 shortlisted candidates (4, 7, 9, 10):
- What failure modes are we not seeing?
- What assumptions are wrong?
- Which candidate is most robust to future changes (more agents, new Claude features, model upgrades)?

### 2. Propose New Candidates
We believe there may be better approaches we haven't considered. Some prompts:
- Is there a way to make the EXISTING autopilot context-resilient without adding agents or external scripts?
- Could Claude Code's native compaction be leveraged more intelligently (e.g., strategic `/compact` at phase boundaries)?
- Are there patterns from other long-running agent systems (not Claude-specific) that would apply?
- Could the problem be reframed entirely? (e.g., instead of "how to survive context death," maybe "how to never need this much context in the first place")
- Is there a minimal change (< 20 lines of code) that would solve 90% of the problem?

### 3. Rank All Candidates
After adding your own candidates, rank all of them on:
1. **Reliability** — how certain is it that context death is eliminated?
2. **Simplicity** — how much new code/infrastructure is needed?
3. **Maintainability** — how much ongoing maintenance does it add?
4. **Future-proofing** — how well does it adapt as Claude Code evolves?
5. **Incremental adoptability** — can it be shipped in stages?

---

## Key Files to Read

For full context on the autopilot system:
- `CLAUDE.md` — operating contract (autonomy classes, forbidden actions, required artifacts)
- `HANDOFF.md` — current project state
- `.claude/skills/autopilot/SKILL.md` — the autopilot skill (the system being redesigned)
- `.claude/agents/tail-runner.md` — existing fresh-context delegation pattern
- `.claude/agents/self-audit-reviewer.md` — independent verification agent
- `docs/solutions/2026-06-02-prompting-dashboard-engine-run-064.md` — most recent build (context death occurred)
- `BUILD_TRACKING.md` — disk-based state tracking template
- `CHECKPOINT.md` — (deleted, but was the recovery mechanism for Run 064)
- `compound-engineering.local.md` — review context for most recent run

## Constraints

- Solution must work locally (Flask+SQLite test apps need local execution)
- Solution must be end-to-end automated (no manual session splits)
- Solution should be incremental (can ship in stages, not all-or-nothing)
- Existing autopilot artifacts (BUILD_TRACKING, HANDOFF, solution docs, agent-pitfalls) must continue to be produced
- The compound engineering 6-phase loop must be preserved
