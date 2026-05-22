---
title: CoWorkFlow Deferred Fixes (Run 055)
date: 2026-05-22
type: brainstorm
project: coworkflow
source: HANDOFF.md deferred items 055-W1, 055-W2, 055-W3
---

# CoWorkFlow Deferred Fixes Brainstorm

## Context

Run 055 built CoWorkFlow (22-agent swarm). Review deferred 2 P1s and 6 P2s.
This brainstorm explores approaches for all 8 items before planning.

---

## 055-W1: Invoice auto-status on payment (P1, MEDIUM)

### Problem
When a payment is recorded via `create_payment()`, the invoice status stays
`pending` even if total payments >= invoice amount. The admin must manually
edit the invoice to mark it `paid`.

### Current code
- `create_payment()` in `models/payment.py` just INSERTs and commits
- `get_total_paid_for_invoice()` already exists and works correctly
- Invoice detail page already shows `total_paid` -- so the data is there
- `update_invoice()` exists and can set status

### Approaches

**A. Update status in `create_payment()` (model layer)**
- After INSERT, query total_paid vs invoice amount_cents
- If total_paid >= amount_cents, UPDATE invoice status to 'paid'
- Pro: Encapsulated, always fires regardless of caller
- Con: `create_payment` currently commits once; now needs a transaction
  wrapping two writes (payment INSERT + invoice UPDATE)
- Con: Mixes payment and invoice concerns in one model function

**B. Update status in the payments route (controller layer)**
- After calling `create_payment()`, check total and update invoice
- Pro: Simple, clear control flow
- Con: If another route or script creates payments, the auto-update is missed
- Con: Two separate commits = risk of invoice staying stale if crash between

**C. SQLite trigger**
- `AFTER INSERT ON payments` trigger that updates invoice status
- Pro: Database-level guarantee, impossible to bypass
- Con: Harder to test, hidden business logic, SQLite trigger syntax is fragile

### Decision
**Approach A is best.** Wrap both writes in a single transaction inside
`create_payment()`. This matches the existing pattern in `create_desk_booking()`
which uses BEGIN IMMEDIATE for multi-step operations. The function already
commits internally (per the transaction contracts), so expanding the
transaction scope is consistent. The concern-mixing con is acceptable because
the alternative (controller layer) risks data integrity -- a single transaction
across both writes is more important than model purity.

Partial payments: status stays `pending` until total_paid >= amount_cents.
This is correct -- only auto-mark `paid` when fully paid.

### Overpayment check (ties into 055-W3 P2-4)
Currently nothing prevents paying more than the remaining balance.
Validation belongs in the payments route -- see 055-W3 P2-4 for the fix.

### Reverse case: delete_payment
If a payment is deleted on a "paid" invoice, the status should revert to
"pending". The `delete` route in `payments/routes.py` calls `delete_payment()`
but never rechecks the invoice total. Fix: apply same model-layer pattern --
wrap DELETE + status recheck in a BEGIN IMMEDIATE transaction inside
`delete_payment()`. After deleting, recompute total_paid and set invoice
status to "pending" if total_paid < amount_cents. Requires adding
`invoice_id` awareness to `delete_payment()` (currently only takes
`payment_id` -- query the payment's invoice_id before deleting).

---

## 055-W2: Desk bookings UNIQUE constraint (P1, LOW)

### Problem
`desk_bookings` has no DB-level UNIQUE constraint. The `room_bookings` table
has one (`idx_room_bookings_no_double`), but desk bookings have am/pm/full
overlap that makes a simple index insufficient.

### Current code
`create_desk_booking()` uses BEGIN IMMEDIATE + application-level conflict
check. This is correct and race-safe for SQLite (single-writer via WAL), but
a DB constraint would be defense-in-depth.

### Approaches

**A. Multiple partial unique indexes**
```sql
-- Prevent two 'full' bookings on same desk+date
CREATE UNIQUE INDEX idx_desk_full
  ON desk_bookings(desk_id, booking_date)
  WHERE block = 'full' AND status != 'cancelled';

-- Prevent two 'am' bookings on same desk+date
CREATE UNIQUE INDEX idx_desk_am
  ON desk_bookings(desk_id, booking_date)
  WHERE block = 'am' AND status != 'cancelled';

-- Prevent two 'pm' bookings on same desk+date
CREATE UNIQUE INDEX idx_desk_pm
  ON desk_bookings(desk_id, booking_date)
  WHERE block = 'pm' AND status != 'cancelled';
```
- Pro: Prevents duplicate am+am or pm+pm or full+full
- Con: Does NOT prevent am + full or pm + full. A 'full' booking should
  block 'am' and 'pm', but they have different `block` values so no single
  partial index catches cross-block conflicts.
- Verdict: Partial solution only.

**B. Normalized block model (two rows for 'full')**
- Store 'full' as two rows: one 'am' + one 'pm'
- Then a simple UNIQUE on (desk_id, booking_date, block) WHERE status != 'cancelled' works
- Pro: Clean, complete DB-level guarantee
- Con: Major schema change, breaks existing queries, UI, and reports. Way too
  much scope for a deferred fix.

**C. CHECK trigger**
```sql
CREATE TRIGGER desk_booking_conflict_check
BEFORE INSERT ON desk_bookings
BEGIN
  SELECT RAISE(ABORT, 'Desk booking conflict')
  WHERE EXISTS (
    SELECT 1 FROM desk_bookings
    WHERE desk_id = NEW.desk_id
      AND booking_date = NEW.booking_date
      AND status = 'confirmed'
      AND (NEW.block = 'full' OR block = 'full' OR block = NEW.block)
  );
END;
```
- Pro: Covers ALL conflict cases including am/full and pm/full overlap
- Pro: DB-level guarantee
- Con: Triggers in SQLite are less visible, but this is a well-known pattern

**D. Keep application-level check only (status quo + add the partial indexes)**
- The BEGIN IMMEDIATE pattern is already race-safe
- Add partial indexes from approach A as defense-in-depth for same-block dupes
- Accept that cross-block conflicts (am vs full) are only caught at app level
- Pro: Minimal change, already working correctly
- Con: Not fully DB-enforced

### Decision
**Approach C (trigger) is the cleanest complete solution.** It handles all
conflict cases in one place. The existing application-level check in
`create_desk_booking()` stays as the primary path (returns None for conflicts),
and the trigger acts as a safety net. If the trigger fires, it raises
IntegrityError which the existing `except Exception` block catches.

---

## 055-W3: P2 Security/Integrity Items

### P2-1: No login brute-force protection
- Current: Unlimited login attempts, no rate limiting
- Fix: Add in-memory counter (dict keyed by IP). Lock out after 5 failures
  in 60 seconds. Reset on success.
- Simple approach: Store `{ip: (count, first_failure_time)}` in a module-level
  dict. No external dependencies needed for a single-instance SQLite app.
- Clear the dict entry on successful login from that IP.

### P2-2: No session expiration
- Current: Flask session never expires (cookie-based, lives until browser closes)
- Fix: Set `PERMANENT_SESSION_LIFETIME` in Flask config (e.g., 8 hours).
  Set `session.permanent = True` on login.
- Flask handles this natively -- just needs configuration.

### P2-3: No security headers
- Current: No X-Content-Type-Options, X-Frame-Options, etc.
- Fix: Add `@app.after_request` handler in `__init__.py` that sets:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 0` (modern best practice -- rely on CSP instead)
  - `Referrer-Policy: strict-origin-when-cross-origin`
- Simple, 5 lines of code.

### P2-4: Overpayment not prevented
- Current: Can record a payment for more than the remaining balance
- Fix: In payments route `create()`, after validating the invoice exists,
  compute `remaining = invoice['amount_cents'] - get_total_paid_for_invoice(conn, invoice_id)`.
  Reject if `amount_cents > remaining`. Flash error "Payment exceeds remaining balance."
- Implement alongside 055-W1 since both modify the payment creation flow.

### P2-5: conn.commit() inconsistency
- All model functions commit internally. `create_desk_booking` uses explicit
  BEGIN IMMEDIATE/COMMIT instead of plain `conn.commit()` because it needs
  the conflict check to be atomic. This is intentional, not inconsistent.
- Decision: **No action needed.**

### P2-6: Member plan_id silent fallthrough
- `PRAGMA foreign_keys=ON` is set, so a nonexistent plan_id raises
  IntegrityError on INSERT. But this surfaces as a raw 500 error, not a
  friendly flash message.
- Fix: In members route, validate that plan_id exists (via `get_plan()`)
  before calling `create_member()` / `update_member()`. Flash error if None.

---

## Priority Order

1. **055-W1** (invoice auto-status + delete_payment reverse case) -- MEDIUM, data integrity
2. **055-W3 P2-4** (overpayment) -- do together with W1 since both touch payment flow
3. **055-W2** (desk booking UNIQUE trigger) -- LOW, defense-in-depth
4. **055-W3 P2-3** (security headers) -- LOW, 5 lines
5. **055-W3 P2-1** (brute-force) -- LOW, ~20 lines
6. **055-W3 P2-2** (session expiry) -- LOW, 2 lines
7. **055-W3 P2-6** (plan_id validation) -- LOW, ~5 lines
8. **055-W3 P2-5** (commit inconsistency) -- No action needed

---

## Feed-Forward
- **Hardest decision:** Whether desk booking UNIQUE should use trigger vs partial
  indexes. Trigger is more complete but less visible. Chose trigger because
  partial indexes can't catch am-vs-full conflicts.
- **Rejected alternatives:** Normalized block model (too much scope), controller-
  layer invoice update (misses non-route callers), SQLite trigger for invoice
  auto-status (overkill when model-layer function is sufficient).
- **Least confident:** Brute-force rate limiting with in-memory dict -- loses
  state on restart, but acceptable for a single-instance dev tool. If this
  were production, would need Redis or DB-backed counters.
- **Gap found during review:** `delete_payment` route doesn't revert invoice
  status. Plan must include the reverse-case fix alongside the auto-status work.
