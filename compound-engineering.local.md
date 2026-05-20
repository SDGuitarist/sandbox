# Review Context -- Sandbox (Invoice & CRM, Run 046)

## Risk Chain

**Brainstorm risk:** "cross-blueprint data flows (deal-to-invoice, payment-to-invoice-status, recurring generation from dashboard) and spec size (~1200 lines) are highest coordination risk"

**Plan mitigation:** Cross-Boundary Wiring Table with exact code blocks for all 3 flows. Coordinated Behaviors Table for flash messages and activity logging. Endpoint Registry with url_for names.

**Work risk (from Feed-Forward):** "invoice line items form with parallel arrays (descriptions[], quantities[], unit_prices[], tax_rates[], catalog_item_ids[]) and the JS to add/remove rows"

**Review resolution:** 5 agents found 8 P1, ~12 P2, ~17 P3. 6 P1s fixed in code, 2 documented as acceptable (brute-force login, line-item duplication). Flow-trace reviewer found 3 cross-flow bugs (prefix crash, status revert, overdue gap) -- all fixed.

## Files to Scrutinize

| File | What changed | Risk area |
|------|-------------|-----------|
| invoice-crm/app/invoices/routes.py | 1134 lines, line-item parallel arrays, 70-line duplicated parsing block | Array desync, code duplication (046-W2) |
| invoice-crm/app/recurring/routes.py | generate_due_invoices cross-boundary import | Invoice number generation, prefix handling |
| invoice-crm/app/dashboard/routes.py | Imports from recurring, overdue detection, writes on GET | Performance (12 queries/load), status transitions |
| invoice-crm/app/payments/routes.py | Payment→invoice status update, overpayment logic | Status bypass (draft payments), delete revert |
| invoice-crm/app/pipeline/routes.py | Deal-won redirect to invoice creation | Cross-boundary wiring, activity logging |
| invoice-crm/app/auth/routes.py | Login endpoint, no rate limiting | Brute-force risk (046-W1) |

## Plan Reference

`docs/plans/invoice-crm-plan.md`
