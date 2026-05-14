# Review Context -- Sandbox (Workshop Registration Hub)

## Risk Chain

**Brainstorm risk:** Cross-stack API contract between Flask and Express is novel -- no prior swarm build has bridged two stacks.

**Plan mitigation:** Detailed cross-stack API contract with endpoint table, response shapes, registrant object shape, error codes. Express proxy prescribed as http-proxy-middleware with exact middleware order.

**Work risk (from Feed-Forward):** http-proxy-middleware body parsing order interaction untested. Exact field name consumption by Express not specified.

**Review resolution:** 30 findings from 4 agents (8 P1, 12 P2, 8 P3). Top findings: transaction safety (4 related P1s), admin dashboard field name mismatches, Helmet CSP blocking scripts, timing-vulnerable password comparison.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/models.py | Removed conn.commit() from update_status() | All callers must now commit explicitly |
| app/waitlist/routes.py | try_promote_next defers commit, rolls back on Square failure | Square API timeout could leave uncommitted state |
| app/registration/routes.py | Re-registration wrapped in BEGIN IMMEDIATE, reads status from DB | Complex branching on duplicate email statuses |
| frontend/app.js | Helmet CSP configured, compression added, proxy at root | CSP directives may need tuning for production |
| app/email/engine.py | DB connection separated from network I/O | 3-phase pattern must be maintained on future changes |

## Plan Reference

`docs/plans/2026-05-13-feat-workshop-registration-hub-plan.md`
