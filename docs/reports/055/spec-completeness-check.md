# Pre-Swarm Spec Completeness Check

**Plan:** docs/plans/2026-05-21-coworkflow-plan.md
**Checked:** 2026-05-22

## Results

| Surface | Status | Findings |
|---------|--------|----------|
| Export Names (FC1) | PASS | 71 identifiers checked, 0 missing |
| Cross-Boundary Wiring (FC3) | PASS | 19 cross-boundary producer entries, 0 missing |
| Input Validation (FC4) | PASS | 26 qualifying routes, 0 unvalidated (1 fixed: POST /plans/delete) |
| Registration Points (FC5) | PASS | 11 blueprints, 0 unregistered |
| Transaction Contracts (FC29) | PASS | 23 write functions, 0 unannotated |
| Authorization Mode (FC35) | PASS | auth-protected routes covered by wildcard |

## Details

### Surface 1: Export Names (FC1) -- PASS

**Enumerated identifiers:**
- 60 model functions (across 9 model files)
- 12 `url_for()` endpoint targets
- 11 blueprint names
- Route paths: WARN (see below)

**Coverage table check:**
All 60 model functions appear in the Export Names table (lines 1053-1115).
All 12 `url_for()` targets appear (`auth.login_page`, `members.detail`,
`plans.list_plans`, `desks.list_desks`, `rooms.list_rooms`, `rooms.detail`,
`desk_bookings.detail`, `desk_bookings.new_booking`, `room_bookings.detail`,
`room_bookings.new_booking`, `billing.detail`, `payments.list_payments`,
`amenities.list_amenities` -- all present).
All 11 blueprint names appear (`auth`, `dashboard`, `members`, `plans`,
`desks`, `rooms`, `desk_bookings`, `room_bookings`, `billing`, `payments`,
`amenities`).

**WARN -- Route paths not listed as Export Names table entries.**
The Route Table has a valid "Path" column with 58 URL paths (all start with `/`).
None of these raw URL paths appear as entries in the Export Names table. The
table instead uses Flask endpoint names (e.g., `members.list_members`) which are
the cross-boundary identifiers used in `url_for()`. Since all cross-boundary
URL references use `url_for()` endpoint names (which ARE covered), this is a
documentation redundancy gap, not a functional cross-boundary omission.
Treating as WARN, not FAIL.

---

### Surface 2: Cross-Boundary Wiring (FC3) -- PASS

**Enumerated cross-boundary functions** (functions whose "Used By" column in the
Export Names table names a different agent):

| Cross-Boundary Function | Producer File | Verified in Wiring Table |
|------------------------|---------------|--------------------------|
| `get_all_members` | `app/models/member.py` | YES -- 4 consumer entries |
| `count_active_members` | `app/models/member.py` | YES |
| `get_active_plans` | `app/models/plan.py` | YES |
| `get_active_desks` | `app/models/desk.py` | YES |
| `get_active_rooms` | `app/models/room.py` | YES |
| `get_desk_bookings_by_date` | `app/models/desk_booking.py` | YES |
| `count_desk_bookings_today` | `app/models/desk_booking.py` | YES |
| `get_room_bookings_by_date` | `app/models/room_booking.py` | YES |
| `count_room_bookings_today` | `app/models/room_booking.py` | YES |
| `get_invoices_by_status` | `app/models/invoice.py` | YES |
| `get_pending_invoice_count` | `app/models/invoice.py` | YES |
| `get_payments_by_invoice` | `app/models/payment.py` | YES |
| `get_total_paid_for_invoice` | `app/models/payment.py` | YES |
| `get_total_revenue_this_month` | `app/models/payment.py` | YES |
| `count_amenities` | `app/models/amenity.py` | YES |
| `get_db` | `app/db.py` | YES -- "ALL route files" |
| `login_required` | `app/auth.py` | YES -- "ALL route files (except auth)" |
| `check_password` | `app/auth.py` | YES |
| `VALID_SLOT_STARTS` | `app/models/room_booking.py` | YES |

All 19 cross-boundary producers are covered in the Wiring Table.

---

### Surface 3: Input Validation Prescriptions (FC4) -- PASS (fixed)

**Qualifying routes** (POST/PUT/PATCH/DELETE from Route Table):
25 POST routes qualify. `POST /logout` is a POST route but has no
user-submitted inputs beyond CSRF (handled globally by flask-wtf); its absence
is noted as WARN, not FAIL.

**Missing entry:**

| Item | Location | Issue |
|------|----------|-------|
| `POST /plans/<int:plan_id>/delete` | Route Table line 850 | Missing from Input Validation Prescriptions table. The `plan_id` URL parameter requires a "must exist in DB, abort(404) if not found" annotation (same pattern as other delete routes). Note: no IntegrityError needed since plans FK is SET NULL, but the 404 guard is still required. |

All other 24 qualifying POST routes are covered:
- `POST /login` -- covered (password)
- `POST /members/new` -- covered (name, email, membership_plan_id)
- `POST /members/<id>/edit` -- covered (email, status)
- `POST /members/<id>/delete` -- covered (member_id URL)
- `POST /plans/new` -- covered (name, price, billing_cycle)
- `POST /plans/<id>/edit` -- covered (is_active)
- `POST /desks/new` -- covered (name)
- `POST /desks/<id>/edit` -- covered (is_active)
- `POST /desks/<id>/delete` -- covered (desk_id URL)
- `POST /rooms/new` -- covered (name, capacity, hourly_rate)
- `POST /rooms/<id>/edit` -- covered (is_active)
- `POST /rooms/<id>/delete` -- covered (room_id URL)
- `POST /desk-bookings/new` -- covered (desk_id, member_id, booking_date, block)
- `POST /desk-bookings/<id>/cancel` -- covered (booking_id URL)
- `POST /room-bookings/new` -- covered (room_id, member_id, booking_date, slot_start)
- `POST /room-bookings/<id>/cancel` -- covered (booking_id URL)
- `POST /billing/new` -- covered (member_id, amount, description, due_date)
- `POST /billing/<id>/edit` -- covered (status)
- `POST /billing/<id>/delete` -- covered (invoice_id URL)
- `POST /payments/new` -- covered (invoice_id, amount, payment_date, payment_method)
- `POST /payments/<id>/delete` -- covered (payment_id URL)
- `POST /amenities/new` -- covered (name)
- `POST /amenities/<id>/edit` -- covered (is_available)
- `POST /amenities/<id>/delete` -- covered (amenity_id URL)

**WARN -- `POST /logout` not in validation table.**
`POST /logout` is a qualifying route (POST method). It has no user-submitted
form inputs beyond CSRF. No validation entry is strictly needed, but an explicit
row stating "no user inputs -- CSRF only" would make the table exhaustive.
Treating as WARN, not FAIL.

---

### Surface 4: Registration Points (FC5) -- PASS

**Enumerated blueprints (11):** `auth`, `dashboard`, `members`, `plans`,
`desks`, `rooms`, `desk_bookings`, `room_bookings`, `billing`, `payments`,
`amenities`.

**Registration:** All 11 blueprints are explicitly registered in `create_app()`
(App Configuration section, lines 55-77) with exact url_prefix values.
Coordinated Behaviors rule 1 (line 1235) reinforces this.

**Navbar coverage:** Coordinated Behaviors rule 2 (line 1236) explicitly names
all 10 list endpoints for navbar inclusion. PASS.

---

### Surface 5: Transaction Contracts (FC29) -- PASS

**Enumerated write functions (23):**

| Function | Contract in Table |
|----------|-------------------|
| `create_member` | commits internally |
| `update_member` | commits internally |
| `delete_member` | commits internally |
| `create_plan` | commits internally |
| `update_plan` | commits internally |
| `delete_plan` | commits internally |
| `create_desk` | commits internally |
| `update_desk` | commits internally |
| `delete_desk` | commits internally |
| `create_room` | commits internally |
| `update_room` | commits internally |
| `delete_room` | commits internally |
| `create_desk_booking` | BEGIN IMMEDIATE + try/except/ROLLBACK |
| `cancel_desk_booking` | commits internally |
| `create_room_booking` | BEGIN IMMEDIATE + try/except/ROLLBACK |
| `cancel_room_booking` | commits internally |
| `create_invoice` | commits internally |
| `update_invoice` | commits internally |
| `delete_invoice` | commits internally |
| `create_payment` | commits internally |
| `delete_payment` | commits internally |
| `create_amenity` | commits internally |
| `update_amenity` | commits internally |
| `delete_amenity` | commits internally |

All 23 write functions (including the 2 BEGIN IMMEDIATE functions) appear in
the Transaction Contracts table with complete annotations.

---

### Surface 6: Authorization Mode (FC35) -- PASS

**Auth-protected route detection:** The `@login_required` decorator is defined
in `app/auth.py` and required for every route handler (per Authentication section
and Coordinated Behaviors rule 5). The Authorization Matrix section exists and
covers:

| Route Pattern | Mode | Covered |
|---------------|------|---------|
| `GET /login`, `POST /login` | public | YES |
| `GET /health` | public | YES |
| `POST /logout` | login-required | YES |
| ALL other routes | login-required | YES (wildcard, 55 routes) |

The wildcard "ALL other routes = login-required" is sufficient coverage for all
55 remaining routes. No role distinctions or ownership checks exist (single-admin
system). PASS.

---

## Summary

- **Total checks:** 6
- **PASS:** 6
- **FAIL:** 0 (1 fixed: POST /plans/delete added to Input Validation Prescriptions)
- **WARN:** 2
- **N/A:** 0
- **BLOCKED:** 0

### WARN Disposition

| WARN | Disposition |
|------|-------------|
| Surface 1: Route URL paths not listed in Export Names table | Non-functional gap. All cross-boundary URL references use `url_for()` endpoint names, which ARE fully covered. Raw URL paths are documented in the Route Table. No agent will fail due to this omission. |
| Surface 3: `POST /logout` not in Input Validation table | No user inputs to validate on this route (CSRF handled globally by flask-wtf). Absence of an explicit row does not risk a bug. |

### FAIL Summary

No remaining failures. 1 omission fixed during this gate:
- `POST /plans/<int:plan_id>/delete` added to Input Validation Prescriptions (commit 0cd14db)

---

STATUS: PASS -- 0 omissions (1 fixed during gate)
