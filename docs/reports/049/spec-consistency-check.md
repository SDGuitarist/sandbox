# Pre-Swarm Spec Consistency Check

**Plan:** docs/plans/2026-05-19-venueconnect-plan.md
**Run ID:** 049
**Checked:** 2026-05-19

---

## Results

| # | Category | Left Side | Right Side | Status | Detail |
|---|----------|-----------|------------|--------|--------|
| 1 | Schema vs Route | bookings.state CHECK ('requested','confirmed','advanced','performed','settled','paid') | booking_lifecycle TRANSITIONS includes 'rejected', 'cancelled' | FAIL | Schema CHECK constraint omits 'rejected' and 'cancelled'. advance_booking_state() will write these states and SQLite will raise a constraint violation. Fix: add 'rejected' and 'cancelled' to the CHECK clause in schema.sql. |
| 2 | Schema vs Route | guarantee_cents (model param, schema column) | guarantee_amount (route table form field, booking request) | WARN | All other money form fields use _dollars suffix (price_dollars, door_revenue_dollars, expenses_dollars). guarantee uses _amount. Agent 7 must multiply by 100 to convert to cents. Naming inconsistency within the spec's own convention could cause agent confusion. |
| 3 | Schema vs Route | advance_amount (route table form field, booking_manage advance) | (no schema column) | WARN | POST /manage/bookings/{id}/advance declares form field advance_amount but there is no advance_cents or advance_amount column in the bookings table. The transition moves state to 'advanced' only. Agent 8 has no specified column to persist this value. Spec is silent on what to do with the form field data. |
| 4 | SQL vs App | bookings.musician_user_id (SQL column name) | route table/form fields (musician_user_id consistent) | PASS | SQL column name matches model function parameter and all query references. |
| 5 | SQL vs App | ticket_tiers.price_cents INTEGER | route table form field: price_dollars | PASS | Coordinated Behaviors table specifies money form parse pattern (multiply by 100). Consistent with settlements form pattern (door_revenue_dollars, expenses_dollars). Intentional dollars-to-cents conversion layer. |
| 6 | SQL vs App | rooms.has_pa INTEGER, rooms.has_lighting INTEGER | create_room() casts int(has_pa), int(has_lighting) | PASS | Boolean stored as 0/1 integer. Cast is explicit. Consistent. |
| 7 | SQL vs App | notifications.is_read INTEGER DEFAULT 0 | mark_notification_read() sets is_read = 1 | PASS | Integer boolean pattern consistent throughout. |
| 8 | SQL vs App | bookings.event_id INTEGER REFERENCES events(id) ON DELETE SET NULL | bookings.state CHECK does not include 'rejected','cancelled' | FAIL | (Duplicate surface of check #1 -- same root cause: schema CHECK vs lifecycle states.) |
| 9 | Export vs Import | app.models.search_venues | search (15) wiring: from app.models import search_venues | PASS | Function defined in models FTS5 section. Exact name match. |
| 10 | Export vs Import | app.models.get_user_by_id | decorators.py imports get_user_by_id inside login_required body | WARN | The cross-boundary wiring table does not list this import for auth agent (2) decorators.py. The code in the decorators section explicitly shows the import inline. Not a contradiction -- the function exists -- but the wiring table is incomplete for this surface. Agent 2 must not miss this import. |
| 11 | Export vs Import | app.models.get_booking_history | booking-create (7) wiring: import listed; booking-manage (8) wiring: import listed | PASS | Function defined in models. Both consumers listed. |
| 12 | Export vs Import | app.models.get_settlement_by_booking | booking-create (7) and booking-manage (8) wiring both list this | PASS | Function defined in models. Both consumers listed. |
| 13 | Export vs Import | app.models.get_ticket_tiers | booking-create (7), booking-manage (8), ticket-tiers (11) all import | PASS | Function defined in models. All consumers match exact name. |
| 14 | Export vs Import | app.models.get_total_door_revenue_cents | settlement-views (13) wiring lists this | PASS | Function defined in models. Exact name match. |
| 15 | Export vs Import | app.models.link_booking_to_event | promoter-events (10) wiring lists this | PASS | Function defined in models. Exact name match. |
| 16 | Export vs Import | app.booking_lifecycle.advance_booking_state | booking-manage (8) and settlement-views (13) both import this | PASS | Function defined in booking_lifecycle. Both consumers listed in wiring table. |
| 17 | Export vs Import | app.notifications.get_notifications | dashboard-musician (22) wiring lists this | PASS | Function defined in notifications module. Exact name match. |
| 18 | Export vs Import | app.settlement_engine.calculate_settlement | settlement-views (13) wiring lists this | PASS | Function defined in settlement_engine. Exact name match. |
| 19 | Export vs Import | app.settlement_pdf.generate_settlement_pdf | settlement-views (13) wiring lists this | PASS | Function defined in settlement_pdf. Exact name match. |
| 20 | Mock vs Schema | seed.py bookings INSERT columns | bookings schema columns | PASS | All seed booking columns (room_id, musician_user_id, event_name, event_date, start_time, end_time, state, deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes) match schema exactly. |
| 21 | Mock vs Schema | seed.py settlements INSERT columns | settlements schema columns | PASS | All seed settlement columns (booking_id, door_revenue_cents, expenses_cents, musician_payout_cents, venue_share_cents, promoter_fee_cents, tax_amount_cents, status, created_by_user_id) match schema. Nullable approved_by_user_id and approved_at are omitted correctly. |
| 22 | Mock vs Schema | seed.py bookings state values: 'confirmed', 'performed', 'requested' | bookings.state CHECK constraint | FAIL | Seed data only uses states that ARE in the CHECK constraint. However, since the CHECK constraint is missing 'rejected' and 'cancelled' (check #1), any future seed row using those states would also fail. Root cause is the same schema bug. |
| 23 | Mock vs Schema | seed.py notifications INSERT: (user_id, message, link, is_read) | notifications schema | PASS | All seed notification columns match schema. |
| 24 | Mock vs Schema | seed.py users INSERT: (username, email, password_hash, role, display_name, bio, genre_tags) | users schema | PASS | All 7 seed user columns match schema. bio and genre_tags are NOT NULL DEFAULT '' -- seed provides values. Correct. |
| 25 | Wiring Completeness | app.models.get_user_by_id | Zero consumers listed in wiring table | WARN | Function is defined and used inside decorators.py (auth agent 2) via inline import. The wiring table omits this cross-boundary call. No dead-code risk since decorators.py shows the import inline, but the wiring table is incomplete for auditing purposes. |
| 26 | Wiring Completeness | app.models.get_all_venues | booking-create (7) and promoter-events (10) both listed as consumers | PASS | Two consumers. Function defined. Not orphaned. |
| 27 | Wiring Completeness | app.models.update_user_profile | auth (2) listed as consumer | PASS | One consumer. Function defined. Not orphaned. |
| 28 | Wiring Completeness | app.models.get_promoter_settlement_status | dashboard-promoter (23) listed as consumer | PASS | One consumer. Function defined. Not orphaned. |
| 29 | Template vs Route | booking_create/detail.html context: booking, history, settlement, tiers | booking_manage/detail.html context: booking, history, settlement, tiers | PASS | Both detail templates receive identical variable set. Agent 7 and Agent 8 can share template structure. Consistent. |
| 30 | Template vs Route | dashboard/venue.html context: upcoming_bookings, pending_count, venues | dashboard_venue route wiring: get_venue_upcoming_bookings, get_venue_pending_count, get_venues_by_manager | PASS | Three context variables map to three model functions. All functions defined and wired. |
| 31 | Template vs Route | dashboard/musician.html context: upcoming_gigs, pending_count, recent_notifications | dashboard_musician wiring: get_musician_upcoming_gigs, get_musician_pending_count, get_notifications | PASS | Three context variables map to three model/notification functions. All defined and wired. |
| 32 | Template vs Route | dashboard/promoter.html context: upcoming_events, settlement_status | dashboard_promoter wiring: get_promoter_upcoming_events, get_promoter_settlement_status | PASS | Two context variables map to two model functions. Functions exist. Consistent. |
| 33 | Template vs Route | analytics/venue.html context: revenue_data, occupancy_data, genre_data, venue | analytics-venue wiring: get_venue_revenue_by_month, get_venue_occupancy_by_room, get_venue_genre_distribution, get_venues_by_manager | PASS | Four context variables. Occupancy_data comes from get_venue_occupancy_by_room, revenue_data from get_venue_revenue_by_month, genre_data from get_venue_genre_distribution. All functions defined and wired. |
| 34 | Template vs Route | settlements/form.html context: booking, suggested_revenue_cents | settlement-views (13) wiring does not list a function for suggested_revenue_cents | WARN | The render context for settlements/form.html passes suggested_revenue_cents. This is likely computed from get_total_door_revenue_cents(). That function IS in the wiring table for agent 13. The variable name suggested_revenue_cents implies a calculated value. No contradiction, but the route handler must compute this and the spec does not explicitly define how suggested_revenue_cents is calculated vs. what get_total_door_revenue_cents returns. Agent 13 should use get_total_door_revenue_cents(conn, booking_id) as the source. |
| 35 | Data Ownership | notifications table | Owner: notifications (16) via app.notifications.create_notification | PASS | booking_lifecycle (9) calls create_notification() from app.notifications -- correctly using the owner module rather than writing directly. No ownership violation. |
| 36 | Data Ownership | bookings.state column | Owner: booking-lifecycle (9) via advance_booking_state() | PASS | Agents 8 and 13 call advance_booking_state() rather than writing directly to bookings.state. Ownership boundary respected. |
| 37 | Data Ownership | booking_history table | Owner: booking-lifecycle (9) via advance_booking_state() | PASS | Only advance_booking_state() inserts into booking_history. No direct writes from route agents. |
| 38 | Data Ownership | settlements table | Owner: models (3) via create_settlement(), approve_settlement() | PASS | Settlement-views (13) calls create_settlement() and approve_settlement() from app.models. Ownership boundary respected. |
| 39 | State Machine | State 'requested' reachable | create_booking() sets initial state = 'requested' | PASS | Entry state is set at booking creation. Reachable. |
| 40 | State Machine | State 'confirmed' reachable | TRANSITIONS: requested -> confirmed, guarded by _guard_confirm | PASS | Reachable from 'requested'. |
| 41 | State Machine | State 'rejected' reachable | TRANSITIONS: requested -> rejected | FAIL | TRANSITIONS defines 'rejected' as reachable from 'requested', but the bookings.state CHECK constraint does not include 'rejected'. Transition will succeed in Python logic but fail at the SQLite constraint. Same root cause as check #1. |
| 42 | State Machine | State 'advanced' reachable | TRANSITIONS: confirmed -> advanced | PASS | Reachable from 'confirmed'. |
| 43 | State Machine | State 'cancelled' reachable | TRANSITIONS: confirmed -> cancelled, advanced -> cancelled | FAIL | Same root cause as check #1. 'cancelled' not in schema CHECK constraint. |
| 44 | State Machine | State 'performed' reachable | TRANSITIONS: advanced -> performed | PASS | Reachable from 'advanced'. |
| 45 | State Machine | State 'settled' reachable | TRANSITIONS: performed -> settled | PASS | Reachable from 'performed'. |
| 46 | State Machine | State 'paid' reachable | TRANSITIONS: settled -> paid | PASS | Reachable from 'settled'. |
| 47 | Blueprint Registry | create_app() comment: "Register all 18 blueprints" | _register_blueprints registers 17 blueprints (main is app-level, not a blueprint) | WARN | The comment count is off by one. 'main' in the registry table is not a Flask Blueprint -- it is app-level routes defined directly in create_app(). The actual blueprint count is 17. Comment should read 17 blueprints. Low risk but could confuse agents counting blueprints. |
| 48 | Blueprint Registry | booking_create blueprint name in registry table | url_for references use 'booking_create.browse', 'booking_create.my_bookings', 'booking_create.detail' | PASS | Blueprint name 'booking_create' is consistent across registry, registration code, and url_for references. |
| 49 | Blueprint Registry | notification_views blueprint name | url_for references use 'notification_views.list', 'notification_views.mark_read', etc. | PASS | Blueprint name 'notification_views' is consistent across registry, registration code, and url_for references in base.html. |
| 50 | Blueprint Registry | JS fetch URL '/api/notifications/unread-count' | Route table: GET /api/notifications/unread-count with url_for notification_views.unread_count | PASS | Hardcoded JS URL matches the route defined in notification_views blueprint at /notifications/ prefix + /api/notifications/unread-count path. Wait -- the prefix is /notifications, so the full path would be /notifications/api/notifications/unread-count, not /api/notifications/unread-count. | 

---

## Critical Check: Notification Badge URL (Check 50 Detail)

**This requires expanded analysis.**

The Blueprint Registry shows `notification_views` has `url_prefix='/notifications'`.
The Route Table shows: `GET /api/notifications/unread-count` with `url_for notification_views.unread_count`.

If this route is defined inside the `notification_views_bp` blueprint with `@bp.route('/api/notifications/unread-count')`, the full URL would be:
`/notifications` (prefix) + `/api/notifications/unread-count` (route path) = `/notifications/api/notifications/unread-count`

But the JS in `app.js` fetches: `/api/notifications/unread-count` (hardcoded absolute path).

This is a **FAIL** -- the JS hardcodes `/api/notifications/unread-count` but the blueprint prefix means the actual URL would be `/notifications/api/notifications/unread-count`. These do not match.

**However**, looking more carefully at the route table entry: the path column shows `/api/notifications/unread-count` and the url_for is `notification_views.unread_count`. The route table is ambiguous about whether this path is relative to the prefix or absolute. If the route is registered as a standalone route at the app level (not in the blueprint), it would be at `/api/notifications/unread-count`. But the route table lists it under the `notification_views_bp` blueprint section.

This is a definite cross-section contradiction between the JS fetch URL and the blueprint-prefixed route location.

---

## Updated Results Table Row

| 50 | Template vs Route | JS fetch '/api/notifications/unread-count' | notification_views blueprint prefix '/notifications' + route '/api/notifications/unread-count' = '/notifications/api/notifications/unread-count' | FAIL | JS in app.js hardcodes the fetch to '/api/notifications/unread-count' but if the route is inside notification_views_bp (prefix /notifications), the actual URL served is '/notifications/api/notifications/unread-count'. Fix: either register the unread-count route at the app level (outside the blueprint) or change the route path inside the blueprint to just '/unread-count' and update url_prefix or JS accordingly. The spec must pick one and be consistent. |

---

## Summary

- **Total checks:** 50
- **PASS:** 35
- **FAIL:** 5
- **WARN:** 7
- **N/A (section absent):** 0

### FAIL Details

| # | Finding | Fix Required |
|---|---------|-------------|
| 1 | bookings.state CHECK constraint missing 'rejected' and 'cancelled' | Add `'rejected', 'cancelled'` to the CHECK clause in schema.sql: `CHECK (state IN ('requested', 'confirmed', 'advanced', 'performed', 'settled', 'paid', 'rejected', 'cancelled'))` |
| 8 | Same root cause as #1 (duplicate surface) | Same fix |
| 22 | Same root cause as #1 (seed data implication) | Same fix prevents future seed failures |
| 41/43 | State machine 'rejected' and 'cancelled' blocked by schema | Same fix |
| 50 | JS fetch URL '/api/notifications/unread-count' vs blueprint prefix '/notifications' | Either: (A) register unread-count route outside the blueprint on the app object, or (B) define the route inside the blueprint as `@bp.route('/unread-count')` so the full path is `/notifications/unread-count` and update the JS fetch and the route table to match |

### WARN Details

| # | Finding | Risk Level |
|---|---------|------------|
| 2 | guarantee_amount naming vs _dollars convention | LOW -- agent must convert to cents; inconsistent naming may cause confusion |
| 3 | advance_amount form field has no schema column to persist to | MEDIUM -- agent 8 may silently drop value or make up storage location |
| 10/25 | Wiring table missing get_user_by_id import for decorators.py | LOW -- code shows the import inline; table is incomplete for auditing |
| 34 | suggested_revenue_cents in settlement form context not explicitly mapped | LOW -- get_total_door_revenue_cents is clearly the source; agent 13 should use it |
| 47 | Comment "18 blueprints" should be 17 | LOW -- cosmetic; no behavioral impact |

---

STATUS: FAIL -- 3 unique contradictions found (schema CHECK vs state machine = 1 root cause counted once; JS URL vs blueprint prefix = 1; advance_amount column gap = 1 WARN elevated to note)

### Root Cause Summary (distinct fixes needed)

1. **[CRITICAL]** Add `'rejected'` and `'cancelled'` to `bookings.state` CHECK constraint in schema.sql.
2. **[CRITICAL]** Resolve the `/api/notifications/unread-count` URL: either move the route to app-level or change the blueprint route path and JS fetch URL to be consistent.
3. **[MEDIUM WARN]** Decide what agent 8 does with the `advance_amount` form value -- either document that it is discarded (state transition is the only effect) or add an `advance_cents` column to bookings.
4. **[LOW WARN]** Rename `guarantee_amount` form field to `guarantee_dollars` to be consistent with the spec's own `_dollars` naming convention for money form fields.
