---
title: CoWorkFlow Deferred Fixes Plan
date: 2026-05-22
type: plan
project: coworkflow
source: docs/brainstorms/2026-05-22-coworkflow-deferred-fixes-brainstorm.md
swarm: false
deepened: 2026-05-22
feed_forward:
  risk: "delete_payment reverse case was not in original deferred items -- discovered during brainstorm review"
  verify_first: false
---

# CoWorkFlow Deferred Fixes Plan

## Enhancement Summary

**Deepened on:** 2026-05-22
**Agents used:** security-sentinel, data-integrity-guardian, kieran-python-reviewer,
architecture-strategist, code-simplicity-reviewer, performance-oracle,
best-practices-researcher, learnings-researcher, Context7 (Flask + SQLite docs)

### Key Improvements
1. **P0 fix: TOCTOU race on overpayment** -- moved overpayment enforcement inside
   the BEGIN IMMEDIATE transaction in `create_payment()` (data-integrity-guardian)
2. **P0 fix: Rate limiter memory exhaustion** -- replaced IP-keyed dict with single
   global counter, eliminating unbounded memory growth (security-sentinel + simplicity)
3. **P1 fix: Invoice status guards** -- `create_payment` won't auto-update cancelled
   invoices; `delete_payment` only reverts from 'paid' (security + data-integrity)
4. **P1 fix: Session fixation prevention** -- added `session.clear()` before login
   (best-practices-researcher, Flask official docs)
5. **Simplified Fix 1** -- calls existing `get_total_paid_for_invoice()` helper
   instead of inlining the query (simplicity reviewer, DRY)

### New Considerations Discovered
- `request.remote_addr` returns proxy IP behind reverse proxy -- documented as
  deployment assumption (security-sentinel, architecture-strategist)
- HSTS header should be added alongside other security headers (security-sentinel)
- Invalid plan_id strings ("abc") silently become None -- fix while touching the
  code path (python-reviewer)
- `cursor.lastrowid` preferred over `SELECT last_insert_rowid()` (python-reviewer)
- `RAISE(ABORT)` in triggers rolls back the statement but NOT the transaction --
  trigger design is correct (best-practices-researcher, SQLite docs)

---

## Plan Quality Gate

1. **What exactly is changing?** 7 targeted fixes across 6 files in the
   CoWorkFlow app: invoice auto-status on payment create/delete, overpayment
   prevention, desk booking conflict trigger, security headers, brute-force
   protection, session expiry, and plan_id validation in members route.

2. **What must not change?** Existing happy-path behavior for all routes.
   DB schema columns and table structure. The `create_desk_booking()` BEGIN
   IMMEDIATE pattern (trigger is additive). Template files. Blueprint
   registration order.

3. **How will we know it worked?** EARS acceptance tests below, plus the
   existing smoke tests in `test_smoke.py` must still pass.

4. **What is the most likely way this plan is wrong?** The `create_payment()`
   transaction refactor could break if `get_total_paid_for_invoice()` behaves
   unexpectedly inside a BEGIN IMMEDIATE block. SQLite docs confirm that reads
   inside a write transaction DO see uncommitted writes from the same connection
   (https://www.sqlite.org/isolation.html), and this is validated by GymFlow
   Run 054's `check_in_class` pattern. Test explicitly nonetheless.

---

## Fix 1: Invoice auto-status on payment (055-W1)

**Files:** `app/models/payment.py`

### create_payment() changes

Wrap the INSERT + overpayment check + status-check in a BEGIN IMMEDIATE
transaction. The overpayment enforcement is inside the transaction to prevent
TOCTOU races (P0 finding from data-integrity-guardian).

```python
def create_payment(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, payment_date: str,
                   payment_method: str, reference_number: str,
                   notes: str) -> int | None:
    """Create payment. Returns payment ID, or None if overpayment rejected.
    Commits: yes (BEGIN IMMEDIATE / COMMIT).
    Auto-updates invoice status to 'paid' when fully paid."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Overpayment check INSIDE the transaction (TOCTOU-safe)
        total_paid = get_total_paid_for_invoice(conn, invoice_id)
        invoice = conn.execute(
            "SELECT amount_cents, status FROM invoices WHERE id=?",
            (invoice_id,)).fetchone()
        if invoice is None:
            conn.execute('ROLLBACK')
            return None
        remaining = invoice['amount_cents'] - total_paid
        if amount_cents > remaining:
            conn.execute('ROLLBACK')
            return None  # caller flashes appropriate error
        # Insert the payment
        cursor = conn.execute(
            "INSERT INTO payments (invoice_id, amount_cents, payment_date, "
            "payment_method, reference_number, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (invoice_id, amount_cents, payment_date,
             payment_method, reference_number, notes))
        payment_id = cursor.lastrowid
        # Auto-update invoice status if fully paid (skip cancelled invoices)
        new_total = total_paid + amount_cents
        if new_total >= invoice['amount_cents'] and invoice['status'] != 'cancelled':
            conn.execute(
                "UPDATE invoices SET status='paid', updated_at=datetime('now') "
                "WHERE id=?", (invoice_id,))
        # conn.execute('COMMIT') not conn.commit() because isolation_level=None
        # (autocommit mode -- conn.commit() is a no-op)
        conn.execute('COMMIT')
        return payment_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

### Research Insights (Fix 1)

**SQLite transaction visibility (confirmed):**
From https://www.sqlite.org/isolation.html: "Within a single database connection X,
a SELECT statement always sees all changes to the database that are completed prior
to the start of the SELECT statement, whether committed or uncommitted."
`get_total_paid_for_invoice()` is a pure SELECT and will not interfere with the
transaction. Calling it instead of inlining avoids DRY violation.

**GymFlow Run 054 lesson:** The try/except/ROLLBACK wrapper is mandatory.
Missing it leaves the write lock open on any exception. Both `create_payment()`
and `delete_payment()` must have the wrapper.

**Why `cursor.lastrowid` over `SELECT last_insert_rowid()`:** More Pythonic,
avoids a separate query, matches `create_invoice()` and `create_member()` patterns.

**Return type change:** Returns `int | None` instead of `int`. `None` means
overpayment rejected or invalid invoice. The route must handle this.

### delete_payment() changes

Same pattern. Only reverts status from 'paid' to 'pending' (not from
'cancelled' or 'overdue').

```python
def delete_payment(conn: sqlite3.Connection, payment_id: int) -> None:
    """Delete payment. Reverts invoice to 'pending' if it was auto-set to 'paid'.
    Commits: yes (BEGIN IMMEDIATE / COMMIT)."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            "SELECT invoice_id FROM payments WHERE id=?",
            (payment_id,)).fetchone()
        if row is None:
            conn.execute('ROLLBACK')
            return  # payment doesn't exist, nothing to do
        invoice_id = row['invoice_id']
        conn.execute("DELETE FROM payments WHERE id=?", (payment_id,))
        # Only revert status if it was auto-set to 'paid'
        invoice = conn.execute(
            "SELECT amount_cents, status FROM invoices WHERE id=?",
            (invoice_id,)).fetchone()
        if invoice is not None and invoice['status'] == 'paid':
            new_total = get_total_paid_for_invoice(conn, invoice_id)
            if new_total < invoice['amount_cents']:
                conn.execute(
                    "UPDATE invoices SET status='pending', "
                    "updated_at=datetime('now') WHERE id=?",
                    (invoice_id,))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

**Key change from original plan:** Only reverts from 'paid' to 'pending', never
touches 'cancelled' or 'overdue' invoices. Those statuses were set by admin
action and require admin action to change. (data-integrity-guardian P1 finding)

---

## Fix 2: Overpayment prevention (055-W3 P2-4)

**Files:** `app/blueprints/payments/routes.py`

The authoritative overpayment enforcement is now inside `create_payment()`
(Fix 1). The route-level check is a UX optimization: it provides a friendly
flash message before entering the transaction.

```python
from app.models.payment import get_total_paid_for_invoice

# After invoice validation (line 45-48), before create_payment:
if invoice['status'] in ('paid', 'cancelled'):
    flash('This invoice cannot receive payments.', 'error')
    return redirect(url_for('payments.new_payment'))

total_paid = get_total_paid_for_invoice(conn, invoice_id)
remaining = invoice['amount_cents'] - total_paid
if remaining <= 0:
    flash('Invoice is already fully paid.', 'error')
    return redirect(url_for('payments.new_payment'))
if amount_cents > remaining:
    flash('Payment exceeds remaining balance.', 'error')
    return redirect(url_for('payments.new_payment'))
```

Then update the `create_payment()` call to handle `None` return:

```python
payment_id = create_payment(conn, invoice_id, amount_cents, payment_date,
                            payment_method, reference_number, notes)
if payment_id is None:
    flash('Payment rejected.', 'error')
    return redirect(url_for('payments.new_payment'))
```

### Research Insights (Fix 2)

**TOCTOU resolution:** The data-integrity-guardian identified a P0 race condition:
the route-level check and the model-level insert were not atomic. Two concurrent
requests could both pass the route check and both insert, causing overpayment.
The fix moves the authoritative check inside `BEGIN IMMEDIATE` in `create_payment()`.
The route check stays as a soft gate for UX. (SQLite `BEGIN IMMEDIATE` acquires a
RESERVED lock that serializes concurrent writers.)

**Invoice status gate:** The route should reject payments on 'paid' or 'cancelled'
invoices. Without this, a crafted POST request could submit a payment for an
invoice not shown in the dropdown. (data-integrity-guardian P1)

---

## Fix 3: Desk booking conflict trigger (055-W2)

**Files:** `schema.sql`

Add after the `desk_bookings` table and its indexes:

```sql
CREATE TRIGGER IF NOT EXISTS desk_booking_conflict_check
BEFORE INSERT ON desk_bookings
WHEN NEW.status = 'confirmed'
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

### Research Insights (Fix 3)

**Trigger conflict logic verified:** The data-integrity-guardian enumerated all 9
block combinations and confirmed the WHERE clause is complete. The only allowed
combination is am+pm (correct -- different halves of the day).

**RAISE(ABORT) behavior confirmed:** From SQLite docs, RAISE(ABORT) rolls back the
INSERT statement but NOT the surrounding transaction. This means the app-level
check in `create_desk_booking()` catches conflicts first (returns None), and if
somehow bypassed, the trigger fires and raises `sqlite3.IntegrityError` which the
existing `except Exception` block catches and rolls back. Defense-in-depth works
correctly.

**UPDATE trigger omitted intentionally:** The architecture-strategist noted that
a `BEFORE UPDATE` trigger would be needed for completeness (re-confirming a
cancelled booking). No UPDATE-to-confirmed path exists in the current routes
(only cancel). Adding the UPDATE trigger is ~10 lines but protecting against a
code path that doesn't exist. Noted as a known limitation for future reference.

**Simplicity consideration:** The code-simplicity-reviewer recommended dropping
Fix 3 entirely (app-level check is already race-safe). Keeping it because the
trigger is 10 lines, costs nothing at runtime, and catches direct DB manipulation
during schema migrations or manual fixes -- a real scenario in this project.

---

## Fix 4: Security headers (055-W3 P2-3)

**Files:** `app/__init__.py`

Add after `csrf.init_app(app)` inside `create_app()`:

```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Strict-Transport-Security'] = (
        'max-age=31536000; includeSubDomains')
    return response
```

### Research Insights (Fix 4)

**HSTS added:** The security-sentinel flagged that the app already sets
`SESSION_COOKIE_SECURE = not app.debug`, indicating HTTPS in production. Without
HSTS, the first request on a fresh browser can be intercepted via HTTP downgrade.
One extra line, high impact.

**X-Frame-Options not deprecated:** MDN confirms X-Frame-Options is still valid
(not deprecated), though CSP `frame-ancestors` supersedes it. Both can coexist.
Since we're not adding CSP (requires auditing inline scripts), X-Frame-Options
alone is correct.

**Permissions-Policy skipped:** Browser support is not yet baseline (MDN). Low
priority for a single-admin tool. Can add later.

**No CSP (confirmed):** Would require auditing all inline styles/scripts in
templates. Out of scope for a deferred fix batch. Noted as future follow-up.

---

## Fix 5: Brute-force login protection (055-W3 P2-1)

**Files:** `app/blueprints/auth/routes.py`

Simplified to a single global counter (not per-IP dict). This eliminates the
memory exhaustion P0 and is appropriate for a single-password admin tool.

```python
import time

_fail_count: int = 0
_first_fail: float = 0.0
_MAX_ATTEMPTS: int = 5
_LOCKOUT_SECONDS: int = 60
```

In the `login()` route:

```python
@bp.route('/login', methods=['POST'])
def login():
    global _fail_count, _first_fail
    now = time.time()
    # Reset counter if lockout window has passed
    if now - _first_fail > _LOCKOUT_SECONDS:
        _fail_count = 0
    # Check lockout
    if _fail_count >= _MAX_ATTEMPTS:
        flash('Too many attempts. Try again later.', 'error')
        return redirect(url_for('auth.login_page'))
    password = request.form.get('password', '')
    if not password or not check_password(password):
        if _fail_count == 0:
            _first_fail = now
        _fail_count += 1
        flash('Invalid password.', 'error')
        return redirect(url_for('auth.login_page'))
    # Success -- clear counter, set session
    _fail_count = 0
    session.clear()  # prevent session fixation (Flask best practice)
    session['logged_in'] = True
    session.permanent = True  # activate PERMANENT_SESSION_LIFETIME
    return redirect(url_for('dashboard.index'))
```

### Research Insights (Fix 5)

**Why single counter, not IP-keyed dict:** The code-simplicity-reviewer identified
that this is a single-password admin tool with one shared password. Per-IP tracking
solves a problem (legitimate admin locked out while attacker is rate-limited at a
different IP) that doesn't exist here. A single counter is ~8 lines instead of ~30.

**Memory exhaustion eliminated:** The security-sentinel P0 (unbounded dict growth
from spoofed IPs) is eliminated entirely -- there is no dict.

**Proxy IP concern eliminated:** The architecture-strategist and security-sentinel
flagged `request.remote_addr` behind proxy. Since we no longer use IP-based tracking,
this concern is moot.

**Session fixation prevention:** The best-practices-researcher found that Flask's
official security docs recommend `session.clear()` before setting login state.
This prevents session fixation attacks. Added to the login success path.

**Known limitation:** Counter resets on restart. Acceptable for a single-instance
admin tool. If the admin gets locked out, restart the server.

---

## Fix 6: Session expiration (055-W3 P2-2)

**Files:** `app/__init__.py`, `app/blueprints/auth/routes.py`

In `__init__.py`, add to `create_app()` after the SESSION_COOKIE settings:

```python
from datetime import timedelta
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
```

In `auth/routes.py`, `session.permanent = True` is already included in the
Fix 5 login route (after `session.clear()` and `session['logged_in'] = True`).

### Research Insights (Fix 6)

**Pattern confirmed by Flask docs and Context7:** This is the canonical Flask
pattern. Without `session.permanent = True`, the `PERMANENT_SESSION_LIFETIME`
config is completely ignored (Gotcha 1 from best-practices-researcher).

**Sliding window behavior:** `SESSION_REFRESH_EACH_REQUEST` defaults to `True`,
which re-sends the cookie on every response. This creates a sliding window --
the session stays alive as long as the admin is active. For an admin tool, this
is desirable. The 8-hour timeout only fires after 8 hours of inactivity.

**session.clear() before login:** Already added in Fix 5. Prevents session
fixation (Flask security docs recommend this).

---

## Fix 7: Member plan_id validation (055-W3 P2-6)

**Files:** `app/blueprints/members/routes.py`

In both `create()` and `update()` routes, fix two issues:

1. Flash error on non-integer plan_id (instead of silently setting None)
2. Validate that the plan exists before calling the model

Add `get_plan` to the existing import from `app.models.plan`:

```python
from app.models.plan import get_active_plans, get_plan
```

### create() path (replaces lines 58-63)

In `create()`, `conn` is not assigned until line 66. The plan_id validation
needs a connection, so call `get_db()` here. (`get_db()` caches in `g`, so
the later `conn = get_db()` on line 66 returns the same connection.)

```python
if membership_plan_id_raw:
    try:
        membership_plan_id = int(membership_plan_id_raw)
    except (ValueError, TypeError):
        flash('Invalid membership plan.', 'error')
        conn = get_db()
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=None, plans=plans)
    conn = get_db()
    if get_plan(conn, membership_plan_id) is None:
        flash('Invalid membership plan.', 'error')
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=None, plans=plans)
else:
    membership_plan_id = None
```

### update() path (replaces lines 132-137)

In `update()`, `conn` and `member` already exist (lines 103-104). Re-render
with the real `member` object so form fields are preserved.

```python
if membership_plan_id_raw:
    try:
        membership_plan_id = int(membership_plan_id_raw)
    except (ValueError, TypeError):
        flash('Invalid membership plan.', 'error')
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=member, plans=plans)
    if get_plan(conn, membership_plan_id) is None:
        flash('Invalid membership plan.', 'error')
        plans = get_active_plans(conn)
        return render_template('members/form.html', member=member, plans=plans)
else:
    membership_plan_id = None
```

### Research Insights (Fix 7)

**Silent None fallthrough fixed:** The python-reviewer and data-integrity-guardian
both identified that a garbage input like "abc" falls through `except ValueError`
to `membership_plan_id = None`, bypassing the new `get_plan()` validation entirely.
The fix flashes an error on ValueError instead of silently nullifying.

**Misleading error message fixed:** Without this fix, a nonexistent plan_id triggers
`IntegrityError` which the existing `except sqlite3.IntegrityError` block catches
and shows "A member with this email already exists." Pre-validating the plan_id
ensures the IntegrityError catch remains specific to email uniqueness.

---

## No action: conn.commit() inconsistency (055-W3 P2-5)

All model functions commit internally. `create_desk_booking` uses BEGIN
IMMEDIATE intentionally. No inconsistency exists. Skipped.

---

## Acceptance Tests

### Fix 1: Invoice auto-status

- WHEN a payment is created that makes total_paid >= invoice amount_cents THE SYSTEM SHALL auto-update the invoice status to 'paid'
- WHEN a payment is created that leaves total_paid < invoice amount_cents THE SYSTEM SHALL leave the invoice status unchanged
- WHEN a payment is created for a cancelled invoice THE SYSTEM SHALL NOT auto-update the invoice status
- WHEN a payment is deleted on a 'paid' invoice and total_paid drops below amount_cents THE SYSTEM SHALL revert the invoice status to 'pending'
- WHEN a payment is deleted on a 'paid' invoice and total_paid still >= amount_cents THE SYSTEM SHALL leave the invoice status as 'paid'
- WHEN a payment is deleted on an 'overdue' or 'cancelled' invoice THE SYSTEM SHALL NOT change the invoice status

### Fix 2: Overpayment prevention

- WHEN a payment amount exceeds the remaining invoice balance THE SYSTEM SHALL reject with flash "Payment exceeds remaining balance."
- WHEN a payment is submitted for a fully paid invoice (remaining = 0) THE SYSTEM SHALL reject with flash "Invoice is already fully paid."
- WHEN a payment is submitted for a paid or cancelled invoice THE SYSTEM SHALL reject -- even if the route-level state was stale before insert, the model authoritatively rejects inside BEGIN IMMEDIATE. Route flashes "This invoice cannot receive payments."; model returns None.
- WHEN a payment amount equals the remaining balance exactly THE SYSTEM SHALL accept the payment
- WHEN create_payment() returns None THE SYSTEM SHALL flash "Payment rejected." and redirect

### Fix 2 concurrency: TOCTOU prevention

- WHEN two concurrent calls to create_payment() each attempt to pay the full remaining balance of the same invoice THE SYSTEM SHALL accept exactly one and reject the other (return None), with no overpayment persisted. Implementation: the test MUST use two independent `sqlite3.connect()` calls (not `get_db()`, which is `g`-cached and returns the same connection within a single Flask request/app context). Calling `get_db()` twice in the same context does NOT create two real transactions and does NOT satisfy this test. Sequence: conn_a and conn_b each call `create_payment()` with amount = remaining balance. One returns a payment_id, the other returns None. Assert `SUM(amount_cents) == invoice.amount_cents` (no overpayment). This is an implementation-level test, not a browser test.

### Fix 3: Desk booking trigger

The trigger's WHERE clause `(NEW.block = 'full' OR block = 'full' OR block = NEW.block)`
produces 7 conflict cases and 2 allow cases from the 3x3 confirmed-booking matrix:
same-block conflicts (am+am, pm+pm, full+full = 3), full-vs-half conflicts in both
directions (am+full, full+am, pm+full, full+pm = 4), and the only allowed combination
is the cross-half pair (am+pm, pm+am = 2). The cancelled-status edge case is outside
the confirmed matrix but tested as an additional allow scenario.

**Conflict cases (7 of 9 confirmed-booking combinations):**
- WHEN existing 'am' + new 'am' on same desk+date THE SYSTEM SHALL raise ABORT 'Desk booking conflict'
- WHEN existing 'pm' + new 'pm' on same desk+date THE SYSTEM SHALL raise ABORT 'Desk booking conflict'
- WHEN existing 'full' + new 'full' on same desk+date THE SYSTEM SHALL raise ABORT 'Desk booking conflict'
- WHEN existing 'am' + new 'full' on same desk+date THE SYSTEM SHALL raise ABORT 'Desk booking conflict'
- WHEN existing 'full' + new 'am' on same desk+date THE SYSTEM SHALL raise ABORT 'Desk booking conflict'
- WHEN existing 'pm' + new 'full' on same desk+date THE SYSTEM SHALL raise ABORT 'Desk booking conflict'
- WHEN existing 'full' + new 'pm' on same desk+date THE SYSTEM SHALL raise ABORT 'Desk booking conflict'

**Allow cases (2 of 9 confirmed-booking combinations):**
- WHEN existing 'am' + new 'pm' on same desk+date THE SYSTEM SHALL allow the insert
- WHEN existing 'pm' + new 'am' on same desk+date THE SYSTEM SHALL allow the insert

**Edge case (cancelled status, outside the confirmed matrix):**
- WHEN existing 'cancelled' booking (any block) + new confirmed booking on same desk+date THE SYSTEM SHALL allow the insert

### Fix 4: Security headers

- WHEN any response is returned THE SYSTEM SHALL include X-Content-Type-Options: nosniff
- WHEN any response is returned THE SYSTEM SHALL include X-Frame-Options: DENY
- WHEN any response is returned THE SYSTEM SHALL include Referrer-Policy: strict-origin-when-cross-origin
- WHEN any response is returned THE SYSTEM SHALL include Strict-Transport-Security with max-age >= 31536000

### Fix 5: Brute-force protection

The counter increments after each failed attempt and the lockout check runs at
the start of the next request. This means the 5th failed attempt still receives
"Invalid password." (incrementing the counter to 5), and the 6th attempt is the
first to be blocked with "Too many attempts."

- WHEN 5 failed login attempts have occurred within 60 seconds THE SYSTEM SHALL reject the 6th attempt with "Too many attempts. Try again later." (the 5th attempt itself receives "Invalid password." and increments the counter to 5)
- WHEN 60 seconds elapse after the first failure THE SYSTEM SHALL reset the counter and allow login attempts
- WHEN a successful login occurs THE SYSTEM SHALL clear the failure counter
- WHEN a successful login occurs THE SYSTEM SHALL clear the existing session before setting logged_in (session fixation prevention)

### Fix 6: Session expiration

- WHEN a user logs in THE SYSTEM SHALL set a permanent session with 8-hour lifetime
- WHEN 8 hours of inactivity elapse after login THE SYSTEM SHALL require re-authentication

### Fix 7: Plan_id validation

- WHEN a member is created with a nonexistent numeric plan_id (e.g., "9999") THE SYSTEM SHALL flash "Invalid membership plan." (not "email already exists")
- WHEN a member is updated with a nonexistent numeric plan_id (e.g., "9999") THE SYSTEM SHALL flash "Invalid membership plan." (not "email already exists")
- WHEN a member is created with a non-integer plan_id (e.g., "abc") THE SYSTEM SHALL flash "Invalid membership plan." and NOT silently coerce to NULL
- WHEN a member is updated with a non-integer plan_id (e.g., "abc") THE SYSTEM SHALL flash "Invalid membership plan." and NOT silently coerce to NULL
- WHEN a member is created with no plan_id (empty string) THE SYSTEM SHALL allow creation with NULL plan
- WHEN a member is updated with no plan_id (empty string) THE SYSTEM SHALL allow update with NULL plan

### Verification Commands

```bash
# Run existing smoke tests (must still pass)
cd coworkflow && .venv/bin/python -m pytest test_smoke.py -v

# Verify security headers (including HSTS)
curl -s -I http://127.0.0.1:5000/login | grep -E '(X-Content-Type|X-Frame|Referrer-Policy|Strict-Transport)'

# Verify brute-force lockout (7 rapid failed attempts)
for i in $(seq 1 7); do
  curl -s -X POST http://127.0.0.1:5000/login -d 'password=wrong' -c cookies.txt -b cookies.txt -L | grep -o 'Too many\|Invalid password'
done
# Expected: 5x "Invalid password" (attempts 1-5), 2x "Too many" (attempts 6-7)
```

---

## Implementation Order

All fixes are independent. Implement in this order (data integrity first,
security second, validation last):

1. Fix 1 (invoice auto-status) -- `models/payment.py`
2. Fix 2 (overpayment) -- `blueprints/payments/routes.py`
3. Fix 3 (desk trigger) -- `schema.sql`
4. Fix 4 (security headers) -- `app/__init__.py`
5. Fix 5 + Fix 6 (brute-force + session expiry) -- `blueprints/auth/routes.py` + `app/__init__.py`
6. Fix 7 (plan_id validation) -- `blueprints/members/routes.py`

One commit per fix (~50 lines each). Fixes 5+6 combined into one commit since
both modify the login route and `__init__.py`. Run smoke tests after each commit.

**Dependency note:** Fix 2 depends on Fix 1's new `create_payment()` return type
(`int | None`). Implement Fix 1 first. All other fixes are independent.

---

## Feed-Forward

- **Hardest decision:** Whether to move overpayment enforcement inside the
  transaction (P0 TOCTOU fix) or keep it route-only. Moved it inside because
  the data-integrity-guardian demonstrated a concrete race sequence. The route
  check remains as a UX optimization.
- **Rejected alternatives:** IP-keyed dict for brute-force (over-engineered for
  single-password tool, introduces memory exhaustion P0), UPDATE trigger for desk
  bookings (no UPDATE path exists), inlined SUM query in create_payment (DRY
  violation when helper exists).
- **Least confident:** The `delete_payment` reverse case -- reverting only from
  'paid' to 'pending' is safe but means 'overdue' invoices that get fully paid
  then have a payment deleted stay 'paid'. This is an edge case where admin
  intervention is appropriate.

---

## Codex Handoff Prompt

```
Review the plan at docs/plans/2026-05-22-coworkflow-deferred-fixes-plan.md
for the CoWorkFlow project (Flask+SQLite coworking space manager).

Context: This plan fixes 7 deferred items from Run 055 (22-agent swarm build).
The brainstorm is at docs/brainstorms/2026-05-22-coworkflow-deferred-fixes-brainstorm.md.
The plan has been deepened with 8 review/research agents.

Check:
1. Does the TOCTOU fix (overpayment check inside BEGIN IMMEDIATE) correctly
   prevent concurrent overpayment? Is the return type change (int -> int | None)
   handled correctly in the route?
2. Is the single global counter for brute-force protection correct for a
   single-password admin tool? Any edge cases with the global statement?
3. Does the delete_payment() correctly only revert from 'paid' status? What
   happens if a payment is deleted on a 'pending' invoice (no-op is correct)?
4. Is the HSTS header appropriate given that SESSION_COOKIE_SECURE is only
   set when not in debug mode?
5. Does session.clear() before login introduce any issues (losing flash messages)?
6. Is the desk booking trigger's conflict logic complete for all am/pm/full combos?
7. Does Fix 7 correctly handle both create() and update() paths in members routes?
8. Any gaps in the EARS acceptance tests?

Flag any P0 issues (will cause bugs) vs P1 issues (code quality concerns).
```
