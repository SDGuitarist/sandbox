# HANDOFF -- Sandbox

**Date:** 2026-05-22
**Branch:** master
**Phase:** Run 057 -- Shared Tail (review + compound + learnings + audit)

## Current State

Run 057 (BrewOps Craft Brewery Manager) swarm build is complete through
Step 15w (assembly merge to master). 21 agents, 54 files, ~4,343 LOC,
61/61 smoke tests pass, 0 merge conflicts, 0 assembly fixes.

**CHECKPOINT.md exists** -- the previous session paused for context after
the swarm. The tail resume skill (`/tail-resume`) reads CHECKPOINT.md and
picks up from the next_step field.

## What's Done

| Step | Status |
|------|--------|
| Compound Start + Lessons | DONE |
| BUILD_TRACKING.md | DONE (AGENT_STATUS filled, FAILURES/METRICS pending) |
| Agent Pitfalls (FC1-FC44) | Loaded and injected |
| Brainstorm | DONE (docs/brainstorms/2026-05-22-brewops-brainstorm.md) |
| Brainstorm Refinement | PASS (5 gaps addressed in plan) |
| Plan | DONE (docs/plans/brewops-plan.md, ~1,530 lines) |
| Deepen Plan (4 agents) | DONE -- 5 fixes merged (isolation_level, circular FK, session.permanent, float clamp, cookie secure) |
| Run ID | 057, reports at docs/reports/057/ |
| Pre-Swarm Gates | CLEARED (consistency: 9 found+fixed, completeness: 59+2 found+fixed) |
| Swarm (21 agents) | 21/21 committed, 0 FC37 failures |
| Ownership Gate | PASS |
| Assembly Merge | 21/21 merged, 0 conflicts |
| Smoke Tests | 61/61 PASS |
| Merge to Master | DONE |

## What's Remaining (Shared Tail)

All of these are mandatory. Missing any fails the run.

1. **Review** -- `/workflows:review`. Review agents should scrutinize the
   Feed-Forward risk: sale_models derived state chain (4-step side effect).
2. **Resolve TODOs** -- `/compound-engineering:resolve_todo_parallel`
3. **Compound** -- `/workflows:compound`. Solution doc must include Risk
   Resolution section tracing Feed-Forward through implementation.
4. **Update Learnings** -- `/update-learnings-noninteractive`
5. **Verify Learnings Artifacts** -- 4 checks (summary table, HANDOFF date,
   agent-pitfalls entry, ID uniqueness)
6. **Fill FAILURES + RUN_METRICS** -- Edit BUILD_TRACKING.md after review
7. **Verify BUILD_TRACKING** -- Non-empty AGENT_STATUS, FAILURES, RUN_METRICS
8. **Self-Audit** -- self-audit-reviewer agent writes docs/reports/057/self-audit.md
9. **Verify Self-Audit** -- `/verify-self-audit 057 docs/reports/057/`

## Key Files

| File | Purpose |
|------|---------|
| CHECKPOINT.md | Tail resume state (read by /tail-resume) |
| docs/plans/brewops-plan.md | Shared interface spec (1,530 lines) |
| docs/brainstorms/2026-05-22-brewops-brainstorm.md | Brainstorm |
| BUILD_TRACKING.md | Agent status (filled), failures/metrics (pending) |
| docs/reports/057/ | All gate reports + deepening audit |
| app/ | Application source (21 agents' output) |
| schema.sql | Database schema with CHECK constraints |
| test_smoke.py | 61 smoke tests |
| seed.py | Development seed data |

## Run 057 Validation Targets

This run validates 3 new mandatory spec sections from Run 056:

1. **Concurrency Contract** -- 4 NEEDS-BEGIN-IMMEDIATE functions (start_brewing,
   advance_batch_status, assign_to_tap, create_sale) with try/except/ROLLBACK
2. **Defense-in-Depth Matrix** -- 12 constraints with app + DB enforcement
3. **Derived State** -- 8 cross-table computed fields with owning agents

**Success bar:** Review finds 0 FC43/FC44 issues caused by missing or
underspecified spec coverage.

## Feed-Forward Risk (for Review)

**Risk:** sale_models derived state chain: sale -> decrement volume -> check
empty -> update batch status -> clear tap. 4-step side effect chain inside
one transaction. If any step missing, data integrity breaks silently.

**Review agents should:** Trace the create_sale function end-to-end and verify
all 4 steps are present and correctly ordered. Also verify the max(0, ...)
float clamping is in place.

## Prior Runs (Reference)

| Run | App | Agents | Key Lesson |
|-----|-----|--------|------------|
| 057 | BrewOps | 21 | (this run -- pending review) |
| 056 | CoWorkFlow fixes | solo | TOCTOU Fence, 3 new spec sections |
| 055 | CoWorkFlow | 22 | CSRF syntax in Coordinated Behaviors |
| 054 | GymFlow | 26 | BEGIN IMMEDIATE needs try/except/ROLLBACK |

## Deferred Items (Unrelated to Run 057)

### CoWorkFlow (Run 056 review -- all pre-existing)
- [056-D1] P1: `conn.commit()` no-op across all models. DEFERRED, MEDIUM.
- [056-D2] P1: Full-table FK validation in billing/desk_bookings. DEFERRED, LOW.
- [056-D3-D8] P1-P2: 6 additional items. DEFERRED, LOW.

### Prior
- GymFlow 054 P2s, spec-consistency-checker P2s, GigSheet 050 P2s

## Prompt for Next Session

```
Read HANDOFF.md. This is the Sandbox project, Run 057 (BrewOps).

The swarm build is complete (21 agents, 54 files, 61/61 smoke tests pass).
Resume the shared tail: review, resolve TODOs, compound, update-learnings,
BUILD_TRACKING, self-audit, verify.

Run /tail-resume
```
