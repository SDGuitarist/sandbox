---
title: "CoWorkFlow Deferred Fixes Batch (Run 056)"
date: 2026-05-22
category: deferred-fix-batch
tags:
  - flask
  - sqlite
  - coworkflow
  - deferred-fixes
  - invoice-status
  - desk-booking
  - brute-force
  - session-expiry
  - security-headers
  - overpayment
  - plan-id-validation
  - toctou
  - begin-immediate
module: payments, bookings, auth, members, security
symptom: >
  Seven deferred items from Run 055 remained unresolved: invoices stayed
  'pending' after payment (P1), desk bookings lacked a DB-level conflict
  trigger (P1), login had no brute-force throttling (P2), sessions never
  expired (P2), responses lacked security headers (P2), overpayment was
  possible due to TOCTOU race (P2), and plan_id accepted invalid FKs (P2).
root_cause: >
  Run 055's 22-agent swarm deferred these items because they crossed agent
  boundaries or required design decisions beyond the original spec. Invoice
  auto-status required payment-to-invoice cross-module wiring. The overpayment
  TOCTOU race existed because balance checks ran outside transactions. Security
  hardening was not assigned to any agent in the original spec.
severity: P1 (invoice auto-status, desk booking trigger), P2 (remaining 5)
status: resolved
---

# CoWorkFlow Deferred Fixes Batch (Run 056)

## Context

Run 055 built CoWorkFlow (22-agent swarm, Flask+SQLite coworking space manager).
Review deferred 2 P1s and 6 P2s (1 was a no-op). Run 056 fixed all 7 actionable
items through the full compound engineering cycle: brainstorm (2 refinements),
plan (deepened with 8 agents, 2 Codex reviews), work (9 commits), review (6 agents).

## The Seven Fixes

### Fix 1: Invoice Auto-Status on Payment (P1)

**Problem:** Invoices stayed 'pending' after full payment. Admin had to manually
set status to 'paid'.

**Root cause:** `create_payment()` was a pure INSERT with no cross-table side effects.

**Solution:** Wrapped `create_payment()` and `delete_payment()` in BEGIN IMMEDIATE
transactions that atomically check totals and update invoice status.

Key pattern:
```python
def create_payment(conn, ...) -> int | None:
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Reject paid/cancelled invoices (authoritative, TOCTOU-safe)
        if invoice['status'] in ('paid', 'cancelled'):
            conn.execute('ROLLBACK')
            return None
        # Reject overpayment
        if amount_cents > remaining:
            conn.execute('ROLLBACK')
            return None
        # INSERT + auto-update status if fully paid
        if new_total >= invoice['amount_cents']:
            conn.execute("UPDATE invoices SET status='paid' ...")
        conn.execute('COMMIT')
        return payment_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

**Tradeoff:** `delete_payment()` only reverts from 'paid' to 'pending', never
touches 'cancelled' or 'overdue'. Those are admin-set statuses.

### Fix 2: Overpayment Prevention (P2)

**Problem:** No guard prevented payment amounts exceeding the remaining balance.
TOCTOU race: two concurrent requests could both pass the check and both insert.

**Solution:** Two-layer defense. Route-level check is a UX gate (friendly flash).
Model-level check inside BEGIN IMMEDIATE is authoritative (TOCTOU-safe).

**Key insight:** The overpayment check MUST be inside the BEGIN IMMEDIATE block.
SQLite's RESERVED lock serializes concurrent writers, making the check-then-insert
atomic. A route-level-only check has a race window.

### Fix 3: Desk Booking Conflict Trigger (P1)

**Problem:** No DB-level constraint for desk booking conflicts. Direct DB
manipulation could bypass the app-level check.

**Solution:** BEFORE INSERT trigger with the compact conflict expression:
```sql
AND (NEW.block = 'full' OR block = 'full' OR block = NEW.block)
```
Covers all 7 conflict cases from the 3x3 block matrix. Only am+pm and pm+am
are allowed.

**Tradeoff:** No BEFORE UPDATE trigger added (no update-to-confirmed path exists).

### Fix 4: Security Headers (P2)

**Solution:** `@app.after_request` handler setting X-Content-Type-Options, X-Frame-Options,
Referrer-Policy, and HSTS. No CSP (requires auditing inline scripts).

### Fix 5: Brute-Force Login Protection (P2)

**Solution:** Single global counter (not per-IP dict). 5 failures in 60 seconds
triggers lockout. Counter resets on successful login or after window expires.

**Key decision:** Single counter eliminates the memory exhaustion P0 that a
per-IP dict would introduce. Acceptable because this is a single-password admin
tool. Limitations documented in code comments.

### Fix 6: Session Expiration (P2)

**Solution:** `PERMANENT_SESSION_LIFETIME = 8 hours` + `session.permanent = True`.
Sliding window (default Flask behavior). `session.clear()` before login prevents
session fixation.

### Fix 7: Plan_id FK Validation (P2)

**Problem:** Non-integer plan_id silently became None. Nonexistent numeric plan_id
triggered IntegrityError caught as "email already exists" (misleading).

**Solution:** Flash error on ValueError (non-integer). Validate plan exists via
`get_plan()` before INSERT. Separate snippets for create() and update() routes
because they have different conn timing and member object availability.

## Review Findings

6 review agents found 0 P0s, 3 introduced findings (all fixed):
1. Dead `cancelled` guard -- removed redundant condition
2. Rate limiter undocumented -- added limitation comments
3. Import order violation -- moved stdlib import to top

8 pre-existing findings deferred (conn.commit no-op, LIKE injection, etc.)

## Patterns for Future Builds

### Pattern 1: The TOCTOU Fence

Any check that gates a write must appear in TWO places:
1. **Route level (UX gate):** Friendly error messages. NOT authoritative.
2. **Model level (authoritative):** Inside BEGIN IMMEDIATE. TOCTOU-safe.

The route-level check prevents unnecessary transaction overhead. The model-level
check prevents races. Both are required.

### Pattern 2: The Constraint Stack

Every business constraint needs enforcement at the lowest possible layer AND
translation at the highest:
- **DB layer:** Trigger, CHECK, UNIQUE, FK -- prevents invalid data regardless
  of entry point. Error messages are opaque.
- **Model layer:** Python validation inside transaction -- specific error handling.
- **Route layer:** Pre-validation -- user-friendly flash messages.

### Pattern 3: Validation Ordering for Error Specificity

Pre-validate in this order: (1) type/format, (2) FK existence, (3) business rules,
(4) DB write. After steps 1-3, the only remaining IntegrityError cause is a race
condition on a unique constraint, so the error message can be precise.

### Pattern 4: Derived State Contract

If Agent A's table has a field computed from Agent B's table, the update logic
belongs to Agent B (the writer of the source data). Agent B's model function
must write to its own table AND update the derived field in a single transaction.

## Spec Improvements for Future Swarms

Three new mandatory spec sections would have prevented all 7 deferred items:

1. **Concurrency Contract** -- tag every write function as SERIAL-SAFE,
   NEEDS-BEGIN-IMMEDIATE, or TRIGGER-BACKED.
2. **Defense-in-Depth Matrix** -- map every constraint to app-level and DB-level
   enforcement with error translation.
3. **Derived State** -- declare every field computed from other tables with an
   explicit owning agent.

Plus fold security hardening into Coordinated Behaviors as a subsection, and
extend Input Validation Prescriptions with validation ordering.

## Related Solution Docs

- [CoWorkFlow Run 055](2026-05-22-coworkflow-22-agent-swarm-build.md) -- source of all deferred items
- [GymFlow Run 054](2026-05-21-gymflow-26-agent-swarm-build.md) -- BEGIN IMMEDIATE + try/except/ROLLBACK lesson
- [Invoice CRM Run 046](2026-05-19-invoice-crm-15-agent-swarm-build.md) -- payment-to-invoice auto-status prior art
- [Flask Swarm Acid Test](2026-04-07-flask-swarm-acid-test.md) -- foundational Flask swarm patterns
- [Ethics Toolkit Review Fix Cycle](2026-05-06-ethics-toolkit-review-fix-cycle.md) -- process model for fix batches

## Feed-Forward
- **Hardest decision:** Moving overpayment enforcement inside BEGIN IMMEDIATE
  (P0 TOCTOU fix). The data-integrity-guardian demonstrated a concrete race
  sequence that convinced us route-level-only was insufficient.
- **Rejected alternatives:** Per-IP dict for brute-force (memory exhaustion P0),
  UPDATE trigger for desk bookings (no UPDATE path exists), inlined SUM query
  (DRY violation when helper exists).
- **Least confident:** The three new mandatory spec sections (Concurrency Contract,
  Defense-in-Depth Matrix, Derived State). They add ~30 minutes of spec authoring
  time. Need to validate on the next swarm build whether they actually prevent
  deferred items or just add bureaucracy.
