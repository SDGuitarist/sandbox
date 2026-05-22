---
date: 2026-05-21
topic: gym-manager
---

# GymFlow -- Gym/Fitness Center Manager

## What We're Building

A standalone single-location gym management system for one admin user. Covers
the full operational lifecycle: member registration, trainer management, class
scheduling, attendance tracking, equipment inventory, billing, and fitness
assessments. Built in Flask + SQLite + Jinja2 with Bootstrap 5 for UI.

This is an admin-only tool -- no member self-service portal, no public-facing
pages, no online payments. The admin logs in and manages everything.

## Why This Approach

**Approach chosen: Admin-only CRUD with model/route vertical agent split.**

Considered alternatives:
1. **Multi-role system** (admin + trainer + member logins) -- rejected because
   it triples auth complexity without adding MVP value. A single admin can
   manage a small gym. Member portal is Phase 2.
2. **API-first with separate frontend** -- rejected because Jinja2 server-side
   rendering is simpler, proven at 29-31 agent scale, and matches the sandbox
   standard stack.
3. **Fewer agents with fat modules** -- rejected because model/route split is
   validated at 29 agents (RestaurantOps) and 31 agents (GigSheet) with zero
   merge conflicts. More agents = better parallelism.

## Key Decisions

### 1. Single Admin Auth (No Roles)
One admin user. Login with password from environment variable
(`ADMIN_PASSWORD`). No user table, no registration, no roles. Session-based
auth with `@login_required` decorator. Logout via POST (CSRF-protected).

**Rationale:** Simplest auth model. Gym has one manager using the system.
Multi-user is Phase 2.

### 2. Schedule Model: Individual Class Sessions (Not Recurring)
Each row in `class_schedules` is a single session with a specific date and
time. No recurrence engine. Admin creates sessions manually or uses a "copy
week" bulk action.

**Rationale:** Recurring schedules need a generation engine (cron-like) which
adds complexity. Individual sessions are simpler to query, display, and
manage attendance against. The "copy week" action covers the practical need.

### 3. Money as Integer Cents
All monetary values (membership price, payment amount, equipment cost,
maintenance cost) stored as INTEGER cents in SQLite. Jinja2 `|dollars` filter
for display. Form parsing: `round(float(value) * 100)`.

**Rationale:** Proven pattern from Invoice & CRM (FC33 prevention). Avoids
floating-point rounding errors.

### 4. Attendance: Class-Based and Open Gym
Two attendance types:
- **Class attendance**: linked to a specific `class_schedule_id`. Capacity
  check with BEGIN IMMEDIATE (FC29).
- **Open gym**: `class_schedule_id` is NULL. No capacity check. Just
  records member was at the gym.

**Rationale:** Gyms track both structured class attendance and general
facility usage. Keeping them in one table with a nullable FK is simpler
than two tables.

### 5. Fitness Assessments: Simple Metrics Log
Each assessment is a row with: member_id, date, trainer_id (nullable),
weight, height, body_fat_pct, bmi (computed), resting_heart_rate, notes.
No progress charts -- just a history table. Dashboard shows latest vs
previous for a member.

**Rationale:** Progress visualization is Phase 2. Recording metrics is the
core need.

### 6. Equipment + Maintenance as Separate Domains
Equipment has status (available/in_use/maintenance/retired). Maintenance
is a separate log table linked to equipment. Maintenance records track
cost, date, who performed it, and next due date.

**Rationale:** Separate tables allow different agents to own each domain.
Maintenance log is append-only, equipment status is mutable.

### 7. Billing: Manual Invoice Creation
Admin creates invoices manually for each member. No automated billing cycle.
Invoice has: member_id, amount_cents, description, due_date, status
(pending/paid/overdue/cancelled). Payments link to invoices. Multiple
payments can apply to one invoice (partial payments).

**Rationale:** Automated billing needs cron + email + payment gateway, all
out of scope. Manual invoicing covers MVP.

### 8. Agent Split: 26 Agents (Model/Route Vertical)
Proven pattern from RestaurantOps (29 agents) and GigSheet (31 agents):

**Infrastructure (3):**
- `core` -- app factory, db.py, auth decorator, Jinja filters
- `layout` -- base.html, style.css, navbar, static assets
- `auth` -- login/logout routes + templates

**Model agents (11):**
- `member_models`, `trainer_models`, `membership_type_models`
- `class_type_models`, `schedule_models`, `attendance_models`
- `equipment_models`, `maintenance_models`
- `billing_models`, `payment_models`, `assessment_models`

**Route agents (12):**
- `member_routes`, `trainer_routes`, `membership_type_routes`
- `class_type_routes`, `schedule_routes`, `attendance_routes`
- `equipment_routes`, `maintenance_routes`
- `billing_routes`, `payment_routes`, `assessment_routes`
- `dashboard_routes`

### 9. Database Tables (11)

| Table | Key Columns | Notes |
|-------|-------------|-------|
| membership_types | name, duration_months, price_cents, is_active | Reference table |
| members | name, email, phone, membership_type_id, status, join_date | FK to membership_types |
| trainers | name, email, phone, specializations, bio, hire_date, status | Independent |
| class_types | name, description, duration_minutes, default_capacity | Reference table |
| class_schedules | class_type_id, trainer_id, session_date, start_time, end_time, room, capacity | FK to class_types, trainers |
| attendance | member_id, class_schedule_id (nullable), check_in_time, check_out_time, type | FK to members, class_schedules |
| equipment | name, category, serial_number, purchase_date, purchase_price_cents, status, location | Independent |
| maintenance_log | equipment_id, description, maintenance_date, cost_cents, performed_by, next_due_date | FK to equipment |
| invoices | member_id, amount_cents, description, due_date, status | FK to members |
| payments | invoice_id, amount_cents, payment_date, payment_method, reference_number | FK to invoices |
| fitness_assessments | member_id, trainer_id, assessment_date, weight_kg, height_cm, body_fat_pct, notes | FK to members, trainers |

### 10. Dashboard Scope
- Today's class schedule with attendance counts
- Active members count, new this month
- Revenue this month (sum of payments)
- Equipment needing maintenance (next_due_date <= today)
- Recent check-ins (last 10)

## Constraints from Prior Builds

- CSRF on ALL POST forms (flask-wtf CSRFProtect)
- SECRET_KEY + ADMIN_PASSWORD from environment
- PRAGMA WAL + busy_timeout=5000 + foreign_keys=ON in every get_db()
- BEGIN IMMEDIATE for attendance capacity check
- Money as integer cents everywhere
- Explicit `git add` + `git commit` in every agent brief (FC37)
- 6 mandatory spec coverage sections for completeness gate
- Logout via POST (not GET)
- SESSION_COOKIE_SECURE = not app.debug
- email-validator in requirements.txt if using WTForms Email()
- No `python3 -c` for smoke tests (FC8)
- isolation_level=None in sqlite3.connect() for manual transaction control
- Skip CSP header for MVP (avoids FC38 CDN mismatch with Bootstrap CDN)
- Trailing slash on all navbar links and smoke test URLs for blueprint roots
- Explicit `with get_db() as db:` usage example in spec (not plain function call)

## Open Questions

None -- all decisions resolved for MVP scope.

## Refinement Findings

**Gaps found:** 4 (from cross-referencing solution docs)

1. **isolation_level=None required in get_db()** -- Python's default
   `isolation_level=""` creates implicit transactions that conflict with
   manual `BEGIN IMMEDIATE`. Must set `isolation_level=None` in sqlite3.connect().
   (Source: RestaurantOps run 052)

2. **CSP-CDN mismatch risk** -- If core agent adds CSP header with
   `script-src 'self'` and layout agent loads Bootstrap from CDN, all JS
   breaks silently. Spec must prescribe CDN domains in CSP or skip CSP
   entirely for MVP. (Source: GigSheet run 050, FC38)

3. **Trailing slash on blueprint root routes** -- Blueprint routes registered
   at `/prefix` serve root as `/prefix/`. Smoke tests and navbar links must
   include trailing slash to avoid 308 redirects. (Source: VenueConnect run 049)

4. **Context manager usage example mandatory** -- Spec must show explicit
   `with get_db() as db:` pattern. Without it, all 23 consuming agents will
   write `db = get_db()` (wrong). (Source: Flask Acid Test)

## Feed-Forward

- **Hardest decision:** Schedule model -- individual sessions vs recurring.
  Individual sessions are simpler but mean more admin work. The "copy week"
  action mitigates this without adding a recurrence engine.
- **Rejected alternatives:** Multi-role auth (too complex for MVP), API-first
  (unnecessary for admin-only tool), automated billing (needs cron/email/gateway).
- **Least confident:** Attendance capacity check with BEGIN IMMEDIATE -- this
  is the only concurrent-write scenario in a single-admin app, but the pattern
  is proven from RestaurantOps. The real risk is whether the spec prescribes
  the transaction boundary clearly enough for the attendance_models agent
  vs the attendance_routes agent (FC29 territory).

## Next Steps

→ `/workflows:plan` for full shared interface spec with 26-agent assignment
