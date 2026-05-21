# Review Context -- RestaurantOps

## Risk Chain

**Brainstorm risk:** "Whether 30+ agents at this feature breadth will produce consistent UX patterns across 14 blueprints."

**Plan mitigation:** 10-item Coordinated Behaviors table with prescriptive code blocks for flash messages, form styling, table styling, empty states, error handling, database connection pattern, status badges, and navigation.

**Work risk (from Feed-Forward):** "Whether the 29-agent model/route split produces correct cross-boundary imports."

**Review resolution:** 8 P1 (all fixed), 16 P2 (deferred). Top findings: security infrastructure gaps (3 P1), BEGIN IMMEDIATE scope (1 P1), naming divergence in supplier routes (1 P1). UX consistency risk did NOT materialize -- Coordinated Behaviors worked.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| restaurantops/app/__init__.py | Auth gate, security headers, CSRF handler | Auth bypass, session security |
| restaurantops/app/models/order_models.py | BEGIN IMMEDIATE transactions for prepare/cancel | Inventory deduction atomicity |
| restaurantops/app/models/inventory_models.py | Stock movement + inventory update | Data integrity under concurrent access |
| restaurantops/app/blueprints/orders/routes.py | Kitchen board, status transitions | TOCTOU races on concurrent updates |
| restaurantops/app/blueprints/purchase_orders/routes.py | PO receive with stock movements | Transaction boundary correctness |

## Plan Reference

`docs/plans/2026-05-21-restaurant-kitchen-mgmt-plan.md`
