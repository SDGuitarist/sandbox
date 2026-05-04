# Codex Handoff: Writers Room Council App Brainstorm Review

**Date:** 2026-05-02
**Phase:** Brainstorm (pre-plan)
**Purpose:** External review of brainstorm document before planning phase begins

---

## Instructions for Codex

Read these files in order:

1. `docs/brainstorms/2026-05-02-writers-room-council-app-brainstorm.md` (THE BRAINSTORM - primary review target)
2. `~/Downloads/ai-human-editor-claude-code-handoff.md` (Editor strategic context)
3. `~/Downloads/ai-human-editor-build-brief-v0.2.md` (Editor 15 principles with operational definitions)
4. `~/Projects/amplify-workshop/workshops/2026-04-25-amplify/writers-room-council-handoff.md` (WRC v1.4 framework)

## Review the brainstorm for:

### 1. Cross-Section Contradictions
This is the highest-priority check. Prior spec work (Run 033, ethics-toolkit) proved that AI tools miss contradictions that are internally consistent within each section but incompatible across sections. Check:
- Does the Phase 0 fingerprint design (Decision 6) actually serve both the Council modes AND the Editor mode? The questions are editorial-focused. Do they give the Council enough to calibrate creative judgment?
- Does the Crystal Principle filter design (generate-then-filter + P7-P8 bypass) contradict any of the 15 editorial principles' operational definitions in the build brief?
- Does the project model (Decision 7, verdict + central question as first-class fields) support ALL the flows described in the verdict handoff (Decision 14)?
- Does the "never rewrites" constraint hold consistently across all four modes? Is there any place where the brainstorm accidentally describes the app generating text for the user?

### 2. Unstated Assumptions
- The brainstorm assumes the WRC v1.4 system prompt (~4,000 words designed for Claude Projects) will translate to per-call API prompts without quality loss. Is this assumption valid? What could degrade?
- The brainstorm assumes 15 editorial principles (extracted from one user's essay editing sessions) will work for other writers in the Essay/Long-form genre. Is this reasonable for a beta, or is it a risk?
- The brainstorm assumes Opus 4.6 can reliably perform the Contrarian's verb catch and the Crystal Principle classification via API calls. Any concerns?

### 3. Scope Creep or Missing Scope
- Is anything in the brainstorm that wasn't in the source artifacts (Editor handoff, WRC v1.4 handoff)?
- Is anything in the source artifacts that should be in the brainstorm but isn't?
- Are the 4 build phases realistic for 28 days with autopilot/swarm? Flag if any phase is overloaded.

### 4. Feed-Forward Risk
The brainstorm's "least confident" item is: whether the inline annotation system with editable-on-accept can be built with sufficient quality in the autopilot timeframe. Is this the right risk to be least confident about, or is there a bigger risk hiding?

### 5. Decision Quality
20 decisions were made. For each, ask: is the rationale sound? Is there a better alternative that wasn't considered? Flag any decision that feels premature or under-justified.

### 6. Plan Readiness
Can a plan be written from this brainstorm without re-opening fundamental WHAT/WHY questions? Or are there gaps that would force the planner to make product decisions that should have been made here?

## Output Format

```
## Findings

### P0 (Must fix before planning)
- [finding]

### P1 (Should fix, risk if ignored)
- [finding]

### P2 (Worth noting, not blocking)
- [finding]

## Claude Code Fix Prompt
[If P0s or P1s exist, provide a prompt for Claude Code to address them in the brainstorm document before proceeding to planning.]
```
