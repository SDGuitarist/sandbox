---
date: 2026-05-21
topic: coworking-space-manager
---

# CoWorkFlow -- Coworking Space Manager

## What We're Building

A single-location coworking space management system for one admin user. Hot
desks bookable by date (half-day/full-day), meeting rooms bookable in 30-minute
slots, membership plans, billing, payments, and amenities tracking. Built in
Flask + SQLite + Jinja2 with Bootstrap 5 for UI.

This is Run 055 -- the first build to validate the infrastructure fixes from
Run 054: consistency checker Check #7 (ON DELETE FK parsing), gate-verification
artifact (Step 9w.7), and flow-trace reviewer Write tool.

Admin-only tool -- no member self-service portal, no public-facing pages, no
online payments. The admin logs in and manages everything.

## Why This Approach

**Approach chosen: Hot desks + meeting rooms with slot-based booking.**

Considered alternatives:
1. **Assigned desks + meeting rooms** -- rejected because assigned desks remove
   the most interesting scheduling logic (availability checking, capacity
   management) while adding administrative state. Less useful as an
   infrastructure validation build.
2. **Zones (hot desk + dedicated + private offices)** -- rejected because three
   tiers add tier-matrix complexity without proportional validation value.
   Better as a later run once the new gates have more real-world validation.
3. **Core 8 + amenities + events** -- rejected because events pull the app back
   toward GymFlow's class-scheduling shape, increasing overlap and reducing
   test independence. Amenities alone gives enough cross-boundary wiring
   novelty.

## Key Decisions

### 1. Single Admin Auth (No Roles)
One admin user. Login with password from environment variable
(`ADMIN_PASSWORD`). No user table, no registration, no roles. Session-based
auth with `@login_required` decorator. Logout via POST (CSRF-protected).

**Rationale:** Same proven pattern as GymFlow. Single manager runs the space.

### 2. Hot Desk Booking Model
Desks are shared resources with no permanent assignment. Members book any
available desk for a date, choosing half-day (AM/PM) or full-day. No
arbitrary time ranges -- discrete slots only.

**Rationale:** Keeps the booking model discrete, easier to spec and implement
correctly. Avoids overlap-detection complexity. Maps to GymFlow's constrained
availability pattern.

### 3. Meeting Room 30-Minute Slots
Meeting rooms bookable in 30-minute increments only. Bookings must align to
slot boundaries (9:00, 9:30, 10:00, etc.). Availability checked per slot.
Booking creation must be transaction-safe to prevent double-booking.

**Rationale:** Discrete slots avoid overlap-detection queries. 30 minutes is
the industry standard. Compound uniqueness key (room_id, booking_date,
slot_start) exercises the BEGIN IMMEDIATE pattern with higher complexity than
GymFlow's single-key attendance check.

### 4. MVP Domains (9 total)
Members, membership plans, desks, meeting rooms, desk bookings, room bookings,
billing/invoices, payments, amenities.

**Rationale:** Core 8 gives the operational spine. Amenities adds one
cross-boundary domain (rooms/desks have amenities) without bloating scope.
Events, community board, and multi-tier plans deferred to Phase 2.

### 5. Integer Cents for Money
All monetary values stored as INTEGER cents. Displayed with `{{ value|dollars }}`
filter. Parsed with `round(float(val) * 100)` and NaN/Inf guards.

**Rationale:** Proven pattern across 5+ Flask builds. No violations found.

### 6. Agent Split (~20-22 agents)
Vertical model/route split. Estimated: 3 infrastructure (core, layout, auth) +
9 model agents + 9 route agents + 1 dashboard = ~22 agents.

**Rationale:** Proven at 20 (Client Music Planner), 25 (VenueConnect), 26
(GymFlow), 29 (RestaurantOps), 31 (GigSheet). Zero merge conflicts at every
scale with vertical ownership.

## Infrastructure Validation Targets

This build validates 3 infrastructure fixes from Run 054:

1. **Consistency checker Check #7** -- ON DELETE FK parsing with multiline
   extraction, mixed-FK grouping, NO ACTION/omitted handling. The coworking
   schema should exercise mixed FKs (e.g., member delete with RESTRICT
   bookings + SET NULL amenity preferences).
2. **Gate-verification artifact (Step 9w.7)** -- The new artifact-based gate
   enforcement. Both pre-swarm gates must write CLEARED to
   `gate-verification.md` before agents spawn.
3. **Flow-trace reviewer Write tool** -- The reviewer now has Write + reports
   directory input. Validates that the report is written to disk, not lost.

## Open Questions

(None -- all key decisions resolved during brainstorm dialogue.)

## Feed-Forward

- **Hardest decision:** Scoping to 9 domains. Amenities adds the many-to-many
  exercise without events' scheduling complexity. Events is Phase 2.
- **Rejected alternatives:** Assigned desks (removes scheduling), zones
  (tier complexity), events (GymFlow overlap), community board (low value).
- **Least confident:** Room booking double-booking prevention. Meeting rooms
  book in 30-minute slots, so the booking path must atomically verify
  (room_id, booking_date, slot_start) availability and create the booking
  without race conditions. This is FC29 territory again: the spec must
  prescribe the exact transaction pattern, error-handling wrapper, and
  uniqueness invariant so agents do not diverge. Secondary validation target:
  mixed FK behavior on member delete (RESTRICT bookings + SET NULL amenity
  preferences) -- exercises the new Check #7 edge case.
