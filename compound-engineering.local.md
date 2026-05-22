# Review Context -- CoWorkFlow

## Risk Chain

**Brainstorm risk:** "Brute-force rate limiting with in-memory dict -- loses state on restart"

**Plan mitigation:** Simplified to single global counter (not per-IP dict), eliminating memory exhaustion P0. Documented limitations.

**Work risk (from Feed-Forward):** "delete_payment reverse case -- reverting only from 'paid' to 'pending' may not match prior status"

**Review resolution:** 6 agents, 0 P0s. 3 introduced findings fixed (dead guard, rate limiter docs, import order). 8 pre-existing findings deferred. All agents confirmed transaction ROLLBACK paths complete.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| app/models/payment.py | BEGIN IMMEDIATE transactions for create/delete + auto-status + overpayment | Transaction safety, TOCTOU |
| app/blueprints/payments/routes.py | Overpayment UX gate + invoice status gate | Route-model consistency |
| schema.sql | BEFORE INSERT trigger for desk booking conflicts | Trigger logic completeness |
| app/__init__.py | Security headers + session lifetime | Cross-cutting config |
| app/blueprints/auth/routes.py | Global brute-force counter + session fixation | Rate limiter limitations |
| app/blueprints/members/routes.py | plan_id FK validation in create+update | conn timing, member object |

## Plan Reference

`docs/plans/2026-05-22-coworkflow-deferred-fixes-plan.md`
