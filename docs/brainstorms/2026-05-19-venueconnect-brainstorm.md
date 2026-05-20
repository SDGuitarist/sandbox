---
title: VenueConnect -- Three-Sided Venue Booking & Settlement Platform
date: 2026-05-19
status: complete
type: brainstorm
feed_forward:
  risk: "RBAC permission boundaries and booking state machine are the two novel patterns most likely to produce cross-section contradictions in the spec"
  verify_first: true
---

# VenueConnect Brainstorm

## What We're Building

A three-sided platform for the live music industry connecting venues, musicians,
and promoters. Venues list rooms and availability windows. Musicians search and
request bookings. Promoters create events spanning venues. After shows, the
system generates settlement sheets calculating who gets what (the #1 pain point
currently solved with spreadsheets).

**Target users:** Small/mid-size live music venues, independent musicians, local
promoters. Single-instance deployment, multi-role auth.

**Stack:** Flask + SQLite + Jinja2 + Bootstrap 5 (sandbox standard, same as
runs 046-048).

**Build target:** 22-25 agent swarm (biggest to date; run 048 was 20 agents).

## Why This Approach

### Three-Role RBAC on a Single User Table

**Decision:** Single `users` table with a `role` column (`venue_manager`,
`musician`, `promoter`). No separate role tables, no many-to-many user-role
join.

**Why:** Simplest model that works for MVP. Each user IS one role. A person who
is both a musician and a promoter creates two accounts. This avoids the
complexity of role-switching UI, per-role session state, and multi-role
permission resolution. Prior builds (046-048) used single-role auth
successfully.

**Decorator chain:** `@login_required` -> `@role_required('venue_manager')`.
Both decorators set `g.user` from session. `role_required` checks
`g.user['role']` and returns 403 if mismatched.

**Rejected:** Many-to-many user-role table. Adds UI complexity (role switcher),
session ambiguity (which role is active?), and permission resolution complexity
far beyond MVP needs.

### Availability Windows + Conflict Detection

**Decision:** An `availability_windows` table with `room_id`, `day_of_week`
(0-6), `start_time`, `end_time` for recurring weekly availability. Bookings
reference a specific `event_date` + `start_time`/`end_time`. Conflict detection
query: `WHERE room_id = ? AND event_date = ? AND start_time < ? AND end_time > ?`
(overlapping range check).

**TOCTOU prevention:** Wrap the check-then-insert in a single
`get_db(immediate=True)` block (BEGIN IMMEDIATE). This serializes concurrent
requests at the SQLite level. (Lesson from recipe-organizer, FC6/TOCTOU.)

**Why:** SQLite date/time functions handle this cleanly. No need for a calendar
library. The overlap query is a standard range intersection check. Weekly
recurring windows are the simplest model that matches how venues actually
think ("we're available Fri-Sat 7pm-2am").

**Rejected:** 
- Slot-based system (15-min slots) -- over-engineered for live music where
  events are typically 3-6 hour blocks.
- Full datetime range table -- adds complexity without benefit for weekly
  patterns.

### 7-State Booking Lifecycle (State Machine)

**Decision:** Dictionary-based state machine with guard functions. No class
hierarchy.

```
TRANSITIONS = {
    'available':  ['requested'],
    'requested':  ['confirmed', 'available'],   # confirm or reject (back to available)
    'confirmed':  ['advanced', 'available'],     # advance payment or cancel
    'advanced':   ['performed', 'available'],    # show happened or cancel
    'performed':  ['settled'],                   # settlement created
    'settled':    ['paid'],                      # payment confirmed
    'paid':       []                             # terminal state
}
```

**Guard conditions per transition:**
- `requested -> confirmed`: only venue_manager who owns the venue
- `confirmed -> advanced`: advance payment amount recorded (cents > 0)
- `performed -> settled`: settlement sheet must be created first
- `settled -> paid`: only venue_manager marks as paid
- Any state -> `available` (cancel): only venue_manager or the requesting musician

**Implementation:** A single `advance_booking_state(booking_id, new_state, actor_user_id)` function in models.py that:
1. Loads current state
2. Checks new_state is in TRANSITIONS[current_state]
3. Runs guard function for the transition
4. Updates state + creates audit trail row
5. Creates notification for affected parties
6. Does NOT commit (caller commits) -- FC29 lesson

**Why:** A dict lookup is simpler than a class hierarchy and more explicit than
if/elif chains. Guard functions are easy to test. The "does NOT commit" pattern
prevents FC29 (transaction boundary ambiguity).

**Rejected:** Python `transitions` library -- adds an external dependency for
what's a simple dict + 5 guard functions. State pattern (class per state) --
over-engineered for 7 states with simple guards.

### Settlement Calculation Engine

**Decision:** Support three deal types on each booking:

1. **Guarantee:** Musician gets a fixed amount regardless of door revenue.
   Venue covers the guarantee from door + bar revenue.
2. **Door split:** Musician gets X% of door revenue after expenses. Venue
   keeps (100-X)%. Typical: 70/30 or 80/20.
3. **Hybrid:** Guarantee minimum OR door split percentage, whichever is higher.

**Settlement sheet fields (all integer cents):**
- `door_revenue_cents` -- total ticket sales
- `guarantee_cents` -- fixed amount (if applicable)
- `door_split_pct` -- musician's percentage (0-100)
- `promoter_fee_pct` -- promoter's cut (0-30 typical)
- `tax_pct` -- local tax percentage
- `expenses_cents` -- sound/lighting/misc deducted before split
- Computed: `musician_payout_cents`, `venue_share_cents`, `promoter_fee_cents`, `tax_amount_cents`

**Calculation logic:**
```
net_door = door_revenue_cents - expenses_cents
musician_share_from_door = net_door * door_split_pct / 100
musician_payout = max(guarantee_cents, musician_share_from_door)  # hybrid
promoter_fee = door_revenue_cents * promoter_fee_pct / 100
venue_share = door_revenue_cents - musician_payout - promoter_fee - tax
```

**Integer cents everywhere.** Display with `|dollars` Jinja filter. Form prefill
with manual `cents / 100` conversion. (Lessons from personal-finance-tracker,
invoice-crm.)

**Rejected:** Float-based money (rounding errors). Single deal type only
(too restrictive -- venues use all three models).

### PDF Generation with ReportLab

**Decision:** ReportLab (pure Python). No system dependencies needed.

**Settlement PDF contents:**
- Header: venue name, event date, room
- Parties: musician name, promoter name (if any)
- Financial breakdown table: door revenue, expenses, split calculation
- Signature lines (blank, for wet signatures)
- Footer: generated date, VenueConnect branding

**Why:** ReportLab is a single `pip install`, pure Python, well-documented.
WeasyPrint requires system-level dependencies (cairo, pango) that complicate
deployment and sandbox builds.

### FTS5 Full-Text Search

**Decision:** FTS5 virtual table `venues_fts` with columns: `name`, `location`,
`description`, `genre_tags`. Kept in sync via INSERT/UPDATE/DELETE triggers on
the `venues` table. Search route uses `MATCH` query with `rank`.

**Proven pattern** from solopreneur-command-center (run 047). FTS5 + triggers
is the sandbox standard for search.

### In-App Notification System

**Decision:** A `notifications` table with `user_id`, `message`, `link`,
`is_read` (boolean), `created_at`. A `create_notification(user_id, message, link)`
helper called by the state machine after each transition.

**Who gets notified on each transition:**
- `requested`: venue_manager (new booking request)
- `confirmed`: musician (your booking was confirmed)
- `available` (rejection/cancel): musician or venue_manager (depending on who cancelled)
- `advanced`: musician (advance payment recorded)
- `performed`: venue_manager + musician (show marked as performed)
- `settled`: musician + promoter (settlement sheet ready)
- `paid`: musician (payment confirmed)

**Badge count:** An API endpoint `/api/notifications/unread-count` returns JSON
for a navbar badge (polled on page load, not WebSocket).

### Chart.js Analytics Dashboards

**Decision:** One dashboard per role with role-specific charts:

**Venue manager:**
- Revenue by month (bar chart)
- Occupancy rate by room (bar chart)
- Genre distribution of bookings (doughnut)

**Musician:**
- Earnings by month (bar chart)
- Venues played (horizontal bar)
- Booking success rate (doughnut: confirmed vs rejected)

**Promoter:**
- Event revenue by month (bar chart)
- Settlement totals by venue (horizontal bar)
- Event count by status (doughnut)

**Data source:** SQL aggregate queries in route handlers, passed as JSON to
Chart.js via `<script>` tags in templates (no separate API needed).

### Agent Split Strategy (Target: 25 Agents)

Vertical blueprint split -- each agent owns a Flask blueprint (routes +
templates) or a shared module. File ownership is strict: no two agents write
to the same file.

| # | Agent Name | Owns | Blueprint Prefix |
|---|-----------|------|-----------------|
| 1 | scaffold | app factory, config, base layout, static, error handlers | - |
| 2 | auth | register, login, logout, role decorators | /auth |
| 3 | models | schema.sql, db.py, models.py (all model functions) | - |
| 4 | venue-crud | venue CRUD routes + templates | /venues |
| 5 | room-crud | room/stage CRUD routes + templates | /rooms |
| 6 | availability | availability window CRUD, calendar view, conflict query | /availability |
| 7 | booking-create | musician: browse, view availability, create request | /bookings (musician-facing) |
| 8 | booking-manage | venue manager: view requests, approve/reject | /bookings/manage |
| 9 | booking-lifecycle | state machine dict, guards, advance_state() | (in models, but separate agent) |
| 10 | promoter-events | promoter: create/manage events across venues | /events |
| 11 | ticket-tiers | ticket tier CRUD for events | /tickets |
| 12 | settlement-engine | calculation functions (pure logic, no routes) | - |
| 13 | settlement-views | settlement list, detail, create, approve | /settlements |
| 14 | settlement-pdf | ReportLab PDF generation endpoint | /settlements/pdf |
| 15 | search | FTS5 virtual table, triggers, search routes | /search |
| 16 | notifications | notification model helpers, create_notification() | - |
| 17 | notification-views | notification list, badge count API, mark-read | /notifications |
| 18 | analytics-venue | venue manager Chart.js dashboard | /analytics/venue |
| 19 | analytics-musician | musician Chart.js dashboard | /analytics/musician |
| 20 | analytics-promoter | promoter Chart.js dashboard | /analytics/promoter |
| 21 | dashboard-venue | venue manager home (upcoming, pending, stats) | /dashboard |
| 22 | dashboard-musician | musician home (upcoming gigs, search shortcut) | /dashboard |
| 23 | dashboard-promoter | promoter home (events, settlements, preview) | /dashboard |
| 24 | seed | seed data generator for all tables, demo users | - |
| 25 | tests | smoke tests for all routes | - |

**Data ownership concern:** Agents 9 (booking-lifecycle) and 3 (models) both
touch models.py. Resolution: booking-lifecycle owns ONLY
`app/booking_lifecycle.py` (a separate module imported by models.py). The models
agent owns `app/models.py` and imports from booking_lifecycle. This prevents
FC3 (dead wiring) by making the import explicit in the spec.

**Dashboard collision concern:** Agents 21-23 all register at `/dashboard`.
Resolution: the scaffold agent's root route checks `g.user['role']` and redirects
to `/dashboard/venue`, `/dashboard/musician`, or `/dashboard/promoter`. Each
dashboard agent uses a distinct prefix.

## Key Decisions Summary

| Decision | Choice | Why |
|----------|--------|-----|
| RBAC model | Single role column on users table | Simplest; no role-switching UI needed |
| Calendar | Weekly availability windows + overlap query | Matches venue mental model |
| Conflict prevention | BEGIN IMMEDIATE (get_db immediate=True) | SQLite-level serialization (TOCTOU) |
| State machine | Dict of transitions + guard functions | Explicit, testable, no external deps |
| Settlement types | Guarantee / door split / hybrid | Covers all real-world deal structures |
| Money storage | Integer cents + |dollars filter | Proven pattern from 3 prior builds |
| PDF library | ReportLab | Pure Python, no system deps |
| Search | FTS5 + triggers | Proven pattern from run 047 |
| Notifications | Table + helper + poll | Simplest; no WebSocket complexity |
| Charts | Chart.js via inline JSON | No separate API needed |
| Agent count | 25 | Vertical blueprint split, strict ownership |
| Transaction boundaries | "does NOT commit" on all shared functions | FC29 prevention |

## Open Questions

None -- all key decisions resolved. The plan phase will need to flesh out:
1. Exact schema DDL for all tables
2. Complete endpoint registry with url_for names and form field names
3. Cross-boundary wiring table
4. Data ownership table
5. Coordinated behaviors table

## Feed-Forward

- **Hardest decision:** The agent split for 25 agents. Three agents (21-23) all
  serve "dashboard" functionality but for different roles. The booking blueprint
  is split across three agents (create, manage, lifecycle). Getting the file
  ownership boundaries right in the spec -- especially for the state machine
  (agent 9) which is called by booking-manage (agent 8), settlement-views
  (agent 13), and notification dispatch (agent 16) -- is the highest-risk
  surface for FC3 (dead wiring) and FC29 (transaction boundary) bugs.

- **Rejected alternatives:** (1) WeasyPrint for PDF -- requires system deps.
  (2) Many-to-many role table -- over-engineered for MVP. (3) Slot-based
  calendar -- over-engineered for 3-6 hour music events. (4) WebSocket
  notifications -- unnecessary complexity. (5) `transitions` library for state
  machine -- external dep for a simple dict.

- **Least confident:** Calendar conflict detection under concurrent requests.
  The BEGIN IMMEDIATE approach serializes at the SQLite level, but the spec
  must be very precise about the transaction boundary: the availability check
  AND the booking insert must happen in the same BEGIN IMMEDIATE block. If
  the spec splits these across functions without explicit "does NOT commit"
  annotations, agents will add their own commits and break atomicity (FC29).
  The plan MUST specify this as a single atomic operation with explicit
  transaction boundary.

## Refinement Findings

**Gaps found:** 5 (all addressable in plan phase)

1. **Flow-trace reviewer mandatory** (from run 048) -- VenueConnect has 4+ multi-file traces (notification badge JS->Python->DB, Chart.js inline JSON, settlement PDF link, booking state POST->lifecycle->notification). Plan must include flow-trace reviewer in review phase.

2. **Coordinated Behaviors table required** (from project-tracker, run 047) -- 25 agents with multiple write operations triggering `create_notification()`. Plan must include a Coordinated Behaviors table mapping every write operation to its expected flash message + notification call.

3. **Template Render Context section must be ~20% of spec** (from runs 046-048) -- 15 template-producing agents need exact variable names in every `render_template()` call prescribed in the spec. Omitting this section is the leading cause of silent missing-data bugs.

4. **Form field names must be prescribed** (from run 046, FC9) -- VenueConnect has 6+ form-heavy flows. Test agent (25) and route agents must converge on identical field names. Every form's WTForms field names and `request.form.get()` keys must be in the endpoint registry.

5. **Novel patterns need prescriptive code blocks in agent briefs** (from run 048) -- The `advance_booking_state()` call pattern must be embedded directly in the briefs of agents 8, 13, and 16 (not just referenced). Run 048 showed ~5% agent failure rate when agents generate code from descriptions rather than copying spec code blocks.
