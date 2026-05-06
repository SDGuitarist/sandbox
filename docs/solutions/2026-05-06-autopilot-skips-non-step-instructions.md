---
title: "Autopilot Orchestrator Skips Non-Step Instructions"
date: 2026-05-06
project: sandbox (autopilot skill)
tags: [autopilot, orchestrator, skill-design, compound-engineering]
failure_class: orchestrator-follows-steps-not-prose
agents_involved: autopilot orchestrator (Claude)
complexity: low
---

# Autopilot Orchestrator Skips Non-Step Instructions

## Problem

The autopilot skill had three mandatory actions documented in CLAUDE.md as prose instructions but NOT as numbered steps in the skill itself:

1. **BUILD_TRACKING.md** -- "Copy autopilot-tracking-template.md as BUILD_TRACKING.md before each run" (CLAUDE.md)
2. **Agent pitfalls injection** -- "Read agent-pitfalls.md and inject into each agent's brief" (CLAUDE.md)
3. **`/update-learnings`** -- Listed in the Shared Tail but merged with the Compound step, making it feel optional

Result: In the Tunestamp 6-agent swarm build, BUILD_TRACKING.md was never created, and `/update-learnings` was never run. Agent pitfalls were updated only because the review step happened to trigger it -- not because the skill enforced it.

This was the SECOND time `/update-learnings` was skipped. It was already documented as FC11 in agent-pitfalls.md from the venue-scraper build. The documented pitfall didn't prevent the repeat because the pitfall doc is injected into swarm agents, not into the orchestrator itself.

## Root Cause

**The orchestrator follows numbered steps, not prose.** CLAUDE.md instructions are loaded into context but compete with the skill's step-by-step structure. When the skill says "Step 1, Step 2, Step 3...", the orchestrator executes those steps sequentially and ignores anything not in that numbered sequence -- even if CLAUDE.md says it's mandatory.

This is the same failure pattern as swarm agents following spec tables but not spec prose (FC3: Dead Wiring). The orchestrator IS an agent. Agent rules apply to it.

## Solution

Converted all three prose instructions into explicit numbered steps in the autopilot skill:

**New Step 2.5: Create BUILD_TRACKING.md**
- Read template from `~/.claude/docs/autopilot-tracking-template.md`
- Write to project root as `BUILD_TRACKING.md`
- Fill in Run Info section

**New Step 2.6: Inject Agent Pitfalls**
- Read `~/.claude/docs/agent-pitfalls.md`
- Capture content for injection into agent briefs

**Separated Compound and Update Learnings into distinct steps:**
- Compound step writes the solution doc
- Update Learnings step runs `/update-learnings` with a bold FC11 warning
- Update Agent Pitfalls step traces findings to agents and updates pitfalls doc
- Update BUILD_TRACKING step fills in final metrics and commits

Each step has a "MANDATORY -- DO NOT SKIP" label.

## Pattern: If It's Not a Step, It Won't Happen

When designing skills or automation pipelines for LLM orchestrators:

1. **Every mandatory action must be a numbered step.** Prose instructions in surrounding docs (CLAUDE.md, READMEs, comments) are context, not commands. The orchestrator may read them but won't execute them reliably.

2. **Separate logically distinct actions into separate steps.** "Compound + Learnings" as one step means the orchestrator treats "learnings" as part of "compound" and stops after the solution doc. Two steps = two actions.

3. **Pitfall docs for agents don't protect the orchestrator.** Agent-pitfalls.md is injected into swarm agent briefs, but the orchestrator that runs the skill isn't a swarm agent. Orchestrator-level pitfalls must be embedded in the skill itself (as warnings in the relevant step).

4. **Label skippable vs non-skippable steps.** "MANDATORY -- DO NOT SKIP" in the step title creates a stronger signal than a note buried in prose.

## Verification

- Autopilot skill now has Steps 2.5, 2.6, and separated post-review steps
- Each mandatory step has explicit "DO NOT SKIP" label
- FC11 warning embedded directly in the Update Learnings step
- Next autopilot run should produce BUILD_TRACKING.md + run /update-learnings + update agent-pitfalls.md
