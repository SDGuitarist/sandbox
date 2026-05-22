# Review Summary -- Run 055, CoWorkFlow

**Date:** 2026-05-22
**Reviewers:** flow-trace-reviewer, security-sentinel, data-integrity-guardian, architecture-strategist, learnings-researcher, manual synthesis
**Plan:** docs/plans/2026-05-21-coworkflow-plan.md
**Feed-Forward risk:** Desk booking conflict logic (no UNIQUE constraint, relies on BEGIN IMMEDIATE + app logic)

## Severity Snapshot

| Priority | Count | Fixed | Deferred |
|----------|-------|-------|----------|
| P0       | 1     | 1     | 0        |
| P1       | 3     | 1     | 2        |
| P2       | 6     | 0     | 6        |
| INFO     | 2     | 0     | 2        |

## Recommended Fix Order

| # | Issue | Priority | Why this order | Unblocks |
|---|-------|----------|---------------|----------|
| 0 | P0-1: Navbar session key mismatch (base.html checks user_id, login sets logged_in) | P0 | App unusable -- navbar never renders, no navigation possible | -- |
| 1 | P1-1: CSRF token missing parens in plans templates | P1 | Breaks plan create/edit/delete -- forms submit function repr instead of token | -- |
| 2 | P1-2: Invoice status not auto-updated on payment | P1 | Design gap -- spec doesn't require it, admin can manually update. DEFER. | -- |
| 3 | P1-3: desk_bookings missing DB UNIQUE constraint | P1 | Accepted risk from Feed-Forward. App-level BEGIN IMMEDIATE is correct. DEFER. | -- |

## P1 Findings

### P1-1: CSRF token missing parentheses in plans templates (FIX)

**Files:** `plans/list.html:33`, `plans/form.html:9`
**Issue:** Templates use `{{ csrf_token }}` instead of `{{ csrf_token() }}`. In Jinja2, this renders the function object's string representation (e.g., `<function generate_csrf at 0x...>`) instead of the actual CSRF token. Flask-WTF's `CSRFProtect` will reject all plan form submissions with 400 Bad Request.
**Impact:** All plan management operations (create, edit, delete) are broken.
**Fix:** Add `()` to both `csrf_token` references.
**FC mapping:** FC1 (naming divergence) -- plans agent used different template pattern than all other agents.

### P1-2: Invoice status not auto-updated on payment (DEFER)

**Files:** `payment.py:4-11`, `payments/routes.py:88-92`
**Issue:** `create_payment()` inserts a payment row but never updates `invoices.status` to 'paid'. `delete_payment()` never reverts status. Invoice status is purely manual via the billing edit form.
**Impact:** Pending invoice count is inflated. Fully-paid invoices still appear in payment dropdown. Overpayment not prevented.
**Decision:** DEFER. The spec says "WHEN admin records a payment THE SYSTEM SHALL store amount in cents linked to invoice" -- it does NOT prescribe auto-status updates. This is a design gap in a single-admin tool where the admin manages invoice status manually. Fixing requires transaction wrapping and business logic for partial payments.
**FC mapping:** FC31 (cross-flow data integrity)

### P1-3: desk_bookings missing DB UNIQUE constraint (DEFER)

**Files:** `schema.sql:48-61`
**Issue:** Room bookings have a partial UNIQUE index (`idx_room_bookings_no_double`); desk bookings do not. Double-booking prevention relies entirely on `BEGIN IMMEDIATE` + app logic.
**Decision:** DEFER. Explicitly documented in plan Feed-Forward as accepted risk. The am/pm/full overlap semantics make a simple UNIQUE index insufficient (a `full` booking conflicts with `am` and `pm` but they have different `block` values). A trigger-based solution adds complexity beyond scope. The `BEGIN IMMEDIATE` mechanism works correctly under concurrent load (verified by flow-trace analysis).
**FC mapping:** FC29 (transaction boundary)

## P2 Findings (All Deferred)

| ID | Finding | File | Reason for Deferral |
|----|---------|------|---------------------|
| P2-1 | No login brute-force protection | auth.py, auth/routes.py | Single-admin tool, carried from Run 054 |
| P2-2 | No session expiration | auth.py | Single-admin tool, carried from Run 054 |
| P2-3 | No security headers (CSP, X-Frame-Options) | __init__.py | Dev tool, carried from Run 054 |
| P2-4 | Overpayment not prevented | payments/routes.py:26 | Related to P1-2, deferred together |
| P2-5 | conn.commit() vs conn.execute('COMMIT') inconsistency | desk_booking.py:79, room_booking.py:83 | Harmless with isolation_level=None, maintenance hazard only |
| P2-6 | Member plan_id validation silently falls through to None | members/routes.py:62-63 | Non-critical -- None is a valid value (no plan) |

## INFO Findings

| ID | Finding | File |
|----|---------|------|
| INFO-1 | All templates correctly extend base.html (FC1 fix confirmed) | All 25 templates |
| INFO-2 | Transaction pattern (BEGIN IMMEDIATE + try/except/ROLLBACK) correctly applied to both booking models | desk_booking.py:9-33, room_booking.py:15-31 |

## Learnings Researcher Summary

No solution doc violations found. Key patterns correctly applied:
- FC29: BEGIN IMMEDIATE with try/except/ROLLBACK (GymFlow lesson applied)
- FC4: NaN/Inf guards on all money parsing (VenueConnect lesson applied)
- FC40: PRAGMA per-connection (busy_timeout, WAL, foreign_keys all set in get_db())
- FC37: All 22 agents committed (zero worktree failures)

One new pattern emerged: FC1 variant where plans agent diverged on CSRF token syntax. The spec prescribed `{{ csrf_token() }}` but the plans agent used `{{ csrf_token }}`.

## Flow-Trace Report

Full report at docs/reports/055/flow-trace-review.md. Key findings:
- Desk booking overlap logic is correct (am/pm/full symmetry verified)
- Room booking has DB-level backstop via partial UNIQUE index
- Payment/invoice flow has no auto-status updates (P1-2)
- `isolation_level=None` + manual `BEGIN IMMEDIATE` is functionally correct

## Feed-Forward Verification

The plan's "least confident" item (desk booking conflict logic for AM/PM/full overlap) was verified:
- The 3-way conflict matrix is correct and complete
- BEGIN IMMEDIATE provides serialization under concurrent load
- The missing UNIQUE constraint is a defense-in-depth gap, not an active bug
- No double-booking is possible through the existing code paths

## Feed-Forward

- **Hardest decision:** Classifying invoice auto-status as P1 DEFER vs P1 FIX. The flow-trace reviewer called it P0, but the spec doesn't require it and the admin has a manual workaround.
- **Rejected alternatives:** Adding a partial UNIQUE index to desk_bookings (the am/pm/full overlap makes simple indexing insufficient). Adding auto-invoice-status (requires transaction wrapping, partial payment logic, and scope expansion).
- **Least confident:** The CSRF bug in plans templates. If Flask-WTF handles `{{ csrf_token }}` (without parens) differently than expected, it might work -- but standard Jinja2 behavior says it won't. Fix is trivial and risk-free.
