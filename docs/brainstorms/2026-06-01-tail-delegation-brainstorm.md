---
title: "Tier 2 Tail Delegation for Autopilot Context Resilience"
date: 2026-06-01
status: complete
origin: docs/reports/061/context-death-analysis.md
related:
  - docs/solutions/2026-05-20-autopilot-context-window-optimization.md
  - docs/solutions/2026-05-06-autopilot-skips-non-step-instructions.md
---

# Tier 2 Tail Delegation for Autopilot Context Resilience

## What We're Building

After the swarm build phase completes (Step 16w), the autopilot orchestrator
spawns a fresh agent to run the entire Shared Tail (review through self-audit)
in a clean context window. This eliminates context death during the tail
without requiring human intervention.

Three changes in scope:

1. **Tail delegation** — new agent definition (`.claude/agents/tail-runner.md`)
   + autopilot SKILL.md modification to spawn it after Step 16w
2. **BUILD_TRACKING structural fix** — replace `echo >>` appends with Edit
   tool insertions so agent rows land inside the AGENT_STATUS table, not
   after the Template Version section
3. **Deepen-plan sub-agent cap** — limit to 12 sub-agents when running
   inside autopilot to reduce pre-swarm context consumption

## Why This Approach

### Problem

Run 061 (10-agent swarm) completed the build successfully but the
orchestrator's context was ~98% consumed by Step 16w. The 9 remaining
tail steps (review, compound, learnings, self-audit, etc.) couldn't fit.
The orchestrator improvised an early checkpoint, but `/tail-resume` only
supports resuming from post-compound — 6 steps too late.

The existing Tier 1 checkpoint (load > 30 heuristic, fires post-compound)
was designed for a different failure mode: context death during the tail
after review. Run 061 died before the tail even started.

### Why delegation beats checkpointing

| Criterion | Checkpoint + resume | Tail delegation |
|-----------|-------------------|-----------------|
| Uninterrupted autopilot | No — requires human `/tail-resume` | Yes — orchestrator spawns agent, waits |
| Context budget | Shared with orchestrator | Fresh window (starts at 0%) |
| Complexity | Two checkpoint locations, heuristic tuning | One agent file, one skill edit |
| Failure recovery | Manual only | Orchestrator verifies artifacts on return |

The key insight: **delegation gives the tail a fresh context window without
stopping the pipeline**. Checkpointing is a pause-and-resume pattern;
delegation is a hand-off pattern. Hand-off is better when the downstream
work is self-contained, which the tail is.

### Alternatives considered

1. **Heuristic-based checkpoint** — expanding the load formula to include
   pre-swarm work density. Rejected: heuristics have false negatives by
   definition. Run 061 scored below the threshold and still died.

2. **Split tail into two sequential agents** — heavy agent (review +
   compound) and light agent (self-audit). Rejected: over-engineered.
   A single fresh agent has ~85% headroom, which is plenty. YAGNI.

3. **Auto-checkpoint + auto-spawn** — write CHECKPOINT.md, then
   immediately spawn a fresh agent to process it. Rejected: adds a
   file-based handoff that isn't necessary — just pass paths in the
   agent's prompt directly.

4. **Remove Tier 1 checkpoint entirely** — the tail agent makes it
   redundant. Rejected: solo builds still run the tail in the
   orchestrator's context. Removing Tier 1 leaves solo builds
   unprotected.

## Key Decisions

1. **Tail agent is a separate agent definition** at
   `.claude/agents/tail-runner.md`, not inlined in the autopilot skill.
   Easier to test independently, version separately, and reuse.

2. **Tier 1 checkpoint stays for solo builds, skipped in tail agent.**
   Solo builds still run the tail in the orchestrator's own context and
   need the safety net. The tail agent starts fresh and doesn't need it.
   Cleanest separation of concerns.

3. **Orchestrator verifies tail agent success.** After the tail agent
   returns, the orchestrator checks that mandatory artifacts exist
   (solution doc, self-audit, HANDOFF.md). Missing artifacts = run failure.
   Prevents silent tail agent crashes from being accepted. The tail
   agent is spawned as **foreground** (orchestrator waits for result)
   and **without `isolation: "worktree"`** (it operates on the merged
   main branch, not a copy).

4. **Deepen-plan cap: 12 sub-agents during autopilot.** The skill
   currently says "no limit, 20-40 is fine." This is at odds with
   context conservation in long pipelines. Cap only applies during
   autopilot runs — manual `/deepen-plan` remains uncapped. The cap
   must be enforced from the autopilot skill (e.g., passing a
   max-agents instruction when invoking deepen-plan), NOT by editing
   the plugin file directly — plugin cache files are overwritten on
   update.

5. **BUILD_TRACKING writes use Edit tool, not echo >>.** The `echo`
   append targets the file end, which put agent rows after the Template
   Version section in run 061. Edit tool insertions target the correct
   table location.

## Scope

### In scope

- `.claude/agents/tail-runner.md` — new agent definition
- `.claude/skills/autopilot/SKILL.md` — Step 16w.5 (spawn tail agent),
  artifact verification after return, BUILD_TRACKING Edit-based writes
- Autopilot SKILL.md Step 6 — pass max-agents instruction to deepen-plan
  invocation (enforced from caller, not by editing the plugin file)

### Out of scope

- Expanding the Tier 1 load heuristic formula (not needed with delegation)
- Auto-resume for solo builds (different problem, different solution)
- Tail agent checkpoint logic (YAGNI — fresh context has ~85% headroom)
- Changes to `/tail-resume` (stays as-is for solo build crash recovery)

## Open Questions

None — all resolved during brainstorm dialogue.

## Feed-Forward

- **Hardest decision:** Choosing delegation over checkpoint-and-resume.
  Both solve context death, but only delegation preserves uninterrupted
  execution. The trade-off is that we're trusting a spawned agent to
  run complex multi-step workflows (review with 7+ sub-agents, compound,
  learnings propagation) — this is architecturally supported but hasn't
  been tested at this depth.
- **Rejected alternatives:** Heuristic expansion (unreliable), split
  tail into two agents (YAGNI), auto-checkpoint (unnecessary file
  handoff), remove Tier 1 (unsafe for solo builds).
- **Least confident:** Whether the tail agent can effectively invoke
  `/workflows:review` and `/workflows:compound` as a spawned agent.
  General-purpose agents have all tools, but skill invocation from
  inside a sub-agent is untested in this repo. If it fails, the
  fallback is to inline the review/compound logic directly in
  tail-runner.md rather than delegating to skills.
