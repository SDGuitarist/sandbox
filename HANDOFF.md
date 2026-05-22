# HANDOFF -- Sandbox

**Date:** 2026-05-22
**Branch:** master
**Phase:** Ready for Run 057 -- Craft Brewery Manager swarm build

## Current State

Run 056 (CoWorkFlow deferred fixes) is complete. All compound cycle artifacts
are written, learnings propagated, git clean and pushed. This session chose
**Craft Brewery Manager** as the Run 057 domain app.

## Run 057 Brief

**App:** Craft Brewery Manager (BrewOps)
**Stack:** Flask + SQLite (single-admin, same pattern as CoWorkFlow/GymFlow/RestaurantOps)
**Target:** 20-25 agents, autopilot swarm
**Key goal:** Validate the 3 new mandatory spec sections proposed in Run 056:
  1. **Concurrency Contract** -- tag every write function as SERIAL-SAFE, NEEDS-BEGIN-IMMEDIATE, or TRIGGER-BACKED
  2. **Defense-in-Depth Matrix** -- map every constraint to app-level and DB-level enforcement
  3. **Derived State** -- declare every field computed from other tables with an explicit owning agent

### Domain Sketch (for brainstorm seed)

A craft brewery management tool for a small brewery/taproom:
- **Recipes** -- beer recipes with ingredients, target ABV, style
- **Batches** -- brewing batches linked to recipes, with status tracking (planned, brewing, fermenting, conditioning, ready, tapped, empty)
- **Ingredients/Inventory** -- grain, hops, yeast, adjuncts with stock levels
- **Tanks/Fermenters** -- equipment with capacity, current batch assignment, availability
- **Taproom** -- tap assignments (which batch is on which tap), tap status
- **Sales** -- pint/growler/case sales by tap, daily totals
- **Staff** -- brewery staff with roles (brewer, server, admin)

### Derived State Opportunities (to test the new spec section)

- Batch status should auto-update based on timeline/events
- Inventory levels should auto-decrement when a batch starts brewing
- Tap status should reflect the assigned batch's remaining volume
- Sales should auto-decrement batch remaining volume

These cross-table dependencies are exactly what FC44 (implicit derived state)
is designed to catch. The spec must declare them explicitly.

### TOCTOU Opportunities (to test Concurrency Contract)

- Two batches claiming the same tank simultaneously
- Two sales reducing the same batch's remaining volume below zero
- Ingredient stock going negative from concurrent batch starts

## Prior Runs (Reference)

| Run | App | Agents | Key Lesson |
|-----|-----|--------|------------|
| 055 | CoWorkFlow | 22 | CSRF syntax in Coordinated Behaviors |
| 054 | GymFlow | 26 | BEGIN IMMEDIATE needs try/except/ROLLBACK |
| 052 | RestaurantOps | 29 | Model/route split, auth security checklist |
| 050 | GigSheet | 31 | CSP-CDN mismatch, PRAGMA per-connection |

## Key Docs to Read Before Starting

| Doc | Why |
|-----|-----|
| `~/.claude/docs/agent-pitfalls.md` | Inject FC1-FC44 into agent briefs |
| `~/.claude/docs/autopilot-tracking-template.md` | Copy to BUILD_TRACKING.md |
| `docs/solutions/2026-05-22-coworkflow-deferred-fixes-batch.md` | 3 new spec patterns + TOCTOU Fence |
| `docs/solutions/2026-05-22-coworkflow-22-agent-swarm-build.md` | 22-agent Flask swarm patterns |
| `docs/solutions/2026-05-21-gymflow-26-agent-swarm-build.md` | Transaction safety lessons |

## Deferred Items (Unrelated to Run 057)

### CoWorkFlow (Run 056 review -- all pre-existing)
- [056-D1] P1: `conn.commit()` no-op across all models. DEFERRED, MEDIUM.
- [056-D2] P1: Full-table FK validation in billing/desk_bookings. DEFERRED, LOW.
- [056-D3-D8] P1-P2: 6 additional items. DEFERRED, LOW.

### Prior
- GymFlow 054 P2s, spec-consistency-checker P2s, GigSheet 050 P2s

## Three Questions (from Run 056)

1. **Hardest decision?** Moving overpayment enforcement inside BEGIN IMMEDIATE.
2. **What was rejected?** Per-IP dict for brute-force, UPDATE trigger for desk bookings.
3. **Least confident about?** The 3 new spec sections. Run 057 is the validation.

## Prompt for Next Session

```
Read HANDOFF.md. This is the Sandbox project.

Run 057: Build BrewOps, a Craft Brewery Manager, as a standalone Flask +
SQLite autopilot-swarm build. Target 20-25 agents.

This run validates 3 new mandatory spec sections from Run 056:
- Concurrency Contract
- Defense-in-Depth Matrix
- Derived State

Use the definitions and reference patterns in HANDOFF.md and:
- docs/solutions/2026-05-22-coworkflow-deferred-fixes-batch.md
- docs/solutions/2026-05-22-coworkflow-22-agent-swarm-build.md
- docs/solutions/2026-05-21-gymflow-26-agent-swarm-build.md

Domain scope:
- recipes
- batches
- ingredients / inventory
- tanks / fermenters
- taps / taproom
- sales
- staff

Constraints:
- same single-admin Flask + SQLite pattern as recent sandbox swarms
- keep domains as clean vertical slices, but allow supporting tables where
  the schema requires them
- prefer simple CRUD plus only the business rules needed to exercise
  concurrency, defense-in-depth, and derived state
- keep overall complexity roughly in CoWorkFlow scale

Primary validation targets:
- Concurrency: tank assignment, sales decrementing batch volume, inventory
  decrements on brew start
- Derived state: batch status, inventory levels, tap status / remaining volume
- Defense-in-depth: app-level and DB-level enforcement are both prescribed
  where needed

Success bar:
- the shared spec includes all 3 new sections clearly
- review finds 0 FC43/FC44 issues caused by missing or underspecified spec
  coverage

Read ~/.claude/docs/agent-pitfalls.md before planning.

Run /autopilot
```
