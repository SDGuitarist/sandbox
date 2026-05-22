# Flow Trace Review -- Run 055, CoWorkFlow

**Reviewer:** Cross-flow data integrity agent
**Date:** 2026-05-22
**Scope:** 3 critical flows traced end-to-end across 3+ files each

---

## Summary Table

| Flow | Files Traced | Severity | Finding |
|------|-------------|----------|---------|
| Flow 1: Desk Booking Creation | routes.py -> desk_booking.py -> db.py -> schema.sql | **P1** | `conn.execute('BEGIN IMMEDIATE')` fails silently when `isolation_level=None` puts the connection in autocommit mode; `BEGIN IMMEDIATE` via `conn.execute()` is a SQL statement that works correctly in autocommit mode -- but the mixed use of `conn.commit()` vs `conn.execute('COMMIT')` is a latent hazard. Overlap logic itself is correct. See details. |
| Flow 2: Room Booking Creation | routes.py -> room_booking.py -> schema.sql | **P1** | Same `BEGIN IMMEDIATE` pattern as Flow 1. UNIQUE index is present as a DB-level backstop, but the app-level locking pattern has the same structural issue. |
| Flow 3: Payment -> Invoice Status | payments/routes.py -> payment.py -> invoice.py -> schema.sql | **P0** | Creating a payment NEVER updates the invoice status to 'paid'. Deleting a payment NEVER reverts invoice status. Invoice status is perpetually 'pending' regardless of payments received. |

---

## Flow 1: Desk Booking Creation

**Files:** `app/blueprints/desk_bookings/routes.py` -> `app/models/desk_booking.py` -> `app/db.py` -> `schema.sql`

**Data traced:** `(desk_id, member_id, booking_date, block)` created from POST form, consumed by INSERT into `desk_bookings`.

**Storage step:** `desk_bookings` table, no UNIQUE constraint, conflict prevention is purely application-level.

### Step-by-step trace

**Step 1 -- Route validation (routes.py:41-94)**

All four required fields are validated before calling the model:
- `desk_id`: parsed to `int`, checked against active desks list (lines 48-56)
- `member_id`: parsed to `int`, checked against members list (lines 59-68)
- `booking_date`: stripped, parsed with `strptime('%Y-%m-%d')` (lines 71-79)
- `block`: checked against `('am', 'pm', 'full')` (lines 82-85)

Validation is complete. Return value of `create_desk_booking()` is captured and checked for `None` (lines 88-91). PASS.

**Step 2 -- Model transaction (desk_booking.py:4-34)**

The overlap logic at lines 11-22:

- `block == 'full'`: conflicts with ANY existing confirmed booking for that desk+date (any block value). Correct -- a full-day booking can't coexist with am or pm.
- `block == 'am'`: conflicts with existing `am` or `full`. Correct -- an am booking blocks if am or full is taken.
- `block == 'pm'`: conflicts with existing `pm` or `full`. Correct -- a pm booking blocks if pm or full is taken.

The symmetry is complete. A `'full'` request conflicts with any row; an `'am'` request conflicts with `'am'` or `'full'`; a `'pm'` request conflicts with `'pm'` or `'full'`. No gap exists in the overlap matrix.

**Step 3 -- Transaction boundary and isolation_level interaction (db.py:15, desk_booking.py:10)**

`db.py` line 15 opens the connection with `isolation_level=None`. In Python's `sqlite3` module, `isolation_level=None` means **autocommit mode**: no implicit transaction is ever started by the driver. Each SQL statement executes and commits immediately unless you manually issue `BEGIN`.

`desk_booking.py` line 10 calls `conn.execute('BEGIN IMMEDIATE')`. Because `isolation_level=None` puts the connection in autocommit mode, this `BEGIN IMMEDIATE` SQL statement executes directly against SQLite and works correctly -- SQLite receives a literal `BEGIN IMMEDIATE` and opens a write-locking transaction. The subsequent `conn.execute('COMMIT')` at line 30 and `conn.execute('ROLLBACK')` at lines 24 and 33 are also SQL statements that SQLite processes correctly.

This means the `BEGIN IMMEDIATE` locking mechanism is functionally correct.

**However**, `cancel_desk_booking()` at line 79 uses `conn.commit()` (a Python driver call) rather than `conn.execute('COMMIT')`. With `isolation_level=None`, `conn.commit()` is documented to be a no-op when no transaction is open via the driver. The UPDATE at line 76 in `cancel_desk_booking()` executes as an autocommit statement (because `isolation_level=None` means every statement auto-commits). So `conn.commit()` is redundant but harmless here.

**Step 4 -- Race condition analysis**

`BEGIN IMMEDIATE` acquires a reserved lock immediately, blocking concurrent writers. This is the correct SQLite mechanism for preventing double-booking without a UNIQUE index. If two requests arrive simultaneously:
- Request A: `BEGIN IMMEDIATE` succeeds, gets reserved lock
- Request B: `BEGIN IMMEDIATE` blocks for up to `busy_timeout=5000ms` (line 19 of db.py)
- Request A commits -> Request B unblocks, re-runs its SELECT, sees the new row, returns `None`

This is correct behavior. The `busy_timeout` of 5 seconds prevents immediate failure.

**Step 5 -- Schema verification (schema.sql:48-61)**

No UNIQUE index on `desk_bookings`. The table has only performance indexes. This means the DB has no backstop if the app-level lock fails (e.g., if a different code path inserts without `BEGIN IMMEDIATE`). Currently, no other insert path exists.

**Findings:**

| Severity | Description |
|----------|-------------|
| P1 | The `desk_bookings` table has no DB-level UNIQUE constraint. If any future code path inserts without the `BEGIN IMMEDIATE` guard (e.g., a bulk import, migration script, or a new route that calls `conn.execute()` directly), double-bookings will silently succeed. The room_bookings table has a partial UNIQUE index as a DB-level backstop; desk_bookings does not. This is a defense-in-depth gap, not an active bug. |
| INFO | `cancel_desk_booking()` uses `conn.commit()` (Python driver call) while `create_desk_booking()` uses `conn.execute('COMMIT')` (SQL statement). Both work correctly with `isolation_level=None` but the inconsistency is a maintenance hazard. |

**Result: PASS (with P1 structural risk noted)**

The active booking-creation path is correct. The P1 is a missing safety net at the DB layer.

---

## Flow 2: Room Booking Creation (Comparison)

**Files:** `app/blueprints/room_bookings/routes.py` -> `app/models/room_booking.py` -> `schema.sql`

**Data traced:** `(room_id, member_id, booking_date, slot_start, purpose)` created from POST form, consumed by INSERT into `room_bookings`.

**Storage step:** `room_bookings` table with partial UNIQUE index on `(room_id, booking_date, slot_start) WHERE status != 'cancelled'`.

### Step-by-step trace

**Step 1 -- Route validation (room_bookings/routes.py:38-98)**

Fields validated before model call:
- `room_id`: parsed to `int` (line 49), room checked active via `get_room()` (lines 79-82)
- `member_id`: parsed to `int` (line 56), member existence checked via `get_member()` (lines 85-88)
- `booking_date`: stripped, parsed with `strptime('%Y-%m-%d')` (lines 62-69)
- `slot_start`: checked against `VALID_SLOT_STARTS` list (lines 72-74)
- `purpose`: no validation, optional free text (line 45)

Return value of `create_room_booking()` is captured and checked for `None` (lines 93-95). PASS.

**Step 2 -- Model transaction (room_booking.py:11-31)**

Identical `BEGIN IMMEDIATE` -> conflict SELECT -> INSERT -> COMMIT pattern. Same analysis applies as Flow 1. Functionally correct.

**Step 3 -- Schema backstop (schema.sql:73-75)**

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_room_bookings_no_double
    ON room_bookings(room_id, booking_date, slot_start)
    WHERE status != 'cancelled';
```

This partial UNIQUE index provides a DB-level guarantee that no two confirmed bookings can occupy the same room/date/slot. Even if the `BEGIN IMMEDIATE` guard were bypassed, SQLite would raise `UNIQUE constraint failed` and prevent the double-booking.

**Comparison to Flow 1:**

Room bookings have two layers of protection: app-level `BEGIN IMMEDIATE` + DB-level UNIQUE index. Desk bookings have only one layer: app-level `BEGIN IMMEDIATE`. Room bookings are more robust.

**Findings:**

| Severity | Description |
|----------|-------------|
| INFO | `cancel_room_booking()` at room_booking.py:83 uses `conn.commit()` (Python driver call) while `create_room_booking()` uses `conn.execute('COMMIT')` (SQL statement). Same inconsistency as Flow 1, same harmless outcome. |

**Result: PASS**

---

## Flow 3: Payment -> Invoice Status

**Files:** `app/blueprints/payments/routes.py` -> `app/models/payment.py` -> `app/models/invoice.py` -> `schema.sql`

**Data traced:** Payment creation/deletion should drive `invoices.status` transitions (`pending` -> `paid` on payment; `paid` -> `pending` on deletion).

**Storage step:** `invoices.status` column, `payments` table.

### Step-by-step trace

**Step 1 -- Payment creation (payments/routes.py:30-92)**

Route validates all fields, then calls `create_payment()` at line 89. The return value (payment_id) is discarded -- the route does not capture it, but this is acceptable because the route redirects to `list_payments` rather than to a payment detail page.

**Step 2 -- create_payment() does NOT update invoice status (payment.py:4-11)**

```python
def create_payment(...) -> int:
    cursor = conn.execute(
        "INSERT INTO payments (...) VALUES (?, ?, ?, ?, ?, ?)",
        (...))
    conn.commit()
    return cursor.lastrowid
```

`create_payment()` inserts one row into `payments` and commits. It makes no call to `update_invoice()` and issues no UPDATE to `invoices`. After this function returns, the invoice remains in its prior state (typically `'pending'`).

**Step 3 -- No post-payment invoice update in the route (payments/routes.py:88-92)**

```python
create_payment(conn, invoice_id, amount_cents, payment_date,
               payment_method, reference_number, notes)
flash('Payment created successfully.', 'success')
return redirect(url_for('payments.list_payments'))
```

The route does not call `update_invoice()` after `create_payment()`. There is no logic to check whether the payment amount satisfies the invoice balance and set status to `'paid'`.

**Step 4 -- Payment deletion does NOT revert invoice status (payment.py:37-39, payments/routes.py:95-104)**

```python
def delete_payment(conn, payment_id):
    conn.execute("DELETE FROM payments WHERE id=?", (payment_id,))
    conn.commit()
```

`delete_payment()` removes the payment row and commits. No invoice status update. The route at lines 95-104 does not call `update_invoice()` after `delete_payment()`.

**Step 5 -- Invoice status is manual-only (billing/routes.py:116-161)**

The only way invoice status changes is through the billing edit form (`billing/routes.update`), which is a fully manual operation by a staff member. The `update_invoice()` function accepts any valid status string supplied by the form.

**Step 6 -- Schema confirms no trigger (schema.sql:80-92)**

There is no SQLite trigger on `payments` that would auto-update `invoices.status`. The schema has no triggers at all.

**Step 7 -- Functional impact**

A staff member records a payment. The invoice status stays `'pending'`. The dashboard's `get_pending_invoice_count()` (invoice.py:55) counts this invoice as still pending. The `get_invoices_by_status(conn, 'pending')` call in `payments/routes.py:26` continues to show the already-paid invoice as available for additional payments. A second payment can be recorded against the same invoice with no warning. There is no computed `total_paid >= amount_cents` check anywhere in the payment creation flow.

**Findings:**

| Severity | Description |
|----------|-------------|
| **P0** | `create_payment()` does not update `invoices.status` to `'paid'`. Invoice status is never automatically driven by payment events. An invoice that has been fully paid continues to appear as `'pending'` in the system until a staff member manually edits it. |
| **P0** | `delete_payment()` does not revert `invoices.status`. If a staff member manually set the status to `'paid'`, then the payment is deleted (e.g., recorded in error), the invoice stays `'paid'` despite having zero associated payments. |
| **P1** | `payments/routes.py:26` queries `get_invoices_by_status(conn, 'pending')` to populate the payment form's invoice dropdown. Because status is never auto-updated, a fully-paid invoice remains in this list indefinitely, enabling overpayment with no application-level warning or guard. |

**Result: FAIL**

---

## Detailed Bug Descriptions

### Bug F3-A (P0): Payment creation never marks invoice paid

- **File:** `app/models/payment.py:4-11`
- **Impact:** Every invoice in the system remains `'pending'` after payment unless staff manually edits it. The dashboard's pending invoice count is permanently inflated. The billing workflow requires a separate manual step that has no reminder or enforcement mechanism.
- **Fix:** After the INSERT and commit in `create_payment()`, compute `SUM(amount_cents)` for the invoice and if it meets or exceeds `invoices.amount_cents`, call `UPDATE invoices SET status='paid' WHERE id=?`. Wrap both writes in a single transaction.

### Bug F3-B (P0): Payment deletion never reverts invoice status

- **File:** `app/models/payment.py:37-39`
- **Impact:** If a payment that caused a manual `'paid'` status is deleted, the invoice stays `'paid'` with zero supporting payments. A `'cancelled'` invoice whose only payment is deleted also has no reconciliation path.
- **Fix:** After deleting the payment in `delete_payment()`, recompute the invoice's total paid. If `total_paid < invoice.amount_cents` and status is `'paid'`, revert to `'pending'`. Wrap in a single transaction.

### Bug F3-C (P1): Overpayment not prevented

- **File:** `app/blueprints/payments/routes.py:26` and `app/models/payment.py:4-11`
- **Impact:** Because invoice status is never auto-updated, all invoices appear in the "pending" dropdown regardless of payment history. A second (or third) payment can be recorded against a fully-paid invoice. `payments` has no constraint preventing this. The `invoice_id` FK only checks the invoice exists, not its payment state.
- **Fix:** In `create_payment()`, before inserting, check `total_paid + new_amount_cents <= invoice.amount_cents` (or enforce a business rule about overpayment). Alternatively, filter the invoice dropdown to exclude those where total paid >= amount due.

---

## Schema Risk: desk_bookings missing DB-level UNIQUE constraint

- **File:** `schema.sql:48-61`
- **Severity:** P1
- **Impact:** The `desk_bookings` table relies entirely on the application-level `BEGIN IMMEDIATE` guard in `create_desk_booking()`. If any other code path (migration script, admin tool, a future route, or a test fixture) inserts a desk booking without this guard, double-bookings will be silently committed. By contrast, `room_bookings` has a partial UNIQUE index that acts as a DB-level backstop.
- **Fix:** Add a partial UNIQUE index: `CREATE UNIQUE INDEX IF NOT EXISTS idx_desk_bookings_no_double ON desk_bookings(desk_id, booking_date, block) WHERE status != 'cancelled'`. Note this requires thought: a `'full'` booking conflicts with `'am'` and `'pm'` but they have different `block` values, so a simple unique-on-block index does not capture the full/am/pm overlap. The correct DB-level solution requires either a trigger or application-enforced overlap logic remains necessary. The index would at minimum prevent exact duplicates (same block booked twice).

---

## Code Paths Checked Per Flow

| Flow | Branches Verified |
|------|------------------|
| Flow 1 | Happy path (booking created), conflict path (None returned), exception path (ROLLBACK), block='am'/'pm'/'full' overlap matrix, cancellation path |
| Flow 2 | Happy path, conflict path, exception path, cancellation path, UNIQUE index DB backstop |
| Flow 3 | Payment creation (happy path), payment deletion, manual invoice edit path, no-trigger schema verification, dropdown population path |

---

```
STATUS: FAIL -- 3 flows traced, 5 issues found (2 P0, 2 P1, 1 INFO)
```
