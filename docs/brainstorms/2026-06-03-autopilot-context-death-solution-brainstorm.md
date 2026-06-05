---
title: "Autopilot Context Death Solution"
date: 2026-06-03
status: brainstorm-revised-r3
type: brainstorm
origin: docs/brainstorms/2026-06-03-autopilot-context-death-solution-handoff.md
related:
  - docs/brainstorms/2026-05-20-autopilot-context-optimization-brainstorm.md
  - docs/brainstorms/2026-06-01-tail-delegation-brainstorm.md
  - docs/brainstorms/codex-handoff-context-death-solution.md
  - docs/solutions/2026-06-02-prompting-dashboard-engine-run-064.md
feed_forward:
  risk: "Reduced swarm-runner scope (11w-16w only) may not save enough context for 20+ agent builds; BUILD_TRACKING YAML frontmatter fragility under repeated agent edits"
  verify_first: true
---

# Autopilot Context Death Solution -- Brainstorm

## Problem Summary

The autopilot runs the full compound engineering pipeline in one Claude Code session. On complex swarm builds (12-31 agents), the orchestrator runs out of context before the pipeline completes. We call this "context death."

### What We Know From Prior Builds

| Run | Agents | Context Death? | Where? | Root Cause |
|-----|--------|----------------|--------|------------|
| 050 | 31 | Yes | Shared tail | Raw accumulation -- 31 agent spawns + deepening + review |
| 061 | 10 | Yes | Before tail | Heavy pre-swarm density (deepening + gate retries) |
| 064 | 12 | Near-miss | Tail delegation saved it | 15 deepening fixes + 3 consistency rounds + 2 doc reviews pre-swarm |

The pattern: context death is not caused by one big phase. It is caused by the orchestrator carrying the full output of every completed phase in its conversation history, even though it only needs the STATUS line and artifact paths going forward.

### The Key Insight

Most phase state is already written to disk. The orchestrator needs only:
- Phase status (PASS/FAIL)
- Artifact paths (where the report was written)
- Key counts (agent count, finding count, etc.)
- Next action (which step to run next)

It does NOT need the full text of deepening reports, gate check details, merge logs, or worker outputs. But the current autopilot reads these files inline, and they stay in the conversation history forever.

### Context Budget Breakdown (Unmeasured Estimates -- See Measurement Plan)

These numbers are rough estimates based on file sizes and observed behavior.
They have NOT been measured against actual orchestrator context consumption.
The plan phase must define a measurement method before using these numbers
to set thresholds or validate success.

| Phase | Est. Tokens (rough) | Avoidable? | Confidence |
|-------|---------------------|------------|------------|
| SKILL.md (loaded once) | ~15K | No | Medium (file is 835 lines, but system prompt overhead unknown) |
| Steps 1-5 (brainstorm, plan) | ~60K | Partially (plan must be read for branching) | Low (depends on brainstorm length) |
| Step 6 (deepening) | ~90K | Yes -- only merged plan needed | Low (deepening agent count varies 4-12) |
| Steps 9w.5-9w.7 (gates) | ~50K cumulative | Yes -- only STATUS needed | Medium (gate reports are ~5-10KB on disk) |
| Step 10w (agent spawn prompts) | ~40-60K (N * spec size) | Partially (spec sent per agent) | Medium (N and spec size are known per build) |
| Steps 11w-15w (assembly, smoke, test) | ~30-50K | Yes -- only STATUS + commit hashes needed | Low (depends on merge conflicts and retries) |
| Step 17w (tail delegation prompt) | ~5K | No | High (tail prompt is a fixed template) |
| **Total orchestrator load** | **~290-330K (est.)** | **~170-210K avoidable (est.)** | **Low overall** |

**Measurement plan (required before Stage 1 ships):**
1. **Proxy metric:** After each phase, write the total character count of all Read
   tool outputs and Agent tool outputs in the orchestrator's conversation to a
   tracking line in BUILD_TRACKING.md. Character count * 0.25 approximates tokens.
2. **Validation run:** Run one 10-12 agent build with the current (unmodified)
   autopilot. Record the proxy metric at each phase boundary. This produces the
   baseline against which all context savings are measured.
3. **Success threshold:** Defined relative to the baseline, not to these estimates.
   Stage 1 must show a measurable reduction vs. baseline. Stages 2+3 combined
   must show the orchestrator's cumulative proxy metric stays below 60% of
   baseline at Step 17w (fallback), with 30% as the stretch target.

## Current System Constraints

These must be preserved by any solution:

1. **Fully unattended execution.** No human interaction during a run. No `PAUSED_FOR_CONTEXT` requiring manual `/tail-resume`.
2. **Required artifacts.** BUILD_TRACKING.md, solution doc, learnings propagation, HANDOFF.md, self-audit report. All must be produced.
3. **6-phase compound engineering loop.** Brainstorm, plan, work, review, compound, learnings. The phases cannot be reordered or removed.
4. **Local execution.** Flask + SQLite apps need local file system access and local smoke tests.
5. **Swarm worktree isolation.** Worker agents run in isolated worktrees. This works well and must continue.
6. **Incremental adoption.** The solution must be shippable in stages, not all-or-nothing.
7. **Tail delegation.** The tail-runner agent already works. Any solution must preserve or extend it, not replace it.

## Candidate Analysis

### Candidate 1: No-Read Orchestrator Discipline

**What it is:** Change the autopilot SKILL.md instructions so the orchestrator never reads full phase reports when STATUS is PASS. After each phase, the orchestrator reads only the STATUS line and artifact paths from the report file. Full reports stay on disk, unread by the orchestrator.

**How it works:**
- **Phase reports MUST NOT have YAML frontmatter.** Only BUILD_TRACKING.md
  has frontmatter (for orchestration state). All other phase reports
  (gate checks, smoke tests, contract checks, ownership gates, deepening
  reports) start with content on line 1.
- Line 1 of every phase report is the STATUS line. Format:
  `STATUS: PASS` or `STATUS: FAIL -- <reason>`. No markdown formatting
  (`**`, `###`, backticks) around the STATUS value. No blank lines before it.
- After each phase, the orchestrator reads the report file with `limit: 1`
  (Read tool's line-limit parameter). This always returns exactly 1 line --
  the STATUS line. Deterministic, no ambiguity about frontmatter depth.
- If the STATUS line contains `PASS`, the orchestrator proceeds without
  reading the rest. If it contains `FAIL`, the orchestrator reads the full
  report for recovery.
- The SKILL.md instructions explicitly say "DO NOT read the full report"
  after each phase that returns PASS.

**Evaluation:**
- **Reliability:** Reduces context but does not eliminate death. The LLM may still read more than instructed, or tool outputs may include more content than expected. This is a _probabilistic_ reduction, not a _structural_ one.
- **Simplicity:** Very low cost -- approximately 20-30 lines of SKILL.md changes. No new files, no new agents.
- **Maintainability:** Minimal. The same person maintaining SKILL.md already writes these instructions.
- **Future-proofing:** Fragile. Depends on instruction-following fidelity. A model update that interprets "read only the first 5 lines" differently could break it.
- **Incremental adoptability:** Excellent. Can ship immediately. Easily reversed.
- **Unattended:** Yes, no human interaction.

**Verdict:** Necessary but not sufficient. This is a discipline layer, not an architecture change. It cannot prevent context death on 25+ agent builds because it doesn't address the structural problem (full agent spawn prompts, deepening synthesis in-context). But it is the cheapest possible first stage and validates whether SKILL.md instruction discipline is reliable at all.

---

### Candidate 2: Bounded Phase Summaries

**What it is:** Every heavy phase (deepening, gates, swarm, assembly, smoke) writes a full report to disk but returns only a strict bounded summary to the orchestrator. The summary is capped at 1-2K tokens and follows a machine-readable format.

**Summary contract (two tiers):**

The orchestrator needs a compact decision line (Tier 1) plus optional
detail fields (Tier 2). Tier 1 is always returned. Tier 2 is returned
only by phases that produce the relevant state (e.g., merge_status only
from assembly phases).

**Tier 1 -- Decision line (MUST fit in 200 characters):**
```
STATUS: PASS | blocking: false | retry: false | report: docs/reports/065/smoke-test.md | next: Step 14w
```

This is a single pipe-delimited line. The orchestrator parses it for
pass/fail, blocking, retry eligibility, report path, and next step. It
never exceeds 200 characters because paths are relative and field values
are short tokens.

**Tier 2 -- Detail fields (written to BUILD_TRACKING frontmatter, not returned inline):**
```
counts: { agents: 12, findings: 0, fixes: 0 }
merge_status: "merged to master at abc1234"
preserved_branches: ["swarm-065-auth"]
cleanup_status: "11 removed, 1 preserved"
failure_report_path: null
artifact_paths: [docs/reports/065/smoke-test.md]
```

Tier 2 fields are written directly to the BUILD_TRACKING.md YAML
frontmatter by the phase agent before returning. The orchestrator reads
them from frontmatter only if it needs them for recovery (FAIL path).
On PASS, the orchestrator uses only the Tier 1 decision line.

**Why two tiers:** The original 11-field summary contract exceeds 500
characters with real paths and branch names. Splitting into a compact
decision line (always returned) and persistent detail fields (written to
disk) keeps the orchestrator's context small while preserving all state
for downstream consumers.

**Field definitions (Tier 1):**
- `STATUS` -- PASS or FAIL.
- `blocking` -- true = pipeline must stop. false = continue with failure noted.
- `retry` -- true = orchestrator should retry (max 1). false = non-retriable.
- `report` -- path to the full report on disk.
- `next` -- exact next step ID (e.g., "Step 14w").

**Field definitions (Tier 2, in frontmatter):**
- `counts` -- phase-specific metrics (agent count, test count, finding count).
- `merge_status` -- commit hash and target branch. null for non-merge phases.
- `preserved_branches` -- branches kept for inspection. Empty on clean success.
- `cleanup_status` -- worktree/branch cleanup result.
- `failure_report_path` -- detailed failure report path. null on PASS.
- `artifact_paths` -- all files written by this phase.

**How it differs from Candidate 1:** No-read discipline tells the orchestrator "don't read the file." Bounded summaries tell the _phase_ "write a small summary that the orchestrator CAN read." The orchestrator reads everything the phase returns -- but the phase returns less.

**Evaluation:**
- **Reliability:** Better than Candidate 1 because the constraint is on the producer (phase/agent), not the consumer (orchestrator). If the phase agent follows the contract, the orchestrator never sees the full report. But still depends on instruction-following.
- **Simplicity:** Medium. Every agent definition that returns to the orchestrator needs a summary contract. 5-7 agent files need modification.
- **Maintainability:** Medium. Adding a new phase means writing a new summary contract. But the contract format is reusable.
- **Future-proofing:** Better than Candidate 1 because the constraint is structural (agent output format) rather than behavioral (orchestrator self-restraint).
- **Incremental adoptability:** Good. Can be added one agent at a time.
- **Unattended:** Yes.

**Verdict:** Good complement to Candidate 1. Together, they cover both sides -- producer (bounded output) and consumer (no-read discipline). But they still cannot prevent context death on very large builds because the orchestrator still carries the plan text, agent spawn prompts, and in-context brainstorm/plan phases.

---

### Candidate 3: Hybrid Delegation (deepen-runner + swarm-runner + tail-runner)

**What it is:** Delegate the three heaviest phases to fresh-context agents. The orchestrator becomes a thin coordinator that runs lightweight phases inline and delegates heavy phases.

**Architecture (updated per spike result -- REDUCED DELEGATION):**
```
Orchestrator
  ├── Steps 1-5: brainstorm, plan (inline)
  ├── Step 6: spawn deepen-runner agent (summary back)
  ├── Steps 9w.5-9w.8: gates + ghost cleanup (inline, no-read discipline)
  ├── Steps 7w-10.5w: swarm planner, worker spawn, ownership gate (inline -- cannot delegate, no nested Agent tool)
  ├── Steps 11w-16w: spawn swarm-runner agent (assembly, verification, merge, cleanup -- summary back)
  └── Step 17w: spawn tail-runner agent (already exists)
```

**New agents:**
1. **deepen-runner** -- Reads the plan, spawns research agents, merges corrections, commits the deepened plan, returns a bounded summary (STATUS, plan path, change count).
2. **swarm-runner** -- Reads the assembly branch after worker spawn completes, handles assembly merge, runs smoke/contract checks, merges to main, cleans up worktrees. Returns a bounded Tier 1 decision line. (Originally proposed to also spawn workers, but the pre-plan spike confirmed sub-agents lack the Agent tool. Scope reduced to Steps 11w-16w.)

**Evaluation:**
- **Reliability:** High. Each heavy phase gets a fresh context window. The orchestrator's context never exceeds ~80-100K (inline phases + bounded summaries). This _structurally_ prevents context death for builds up to at least 30-40 agents.
- **Simplicity:** Medium-high. Two new agent files (~100-150 lines each). SKILL.md changes to spawn them instead of running inline (~30 lines changed). Total: ~300-350 new lines across 3 files.
- **Maintainability:** The three agent files (deepen-runner, swarm-runner, tail-runner) each own a distinct phase boundary. Changes to deepening logic go in deepen-runner. Changes to swarm logic go in swarm-runner. No cross-cutting concerns.
- **Future-proofing:** Good. If context windows grow (2M, 5M), these agents simply have more headroom. If builds grow (50+ agents), the swarm-runner can be further decomposed. The pattern scales.
- **Incremental adoptability:** Excellent. Stage 1: deepen-runner (saves ~90K). Stage 2: swarm-runner (saves ~200K). Stage 3: optimizations within each agent. Each stage is independently valuable.
- **Unattended:** Yes. The orchestrator spawns each agent and waits for the summary.

**Verdict:** This is the strongest candidate. It addresses the structural problem (heavy phases running in the orchestrator's context) rather than just the behavioral problem (orchestrator reading too much). The three-agent split matches natural phase boundaries and each agent is independently testable.

---

### Candidate 4: Automatic Context Budget Gate

**What it is:** Before each major phase boundary, estimate remaining context capacity. If under threshold, automatically delegate the next phase to a fresh-context agent instead of running it inline. This is an adaptive version of the Tier 1 checkpoint -- but instead of pausing and requiring human resume, it spawns a delegated agent.

**How it works:**
1. Before Steps 6, 10w, and 17w, calculate orchestration load using the existing heuristic (agent count * 1 + deepening * 2 + review * 1.5 + retries * 3).
2. If load > threshold, the next phase is automatically delegated to a fresh-context agent.
3. The agent reads state from PHASE_STATE.json (or BUILD_TRACKING.md), executes the phase, writes results to disk, returns a bounded summary.

**Evaluation:**
- **Reliability:** Medium. The heuristic has known false positives (Run 048) and potential false negatives. Context estimation is imprecise. The heuristic is calibrated against runs 047-050 but may not generalize.
- **Simplicity:** Medium. Requires the heuristic logic plus the delegation machinery (agent files). If you're going to build the delegation machinery anyway (Candidate 3), the heuristic becomes less valuable -- just always delegate.
- **Maintainability:** The heuristic needs ongoing calibration as build patterns change.
- **Future-proofing:** Poor for the heuristic itself (model changes invalidate calibration). Good for the delegation fallback.
- **Incremental adoptability:** Good if combined with Candidate 3's agents. Poor standalone (heuristic alone doesn't solve the problem).
- **Unattended:** Yes.

**Verdict:** The right question is: if we're building delegation agents anyway (Candidate 3), do we still need the heuristic? The answer is: only as a safety net. If Candidate 3 is implemented, the heuristic becomes a secondary check, not the primary defense. Ship Candidate 3 first; add the budget gate later only if delegation doesn't fully solve the problem.

---

### Candidate 5: Contract-First PHASE_STATE.json

**What it is:** Introduce a machine-readable state file that records the current phase, completed phases, artifact paths, and next action. Every phase reads and writes this file. The orchestrator's primary source of truth is the file, not conversation history.

**Schema (example):**
```json
{
  "run_id": "065",
  "current_phase": "swarm",
  "phases": {
    "brainstorm": { "status": "PASS", "artifact": "docs/brainstorms/..." },
    "plan": { "status": "PASS", "artifact": "docs/plans/..." },
    "deepen": { "status": "PASS", "artifact": "docs/plans/...", "changes": 3 },
    "gates": { "status": "PASS", "artifacts": ["docs/reports/065/..."] },
    "swarm": { "status": "IN_PROGRESS", "agents_spawned": 12, "agents_complete": 8 }
  },
  "next_action": "wait for remaining 4 agents"
}
```

**Evaluation:**
- **Reliability:** Does not reduce context on its own. It is a state management improvement, not a context reduction technique. The orchestrator still runs all phases inline and accumulates context.
- **Simplicity:** Medium. Every phase needs read/write logic for the JSON file. Risk of schema drift.
- **Maintainability:** JSON schema needs to be kept in sync with SKILL.md steps. Two sources of truth for "what phase are we in."
- **Future-proofing:** Good for resume and observability. Poor as a standalone context death solution.
- **Incremental adoptability:** Good. Can be added incrementally per phase.
- **Unattended:** Yes.

**Verdict:** Useful for observability and resume, but does not solve context death. Better as a complement to Candidate 3 (delegated agents read PHASE_STATE.json to know where they are) than as a standalone solution. However, BUILD_TRACKING.md already fills most of this role. Adding PHASE_STATE.json creates a second state file, which is a dual-source-of-truth risk. **Recommendation: extend BUILD_TRACKING.md with a machine-readable header instead of creating a new file.**

---

### Candidate 6: Two-Run Autopilot Split

**What it is:** Split the autopilot into two separate Claude Code sessions. Run A handles brainstorm, plan, deepening, and gates. Run B handles swarm, assembly, smoke, and tail. Run A writes PHASE_STATE.json; Run B reads it. A shell script or hook triggers Run B after Run A completes.

**Evaluation:**
- **Reliability:** High. Each run gets a full 1M context window. Context death is structurally impossible within each run.
- **Simplicity:** Low. Requires an external coordinator (shell script, cron, or hook) to launch Run B after Run A. The handoff contract between runs must be precise. Error handling for Run A failure must prevent Run B from launching.
- **Maintainability:** The split point is fragile. If a future change moves logic between planning and execution, the split contract needs updating.
- **Future-proofing:** Poor. If Claude Code adds native session chaining, this custom solution becomes tech debt.
- **Incremental adoptability:** Moderate. The split is binary -- you either have two runs or one.
- **Unattended:** Possible but requires external automation (shell script or cron). Not purely Claude Code-native.

**Verdict:** Solves the problem but at high complexity cost. If Candidate 3 (hybrid delegation) works, this is unnecessary. Reserve as a fallback for builds with 50+ agents where even delegated agents might hit limits.

---

### Candidate 7: External Agent SDK Orchestrator

**What it is:** Replace the Claude Code orchestrator with a Python/TypeScript script using the Anthropic Agent SDK. The script calls `query()` for each phase, each call creating a completely fresh session. The orchestrator lives outside any context window.

**Evaluation:**
- **Reliability:** Maximum. Context death is structurally impossible. Each phase gets 100% of the context window.
- **Simplicity:** Low. Requires a new codebase (the orchestrator script), a new dependency (Agent SDK), and a new execution model. The orchestrator must implement all the logic currently in SKILL.md (~835 lines) in Python/TypeScript.
- **Maintainability:** High ongoing cost. Changes to the pipeline require editing both the SDK script and any agent files. Testing requires running the full SDK flow.
- **Future-proofing:** Good for context death. Poor for Claude Code feature adoption -- new Claude Code features (hooks, skills, agents) might not be usable from the SDK.
- **Incremental adoptability:** Poor. This is a full rewrite of the orchestrator.
- **Unattended:** Yes, but requires the machine to stay running the script.

**Verdict:** Strongest context death guarantee, but highest migration cost. Not justified when Candidate 3 achieves 80-90% of the benefit at 20% of the cost. Consider only if Claude Code hits fundamental limits that can't be worked around with delegation.

---

### Candidate 8: Anthropic-Style Shell Harness Loop

**What it is:** A shell script loop that checks a contract file. While phases remain incomplete, it spawns a fresh Claude Code session. Each session reads the contract file, executes the next phase, and updates the file. Approximately 50 lines of bash.

```bash
while ! grep -q '"status": "complete"' PHASE_STATE.json; do
    claude -p "Read PHASE_STATE.json. Execute the next incomplete phase."
done
```

**Evaluation:**
- **Reliability:** High. Each session is fresh. Context death is structurally impossible.
- **Simplicity:** Medium. The bash script is simple (~50 lines), but the contract file (PHASE_STATE.json) must encode all inter-phase state precisely. Misalignment between what the session expects and what the contract provides causes subtle failures.
- **Maintainability:** Medium. The bash script is straightforward, but debugging failures requires understanding the session's interpretation of the contract file.
- **Future-proofing:** Fragile. Depends on `claude -p` CLI interface. If the CLI changes invocation patterns, the script breaks.
- **Incremental adoptability:** Moderate. The contract file is the hard part, not the loop.
- **Unattended:** Yes, as long as the script runs unattended (nohup, tmux, etc.).

**Verdict:** Simpler than Candidate 7 (Agent SDK) but shares the core trade-off: the orchestrator is outside Claude Code, losing access to skills, hooks, and agent features. Also introduces a second execution model (bash harness + Claude sessions) that is harder to debug than a single Claude Code session with delegated agents. Candidate 3 is preferable because it stays within the Claude Code ecosystem.

---

### Candidate 9: Stop Hook + Delegated Phase Agents + /goal

**What it is:** Three mechanisms combined:
1. A stop hook reads PHASE_STATE.json after every turn and drives phase transitions deterministically.
2. Phase agents handle heavy work in fresh context (same as Candidate 3).
3. `/goal` sets the overall completion condition ("self-audit passes, HANDOFF updated").

**Evaluation:**
- **Reliability:** High if all three mechanisms work together. The stop hook prevents drift, phase agents prevent context death, and `/goal` ensures completion.
- **Simplicity:** Low. Three independent mechanisms that must be coordinated. The stop hook is a new pattern not yet used in this repo. `/goal` is an experimental Claude Code feature.
- **Maintainability:** High. The stop hook, PHASE_STATE.json, agent files, and `/goal` condition all need to stay synchronized. Four sources of truth.
- **Future-proofing:** Uncertain. Both stop hooks and `/goal` are relatively new Claude Code features. Their behavior may change.
- **Incremental adoptability:** Moderate. The phase agents can ship independently (Candidate 3), but the hook and `/goal` are tightly coupled.
- **Unattended:** Yes.

**Verdict:** Over-engineered for the current problem. The stop hook and `/goal` are interesting but introduce coordination complexity that isn't needed if Candidate 3 works. The value of a stop hook is deterministic phase transitions -- but the orchestrator already transitions between phases deterministically via the numbered steps in SKILL.md. Adding a hook is a second control mechanism on top of an existing one. Reserve for future work if Candidate 3 proves insufficient.

---

### Candidate 10: Full Phase Delegation (7 Agents)

**What it is:** Every phase gets its own agent. The orchestrator is a pure dispatcher.

**Agents:** brainstorm-runner, plan-runner, deepen-runner, gate-runner, swarm-runner, tail-runner, learnings-runner.

**Evaluation:**
- **Reliability:** Maximum within Claude Code. Each phase gets a fresh context.
- **Simplicity:** Low. 7 agent files, each ~100-150 lines. The orchestrator SKILL.md shrinks but the total system complexity grows.
- **Maintainability:** High. 7 agent files to keep synchronized with each other and with the pipeline contract.
- **Future-proofing:** Good structurally. More agents = more flexibility. But 7 agents is maintenance overhead.
- **Incremental adoptability:** Yes -- add agents one at a time.
- **Unattended:** Yes.

**Verdict:** Candidate 3 (3 agents) solves 80% of the problem. The remaining 20% (brainstorm, plan, gates) runs within ~70K of context -- well within the 1M budget. Adding 4 more agents for phases that don't cause context death is YAGNI. The 80/20 point is 3 agents (deepen, swarm, tail).

---

### Candidate 11: Native Compaction or /goal-Only Resilience

**What it is:** Rely on Claude Code's native `/compact` command (automatic context compaction) or the `/goal` feature to survive context death without architectural changes.

**Evaluation:**
- **Reliability:** Low. Compaction is lossy (~12% from prior experience). Skill descriptions, instruction nuances, and inter-phase state can vanish. `/goal` is experimental and its behavior during context compaction is undefined.
- **Simplicity:** Maximum. Zero code changes.
- **Maintainability:** Zero added maintenance.
- **Future-proofing:** Good if Claude Code improves compaction fidelity. Bad if it doesn't.
- **Incremental adoptability:** N/A -- it's a zero-change option.
- **Unattended:** Uncertain. Compaction may drop critical instructions (e.g., "DO NOT skip learnings propagation") that cause the orchestrator to produce incomplete artifacts.

**Verdict:** Not viable as a primary solution. Compaction has already demonstrated data loss (skill descriptions vanishing post-compact). The autopilot's correctness depends on following detailed step instructions -- compaction that drops steps produces silent failures. However, compaction is a useful _safety net_ behind Candidate 3's delegation. If a delegated agent's context gets tight, compaction gives it a second chance rather than immediate death.

---

## Comparative Ranking

| Rank | Candidate | Reliability | Simplicity | Maintain. | Future-proof | Incremental | Unattended |
|------|-----------|-------------|------------|-----------|-------------|-------------|------------|
| 1 | **3: Hybrid Delegation** | High | Medium | Low | Good | Excellent | Yes |
| 2 | **1+2: No-Read + Bounded Summaries** | Medium | High | Low | Medium | Excellent | Yes |
| 3 | **8: Shell Harness Loop** | High | Medium | Medium | Fragile | Moderate | Yes |
| 4 | **7: Agent SDK Orchestrator** | Maximum | Low | High | Good | Poor | Yes |
| 5 | **6: Two-Run Split** | High | Low | Medium | Poor | Moderate | Possible |
| 6 | **4: Auto Context Budget Gate** | Medium | Medium | Medium | Poor | Good | Yes |
| 7 | **9: Stop Hook + Agents + /goal** | High | Low | High | Uncertain | Moderate | Yes |
| 8 | **10: Full Phase Delegation** | Maximum | Low | High | Good | Yes | Yes |
| 9 | **5: PHASE_STATE.json** | Low (alone) | Medium | Medium | Good | Good | Yes |
| 10 | **11: Compaction / /goal** | Low | Maximum | Zero | Uncertain | N/A | Uncertain |

## Recommended MVP Solution

**Three layers, shipped in four stages (including a spike).**

### Layer 1a: No-Read Orchestrator Discipline (SKILL.md Only)

The minimal change. Edit SKILL.md instructions only -- no agent file changes.

**What changes:**
1. Standardize all phase reports: no YAML frontmatter, STATUS on line 1,
   no markdown formatting around the STATUS value.
2. After every phase that writes a report, add SKILL.md instructions:
   "Read the report file with `limit: 1`. If STATUS: PASS, proceed. If
   STATUS: FAIL, read the full report."
3. After deepening completes (Step 6.5), the orchestrator reads only the
   merged plan file -- not the raw deepening outputs. (Already partially
   implemented.)

**What this does NOT change:** No agent files are modified. The agents
still return whatever they return. The discipline is entirely on the
orchestrator (consumer side).

**How to measure:** Compare orchestrator proxy metric (cumulative Read/Agent
output character count) at Step 17w against the baseline run. Target: measurable
reduction vs. baseline.

**Why ship this first:** It validates whether the orchestrator can follow
"read only 1 line" instructions reliably. If it can, this alone may be
sufficient for 10-12 agent builds. If it can't (orchestrator reads full
reports anyway), we know SKILL.md discipline is unreliable and Layer 1b/2
become mandatory.

### Layer 1b: Bounded Agent Summary Contracts (Agent File Edits)

Separate from Layer 1a because it modifies agent files, not just SKILL.md.
Ship after Layer 1a is validated or after Layer 1a proves insufficient.

**What changes:**
1. Add an output contract section to each agent that returns results to the
   orchestrator: spec-consistency-checker, spec-completeness-checker,
   smoke-test-runner, test-suite-runner, spec-contract-checker.
2. Each agent's output contract specifies: write a full report to disk,
   write Tier 2 detail fields to BUILD_TRACKING.md frontmatter, then
   return a Tier 1 decision line (under 200 characters) as the agent's
   return value. See Candidate 2 for the full two-tier contract.
3. The orchestrator reads the agent's Tier 1 decision line and never reads
   the report file on PASS. On FAIL, the orchestrator checks `blocking`
   and `retry` from the decision line to decide whether to retry, continue
   with failure noted, or abort. Reads the full report only if recovery
   requires understanding the failure details. Reads Tier 2 fields from
   BUILD_TRACKING.md frontmatter if needed.

**How this differs from Layer 1a:** Layer 1a constrains the consumer
(orchestrator reads less). Layer 1b constrains the producer (agents return
less). Layer 1b is structurally stronger because the orchestrator cannot
accidentally read what was never sent to it.

**Dependency:** Layer 1b can ship independently of Layer 1a. But they
complement each other -- 1a handles phases that don't use agents (inline
gate checks), 1b handles phases that do.

### Layer 2: Hybrid Delegation (Ship After Spike)

Add `deepen-runner` and `swarm-runner` agents. The pre-plan spike confirmed
that sub-agents lack the Agent tool, so **swarm-runner owns only Steps
11w-16w** (assembly, verification, merge, cleanup). The orchestrator keeps
worker spawn (Steps 7w-10.5w). See completed spike report at
`docs/reports/spike-nested-worktree-delegation.md`.

**What changes:**
1. Create `.claude/agents/deepen-runner.md` (~100-120 lines):
   - Reads the plan file path from orchestrator prompt
   - Spawns research sub-agents (existing deepen-plan behavior)
   - Merges corrections into plan in-place
   - Commits the deepened plan
   - Returns bounded summary: STATUS, plan path, change count, deepening-applied.md path

2. Create `.claude/agents/swarm-runner.md` (~120-150 lines):
   - Reads the assembly branch name and plan path from orchestrator prompt
   - Handles assembly merge (Step 11w)
   - Runs circuit breaker, smoke test, test suite (Steps 12w-14w)
   - Merges assembly to main (Step 15w)
   - Cleans up worktrees (Step 16w)
   - Returns Tier 1 decision line: STATUS, blocking, retry, report, next step
   - Writes Tier 2 detail fields (merge_status, cleanup_status, etc.) to
     BUILD_TRACKING.md frontmatter before returning
   - NOTE: Does NOT spawn workers or run swarm planner (spike confirmed
     sub-agents lack Agent tool). Orchestrator handles Steps 7w-10.5w.

3. Modify SKILL.md (~40 lines changed):
   - Step 6 becomes: spawn deepen-runner, wait for summary
   - Steps 11w-16w become: spawn swarm-runner, wait for summary
   - Steps 7w-10.5w remain inline (orchestrator keeps worker spawn)
   - Remove inline deepening and assembly/verification logic from SKILL.md

**Estimated orchestrator context after Layer 2 (unmeasured -- see measurement plan):**
The orchestrator's conversation contains SKILL.md, inline phases (brainstorm,
plan, gates), worker spawn prompts (Steps 7w-10.5w, still inline), and
bounded Tier 1 decision lines from 3 delegated agents. Worker spawn remains
in-context because sub-agents lack the Agent tool (spike confirmed).
Target: proxy metric at Step 17w under 60% of baseline (fallback), 30%
stretch. The 30% target was designed for full delegation; reduced scope
means higher residual context from inline worker spawn.

**Why this works:** The orchestrator's job becomes "coordinate phases and
check summaries." It never reads full reports, never runs deepening research,
never manages worktree merges. Each heavy phase gets a fresh 1M context
window via its own agent.

### Solo-Build Strategy and Maintenance Drift Control (Layer 2)

**Decision: Solo builds remain inline. Swarm agent files are the single
source of truth for swarm logic. No duplication.**

When deepen-runner and swarm-runner are created, the swarm-specific steps
(Steps 11w-16w for swarm-runner, Step 6 for deepen-runner) exist in two architecturally different
forms:
- **Swarm path:** Agent files own the logic. SKILL.md says only "spawn
  deepen-runner" / "spawn swarm-runner" / "spawn tail-runner."
- **Solo path:** SKILL.md retains a simpler inline path (Step 7s: Work).
  Solo deepening still runs inline because solo builds don't hit context
  limits (no swarm spawn, no assembly, no 10+ agents).

**Why this is NOT duplication:** The solo and swarm paths share the
compound engineering loop but have different step implementations. Solo
Step 7s invokes `/workflows:work` -- it does not duplicate Steps 11w-16w.
Solo deepening (Step 6) is a single skill invocation, not 4-12 research
agents. The logic that moves to agent files (assembly merge, contract
checks, smoke/test, merge to main, cleanup) has no solo equivalent.
Worker spawn and swarm planner remain in the orchestrator (both paths).

**Drift control mechanism:**
1. SKILL.md's swarm path becomes three spawn-and-check blocks (~10 lines
   each). There is no swarm logic left in SKILL.md to drift from.
2. The solo path's shared steps (brainstorm, plan, gates, tail) remain in
   SKILL.md. These are also used by the swarm path's orchestrator -- no
   drift because the orchestrator runs them inline in both cases.
3. The only shared logic between the solo tail (inline in SKILL.md) and
   the swarm tail (tail-runner.md) continues using the existing
   TAIL_SYNC_POINT pattern. This works because the tail section is ~30
   lines -- small enough for human-enforced sync.
4. **Invariant:** No same-path implementation logic exists in both an agent
   file and SKILL.md inline. Steps with the same number (e.g., Step 6)
   may appear in both, but the solo version (single skill invocation) and
   the swarm version (agent with sub-agent research) are architecturally
   different implementations, not duplicated logic. The invariant violation
   is: identical merge/check/cleanup code copy-pasted between files.

## Pre-Plan Spike: Nested Worktree Delegation (COMPLETED)

**Status:** Completed 2026-06-03. Report: `docs/reports/spike-nested-worktree-delegation.md`.

**Verdict: REDUCED DELEGATION.**

### Spike Result Summary

Sub-agents do NOT have the Agent tool. This is a platform limitation, not
a configuration issue. Three independent tests confirmed it:

1. General-purpose sub-agent (ToolSearch-based): Agent tool not available.
2. General-purpose sub-agent (direct check, no ToolSearch): Agent tool not available.
3. Typed sub-agent (tail-runner type with `tools: ... Agent` in definition):
   Agent tool not available.

The `tools` field in agent definition frontmatter does not grant tools that
the platform excludes from sub-agents. The Agent tool is available only to
the top-level orchestrator session.

### Architecture Impact

| Finding | Design Decision |
|---------|----------------|
| Nested agent spawning impossible | swarm-runner owns Steps 11w-16w only (assembly + verification). Orchestrator keeps worker spawn (Steps 7w-10.5w). |
| EnterWorktree/ExitWorktree work (session-level only) | Not useful for parallel workers (single worktree per session). |
| SendMessage doesn't validate recipients | Team-based coordination unreliable for missing agents. |

### Latent Bug Discovered

The tail-runner (`.claude/agents/tail-runner.md`) Step 8 instructs the agent
to spawn the self-audit-reviewer agent. But sub-agents don't have the Agent
tool. This step either fails silently, uses a different mechanism (Skill
tool), or worked in prior runs due to different session configuration. This
must be investigated separately.

### What This Means for the Plan

- **Orchestrator keeps:** Steps 7w-10.5w (swarm planner, worker spawn, ownership gate)
- **swarm-runner owns:** Steps 11w-16w (assembly merge, contract check, smoke test, test suite, merge to main, cleanup)
- **Estimated savings:** Assembly/verification delegation still removes merge
  logs, smoke/test output, and cleanup operations from orchestrator context.

### Original Spike Tests (for reference)

| # | Test | What it validates | PASS criterion |
|---|------|-------------------|----------------|
| 1 | **Basic nested worktree spawn** | Parent agent spawns child with `isolation: "worktree"`, child writes a file and commits | Child's commit exists on the worktree branch |
| 2 | **Multiple parallel nested workers** | Parent spawns 3 child agents simultaneously with `isolation: "worktree"` and `run_in_background: true` | All 3 complete, each in its own worktree, no cross-contamination |
| 3 | **Child crash / error** | Child agent deliberately fails (e.g., writes invalid code, raises an error) | Parent receives a result (even if error), does not hang |
| 4 | **Child timeout** | Child agent sleeps beyond parent's expected wait time | Parent detects timeout and continues (does not hang indefinitely) |
| 5 | **Worktree cleanup on failure** | After child crash, verify worktree is cleaned up or can be cleaned up by parent | `git worktree list` shows no orphaned worktrees, or parent can `git worktree remove` them |
| 6 | **bypassPermissions propagation** | Parent spawned with `mode: "bypassPermissions"`; child also needs bypass to run git operations | Child completes git operations without permission prompts |
| 7 | **Bounded parent return** | Parent agent returns a summary under 500 characters despite children producing large outputs | Parent return value character count < 500 |

**Possible outcomes and architecture impact:**

| Outcome | Impact on swarm-runner design |
|---------|-------------------------------|
| **All 7 tests pass** | swarm-runner owns Steps 7w-16w as designed. Full worker delegation. |
| **Tests 1-2 fail** (nested worktree spawn rejected entirely) | swarm-runner scope shrinks to assembly + verification (Steps 11w-16w only). Orchestrator keeps worker spawn (Steps 7w-10.5w). Context savings reduced but still meaningful from assembly/verification delegation. |
| **Tests 1-2 pass but 3-5 fail** (spawn works but error handling is broken) | swarm-runner can own Steps 7w-16w but must include explicit error handling: catch child failures, clean up worktrees manually via Bash, report partial results. Additional complexity in agent file. |
| **Test 6 fails** (permissions don't propagate) | swarm-runner cannot spawn workers in autopilot mode. Same fallback as "tests 1-2 fail." |

**Branch-only workers (child runs without worktree isolation) is NOT a viable
outcome.** If `isolation: "worktree"` is ignored and workers share the repo,
concurrent writes cause merge conflicts and data corruption. The only two
viable architectures are: workers in worktrees (full delegation) or workers
spawned by the orchestrator (reduced delegation). There is no middle ground.

**Deliverable:** `docs/reports/spike-nested-worktree-delegation.md` with:
- Test results table (7 rows, PASS/FAIL per test, error output if FAIL)
- Architecture recommendation (full 7w-16w or reduced 11w-16w)
- Any constraints discovered (e.g., max concurrent nested agents)

**Estimated effort:** 1 session, ~45 minutes.

## Staged Roadmap

The pre-plan spike is complete (REDUCED DELEGATION). All stages below
are implementation stages. swarm-runner scope is fixed at Steps 11w-16w.

### Stage 1a: No-Read Discipline (1 session, SKILL.md only)
- Standardize all phase reports: no frontmatter, STATUS on line 1
- Add `limit: 1` Read instructions after each phase in SKILL.md
- Run one baseline measurement build (unmodified autopilot) to get proxy
  metric values at each phase boundary
- Run one validation build with the no-read instructions applied
- **Success criterion:** Proxy metric (cumulative Read/Agent output character
  count) at Step 17w is measurably lower than baseline. If reduction is less
  than 10%, Layer 1a is insufficient and Layer 1b/2 are mandatory.
- **Falsifier:** If the orchestrator reads full reports despite `limit: 1`
  instructions (visible in tool call audit), no-read discipline is unreliable.

### Stage 1b: Bounded Agent Summary Contracts (1 session, agent files)
- Add output contract sections to 5-7 agent files
- Validate that each agent emits Tier 1 decision line AND writes Tier 2
  fields to BUILD_TRACKING.md frontmatter AND writes full report to disk
- **Success criterion:** Proxy metric at Step 17w is measurably lower than
  Stage 1a alone. Agent Tier 1 decision lines are under 200 characters each.
  Tier 2 fields present in BUILD_TRACKING.md frontmatter after each phase.
- **Falsifier:** If agents emit full reports in their return value despite
  the output contract, bounded summaries require agent-level enforcement
  (not instruction-based).

### Stage 2: deepen-runner Agent (1 session)
- Create `.claude/agents/deepen-runner.md`
- Modify SKILL.md Step 6 to spawn it
- Validate that deepened plan is identical to inline deepening result
  (diff the plan file before/after to verify no content loss)
- **Success criterion:** Orchestrator proxy metric at Step 6 boundary is
  under 5% of baseline (vs. ~30% with inline deepening). The deepened plan
  commits cleanly and passes gate checks.
- **Falsifier:** If deepen-runner fails to produce a valid deepened plan on
  2 consecutive attempts, the agent's logic needs debugging before Stage 3.

### Stage 3: swarm-runner Agent (1-2 sessions)
- Create `.claude/agents/swarm-runner.md` with scope: Steps 11w-16w only
  (assembly merge, contract check, smoke test, test suite, merge to main,
  cleanup). Spike confirmed nested spawn is impossible -- orchestrator
  keeps worker spawn (Steps 7w-10.5w).
- Modify SKILL.md to spawn it after gates pass
- Validate on a 12+ agent build
- **Success criterion:** Orchestrator proxy metric at Step 17w shows
  measurable reduction vs. baseline. Target: under 30% of baseline.
  If the metric improves materially (e.g., 40-50% of baseline) but does
  not hit 30%, the stage still ships -- the 30% target assumed full
  worker delegation which the spike ruled out. The plan must define
  "materially improved" as a fallback threshold (e.g., under 60%).
  All 5 mandatory artifacts produced. Pipeline ends with
  `<promise>DONE</promise>` without human intervention.
- **Falsifier:** If the build requires manual intervention or produces
  incomplete artifacts, debug the agent before declaring success.

### Stage 4: Observability and Safety Nets (Optional, Future)
- Extend BUILD_TRACKING.md with machine-readable phase status header
  (see "Orchestration State: BUILD_TRACKING.md, Not PHASE_STATE.json" section)
- Add context budget gate as secondary safety net (Candidate 4), triggered
  only when proxy metric exceeds 60% of baseline at any phase boundary
- Consider auto-compaction before heavy phases

## Orchestration State: BUILD_TRACKING.md, Not PHASE_STATE.json

**Decision:** Orchestration state lives in BUILD_TRACKING.md. No separate
PHASE_STATE.json file. This avoids dual-source-of-truth drift between two
state files.

**How:** Add a YAML frontmatter block to BUILD_TRACKING.md that delegated
agents can parse deterministically. The existing markdown body continues to
serve as the human-readable log.

**Concrete format:**
```yaml
---
run_id: "065"
phase: "swarm"
status: "IN_PROGRESS"
plan_path: "docs/plans/2026-06-03-context-death-plan.md"
brainstorm_path: "docs/brainstorms/2026-06-03-context-death-brainstorm.md"
reports_dir: "docs/reports/065/"
branch: "master"
date: "2026-06-03"
context_proxy_chars: 142000
manual_resume: false
final_status: null
deepen:
  status: "PASS"
  plan_committed: true
  changes: 3
  report: "docs/reports/065/deepening-applied.md"
  summary_path: "docs/reports/065/deepen-summary.md"
gates:
  consistency: "PASS"
  completeness: "PASS"
  verification: "CLEARED"
  consistency_report: "docs/reports/065/spec-consistency-check.md"
  completeness_report: "docs/reports/065/spec-completeness-check.md"
  verification_report: "docs/reports/065/gate-verification.md"
swarm:
  status: "IN_PROGRESS"
  agents_spawned: 12
  agents_complete: 8
  assembly_branch: "swarm-065-assembly"
  # Tier 2 fields (written by swarm-runner before returning)
  counts: { agents: 12, findings: 0, fixes: 0 }
  merge_status: null
  preserved_branches: []
  cleanup_status: null
  failure_report_path: null
  artifact_paths: []
  # Per-phase report paths (write-once)
  contract_check: "docs/reports/065/contract-check.md"
  smoke_test: "docs/reports/065/smoke-test.md"
  test_results: "docs/reports/065/test-results.md"
  ownership_gate: "docs/reports/065/ownership-gate.md"
tail:
  status: "NOT_STARTED"
  # Tier 2 fields (written by tail-runner before returning)
  counts: { p1: 0, p2: 0, fix_commits: 0 }
  failure_report_path: null
  artifact_paths: []
  review_summary: null
  solution_doc: null
  self_audit: null
---
```

**Field definitions for new fields:**
- `context_proxy_chars` -- cumulative character count of all Read and Agent
  tool outputs in the orchestrator's conversation. Updated after each phase
  boundary. Used to measure context savings vs. baseline.
- `manual_resume` -- false during normal execution. Set to true if the run
  was resumed via `/tail-resume` or manual intervention. Tells the self-audit
  agent that the run was not fully unattended.
- `final_status` -- null during execution. Set to `"DONE"` or
  `"FAIL -- <reason>"` when the pipeline completes. Corresponds to the
  `<promise>` tag emitted by the orchestrator.
- `summary_path` (per phase) -- path to the bounded summary file, if the
  phase wrote one separately from the full report. null if the summary was
  returned inline by the agent.
- Per-phase report paths -- explicit paths to every report file. Eliminates
  glob-based discovery for downstream consumers (tail-runner, self-audit).

**Frontmatter edit frequency (fragility mitigation):**

Most frontmatter fields are **write-once** (set when the phase completes,
never edited again). Only 3 fields are **frequently edited**:

| Field | Edit Frequency | Mitigation |
|-------|---------------|------------|
| `phase` | Once per phase boundary (~6 times) | Top-level field, easy to locate |
| `status` | Once per phase boundary (~6 times) | Top-level field, easy to locate |
| `context_proxy_chars` | Once per phase boundary (~6 times) | Top-level field, easy to locate |

All per-phase sub-fields (`deepen.status`, `gates.consistency`, etc.) and
all report paths are write-once. The Tier 2 detail fields (counts,
merge_status, preserved_branches, etc.) are written by the phase agent
once and never modified.

**Rule:** Orchestrator edits only the 3 frequently-edited top-level fields.
Phase agents write their own sub-section once. This minimizes the number
of Edit tool operations on the frontmatter, reducing malformed-YAML risk.

**Rules:**
1. The orchestrator writes this frontmatter at Step 1.5 (BUILD_TRACKING creation)
   and updates it after each phase boundary.
2. Delegated agents (deepen-runner, swarm-runner, tail-runner) read the
   frontmatter to discover paths and prior phase results. They update their
   own section before returning.
3. The `phase` and `status` fields are the machine-readable equivalent of
   "where are we." No grep-based discovery needed.
4. The existing markdown body (AGENT_STATUS table, FAILURES, RUN_METRICS)
   continues to be filled as before. Frontmatter is additive, not a replacement.
5. If the orchestrator or agent crashes, the frontmatter records the last
   known good state. A manual resume session reads frontmatter to orient.

**Frontmatter validation (MANDATORY after every update):**

After every Edit to BUILD_TRACKING.md that modifies the YAML frontmatter,
the orchestrator or agent must validate the frontmatter is parseable:

1. Read BUILD_TRACKING.md with `limit: 30` (enough for the full frontmatter
   block).
2. Verify the file starts with `---` on line 1.
3. Verify a closing `---` exists within the first 30 lines.
4. Verify the `run_id`, `phase`, and `status` fields are present between
   the delimiters.

**On validation failure:**
- If the closing `---` is missing or the required fields are absent, the
  Edit introduced malformed YAML. This is a **blocking error**.
- The orchestrator must re-read the full BUILD_TRACKING.md, identify the
  malformed section, and rewrite the frontmatter using the Write tool
  (overwrite the entire file with corrected content).
- If the rewrite also fails validation, FAIL the run with:
  `"BUILD_TRACKING FRONTMATTER CORRUPT: manual repair required."`
- Agents must not proceed to the next phase with corrupt frontmatter,
  because downstream agents parse it to discover paths and phase status.

**Why not a separate JSON file:** BUILD_TRACKING.md is already the canonical
state file that every agent reads. Adding a second file (PHASE_STATE.json)
that must agree with BUILD_TRACKING.md is a synchronization burden with no
added value. YAML frontmatter in the existing file serves the same purpose.

## Risks and Mitigations

### Risk 1: Delegated agents can't invoke skills
**What could go wrong:** deepen-runner or swarm-runner may need to invoke skills (e.g., deepen-plan, swarm-planner). Skill invocation from inside a sub-agent was untested before Run 064, and tail-runner showed it works -- but it's not guaranteed for all skills.
**Mitigation:** The deepen-runner and swarm-runner should inline the logic rather than invoking skills. This avoids the skill-from-agent dependency entirely. The tail-runner already demonstrates this pattern -- it invokes skills successfully, but could inline if needed.

### Risk 2: swarm-runner has reduced scope (RESOLVED)
**What happened:** The pre-plan spike confirmed that sub-agents do not have the Agent tool. Nested worker spawning is impossible.
**Resolution:** swarm-runner scope is fixed at Steps 11w-16w (assembly + verification). The orchestrator keeps worker spawn (Steps 7w-10.5w). This is less context savings than full delegation but still meaningful. See spike report: `docs/reports/spike-nested-worktree-delegation.md`.

### Risk 3: No-read discipline breaks on FAIL paths
**What could go wrong:** When a phase fails, the orchestrator MUST read the full report to understand the failure and decide on recovery. The "no-read on PASS" discipline means the FAIL path still accumulates context. If a build has multiple FAIL/retry cycles, context grows despite the discipline.
**Mitigation:** Candidate 4 (context budget gate) as a safety net. After N retries, if estimated load exceeds threshold, delegate the remaining recovery to a fresh-context agent. Implement this only if real builds show FAIL-path context accumulation is a problem.

### Risk 4: Bounded summaries are too small for debugging
**What could go wrong:** When a phase produces a 2K summary, the orchestrator has enough information to proceed but not enough to debug if something goes wrong later. A human reviewing the run would need to read the full reports on disk.
**Mitigation:** This is acceptable. The full reports are always on disk. The orchestrator is not the debugging interface -- the human reviews disk artifacts. The summary is for orchestration, not diagnosis.

## What Must Not Change

1. **Required artifacts.** BUILD_TRACKING, solution doc, learnings, HANDOFF, self-audit. All 5 must be produced by every run.
2. **Compound engineering phases.** Brainstorm, plan, work, review, compound, learnings. Order and content preserved.
3. **Swarm worktree isolation.** Worker agents run in isolated worktrees.
4. **Tail delegation.** tail-runner continues to own review through self-audit.
5. **Agent pitfalls injection.** Every agent brief includes failure class pitfalls.
6. **Gate verification.** Pre-swarm gates (consistency + completeness) must pass before swarm launch.
7. **Ghost file cleanup.** Step 9w.8 continues to catch prior-build artifacts.
8. **Incremental BUILD_TRACKING.** Agent status rows written after each merge, not reconstructed at end.

## How We Will Know It Worked

### Hard Success Gates (All Must Pass)

These are machine-verifiable. Any failure means the stage has not shipped.

1. **Unattended completion:** Pipeline ends with `<promise>DONE</promise>`.
   No `PAUSED_FOR_CONTEXT`, no manual resume, no human interaction during
   the run. Verified by: BUILD_TRACKING.md frontmatter contains
   `manual_resume: false` AND `final_status: "DONE"`. These are stronger
   proofs than absence of CHECKPOINT.md, which could be missing for other
   reasons.

2. **Context reduction (measured):** Orchestrator proxy metric at Step 17w
   shows measurable reduction vs. baseline (baseline = unmodified autopilot
   on same-size build). Target: under 30% of baseline. Fallback: under
   60% of baseline (accounts for reduced swarm-runner scope post-spike).
   Measured by: cumulative character count of Read and Agent tool outputs
   in orchestrator conversation, recorded in BUILD_TRACKING.md frontmatter
   as `context_proxy_chars`.

3. **Artifact completeness:** All 5 mandatory artifacts exist and are
   non-empty after the run:
   - `BUILD_TRACKING.md` with non-empty AGENT_STATUS, FAILURES, RUN_METRICS
   - `docs/solutions/YYYY-MM-DD-*.md` (solution doc)
   - `docs/reports/<run-id>/self-audit.md` (self-audit report)
   - `HANDOFF.md` with today's date
   - `~/.claude/docs/agent-pitfalls.md` Update Log with today's entry
   Verified by: existing `/verify-self-audit` gate (9 checks) + learnings
   verification gate (4 checks). These gates already exist and are unchanged.

4. **No new gate failures:** Pre-swarm gates (consistency, completeness,
   verification) pass at the same rate as baseline. Verified by:
   `docs/reports/<run-id>/gate-verification.md` contains `STATUS: CLEARED`.

5. **Bounded summary compliance:** Every delegated agent's Tier 1 decision
   line is under 200 characters. Tier 2 detail fields are written to
   BUILD_TRACKING.md frontmatter, not returned inline. Verified by:
   agent return values contain only the pipe-delimited decision line.
   (Manual check for Stage 1; automate in Stage 4 if needed.)

### Stretch Goal
- A 20-agent swarm build completes fully unattended with all 5 hard gates
  passing. This validates that the architecture scales beyond the 12-agent
  builds used for initial validation.

### Regression Gates (Must Not Regress)

These protect existing functionality from being broken by the changes:

1. **Solo build parity:** A solo build (swarm: false) completes with all 5
   mandatory artifacts. Solo builds remain inline (no delegated agents) and
   must not be broken by changes to SKILL.md's swarm path. Verified by:
   one solo build run after each stage ships. The no-duplication invariant
   (no same-path implementation logic in both an agent file and SKILL.md)
   must hold.

2. **Self-audit quality:** Self-audit report Run Quality Grade is B or above
   on all 6 dimensions. Verified by: existing `/verify-self-audit` gate.

3. **Swarm worktree isolation:** Worker agents produce commits only in their
   assigned worktrees. Verified by: existing ownership gate
   (`docs/reports/<run-id>/ownership-gate.md` contains `STATUS: PASS`).

4. **Tail artifact consistency:** Solution doc's review findings match the
   review report's findings. Verified by: existing self-audit source
   reconciliation check (Gate 5 of `/verify-self-audit`).

## Why Not an External Orchestrator?

The Codex handoff document shortlisted two external orchestrator options: Agent SDK (Candidate 7) and Shell Harness (Candidate 8). Both structurally eliminate context death. Here is why they are not the recommended MVP:

1. **Migration cost.** The autopilot SKILL.md is 835 lines of battle-tested pipeline logic with 20+ edge case handlers, 5 mandatory gates, and 3 retry mechanisms. Rewriting this in Python/TypeScript or encoding it in a PHASE_STATE.json contract for a shell loop is a multi-session project with high defect risk.

2. **Feature loss.** Claude Code skills, hooks, and agents are designed to work together within a Claude Code session. An external orchestrator loses access to skill invocation, hook-driven validation, and the Agent tool's isolation features. These would need to be reimplemented.

3. **The problem is smaller than it looks.** The orchestrator doesn't need a full 1M context. It needs ~80-100K. The remaining ~900K is used by phases that already run in separate agents. The problem is that 3 heavy phases (deepening, swarm, tail) run in the orchestrator's context instead of their own. Moving them to their own agents is a targeted fix, not a full rewrite.

4. **Reversibility.** If the delegation approach fails, we revert 3 agent files and ~40 SKILL.md lines. If the external orchestrator fails, we're stuck with a half-migrated system that can't run in either mode.

**When external orchestration makes sense:** If builds grow to 50+ agents with 10+ retry cycles, and even delegated agents can't handle the swarm phase in a single context, then an external orchestrator becomes necessary. But we are 3x below that threshold today.

## Feed-Forward

- **Hardest decision:** Whether to recommend hybrid delegation (Candidate 3) or start with no-read discipline alone (Candidates 1+2). No-read is simpler but unreliable -- it depends on instruction-following fidelity. Delegation is structural but requires new agent files. Chose delegation as the _target_ architecture, no-read as the _first stage_ to validate the principle cheaply, and a mandatory pre-plan spike to test the riskiest assumption (nested worktree delegation) before committing to swarm-runner's scope.

- **Rejected alternatives:**
  - PHASE_STATE.json as separate file (dual-source-of-truth risk; use BUILD_TRACKING.md YAML frontmatter instead)
  - Full phase delegation / 7 agents (YAGNI -- 3 agents solve 80% of the problem)
  - Shell harness / Agent SDK (high migration cost, feature loss, problem is smaller than it looks)
  - Stop hook + /goal (too many moving parts, experimental features)
  - Native compaction as primary defense (lossy, drops instructions)
  - Two-run split (external coordination, fragile split point)
  - Confident token estimates as success thresholds (unmeasurable; replaced with proxy metric relative to baseline)
  - Branch-only workers without worktree isolation (concurrent writes cause merge conflicts and data corruption; no safe middle ground between worktree isolation and orchestrator-managed spawning)
  - Solo builds using delegated agents (adds agent overhead for builds that don't hit context limits; solo inline path is simpler and the code paths are architecturally different, not duplicated)

- **Least confident about:** Two things, in priority order:
  1. **BUILD_TRACKING YAML frontmatter reliability** -- agents editing YAML frontmatter in a markdown file risk malformed output (missing closing `---`, bad indentation, truncated fields). The validation-after-every-update rule and write-once field design mitigate this, but the recovery path (full-file rewrite) is expensive if it fires frequently.
  2. **Reduced swarm-runner context savings** -- with the spike confirming REDUCED DELEGATION, swarm-runner owns only Steps 11w-16w. The orchestrator still carries Steps 7w-10.5w (worker spawn) in-context. Whether the reduced savings are sufficient to prevent context death on 20+ agent builds is unproven. (Nested worktree delegation is no longer uncertain -- the spike resolved it as impossible.)
