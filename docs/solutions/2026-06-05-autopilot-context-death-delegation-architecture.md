---
title: "Delegation Over Checkpointing: Solving Autopilot Context Death"
date: 2026-06-05
category: architecture
severity: P0
problem_type: resource-exhaustion/context-death
tags:
  - context-management
  - swarm-orchestration
  - delegation-pattern
  - autopilot
  - output-contracts
  - worker-status-serialization
  - context-death
  - build-reliability
components:
  - .claude/skills/autopilot/SKILL.md
  - .claude/agents/swarm-runner.md
  - .claude/agents/deepen-merge-runner.md
  - .claude/agents/spec-completeness-checker.md
  - .claude/agents/spec-consistency-checker.md
root_cause: >
  Orchestrator context window saturates on swarm builds because it carries
  full outputs of every completed phase — deepening reports, gate check
  details, assembly merge logs, smoke/test results — even though it only
  needs STATUS and artifact paths going forward. The accumulation is
  structural (each phase adds to conversation history), not tunable
  (instruction-following alone cannot reliably prevent it).
resolution: >
  Three-stage architecture: (1) no-read discipline on PASS reports via
  limit:1 reads, (2) deepen-merge-runner delegates plan merge to fresh
  context (swarm-only), (3) swarm-runner delegates assembly + verification
  (Steps 11w-16w) to fresh context. Combined with two-tier output contracts
  (report_path + STATUS) for all phase agents. Honestly scoped: delegation
  saves post-spawn tail, but deepening + worker spawn remain inline due to
  Agent tool limitation. Not proven sufficient for 20+ agent builds.
review_findings:
  p1_count: 2
  p2_count: 3
  all_fixed: true
related_runs:
  - "050"
  - "061"
  - "064"
failure_class: context-exhaustion
recurrence_risk: medium
predecessor: docs/solutions/2026-06-01-tail-delegation-context-resilience.md
---

# Delegation Over Checkpointing: Solving Autopilot Context Death

## Problem

Swarm builds exhaust the orchestrator's context window before the pipeline
completes. Three runs demonstrated the pattern:

| Run | Agents | Died Where | Root Cause |
|-----|--------|------------|------------|
| 050 | 31 | Shared tail | Raw accumulation — 31 spawns + deepening + review |
| 061 | 10 | Before tail | Heavy pre-swarm density (deepening + gate retries) |
| 064 | 12 | Near-miss | Tail delegation saved it, but barely |

The orchestrator carries every phase's full output in conversation history.
A gate check report is ~5-10KB on disk. Deepening produces ~90K tokens of
research output. Assembly merges, smoke tests, and cleanup logs all compound.
By Step 16w, context is at ~98% — leaving ~2% for the 9-step review tail.

**Why checkpointing doesn't work:** The prior approach (CHECKPOINT.md +
manual `/tail-resume`) requires human intervention, violating the
"fully unattended execution" constraint. It also loses all in-context state
at the resume boundary, forcing the resumed session to re-read everything —
which partially recreates the problem it was meant to solve.

**The key insight:** Most phase state is already on disk. The orchestrator
needs only STATUS (PASS/FAIL) and artifact paths to proceed. It does NOT
need the full text of reports, merge logs, or worker outputs. The fix is
to stop the orchestrator from ever seeing that detail.

## Root Cause

Context death is structural, not tunable:

1. **Phase outputs accumulate.** Each Read tool call and Agent return value
   stays in conversation history. There is no way to "forget" them.
2. **Agent tool is top-level only.** Sub-agents cannot spawn other agents
   (confirmed by spike: `docs/reports/spike-nested-worktree-delegation.md`).
   This means deepening research and worker spawn MUST run inline in the
   orchestrator — they cannot be fully delegated.
3. **Instruction-following is probabilistic.** Telling the orchestrator
   "don't read the full report" reduces context but doesn't guarantee it.
   The LLM may still read more than instructed, or tool outputs may include
   more content than expected.

The combination means: no single technique solves it. The solution requires
layered defenses — producer-side contracts (agents return less), consumer-side
discipline (orchestrator reads less), and structural delegation (heavy phases
run in fresh context windows).

## Solution: Three-Stage Architecture

### Stage 1: No-Read Discipline + Output Contracts

**Consumer side (SKILL.md):** After every phase that writes a report, the
orchestrator reads with `limit: 1` — only the STATUS line. On PASS, it
proceeds without reading the full report. On FAIL, it reads the full report
for recovery.

Steps modified: 9w.5, 9w.6, 9w.7 (gate checks).

**Producer side (agent files):** Every agent follows a two-tier output
contract based on the tail-runner's proven pattern:

```
report_path: docs/reports/065/smoke-test.md
STATUS: PASS
```

Rules:
- Agents write full reports to disk (always).
- Agents return only `report_path` + `STATUS` to the orchestrator.
- The orchestrator searches backward for `STATUS:` in agent output (robust
  against trailing text).
- No `blocking`, `retry`, or `next_step` fields — the orchestrator owns
  retry logic from SKILL.md step definitions. Encoding it in agent output
  creates a second source of truth.

**Phase reports standardized:** No YAML frontmatter on reports. Line 1 is
always `STATUS: PASS` or `STATUS: FAIL -- <reason>`. No markdown formatting
around STATUS values.

### Stage 2: Deepen-Merge Delegation (Swarm Only)

**Why swarm-only:** The `/compound-engineering:deepen-plan` skill spawns
research sub-agents via the Agent tool. Sub-agents don't have the Agent
tool. Therefore deepening research MUST run inline (both solo and swarm).

After deepening, merge/commit/audit is delegated to `deepen-merge-runner`
in swarm builds. This saves no meaningful context (the orchestrator already
carries the deepening outputs), but keeps a consistent pattern: every swarm
phase beyond gates runs in a fresh context window.

Solo builds merge inline (Step 6.03s) — they don't hit context limits.

**Key design decision — corrections format:** The orchestrator extracts a
compressed correction summary from deepening outputs and passes it to the
merge runner in a structured format:

```markdown
### <Section Name>
**Change:** <old text → new text>
**Rationale:** <why the deepening agent recommended this>
```

The merge runner uses Edit tool to apply each change, matching section
headings as anchors. On anchor failure: read the file, find the correct
location, retry once.

### Stage 3: Swarm-Runner Delegation

The swarm-runner agent executes Steps 11w-16w (assembly merge, contract
check, smoke test, test suite, merge to main, cleanup) in a fresh context
window.

**Scope is reduced from the original design:** The spike confirmed sub-agents
lack the Agent tool, so swarm-runner cannot spawn workers. The orchestrator
keeps Steps 7w-10.5w (swarm planner, worker spawn, ownership gate).

**Key behaviors:**
- Merge conflicts resolved inline (cannot spawn assembly-fix — same
  Agent tool limitation). Uses the plan's spec as source of truth.
- Contract check is a circuit breaker: FAIL after one retry → abort
  pipeline, set `final_status: "FAIL -- contract-check"`, return immediately.
- Smoke test and test suite are non-blocking: FAIL after retry → continue
  to merge, note failure in assembly-summary.md. Tail-runner reviews.

### Step Reordering

Run-id generation moved from Step 6.1 to Step 5.5 (before deepening), so
`run_id` and `reports_dir` exist when the merge agent needs them. All 8
references to "Step 6.1" in SKILL.md updated to "Step 5.5".

**Special case:** Step 6.07's closing pointer ("proceed to Step 6.1")
became "proceed to Step 6.08" (the new self-review commit step) — NOT
"Step 5.5". This is a control-flow pointer, not a run-id citation.

## Pattern: worker_status Serialization

**Problem discovered in review (P1-1):** Step 10w didn't define how the
orchestrator builds the `{ role, branch, status }` list that swarm-runner
consumes. The orchestrator knows worker completion status from spawn results,
but this knowledge is implicit in conversation history — not serialized for
the sub-agent.

**Fix:** After all workers complete, the orchestrator explicitly constructs
`worker_status` — a list of `{ role, branch, status }` where status is
COMPLETED, TIMED_OUT, or FAILED. The swarm-runner skips merging branches
marked TIMED_OUT or FAILED.

**Lesson:** When delegating to a sub-agent, serialize ALL implicit state.
The sub-agent has no access to the orchestrator's conversation history.
If the orchestrator "knows" something from a prior tool call, it must
explicitly pass it. This is obvious in retrospect but was missed because
the worker spawn and the swarm-runner spawn feel like "the same context"
to the person writing the SKILL.md — they aren't.

## Pattern: Iterative STATUS Normalization

**Problem discovered in review (P2-3):** The SKILL.md said the orchestrator
should "normalize" STATUS values (strip quotes, backticks, markdown
formatting) but didn't specify how. "Start and end" stripping was ambiguous.

**Fix:** Defined as iterative stripping from both ends — repeatedly remove
leading/trailing whitespace, backticks, asterisks, and quotes until the
value stabilizes. This handles nested formatting like `` `**PASS**` ``.

**Why iterative:** Agents sometimes wrap STATUS values in markdown
formatting (bold, code). A single strip pass misses nested cases.
Iterative stripping is the simplest approach that handles all observed
variations.

## Pattern: Orchestration State in Markdown, Not YAML

**Brainstorm proposed:** YAML frontmatter in BUILD_TRACKING.md for
machine-readable orchestration state.

**Deepening research found:** Zero precedent for programmatic YAML editing
in this codebase. All 15+ builds use markdown tables and section-based
appends. The YAML validation protocol would be solving a self-created
problem.

**Resolution:** Orchestration state lives in a `## Phase Status` markdown
table, following the proven pattern. Run state uses key-value lines that
agents can grep for. This eliminated the brainstorm's #1 risk (YAML
frontmatter fragility under repeated agent edits).

## What Changed

| File | Change |
|------|--------|
| `.claude/skills/autopilot/SKILL.md` | Added `limit: 1` reads (9w.5-9w.7); moved run-id to Step 5.5; added Step 6.03/6.03s (swarm/solo deepen merge); added Step 6.08 (self-review commit); replaced Steps 11w-16w with swarm-runner spawn; added Phase Status insertion at Step 1.5; updated all Step 6.1 refs to 5.5 |
| `.claude/agents/swarm-runner.md` | **New.** Assembly + verification in fresh context (Steps 11w-16w). Circuit breaker on contract-check FAIL. Inline merge conflict resolution. |
| `.claude/agents/deepen-merge-runner.md` | **New.** Merges deepening corrections, commits, writes audit trail. Swarm-only. |
| `.claude/agents/spec-completeness-checker.md` | Added output contract (report_path + STATUS). |
| `.claude/agents/spec-consistency-checker.md` | Added output contract (report_path + STATUS). |

## What Did NOT Change

| Item | Why |
|------|-----|
| Solo build path | Solo doesn't hit context limits. Inline execution unchanged. |
| tail-runner.md | Already works. No changes needed. |
| spec-contract-checker.md | Superseded by swarm-runner inline check. File kept for potential solo use. |
| smoke-test-runner.md | Superseded by swarm-runner inline check. Same rationale. |
| test-suite-runner.md | Superseded by swarm-runner inline check. Same rationale. |
| assembly-fix.md | Cannot be spawned from swarm-runner (sub-agents lack Agent tool). Conflicts resolved inline. |
| `~/.claude/docs/autopilot-tracking-template.md` | Global template unchanged. Phase Status inserted locally after copy. |

## Risk Resolution

| Plan Feed-Forward Risk | What Happened | Resolved? |
|------------------------|---------------|-----------|
| BUILD_TRACKING YAML frontmatter fragility | Dropped entirely. Replaced with markdown Phase Status table. | Yes — risk eliminated |
| Reduced swarm-runner scope insufficient for 20+ builds | Acknowledged as architectural limitation. Deepening + worker spawn require Agent tool, must stay inline. Documented honestly. | Partially — design limitation, not a bug. First 20+ build calibrates. |
| Tier 1 output contract compliance depends on instruction-following | Standardized on proven 2-line tail-runner pattern. Backward STATUS search handles trailing text. | Yes — pattern proven across 7 agents |

## Honest Limitations

1. **20+ agent builds not proven.** Deepening (Step 6) and worker spawn
   (Steps 7w-10.5w) remain inline because they require the Agent tool.
   Context savings come from post-spawn tail delegation. Whether this is
   sufficient for 20+ agents is unknown until the first real build.

2. **Tail-runner has no auto-checkpoint.** If a 20+ agent review phase
   exhausts tail-runner context, recovery is manual. This is intentional —
   adding auto-checkpoint reintroduces the complexity this solution
   was designed to eliminate.

3. **context_proxy_chars is a rough metric.** It's a manual tally of
   Read/Agent output character counts. It misses system prompts, tool
   schemas, and compaction effects. Useful for comparing runs, not for
   absolute thresholds.

4. **The fallback is expensive.** If delegation proves insufficient for
   very large builds (50+), the next step is an external orchestrator
   (Agent SDK or shell harness) — a fundamentally different architecture
   requiring a rewrite of 835 lines of SKILL.md logic.

## Prevention

**What this solution prevents:**
- Context death on 10-15 agent swarm builds (the current operating range).
- Orchestrator reading full reports on PASS (no-read discipline + output
  contracts eliminate this class of waste).
- YAML frontmatter corruption risk (never introduced — markdown throughout).

**What remains unproven:**
- 20+ agent builds completing fully unattended.
- Whether the 30-minute tail-runner timeout is sufficient for 20+ agents.
- Whether BUILD_TRACKING.md Edit writes remain stable under heavy
  concurrent edits.

**Monitoring plan:** The first 20+ agent build must be watched. Track
`context_proxy_chars` at each phase boundary. If the orchestrator exceeds
~70% context before Step 17w, the architecture needs the next tier
(external orchestrator or worker-spawn delegation via future platform
changes).

## Feed-Forward

- **Hardest decision:** Dropping YAML frontmatter from BUILD_TRACKING.md
  after the brainstorm committed to it. Deepening research found zero
  precedent for programmatic YAML editing. The brainstorm's validation
  protocol was solving a self-created problem. Markdown Phase Status
  table aligns with 15+ builds of proven patterns.

- **Rejected alternatives:**
  - YAML frontmatter in BUILD_TRACKING.md (zero precedent, fragility risk)
  - Pipe-delimited Tier 1 decision lines (no precedent; all agents use
    multi-line key-value)
  - Separate PHASE_STATE.json (dual-source-of-truth drift)
  - Hard 30% context target as gate (metric has measurement gaps;
    downgraded to observability-only)
  - Stage 2 as context-saving mechanism (orchestrator already carries
    deepening outputs; kept for structural consistency only)
  - Full phase delegation / 7 agents (YAGNI — 3 agents solve 80%)
  - External orchestrator (high migration cost, feature loss, problem
    is smaller than it looks)
  - Checkpointing with manual resume (violates unattended constraint,
    reintroduces state-reconstruction problem)

- **Least confident:** Whether the tail-runner can complete review +
  compound + learnings for a 20+ agent build within its fresh context
  window. The 30-minute timeout and lack of auto-checkpoint make this
  the riskiest remaining gap. First real 20+ build will calibrate.
