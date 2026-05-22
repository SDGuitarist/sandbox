# Spec Consistency Check -- CoWorkFlow (Run 055)

**Date:** 2026-05-22
**Plan:** docs/plans/2026-05-21-coworkflow-plan.md
**Note:** This is the re-run after fixes for FAIL-7a, FAIL-7b, and WARN-2. Only checks 2 and 7 were re-verified; all other checks carried forward from the initial run.

---

## Results

### Check 1: Export Name Consistency

Verified every function name in the Export Names Table (lines 1052-1150) against its
definition in the Model Functions section (lines 356-827).

Findings:

- All 59 model functions listed in the Export Names Table have exact name matches in
  their respective model section definitions. No capitalization drift, no snake_case
  vs. camelCase conflicts.
- Blueprint endpoint names in the Export Names Table (e.g., `members.list_members`,
  `billing.detail`, `desk_bookings.new_booking`) all match entries in the Route Table
  (lines 831-890).
- Blueprint names (`auth`, `dashboard`, `members`, `plans`, `desks`, `rooms`,
  `desk_bookings`, `room_bookings`, `billing`, `payments`, `amenities`) all appear
  consistently in the Export Names Table, App Configuration blueprint registration,
  and the Swarm Agent Assignment table.

**STATUS: PASS**

---

### Check 2: Cross-Boundary Wiring Consistency

Verified every row in the Cross-Boundary Wiring Table (lines 1154-1181) against
the Export Names Table and model function definitions.

Findings:

- Every import path listed references the correct source module and correct function
  names. Spot-checked:
  - `from app.models.desk_booking import create_desk_booking, get_desk_booking, get_all_desk_bookings, get_desk_bookings_by_member, cancel_desk_booking` -- all five names match the model definitions at lines 524-607.
  - `from app.models.room_booking import create_room_booking, get_room_booking, get_all_room_bookings, get_room_bookings_by_member, get_available_slots, cancel_room_booking, VALID_SLOT_STARTS` -- all seven names match definitions at lines 615-703.
  - `from app.models.invoice import create_invoice, get_invoice, get_all_invoices, get_invoices_by_member, update_invoice, delete_invoice` -- all six match definitions at lines 711-748. Note: `get_pending_invoice_count` is correctly NOT listed here (it goes via a separate wiring row for `dashboard/routes.py`).
  - `from app.models.payment import create_payment, get_payment, get_all_payments, delete_payment` for `payments/routes.py` -- matches payment model at lines 755-795. Note: `get_total_revenue_this_month` is separately routed to `dashboard/routes.py`.

- Previously flagged gap RESOLVED: `get_active_plans` is now listed in the Export
  Names Table (line 1064) as used by both `member_routes` agent AND `plan_routes`
  agent. The Wiring Table (line 1164) imports it for `plans/routes.py` and (line 1165)
  for `members/routes.py`. The Export Names Table and Wiring Table now agree on the
  full consumer set.

**STATUS: PASS** (previously WARN; resolved by adding `plan_routes` as consumer in Export Names Table line 1064)

---

### Check 3: Route Path Consistency

Verified route paths in the Route Table (lines 831-890) against:
- `url_prefix` values in App Configuration (lines 67-77)
- `url_for()` calls in model docstring usage examples (lines 369-808)
- Smoke test endpoint list (lines 1525-1533)

Findings:

- `url_prefix` values in `register_blueprint()` calls all match Route Table prefixes:
  `/members`, `/plans`, `/desks`, `/rooms`, `/desk-bookings`, `/room-bookings`,
  `/billing`, `/payments`, `/amenities`.
- `auth_bp` and `dashboard_bp` are registered without a `url_prefix`, matching
  Route Table entries `/login`, `/logout`, `/health`, `/` which have no prefix.
- `url_for()` calls checked:
  - `url_for('members.detail', member_id=member_id)` -- Route Table has
    `GET /members/<int:member_id>` with handler `members.detail`. PASS.
  - `url_for('plans.list_plans')` -- Route Table has `GET /plans/` with handler
    `plans.list_plans`. PASS.
  - `url_for('desks.list_desks')` -- Route Table has `GET /desks/` with handler
    `desks.list_desks`. PASS.
  - `url_for('rooms.list_rooms')` -- Route Table has `GET /rooms/` with handler
    `rooms.list_rooms`. PASS.
  - `url_for('desk_bookings.new_booking')` -- Route Table has
    `GET /desk-bookings/new` with handler `desk_bookings.new_booking`. PASS.
  - `url_for('desk_bookings.detail', booking_id=booking_id)` -- Route Table has
    `GET /desk-bookings/<int:booking_id>` with handler `desk_bookings.detail`. PASS.
  - `url_for('room_bookings.new_booking')` -- Route Table has
    `GET /room-bookings/new` with handler `room_bookings.new_booking`. PASS.
  - `url_for('room_bookings.detail', booking_id=booking_id)` -- Route Table has
    `GET /room-bookings/<int:booking_id>` with handler `room_bookings.detail`. PASS.
  - `url_for('billing.detail', invoice_id=invoice_id)` -- Route Table has
    `GET /billing/<int:invoice_id>` with handler `billing.detail`. PASS.
  - `url_for('payments.list_payments')` -- Route Table has `GET /payments/` with
    handler `payments.list_payments`. PASS.
  - `url_for('amenities.list_amenities')` -- Route Table has `GET /amenities/` with
    handler `amenities.list_amenities`. PASS.
  - `url_for('auth.login_page')` (in `login_required` decorator) -- Route Table has
    `GET /login` with handler `auth.login_page`. PASS.
- Smoke test endpoints (`/desk-bookings/`, `/room-bookings/`, etc.) all match Route
  Table paths. PASS.

**STATUS: PASS**

---

### Check 4: Blueprint Registration Consistency

Verified blueprint names and `url_prefix` values in App Configuration against
the Export Names Table blueprint name rows and File Assignment Boundaries section.

Findings:

- App Configuration imports and registers 11 blueprints. The Export Names Table
  lists 11 blueprint names (`auth`, `dashboard`, `members`, `plans`, `desks`,
  `rooms`, `desk_bookings`, `room_bookings`, `billing`, `payments`, `amenities`).
  All 11 match.
- Import paths in App Configuration:
  - `from app.blueprints.auth.routes import bp as auth_bp`
  - `from app.blueprints.dashboard.routes import bp as dashboard_bp`
  - (etc. through amenities)
  These all match the file paths listed in the File Assignment Boundaries section.
- `url_prefix` values in `register_blueprint()` match the Route Table path prefixes
  exactly (verified in Check 3 above).
- Blueprint variable `bp` is used consistently (no mismatches like `auth_bp` vs `bp`
  in the route file).

**STATUS: PASS**

---

### Check 5: Template Reference Consistency

Verified template names in the Route Table "Template" column and the Template
Render Context section against the template file paths in File Assignment Boundaries.

Findings:

- Route Table template names checked against File Assignment Boundaries:

| Route Table Template | File Assignment Boundaries |
|---|---|
| `dashboard/index.html` | `coworkflow/app/templates/dashboard/index.html` |
| `auth/login.html` | `coworkflow/app/templates/auth/login.html` |
| `members/list.html` | `coworkflow/app/templates/members/list.html` |
| `members/form.html` | `coworkflow/app/templates/members/form.html` |
| `members/detail.html` | `coworkflow/app/templates/members/detail.html` |
| `plans/list.html` | `coworkflow/app/templates/plans/list.html` |
| `plans/form.html` | `coworkflow/app/templates/plans/form.html` |
| `desks/list.html` | `coworkflow/app/templates/desks/list.html` |
| `desks/form.html` | `coworkflow/app/templates/desks/form.html` |
| `rooms/list.html` | `coworkflow/app/templates/rooms/list.html` |
| `rooms/detail.html` | `coworkflow/app/templates/rooms/detail.html` |
| `rooms/form.html` | `coworkflow/app/templates/rooms/form.html` |
| `desk_bookings/list.html` | `coworkflow/app/templates/desk_bookings/list.html` |
| `desk_bookings/detail.html` | `coworkflow/app/templates/desk_bookings/detail.html` |
| `desk_bookings/form.html` | `coworkflow/app/templates/desk_bookings/form.html` |
| `room_bookings/list.html` | `coworkflow/app/templates/room_bookings/list.html` |
| `room_bookings/detail.html` | `coworkflow/app/templates/room_bookings/detail.html` |
| `room_bookings/form.html` | `coworkflow/app/templates/room_bookings/form.html` |
| `billing/list.html` | `coworkflow/app/templates/billing/list.html` |
| `billing/detail.html` | `coworkflow/app/templates/billing/detail.html` |
| `billing/form.html` | `coworkflow/app/templates/billing/form.html` |
| `payments/list.html` | `coworkflow/app/templates/payments/list.html` |
| `payments/form.html` | `coworkflow/app/templates/payments/form.html` |
| `amenities/list.html` | `coworkflow/app/templates/amenities/list.html` |
| `amenities/form.html` | `coworkflow/app/templates/amenities/form.html` |

All 25 templates match. The Template Render Context section uses the same names
as the Route Table. No plans/detail.html exists in the Route Table or in File
Assignment Boundaries (consistent -- plans has no detail page, only list).

**STATUS: PASS**

---

### Check 6: Model Function Signature Consistency

Verified function signatures in model sections against the Export Names Table and
Wiring Table.

Findings:

- Every function listed in the Export Names Table has a matching definition with the
  same name and same parameter pattern (conn as first arg, then domain args).
- `VALID_SLOT_STARTS` is defined as a module-level list in `models/room_booking.py`
  (line 615), listed in Export Names Table as a constant (line 1094), and imported
  explicitly in the Wiring Table row for `room_bookings/routes.py` (line 1172). The
  Template Render Context passes it as `slot_starts=VALID_SLOT_STARTS` (line 966),
  which is a correct usage pattern. PASS.
- All `create_*` functions return `int` (new ID). All `get_*` functions return
  `sqlite3.Row | None` (single) or `list[sqlite3.Row]` (plural). All `update_*`
  and `delete_*` return `None`. All `count_*` and `get_total_*` return `int`.
  These are internally consistent.
- `create_desk_booking` and `create_room_booking` both return `int | None` (None on
  conflict). This is consistent with the Transaction Contracts section which says
  "return None" on conflict.

**STATUS: PASS**

---

### Check 7: FK ON DELETE Consistency (CRITICAL)

#### Step 1: Extract all FK constraints with ON DELETE tokens

| Child Table | Column | Parent Table | ON DELETE Token |
|---|---|---|---|
| members | membership_plan_id | membership_plans | SET NULL |
| desk_bookings | desk_id | desks | RESTRICT |
| desk_bookings | member_id | members | RESTRICT |
| room_bookings | room_id | meeting_rooms | RESTRICT |
| room_bookings | member_id | members | RESTRICT |
| invoices | member_id | members | RESTRICT |
| payments | invoice_id | invoices | RESTRICT |

#### Step 2: Group by parent table (what deletes are affected)

**delete_member (parent: members)**
- desk_bookings.member_id ON DELETE RESTRICT
- room_bookings.member_id ON DELETE RESTRICT
- invoices.member_id ON DELETE RESTRICT
- Verdict: ALL RESTRICT -- IntegrityError WILL fire if any child rows exist.

**delete_plan (parent: membership_plans)**
- members.membership_plan_id ON DELETE SET NULL
- Verdict: ALL SET NULL -- IntegrityError will NOT fire.

**delete_desk (parent: desks)**
- desk_bookings.desk_id ON DELETE RESTRICT
- Verdict: ALL RESTRICT -- IntegrityError WILL fire.

**delete_room (parent: meeting_rooms)**
- room_bookings.room_id ON DELETE RESTRICT
- Verdict: ALL RESTRICT -- IntegrityError WILL fire.

**delete_invoice (parent: invoices)**
- payments.invoice_id ON DELETE RESTRICT
- Verdict: ALL RESTRICT -- IntegrityError WILL fire.

#### Step 3: Evaluate each delete function against docstring and route behavior

**delete_plan:**
- Schema: members.membership_plan_id ON DELETE SET NULL (line 243)
- Docstring (line 446-449): "FK constraint is SET NULL -- membership_plan_id on members becomes NULL. No IntegrityError raised."
- Coordinated Behavior #8 (line 1242): confirms delete_plan does NOT need IntegrityError handling (routes where all child FKs are SET NULL do NOT need IntegrityError handling).
- PASS -- docstring matches schema.

**delete_member:**
- Schema: 3 RESTRICT child FKs (lines 275-276, 289-290, 307)
- Docstring (lines 395-398): "Raises sqlite3.IntegrityError if member has desk_bookings, room_bookings, or invoices (all ON DELETE RESTRICT)."
- Transaction Contracts (line 1267): "none needed (IntegrityError caught by route)"
- Coordinated Behavior #8 (line 1242): "Delete routes with RESTRICT FKs catch sqlite3.IntegrityError specifically ... and flash an entity-specific message as defined in Input Validation Prescriptions."
- Input Validation Prescriptions (line 1193): `POST /members/<id>/delete` now reads: "Must exist in DB; catch `sqlite3.IntegrityError` | `abort(404)` if not found; Flash 'Cannot delete: member has bookings or invoices.' if IntegrityError" -- IntegrityError catch is now present and consistent with the schema and Coordinated Behavior #8.
- PASS (previously FAIL-7a; resolved).

**delete_desk:**
- Schema: desk_bookings.desk_id ON DELETE RESTRICT (line 275)
- Docstring (line 481): "Raises sqlite3.IntegrityError if desk has bookings (ON DELETE RESTRICT)."
- Input Validation Prescriptions (line 1200): "Must exist; catch IntegrityError | Flash 'Cannot delete: desk has bookings.'"
- PASS.

**delete_room:**
- Schema: room_bookings.room_id ON DELETE RESTRICT (line 289)
- Docstring (line 515): "Raises sqlite3.IntegrityError if room has bookings (ON DELETE RESTRICT)."
- Input Validation Prescriptions (line 1205): "Must exist; catch IntegrityError | Flash 'Cannot delete: room has bookings.'"
- PASS.

**delete_invoice:**
- Schema: payments.invoice_id ON DELETE RESTRICT (line 321)
- Docstring (line 743): "Raises sqlite3.IntegrityError if invoice has payments (ON DELETE RESTRICT)."
- Input Validation Prescriptions (line 1221): "Must exist; catch IntegrityError | Flash 'Cannot delete: invoice has payments.'"
- PASS.

#### Step 4: Flash message text consistency

Coordinated Behavior #8 (line 1242) now reads: "flash an entity-specific message as defined in Input Validation Prescriptions (e.g., 'Cannot delete: member has bookings or invoices.', 'Cannot delete: desk has bookings.')."

This defers to Input Validation Prescriptions as the authoritative source for flash text, and the examples given match the actual Input Validation Prescriptions entries. The contradiction between Coordinated Behavior #8 (previously generic) and Input Validation Prescriptions (entity-specific) is resolved.

PASS (previously FAIL-7b; resolved).

**STATUS: PASS** (previously FAIL; both sub-issues FAIL-7a and FAIL-7b resolved)

---

### Check 8: Input Validation Consistency

Verified that the Input Validation Prescriptions table is internally consistent with
the model function signatures and schema definitions.

Findings:

- `POST /members/new` lists field `membership_plan_id` (form) as "Optional; if
  provided, must be valid int." The model signature at line 363 accepts
  `membership_plan_id: int | None`. PASS.
- `POST /plans/new` lists field `price` (form). Form Field Names table (line 1020)
  confirms the field is named `price` (not `price_cents`). Route parses it to
  `price_cents`. PASS.
- `POST /rooms/new` lists field `hourly_rate` (form). Form Field Names table (line
  1024) confirms the field is named `hourly_rate`. Route parses to
  `hourly_rate_cents`. PASS.
- `POST /billing/new` lists field `amount` (form). Form Field Names table (line
  1028) confirms `amount`. Route parses to `amount_cents`. PASS.
- `POST /payments/new` lists field `amount` (form). Form Field Names table (line
  1030) confirms `amount`. Route parses to `amount_cents`. PASS.
- Status enum values checked:
  - members: `('active', 'frozen', 'cancelled')` -- matches schema CHECK at line 246. PASS.
  - invoices: `('pending', 'paid', 'overdue', 'cancelled')` -- matches schema CHECK at line 312. PASS.
  - payments method: `('cash', 'card', 'bank_transfer', 'other')` -- matches schema CHECK at line 323. PASS.
  - billing_cycle: `('monthly', 'quarterly', 'annual')` -- matches schema CHECK at line 229. PASS.
  - desk booking block: `('am', 'pm', 'full')` -- matches schema CHECK at line 279. PASS.
  - room booking status confirmed: `('confirmed', 'cancelled')` -- matches schema CHECK at line 296. PASS.

**STATUS: PASS**

---

### Check 9: Transaction Contract Consistency

Verified Transaction Contracts table (lines 1262-1288) against model function
docstrings.

Findings:

- `create_desk_booking`: Transaction Contracts says "requires BEGIN IMMEDIATE (atomic conflict check), try/except/ROLLBACK". Model docstring (lines 524-579) shows exactly this pattern: BEGIN IMMEDIATE -> conflict check -> INSERT -> COMMIT, wrapped in try/except/ROLLBACK. PASS.
- `create_room_booking`: Same pattern confirmed in model docstring (lines 622-666). PASS.
- All `create_*` (except bookings) listed as "commits internally (`conn.commit()`)". Model docstrings confirm "Commits: yes" for each. PASS.
- All `update_*` listed as "commits internally". Docstrings confirm "Commits: yes." PASS.
- All `delete_*` listed as "commits internally". Docstrings confirm "Commits: yes." PASS.
- `cancel_desk_booking`: Listed as "commits internally". Docstring (line 598) says "Commits: yes." PASS.
- `cancel_room_booking`: Listed as "commits internally". Docstring (line 696) says "Commits: yes." PASS.
- Note at line 1290: "All read-only functions (get_*, count_*, search_*, get_available_*) do NOT commit." This is consistent with all read function docstrings which make no mention of committing.

**STATUS: PASS**

---

### Check 10: Authorization Consistency

Verified the Authorization Matrix (lines 1297-1308) against the authentication
rules stated in the Authentication section (lines 159-176).

Findings:

- Authorization Matrix says public routes are: `GET /login`, `POST /login`, `GET /health`.
- Authentication section (line 175) says: "Every route except `auth.login_page`,
  `auth.login`, and `dashboard.health` MUST use `@login_required`."
- These match -- same three routes exempt from login_required. PASS.
- Authorization Matrix says `POST /logout` is login-required. This is consistent with
  the Authentication section rule (logout is not in the exception list). PASS.
- Authorization Matrix says "ALL other routes: login-required." This aligns with the
  Authentication section. PASS.
- No role distinctions or ownership checks are needed (single-admin system) --
  consistent across both sections. PASS.
- `login_required` decorator is defined in `app/auth.py` (line 159-167), listed in
  Export Names Table (line 1117), and imported by all route agents per the Wiring
  Table (line 1157). PASS.

**STATUS: PASS**

---

## Summary Table

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Export Name Consistency | PASS | All 59 model functions and endpoint names match exactly |
| 2 | Cross-Boundary Wiring Consistency | PASS | `get_active_plans` now listed as consumed by both `member_routes` and `plan_routes` in Export Names Table (line 1064); tables now agree |
| 3 | Route Path Consistency | PASS | All `url_for()` calls, Route Table paths, and `url_prefix` values are consistent |
| 4 | Blueprint Registration Consistency | PASS | All 11 blueprints match across App Configuration, Export Names Table, and File Assignment Boundaries |
| 5 | Template Reference Consistency | PASS | All 25 templates match between Route Table, Render Context, and File Assignment Boundaries |
| 6 | Model Function Signature Consistency | PASS | All signatures internally consistent; return types consistent |
| 7 | FK ON DELETE Consistency | PASS | (a) `POST /members/<id>/delete` now includes IntegrityError catch in Input Validation Prescriptions (line 1193); (b) Coordinated Behavior #8 now defers to entity-specific messages in Input Validation Prescriptions (line 1242) |
| 8 | Input Validation Consistency | PASS | All form field names, enum values, and type rules match schema |
| 9 | Transaction Contract Consistency | PASS | All commit annotations match model docstrings |
| 10 | Authorization Consistency | PASS | Auth Matrix and Authentication section agree on exempt routes |

---

## Final Summary

- **Total checks:** 10
- **PASS:** 10
- **FAIL:** 0
- **WARN:** 0
- **N/A (section absent):** 0

**STATUS: PASS**

All three issues from the initial run have been resolved. The spec is internally consistent and ready for swarm agent launch.
