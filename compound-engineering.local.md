# Review Context -- Sandbox

## Risk Chain

**Brainstorm risk:** Whether assembly-fix agent can correct a spec violation from a contract-check report alone -- never tested on a real failure in 8 prior builds.

**Plan mitigation:** Designed a controlled test: minimal app with one agent deliberately given wrong function names. Contract-check report includes file, line, what's wrong, and what spec says.

**Work risk (from Feed-Forward):** Whether the assembly-fix -> re-check -> smoke-test pipeline works end-to-end when exercised with a real spec violation.

**Review resolution:** 1 P1, 7 P2, 8 P3 -- all production concerns irrelevant to a test harness. Zero code changes applied. Assembly-fix produced clean, spec-compliant code with no residual artifacts. Risk fully resolved.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| error-test-app/routes.py | Assembly-fix corrected 4 lines (import + 3 call sites) | Residual error artifacts |
| error-test-app/models.py | Correct function names (never changed) | Spec source of truth |
| error-test-app/app.py | App factory (never changed) | DB init, teardown |

## Plan Reference

docs/plans/2026-04-12-test-error-injection-plan.md
