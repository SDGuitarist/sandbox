# Review Context -- Client Intake Dashboard

## Risk Chain

**Brainstorm risk:** "Multiple blueprints sharing /admin/submissions url_prefix -- route registration order matters; wrong order could shadow routes"

**Plan mitigation:** Defined strict blueprint registration order (auth -> intake -> dashboard -> submissions -> detail -> status -> assessments). Each blueprint has distinct path patterns -- no overlap possible.

**Work risk (from Feed-Forward):** "Route registration order with multiple blueprints on the same url_prefix"

**Review resolution:** 5 agents, 10 P1s (9 fixed, 1 deferred). Top findings: XSS in custom filter (FC20), key mismatch crash (FC43), SECRET_KEY fallback (FC15), missing rate limiting (FC25). Feed-Forward risk (route shadowing) verified CLEAR. 11 P2, 15 P3 deferred.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/filters.py | XSS fix in status_badge (escape before Markup) | Custom filter security |
| app/__init__.py | SECRET_KEY fail-closed, login rate limiting | App configuration security |
| app/auth.py | session.clear() on logout, rate limiting on login | Session security |
| app/blueprints/status/routes.py | Same-status check, dead import removed | Status transition validation |
| app/blueprints/assessments/routes.py | Summary required validation | Assessment data quality |
| app/templates/detail/show.html | is_audit_fit key fix (was audit_fit) | Template-schema consistency |

## Plan Reference

`docs/plans/client-intake-dashboard-plan.md`
