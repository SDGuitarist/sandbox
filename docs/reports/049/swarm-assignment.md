---
run_id: "049"
plan: docs/plans/2026-05-19-venueconnect-plan.md
generated: 2026-05-19
validator: swarm-planner
---

# VenueConnect Run 049 -- Swarm Agent Assignment

## Validation Summary

**Total agents:** 25
**Total files:** 90
**Duplicate file check:** Passed -- every file appears in exactly one agent assignment
**Cross-boundary import check:** Passed -- every imported symbol is defined in the owning agent's files

### Duplicate Check Trace

All files were enumerated and compared. The high-risk shared files (owned by a single agent, imported by many) are:

| File | Owner Agent | Imported By |
|------|-------------|-------------|
| `venueconnect/app/__init__.py` | scaffold (1) | nobody imports it -- entry point |
| `venueconnect/app/db.py` | models (3) | agents 2, 4, 5, 6, 7, 8, 10, 11, 13, 15, 17, 18, 19, 20, 21, 22, 23 |
| `venueconnect/app/models.py` | models (3) | agents 2, 4, 5, 6, 7, 8, 10, 11, 13, 15, 18, 19, 20, 21, 22, 23 |
| `venueconnect/app/schema.sql` | models (3) | db.py only (via open_resource) |
| `venueconnect/app/decorators.py` | auth (2) | agents 4, 5, 6, 7, 8, 10, 11, 13, 15, 17, 18, 19, 20, 21, 22, 23 |
| `venueconnect/app/filters.py` | scaffold (1) | nobody imports it -- registered via create_app |
| `venueconnect/app/booking_lifecycle.py` | booking-lifecycle (9) | agents 8, 13 |
| `venueconnect/app/notifications.py` | notifications (16) | agents 9, 22 |
| `venueconnect/app/settlement_engine.py` | settlement-engine (12) | agent 13 |
| `venueconnect/app/settlement_pdf.py` | settlement-pdf (14) | agent 13 |

No file appears in two agents' lists. No cross-boundary import references an undefined symbol.

### Cross-Boundary Import Resolution

Every `from app.X import Y` statement in the wiring table resolves to a function defined in the spec:

- `search_venues` -- defined in models.py FTS5 section (plan line 1866-1882). Assigned to agent 3.
- `advance_booking_state` -- defined in booking_lifecycle.py. Assigned to agent 9.
- `create_notification`, `get_notifications`, `get_unread_count`, `mark_notification_read`, `mark_all_read` -- defined in notifications.py. Assigned to agent 16.
- `calculate_settlement` -- defined in settlement_engine.py. Assigned to agent 12.
- `generate_settlement_pdf` -- defined in settlement_pdf.py. Assigned to agent 14.

---

## Shared Interface Spec

The following spec text is the authoritative contract for all agents. Every agent
receives this full spec so they can work independently without inter-agent
communication. Do not deviate from function signatures, url_for names, form field
names, or template variable names defined here.

### Stack

Flask + SQLite + Jinja2 + Bootstrap 5. Python package root is `venueconnect/`.
App factory is `create_app()` in `venueconnect/app/__init__.py`.

### Blueprint Registry (url_for names and prefixes)

| Blueprint Name | Variable | url_prefix |
|---------------|----------|------------|
| auth | auth_bp | /auth |
| venues | venues_bp | /venues |
| rooms | rooms_bp | /rooms |
| availability | availability_bp | /availability |
| booking_create | booking_create_bp | /bookings |
| booking_manage | booking_manage_bp | /manage |
| events | events_bp | /events |
| tickets | tickets_bp | /tickets |
| settlements | settlements_bp | /settlements |
| search | search_bp | /search |
| notification_views | notification_views_bp | /notifications |
| analytics_venue | analytics_venue_bp | /analytics/venue |
| analytics_musician | analytics_musician_bp | /analytics/musician |
| analytics_promoter | analytics_promoter_bp | /analytics/promoter |
| dashboard_venue | dashboard_venue_bp | /dashboard/venue |
| dashboard_musician | dashboard_musician_bp | /dashboard/musician |
| dashboard_promoter | dashboard_promoter_bp | /dashboard/promoter |

Route paths are RELATIVE to the prefix. Never include the prefix in `@bp.route(...)`.

### Database Tables and Ownership

| Table | Write Owner | Owner Module |
|-------|-------------|--------------|
| users | agent 3 (models) | app.models |
| venues | agent 3 (models) | app.models |
| rooms | agent 3 (models) | app.models |
| availability_windows | agent 3 (models) | app.models |
| bookings (INSERT, non-state UPDATE) | agent 3 (models) | app.models |
| bookings.state (UPDATE) | agent 9 (booking-lifecycle) | app.booking_lifecycle |
| booking_history (INSERT) | agent 9 (booking-lifecycle) | app.booking_lifecycle |
| events | agent 3 (models) | app.models |
| ticket_tiers | agent 3 (models) | app.models |
| settlements | agent 3 (models) | app.models |
| notifications | agent 16 (notifications) | app.notifications |
| venues_fts | schema.sql triggers | n/a |

### Key Function Signatures (do not alter)

```python
# app/db.py
def get_db() -> sqlite3.Connection: ...
def close_db(e=None): ...
def init_db(): ...

# app/models.py -- users
def create_user(conn, username, email, password_hash, role, display_name) -> int: ...
def get_user_by_id(conn, user_id) -> sqlite3.Row | None: ...
def get_user_by_username(conn, username) -> sqlite3.Row | None: ...
def update_user_profile(conn, user_id, display_name, bio, genre_tags) -> None: ...

# app/models.py -- venues
def create_venue(conn, user_id, name, location, description, capacity, genre_tags) -> int: ...
def get_venue(conn, venue_id) -> sqlite3.Row | None: ...
def get_venues_by_manager(conn, user_id) -> list: ...
def get_all_venues(conn) -> list: ...
def update_venue(conn, venue_id, name, location, description, capacity, genre_tags) -> None: ...
def delete_venue(conn, venue_id) -> None: ...
def search_venues(conn, query) -> list: ...  # FTS5

# app/models.py -- rooms
def create_room(conn, venue_id, name, capacity, description, has_pa, has_lighting) -> int: ...
def get_room(conn, room_id) -> sqlite3.Row | None: ...
def get_rooms_by_venue(conn, venue_id) -> list: ...
def update_room(conn, room_id, name, capacity, description, has_pa, has_lighting) -> None: ...
def delete_room(conn, room_id) -> None: ...

# app/models.py -- availability
def create_availability_window(conn, room_id, day_of_week, start_time, end_time) -> int: ...
def get_availability_windows(conn, room_id) -> list: ...
def delete_availability_window(conn, window_id) -> None: ...
def check_room_available(conn, room_id, event_date, start_time, end_time) -> bool: ...
# CRITICAL: check_room_available must be called inside BEGIN IMMEDIATE transaction. Does NOT commit.

# app/models.py -- bookings
def create_booking(conn, room_id, musician_user_id, event_name, event_date,
                   start_time, end_time, deal_type, guarantee_cents,
                   door_split_pct, promoter_fee_pct, tax_pct, notes) -> int: ...
# CRITICAL: does NOT commit -- caller commits after conflict check
def get_booking(conn, booking_id) -> sqlite3.Row | None: ...  # has joined venue/room/musician
def get_bookings_by_musician(conn, musician_user_id) -> list: ...
def get_bookings_by_venue(conn, venue_id) -> list: ...
def get_pending_bookings_for_venue(conn, venue_id) -> list: ...
def get_bookings_by_event(conn, event_id) -> list: ...
def get_booking_history(conn, booking_id) -> list: ...

# app/models.py -- events
def create_event(conn, promoter_user_id, venue_id, name, description, event_date) -> int: ...
def get_event(conn, event_id) -> sqlite3.Row | None: ...
def get_events_by_promoter(conn, promoter_user_id) -> list: ...
def update_event(conn, event_id, name, description, event_date) -> None: ...
def link_booking_to_event(conn, booking_id, event_id) -> None: ...

# app/models.py -- ticket_tiers
def create_ticket_tier(conn, booking_id, name, price_cents, quantity) -> int: ...
def get_ticket_tiers(conn, booking_id) -> list: ...
def update_ticket_tier(conn, tier_id, name, price_cents, quantity, sold_count) -> None: ...
def delete_ticket_tier(conn, tier_id) -> None: ...
def get_total_door_revenue_cents(conn, booking_id) -> int: ...

# app/models.py -- settlements
def create_settlement(conn, booking_id, door_revenue_cents, expenses_cents,
                      musician_payout_cents, venue_share_cents,
                      promoter_fee_cents, tax_amount_cents, created_by_user_id) -> int: ...
def get_settlement(conn, settlement_id) -> sqlite3.Row | None: ...  # full join
def get_settlement_by_booking(conn, booking_id) -> sqlite3.Row | None: ...
def get_settlements_list(conn, user_id, role) -> list: ...
def approve_settlement(conn, settlement_id, approved_by_user_id) -> None: ...

# app/models.py -- analytics
def get_venue_revenue_by_month(conn, venue_id) -> list: ...
def get_venue_occupancy_by_room(conn, venue_id) -> list: ...
def get_venue_genre_distribution(conn, venue_id) -> list: ...
def get_musician_earnings_by_month(conn, user_id) -> list: ...
def get_musician_venues_played(conn, user_id) -> list: ...
def get_musician_booking_success_rate(conn, user_id) -> dict: ...
def get_promoter_revenue_by_month(conn, user_id) -> list: ...
def get_promoter_settlements_by_venue(conn, user_id) -> list: ...
def get_promoter_event_status_counts(conn, user_id) -> list: ...

# app/models.py -- dashboard
def get_venue_upcoming_bookings(conn, venue_id, limit=5) -> list: ...
def get_venue_pending_count(conn, venue_id) -> int: ...
def get_musician_upcoming_gigs(conn, user_id, limit=5) -> list: ...
def get_musician_pending_count(conn, user_id) -> int: ...
def get_promoter_upcoming_events(conn, user_id, limit=5) -> list: ...
def get_promoter_settlement_status(conn, user_id) -> dict: ...

# app/booking_lifecycle.py
def advance_booking_state(conn, booking_id, new_state, actor_user_id, notes='') -> bool: ...
# Returns True if transition succeeded, False if denied. Does NOT commit.
# CRITICAL call pattern (agents 8 and 13 MUST use exactly):
#   conn.execute('BEGIN IMMEDIATE')
#   success = advance_booking_state(conn, booking_id, '<new_state>', g.user['id'])
#   if not success:
#       conn.rollback()
#       flash('Cannot transition booking to this state.', 'error')
#       return redirect(url_for('<blueprint>.detail', booking_id=booking_id))
#   conn.commit()

# app/notifications.py
def create_notification(conn, user_id, message, link='') -> int: ...  # does NOT commit
def get_notifications(conn, user_id, limit=20) -> list: ...
def get_unread_count(conn, user_id) -> int: ...
def mark_notification_read(conn, notification_id) -> None: ...  # does NOT commit
def mark_all_read(conn, user_id) -> None: ...  # does NOT commit

# app/settlement_engine.py
def calculate_settlement(door_revenue_cents, expenses_cents, deal_type,
                         guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct) -> dict: ...
# Returns: {musician_payout_cents, venue_share_cents, promoter_fee_cents, tax_amount_cents}

# app/settlement_pdf.py
def generate_settlement_pdf(settlement) -> bytes: ...
# Takes sqlite3.Row from get_settlement(). Returns PDF bytes.

# app/decorators.py
def login_required(f): ...   # redirects to auth.login if not logged in; sets g.user
def role_required(role): ... # aborts 403 if g.user['role'] != role
```

### Booking State Machine

```
requested -> confirmed | rejected
confirmed -> advanced | cancelled
advanced  -> performed | cancelled
performed -> settled
settled   -> paid
paid      -> (terminal)
rejected  -> (terminal)
cancelled -> (terminal)
```

### Coordinated Behaviors (ALL agents must follow)

| Behavior | Pattern |
|----------|---------|
| Success flash | `flash('<Resource> <action> successfully.', 'success')` |
| Error flash | `flash('<Error description>.', 'error')` |
| Warning flash | `flash('<Warning>.', 'warning')` |
| 404 on missing | `if resource is None: abort(404)` |
| 403 on wrong role | Via `@role_required(role)` decorator |
| CSRF in forms | `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` |
| Money display | `{{ amount_cents\|dollars }}` |
| Money form parse | `int(round(float(request.form.get('field', '0')) * 100))` |
| Date format | YYYY-MM-DD (stored and displayed) |
| Time format | HH:MM 24-hour (stored and displayed) |
| Redirect after POST | `return redirect(url_for('blueprint.route'))` |
| Analytics data | Convert Row to dict: `[dict(r) for r in get_X(conn, ...)]` before `\|tojson` |
| Blueprint __init__.py | Empty file -- blueprint defined in routes.py |

### Authorization Matrix

| Blueprint | venue_manager | musician | promoter |
|-----------|:---:|:---:|:---:|
| auth | Y | Y | Y |
| venues | Y (own) | - | - |
| rooms | Y (own venue) | - | - |
| availability | Y (own room) | - | - |
| booking_create | - | Y | - |
| booking_manage | Y (own venue) | - | - |
| events | - | - | Y |
| tickets | Y (own booking) | - | Y (own event) |
| settlements | Y (create/approve) | Y (view own) | Y (view own) |
| search | Y | Y | Y |
| notifications | Y | Y | Y |
| analytics | Y (own) | Y (own) | Y (own) |
| dashboard | Y (own) | Y (own) | Y (own) |

---

## Swarm Agent Assignment

**Total agents:** 25
**Total files:** 90
**Validation:** No file appears in multiple assignments

---

### Agent: scaffold

**Files:**
- `venueconnect/app/__init__.py`
- `venueconnect/app/config.py`
- `venueconnect/app/filters.py`
- `venueconnect/app/templates/base.html`
- `venueconnect/app/templates/errors/404.html`
- `venueconnect/app/templates/errors/500.html`
- `venueconnect/app/static/css/style.css`
- `venueconnect/app/static/js/app.js`
- `venueconnect/requirements.txt`
- `venueconnect/run.py`
- `venueconnect/.gitignore`

**Responsibility:** Build the Flask app factory, blueprint registration, Jinja filters, base template with role-based navbar and notification badge JS, static assets, and project config files.

**Key constraints:**
- `create_app()` registers all 17 blueprints via `_register_blueprints(app)` -- see Blueprint Registry table above
- Must add `if app.debug or app.testing: app.config['WTF_CSRF_ENABLED'] = False` for smoke tests
- `app.js` polls `/api/notifications/unread-count` (endpoint owned by agent 17) on DOMContentLoaded
- `filters.py` registers `dollars` and `day_name` template filters
- `base.html` includes Chart.js CDN for analytics pages; uses `{% block head %}` for page-level scripts

---

### Agent: auth

**Files:**
- `venueconnect/app/auth/__init__.py`
- `venueconnect/app/auth/routes.py`
- `venueconnect/app/decorators.py`
- `venueconnect/app/templates/auth/login.html`
- `venueconnect/app/templates/auth/register.html`
- `venueconnect/app/templates/auth/profile.html`

**Responsibility:** Implement registration, login, logout, profile routes, and the `login_required` / `role_required` decorators that every other blueprint depends on.

**Key constraints:**
- Blueprint variable: `auth_bp`, url_prefix `/auth`
- Routes: `auth.register`, `auth.login`, `auth.logout`, `auth.profile`
- Register form fields: `username, email, password, confirm_password, role, display_name`
- Login form fields: `username, password`
- Profile form fields: `display_name, bio, genre_tags`
- `login_required` sets `g.user` from `get_user_by_id(conn, session['user_id'])`
- After login, redirect to `url_for(f'dashboard_{role}.index')` where role is the user's role
- `decorators.py` is imported by all route agents -- its signatures must not change

---

### Agent: models

**Files:**
- `venueconnect/app/db.py`
- `venueconnect/app/models.py`
- `venueconnect/app/schema.sql`

**Responsibility:** Implement all database functions (users, venues, rooms, availability, bookings, events, ticket_tiers, settlements, analytics, dashboard queries) and the SQLite schema with FTS5 triggers.

**Key constraints:**
- `get_db()` returns request-scoped connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- `check_room_available` and `create_booking` do NOT commit -- callers own the transaction
- `update_*` and `delete_*` functions do NOT commit -- callers commit
- `search_venues` uses FTS5 `venues_fts` virtual table defined in schema.sql
- All analytics functions return `list[sqlite3.Row]` or `dict` exactly as specified
- schema.sql must include FTS5 sync triggers for venues table

---

### Agent: venue-crud

**Files:**
- `venueconnect/app/venues/__init__.py`
- `venueconnect/app/venues/routes.py`
- `venueconnect/app/templates/venues/list.html`
- `venueconnect/app/templates/venues/detail.html`
- `venueconnect/app/templates/venues/form.html`

**Responsibility:** Implement venue listing, detail, create, edit, and delete routes for venue_manager role.

**Key constraints:**
- Blueprint variable: `venues_bp`, url_prefix `/venues`
- Routes: `venues.list`, `venues.detail`, `venues.create`, `venues.edit`, `venues.delete`
- Form fields (create/edit): `name, location, description, capacity, genre_tags`
- `venues.detail` renders with `venue=venue, rooms=rooms` (rooms from `get_rooms_by_venue`)
- `venues/form.html` used for both create (`venue=None`) and edit
- Ownership check: only the venue's `user_id` matches `g.user['id']`
- Imports: `from app.decorators import login_required, role_required`
- Imports: `from app.models import create_venue, get_venue, get_venues_by_manager, update_venue, delete_venue, get_rooms_by_venue`

---

### Agent: room-crud

**Files:**
- `venueconnect/app/rooms/__init__.py`
- `venueconnect/app/rooms/routes.py`
- `venueconnect/app/templates/rooms/list.html`
- `venueconnect/app/templates/rooms/detail.html`
- `venueconnect/app/templates/rooms/form.html`

**Responsibility:** Implement room listing, detail, create, edit, and delete routes scoped to a parent venue.

**Key constraints:**
- Blueprint variable: `rooms_bp`, url_prefix `/rooms`
- Routes: `rooms.list`, `rooms.detail`, `rooms.create`, `rooms.edit`, `rooms.delete`
- `rooms.list` at `/rooms/venue/<venue_id>`, renders `venue=venue, rooms=rooms`
- `rooms.create` at `/rooms/venue/<venue_id>/new`
- Form fields: `name, capacity, description, has_pa, has_lighting` (has_pa/has_lighting are checkboxes -> bool)
- Imports: `from app.models import create_room, get_room, get_rooms_by_venue, get_venue, update_room, delete_room`

---

### Agent: availability

**Files:**
- `venueconnect/app/availability/__init__.py`
- `venueconnect/app/availability/routes.py`
- `venueconnect/app/templates/availability/calendar.html`
- `venueconnect/app/templates/availability/form.html`

**Responsibility:** Implement weekly availability window management for rooms (calendar view, add, delete).

**Key constraints:**
- Blueprint variable: `availability_bp`, url_prefix `/availability`
- Routes: `availability.calendar`, `availability.add`, `availability.delete`
- `availability.calendar` renders `room=room, venue=venue, windows=windows, bookings=bookings`
- Form fields (add): `day_of_week` (0-6), `start_time` (HH:MM), `end_time` (HH:MM)
- Use `{{ day_of_week|day_name }}` filter in templates for human-readable day names
- Imports: `from app.models import get_availability_windows, create_availability_window, delete_availability_window, get_room, get_venue`

---

### Agent: booking-create

**Files:**
- `venueconnect/app/booking_create/__init__.py`
- `venueconnect/app/booking_create/routes.py`
- `venueconnect/app/templates/booking_create/browse.html`
- `venueconnect/app/templates/booking_create/room_availability.html`
- `venueconnect/app/templates/booking_create/request_form.html`
- `venueconnect/app/templates/booking_create/my_bookings.html`
- `venueconnect/app/templates/booking_create/detail.html`

**Responsibility:** Implement the musician-facing booking flow: browse venues, check room availability, submit booking request, and view booking detail/history.

**Key constraints:**
- Blueprint variable: `booking_create_bp`, url_prefix `/bookings`
- Routes: `booking_create.browse`, `booking_create.room_availability`, `booking_create.request_booking`, `booking_create.my_bookings`, `booking_create.detail`
- Request form fields: `event_name, event_date, start_time, end_time, deal_type, guarantee_amount, door_split_pct, promoter_fee_pct, tax_pct, notes`
- `guarantee_amount` is in dollars (float) -- parse as `int(round(float(val) * 100))` for cents
- CRITICAL transaction pattern for booking creation:
  ```python
  conn.execute('BEGIN IMMEDIATE')
  if not check_room_available(conn, room_id, event_date, start_time, end_time):
      conn.rollback()
      flash('Time slot conflict.', 'error')
      return redirect(...)
  booking_id = create_booking(conn, ...)
  conn.commit()
  ```
- `booking_create.detail` renders `booking=booking, history=history, settlement=settlement, tiers=tiers`
- Imports: `from app.models import get_all_venues, get_room, get_venue, get_availability_windows, check_room_available, create_booking, get_bookings_by_musician, get_booking, get_booking_history, get_settlement_by_booking, get_ticket_tiers`

---

### Agent: booking-manage

**Files:**
- `venueconnect/app/booking_manage/__init__.py`
- `venueconnect/app/booking_manage/routes.py`
- `venueconnect/app/templates/booking_manage/pending.html`
- `venueconnect/app/templates/booking_manage/detail.html`
- `venueconnect/app/templates/booking_manage/all_bookings.html`

**Responsibility:** Implement venue-manager booking management: view pending/all bookings, confirm, reject, advance, mark performed, cancel, mark paid.

**Key constraints:**
- Blueprint variable: `booking_manage_bp`, url_prefix `/manage`
- Routes: `booking_manage.pending`, `booking_manage.all_bookings`, `booking_manage.detail`, `booking_manage.confirm`, `booking_manage.reject`, `booking_manage.record_advance`, `booking_manage.mark_performed`, `booking_manage.cancel`, `booking_manage.mark_paid`
- All state transitions MUST use the exact pattern:
  ```python
  conn.execute('BEGIN IMMEDIATE')
  success = advance_booking_state(conn, booking_id, '<new_state>', g.user['id'])
  if not success:
      conn.rollback()
      flash('Cannot transition booking to this state.', 'error')
      return redirect(url_for('booking_manage.detail', booking_id=booking_id))
  conn.commit()
  ```
- `booking_manage.reject` form field: `rejection_notes`
- `booking_manage.record_advance` form field: `advance_amount`
- `booking_manage.cancel` form field: `cancel_notes`
- Imports: `from app.booking_lifecycle import advance_booking_state`
- Imports: `from app.models import get_booking, get_pending_bookings_for_venue, get_bookings_by_venue, get_booking_history, get_venues_by_manager, get_settlement_by_booking, get_ticket_tiers`

---

### Agent: booking-lifecycle

**Files:**
- `venueconnect/app/booking_lifecycle.py`

**Responsibility:** Implement the booking state machine, guard functions, audit trail writes to `booking_history`, and notification dispatch on every state transition.

**Key constraints:**
- `advance_booking_state` does NOT commit -- caller commits
- Must import `from app.notifications import create_notification`
- TRANSITIONS dict must match spec exactly (including rejected/cancelled terminal states)
- Guard functions enforce role-based permissions per transition (see plan)
- `_dispatch_notifications` uses `NOTIFICATION_MAP` templates with `{event_name}` substitution
- This file is consumed by agents 8 and 13 -- its interface must not change

---

### Agent: promoter-events

**Files:**
- `venueconnect/app/events/__init__.py`
- `venueconnect/app/events/routes.py`
- `venueconnect/app/templates/events/list.html`
- `venueconnect/app/templates/events/detail.html`
- `venueconnect/app/templates/events/form.html`

**Responsibility:** Implement promoter event management: create, edit, list, detail, and link existing bookings to events.

**Key constraints:**
- Blueprint variable: `events_bp`, url_prefix `/events`
- Routes: `events.list`, `events.detail`, `events.create`, `events.edit`, `events.link_booking`
- Create form fields: `venue_id, name, description, event_date`
- Edit form fields: `name, description, event_date`
- `events.link_booking` form field: `booking_id` (POST only)
- `events.detail` renders `event=event, bookings=bookings`
- `events.create` renders `event=None, venues=venues` (all venues for dropdown)
- Imports: `from app.models import create_event, get_event, get_events_by_promoter, update_event, get_all_venues, link_booking_to_event, get_bookings_by_event`

---

### Agent: ticket-tiers

**Files:**
- `venueconnect/app/tickets/__init__.py`
- `venueconnect/app/tickets/routes.py`
- `venueconnect/app/templates/tickets/manage.html`
- `venueconnect/app/templates/tickets/form.html`

**Responsibility:** Implement ticket tier management per booking (add tiers, edit, delete, track sold counts).

**Key constraints:**
- Blueprint variable: `tickets_bp`, url_prefix `/tickets`
- Routes: `tickets.manage`, `tickets.add`, `tickets.edit`, `tickets.delete`
- `tickets.manage` at `/tickets/booking/<booking_id>`, renders `booking=booking, tiers=tiers`
- Add form fields: `name, price_dollars, quantity` (price_dollars is float -> cents)
- Edit form fields: `name, price_dollars, quantity, sold_count`
- Parse price: `int(round(float(request.form['price_dollars']) * 100))`
- Display price: `{{ tier.price_cents|dollars }}`
- Imports: `from app.models import get_booking, get_ticket_tiers, create_ticket_tier, update_ticket_tier, delete_ticket_tier`

---

### Agent: settlement-engine

**Files:**
- `venueconnect/app/settlement_engine.py`

**Responsibility:** Implement the pure calculation function for settlement math (no DB access, integer cents only).

**Key constraints:**
- `calculate_settlement` signature must match spec exactly
- Returns dict with keys: `musician_payout_cents, venue_share_cents, promoter_fee_cents, tax_amount_cents`
- Negative `net_door` (door_revenue - expenses) is clamped to 0
- Promoter fee calculated on GROSS door revenue
- Tax calculated on GROSS door revenue
- deal_type='guarantee': musician gets `guarantee_cents`
- deal_type='door_split': musician gets `net_door * door_split_pct // 100`
- deal_type='hybrid': musician gets `max(guarantee_cents, net_door * door_split_pct // 100)`
- All arithmetic uses integer division (`//`) -- no floats inside this function

---

### Agent: settlement-views

**Files:**
- `venueconnect/app/settlements/__init__.py`
- `venueconnect/app/settlements/routes.py`
- `venueconnect/app/templates/settlements/list.html`
- `venueconnect/app/templates/settlements/detail.html`
- `venueconnect/app/templates/settlements/form.html`

**Responsibility:** Implement settlement creation, approval, list, detail, and PDF download routes.

**Key constraints:**
- Blueprint variable: `settlements_bp`, url_prefix `/settlements`
- Routes: `settlements.list`, `settlements.detail`, `settlements.create`, `settlements.approve`, `settlements.download_pdf`
- Create form fields: `door_revenue_dollars, expenses_dollars` (floats -> cents)
- `settlements.create` calls `calculate_settlement` then `create_settlement`
- `settlements.approve` transitions booking to 'settled' using advance_booking_state:
  ```python
  conn.execute('BEGIN IMMEDIATE')
  success = advance_booking_state(conn, booking_id, 'settled', g.user['id'])
  if not success:
      conn.rollback()
      ...
  conn.commit()
  ```
- `settlements.download_pdf` returns `Response(pdf_bytes, mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename=settlement_{settlement_id}.pdf'})`
- `settlements.create` form renders with `booking=booking, suggested_revenue_cents=suggested_revenue_cents`
- Imports: `from app.settlement_engine import calculate_settlement`
- Imports: `from app.settlement_pdf import generate_settlement_pdf`
- Imports: `from app.booking_lifecycle import advance_booking_state`
- Imports: `from app.models import get_booking, get_settlement, get_settlement_by_booking, create_settlement, approve_settlement, get_settlements_list, get_total_door_revenue_cents`

---

### Agent: settlement-pdf

**Files:**
- `venueconnect/app/settlement_pdf.py`

**Responsibility:** Implement ReportLab PDF generation for settlement sheets.

**Key constraints:**
- `generate_settlement_pdf(settlement)` takes a `sqlite3.Row` from `get_settlement()` and returns `bytes`
- Required fields from settlement Row: `event_name, event_date, venue_name, room_name, musician_name, deal_type, door_revenue_cents, expenses_cents, musician_payout_cents, venue_share_cents, promoter_fee_cents, tax_amount_cents, created_at`
- Uses ReportLab SimpleDocTemplate with letter pagesize
- Includes signature lines for venue manager and musician
- Dollar formatting: `f"${cents / 100:,.2f}"`

---

### Agent: search

**Files:**
- `venueconnect/app/search/__init__.py`
- `venueconnect/app/search/routes.py`
- `venueconnect/app/templates/search/results.html`

**Responsibility:** Implement FTS5 venue search accessible to all roles.

**Key constraints:**
- Blueprint variable: `search_bp`, url_prefix `/search`
- Routes: `search.index`
- Query parameter: `q` (GET)
- Renders `results=results, query=query`
- When `q` is empty, returns all venues (`search_venues` falls back to `get_all_venues`)
- Imports: `from app.models import search_venues`
- Only `@login_required` -- no role restriction

---

### Agent: notifications

**Files:**
- `venueconnect/app/notifications.py`

**Responsibility:** Implement the notification helper library (create, read, count, mark-read functions) used by booking_lifecycle and dashboard.

**Key constraints:**
- `create_notification` does NOT commit
- `mark_notification_read` does NOT commit
- `mark_all_read` does NOT commit
- This file is imported by `booking_lifecycle.py` (agent 9) and `dashboard_musician/routes.py` (agent 22) -- interface must not change

---

### Agent: notification-views

**Files:**
- `venueconnect/app/notification_views/__init__.py`
- `venueconnect/app/notification_views/routes.py`
- `venueconnect/app/templates/notifications/list.html`

**Responsibility:** Implement notification list, mark-read, mark-all-read routes, and the JSON unread-count API endpoint polled by the navbar badge.

**Key constraints:**
- Blueprint variable: `notification_views_bp`, url_prefix `/notifications`
- Routes: `notification_views.list`, `notification_views.mark_read`, `notification_views.mark_all_read`, `notification_views.unread_count`
- `notification_views.unread_count` at `/api/notifications/unread-count` returns `jsonify(count=N)`
- After mark-read and mark-all-read, commit and redirect to `notification_views.list`
- Imports: `from app.notifications import get_notifications, get_unread_count, mark_notification_read, mark_all_read`
- Only `@login_required` -- no role restriction

---

### Agent: analytics-venue

**Files:**
- `venueconnect/app/analytics_venue/__init__.py`
- `venueconnect/app/analytics_venue/routes.py`
- `venueconnect/app/templates/analytics/venue.html`

**Responsibility:** Implement venue analytics dashboard showing revenue by month, room occupancy, and genre distribution using Chart.js.

**Key constraints:**
- Blueprint variable: `analytics_venue_bp`, url_prefix `/analytics/venue`
- Route: `analytics_venue.index` at `/`
- Renders `revenue_data=revenue_data, occupancy_data=occupancy_data, genre_data=genre_data, venue=venue`
- Convert Row to dict before passing to template: `[dict(r) for r in get_X(conn, ...)]`
- Chart.js loaded in `{% block head %}` via CDN
- Data passed as `{{ revenue_data|tojson }}` in template scripts
- Imports: `from app.models import get_venue_revenue_by_month, get_venue_occupancy_by_room, get_venue_genre_distribution, get_venues_by_manager`

---

### Agent: analytics-musician

**Files:**
- `venueconnect/app/analytics_musician/__init__.py`
- `venueconnect/app/analytics_musician/routes.py`
- `venueconnect/app/templates/analytics/musician.html`

**Responsibility:** Implement musician analytics showing earnings by month, venues played, and booking success rate.

**Key constraints:**
- Blueprint variable: `analytics_musician_bp`, url_prefix `/analytics/musician`
- Route: `analytics_musician.index` at `/`
- Renders `earnings_data=earnings_data, venues_data=venues_data, success_data=success_data`
- `success_data` is a dict (not a Row list) -- pass directly to `|tojson`
- Convert Row lists to dicts before passing to template
- Imports: `from app.models import get_musician_earnings_by_month, get_musician_venues_played, get_musician_booking_success_rate`

---

### Agent: analytics-promoter

**Files:**
- `venueconnect/app/analytics_promoter/__init__.py`
- `venueconnect/app/analytics_promoter/routes.py`
- `venueconnect/app/templates/analytics/promoter.html`

**Responsibility:** Implement promoter analytics showing revenue by month, settlements by venue, and event status counts.

**Key constraints:**
- Blueprint variable: `analytics_promoter_bp`, url_prefix `/analytics/promoter`
- Route: `analytics_promoter.index` at `/`
- Renders `revenue_data=revenue_data, settlements_data=settlements_data, status_data=status_data`
- Convert Row lists to dicts before passing to template
- Imports: `from app.models import get_promoter_revenue_by_month, get_promoter_settlements_by_venue, get_promoter_event_status_counts`

---

### Agent: dashboard-venue

**Files:**
- `venueconnect/app/dashboard_venue/__init__.py`
- `venueconnect/app/dashboard_venue/routes.py`
- `venueconnect/app/templates/dashboard/venue.html`

**Responsibility:** Implement venue manager dashboard showing upcoming confirmed bookings, pending request count, and venue list.

**Key constraints:**
- Blueprint variable: `dashboard_venue_bp`, url_prefix `/dashboard/venue`
- Route: `dashboard_venue.index` at `/`
- Renders `upcoming_bookings=upcoming_bookings, pending_count=pending_count, venues=venues`
- Fetch data for all venues owned by the logged-in manager
- Imports: `from app.models import get_venue_upcoming_bookings, get_venue_pending_count, get_venues_by_manager`

---

### Agent: dashboard-musician

**Files:**
- `venueconnect/app/dashboard_musician/__init__.py`
- `venueconnect/app/dashboard_musician/routes.py`
- `venueconnect/app/templates/dashboard/musician.html`

**Responsibility:** Implement musician dashboard showing upcoming gigs, pending booking count, and recent notifications.

**Key constraints:**
- Blueprint variable: `dashboard_musician_bp`, url_prefix `/dashboard/musician`
- Route: `dashboard_musician.index` at `/`
- Renders `upcoming_gigs=upcoming_gigs, pending_count=pending_count, recent_notifications=recent_notifications`
- `recent_notifications` = `get_notifications(conn, g.user['id'], limit=5)`
- Imports: `from app.models import get_musician_upcoming_gigs, get_musician_pending_count`
- Imports: `from app.notifications import get_notifications`

---

### Agent: dashboard-promoter

**Files:**
- `venueconnect/app/dashboard_promoter/__init__.py`
- `venueconnect/app/dashboard_promoter/routes.py`
- `venueconnect/app/templates/dashboard/promoter.html`

**Responsibility:** Implement promoter dashboard showing upcoming events and settlement status summary.

**Key constraints:**
- Blueprint variable: `dashboard_promoter_bp`, url_prefix `/dashboard/promoter`
- Route: `dashboard_promoter.index` at `/`
- Renders `upcoming_events=upcoming_events, settlement_status=settlement_status`
- `settlement_status` is a dict with keys `total_settlements` and `pending_settlements`
- Imports: `from app.models import get_promoter_upcoming_events, get_promoter_settlement_status`

---

### Agent: seed

**Files:**
- `venueconnect/seed.py`

**Responsibility:** Implement the database seed script that creates demo users, venue, rooms, availability windows, bookings in various states, ticket tiers, settlement, event, and notifications.

**Key constraints:**
- Sets `SECRET_KEY` env var before importing app
- Calls `init_db()` then uses raw `conn.execute` with `INSERT OR IGNORE` for idempotency
- Demo password for all accounts: `password123`
- Demo accounts: `bluenote_mgr` (venue_manager), `jazz_trio` (musician), `rock_band` (musician), `city_nights` (promoter)
- Must create at least: 1 venue, 2 rooms, 3 availability windows, 3 bookings (confirmed/performed/requested), 1 booking_history row, 2 ticket_tiers, 1 settlement (draft), 1 event, 3 notifications
- Run with: `.venv/bin/python seed.py`

---

### Agent: tests

**Files:**
- `venueconnect/test_smoke.py`

**Responsibility:** Implement smoke tests that verify all major routes return expected status codes with and without authentication.

**Key constraints:**
- Sets `SECRET_KEY` and `FLASK_DEBUG=1` before importing app (disables CSRF)
- Calls `init_db()` in app context before running tests
- Tests: `/health` (200), `/auth/login` (200), `/auth/register` (200), root redirect (302)
- Registers two test users (venue_manager + musician) and logs in to test authenticated routes
- Verifies role protection: musician blocked from `/venues/new` (403)
- Tests musician routes: `/bookings/browse`, `/bookings/mine`, `/dashboard/musician`
- Tests venue_manager routes: `/dashboard/venue`, `/venues/`, `/venues/new`, `/analytics/venue`, `/settlements/`
- Tests shared routes: `/search/`, `/notifications/`, `/api/notifications/unread-count`
- Run with: `.venv/bin/python test_smoke.py`
- CSRF is disabled because scaffold agent adds `WTF_CSRF_ENABLED = False` when `app.debug` is True

---

STATUS: PASS
