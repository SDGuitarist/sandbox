---
title: "CoWorkFlow -- Coworking Space Manager"
date: 2026-05-21
brainstorm: docs/brainstorms/2026-05-21-coworking-space-manager-brainstorm.md
swarm: true
agents: 22
feed_forward:
  risk: "Room booking double-booking prevention -- BEGIN IMMEDIATE + try/except/ROLLBACK + partial UNIQUE index on (room_id, booking_date, slot_start) WHERE status != 'cancelled'. Desk booking conflict logic for AM/PM/full overlap (FC29 territory)."
  verify_first: true
---

# Shared Interface Spec -- CoWorkFlow

Single-location coworking space management system. Admin-only (one user). Flask +
SQLite + Jinja2 + Bootstrap 5 (CDN). 22-agent model/route vertical split.

9 domains: members, membership plans, desks, meeting rooms, desk bookings, room
bookings, billing/invoices, payments, amenities.

## App Configuration

```python
# coworkflow/app/__init__.py
import os
from flask import Flask
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    if not app.debug and app.config['SECRET_KEY'] == 'dev-fallback-key':
        raise RuntimeError('SECRET_KEY must be set in production')

    from app.auth import ADMIN_PASSWORD
    if not app.debug and ADMIN_PASSWORD == 'dev-password-123':
        raise RuntimeError('ADMIN_PASSWORD must be set in production')

    app.config['SESSION_COOKIE_SECURE'] = not app.debug
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    csrf.init_app(app)

    from app.db import init_db, close_db
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    from app.filters import register_filters
    register_filters(app)

    # Blueprint registration -- exact order
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.dashboard.routes import bp as dashboard_bp
    from app.blueprints.members.routes import bp as members_bp
    from app.blueprints.plans.routes import bp as plans_bp
    from app.blueprints.desks.routes import bp as desks_bp
    from app.blueprints.rooms.routes import bp as rooms_bp
    from app.blueprints.desk_bookings.routes import bp as desk_bookings_bp
    from app.blueprints.room_bookings.routes import bp as room_bookings_bp
    from app.blueprints.billing.routes import bp as billing_bp
    from app.blueprints.payments.routes import bp as payments_bp
    from app.blueprints.amenities.routes import bp as amenities_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(plans_bp, url_prefix='/plans')
    app.register_blueprint(desks_bp, url_prefix='/desks')
    app.register_blueprint(rooms_bp, url_prefix='/rooms')
    app.register_blueprint(desk_bookings_bp, url_prefix='/desk-bookings')
    app.register_blueprint(room_bookings_bp, url_prefix='/room-bookings')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(payments_bp, url_prefix='/payments')
    app.register_blueprint(amenities_bp, url_prefix='/amenities')

    return app
```

**Requirements (requirements.txt):**
```
flask>=3.0
flask-wtf>=1.2
```

## Database Connection

```python
# coworkflow/app/db.py
import sqlite3
import os
from flask import g

DATABASE = os.environ.get('DATABASE_PATH', 'coworkflow.db')

def get_db():
    """Get database connection. Returns a plain connection (NOT a context manager).

    Usage:
        conn = get_db()
        members = get_all_members(conn)

    DO NOT use: with get_db() as conn:  -- get_db is NOT a context manager.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database from schema.sql."""
    conn = get_db()
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
```

**CRITICAL: `get_db()` is NOT a context manager. It returns a plain connection.
Do NOT use `with get_db() as conn:`. Instead use:**

```python
conn = get_db()
members = get_all_members(conn)
```

**CRITICAL: `isolation_level=None` is MANDATORY. Without it, Python's sqlite3
module creates implicit transactions that conflict with manual `BEGIN IMMEDIATE`.**

**CRITICAL: All three PRAGMAs (`journal_mode=WAL`, `foreign_keys=ON`,
`busy_timeout=5000`) must be set in `get_db()`. There are no other connection
paths in this app. If you add a new connection path (worker, script, etc.),
it MUST set the same PRAGMAs. (FC40)**

## Authentication

```python
# coworkflow/app/auth.py
import os
import hmac
import functools
from flask import session, redirect, url_for, flash, request

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'dev-password-123')
# Startup guard: core agent must add this check in create_app():
#   from app.auth import ADMIN_PASSWORD
#   if not app.debug and ADMIN_PASSWORD == 'dev-password-123':
#       raise RuntimeError('ADMIN_PASSWORD must be set in production')

def login_required(f):
    """Decorator: redirect to login if not authenticated."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated

def check_password(password):
    """Check if password matches admin password. Returns bool.
    Uses hmac.compare_digest for timing-safe comparison."""
    return hmac.compare_digest(password.encode(), ADMIN_PASSWORD.encode())
```

**Rule:** Every route except `auth.login_page`, `auth.login`, and `dashboard.health`
MUST use `@login_required`. The decorator goes AFTER `@bp.route`.

## Jinja Filters

```python
# coworkflow/app/filters.py
from datetime import datetime

def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert cents to dollar display: 1500 -> '$15.00'"""
        if cents is None:
            return '$0.00'
        return f'${cents / 100:.2f}'

    @app.template_filter('dollars_raw')
    def dollars_raw_filter(cents):
        """Convert cents to raw decimal for form prefill: 1500 -> '15.00'
        Usage in templates: value="{{ plan['price_cents']|dollars_raw }}"
        This is the FORM PREFILL surface -- different from |dollars (display)."""
        if cents is None:
            return '0.00'
        return f'{cents / 100:.2f}'

    @app.template_filter('date_format')
    def date_format_filter(date_str, fmt='%b %d, %Y'):
        """Format ISO date string: '2026-05-21' -> 'May 21, 2026'"""
        if not date_str:
            return ''
        return datetime.fromisoformat(date_str).strftime(fmt)

    @app.template_filter('time_format')
    def time_format_filter(time_str):
        """Format time string: '14:30' -> '2:30 PM'"""
        if not time_str:
            return ''
        return datetime.strptime(time_str, '%H:%M').strftime('%-I:%M %p')
```

**Money has THREE surfaces (FC from Personal Finance Tracker):**
1. **Display:** `{{ value|dollars }}` → `$15.00`
2. **Form prefill:** `{{ value|dollars_raw }}` → `15.00` (for edit form input values)
3. **Parse:** `round(float(request.form.get('price', '0')) * 100)` with NaN/Inf guards

## Database Schema

```sql
-- coworkflow/schema.sql

CREATE TABLE IF NOT EXISTS membership_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    price_cents INTEGER NOT NULL,
    billing_cycle TEXT NOT NULL DEFAULT 'monthly' CHECK(billing_cycle IN ('monthly', 'quarterly', 'annual')),
    description TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    membership_plan_id INTEGER REFERENCES membership_plans(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'frozen', 'cancelled')),
    join_date TEXT NOT NULL DEFAULT (date('now')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_members_membership_plan_id ON members(membership_plan_id);
CREATE INDEX IF NOT EXISTS idx_members_status ON members(status);

CREATE TABLE IF NOT EXISTS desks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meeting_rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    capacity INTEGER NOT NULL DEFAULT 4,
    hourly_rate_cents INTEGER NOT NULL DEFAULT 0,
    location TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS desk_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    desk_id INTEGER NOT NULL REFERENCES desks(id) ON DELETE RESTRICT,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    booking_date TEXT NOT NULL,
    block TEXT NOT NULL CHECK(block IN ('am', 'pm', 'full')),
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_desk_bookings_desk_id ON desk_bookings(desk_id);
CREATE INDEX IF NOT EXISTS idx_desk_bookings_member_id ON desk_bookings(member_id);
CREATE INDEX IF NOT EXISTS idx_desk_bookings_date ON desk_bookings(booking_date);

CREATE TABLE IF NOT EXISTS room_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES meeting_rooms(id) ON DELETE RESTRICT,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    booking_date TEXT NOT NULL,
    slot_start TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_room_bookings_no_double
    ON room_bookings(room_id, booking_date, slot_start)
    WHERE status != 'cancelled';
CREATE INDEX IF NOT EXISTS idx_room_bookings_room_id ON room_bookings(room_id);
CREATE INDEX IF NOT EXISTS idx_room_bookings_member_id ON room_bookings(member_id);
CREATE INDEX IF NOT EXISTS idx_room_bookings_date ON room_bookings(booking_date);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    amount_cents INTEGER NOT NULL,
    description TEXT NOT NULL,
    billing_date TEXT NOT NULL DEFAULT (date('now')),
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'paid', 'overdue', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_invoices_member_id ON invoices(member_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    amount_cents INTEGER NOT NULL,
    payment_date TEXT NOT NULL DEFAULT (date('now')),
    payment_method TEXT NOT NULL DEFAULT 'cash' CHECK(payment_method IN ('cash', 'card', 'bank_transfer', 'other')),
    reference_number TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);

CREATE TABLE IF NOT EXISTS amenities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    is_available INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

## Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| membership_plans | models/plan.py | member_routes (dropdown), billing_routes (plan price lookup), dashboard_routes (stats) |
| members | models/member.py | desk_booking_routes (dropdown), room_booking_routes (dropdown), billing_routes (dropdown), dashboard_routes (stats) |
| desks | models/desk.py | desk_booking_routes (dropdown), dashboard_routes (availability) |
| meeting_rooms | models/room.py | room_booking_routes (dropdown), dashboard_routes (stats) |
| desk_bookings | models/desk_booking.py | desk_routes (booking count display), dashboard_routes (today) |
| room_bookings | models/room_booking.py | room_routes (booking count display), dashboard_routes (today) |
| invoices | models/invoice.py | payment_routes (dropdown), dashboard_routes (revenue) |
| payments | models/payment.py | billing_routes (payment history on detail) |
| amenities | models/amenity.py | dashboard_routes (count) |

## Model Functions

### models/member.py (member_models agent)

```python
import sqlite3

def create_member(conn: sqlite3.Connection, name: str, email: str,
                  phone: str, company: str,
                  membership_plan_id: int | None, notes: str) -> int:
    """Create a new member. Returns the new member's ID.
    Usage:
        member_id = create_member(conn, 'John Doe', 'john@example.com',
                                  '555-0100', 'Acme Corp', 1, '')
        return redirect(url_for('members.detail', member_id=member_id))
    Commits: yes (conn.commit())
    """

def get_member(conn: sqlite3.Connection, member_id: int) -> sqlite3.Row | None:
    """Get member by ID with membership plan name joined.
    Returns Row with columns: id, name, email, phone, company,
    membership_plan_id, status, join_date, notes, created_at, updated_at,
    plan_name (from LEFT JOIN membership_plans, may be NULL).
    Usage:
        member = get_member(conn, member_id)
        if member is None:
            abort(404)
    """

def get_all_members(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all members ordered by name. Includes plan_name LEFT JOIN."""

def update_member(conn: sqlite3.Connection, member_id: int, name: str,
                  email: str, phone: str, company: str,
                  membership_plan_id: int | None, status: str,
                  notes: str) -> None:
    """Update member fields. Also sets updated_at = datetime('now').
    Commits: yes."""

def delete_member(conn: sqlite3.Connection, member_id: int) -> None:
    """Delete member. Commits: yes.
    Raises sqlite3.IntegrityError if member has desk_bookings, room_bookings,
    or invoices (all ON DELETE RESTRICT).
    """

def count_active_members(conn: sqlite3.Connection) -> int:
    """Count members with status='active'. Returns int.
    Usage:
        active_count = count_active_members(conn)
        # active_count is an int, NOT a Row
    """

def search_members(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    """Search members by name or email (LIKE %query%). Returns list.
    MUST use parameterized query:
        cursor.execute(
            "SELECT ... FROM members WHERE name LIKE ? OR email LIKE ?",
            (f"%{query}%", f"%{query}%")
        )
    NEVER use f-string or .format() with the query parameter.
    """
```

### models/plan.py (plan_models agent)

```python
import sqlite3

def create_plan(conn: sqlite3.Connection, name: str, price_cents: int,
                billing_cycle: str, description: str) -> int:
    """Create membership plan. Returns new plan ID.
    Usage:
        plan_id = create_plan(conn, 'Monthly', 4999, 'monthly', 'Basic desk access')
        return redirect(url_for('plans.list_plans'))
    Commits: yes
    """

def get_plan(conn: sqlite3.Connection, plan_id: int) -> sqlite3.Row | None:
    """Get membership plan by ID. Returns Row or None."""

def get_all_plans(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all membership plans ordered by name."""

def get_active_plans(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get plans with is_active=1."""

def update_plan(conn: sqlite3.Connection, plan_id: int, name: str,
                price_cents: int, billing_cycle: str,
                description: str, is_active: int) -> None:
    """Update plan fields. Commits: yes."""

def delete_plan(conn: sqlite3.Connection, plan_id: int) -> None:
    """Delete plan. Commits: yes.
    FK constraint is SET NULL -- membership_plan_id on members becomes NULL.
    No IntegrityError raised.
    """
```

### models/desk.py (desk_models agent)

```python
import sqlite3

def create_desk(conn: sqlite3.Connection, name: str, location: str) -> int:
    """Create a desk. Returns new desk ID.
    Usage:
        desk_id = create_desk(conn, 'Desk A1', 'Ground Floor')
        return redirect(url_for('desks.list_desks'))
    Commits: yes
    """

def get_desk(conn: sqlite3.Connection, desk_id: int) -> sqlite3.Row | None:
    """Get desk by ID."""

def get_all_desks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all desks ordered by name."""

def get_active_desks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get desks with is_active=1."""

def update_desk(conn: sqlite3.Connection, desk_id: int, name: str,
                location: str, is_active: int) -> None:
    """Update desk fields. Commits: yes."""

def delete_desk(conn: sqlite3.Connection, desk_id: int) -> None:
    """Delete desk. Commits: yes.
    Raises sqlite3.IntegrityError if desk has bookings (ON DELETE RESTRICT).
    """
```

### models/room.py (room_models agent)

```python
import sqlite3

def create_room(conn: sqlite3.Connection, name: str, capacity: int,
                hourly_rate_cents: int, location: str) -> int:
    """Create a meeting room. Returns new room ID.
    Usage:
        room_id = create_room(conn, 'Board Room', 12, 5000, '2nd Floor')
        return redirect(url_for('rooms.list_rooms'))
    Commits: yes
    """

def get_room(conn: sqlite3.Connection, room_id: int) -> sqlite3.Row | None:
    """Get room by ID."""

def get_all_rooms(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all meeting rooms ordered by name."""

def get_active_rooms(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get rooms with is_active=1."""

def update_room(conn: sqlite3.Connection, room_id: int, name: str,
                capacity: int, hourly_rate_cents: int,
                location: str, is_active: int) -> None:
    """Update room fields. Commits: yes."""

def delete_room(conn: sqlite3.Connection, room_id: int) -> None:
    """Delete room. Commits: yes.
    Raises sqlite3.IntegrityError if room has bookings (ON DELETE RESTRICT).
    """
```

### models/desk_booking.py (desk_booking_models agent)

```python
import sqlite3

def create_desk_booking(conn: sqlite3.Connection, desk_id: int,
                        member_id: int, booking_date: str,
                        block: str) -> int | None:
    """Book a desk for a block. Returns booking ID or None if conflict.

    BEGIN IMMEDIATE -> conflict check -> INSERT -> COMMIT.
    With try/except/ROLLBACK wrapper.

    Conflict rules:
    - block='am': conflicts with existing 'am' or 'full' (same desk+date, status='confirmed')
    - block='pm': conflicts with existing 'pm' or 'full' (same desk+date, status='confirmed')
    - block='full': conflicts with ANY existing booking (same desk+date, status='confirmed')

    Usage:
        booking_id = create_desk_booking(conn, desk_id, member_id, '2026-06-01', 'am')
        if booking_id is None:
            flash('Desk already booked for that block.', 'error')
            return redirect(url_for('desk_bookings.new_booking'))
        return redirect(url_for('desk_bookings.detail', booking_id=booking_id))

    EXACT IMPLEMENTATION (agents MUST follow this pattern):
    ```
    try:
        conn.execute('BEGIN IMMEDIATE')
        if block == 'full':
            conflict = conn.execute(
                "SELECT 1 FROM desk_bookings WHERE desk_id=? AND booking_date=? AND status='confirmed'",
                (desk_id, booking_date)
            ).fetchone()
        elif block == 'am':
            conflict = conn.execute(
                "SELECT 1 FROM desk_bookings WHERE desk_id=? AND booking_date=? AND block IN ('am','full') AND status='confirmed'",
                (desk_id, booking_date)
            ).fetchone()
        else:  # pm
            conflict = conn.execute(
                "SELECT 1 FROM desk_bookings WHERE desk_id=? AND booking_date=? AND block IN ('pm','full') AND status='confirmed'",
                (desk_id, booking_date)
            ).fetchone()
        if conflict:
            conn.execute('ROLLBACK')
            return None
        conn.execute(
            "INSERT INTO desk_bookings (desk_id, member_id, booking_date, block) VALUES (?, ?, ?, ?)",
            (desk_id, member_id, booking_date, block)
        )
        booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute('COMMIT')
        return booking_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
    ```
    Commits: BEGIN IMMEDIATE transaction (manages own transaction boundary)
    Error handling: try/except with ROLLBACK on any exception
    """

def get_desk_booking(conn: sqlite3.Connection, booking_id: int) -> sqlite3.Row | None:
    """Get desk booking by ID. Joins desk name and member name.
    Columns: id, desk_id, member_id, booking_date, block, status,
    created_at, updated_at, desk_name, member_name.
    """

def get_all_desk_bookings(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all desk bookings ordered by booking_date DESC, then block.
    Joins desk name and member name."""

def get_desk_bookings_by_date(conn: sqlite3.Connection, booking_date: str) -> list[sqlite3.Row]:
    """Get desk bookings for a specific date. Joins desk + member names."""

def get_desk_bookings_by_member(conn: sqlite3.Connection, member_id: int) -> list[sqlite3.Row]:
    """Get desk bookings for a specific member. Joins desk name."""

def cancel_desk_booking(conn: sqlite3.Connection, booking_id: int) -> None:
    """Set booking status to 'cancelled'. Also sets updated_at.
    Commits: yes.
    """

def count_desk_bookings_today(conn: sqlite3.Connection) -> int:
    """Count confirmed desk bookings for today. Returns int.
    Usage:
        today_count = count_desk_bookings_today(conn)
        # today_count is an int
    """
```

### models/room_booking.py (room_booking_models agent)

```python
import sqlite3

VALID_SLOT_STARTS = [
    '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
    '11:00', '11:30', '12:00', '12:30', '13:00', '13:30',
    '14:00', '14:30', '15:00', '15:30', '16:00', '16:30',
    '17:00', '17:30'
]

def create_room_booking(conn: sqlite3.Connection, room_id: int,
                        member_id: int, booking_date: str,
                        slot_start: str, purpose: str) -> int | None:
    """Book a single 30-min room slot. Returns booking ID or None if conflict.

    BEGIN IMMEDIATE -> conflict check -> INSERT -> COMMIT.
    With try/except/ROLLBACK wrapper.

    The partial UNIQUE index (room_id, booking_date, slot_start WHERE
    status != 'cancelled') provides a DB-level safety net. This function
    adds application-level checking for clearer error messages.

    Usage:
        booking_id = create_room_booking(conn, room_id, member_id,
                                          '2026-06-01', '09:00', 'Team sync')
        if booking_id is None:
            flash('Room slot already booked.', 'error')
            return redirect(url_for('room_bookings.new_booking'))
        return redirect(url_for('room_bookings.detail', booking_id=booking_id))

    EXACT IMPLEMENTATION (agents MUST follow this pattern):
    ```
    try:
        conn.execute('BEGIN IMMEDIATE')
        conflict = conn.execute(
            "SELECT 1 FROM room_bookings WHERE room_id=? AND booking_date=? AND slot_start=? AND status='confirmed'",
            (room_id, booking_date, slot_start)
        ).fetchone()
        if conflict:
            conn.execute('ROLLBACK')
            return None
        conn.execute(
            "INSERT INTO room_bookings (room_id, member_id, booking_date, slot_start, purpose) VALUES (?, ?, ?, ?, ?)",
            (room_id, member_id, booking_date, slot_start, purpose)
        )
        booking_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute('COMMIT')
        return booking_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
    ```
    Commits: BEGIN IMMEDIATE transaction (manages own transaction boundary)
    Error handling: try/except with ROLLBACK on any exception
    """

def get_room_booking(conn: sqlite3.Connection, booking_id: int) -> sqlite3.Row | None:
    """Get room booking by ID. Joins room name and member name.
    Columns: id, room_id, member_id, booking_date, slot_start, purpose,
    status, created_at, room_name, member_name, room_capacity.
    """

def get_all_room_bookings(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all room bookings ordered by booking_date DESC, slot_start.
    Joins room name and member name."""

def get_room_bookings_by_date(conn: sqlite3.Connection, booking_date: str) -> list[sqlite3.Row]:
    """Get room bookings for a specific date. Joins room + member names.
    Ordered by room_name, slot_start."""

def get_room_bookings_by_member(conn: sqlite3.Connection, member_id: int) -> list[sqlite3.Row]:
    """Get room bookings for a specific member. Joins room name."""

def get_available_slots(conn: sqlite3.Connection, room_id: int,
                        booking_date: str) -> list[str]:
    """Get available 30-min slot starts for a room on a date.
    Returns list of slot_start strings not yet booked (status='confirmed').
    Usage:
        available = get_available_slots(conn, room_id, '2026-06-01')
        # available is a list like ['08:00', '08:30', '10:00', ...]
    Compares VALID_SLOT_STARTS against booked slots.
    """

def cancel_room_booking(conn: sqlite3.Connection, booking_id: int) -> None:
    """Set booking status to 'cancelled'. Also sets updated_at = datetime('now').
    Commits: yes."""

def count_room_bookings_today(conn: sqlite3.Connection) -> int:
    """Count confirmed room bookings for today. Returns int.
    Usage:
        today_count = count_room_bookings_today(conn)
    """
```

### models/invoice.py (invoice_models agent)

```python
import sqlite3

def create_invoice(conn: sqlite3.Connection, member_id: int,
                   amount_cents: int, description: str,
                   due_date: str) -> int:
    """Create invoice. Returns new invoice ID.
    Usage:
        invoice_id = create_invoice(conn, member_id, 4999, 'Monthly plan', '2026-06-21')
        return redirect(url_for('billing.detail', invoice_id=invoice_id))
    Commits: yes
    """

def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> sqlite3.Row | None:
    """Get invoice by ID. Joins member name.
    Columns: id, member_id, amount_cents, description, billing_date,
    due_date, status, created_at, updated_at, member_name.
    """

def get_all_invoices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all invoices ordered by billing_date DESC. Joins member name."""

def get_invoices_by_member(conn: sqlite3.Connection, member_id: int) -> list[sqlite3.Row]:
    """Get invoices for a specific member."""

def get_invoices_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    """Get invoices filtered by status. Joins member name."""

def update_invoice(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, description: str,
                   due_date: str, status: str) -> None:
    """Update invoice fields. Also sets updated_at. Commits: yes."""

def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Delete invoice. Commits: yes.
    Raises sqlite3.IntegrityError if invoice has payments (ON DELETE RESTRICT).
    """

def get_pending_invoice_count(conn: sqlite3.Connection) -> int:
    """Count invoices with status='pending'. Returns int."""
```

### models/payment.py (payment_models agent)

```python
import sqlite3

def create_payment(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, payment_date: str,
                   payment_method: str, reference_number: str,
                   notes: str) -> int:
    """Create payment linked to invoice. Returns new payment ID.
    Usage:
        payment_id = create_payment(conn, invoice_id, 4999, '2026-05-21',
                                     'card', 'TXN-123', '')
        return redirect(url_for('payments.list_payments'))
    Commits: yes
    """

def get_payment(conn: sqlite3.Connection, payment_id: int) -> sqlite3.Row | None:
    """Get payment by ID. Joins invoice description and member name.
    Columns: id, invoice_id, amount_cents, payment_date, payment_method,
    reference_number, notes, created_at, invoice_description, member_name.
    """

def get_all_payments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all payments ordered by payment_date DESC. Joins invoice + member."""

def get_payments_by_invoice(conn: sqlite3.Connection, invoice_id: int) -> list[sqlite3.Row]:
    """Get payments for a specific invoice."""

def delete_payment(conn: sqlite3.Connection, payment_id: int) -> None:
    """Delete payment. Commits: yes."""

def get_total_paid_for_invoice(conn: sqlite3.Connection, invoice_id: int) -> int:
    """Sum of amount_cents for payments linked to invoice_id. Returns int.
    Usage:
        paid_cents = get_total_paid_for_invoice(conn, invoice_id)
        # paid_cents is an int
    """

def get_total_revenue_this_month(conn: sqlite3.Connection) -> int:
    """Sum of amount_cents from payments with payment_date in current month.
    Returns int (cents).
    Usage:
        revenue_cents = get_total_revenue_this_month(conn)
        # revenue_cents is an int, use |dollars filter for display
    """
```

### models/amenity.py (amenity_models agent)

```python
import sqlite3

def create_amenity(conn: sqlite3.Connection, name: str,
                   description: str) -> int:
    """Create amenity. Returns new amenity ID.
    Usage:
        amenity_id = create_amenity(conn, 'High-Speed WiFi', '1 Gbps fiber')
        return redirect(url_for('amenities.list_amenities'))
    Commits: yes
    """

def get_amenity(conn: sqlite3.Connection, amenity_id: int) -> sqlite3.Row | None:
    """Get amenity by ID."""

def get_all_amenities(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all amenities ordered by name."""

def update_amenity(conn: sqlite3.Connection, amenity_id: int, name: str,
                   description: str, is_available: int) -> None:
    """Update amenity fields. Commits: yes."""

def delete_amenity(conn: sqlite3.Connection, amenity_id: int) -> None:
    """Delete amenity. Commits: yes. No FK constraints -- safe to delete."""

def count_amenities(conn: sqlite3.Connection) -> int:
    """Count all amenities. Returns int."""
```

## Route Table

| Method | Path | Handler | Status | Template |
|--------|------|---------|--------|----------|
| GET | /health | dashboard.health | 200 | JSON |
| GET | / | dashboard.index | 200 | dashboard/index.html |
| GET | /login | auth.login_page | 200 | auth/login.html |
| POST | /login | auth.login | 302 | redirect |
| POST | /logout | auth.logout | 302 | redirect |
| GET | /members/ | members.list_members | 200 | members/list.html |
| GET | /members/new | members.new_member | 200 | members/form.html |
| POST | /members/new | members.create | 302 | redirect |
| GET | /members/\<int:member_id\> | members.detail | 200 | members/detail.html |
| GET | /members/\<int:member_id\>/edit | members.edit_form | 200 | members/form.html |
| POST | /members/\<int:member_id\>/edit | members.update | 302 | redirect |
| POST | /members/\<int:member_id\>/delete | members.delete | 302 | redirect |
| GET | /plans/ | plans.list_plans | 200 | plans/list.html |
| GET | /plans/new | plans.new_plan | 200 | plans/form.html |
| POST | /plans/new | plans.create | 302 | redirect |
| GET | /plans/\<int:plan_id\>/edit | plans.edit_form | 200 | plans/form.html |
| POST | /plans/\<int:plan_id\>/edit | plans.update | 302 | redirect |
| POST | /plans/\<int:plan_id\>/delete | plans.delete | 302 | redirect |
| GET | /desks/ | desks.list_desks | 200 | desks/list.html |
| GET | /desks/new | desks.new_desk | 200 | desks/form.html |
| POST | /desks/new | desks.create | 302 | redirect |
| GET | /desks/\<int:desk_id\>/edit | desks.edit_form | 200 | desks/form.html |
| POST | /desks/\<int:desk_id\>/edit | desks.update | 302 | redirect |
| POST | /desks/\<int:desk_id\>/delete | desks.delete | 302 | redirect |
| GET | /rooms/ | rooms.list_rooms | 200 | rooms/list.html |
| GET | /rooms/new | rooms.new_room | 200 | rooms/form.html |
| POST | /rooms/new | rooms.create | 302 | redirect |
| GET | /rooms/\<int:room_id\> | rooms.detail | 200 | rooms/detail.html |
| GET | /rooms/\<int:room_id\>/edit | rooms.edit_form | 200 | rooms/form.html |
| POST | /rooms/\<int:room_id\>/edit | rooms.update | 302 | redirect |
| POST | /rooms/\<int:room_id\>/delete | rooms.delete | 302 | redirect |
| GET | /desk-bookings/ | desk_bookings.list_bookings | 200 | desk_bookings/list.html |
| GET | /desk-bookings/new | desk_bookings.new_booking | 200 | desk_bookings/form.html |
| POST | /desk-bookings/new | desk_bookings.create | 302 | redirect |
| GET | /desk-bookings/\<int:booking_id\> | desk_bookings.detail | 200 | desk_bookings/detail.html |
| POST | /desk-bookings/\<int:booking_id\>/cancel | desk_bookings.cancel | 302 | redirect |
| GET | /room-bookings/ | room_bookings.list_bookings | 200 | room_bookings/list.html |
| GET | /room-bookings/new | room_bookings.new_booking | 200 | room_bookings/form.html |
| POST | /room-bookings/new | room_bookings.create | 302 | redirect |
| GET | /room-bookings/\<int:booking_id\> | room_bookings.detail | 200 | room_bookings/detail.html |
| POST | /room-bookings/\<int:booking_id\>/cancel | room_bookings.cancel | 302 | redirect |
| GET | /billing/ | billing.list_invoices | 200 | billing/list.html |
| GET | /billing/new | billing.new_invoice | 200 | billing/form.html |
| POST | /billing/new | billing.create | 302 | redirect |
| GET | /billing/\<int:invoice_id\> | billing.detail | 200 | billing/detail.html |
| GET | /billing/\<int:invoice_id\>/edit | billing.edit_form | 200 | billing/form.html |
| POST | /billing/\<int:invoice_id\>/edit | billing.update | 302 | redirect |
| POST | /billing/\<int:invoice_id\>/delete | billing.delete | 302 | redirect |
| GET | /payments/ | payments.list_payments | 200 | payments/list.html |
| GET | /payments/new | payments.new_payment | 200 | payments/form.html |
| POST | /payments/new | payments.create | 302 | redirect |
| POST | /payments/\<int:payment_id\>/delete | payments.delete | 302 | redirect |
| GET | /amenities/ | amenities.list_amenities | 200 | amenities/list.html |
| GET | /amenities/new | amenities.new_amenity | 200 | amenities/form.html |
| POST | /amenities/new | amenities.create | 302 | redirect |
| GET | /amenities/\<int:amenity_id\>/edit | amenities.edit_form | 200 | amenities/form.html |
| POST | /amenities/\<int:amenity_id\>/edit | amenities.update | 302 | redirect |
| POST | /amenities/\<int:amenity_id\>/delete | amenities.delete | 302 | redirect |

## Template Render Context

```python
# dashboard/index.html expects:
render_template('dashboard/index.html',
    active_members=count_active_members(conn),
    revenue_cents=get_total_revenue_this_month(conn),
    desk_bookings_today=count_desk_bookings_today(conn),
    room_bookings_today=count_room_bookings_today(conn),
    pending_invoices=get_pending_invoice_count(conn),
    amenity_count=count_amenities(conn),
    today_desk_bookings=get_desk_bookings_by_date(conn, today),
    today_room_bookings=get_room_bookings_by_date(conn, today)
)

# members/list.html expects:
# If request.args.get('q') is provided, use search_members(conn, q)
# Otherwise use get_all_members(conn)
q = request.args.get('q', '').strip()
members = search_members(conn, q) if q else get_all_members(conn)
render_template('members/list.html', members=members, q=q)

# members/detail.html expects:
render_template('members/detail.html', member=member)

# members/form.html expects:
render_template('members/form.html',
    member=member,  # None for new, Row for edit
    plans=get_active_plans(conn)
)

# plans/list.html expects:
render_template('plans/list.html', plans=get_all_plans(conn))

# plans/form.html expects:
render_template('plans/form.html', plan=plan)  # None for new, Row for edit

# desks/list.html expects:
render_template('desks/list.html', desks=get_all_desks(conn))

# desks/form.html expects:
render_template('desks/form.html', desk=desk)  # None for new, Row for edit

# rooms/list.html expects:
render_template('rooms/list.html', rooms=get_all_rooms(conn))

# rooms/detail.html expects:
render_template('rooms/detail.html', room=room)

# rooms/form.html expects:
render_template('rooms/form.html', room=room)  # None for new, Row for edit

# desk_bookings/list.html expects:
render_template('desk_bookings/list.html', bookings=get_all_desk_bookings(conn))

# desk_bookings/detail.html expects:
render_template('desk_bookings/detail.html', booking=booking)

# desk_bookings/form.html expects:
render_template('desk_bookings/form.html',
    desks=get_active_desks(conn),
    members=get_all_members(conn)
)

# room_bookings/list.html expects:
render_template('room_bookings/list.html', bookings=get_all_room_bookings(conn))

# room_bookings/detail.html expects:
render_template('room_bookings/detail.html', booking=booking)

# room_bookings/form.html expects:
render_template('room_bookings/form.html',
    rooms=get_active_rooms(conn),
    members=get_all_members(conn),
    slot_starts=VALID_SLOT_STARTS
)

# billing/list.html expects:
render_template('billing/list.html', invoices=get_all_invoices(conn))

# billing/detail.html expects:
render_template('billing/detail.html',
    invoice=invoice,
    payments=get_payments_by_invoice(conn, invoice_id),
    total_paid=get_total_paid_for_invoice(conn, invoice_id)
)

# billing/form.html expects:
render_template('billing/form.html',
    invoice=invoice,  # None for new, Row for edit
    members=get_all_members(conn)
)

# payments/list.html expects:
render_template('payments/list.html', payments=get_all_payments(conn))

# payments/form.html expects:
render_template('payments/form.html',
    invoices=get_invoices_by_status(conn, 'pending')
)

# amenities/list.html expects:
render_template('amenities/list.html', amenities=get_all_amenities(conn))

# amenities/form.html expects:
render_template('amenities/form.html', amenity=amenity)  # None for new, Row for edit
```

## CSRF in Templates

Every POST form MUST include:

```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <!-- form fields -->
</form>
```

## Form Field Names (per route)

All form field `name` attributes must match exactly what `request.form.get()` uses.

| Route | Form Fields |
|-------|-------------|
| `POST /login` | `password` |
| `POST /members/new` | `name`, `email`, `phone`, `company`, `membership_plan_id`, `notes` |
| `POST /members/<id>/edit` | `name`, `email`, `phone`, `company`, `membership_plan_id`, `status`, `notes` |
| `POST /plans/new` | `name`, `price`, `billing_cycle`, `description` |
| `POST /plans/<id>/edit` | `name`, `price`, `billing_cycle`, `description`, `is_active` |
| `POST /desks/new` | `name`, `location` |
| `POST /desks/<id>/edit` | `name`, `location`, `is_active` |
| `POST /rooms/new` | `name`, `capacity`, `hourly_rate`, `location` |
| `POST /rooms/<id>/edit` | `name`, `capacity`, `hourly_rate`, `location`, `is_active` |
| `POST /desk-bookings/new` | `desk_id`, `member_id`, `booking_date`, `block` |
| `POST /room-bookings/new` | `room_id`, `member_id`, `booking_date`, `slot_start`, `purpose` |
| `POST /billing/new` | `member_id`, `amount`, `description`, `due_date` |
| `POST /billing/<id>/edit` | `amount`, `description`, `due_date`, `status` |
| `POST /payments/new` | `invoice_id`, `amount`, `payment_date`, `payment_method`, `reference_number`, `notes` |
| `POST /amenities/new` | `name`, `description` |
| `POST /amenities/<id>/edit` | `name`, `description`, `is_available` |

**Money fields:** Form has `name="price"`, `name="amount"`, `name="hourly_rate"`.
Route parses with: `price_cents = round(float(request.form.get('price', '0')) * 100)`.
Include NaN/Inf guard:
```python
raw = request.form.get('price', '0').strip()
try:
    val = float(raw)
except ValueError:
    flash('Invalid price.', 'error')
    return redirect(request.url)
if not math.isfinite(val) or val < 0 or val > 999999.99:
    flash('Price out of range.', 'error')
    return redirect(request.url)
price_cents = round(val * 100)
```

## Export Names Table

| Name | Type | Defined By | Used By |
|------|------|------------|---------|
| `create_member` | model function | `app/models/member.py` | `member_routes` agent |
| `get_member` | model function | `app/models/member.py` | `member_routes` agent |
| `get_all_members` | model function | `app/models/member.py` | `member_routes`, `desk_booking_routes`, `room_booking_routes`, `billing_routes`, `dashboard_routes` |
| `update_member` | model function | `app/models/member.py` | `member_routes` agent |
| `delete_member` | model function | `app/models/member.py` | `member_routes` agent |
| `count_active_members` | model function | `app/models/member.py` | `dashboard_routes` agent |
| `search_members` | model function | `app/models/member.py` | `member_routes` agent |
| `create_plan` | model function | `app/models/plan.py` | `plan_routes` agent |
| `get_plan` | model function | `app/models/plan.py` | `plan_routes` agent |
| `get_all_plans` | model function | `app/models/plan.py` | `plan_routes` agent |
| `get_active_plans` | model function | `app/models/plan.py` | `member_routes` agent (dropdown), `plan_routes` agent |
| `update_plan` | model function | `app/models/plan.py` | `plan_routes` agent |
| `delete_plan` | model function | `app/models/plan.py` | `plan_routes` agent |
| `create_desk` | model function | `app/models/desk.py` | `desk_routes` agent |
| `get_desk` | model function | `app/models/desk.py` | `desk_routes` agent |
| `get_all_desks` | model function | `app/models/desk.py` | `desk_routes` agent |
| `get_active_desks` | model function | `app/models/desk.py` | `desk_booking_routes` agent (dropdown) |
| `update_desk` | model function | `app/models/desk.py` | `desk_routes` agent |
| `delete_desk` | model function | `app/models/desk.py` | `desk_routes` agent |
| `create_room` | model function | `app/models/room.py` | `room_routes` agent |
| `get_room` | model function | `app/models/room.py` | `room_routes` agent |
| `get_all_rooms` | model function | `app/models/room.py` | `room_routes` agent |
| `get_active_rooms` | model function | `app/models/room.py` | `room_booking_routes` agent (dropdown) |
| `update_room` | model function | `app/models/room.py` | `room_routes` agent |
| `delete_room` | model function | `app/models/room.py` | `room_routes` agent |
| `create_desk_booking` | model function | `app/models/desk_booking.py` | `desk_booking_routes` agent |
| `get_desk_booking` | model function | `app/models/desk_booking.py` | `desk_booking_routes` agent |
| `get_all_desk_bookings` | model function | `app/models/desk_booking.py` | `desk_booking_routes` agent |
| `get_desk_bookings_by_date` | model function | `app/models/desk_booking.py` | `dashboard_routes` agent |
| `get_desk_bookings_by_member` | model function | `app/models/desk_booking.py` | `desk_booking_routes` agent |
| `cancel_desk_booking` | model function | `app/models/desk_booking.py` | `desk_booking_routes` agent |
| `count_desk_bookings_today` | model function | `app/models/desk_booking.py` | `dashboard_routes` agent |
| `create_room_booking` | model function | `app/models/room_booking.py` | `room_booking_routes` agent |
| `get_room_booking` | model function | `app/models/room_booking.py` | `room_booking_routes` agent |
| `get_all_room_bookings` | model function | `app/models/room_booking.py` | `room_booking_routes` agent |
| `get_room_bookings_by_date` | model function | `app/models/room_booking.py` | `dashboard_routes` agent |
| `get_room_bookings_by_member` | model function | `app/models/room_booking.py` | `room_booking_routes` agent |
| `get_available_slots` | model function | `app/models/room_booking.py` | `room_booking_routes` agent |
| `cancel_room_booking` | model function | `app/models/room_booking.py` | `room_booking_routes` agent |
| `count_room_bookings_today` | model function | `app/models/room_booking.py` | `dashboard_routes` agent |
| `VALID_SLOT_STARTS` | constant | `app/models/room_booking.py` | `room_booking_routes` agent |
| `create_invoice` | model function | `app/models/invoice.py` | `billing_routes` agent |
| `get_invoice` | model function | `app/models/invoice.py` | `billing_routes` agent |
| `get_all_invoices` | model function | `app/models/invoice.py` | `billing_routes` agent |
| `get_invoices_by_member` | model function | `app/models/invoice.py` | `billing_routes` agent |
| `get_invoices_by_status` | model function | `app/models/invoice.py` | `payment_routes` agent (pending dropdown) |
| `update_invoice` | model function | `app/models/invoice.py` | `billing_routes` agent |
| `delete_invoice` | model function | `app/models/invoice.py` | `billing_routes` agent |
| `get_total_revenue_this_month` | model function | `app/models/payment.py` | `dashboard_routes` agent |
| `get_pending_invoice_count` | model function | `app/models/invoice.py` | `dashboard_routes` agent |
| `create_payment` | model function | `app/models/payment.py` | `payment_routes` agent |
| `get_payment` | model function | `app/models/payment.py` | `payment_routes` agent |
| `get_all_payments` | model function | `app/models/payment.py` | `payment_routes` agent |
| `get_payments_by_invoice` | model function | `app/models/payment.py` | `billing_routes` agent (detail page) |
| `delete_payment` | model function | `app/models/payment.py` | `payment_routes` agent |
| `get_total_paid_for_invoice` | model function | `app/models/payment.py` | `billing_routes` agent (detail page) |
| `create_amenity` | model function | `app/models/amenity.py` | `amenity_routes` agent |
| `get_amenity` | model function | `app/models/amenity.py` | `amenity_routes` agent |
| `get_all_amenities` | model function | `app/models/amenity.py` | `amenity_routes` agent |
| `update_amenity` | model function | `app/models/amenity.py` | `amenity_routes` agent |
| `delete_amenity` | model function | `app/models/amenity.py` | `amenity_routes` agent |
| `count_amenities` | model function | `app/models/amenity.py` | `dashboard_routes` agent |
| `get_db` | function | `app/db.py` | ALL route agents |
| `login_required` | decorator | `app/auth.py` | ALL route agents (except auth) |
| `check_password` | function | `app/auth.py` | `auth` agent |
| `auth.login_page` | endpoint | `app/blueprints/auth/routes.py` | `layout` agent (login redirect) |
| `auth.login` | endpoint | `app/blueprints/auth/routes.py` | `auth` agent (form action) |
| `auth.logout` | endpoint | `app/blueprints/auth/routes.py` | `layout` agent (navbar) |
| `dashboard.index` | endpoint | `app/blueprints/dashboard/routes.py` | `layout` agent (navbar), `auth` agent (post-login redirect) |
| `dashboard.health` | endpoint | `app/blueprints/dashboard/routes.py` | none (external monitoring) |
| `members.list_members` | endpoint | `app/blueprints/members/routes.py` | `layout` agent (navbar) |
| `members.detail` | endpoint | `app/blueprints/members/routes.py` | `member_routes` agent (post-create redirect) |
| `plans.list_plans` | endpoint | `app/blueprints/plans/routes.py` | `layout` agent (navbar) |
| `desks.list_desks` | endpoint | `app/blueprints/desks/routes.py` | `layout` agent (navbar) |
| `rooms.list_rooms` | endpoint | `app/blueprints/rooms/routes.py` | `layout` agent (navbar) |
| `rooms.detail` | endpoint | `app/blueprints/rooms/routes.py` | `room_routes` agent |
| `desk_bookings.list_bookings` | endpoint | `app/blueprints/desk_bookings/routes.py` | `layout` agent (navbar) |
| `desk_bookings.detail` | endpoint | `app/blueprints/desk_bookings/routes.py` | `desk_booking_routes` agent |
| `desk_bookings.new_booking` | endpoint | `app/blueprints/desk_bookings/routes.py` | `desk_booking_routes` agent |
| `room_bookings.list_bookings` | endpoint | `app/blueprints/room_bookings/routes.py` | `layout` agent (navbar) |
| `room_bookings.detail` | endpoint | `app/blueprints/room_bookings/routes.py` | `room_booking_routes` agent |
| `room_bookings.new_booking` | endpoint | `app/blueprints/room_bookings/routes.py` | `room_booking_routes` agent |
| `billing.list_invoices` | endpoint | `app/blueprints/billing/routes.py` | `layout` agent (navbar) |
| `billing.detail` | endpoint | `app/blueprints/billing/routes.py` | `billing_routes` agent |
| `payments.list_payments` | endpoint | `app/blueprints/payments/routes.py` | `layout` agent (navbar) |
| `amenities.list_amenities` | endpoint | `app/blueprints/amenities/routes.py` | `layout` agent (navbar) |
| `auth` | blueprint name | `app/blueprints/auth/routes.py` | `core` agent (registration) |
| `dashboard` | blueprint name | `app/blueprints/dashboard/routes.py` | `core` agent |
| `members` | blueprint name | `app/blueprints/members/routes.py` | `core` agent |
| `plans` | blueprint name | `app/blueprints/plans/routes.py` | `core` agent |
| `desks` | blueprint name | `app/blueprints/desks/routes.py` | `core` agent |
| `rooms` | blueprint name | `app/blueprints/rooms/routes.py` | `core` agent |
| `desk_bookings` | blueprint name | `app/blueprints/desk_bookings/routes.py` | `core` agent |
| `room_bookings` | blueprint name | `app/blueprints/room_bookings/routes.py` | `core` agent |
| `billing` | blueprint name | `app/blueprints/billing/routes.py` | `core` agent |
| `payments` | blueprint name | `app/blueprints/payments/routes.py` | `core` agent |
| `amenities` | blueprint name | `app/blueprints/amenities/routes.py` | `core` agent |

## Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `app/db.py` | ALL route files | `from app.db import get_db` |
| `app/auth.py` | ALL route files (except auth) | `from app.auth import login_required` |
| `app/auth.py` | `app/blueprints/auth/routes.py` | `from app.auth import check_password` |
| `app/models/member.py` | `app/blueprints/members/routes.py` | `from app.models.member import create_member, get_member, get_all_members, update_member, delete_member, search_members` |
| `app/models/member.py` | `app/blueprints/desk_bookings/routes.py` | `from app.models.member import get_all_members` |
| `app/models/member.py` | `app/blueprints/room_bookings/routes.py` | `from app.models.member import get_all_members` |
| `app/models/member.py` | `app/blueprints/billing/routes.py` | `from app.models.member import get_all_members` |
| `app/models/member.py` | `app/blueprints/dashboard/routes.py` | `from app.models.member import count_active_members` |
| `app/models/plan.py` | `app/blueprints/plans/routes.py` | `from app.models.plan import create_plan, get_plan, get_all_plans, get_active_plans, update_plan, delete_plan` |
| `app/models/plan.py` | `app/blueprints/members/routes.py` | `from app.models.plan import get_active_plans` |
| `app/models/desk.py` | `app/blueprints/desks/routes.py` | `from app.models.desk import create_desk, get_desk, get_all_desks, update_desk, delete_desk` |
| `app/models/desk.py` | `app/blueprints/desk_bookings/routes.py` | `from app.models.desk import get_active_desks` |
| `app/models/room.py` | `app/blueprints/rooms/routes.py` | `from app.models.room import create_room, get_room, get_all_rooms, update_room, delete_room` |
| `app/models/room.py` | `app/blueprints/room_bookings/routes.py` | `from app.models.room import get_active_rooms` |
| `app/models/desk_booking.py` | `app/blueprints/desk_bookings/routes.py` | `from app.models.desk_booking import create_desk_booking, get_desk_booking, get_all_desk_bookings, get_desk_bookings_by_member, cancel_desk_booking` |
| `app/models/desk_booking.py` | `app/blueprints/dashboard/routes.py` | `from app.models.desk_booking import get_desk_bookings_by_date, count_desk_bookings_today` |
| `app/models/room_booking.py` | `app/blueprints/room_bookings/routes.py` | `from app.models.room_booking import create_room_booking, get_room_booking, get_all_room_bookings, get_room_bookings_by_member, get_available_slots, cancel_room_booking, VALID_SLOT_STARTS` |
| `app/models/room_booking.py` | `app/blueprints/dashboard/routes.py` | `from app.models.room_booking import get_room_bookings_by_date, count_room_bookings_today` |
| `app/models/invoice.py` | `app/blueprints/billing/routes.py` | `from app.models.invoice import create_invoice, get_invoice, get_all_invoices, get_invoices_by_member, update_invoice, delete_invoice` |
| `app/models/invoice.py` | `app/blueprints/payments/routes.py` | `from app.models.invoice import get_invoices_by_status` |
| `app/models/invoice.py` | `app/blueprints/dashboard/routes.py` | `from app.models.invoice import get_pending_invoice_count` |
| `app/models/payment.py` | `app/blueprints/payments/routes.py` | `from app.models.payment import create_payment, get_payment, get_all_payments, delete_payment` |
| `app/models/payment.py` | `app/blueprints/billing/routes.py` | `from app.models.payment import get_payments_by_invoice, get_total_paid_for_invoice` |
| `app/models/payment.py` | `app/blueprints/dashboard/routes.py` | `from app.models.payment import get_total_revenue_this_month` |
| `app/models/amenity.py` | `app/blueprints/amenities/routes.py` | `from app.models.amenity import create_amenity, get_amenity, get_all_amenities, update_amenity, delete_amenity` |
| `app/models/amenity.py` | `app/blueprints/dashboard/routes.py` | `from app.models.amenity import count_amenities` |

## Input Validation Prescriptions

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| `POST /login` | `password` (form) | Required, non-empty | Flash "Invalid password.", redirect to login |
| `POST /members/new` | `name` (form) | Strip, 1-100 chars, required | Flash "Name is required.", redirect back |
| `POST /members/new` | `email` (form) | Strip, 1-200 chars, required; catch `sqlite3.IntegrityError` for UNIQUE | Flash "Email is required." / "A member with this email already exists.", redirect back |
| `POST /members/new` | `membership_plan_id` (form) | Optional; if provided, must be valid int | Treat empty as None |
| `POST /members/<id>/edit` | `email` (form) | Catch `sqlite3.IntegrityError` for UNIQUE on update | Flash "A member with this email already exists.", redirect back |
| `POST /members/<id>/edit` | `status` (form) | Must be in ('active', 'frozen', 'cancelled') | Flash "Invalid status.", redirect back |
| `POST /members/<id>/delete` | `member_id` (URL) | Must exist in DB; catch `sqlite3.IntegrityError` | `abort(404)` if not found; Flash "Cannot delete: member has bookings or invoices." if IntegrityError |
| `POST /plans/new` | `name` (form) | Strip, 1-100 chars, required, unique | Flash "Name is required." / catch IntegrityError for duplicate |
| `POST /plans/new` | `price` (form) | Float, finite, 0-999999.99 | Flash "Invalid price.", redirect back |
| `POST /plans/new` | `billing_cycle` (form) | Must be in ('monthly', 'quarterly', 'annual') | Flash "Invalid billing cycle.", redirect back |
| `POST /plans/<id>/edit` | `is_active` (form) | Checkbox: present=1, absent=0 | Default to 0 |
| `POST /plans/<id>/delete` | `plan_id` (URL) | Must exist in DB | `abort(404)` |
| `POST /desks/new` | `name` (form) | Strip, 1-100 chars, required; catch `sqlite3.IntegrityError` for UNIQUE | Flash "Name is required." / "A desk with this name already exists.", redirect back |
| `POST /desks/<id>/edit` | `is_active` (form) | Checkbox: present=1, absent=0 | Default to 0 |
| `POST /desks/<id>/delete` | `desk_id` (URL) | Must exist; catch IntegrityError | Flash "Cannot delete: desk has bookings." |
| `POST /rooms/new` | `name` (form) | Strip, 1-100 chars, required; catch `sqlite3.IntegrityError` for UNIQUE | Flash "Name is required." / "A room with this name already exists.", redirect back |
| `POST /rooms/new` | `capacity` (form) | Int, 1-999, required | Flash "Invalid capacity.", redirect back |
| `POST /rooms/new` | `hourly_rate` (form) | Float, finite, 0-999999.99 | Flash "Invalid rate.", redirect back |
| `POST /rooms/<id>/edit` | `is_active` (form) | Checkbox: present=1, absent=0 | Default to 0 |
| `POST /rooms/<id>/delete` | `room_id` (URL) | Must exist; catch IntegrityError | Flash "Cannot delete: room has bookings." |
| `POST /desk-bookings/new` | `desk_id` (form) | Required, valid int, desk must exist and be active | Flash "Invalid desk.", redirect back |
| `POST /desk-bookings/new` | `member_id` (form) | Required, valid int, member must exist | Flash "Invalid member.", redirect back |
| `POST /desk-bookings/new` | `booking_date` (form) | Required, valid ISO date (YYYY-MM-DD) | Flash "Invalid date.", redirect back |
| `POST /desk-bookings/new` | `block` (form) | Must be in ('am', 'pm', 'full') | Flash "Invalid block.", redirect back |
| `POST /desk-bookings/<id>/cancel` | `booking_id` (URL) | Must exist in DB | `abort(404)` |
| `POST /room-bookings/new` | `room_id` (form) | Required, valid int, room must exist and be active | Flash "Invalid room.", redirect back |
| `POST /room-bookings/new` | `member_id` (form) | Required, valid int, member must exist | Flash "Invalid member.", redirect back |
| `POST /room-bookings/new` | `booking_date` (form) | Required, valid ISO date | Flash "Invalid date.", redirect back |
| `POST /room-bookings/new` | `slot_start` (form) | Must be in VALID_SLOT_STARTS | Flash "Invalid time slot.", redirect back |
| `POST /room-bookings/<id>/cancel` | `booking_id` (URL) | Must exist in DB | `abort(404)` |
| `POST /billing/new` | `member_id` (form) | Required, valid int, member must exist | Flash "Invalid member.", redirect back |
| `POST /billing/new` | `amount` (form) | Float, finite, >0, max 999999.99 | Flash "Invalid amount.", redirect back |
| `POST /billing/new` | `description` (form) | Strip, 1-500 chars, required | Flash "Description is required.", redirect back |
| `POST /billing/new` | `due_date` (form) | Required, valid ISO date | Flash "Invalid due date.", redirect back |
| `POST /billing/<id>/edit` | `status` (form) | Must be in ('pending', 'paid', 'overdue', 'cancelled') | Flash "Invalid status.", redirect back |
| `POST /billing/<id>/delete` | `invoice_id` (URL) | Must exist; catch IntegrityError | Flash "Cannot delete: invoice has payments." |
| `POST /payments/new` | `invoice_id` (form) | Required, valid int, invoice must exist | Flash "Invalid invoice.", redirect back |
| `POST /payments/new` | `amount` (form) | Float, finite, >0, max 999999.99 | Flash "Invalid amount.", redirect back |
| `POST /payments/new` | `payment_date` (form) | Required, valid ISO date | Flash "Invalid date.", redirect back |
| `POST /payments/new` | `payment_method` (form) | Must be in ('cash', 'card', 'bank_transfer', 'other') | Flash "Invalid payment method.", redirect back |
| `POST /payments/<id>/delete` | `payment_id` (URL) | Must exist in DB | `abort(404)` |
| `POST /amenities/new` | `name` (form) | Strip, 1-100 chars, required; catch `sqlite3.IntegrityError` for UNIQUE | Flash "Name is required." / "An amenity with this name already exists.", redirect back |
| `POST /amenities/<id>/edit` | `is_available` (form) | Checkbox: present=1, absent=0 | Default to 0 |
| `POST /amenities/<id>/delete` | `amenity_id` (URL) | Must exist in DB | `abort(404)` |

## Coordinated Behaviors

| # | Surface | Rule | Owner |
|---|---------|------|-------|
| 1 | Blueprint registration | All blueprints registered in `create_app()` with exact `url_prefix` values from Route Table | `core` agent |
| 2 | Navbar links | `base.html` includes links to ALL list endpoints. Groups: Dashboard, Members, Plans, Desks, Rooms, Desk Bookings, Room Bookings, Billing, Payments, Amenities | `layout` agent |
| 3 | Flash message display | `base.html` renders `get_flashed_messages(with_categories=true)`. Categories: 'success' (green), 'error' (red), 'info' (blue) | `layout` agent |
| 4 | Flash message authoring | Success: `flash('...created/updated/deleted/cancelled successfully.', 'success')`. Error: `flash('...', 'error')`. ALL agents use EXACTLY these categories | ALL route agents |
| 5 | Login required | Every route handler (except auth + health) decorated with `@login_required` AFTER `@bp.route` | ALL route agents |
| 6 | Delete confirmation | All delete/cancel buttons use a form with `onclick="return confirm('Are you sure?')"` | ALL route agents |
| 7 | 404 pattern | `item = get_item(conn, item_id)` then `if item is None: abort(404)` | ALL route agents |
| 8 | IntegrityError handling | Delete routes with RESTRICT FKs catch `sqlite3.IntegrityError` specifically (NOT bare `except Exception`) and flash an entity-specific message as defined in Input Validation Prescriptions (e.g., "Cannot delete: member has bookings or invoices.", "Cannot delete: desk has bookings."). Routes where all child FKs are SET NULL do NOT need IntegrityError handling (delete_plan). | Route agents with RESTRICT FK children |
| 9 | No CSP header | Do NOT add Content-Security-Policy header. Bootstrap 5 loads from CDN. CSP would block it (FC38). | `core` agent |
| 10 | SQLite PRAGMAs | `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000` -- set in `get_db()`. No other connection paths exist. (FC40) | `core` agent |
| 11 | Money display | All monetary values stored as INTEGER cents. Display: `{{ value\|dollars }}`. Form prefill: `{{ value\|dollars_raw }}`. Parse: `round(float(val) * 100)` with guards. | ALL agents with money |
| 12 | Date display | All dates displayed with `{{ value\|date_format }}`, times with `{{ value\|time_format }}` | ALL route agents |
| 13 | Form field naming | Form field `name` attributes MUST match the Form Field Names table exactly. | ALL route agents |
| 14 | Logout form | Navbar logout is a POST form with CSRF token, not a GET link (FC from RestaurantOps) | `layout` agent |
| 15 | Timestamps | Use SQL `datetime('now')` and `date('now')` for all timestamps. Do NOT use Python `datetime.now()`. | ALL model agents |
| 16 | Row factory | Do NOT set `row_factory` in model functions -- `get_db()` handles it. (FC2 from GymFlow) | ALL model agents |
| 17 | Booking status colors | `confirmed` = green badge, `cancelled` = red badge (in templates). Consistent across desk and room bookings. | `desk_booking_routes`, `room_booking_routes` agents |
| 18 | Invoice status colors | `pending` = yellow badge, `paid` = green badge, `overdue` = red badge, `cancelled` = gray badge | `billing_routes` agent |
| 19 | Post-update redirect | After successful update, redirect to the detail page if one exists (members, rooms, invoices), otherwise redirect to the list page (plans, desks, amenities) | ALL route agents |
| 20 | Bookings immutable | Bookings cannot be edited after creation. To change a booking, cancel it and create a new one. No update routes exist for bookings by design. | `desk_booking_routes`, `room_booking_routes` agents |
| 21 | Math import for money | Route files that parse money (plans, rooms, billing, payments) MUST include `import math` for `math.isfinite()` guard | `plan_routes`, `room_routes`, `billing_routes`, `payment_routes` agents |
| 22 | Dashboard today | Dashboard route computes `today = date.today().isoformat()` with `from datetime import date`. ALL date comparisons use ISO format strings. | `dashboard_routes` agent |
| 23 | Duplicate name/email IntegrityError | Routes for entities with UNIQUE columns (members:email, desks:name, rooms:name, amenities:name, plans:name) MUST catch `sqlite3.IntegrityError` on create AND edit, and flash "A [entity] with this [field] already exists." | ALL route agents with UNIQUE columns |
| 24 | Decommission pattern | To decommission a desk or room, set `is_active=0` instead of deleting. Deletion is blocked by RESTRICT FK if any bookings exist (even cancelled ones). | `desk_routes`, `room_routes` agents |
| 25 | Date validation pattern | All date inputs validated with `datetime.strptime(val, '%Y-%m-%d')` in a try/except ValueError. This catches invalid dates like '2026-02-30'. Import: `from datetime import datetime`. | ALL route agents with date inputs |

## Transaction Contracts

| Function | SQL Operations | Commits | Error Handling |
|----------|---------------|---------|----------------|
| `create_member` | INSERT INTO members | commits internally (`conn.commit()`) | none needed |
| `update_member` | UPDATE members | commits internally | none needed |
| `delete_member` | DELETE FROM members | commits internally | none needed (IntegrityError caught by route) |
| `create_plan` | INSERT INTO membership_plans | commits internally | none needed |
| `update_plan` | UPDATE membership_plans | commits internally | none needed |
| `delete_plan` | DELETE FROM membership_plans | commits internally | none needed |
| `create_desk` | INSERT INTO desks | commits internally | none needed |
| `update_desk` | UPDATE desks | commits internally | none needed |
| `delete_desk` | DELETE FROM desks | commits internally | none needed (IntegrityError caught by route) |
| `create_room` | INSERT INTO meeting_rooms | commits internally | none needed |
| `update_room` | UPDATE meeting_rooms | commits internally | none needed |
| `delete_room` | DELETE FROM meeting_rooms | commits internally | none needed (IntegrityError caught by route) |
| `create_desk_booking` | BEGIN IMMEDIATE + SELECT + INSERT + COMMIT | requires BEGIN IMMEDIATE (atomic conflict check) | **try/except/ROLLBACK** |
| `cancel_desk_booking` | UPDATE desk_bookings SET status='cancelled' | commits internally | none needed |
| `create_room_booking` | BEGIN IMMEDIATE + SELECT + INSERT + COMMIT | requires BEGIN IMMEDIATE (atomic conflict check) | **try/except/ROLLBACK** |
| `cancel_room_booking` | UPDATE room_bookings SET status='cancelled' | commits internally | none needed |
| `create_invoice` | INSERT INTO invoices | commits internally | none needed |
| `update_invoice` | UPDATE invoices | commits internally | none needed |
| `delete_invoice` | DELETE FROM invoices | commits internally | none needed (IntegrityError caught by route) |
| `create_payment` | INSERT INTO payments | commits internally | none needed |
| `delete_payment` | DELETE FROM payments | commits internally | none needed |
| `create_amenity` | INSERT INTO amenities | commits internally | none needed |
| `update_amenity` | UPDATE amenities | commits internally | none needed |
| `delete_amenity` | DELETE FROM amenities | commits internally | none needed |

**All read-only functions (get_*, count_*, search_*, get_available_*) do NOT commit.**

**FC29 compliance:** `create_desk_booking` and `create_room_booking` both use the
6-step pattern: (1) BEGIN IMMEDIATE, (2) SELECT conflict check, (3) if conflict
ROLLBACK + return None, (4) INSERT, (5) COMMIT, (6) return ID. Both are wrapped
in try/except with ROLLBACK on any exception to prevent write lock leaks.

## Authorization Matrix

All routes are admin-only (single-user system). No role distinctions or ownership
checks needed.

| Route Pattern | Mode | Notes |
|---------------|------|-------|
| `GET /login`, `POST /login` | public | Only unauthenticated routes |
| `GET /health` | public | Health check, no auth |
| `POST /logout` | login-required | Must be logged in to log out |
| ALL other routes | login-required | `@login_required` decorator |

No ownership checks needed -- single admin manages all resources.

## File Assignment Boundaries

### core agent
| File | Purpose |
|------|---------|
| `coworkflow/app/__init__.py` | App factory with blueprint registration |
| `coworkflow/app/db.py` | Database connection, init_db, close_db |
| `coworkflow/app/auth.py` | login_required decorator, check_password |
| `coworkflow/app/filters.py` | Jinja template filters (dollars, dollars_raw, date_format, time_format) |
| `coworkflow/app/models/__init__.py` | Barrel re-exports of ALL model functions |
| `coworkflow/schema.sql` | Complete database schema |
| `coworkflow/requirements.txt` | Python dependencies |
| `coworkflow/.gitignore` | Git ignore patterns (include `*.db`, `__pycache__/`, `.venv/`, `test_smoke.py`) |

### layout agent
| File | Purpose |
|------|---------|
| `coworkflow/app/templates/base.html` | Base template with navbar, flash messages, Bootstrap 5 CDN |
| `coworkflow/app/static/style.css` | Custom styles |

### auth agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/auth/__init__.py` | Empty init |
| `coworkflow/app/blueprints/auth/routes.py` | Login/logout routes |
| `coworkflow/app/templates/auth/login.html` | Login form |

### member_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/member.py` | Member CRUD functions |

### plan_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/plan.py` | Membership plan CRUD functions |

### desk_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/desk.py` | Desk CRUD functions |

### room_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/room.py` | Meeting room CRUD functions |

### desk_booking_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/desk_booking.py` | Desk booking functions with BEGIN IMMEDIATE |

### room_booking_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/room_booking.py` | Room booking functions with BEGIN IMMEDIATE |

### invoice_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/invoice.py` | Invoice CRUD + revenue/pending queries |

### payment_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/payment.py` | Payment CRUD + total_paid query |

### amenity_models agent
| File | Purpose |
|------|---------|
| `coworkflow/app/models/amenity.py` | Amenity CRUD + count |

### member_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/members/__init__.py` | Empty init |
| `coworkflow/app/blueprints/members/routes.py` | Member routes |
| `coworkflow/app/templates/members/list.html` | Member list page |
| `coworkflow/app/templates/members/detail.html` | Member detail |
| `coworkflow/app/templates/members/form.html` | New/edit member form |

### plan_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/plans/__init__.py` | Empty init |
| `coworkflow/app/blueprints/plans/routes.py` | Membership plan routes |
| `coworkflow/app/templates/plans/list.html` | Plans list with prices |
| `coworkflow/app/templates/plans/form.html` | New/edit plan form |

### desk_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/desks/__init__.py` | Empty init |
| `coworkflow/app/blueprints/desks/routes.py` | Desk routes |
| `coworkflow/app/templates/desks/list.html` | Desk list |
| `coworkflow/app/templates/desks/form.html` | New/edit desk form |

### room_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/rooms/__init__.py` | Empty init |
| `coworkflow/app/blueprints/rooms/routes.py` | Meeting room routes |
| `coworkflow/app/templates/rooms/list.html` | Room list |
| `coworkflow/app/templates/rooms/detail.html` | Room detail |
| `coworkflow/app/templates/rooms/form.html` | New/edit room form |

### desk_booking_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/desk_bookings/__init__.py` | Empty init |
| `coworkflow/app/blueprints/desk_bookings/routes.py` | Desk booking routes |
| `coworkflow/app/templates/desk_bookings/list.html` | Desk bookings list |
| `coworkflow/app/templates/desk_bookings/detail.html` | Desk booking detail |
| `coworkflow/app/templates/desk_bookings/form.html` | New desk booking form |

### room_booking_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/room_bookings/__init__.py` | Empty init |
| `coworkflow/app/blueprints/room_bookings/routes.py` | Room booking routes |
| `coworkflow/app/templates/room_bookings/list.html` | Room bookings list |
| `coworkflow/app/templates/room_bookings/detail.html` | Room booking detail |
| `coworkflow/app/templates/room_bookings/form.html` | New room booking form |

### billing_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/billing/__init__.py` | Empty init |
| `coworkflow/app/blueprints/billing/routes.py` | Invoice routes |
| `coworkflow/app/templates/billing/list.html` | Invoice list |
| `coworkflow/app/templates/billing/detail.html` | Invoice detail with payments |
| `coworkflow/app/templates/billing/form.html` | New/edit invoice form |

### payment_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/payments/__init__.py` | Empty init |
| `coworkflow/app/blueprints/payments/routes.py` | Payment routes |
| `coworkflow/app/templates/payments/list.html` | All payments list |
| `coworkflow/app/templates/payments/form.html` | New payment form |

### amenity_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/amenities/__init__.py` | Empty init |
| `coworkflow/app/blueprints/amenities/routes.py` | Amenity routes |
| `coworkflow/app/templates/amenities/list.html` | Amenities list |
| `coworkflow/app/templates/amenities/form.html` | New/edit amenity form |

### dashboard_routes agent
| File | Purpose |
|------|---------|
| `coworkflow/app/blueprints/dashboard/__init__.py` | Empty init |
| `coworkflow/app/blueprints/dashboard/routes.py` | Dashboard + health routes |
| `coworkflow/app/templates/dashboard/index.html` | Dashboard with stats and today's bookings |

## Swarm Agent Assignment

| # | Agent Name | Role | Files |
|---|-----------|------|-------|
| 1 | core | Infrastructure | `coworkflow/app/__init__.py`, `coworkflow/app/db.py`, `coworkflow/app/auth.py`, `coworkflow/app/filters.py`, `coworkflow/app/models/__init__.py`, `coworkflow/schema.sql`, `coworkflow/requirements.txt`, `coworkflow/.gitignore` |
| 2 | layout | Templates/CSS | `coworkflow/app/templates/base.html`, `coworkflow/app/static/style.css` |
| 3 | auth | Auth routes | `coworkflow/app/blueprints/auth/__init__.py`, `coworkflow/app/blueprints/auth/routes.py`, `coworkflow/app/templates/auth/login.html` |
| 4 | member_models | Models | `coworkflow/app/models/member.py` |
| 5 | plan_models | Models | `coworkflow/app/models/plan.py` |
| 6 | desk_models | Models | `coworkflow/app/models/desk.py` |
| 7 | room_models | Models | `coworkflow/app/models/room.py` |
| 8 | desk_booking_models | Models | `coworkflow/app/models/desk_booking.py` |
| 9 | room_booking_models | Models | `coworkflow/app/models/room_booking.py` |
| 10 | invoice_models | Models | `coworkflow/app/models/invoice.py` |
| 11 | payment_models | Models | `coworkflow/app/models/payment.py` |
| 12 | amenity_models | Models | `coworkflow/app/models/amenity.py` |
| 13 | member_routes | Routes/Templates | `coworkflow/app/blueprints/members/__init__.py`, `coworkflow/app/blueprints/members/routes.py`, `coworkflow/app/templates/members/list.html`, `coworkflow/app/templates/members/detail.html`, `coworkflow/app/templates/members/form.html` |
| 14 | plan_routes | Routes/Templates | `coworkflow/app/blueprints/plans/__init__.py`, `coworkflow/app/blueprints/plans/routes.py`, `coworkflow/app/templates/plans/list.html`, `coworkflow/app/templates/plans/form.html` |
| 15 | desk_routes | Routes/Templates | `coworkflow/app/blueprints/desks/__init__.py`, `coworkflow/app/blueprints/desks/routes.py`, `coworkflow/app/templates/desks/list.html`, `coworkflow/app/templates/desks/form.html` |
| 16 | room_routes | Routes/Templates | `coworkflow/app/blueprints/rooms/__init__.py`, `coworkflow/app/blueprints/rooms/routes.py`, `coworkflow/app/templates/rooms/list.html`, `coworkflow/app/templates/rooms/detail.html`, `coworkflow/app/templates/rooms/form.html` |
| 17 | desk_booking_routes | Routes/Templates | `coworkflow/app/blueprints/desk_bookings/__init__.py`, `coworkflow/app/blueprints/desk_bookings/routes.py`, `coworkflow/app/templates/desk_bookings/list.html`, `coworkflow/app/templates/desk_bookings/detail.html`, `coworkflow/app/templates/desk_bookings/form.html` |
| 18 | room_booking_routes | Routes/Templates | `coworkflow/app/blueprints/room_bookings/__init__.py`, `coworkflow/app/blueprints/room_bookings/routes.py`, `coworkflow/app/templates/room_bookings/list.html`, `coworkflow/app/templates/room_bookings/detail.html`, `coworkflow/app/templates/room_bookings/form.html` |
| 19 | billing_routes | Routes/Templates | `coworkflow/app/blueprints/billing/__init__.py`, `coworkflow/app/blueprints/billing/routes.py`, `coworkflow/app/templates/billing/list.html`, `coworkflow/app/templates/billing/detail.html`, `coworkflow/app/templates/billing/form.html` |
| 20 | payment_routes | Routes/Templates | `coworkflow/app/blueprints/payments/__init__.py`, `coworkflow/app/blueprints/payments/routes.py`, `coworkflow/app/templates/payments/list.html`, `coworkflow/app/templates/payments/form.html` |
| 21 | amenity_routes | Routes/Templates | `coworkflow/app/blueprints/amenities/__init__.py`, `coworkflow/app/blueprints/amenities/routes.py`, `coworkflow/app/templates/amenities/list.html`, `coworkflow/app/templates/amenities/form.html` |
| 22 | dashboard_routes | Routes/Templates | `coworkflow/app/blueprints/dashboard/__init__.py`, `coworkflow/app/blueprints/dashboard/routes.py`, `coworkflow/app/templates/dashboard/index.html` |

## Smoke Test File (FC8 Compliance)

Add `test_smoke.py` to `.gitignore` BEFORE writing it.

```python
"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
os.environ.setdefault("SECRET_KEY", "test-smoke-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-strong-pw-123")
os.environ.setdefault("FLASK_DEBUG", "1")

from app import create_app

app = create_app()
client = app.test_client()

r = client.get("/health")
assert r.status_code == 200, f"Health failed: {r.status_code}"
print("PASS: health")

r = client.get("/login")
assert r.status_code == 200, f"Login page failed: {r.status_code}"
print("PASS: login page")

r = client.post("/login", data={"password": "test-strong-pw-123"}, follow_redirects=False)
assert r.status_code == 302, f"Login failed: {r.status_code}"
print("PASS: login")

with client.session_transaction() as sess:
    sess['logged_in'] = True

endpoints = [
    ("/", 200), ("/members/", 200), ("/plans/", 200),
    ("/desks/", 200), ("/rooms/", 200),
    ("/desk-bookings/", 200), ("/room-bookings/", 200),
    ("/billing/", 200), ("/payments/", 200), ("/amenities/", 200),
    ("/members/new", 200), ("/plans/new", 200),
    ("/desks/new", 200), ("/rooms/new", 200),
    ("/desk-bookings/new", 200), ("/room-bookings/new", 200),
    ("/billing/new", 200), ("/payments/new", 200), ("/amenities/new", 200),
]

for path, expected in endpoints:
    r = client.get(path)
    assert r.status_code == expected, f"{path} failed: {r.status_code}"
    print(f"PASS: GET {path}")

print("ALL SMOKE TESTS PASSED")
```

## Acceptance Tests

### Happy Path
- WHEN admin visits /login THE SYSTEM SHALL display a login form
- WHEN admin submits correct password THE SYSTEM SHALL redirect to dashboard
- WHEN admin visits / (dashboard) THE SYSTEM SHALL display active member count, revenue, today's bookings, pending invoices, and amenity count
- WHEN admin creates a new member THE SYSTEM SHALL store the member and redirect to detail page
- WHEN admin creates a membership plan with price $49.99 THE SYSTEM SHALL store 4999 cents
- WHEN admin creates a desk THE SYSTEM SHALL store the desk and redirect to list
- WHEN admin creates a meeting room with hourly rate $50.00 THE SYSTEM SHALL store 5000 cents
- WHEN admin books desk A1 for 2026-06-01 AM block THE SYSTEM SHALL verify no conflict and create confirmed booking
- WHEN admin books Room 1 for 2026-06-01 slot 09:00 THE SYSTEM SHALL verify slot is free and create confirmed booking
- WHEN admin creates an invoice THE SYSTEM SHALL store amount in cents with due date
- WHEN admin records a payment THE SYSTEM SHALL store amount in cents linked to invoice
- WHEN admin creates an amenity THE SYSTEM SHALL store it and redirect to list
- WHEN admin cancels a desk booking THE SYSTEM SHALL set status to 'cancelled'
- WHEN admin cancels a room booking THE SYSTEM SHALL set status to 'cancelled'
- WHEN admin edits a membership plan price from $49.99 to $59.99 THE SYSTEM SHALL update to 5999 cents and prefill form with '59.99'

### Error Cases
- WHEN admin submits wrong password THE SYSTEM SHALL flash error and stay on login
- WHEN admin books desk A1 for 2026-06-01 AM and AM is already booked THE SYSTEM SHALL flash "Desk already booked for that block." and not create record
- WHEN admin books desk A1 for 2026-06-01 full-day and AM is already booked THE SYSTEM SHALL flash conflict and not create record
- WHEN admin books Room 1 for 2026-06-01 slot 09:00 and that slot is taken THE SYSTEM SHALL flash "Room slot already booked." and not create record
- WHEN admin tries to delete a member with bookings THE SYSTEM SHALL flash "Cannot delete" error
- WHEN admin tries to delete a desk with bookings THE SYSTEM SHALL flash "Cannot delete" error
- WHEN admin tries to delete a room with bookings THE SYSTEM SHALL flash "Cannot delete" error
- WHEN admin tries to delete an invoice with payments THE SYSTEM SHALL flash "Cannot delete" error
- WHEN admin submits a form with missing required fields THE SYSTEM SHALL flash specific error and not create record
- WHEN admin visits a non-existent resource ID THE SYSTEM SHALL return 404

### Verification Commands
```
cd coworkflow
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python test_smoke.py
```

## Feed-Forward

- **Hardest decision:** Per-slot model for room bookings (one row per 30-min slot)
  vs. time-range model. Chose per-slot because it maps cleanly to
  (room_id, booking_date, slot_start) uniqueness constraint and matches the
  brainstorm's explicit design. Trade-off: booking a 1-hour meeting requires
  2 form submissions, but the spec is simpler and the DB constraint is stronger.
- **Rejected alternatives:** Time-range model with overlap detection (more complex
  queries, no simple UNIQUE index), normalized desk booking slots (unnecessary
  when block conflict logic is simple), multi-slot batch creation (adds group_id
  complexity to spec).
- **Least confident:** Desk booking conflict logic for AM/PM/full overlap. The
  3-way check (am conflicts with am|full, pm with pm|full, full with any) has
  no UNIQUE constraint equivalent -- it relies entirely on BEGIN IMMEDIATE +
  application logic. A bug in the conflict query would allow double-booking.
  The room booking path has a partial UNIQUE index as safety net; desk bookings
  do not.

## Sources

- **Origin brainstorm:** docs/brainstorms/2026-05-21-coworking-space-manager-brainstorm.md
  Key decisions: 9 domains, hot desk AM/PM/full blocks, 30-min room slots,
  single-admin auth, integer cents, no amenity junction table.
- **Structural reference:** docs/plans/2026-05-21-gym-manager-plan.md (26-agent GymFlow)
- **Solution docs applied:** RestaurantOps (isolation_level=None), GymFlow
  (try/except/ROLLBACK), Personal Finance Tracker (3 money surfaces),
  Solopreneur (form field names), Flask ACID Test (get_db usage example),
  VenueConnect (IDOR patterns), Spec Completeness Checker (6 mandatory sections)
