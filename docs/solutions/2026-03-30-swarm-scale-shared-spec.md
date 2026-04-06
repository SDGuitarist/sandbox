---
tags: [swarm, parallel-agents, shared-spec, scaling, automation, lifecycle-contract]
module: sandbox-auto
problem: Does the shared interface spec pattern hold at 6+ parallel agents, or does it need a different coordination mechanism?
severity: N/A (experiment, not a bug)
lesson: Shared spec scales to 6 agents / 13 files with 0 mismatches, but spec size grew 27% past target — lifecycle contracts and routing manifests are the cost of scale
origin_repo: sandbox-auto
origin_context: "Built with vanilla HTML/CSS/JS + Chart.js (DevDash SPA). See sandbox-auto repo for source code."
---

# Swarm Scale — Shared Spec at 6 Agents

> **Note:** File paths reference the sandbox-auto repo (archived). Pattern applies to any stack.

## Problem

Previous experiments proved the shared interface spec pattern at small scale:
- 3 agents / 3 files → 7 mismatches WITHOUT spec, 0 WITH spec (Health Journal)
- 3 services / 5 files → 0 mismatches (Uptime Pulse)

Open question: does the pattern hold at 6+ agents, or does it break down and need a different mechanism (e.g., spec + sub-specs, one agent writes interfaces first)?

## Experiment

Built a 4-page SPA dashboard (DevDash) using 6 parallel agents, each reading the same shared spec embedded in the plan doc. No agent depended on another — all depended only on the spec.

| Agent | Files | Result |
|-------|-------|--------|
| 1 — Design System | 1 CSS file (532 lines) | All 36 spec classes present |
| 2 — Shell + Nav | index.html + nav.js | Route manifest exact match |
| 3 — Overview Page | HTML fragment + JS | Lifecycle contract followed |
| 4 — Projects Page | HTML fragment + JS | Lifecycle contract followed |
| 5 — Activity Page | HTML fragment + JS | Lifecycle contract followed |
| 6 — Settings + Data | 4 files (settings page + data.js + utils.js) | All globals match spec |

**Interface mismatches: 0.** All 17 element IDs, 36 CSS classes, 6 window globals, and 4 page lifecycle exports matched across all files.

## Solution

The shared spec pattern scales to 6 agents — but the spec itself needs to grow. Three additions were required at this scale that weren't needed at 3 agents:

### 1. Explicit Route Manifest (not string concatenation)
At 3 agents, routing wasn't needed (single page). At 6 agents with 4 pages, a whitelist route manifest was essential:
```javascript
const ROUTES = {
  overview: { fragment: '...', script: '...', global: 'OverviewPage', title: 'Overview' },
  // ...
};
```
Without this, agents would have invented different routing assumptions.

### 2. Page Lifecycle Contract (the highest-value addition)
The spec prescribed the exact pattern for init/destroy, including cleanup arrays. All 4 page agents implemented it identically. Without it, the Codex plan review predicted agents would export differently — confirmed as the right call.
```javascript
window.PageName = {
  _intervals: [], _listeners: [], _charts: [],
  init() { /* query DOM, attach listeners, store refs */ },
  destroy() { /* idempotent cleanup of all three arrays */ }
};
```

### 3. Shell Ownership Declaration
Explicitly stating what the shell (index.html) owns — script loading order, CDN dependencies, layout containers — prevented page agents from duplicating `<script>` tags or inventing their own structure.

## Patterns

1. **Shared spec scales linearly, not exponentially.** Going from 3→6 agents increased spec from ~60→~190 lines (3.2x), not 6x. The additions were structural (routing, lifecycle, ownership) not per-agent.

2. **The 150-line target was wrong.** The brainstorm predicted this — spec grew to ~190 lines. But the overshoot was ALL structural contracts (routing + lifecycle + ownership = ~80 lines), not interface definitions. The interface surface (IDs, classes, data shapes) stayed compact.

3. **Prescriptive beats descriptive for lifecycle contracts.** Saying "export init() and destroy()" would have produced 4 different implementations. Showing the exact pattern with `_intervals`/`_listeners`/`_charts` produced identical implementations across all 4 agents.

4. **Review found what planning couldn't.** Plan predicted lifecycle inconsistency as the top risk — review actually found XSS (innerHTML string concat) and navigation races. Same pattern as Uptime Pulse: planning catches operational risks, review catches security risks.

5. **Agent 6 (4 files) performed fine.** The plan flagged "settings agent is overloaded" — in practice, all 4 files were correct. 4 files is not too many for one agent if the spec is clear.

## Risk Resolution

- **Flagged risk (brainstorm Feed-Forward):** "Whether the 150-line spec limit is realistic for 6+ agents."
- **What actually happened:** Spec grew to ~190 lines (27% over). The limit IS too low for 6+ agents, but the growth is structural, not per-agent. A better target: 100 lines for interface surface + up to 100 lines for structural contracts (routing, lifecycle, ownership).
- **Flagged risk (plan Feed-Forward):** "Whether the page lifecycle contract is specific enough."
- **What actually happened:** It was. All 4 agents implemented it identically because the spec showed the exact pattern, not just the interface.
- **New finding from review:** XSS via innerHTML string concatenation. Not predicted by planning. Added to the security checklist: any agent building DOM from data must use createElement/textContent.

## Spec Size Guideline (updated)

| Agent Count | Interface Lines | Structural Lines | Total |
|-------------|----------------|-----------------|-------|
| 2-3 | ~40-60 | 0 (single page, no routing) | ~60 |
| 4-6 | ~80-100 | ~80-100 (routing + lifecycle + ownership) | ~190 |
| 7+ | ~100-120 | ~100-120 + consider sub-specs | ~220+ (untested) |

The 150-line target should be split: interface budget + structural budget. Interface grows with file count. Structural grows with architectural complexity (routing, state, services).

## Feed-Forward

- **Hardest decision:** Whether to split the spec into a compact interface doc + a separate conventions doc. Kept it as one document because agents need to read everything — splitting risks them skipping the conventions file.
- **Rejected alternatives:** Sub-specs per agent (adds coordination overhead — who writes the sub-specs?). Interface-first agent (one agent writes types/interfaces, others implement — adds a sequential dependency that defeats parallelism).
- **Least confident:** Whether 7+ agents would still work with a single ~220-line spec, or whether context pressure would cause agents to skip sections. The next experiment should test this boundary.
