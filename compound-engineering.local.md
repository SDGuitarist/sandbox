# Review Context — Prompting Dashboard Engine

## Risk Chain

**Brainstorm risk:** "Claude API synchronous calls may timeout in Flask request cycle"

**Plan mitigation:** 60s explicit timeout on Anthropic client, distinct exception handling for APITimeoutError/APIConnectionError/APIStatusError, threaded=True on dev server.

**Work risk (from Feed-Forward):** "Whether the 60s timeout + distinct exception handling is sufficient, or if Phase 2 async is needed."

**Review resolution:** 7-agent review found 12 issues (2 P1, 6 P2, 4 P3). All P1+P2 fixed. Top findings: missing generic exception handler (P1-048), non-atomic update route (P1-049). Feed-forward risk confirmed well-handled with two gaps fixed.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/blueprints/testing/routes.py | Claude API call, exception handling, model function wiring | Timeout path, empty content arrays |
| app/blueprints/prompts/routes.py | Form parsing helper, single with-block update | TOCTOU race on update |
| app/models.py | update_prompt None guard, get_latest_version_id | Transaction boundary |
| app/__init__.py | Security headers, CSRF | Defense-in-depth |
| run.py | Environment-controlled debug mode | RCE surface |

## Plan Reference

`docs/plans/2026-06-01-feat-prompting-dashboard-engine-plan.md`
