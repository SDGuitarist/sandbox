---
title: Swarm Scale Test — 6+ Parallel Agents
date: 2026-03-30
origin: HANDOFF.md suggestion + solution doc open question
prior_lessons:
  - 2026-03-30-swarm-build-alignment.md (shared spec = 0 mismatches for 3 agents)
  - 2026-03-30-uptime-pulse-multi-service-automation.md (shared spec scales to 5 files / 3 services)
open_question: "Does the shared spec pattern scale beyond 3-5 files? For 10+ file swarms, may need a different coordination mechanism."
origin_repo: sandbox-auto
origin_context: "Experiment design for 6-agent parallel build. See sandbox-auto repo for implementation."
---

# Swarm Scale Test — 6+ Parallel Agents

## What Are We Testing?

The shared spec pattern eliminated mismatches for 3 agents (Health Journal) and 5 files across 3 services (Uptime Pulse). The open question from both solution docs: **does it hold at 6+ parallel agents, or does it need a different coordination mechanism?**

Specifically:
1. Does a single shared spec document stay coherent when 6+ agents read it simultaneously?
2. At what complexity does the spec itself become the bottleneck (too long, too many cross-references)?
3. Do new failure modes emerge at this scale that didn't appear with 3 agents?

## What Should We Build?

Needs to be complex enough to require 6+ genuinely parallel agents (not artificial splitting). Options:

### Option A: Dashboard App (6-8 agents)
A multi-page dashboard with:
- Shared layout/nav component (1 agent)
- 3-4 page-specific views, each with their own CSS + JS (3-4 agents)
- Shared utility module for data fetching/state (1 agent)
- Main entry point that wires everything together (1 agent)

**Pro:** Natural parallelism — each page is independent. **Con:** Pages might be too independent, not enough integration surface to stress-test the spec.

### Option B: Real-Time Chat App (7-8 agents)
- Supabase schema + RLS (1 agent)
- Express API with auth + message endpoints (1 agent)
- WebSocket/Realtime handler (1 agent)
- Frontend HTML structure (1 agent)
- Frontend CSS (1 agent)
- Frontend JS — message rendering + send (1 agent)
- Frontend JS — user presence + typing indicators (1 agent)
- Shared spec + types (written first, not parallel)

**Pro:** High integration surface — every component talks to every other. **Con:** Complexity might overwhelm a sandbox test; we'd spend more time debugging Supabase Realtime than learning about swarm coordination.

### Option C: Static Multi-Page Site with Shared Design System (6 agents)
- Design system CSS (variables, typography, components) (1 agent)
- 4 content pages, each with unique layout + JS interactions (4 agents)
- Navigation + routing JS (1 agent)

**Pro:** Simple stack (no backend), focuses purely on agent coordination. **Con:** Might be too simple — we already proved shared specs work for static apps.

### Recommendation: Option A (Dashboard)

It hits the sweet spot: enough integration surface to stress the spec (shared state, shared nav, cross-page navigation), but simple enough stack (static + maybe a small JSON API) that we're testing swarm coordination, not debugging infrastructure.

## Constraints

- No real data, no secrets, no remote push (per CLAUDE.md)
- All agents must read the shared spec before starting
- Spec must stay under 150 lines (testing whether this limit holds at scale)
- Must be buildable and testable locally (open in browser, everything works)
- Track every mismatch found post-build (the key metric)

## Acceptance Criteria

1. 6+ agents run in parallel, each producing at least one file
2. Shared spec document written before agents launch
3. Post-build: count interface mismatches (target: 0, like Uptime Pulse)
4. If mismatches > 0: document what the spec missed and why
5. If spec > 150 lines: document whether length caused agents to miss details
6. Final app loads in browser with all pages working

## What Could Go Wrong?

1. **Spec bloat** — 6+ agents need more interface definitions. Spec grows past 150 lines, agents skip sections or miss details buried deep in the doc.
2. **Implicit dependencies** — agents assume things about each other's output that aren't in the spec (e.g., "the nav agent will add a container div I can mount into").
3. **Merge conflicts** — if two agents touch the same file (e.g., both add to index.html), their outputs conflict.
4. **Context window pressure** — spec + plan + agent instructions might eat too much context per agent, reducing quality.
5. **Ralph Loop namespace** — if plugin updated, `/slfg` stop hook breaks silently. Re-check namespace before launching.

## Prior Lessons to Carry Forward

| Lesson | Source | How It Applies |
|--------|--------|----------------|
| Shared spec = 0 mismatches | swarm-build-alignment.md | Core hypothesis — we're scaling this |
| Spec is a contract between agents, not a design doc | swarm-build-alignment.md | Keep spec focused on interfaces only |
| Integration surface is the primary risk, not task difficulty | swarm-build-alignment.md | Watch for implicit dependencies between agents |
| SSRF is default risk for server URL fetching | uptime-pulse.md | If we add a backend, add URL validation to the spec |
| Plan Feed-Forward catches operational risks; review catches security risks | uptime-pulse.md | Both phases still needed even in swarm mode |

## Feed-Forward

- **Hardest decision:** Choosing Option A over Option B. The chat app would stress-test integration more, but adds infrastructure complexity (Supabase Realtime, WebSockets) that would muddy the results — we'd be debugging infra, not learning about swarm coordination.
- **Rejected alternatives:** Option B (chat app — too much infra noise) and Option C (static site — already proven, wouldn't teach us anything new).
- **Least confident:** Whether the 150-line spec limit is realistic for 6+ agents. The Uptime Pulse spec covered 5 files in ~60 lines, but a dashboard with shared state, navigation, and 4 distinct pages might need 200+. If the spec has to grow past 150 lines, the "single shared spec" pattern might need to evolve into "spec + module-level sub-specs."
