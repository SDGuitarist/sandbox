# Deepening Applied -- Run 055 (CoWorkFlow)

**Date:** 2026-05-21
**Agents used:** plan-quality-gate, spec-flow-analyzer, architecture-strategist, best-practices-researcher

## Changes Applied

### P1 Fixes (5)

1. **P1-1: `get_total_revenue_this_month` data ownership violation** -- Moved from `models/invoice.py` to `models/payment.py`. Updated Export Names Table, Cross-Boundary Wiring Table (added payment.py -> dashboard import, removed from invoice.py -> dashboard).

2. **P1-2: `get_invoices_by_member` missing from wiring** -- Added to `invoice.py -> billing/routes.py` import path in Cross-Boundary Wiring Table.

3. **P1-3: `room_bookings` missing `updated_at` column** -- Added `updated_at TEXT NOT NULL DEFAULT (datetime('now'))` to room_bookings schema. Updated `cancel_room_booking` docstring to include "Also sets updated_at."

4. **P1-4: `search_members` dead function (FC3)** -- Routed via `GET /members/?q=<query>` parameter. Updated Template Render Context to conditionally use `search_members` when `q` is provided.

5. **P1-5: ADMIN_PASSWORD guard not in create_app() (FC26)** -- Added production guard directly into `create_app()` code block after SECRET_KEY guard.

### P2 Fixes (3)

6. **P2-1: Dashboard `today` not prescribed** -- Added Coordinated Behavior #22: `today = date.today().isoformat()` with import.

7. **P2-3: `import math` not prescribed** -- Added Coordinated Behavior #21: route files parsing money must include `import math`.

8. **Duplicate IntegrityError handling (spec-flow Gaps 28-33)** -- Added IntegrityError handling for UNIQUE columns to Input Validation Prescriptions for members (email), desks (name), rooms (name), amenities (name) on both create and edit routes.

### Coordinated Behavior Additions (7 new rules: #19-#25)

9. **#19 Post-update redirect** -- Redirect to detail if exists, else list.
10. **#20 Bookings immutable** -- Cancel-and-rebook pattern, no edit routes.
11. **#21 Math import** -- Required for money parsing routes.
12. **#22 Dashboard today** -- Prescribed computation and import.
13. **#23 Duplicate IntegrityError** -- Handling on all UNIQUE column entities.
14. **#24 Decommission pattern** -- Use is_active=0, not deletion.
15. **#25 Date validation pattern** -- `datetime.strptime` for ISO date validation.

## Not Changed (accepted as-is)

- P2-2 (barrel file): Kept `models/__init__.py` barrel -- standard pattern even if unused by wiring.
- P2-5 (desk booking no UNIQUE index): Acknowledged in Feed-Forward, accepted risk.
- Spec-flow Gap 6 (member detail sparse): Kept simple -- admin navigates to bookings separately.
- Spec-flow Gap 8 (auto-status on payment): Status remains manual (admin discretion).
