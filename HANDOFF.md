# HANDOFF — Sandbox Merge Complete

**Date:** 2026-04-05
**Branch:** main
**Phase:** Compound complete — all 6 phases done

## Current State

Merged sandbox-auto's swarm coordination knowledge into sandbox. No code changes — this was a knowledge consolidation. 8 docs ported with `origin_repo: sandbox-auto` frontmatter annotations.

## Key Artifacts

| Phase | Location |
|-------|----------|
| Brainstorm | docs/brainstorms/2026-04-05-sandbox-merge-swarm-integration.md |
| Plan | docs/plans/2026-04-05-sandbox-merge-swarm-integration-plan.md |
| Review | docs/reviews/2026-04-05-sandbox-merge-review-summary.md |
| Solution | docs/solutions/2026-04-05-cross-project-knowledge-merge.md |

## What Was Ported (8 docs from sandbox-auto)

- 4 solution docs (swarm alignment, multi-service automation, swarm scaling, chain reaction contracts)
- 2 review summaries (health journal, uptime pulse)
- 2 brainstorm docs (swarm scale experiment, marketing funnel architecture)
- All 8 ported docs have `origin_repo: sandbox-auto` in frontmatter
- Solution docs include body-level note: "File paths reference the sandbox-auto repo (archived)"

## Cycle Artifacts (written in sandbox for this merge)

- `docs/brainstorms/2026-04-05-sandbox-merge-swarm-integration.md` — merge brainstorm
- `docs/plans/2026-04-05-sandbox-merge-swarm-integration-plan.md` — merge plan

These are NOT ported docs. They are the compound engineering cycle artifacts that drove this merge.

## Doc Counts After Merge

| Directory | Before | Ported | Cycle artifacts | After |
|-----------|--------|--------|----------------|-------|
| docs/solutions/ | 14 | +4 | 0 | 18 |
| docs/reviews/ | 0 (new) | +2 | 0 | 2 |
| docs/brainstorms/ | 14 | +2 | +1 | 17 |
| docs/plans/ | 14 | 0 | +1 | 15 |

## Assumptions Verified (During Plan Phase)

1. `/autopilot` command CANNOT branch — it's a static markdown file with `disable-model-invocation: true`. Branching happens in /workflows:work when it reads the plan.
2. Shared interface spec DOES transfer to Python/Flask — 8 integration surfaces identified (function signatures, DB schema, status enums, shared constants, import paths, Flask routes, config/env vars, implicit contracts).

## Python Shared Interface Spec Convention

Defined in the plan doc (Phase 2). When a plan has 2+ independent modules, include a `## Shared Interface Spec` section with: Public Function Signatures, Database Schema, Shared Constants, Flask Routes, Data Ownership, Implicit Contracts.

## Not Yet Validated (Next Cycle)

- Whether /workflows:work can detect a "Swarm Agent Assignment" table in the plan and switch to parallel builds
- Whether the shared spec pattern produces 0 mismatches for Python/Flask apps (validated only for JS so far)
- Spec verification step after parallel builds
- sandbox-auto is read-only but NOT archived until Python swarm validation succeeds

## Deferred Items

- Test agent that auto-generates tests from shared spec (validate pattern first)
- Archive sandbox-auto (after Python swarm validation succeeds)
- Investigate /workflows:work swarm detection capability

## Three Questions

1. **Hardest decision:** Which docs to port and which to leave behind. Chose to port solution docs, review summaries, and brainstorms (patterns transfer across stacks) but NOT plan docs (too many dead file path references to sandbox-auto source code).
2. **What was rejected:** Porting plan docs (60%+ dead references). Porting source code (different stack). Creating a fresh repo (anti-compounding — loses 14 solution docs and 18 test files).
3. **Least confident about:** Whether the "implied capability" risk materializes — ported docs describe swarm workflows that sandbox doesn't support yet. Mitigated by the "Not Yet Validated" section above, but a reader who skips HANDOFF and goes straight to solution docs might assume sandbox can do parallel swarm builds today.

## Prompt for Next Session

```
Read HANDOFF.md for context. This is sandbox, a compound engineering automation lab.
8 docs were just ported from sandbox-auto (swarm coordination patterns).
Next: validate the merge with a Python swarm build — multi-module Flask app,
shared interface spec in the plan, parallel agents in the work phase.
This is the acid test before archiving sandbox-auto.
```
