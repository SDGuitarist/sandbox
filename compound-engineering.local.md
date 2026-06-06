---
review_agents:
  - learnings-researcher
  - architecture-strategist
  - pattern-recognition-specialist
---

# Review Context — Sandbox (Autopilot Context-Death Solution)

## Risk Chain

**Brainstorm risk:** "Reduced swarm-runner scope (11w-16w only) may not save enough context for 20+ agent builds; BUILD_TRACKING YAML frontmatter fragility under repeated agent edits"

**Plan mitigation:** Dropped YAML frontmatter entirely (zero precedent). Replaced with markdown Phase Status table. Reduced swarm-runner scope acknowledged as architectural limitation. Three-stage layered defense: no-read + deepen-merge + swarm-runner.

**Work risk (from Feed-Forward):** "Whether the reduced swarm-runner scope saves enough context for 20+ agent builds. Worker spawn (Steps 7w-10.5w) remains inline."

**Review resolution:** 2 P1 + 3 P2 from 2 review rounds (Codex + Claude Code). All fixed. P1-1: worker_status serialization gap. P1-2: 20+ agent claim documented as limitation. P2s: STATUS normalization, auto-checkpoint, prerequisite gap. 9/9 invariant checks PASS.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| .claude/skills/autopilot/SKILL.md | Steps 5.5, 6-6.08, 9w.5-9w.7, 10w-17w rewritten | Step reference consistency, solo/swarm path divergence |
| .claude/agents/swarm-runner.md | New — assembly + verification delegation | Circuit breaker behavior, inline conflict resolution |
| .claude/agents/deepen-merge-runner.md | New — merge delegation (swarm-only) | Corrections format parsing, anchor-failure recovery |
| .claude/agents/spec-completeness-checker.md | Output contract added | Contract compliance on existing behavior |
| .claude/agents/spec-consistency-checker.md | Output contract added | Contract compliance on existing behavior |

## Plan Reference

`docs/plans/2026-06-03-autopilot-context-death-solution-plan.md`
