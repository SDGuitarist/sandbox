# Review Context — Film Production PM Tool

## Risk Chain

**Brainstorm risk:** "Call sheet Cross-Boundary Wiring — 6 cross-module imports is the densest coupling surface attempted. A single name mismatch or wrong return type crashes the call sheet page."

**Plan mitigation:** Cross-Boundary Wiring Table included all 6 import paths with return types. Pre-swarm contract checker given ground truth to validate against. Flow-trace-reviewer assigned to the callsheet+schedule+reports surface.

**Work risk (from Feed-Forward):** "Call sheet cross-boundary wiring — 6 cross-module imports including 4 into callsheet_models from 4 different model modules."

**Review resolution:** 5 findings (1 P1, 3 P2, 1 P3). Feed-Forward risk RESOLVED — all 6 imports verified correct by flow-trace-reviewer. Contract checker caught and fixed all mismatches before tail. Top finding: missing date validation on callsheets.generate (P1, mirrors pattern from personal-finance-tracker Run). All P1+P2 fixed in commit b783e3a. P3 (hospital/weather_note column mismatch) deferred to todo 060.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/blueprints/callsheets/routes.py | Added `import re` + YYYY-MM-DD date validation to `generate()` | Input validation completeness |
| app/__init__.py | SESSION_COOKIE_SECURE now conditional on FLASK_ENV=production | Auth behavior in dev vs prod |
| app/models/callsheet_models.py | generate_call_sheet multi-table transaction (4 cross-module reads) | Cross-boundary wiring, DOOD computation |

## Plan Reference

`docs/plans/film-production-pm-plan.md`
