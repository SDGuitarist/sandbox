---
review_agents:
  - learnings-researcher
  - security-sentinel
  - performance-oracle
  - flow-trace-reviewer
---

# Review Context — Film Production PM Tool (Run 070)

## Risk Chain

**Brainstorm risk:** Multi-module call sheet aggregation — 6 cross-module imports is the densest coupling surface attempted; a single name or type mismatch crashes the call sheet page.

**Plan mitigation:** FC50 Orchestration Entrypoints table with full signatures for all 6 imports; spec-completeness Check 1b would fire and verify signatures were present before workers spawned.

**Work risk (from Feed-Forward, spec convergence):** Worker worktrees rooted on master f90aed8 (pre-convergence 2010-line spec). 4 spec sections missing. Orchestrator brief-injected the convergence fixes verbatim. Contract-check PASSED but the mitigation was fragile.

**Review resolution:** 0 P1, 2 P2, 3 P3. Feed-Forward risk RESOLVED — 6-import callsheet wiring verified end-to-end clean by flow-trace-reviewer. P2-1 (budget departments context) fixed in commit a09a725. P2-2 (double get_schedule_entries) deferred as todo #070. New finding: FC51 worktree-base divergence extends to spec files — brief injection is fragile, orchestrator must ensure converged spec at worktree base.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/blueprints/callsheets/routes.py | cross-boundary imports + generate route | 6-import wiring, TOCTOU, date validation |
| app/models/callsheet_models.py | generate_call_sheet idempotent algorithm | TOCTOU reads-outside/writes-inside, ON DELETE CASCADE |
| app/blueprints/expenses/routes.py | dept-head ownership (F-H6) | _headed_dept_ids vs _allowed_dept_ids pattern |
| app/blueprints/budget/routes.py | allocate route + index render context | departments list missing (P2-1, fixed) |
| app/models/search_models.py | FTS5 contentless single-writer | rowid encoding, project-scoping, coupling fragility |
| app/models/project_models.py | VALID_PHASE_TRANSITIONS, create_project | set vs list type, creator enrollment |

## Plan Reference

`docs/plans/film-production-pm-plan.md`
