---
title: "CoWorkFlow -- 22-Agent Coworking Space Manager Swarm Build"
date: 2026-05-22
run_id: "055"
project: coworkflow
agents: 22
stack: "Flask + SQLite + Jinja2 + Bootstrap 5"
build_method: swarm
status: complete
tags: [flask, sqlite, swarm, transaction-safety, booking-system, feed-forward, csrf]
---

# CoWorkFlow -- 22-Agent Coworking Space Manager Swarm Build

## Problem

Build a single-admin coworking space management system (members, membership
plans, desks, meeting rooms, desk bookings, room bookings, billing/invoices,
payments, amenities) using a 22-agent swarm with vertical model/route
ownership split.

The Feed-Forward risk from the plan: "Desk booking conflict logic for
AM/PM/full overlap. No UNIQUE constraint -- relies entirely on BEGIN
IMMEDIATE + application logic. Room bookings have a partial UNIQUE index
as safety net; desk bookings do not."

## Solution

22-agent swarm with strict file ownership: 1 core agent (app factory,
db, auth, filters, schema), 1 layout agent (base template, CSS), 1 auth
agent, 9 model agents (one per domain entity), and 10 route agents (one
per blueprint). Zero merge conflicts, 22/22 agents committed, 21/21
smoke tests pass.

### Key Design Decisions

1. **Single admin auth** -- no user table, password from env var,
   `@login_required` decorator on all non-auth routes.
2. **AM/PM/full desk booking blocks** -- 3-way overlap matrix: `full`
   conflicts with any block, `am` conflicts with `am|full`, `pm` with
   `pm|full`. Verified correct by flow-trace review.
3. **30-min room slots** -- single slot per booking, partial UNIQUE
   index `(room_id, booking_date, slot_start) WHERE status != 'cancelled'`
   provides DB-level backstop.
4. **BEGIN IMMEDIATE + try/except/ROLLBACK** -- both booking models use
   the full pattern prescribed by the GymFlow (Run 054) lesson. No
   uncovered exception paths.
5. **Integer cents for all money** -- `round(float(val) * 100)` with
   `math.isfinite()` guards on all 5 money parsing routes.
6. **Manual invoice status** -- invoice status (pending/paid/overdue/
   cancelled) is managed manually by the admin. Payments are linked to
   invoices but do not auto-update status.

## What Went Wrong

### P1-1: CSRF Token Missing Parentheses in Plans Templates

The plans agent used `{{ csrf_token }}` instead of `{{ csrf_token() }}`
in `plans/form.html` and `plans/list.html`. In Jinja2, this renders the
function object string, not the token. All plan create/edit/delete
operations were broken.

**Root cause:** FC1 (naming divergence). The plans agent diverged from
the template pattern used by all 21 other agents. The spec showed the
CSRF token pattern in examples but the plans agent either missed the
parentheses or interpreted `csrf_token` as a variable rather than a
function call.

**Fix:** Added `()` to both `csrf_token` references. Trivial 2-line fix.

**Lesson:** CSRF token syntax should be in the Coordinated Behaviors
section as a mandatory pattern: `{{ csrf_token() }}` with parentheses.
Templates are a high-divergence surface because agents don't see each
other's templates during the swarm.

### Feed-Forward Risk Confirmed: desk_bookings Missing UNIQUE Constraint

The plan's "least confident" item was the desk booking conflict logic
without a UNIQUE constraint. The flow-trace review confirmed:

1. The overlap logic IS correct -- all 3 block combinations are covered.
2. BEGIN IMMEDIATE + busy_timeout=5000ms IS sufficient for concurrency.
3. BUT there is no DB-level backstop if a future code path bypasses the
   BEGIN IMMEDIATE guard.

The room_bookings table has a partial UNIQUE index; desk_bookings does
not. A simple UNIQUE index on `(desk_id, booking_date, block)` would
prevent exact duplicates but wouldn't capture the am/pm/full overlap
semantics. A trigger-based solution was considered and rejected as
overengineered for a single-admin tool.

**Decision:** Accept the risk. Document as known limitation. The single
code path (create_desk_booking) correctly uses BEGIN IMMEDIATE.

### Invoice/Payment Status Gap (P1-2, Deferred)

Payments are stored linked to invoices, but creating/deleting a payment
never updates the invoice status. This means:
- Fully-paid invoices show as "pending" until manually updated
- Deleted payments don't revert invoice status
- The payment dropdown shows all pending invoices regardless of payment state

This is a spec gap, not a code bug -- the spec doesn't require auto-status
updates. Fixing requires transaction wrapping and partial payment logic.

## What Went Right

### Zero Merge Conflicts at 22 Agents

Strict vertical ownership (one model file + one route file per agent)
eliminated merge conflicts entirely. The only assembly fix was FC1
(plan templates using layout.html instead of base.html -- a naming
issue, not a conflict).

### Feed-Forward System Worked

The plan's "least confident" item (desk booking overlap logic) was
verified correct by the flow-trace reviewer. The BEGIN IMMEDIATE
pattern was correctly applied to both booking models, following the
GymFlow (Run 054) lesson about try/except/ROLLBACK wrappers.

### All Prior Lessons Applied

- FC29 (GymFlow): try/except/ROLLBACK wrapper applied correctly
- FC4 (VenueConnect): NaN/Inf guards on all money parsing
- FC40 (GigSheet): PRAGMA per-connection (busy_timeout, WAL, foreign_keys)
- FC37: All 22 agents committed successfully
- FC1: Export Names Table prevented naming divergence (except CSRF token)

### Consistent Validation Patterns

All 11 route files follow the same validation pattern:
- `int()` parsing with try/except for IDs
- `strip()` on all string inputs
- `strptime()` for date validation
- `math.isfinite()` for money fields
- Entity existence checks before writes
- `sqlite3.IntegrityError` caught for UNIQUE violations

## Patterns for Future Builds

### CSRF Token Must Be in Coordinated Behaviors

Add to Coordinated Behaviors table:
```
| Pattern | Syntax | Files |
|---------|--------|-------|
| CSRF token | {{ csrf_token() }} -- WITH parentheses | All form templates |
```

### Desk Booking Overlap Cannot Use Simple UNIQUE Index

The am/pm/full overlap semantics mean a simple UNIQUE index on
`(desk_id, booking_date, block)` is insufficient. A `full` booking
must block `am` and `pm`, but they have different block values.
Options for future builds:
1. **Normalize blocks** -- store individual half-day rows. A "full"
   booking creates two rows (am + pm). Then a simple UNIQUE index
   works. Trade-off: delete/cancel must handle both rows.
2. **Trigger-based** -- CREATE TRIGGER that rejects inserts with
   overlapping blocks. More complex but preserves the current schema.
3. **Accept app-level only** -- current approach. Simplest, works
   for single-admin tools.

### Invoice Auto-Status Pattern

For builds where invoice/payment lifecycle matters, add to the spec:
```python
def create_payment(conn, invoice_id, ...):
    try:
        conn.execute('BEGIN IMMEDIATE')
        # INSERT payment
        # SELECT SUM(amount_cents) for invoice
        # If sum >= invoice.amount_cents: UPDATE status='paid'
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

## Feed-Forward

- **Hardest decision:** Deferring the invoice auto-status fix. It's a
  real data integrity gap, but the spec doesn't require it and adding
  it means scope expansion with transaction complexity.
- **Rejected alternatives:** Partial UNIQUE index for desk bookings
  (insufficient for am/pm/full overlap), auto-status on payments
  (scope expansion), trigger-based booking validation (overengineered).
- **Least confident:** Whether the CSRF `{{ csrf_token }}` (without
  parens) actually breaks in Flask-WTF or if there's a fallback. The
  fix is trivial and risk-free regardless.
