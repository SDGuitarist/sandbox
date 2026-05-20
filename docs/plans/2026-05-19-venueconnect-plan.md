---
title: "feat: VenueConnect -- Three-Sided Venue Booking & Settlement Platform"
type: feat
status: active
date: 2026-05-19
origin: docs/brainstorms/2026-05-19-venueconnect-brainstorm.md
swarm: true
agents: 25
run_id: "049"
feed_forward:
  risk: "Calendar conflict detection TOCTOU and booking state machine cross-agent wiring are the two surfaces most likely to produce integration bugs"
  verify_first: true
---

# VenueConnect -- Shared Interface Spec

Three-sided venue booking and settlement platform for live music.
Venues list rooms/availability, musicians search and request bookings,
promoters create events. After shows, settlement sheets calculate payouts.

**Stack:** Flask + SQLite + Jinja2 + Bootstrap 5
**Agents:** 25 (vertical blueprint split)
**Origin:** [brainstorm](docs/brainstorms/2026-05-19-venueconnect-brainstorm.md)

---

## App Configuration

```python
# app/__init__.py (scaffold agent)
import os
from flask import Flask, g, redirect, url_for, session
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

SECRET_KEY_BLOCKLIST = ['dev-fallback', 'change-me', 'secret', '']

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    secret = os.environ.get('SECRET_KEY', 'dev-fallback')
    if secret in SECRET_KEY_BLOCKLIST and not app.debug:
        raise RuntimeError('Set a real SECRET_KEY in production')
    app.config['SECRET_KEY'] = secret
    app.config['DATABASE'] = os.path.join(app.instance_path, 'venueconnect.db')

    csrf.init_app(app)
    limiter.init_app(app)

    from app.db import close_db, init_db_command
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    from app.filters import register_filters
    register_filters(app)

    # Register all 18 blueprints (see Blueprint Registry below)
    _register_blueprints(app)

    # Security headers
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # CSRF error handler
    from flask_wtf.csrf import CSRFError
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import request, jsonify
        if request.is_json:
            return jsonify(error='CSRF token missing or invalid'), 400
        from flask import flash
        flash('Form expired. Please try again.', 'error')
        return redirect(request.referrer or url_for('main.index'))

    # Root route -- redirect by role
    @app.route('/')
    def index():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        role = session.get('role', 'musician')
        return redirect(url_for(f'dashboard_{role}.index'))

    @app.route('/health')
    def health():
        from flask import jsonify
        return jsonify(status='ok')

    return app
```

**requirements.txt:**
```
flask>=3.0
flask-wtf>=1.2
flask-limiter>=3.5
reportlab>=4.1
werkzeug>=3.0
email-validator>=2.0
```

---

## Blueprint Registry

Every blueprint is registered in `_register_blueprints(app)` in `app/__init__.py`.
Agents use ONLY their assigned blueprint name and url_prefix. Route decorator
paths are RELATIVE to the prefix (FC7 prevention).

| Blueprint Name | Variable | url_prefix | Agent |
|---------------|----------|------------|-------|
| main | (app routes) | / | scaffold (1) |
| auth | auth_bp | /auth | auth (2) |
| venues | venues_bp | /venues | venue-crud (4) |
| rooms | rooms_bp | /rooms | room-crud (5) |
| availability | availability_bp | /availability | availability (6) |
| booking_create | booking_create_bp | /bookings | booking-create (7) |
| booking_manage | booking_manage_bp | /manage | booking-manage (8) |
| events | events_bp | /events | promoter-events (10) |
| tickets | tickets_bp | /tickets | ticket-tiers (11) |
| settlements | settlements_bp | /settlements | settlement-views (13) |
| search | search_bp | /search | search (15) |
| notification_views | notification_views_bp | /notifications | notification-views (17) |
| analytics_venue | analytics_venue_bp | /analytics/venue | analytics-venue (18) |
| analytics_musician | analytics_musician_bp | /analytics/musician | analytics-musician (19) |
| analytics_promoter | analytics_promoter_bp | /analytics/promoter | analytics-promoter (20) |
| dashboard_venue | dashboard_venue_bp | /dashboard/venue | dashboard-venue (21) |
| dashboard_musician | dashboard_musician_bp | /dashboard/musician | dashboard-musician (22) |
| dashboard_promoter | dashboard_promoter_bp | /dashboard/promoter | dashboard-promoter (23) |

**Registration code** (in `_register_blueprints`):
```python
def _register_blueprints(app):
    from app.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    from app.venues.routes import venues_bp
    app.register_blueprint(venues_bp, url_prefix='/venues')
    from app.rooms.routes import rooms_bp
    app.register_blueprint(rooms_bp, url_prefix='/rooms')
    from app.availability.routes import availability_bp
    app.register_blueprint(availability_bp, url_prefix='/availability')
    from app.booking_create.routes import booking_create_bp
    app.register_blueprint(booking_create_bp, url_prefix='/bookings')
    from app.booking_manage.routes import booking_manage_bp
    app.register_blueprint(booking_manage_bp, url_prefix='/manage')
    from app.events.routes import events_bp
    app.register_blueprint(events_bp, url_prefix='/events')
    from app.tickets.routes import tickets_bp
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    from app.settlements.routes import settlements_bp
    app.register_blueprint(settlements_bp, url_prefix='/settlements')
    from app.search.routes import search_bp
    app.register_blueprint(search_bp, url_prefix='/search')
    from app.notification_views.routes import notification_views_bp
    app.register_blueprint(notification_views_bp, url_prefix='/notifications')
    from app.analytics_venue.routes import analytics_venue_bp
    app.register_blueprint(analytics_venue_bp, url_prefix='/analytics/venue')
    from app.analytics_musician.routes import analytics_musician_bp
    app.register_blueprint(analytics_musician_bp, url_prefix='/analytics/musician')
    from app.analytics_promoter.routes import analytics_promoter_bp
    app.register_blueprint(analytics_promoter_bp, url_prefix='/analytics/promoter')
    from app.dashboard_venue.routes import dashboard_venue_bp
    app.register_blueprint(dashboard_venue_bp, url_prefix='/dashboard/venue')
    from app.dashboard_musician.routes import dashboard_musician_bp
    app.register_blueprint(dashboard_musician_bp, url_prefix='/dashboard/musician')
    from app.dashboard_promoter.routes import dashboard_promoter_bp
    app.register_blueprint(dashboard_promoter_bp, url_prefix='/dashboard/promoter')
```

---

## Database Schema

```sql
-- app/schema.sql (models agent)

-- Users: single role per account (venue_manager, musician, promoter)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('venue_manager', 'musician', 'promoter')),
    display_name TEXT NOT NULL DEFAULT '',
    bio TEXT NOT NULL DEFAULT '',
    genre_tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Venues: owned by a venue_manager
CREATE TABLE IF NOT EXISTS venues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    capacity INTEGER NOT NULL DEFAULT 0,
    genre_tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_venues_user_id ON venues(user_id);

-- Rooms/stages within a venue
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    has_pa INTEGER NOT NULL DEFAULT 0,
    has_lighting INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_rooms_venue_id ON rooms(venue_id);

-- Weekly recurring availability windows for rooms
CREATE TABLE IF NOT EXISTS availability_windows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_availability_room_id ON availability_windows(room_id);

-- Bookings: a musician books a room for a specific date
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    musician_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    event_name TEXT NOT NULL DEFAULT '',
    event_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'requested' CHECK (state IN ('requested', 'confirmed', 'advanced', 'performed', 'settled', 'paid', 'rejected', 'cancelled')),
    deal_type TEXT NOT NULL DEFAULT 'door_split' CHECK (deal_type IN ('guarantee', 'door_split', 'hybrid')),
    guarantee_cents INTEGER NOT NULL DEFAULT 0,
    door_split_pct INTEGER NOT NULL DEFAULT 70,
    promoter_fee_pct INTEGER NOT NULL DEFAULT 0,
    tax_pct INTEGER NOT NULL DEFAULT 0,
    advance_cents INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bookings_room_id ON bookings(room_id);
CREATE INDEX IF NOT EXISTS idx_bookings_musician_user_id ON bookings(musician_user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_event_id ON bookings(event_id);
CREATE INDEX IF NOT EXISTS idx_bookings_state ON bookings(state);
CREATE INDEX IF NOT EXISTS idx_bookings_event_date ON bookings(event_date);

-- Booking state transition audit trail
CREATE TABLE IF NOT EXISTS booking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    actor_user_id INTEGER NOT NULL REFERENCES users(id),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_booking_history_booking_id ON booking_history(booking_id);

-- Events: created by promoters, group bookings across venues
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    promoter_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    event_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_promoter_user_id ON events(promoter_user_id);
CREATE INDEX IF NOT EXISTS idx_events_venue_id ON events(venue_id);

-- Ticket tiers per booking
CREATE TABLE IF NOT EXISTS ticket_tiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL DEFAULT 0,
    quantity INTEGER NOT NULL DEFAULT 0,
    sold_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ticket_tiers_booking_id ON ticket_tiers(booking_id);

-- Settlement sheets per booking
CREATE TABLE IF NOT EXISTS settlements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,
    door_revenue_cents INTEGER NOT NULL DEFAULT 0,
    expenses_cents INTEGER NOT NULL DEFAULT 0,
    musician_payout_cents INTEGER NOT NULL DEFAULT 0,
    venue_share_cents INTEGER NOT NULL DEFAULT 0,
    promoter_fee_cents INTEGER NOT NULL DEFAULT 0,
    tax_amount_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved')),
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    approved_by_user_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    approved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_settlements_booking_id ON settlements(booking_id);

-- Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(user_id, is_read);

-- FTS5 full-text search for venues
CREATE VIRTUAL TABLE IF NOT EXISTS venues_fts USING fts5(
    name, location, description, genre_tags,
    content='venues',
    content_rowid='id'
);

-- FTS5 sync triggers
CREATE TRIGGER IF NOT EXISTS venues_fts_insert AFTER INSERT ON venues BEGIN
    INSERT INTO venues_fts(rowid, name, location, description, genre_tags)
    VALUES (new.id, new.name, new.location, new.description, new.genre_tags);
END;

CREATE TRIGGER IF NOT EXISTS venues_fts_update AFTER UPDATE ON venues BEGIN
    DELETE FROM venues_fts WHERE rowid = old.id;
    INSERT INTO venues_fts(rowid, name, location, description, genre_tags)
    VALUES (new.id, new.name, new.location, new.description, new.genre_tags);
END;

CREATE TRIGGER IF NOT EXISTS venues_fts_delete AFTER DELETE ON venues BEGIN
    DELETE FROM venues_fts WHERE rowid = old.id;
END;
```

---

## Data Ownership

No two agents write to the same table. The "Owner Module" column identifies
which Python module contains the INSERT/UPDATE/DELETE functions for each table.

| Table | Owner Agent | Owner Module | Read By |
|-------|-----------|-------------|---------|
| users | models (3) | app.models | auth (2), all route agents via decorators |
| venues | models (3) | app.models | venue-crud (4), room-crud (5), booking-create (7), promoter-events (10), search (15), analytics (18-20), dashboards (21-23) |
| rooms | models (3) | app.models | room-crud (5), availability (6), booking-create (7), booking-manage (8), settlement-views (13) |
| availability_windows | models (3) | app.models | availability (6), booking-create (7) |
| bookings (INSERT, non-state UPDATE) | models (3) | app.models | booking-create (7), booking-manage (8), ticket-tiers (11), settlement-views (13), analytics (18-20), dashboards (21-23) |
| bookings.state (UPDATE) | booking-lifecycle (9) | app.booking_lifecycle | booking-manage (8), settlement-views (13) |
| booking_history (INSERT) | booking-lifecycle (9) | app.booking_lifecycle | booking-manage (8), booking-create (7) |
| events | models (3) | app.models | promoter-events (10), analytics-promoter (20), dashboard-promoter (23) |
| ticket_tiers | models (3) | app.models | ticket-tiers (11), settlement-views (13), booking-manage (8) |
| settlements | models (3) | app.models | settlement-views (13), settlement-pdf (14), analytics (18-20), dashboards (21-23) |
| notifications | notifications (16) | app.notifications | notification-views (17), dashboards (21-23) |
| venues_fts | models (3) | triggers in schema.sql | search (15) |

---

## Model Functions

### Database (app/db.py -- models agent 3)

```python
import sqlite3
from flask import g, current_app
import click

def get_db():
    """Returns the request-scoped database connection.
    Usage:
        conn = get_db()
        venues = get_all_venues(conn)
    For atomic writes, start a transaction:
        conn = get_db()
        conn.execute('BEGIN IMMEDIATE')
        # ... operations ...
        conn.commit()
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database from schema.sql."""
    conn = get_db()
    with current_app.open_resource('schema.sql') as f:
        conn.executescript(f.read().decode('utf8'))

@click.command('init-db')
def init_db_command():
    init_db()
    click.echo('Database initialized.')
```

### User Functions (app/models.py -- models agent 3)

```python
# Returns: int (the new user's ID)
# Usage:
#   user_id = create_user(conn, 'jdoe', 'j@example.com', hashed_pw, 'musician', 'John Doe')
#   redirect(url_for('auth.login'))
def create_user(conn, username, email, password_hash, role, display_name):
    cur = conn.execute(
        'INSERT INTO users (username, email, password_hash, role, display_name) VALUES (?, ?, ?, ?, ?)',
        (username, email, password_hash, role, display_name)
    )
    conn.commit()
    return cur.lastrowid

# Returns: sqlite3.Row or None
# Usage:
#   user = get_user_by_id(conn, user_id)
#   if user is None: abort(404)
def get_user_by_id(conn, user_id):
    return conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

# Returns: sqlite3.Row or None
# Usage:
#   user = get_user_by_username(conn, username)
#   if user is None: flash('Invalid credentials', 'error')
def get_user_by_username(conn, username):
    return conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

# Returns: None
# Usage:
#   update_user_profile(conn, g.user['id'], display_name, bio, genre_tags)
#   conn.commit()
def update_user_profile(conn, user_id, display_name, bio, genre_tags):
    conn.execute(
        'UPDATE users SET display_name = ?, bio = ?, genre_tags = ? WHERE id = ?',
        (display_name, bio, genre_tags, user_id)
    )
```

### Venue Functions (app/models.py -- models agent 3)

```python
# Returns: int (the new venue's ID)
# Usage:
#   venue_id = create_venue(conn, g.user['id'], name, location, description, capacity, genre_tags)
#   conn.commit()
#   redirect(url_for('venues.detail', venue_id=venue_id))
def create_venue(conn, user_id, name, location, description, capacity, genre_tags):
    cur = conn.execute(
        'INSERT INTO venues (user_id, name, location, description, capacity, genre_tags) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, name, location, description, capacity, genre_tags)
    )
    return cur.lastrowid

# Returns: sqlite3.Row or None
def get_venue(conn, venue_id):
    return conn.execute('SELECT * FROM venues WHERE id = ?', (venue_id,)).fetchone()

# Returns: list[sqlite3.Row]
def get_venues_by_manager(conn, user_id):
    return conn.execute('SELECT * FROM venues WHERE user_id = ? ORDER BY name', (user_id,)).fetchall()

# Returns: list[sqlite3.Row]
def get_all_venues(conn):
    return conn.execute('SELECT * FROM venues ORDER BY name').fetchall()

# Returns: None -- does NOT commit
def update_venue(conn, venue_id, name, location, description, capacity, genre_tags):
    conn.execute(
        'UPDATE venues SET name=?, location=?, description=?, capacity=?, genre_tags=?, updated_at=datetime("now") WHERE id=?',
        (name, location, description, capacity, genre_tags, venue_id)
    )

# Returns: None -- does NOT commit
def delete_venue(conn, venue_id):
    conn.execute('DELETE FROM venues WHERE id = ?', (venue_id,))
```

### Room Functions (app/models.py -- models agent 3)

```python
# Returns: int (room_id)
def create_room(conn, venue_id, name, capacity, description, has_pa, has_lighting):
    cur = conn.execute(
        'INSERT INTO rooms (venue_id, name, capacity, description, has_pa, has_lighting) VALUES (?, ?, ?, ?, ?, ?)',
        (venue_id, name, capacity, description, int(has_pa), int(has_lighting))
    )
    return cur.lastrowid

# Returns: sqlite3.Row or None
def get_room(conn, room_id):
    return conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()

# Returns: list[sqlite3.Row]
def get_rooms_by_venue(conn, venue_id):
    return conn.execute('SELECT * FROM rooms WHERE venue_id = ? ORDER BY name', (venue_id,)).fetchall()

# Returns: None -- does NOT commit
def update_room(conn, room_id, name, capacity, description, has_pa, has_lighting):
    conn.execute(
        'UPDATE rooms SET name=?, capacity=?, description=?, has_pa=?, has_lighting=? WHERE id=?',
        (name, capacity, description, int(has_pa), int(has_lighting), room_id)
    )

# Returns: None -- does NOT commit
def delete_room(conn, room_id):
    conn.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
```

### Availability Functions (app/models.py -- models agent 3)

```python
# Returns: int (window_id)
def create_availability_window(conn, room_id, day_of_week, start_time, end_time):
    cur = conn.execute(
        'INSERT INTO availability_windows (room_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)',
        (room_id, day_of_week, start_time, end_time)
    )
    return cur.lastrowid

# Returns: list[sqlite3.Row]
def get_availability_windows(conn, room_id):
    return conn.execute(
        'SELECT * FROM availability_windows WHERE room_id = ? ORDER BY day_of_week, start_time',
        (room_id,)
    ).fetchall()

# Returns: None -- does NOT commit
def delete_availability_window(conn, window_id):
    conn.execute('DELETE FROM availability_windows WHERE id = ?', (window_id,))

# Returns: bool (True if available, False if conflict exists)
# IMPORTANT: must be called inside BEGIN IMMEDIATE transaction
# Usage:
#   conn = get_db()
#   conn.execute('BEGIN IMMEDIATE')
#   if not check_room_available(conn, room_id, event_date, start_time, end_time):
#       conn.rollback()
#       flash('Time slot conflict.', 'error')
#       return redirect(...)
#   booking_id = create_booking(conn, ...)
#   conn.commit()
def check_room_available(conn, room_id, event_date, start_time, end_time):
    conflict = conn.execute(
        '''SELECT id FROM bookings
           WHERE room_id = ? AND event_date = ?
           AND start_time < ? AND end_time > ?
           AND state NOT IN ('settled', 'paid')''',
        (room_id, event_date, end_time, start_time)
    ).fetchone()
    return conflict is None
```

### Booking Functions (app/models.py -- models agent 3)

```python
# Returns: int (booking_id)
# IMPORTANT: does NOT commit -- caller commits after conflict check
# Usage (inside BEGIN IMMEDIATE):
#   booking_id = create_booking(conn, room_id, g.user['id'], event_name, event_date,
#                                start_time, end_time, deal_type, guarantee_cents,
#                                door_split_pct, promoter_fee_pct, tax_pct, notes)
#   conn.commit()
def create_booking(conn, room_id, musician_user_id, event_name, event_date,
                   start_time, end_time, deal_type, guarantee_cents,
                   door_split_pct, promoter_fee_pct, tax_pct, notes):
    cur = conn.execute(
        '''INSERT INTO bookings (room_id, musician_user_id, event_name, event_date,
           start_time, end_time, state, deal_type, guarantee_cents, door_split_pct,
           promoter_fee_pct, tax_pct, notes)
           VALUES (?, ?, ?, ?, ?, ?, 'requested', ?, ?, ?, ?, ?, ?)''',
        (room_id, musician_user_id, event_name, event_date, start_time, end_time,
         deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes)
    )
    return cur.lastrowid

# Returns: sqlite3.Row or None (with joined venue/room/musician info)
def get_booking(conn, booking_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, r.venue_id, v.name AS venue_name,
           v.user_id AS venue_manager_id, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE b.id = ?''',
        (booking_id,)
    ).fetchone()

# Returns: list[sqlite3.Row]
def get_bookings_by_musician(conn, musician_user_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, v.name AS venue_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE b.musician_user_id = ?
           ORDER BY b.event_date DESC''',
        (musician_user_id,)
    ).fetchall()

# Returns: list[sqlite3.Row]
def get_bookings_by_venue(conn, venue_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE r.venue_id = ?
           ORDER BY b.event_date DESC''',
        (venue_id,)
    ).fetchall()

# Returns: list[sqlite3.Row]
def get_pending_bookings_for_venue(conn, venue_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE r.venue_id = ? AND b.state = 'requested'
           ORDER BY b.event_date ASC''',
        (venue_id,)
    ).fetchall()

# Returns: list[sqlite3.Row]
def get_bookings_by_event(conn, event_id):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE b.event_id = ?
           ORDER BY b.start_time ASC''',
        (event_id,)
    ).fetchall()

# Returns: list[sqlite3.Row] (booking history for audit trail)
def get_booking_history(conn, booking_id):
    return conn.execute(
        '''SELECT bh.*, u.display_name AS actor_name
           FROM booking_history bh
           JOIN users u ON bh.actor_user_id = u.id
           WHERE bh.booking_id = ?
           ORDER BY bh.created_at DESC''',
        (booking_id,)
    ).fetchall()
```

### Event Functions (app/models.py -- models agent 3)

```python
# Returns: int (event_id)
def create_event(conn, promoter_user_id, venue_id, name, description, event_date):
    cur = conn.execute(
        'INSERT INTO events (promoter_user_id, venue_id, name, description, event_date) VALUES (?, ?, ?, ?, ?)',
        (promoter_user_id, venue_id, name, description, event_date)
    )
    return cur.lastrowid

# Returns: sqlite3.Row or None (with venue name)
def get_event(conn, event_id):
    return conn.execute(
        '''SELECT e.*, v.name AS venue_name, u.display_name AS promoter_name
           FROM events e
           JOIN venues v ON e.venue_id = v.id
           JOIN users u ON e.promoter_user_id = u.id
           WHERE e.id = ?''',
        (event_id,)
    ).fetchone()

# Returns: list[sqlite3.Row]
def get_events_by_promoter(conn, promoter_user_id):
    return conn.execute(
        '''SELECT e.*, v.name AS venue_name
           FROM events e JOIN venues v ON e.venue_id = v.id
           WHERE e.promoter_user_id = ?
           ORDER BY e.event_date DESC''',
        (promoter_user_id,)
    ).fetchall()

# Returns: None -- does NOT commit
def update_event(conn, event_id, name, description, event_date):
    conn.execute(
        'UPDATE events SET name=?, description=?, event_date=?, updated_at=datetime("now") WHERE id=?',
        (name, description, event_date, event_id)
    )

# Returns: None -- does NOT commit
def link_booking_to_event(conn, booking_id, event_id):
    conn.execute('UPDATE bookings SET event_id = ? WHERE id = ?', (event_id, booking_id))
```

### Ticket Tier Functions (app/models.py -- models agent 3)

```python
# Returns: int (tier_id)
def create_ticket_tier(conn, booking_id, name, price_cents, quantity):
    cur = conn.execute(
        'INSERT INTO ticket_tiers (booking_id, name, price_cents, quantity) VALUES (?, ?, ?, ?)',
        (booking_id, name, price_cents, quantity)
    )
    return cur.lastrowid

# Returns: list[sqlite3.Row]
def get_ticket_tiers(conn, booking_id):
    return conn.execute(
        'SELECT * FROM ticket_tiers WHERE booking_id = ? ORDER BY name', (booking_id,)
    ).fetchall()

# Returns: None -- does NOT commit
def update_ticket_tier(conn, tier_id, name, price_cents, quantity, sold_count):
    conn.execute(
        'UPDATE ticket_tiers SET name=?, price_cents=?, quantity=?, sold_count=? WHERE id=?',
        (name, price_cents, quantity, sold_count, tier_id)
    )

# Returns: None -- does NOT commit
def delete_ticket_tier(conn, tier_id):
    conn.execute('DELETE FROM ticket_tiers WHERE id = ?', (tier_id,))

# Returns: int (total door revenue in cents)
# Usage:
#   total_cents = get_total_door_revenue_cents(conn, booking_id)
def get_total_door_revenue_cents(conn, booking_id):
    row = conn.execute(
        'SELECT COALESCE(SUM(price_cents * sold_count), 0) AS total FROM ticket_tiers WHERE booking_id = ?',
        (booking_id,)
    ).fetchone()
    return row['total']
```

### Settlement Functions (app/models.py -- models agent 3)

```python
# Returns: int (settlement_id) -- does NOT commit
def create_settlement(conn, booking_id, door_revenue_cents, expenses_cents,
                      musician_payout_cents, venue_share_cents,
                      promoter_fee_cents, tax_amount_cents, created_by_user_id):
    cur = conn.execute(
        '''INSERT INTO settlements (booking_id, door_revenue_cents, expenses_cents,
           musician_payout_cents, venue_share_cents, promoter_fee_cents,
           tax_amount_cents, created_by_user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (booking_id, door_revenue_cents, expenses_cents, musician_payout_cents,
         venue_share_cents, promoter_fee_cents, tax_amount_cents, created_by_user_id)
    )
    return cur.lastrowid

# Returns: sqlite3.Row or None (with booking/venue/musician info)
def get_settlement(conn, settlement_id):
    return conn.execute(
        '''SELECT s.*, b.event_name, b.event_date, b.deal_type,
           b.guarantee_cents, b.door_split_pct, b.promoter_fee_pct, b.tax_pct,
           r.name AS room_name, v.name AS venue_name,
           u.display_name AS musician_name
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE s.id = ?''',
        (settlement_id,)
    ).fetchone()

# Returns: sqlite3.Row or None
def get_settlement_by_booking(conn, booking_id):
    return conn.execute(
        'SELECT * FROM settlements WHERE booking_id = ?', (booking_id,)
    ).fetchone()

# Returns: list[sqlite3.Row]
def get_settlements_list(conn, user_id, role):
    if role == 'venue_manager':
        return conn.execute(
            '''SELECT s.*, b.event_name, b.event_date, u.display_name AS musician_name
               FROM settlements s
               JOIN bookings b ON s.booking_id = b.id
               JOIN rooms r ON b.room_id = r.id
               JOIN venues v ON r.venue_id = v.id
               JOIN users u ON b.musician_user_id = u.id
               WHERE v.user_id = ?
               ORDER BY s.created_at DESC''',
            (user_id,)
        ).fetchall()
    elif role == 'musician':
        return conn.execute(
            '''SELECT s.*, b.event_name, b.event_date, v.name AS venue_name
               FROM settlements s
               JOIN bookings b ON s.booking_id = b.id
               JOIN rooms r ON b.room_id = r.id
               JOIN venues v ON r.venue_id = v.id
               WHERE b.musician_user_id = ?
               ORDER BY s.created_at DESC''',
            (user_id,)
        ).fetchall()
    else:  # promoter
        return conn.execute(
            '''SELECT s.*, b.event_name, b.event_date, v.name AS venue_name
               FROM settlements s
               JOIN bookings b ON s.booking_id = b.id
               JOIN rooms r ON b.room_id = r.id
               JOIN venues v ON r.venue_id = v.id
               JOIN events e ON b.event_id = e.id
               WHERE e.promoter_user_id = ?
               ORDER BY s.created_at DESC''',
            (user_id,)
        ).fetchall()

# Returns: None -- does NOT commit
def approve_settlement(conn, settlement_id, approved_by_user_id):
    conn.execute(
        '''UPDATE settlements SET status='approved', approved_by_user_id=?,
           approved_at=datetime('now') WHERE id=?''',
        (approved_by_user_id, settlement_id)
    )
```

### Analytics Functions (app/models.py -- models agent 3)

```python
# Returns: list[sqlite3.Row] with columns: month (TEXT 'YYYY-MM'), total_cents (INT)
def get_venue_revenue_by_month(conn, venue_id):
    return conn.execute(
        '''SELECT strftime('%Y-%m', b.event_date) AS month,
           SUM(s.door_revenue_cents) AS total_cents
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           WHERE r.venue_id = ?
           GROUP BY month ORDER BY month''',
        (venue_id,)
    ).fetchall()

# Returns: list[sqlite3.Row] with columns: room_name (TEXT), booking_count (INT), total_slots (INT)
def get_venue_occupancy_by_room(conn, venue_id):
    return conn.execute(
        '''SELECT r.name AS room_name,
           COUNT(b.id) AS booking_count
           FROM rooms r
           LEFT JOIN bookings b ON r.id = b.room_id AND b.state NOT IN ('requested')
           WHERE r.venue_id = ?
           GROUP BY r.id ORDER BY r.name''',
        (venue_id,)
    ).fetchall()

# Returns: list[sqlite3.Row] with columns: genre (TEXT), count (INT)
def get_venue_genre_distribution(conn, venue_id):
    return conn.execute(
        '''SELECT u.genre_tags AS genre, COUNT(*) AS count
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE r.venue_id = ? AND u.genre_tags != ''
           GROUP BY u.genre_tags ORDER BY count DESC LIMIT 10''',
        (venue_id,)
    ).fetchall()

# Returns: list[sqlite3.Row] with columns: month, total_cents
def get_musician_earnings_by_month(conn, user_id):
    return conn.execute(
        '''SELECT strftime('%Y-%m', b.event_date) AS month,
           SUM(s.musician_payout_cents) AS total_cents
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           WHERE b.musician_user_id = ?
           GROUP BY month ORDER BY month''',
        (user_id,)
    ).fetchall()

# Returns: list[sqlite3.Row] with columns: venue_name (TEXT), gig_count (INT)
def get_musician_venues_played(conn, user_id):
    return conn.execute(
        '''SELECT v.name AS venue_name, COUNT(*) AS gig_count
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE b.musician_user_id = ? AND b.state IN ('performed', 'settled', 'paid')
           GROUP BY v.id ORDER BY gig_count DESC LIMIT 10''',
        (user_id,)
    ).fetchall()

# Returns: dict with keys: confirmed (int), rejected (int), total (int)
def get_musician_booking_success_rate(conn, user_id):
    rows = conn.execute(
        '''SELECT state, COUNT(*) AS cnt FROM bookings
           WHERE musician_user_id = ? GROUP BY state''',
        (user_id,)
    ).fetchall()
    confirmed = sum(r['cnt'] for r in rows if r['state'] not in ('requested',))
    total = sum(r['cnt'] for r in rows)
    rejected_count = 0  # bookings that went back to available are deleted from history
    return {'confirmed': confirmed, 'rejected': rejected_count, 'total': total}

# Returns: list[sqlite3.Row] with columns: month, total_cents
def get_promoter_revenue_by_month(conn, user_id):
    return conn.execute(
        '''SELECT strftime('%Y-%m', b.event_date) AS month,
           SUM(s.promoter_fee_cents) AS total_cents
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN events e ON b.event_id = e.id
           WHERE e.promoter_user_id = ?
           GROUP BY month ORDER BY month''',
        (user_id,)
    ).fetchall()

# Returns: list[sqlite3.Row] with columns: venue_name, total_cents
def get_promoter_settlements_by_venue(conn, user_id):
    return conn.execute(
        '''SELECT v.name AS venue_name, SUM(s.door_revenue_cents) AS total_cents
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           JOIN events e ON b.event_id = e.id
           WHERE e.promoter_user_id = ?
           GROUP BY v.id ORDER BY total_cents DESC''',
        (user_id,)
    ).fetchall()

# Returns: list[sqlite3.Row] with columns: status (TEXT), count (INT)
def get_promoter_event_status_counts(conn, user_id):
    return conn.execute(
        '''SELECT b.state AS status, COUNT(*) AS count
           FROM bookings b
           JOIN events e ON b.event_id = e.id
           WHERE e.promoter_user_id = ?
           GROUP BY b.state''',
        (user_id,)
    ).fetchall()
```

### Dashboard Summary Functions (app/models.py -- models agent 3)

```python
# Returns: list[sqlite3.Row] -- upcoming confirmed bookings for a venue
def get_venue_upcoming_bookings(conn, venue_id, limit=5):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, u.display_name AS musician_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN users u ON b.musician_user_id = u.id
           WHERE r.venue_id = ? AND b.state IN ('confirmed', 'advanced')
           AND b.event_date >= date('now')
           ORDER BY b.event_date ASC LIMIT ?''',
        (venue_id, limit)
    ).fetchall()

# Returns: int -- count of pending booking requests for a venue
def get_venue_pending_count(conn, venue_id):
    row = conn.execute(
        '''SELECT COUNT(*) AS cnt FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           WHERE r.venue_id = ? AND b.state = 'requested' ''',
        (venue_id,)
    ).fetchone()
    return row['cnt']

# Returns: list[sqlite3.Row] -- upcoming gigs for a musician
def get_musician_upcoming_gigs(conn, user_id, limit=5):
    return conn.execute(
        '''SELECT b.*, r.name AS room_name, v.name AS venue_name
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE b.musician_user_id = ? AND b.state IN ('confirmed', 'advanced')
           AND b.event_date >= date('now')
           ORDER BY b.event_date ASC LIMIT ?''',
        (user_id, limit)
    ).fetchall()

# Returns: int -- count of musician's pending requests
def get_musician_pending_count(conn, user_id):
    row = conn.execute(
        'SELECT COUNT(*) AS cnt FROM bookings WHERE musician_user_id = ? AND state = ?',
        (user_id, 'requested')
    ).fetchone()
    return row['cnt']

# Returns: list[sqlite3.Row] -- upcoming events for a promoter
def get_promoter_upcoming_events(conn, user_id, limit=5):
    return conn.execute(
        '''SELECT e.*, v.name AS venue_name
           FROM events e
           JOIN venues v ON e.venue_id = v.id
           WHERE e.promoter_user_id = ? AND e.event_date >= date('now')
           ORDER BY e.event_date ASC LIMIT ?''',
        (user_id, limit)
    ).fetchall()

# Returns: dict with keys: total_settlements (int), pending_settlements (int)
def get_promoter_settlement_status(conn, user_id):
    row = conn.execute(
        '''SELECT COUNT(*) AS total,
           SUM(CASE WHEN s.status = 'draft' THEN 1 ELSE 0 END) AS pending
           FROM settlements s
           JOIN bookings b ON s.booking_id = b.id
           JOIN events e ON b.event_id = e.id
           WHERE e.promoter_user_id = ?''',
        (user_id,)
    ).fetchone()
    return {'total_settlements': row['total'] or 0, 'pending_settlements': row['pending'] or 0}
```

---

## Booking Lifecycle (app/booking_lifecycle.py -- booking-lifecycle agent 9)

```python
"""
Booking state machine. Manages all state transitions and guard conditions.
Dispatches notifications on each transition.

TRANSITIONS dict defines allowed state changes.
advance_booking_state() is the ONLY function that writes to bookings.state
and booking_history. It does NOT commit -- the caller commits.
"""
from app.notifications import create_notification

TRANSITIONS = {
    'requested':  ['confirmed', 'rejected'],
    'confirmed':  ['advanced', 'cancelled'],
    'advanced':   ['performed', 'cancelled'],
    'performed':  ['settled'],
    'settled':    ['paid'],
    'paid':       [],
}

# Rejection and cancellation are pseudo-states: the booking is deleted
# or returned to a terminal state. For simplicity, 'rejected' and 'cancelled'
# cause the booking to be soft-marked (state='rejected'/'cancelled') so
# history is preserved.

# Revised TRANSITIONS with rejection/cancel support:
TRANSITIONS = {
    'requested':  ['confirmed', 'rejected'],
    'confirmed':  ['advanced', 'cancelled'],
    'advanced':   ['performed', 'cancelled'],
    'performed':  ['settled'],
    'settled':    ['paid'],
    'paid':       [],
    'rejected':   [],
    'cancelled':  [],
}

def _guard_confirm(conn, booking, actor_user_id):
    """Only the venue manager who owns the venue can confirm."""
    venue_manager_id = booking['venue_manager_id']
    return actor_user_id == venue_manager_id

def _guard_reject(conn, booking, actor_user_id):
    """Only venue manager can reject."""
    return actor_user_id == booking['venue_manager_id']

def _guard_advance(conn, booking, actor_user_id):
    """Only venue manager can record advance payment."""
    return actor_user_id == booking['venue_manager_id']

def _guard_cancel(conn, booking, actor_user_id):
    """Venue manager or the requesting musician can cancel."""
    return actor_user_id in (booking['venue_manager_id'], booking['musician_user_id'])

def _guard_perform(conn, booking, actor_user_id):
    """Only venue manager marks as performed."""
    return actor_user_id == booking['venue_manager_id']

def _guard_settle(conn, booking, actor_user_id):
    """Only venue manager can create settlement (must have settlement row)."""
    row = conn.execute('SELECT id FROM settlements WHERE booking_id = ?',
                       (booking['id'],)).fetchone()
    return row is not None and actor_user_id == booking['venue_manager_id']

def _guard_pay(conn, booking, actor_user_id):
    """Only venue manager marks as paid."""
    return actor_user_id == booking['venue_manager_id']

GUARD_FUNCTIONS = {
    ('requested', 'confirmed'): _guard_confirm,
    ('requested', 'rejected'): _guard_reject,
    ('confirmed', 'advanced'): _guard_advance,
    ('confirmed', 'cancelled'): _guard_cancel,
    ('advanced', 'performed'): _guard_perform,
    ('advanced', 'cancelled'): _guard_cancel,
    ('performed', 'settled'): _guard_settle,
    ('settled', 'paid'): _guard_pay,
}

# Notification messages per transition
NOTIFICATION_MAP = {
    'confirmed': {
        'musician': 'Your booking "{event_name}" has been confirmed!',
    },
    'rejected': {
        'musician': 'Your booking request "{event_name}" was declined.',
    },
    'advanced': {
        'musician': 'Advance payment recorded for "{event_name}".',
    },
    'cancelled': {
        'musician': 'Booking "{event_name}" has been cancelled.',
        'venue_manager': 'Booking "{event_name}" has been cancelled.',
    },
    'performed': {
        'musician': 'Show "{event_name}" marked as performed. Settlement pending.',
        'venue_manager': 'Show "{event_name}" marked as performed.',
    },
    'settled': {
        'musician': 'Settlement sheet ready for "{event_name}".',
        'venue_manager': 'Settlement created for "{event_name}".',
    },
    'paid': {
        'musician': 'Payment confirmed for "{event_name}"!',
    },
}

def _dispatch_notifications(conn, booking, new_state):
    """Create notifications for affected parties after a state transition."""
    templates = NOTIFICATION_MAP.get(new_state, {})
    event_name = booking['event_name']
    booking_id = booking['id']
    link = f'/bookings/{booking_id}'

    if 'musician' in templates:
        create_notification(
            conn, booking['musician_user_id'],
            templates['musician'].format(event_name=event_name),
            link
        )
    if 'venue_manager' in templates:
        create_notification(
            conn, booking['venue_manager_id'],
            templates['venue_manager'].format(event_name=event_name),
            f'/manage/bookings/{booking_id}'
        )

def advance_booking_state(conn, booking_id, new_state, actor_user_id, notes=''):
    """
    Advance a booking to new_state. Creates audit trail + notifications.
    Does NOT commit -- caller commits.

    Returns: bool (True if transition succeeded, False if denied)

    Usage (in route handler):
        conn = get_db()
        conn.execute('BEGIN IMMEDIATE')
        success = advance_booking_state(conn, booking_id, 'confirmed', g.user['id'])
        if not success:
            conn.rollback()
            flash('Cannot transition booking to this state.', 'error')
            return redirect(url_for('booking_manage.detail', booking_id=booking_id))
        conn.commit()
        flash('Booking confirmed.', 'success')
        return redirect(url_for('booking_manage.detail', booking_id=booking_id))
    """
    booking = conn.execute(
        '''SELECT b.*, r.venue_id, v.user_id AS venue_manager_id
           FROM bookings b
           JOIN rooms r ON b.room_id = r.id
           JOIN venues v ON r.venue_id = v.id
           WHERE b.id = ?''',
        (booking_id,)
    ).fetchone()

    if booking is None:
        return False

    current_state = booking['state']
    if new_state not in TRANSITIONS.get(current_state, []):
        return False

    guard = GUARD_FUNCTIONS.get((current_state, new_state))
    if guard and not guard(conn, booking, actor_user_id):
        return False

    conn.execute(
        'UPDATE bookings SET state = ?, updated_at = datetime("now") WHERE id = ?',
        (new_state, booking_id)
    )

    conn.execute(
        '''INSERT INTO booking_history (booking_id, from_state, to_state,
           actor_user_id, notes, created_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))''',
        (booking_id, current_state, new_state, actor_user_id, notes)
    )

    _dispatch_notifications(conn, booking, new_state)
    return True
```

**CRITICAL: Agents 8, 13 consuming this function MUST use this exact pattern:**
```python
conn = get_db()
conn.execute('BEGIN IMMEDIATE')
success = advance_booking_state(conn, booking_id, '<new_state>', g.user['id'])
if not success:
    conn.rollback()
    flash('Cannot transition booking to this state.', 'error')
    return redirect(url_for('<blueprint>.detail', booking_id=booking_id))
conn.commit()
flash('<Success message>.', 'success')
return redirect(url_for('<blueprint>.detail', booking_id=booking_id))
```

---

## Notifications (app/notifications.py -- notifications agent 16)

```python
"""
Notification helpers. create_notification() does NOT commit -- caller commits.
Used by booking_lifecycle.py and can be called directly from route handlers.
"""

def create_notification(conn, user_id, message, link=''):
    """
    Create a notification. Does NOT commit.
    Returns: int (notification_id)
    """
    cur = conn.execute(
        'INSERT INTO notifications (user_id, message, link) VALUES (?, ?, ?)',
        (user_id, message, link)
    )
    return cur.lastrowid

def get_notifications(conn, user_id, limit=20):
    """Returns: list[sqlite3.Row] ordered by newest first."""
    return conn.execute(
        'SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()

def get_unread_count(conn, user_id):
    """Returns: int"""
    row = conn.execute(
        'SELECT COUNT(*) AS cnt FROM notifications WHERE user_id = ? AND is_read = 0',
        (user_id,)
    ).fetchone()
    return row['cnt']

def mark_notification_read(conn, notification_id):
    """Does NOT commit."""
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))

def mark_all_read(conn, user_id):
    """Does NOT commit."""
    conn.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0',
                 (user_id,))
```

---

## Settlement Engine (app/settlement_engine.py -- settlement-engine agent 12)

```python
"""
Pure calculation functions for settlement sheets.
No database access. All amounts in integer cents.
"""

def calculate_settlement(door_revenue_cents, expenses_cents, deal_type,
                         guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct):
    """
    Calculate settlement amounts.

    Returns: dict with keys:
        musician_payout_cents (int)
        venue_share_cents (int)
        promoter_fee_cents (int)
        tax_amount_cents (int)

    Usage:
        result = calculate_settlement(50000, 5000, 'hybrid', 20000, 70, 10, 8)
        settlement_id = create_settlement(conn, booking_id, 50000, 5000,
            result['musician_payout_cents'], result['venue_share_cents'],
            result['promoter_fee_cents'], result['tax_amount_cents'],
            g.user['id'])
    """
    net_door = door_revenue_cents - expenses_cents
    if net_door < 0:
        net_door = 0

    # Promoter fee on gross door revenue
    promoter_fee_cents = door_revenue_cents * promoter_fee_pct // 100

    # Tax on gross door revenue
    tax_amount_cents = door_revenue_cents * tax_pct // 100

    # Musician payout based on deal type
    if deal_type == 'guarantee':
        musician_payout_cents = guarantee_cents
    elif deal_type == 'door_split':
        musician_payout_cents = net_door * door_split_pct // 100
    else:  # hybrid
        door_share = net_door * door_split_pct // 100
        musician_payout_cents = max(guarantee_cents, door_share)

    # Venue gets the remainder
    venue_share_cents = door_revenue_cents - musician_payout_cents - promoter_fee_cents - tax_amount_cents

    return {
        'musician_payout_cents': musician_payout_cents,
        'venue_share_cents': venue_share_cents,
        'promoter_fee_cents': promoter_fee_cents,
        'tax_amount_cents': tax_amount_cents,
    }
```

---

## Settlement PDF (app/settlement_pdf.py -- settlement-pdf agent 14)

```python
"""
ReportLab PDF generation for settlement sheets.
Takes a settlement dict (from get_settlement) and returns PDF bytes.
"""
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def generate_settlement_pdf(settlement):
    """
    Generate a PDF settlement sheet.

    Args:
        settlement: sqlite3.Row from get_settlement() -- has all joined fields

    Returns: bytes (PDF content)

    Usage:
        settlement = get_settlement(conn, settlement_id)
        pdf_bytes = generate_settlement_pdf(settlement)
        return Response(pdf_bytes, mimetype='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename=settlement_{settlement_id}.pdf'})
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph(f"Settlement Sheet", styles['Title']))
    elements.append(Paragraph(f"Event: {settlement['event_name']}", styles['Heading2']))
    elements.append(Paragraph(
        f"Date: {settlement['event_date']} | Venue: {settlement['venue_name']} | Room: {settlement['room_name']}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 0.25*inch))

    # Parties
    elements.append(Paragraph(f"Musician: {settlement['musician_name']}", styles['Normal']))
    elements.append(Paragraph(f"Deal Type: {settlement['deal_type'].replace('_', ' ').title()}", styles['Normal']))
    elements.append(Spacer(1, 0.25*inch))

    # Financial breakdown
    def fmt_dollars(cents):
        return f"${cents / 100:,.2f}"

    data = [
        ['Item', 'Amount'],
        ['Door Revenue', fmt_dollars(settlement['door_revenue_cents'])],
        ['Expenses', f"({fmt_dollars(settlement['expenses_cents'])})"],
        ['Musician Payout', fmt_dollars(settlement['musician_payout_cents'])],
        ['Venue Share', fmt_dollars(settlement['venue_share_cents'])],
        ['Promoter Fee', fmt_dollars(settlement['promoter_fee_cents'])],
        ['Tax', fmt_dollars(settlement['tax_amount_cents'])],
    ]

    table = Table(data, colWidths=[4*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.5*inch))

    # Signature lines
    elements.append(Paragraph("Signatures:", styles['Heading3']))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph("Venue Manager: _________________________  Date: __________", styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("Musician: _________________________  Date: __________", styles['Normal']))
    elements.append(Spacer(1, 0.5*inch))

    # Footer
    elements.append(Paragraph(
        f"Generated by VenueConnect on {settlement['created_at']}",
        styles['Normal']
    ))

    doc.build(elements)
    return buffer.getvalue()
```

---

## Jinja Filters (app/filters.py -- scaffold agent 1)

```python
def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert integer cents to dollar string. Usage: {{ amount|dollars }}"""
        if cents is None:
            return '$0.00'
        return f"${cents / 100:,.2f}"

    @app.template_filter('day_name')
    def day_name_filter(day_num):
        """Convert 0-6 to day name. Usage: {{ day_of_week|day_name }}"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[day_num] if 0 <= day_num <= 6 else str(day_num)
```

---

## Auth Decorators (app/decorators.py -- auth agent 2)

```python
from functools import wraps
from flask import session, g, redirect, url_for, abort, flash

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login'))
        from app.db import get_db
        from app.models import get_user_by_id
        conn = get_db()
        user = get_user_by_id(conn, session['user_id'])
        if user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        g.user = user
        return f(*args, **kwargs)
    return decorated

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.user['role'] != role:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
```

**Usage in every route file:**
```python
from app.decorators import login_required, role_required

@bp.route('/')
@login_required
@role_required('venue_manager')
def index():
    ...
```

---

## Route Table

### Auth Blueprint (/auth) -- auth agent 2

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET/POST | /auth/register | auth.register | username, email, password, confirm_password, role, display_name |
| GET/POST | /auth/login | auth.login | username, password |
| GET | /auth/logout | auth.logout | - |
| GET/POST | /auth/profile | auth.profile | display_name, bio, genre_tags |

### Venues Blueprint (/venues) -- venue-crud agent 4

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /venues/ | venues.list | - |
| GET | /venues/{id} | venues.detail | - |
| GET/POST | /venues/new | venues.create | name, location, description, capacity, genre_tags |
| GET/POST | /venues/{id}/edit | venues.edit | name, location, description, capacity, genre_tags |
| POST | /venues/{id}/delete | venues.delete | - |

### Rooms Blueprint (/rooms) -- room-crud agent 5

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /rooms/venue/{venue_id} | rooms.list | - |
| GET | /rooms/{id} | rooms.detail | - |
| GET/POST | /rooms/venue/{venue_id}/new | rooms.create | name, capacity, description, has_pa, has_lighting |
| GET/POST | /rooms/{id}/edit | rooms.edit | name, capacity, description, has_pa, has_lighting |
| POST | /rooms/{id}/delete | rooms.delete | - |

### Availability Blueprint (/availability) -- availability agent 6

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /availability/room/{room_id} | availability.calendar | - |
| GET/POST | /availability/room/{room_id}/add | availability.add | day_of_week, start_time, end_time |
| POST | /availability/{window_id}/delete | availability.delete | - |

### Booking Create Blueprint (/bookings) -- booking-create agent 7

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /bookings/browse | booking_create.browse | - |
| GET | /bookings/room/{room_id}/check | booking_create.room_availability | - |
| GET/POST | /bookings/room/{room_id}/request | booking_create.request_booking | event_name, event_date, start_time, end_time, deal_type, guarantee_dollars, door_split_pct, promoter_fee_pct, tax_pct, notes |
| GET | /bookings/mine | booking_create.my_bookings | - |
| GET | /bookings/{id} | booking_create.detail | - |

### Booking Manage Blueprint (/manage) -- booking-manage agent 8

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /manage/bookings | booking_manage.pending | - |
| GET | /manage/bookings/all | booking_manage.all_bookings | - |
| GET | /manage/bookings/{id} | booking_manage.detail | - |
| POST | /manage/bookings/{id}/confirm | booking_manage.confirm | - |
| POST | /manage/bookings/{id}/reject | booking_manage.reject | rejection_notes |
| POST | /manage/bookings/{id}/advance | booking_manage.record_advance | advance_dollars |
| POST | /manage/bookings/{id}/perform | booking_manage.mark_performed | - |
| POST | /manage/bookings/{id}/cancel | booking_manage.cancel | cancel_notes |
| POST | /manage/bookings/{id}/mark-paid | booking_manage.mark_paid | - |

### Events Blueprint (/events) -- promoter-events agent 10

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /events/ | events.list | - |
| GET | /events/{id} | events.detail | - |
| GET/POST | /events/new | events.create | venue_id, name, description, event_date |
| GET/POST | /events/{id}/edit | events.edit | name, description, event_date |
| POST | /events/{id}/link-booking | events.link_booking | booking_id |

### Tickets Blueprint (/tickets) -- ticket-tiers agent 11

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /tickets/booking/{booking_id} | tickets.manage | - |
| GET/POST | /tickets/booking/{booking_id}/add | tickets.add | name, price_dollars, quantity |
| GET/POST | /tickets/{tier_id}/edit | tickets.edit | name, price_dollars, quantity, sold_count |
| POST | /tickets/{tier_id}/delete | tickets.delete | - |

### Settlements Blueprint (/settlements) -- settlement-views agent 13

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /settlements/ | settlements.list | - |
| GET | /settlements/{id} | settlements.detail | - |
| GET/POST | /settlements/booking/{booking_id}/create | settlements.create | door_revenue_dollars, expenses_dollars |
| POST | /settlements/{id}/approve | settlements.approve | - |
| GET | /settlements/{id}/pdf | settlements.download_pdf | - |

### Search Blueprint (/search) -- search agent 15

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /search/ | search.index | q (query param) |

### Notification Views Blueprint (/notifications) -- notification-views agent 17

| Method | Path | url_for | Form Fields |
|--------|------|---------|-------------|
| GET | /notifications/ | notification_views.list | - |
| POST | /notifications/{id}/read | notification_views.mark_read | - |
| POST | /notifications/read-all | notification_views.mark_all_read | - |
| GET | /notifications/unread-count | notification_views.unread_count | - (returns JSON) |

### Analytics Blueprints -- analytics agents 18-20

| Method | Path | url_for | Agent |
|--------|------|---------|-------|
| GET | /analytics/venue | analytics_venue.index | 18 |
| GET | /analytics/musician | analytics_musician.index | 19 |
| GET | /analytics/promoter | analytics_promoter.index | 20 |

### Dashboard Blueprints -- dashboard agents 21-23

| Method | Path | url_for | Agent |
|--------|------|---------|-------|
| GET | /dashboard/venue | dashboard_venue.index | 21 |
| GET | /dashboard/musician | dashboard_musician.index | 22 |
| GET | /dashboard/promoter | dashboard_promoter.index | 23 |

---

## Template Render Context

Every `render_template()` call with exact variable names.

### Auth Templates (agent 2)

```python
# auth/login.html -- no extra context (just the form)
render_template('auth/login.html')

# auth/register.html -- no extra context
render_template('auth/register.html')

# auth/profile.html
render_template('auth/profile.html', user=g.user)
```

### Venue Templates (agent 4)

```python
# venues/list.html
render_template('venues/list.html', venues=venues)

# venues/detail.html
render_template('venues/detail.html', venue=venue, rooms=rooms)

# venues/form.html (create/edit -- venue is None for create)
render_template('venues/form.html', venue=venue)
```

### Room Templates (agent 5)

```python
# rooms/list.html
render_template('rooms/list.html', venue=venue, rooms=rooms)

# rooms/detail.html
render_template('rooms/detail.html', room=room, venue=venue)

# rooms/form.html (room is None for create)
render_template('rooms/form.html', room=room, venue=venue)
```

### Availability Templates (agent 6)

```python
# availability/calendar.html
render_template('availability/calendar.html',
    room=room, venue=venue, windows=windows, bookings=bookings)

# availability/form.html
render_template('availability/form.html', room=room)
```

### Booking Create Templates (agent 7)

```python
# booking_create/browse.html
render_template('booking_create/browse.html', venues=venues)

# booking_create/room_availability.html
render_template('booking_create/room_availability.html',
    room=room, venue=venue, windows=windows)

# booking_create/request_form.html
render_template('booking_create/request_form.html', room=room, venue=venue)

# booking_create/my_bookings.html
render_template('booking_create/my_bookings.html', bookings=bookings)

# booking_create/detail.html
render_template('booking_create/detail.html',
    booking=booking, history=history, settlement=settlement, tiers=tiers)
```

### Booking Manage Templates (agent 8)

```python
# booking_manage/pending.html
render_template('booking_manage/pending.html', bookings=bookings, venue=venue)

# booking_manage/detail.html
render_template('booking_manage/detail.html',
    booking=booking, history=history, settlement=settlement, tiers=tiers)

# booking_manage/all_bookings.html
render_template('booking_manage/all_bookings.html', bookings=bookings, venue=venue)
```

### Event Templates (agent 10)

```python
# events/list.html
render_template('events/list.html', events=events)

# events/detail.html
render_template('events/detail.html', event=event, bookings=bookings)

# events/form.html (event is None for create)
render_template('events/form.html', event=event, venues=venues)
```

### Ticket Templates (agent 11)

```python
# tickets/manage.html
render_template('tickets/manage.html', booking=booking, tiers=tiers)

# tickets/form.html (tier is None for add)
render_template('tickets/form.html', tier=tier, booking=booking)
```

### Settlement Templates (agent 13)

```python
# settlements/list.html
render_template('settlements/list.html', settlements=settlements)

# settlements/detail.html
render_template('settlements/detail.html', settlement=settlement)

# settlements/form.html
# suggested_revenue_cents comes from get_total_door_revenue_cents(conn, booking_id)
render_template('settlements/form.html',
    booking=booking, suggested_revenue_cents=suggested_revenue_cents)
```

### Search Template (agent 15)

```python
# search/results.html
render_template('search/results.html', results=results, query=query)
```

### Notification Templates (agent 17)

```python
# notifications/list.html
render_template('notifications/list.html', notifications=notifications)
```

### Analytics Templates (agents 18-20)

```python
# analytics/venue.html (agent 18)
render_template('analytics/venue.html',
    revenue_data=revenue_data, occupancy_data=occupancy_data,
    genre_data=genre_data, venue=venue)

# analytics/musician.html (agent 19)
render_template('analytics/musician.html',
    earnings_data=earnings_data, venues_data=venues_data,
    success_data=success_data)

# analytics/promoter.html (agent 20)
render_template('analytics/promoter.html',
    revenue_data=revenue_data, settlements_data=settlements_data,
    status_data=status_data)
```

### Dashboard Templates (agents 21-23)

```python
# dashboard/venue.html (agent 21)
render_template('dashboard/venue.html',
    upcoming_bookings=upcoming_bookings, pending_count=pending_count,
    venues=venues)

# dashboard/musician.html (agent 22)
render_template('dashboard/musician.html',
    upcoming_gigs=upcoming_gigs, pending_count=pending_count,
    recent_notifications=recent_notifications)

# dashboard/promoter.html (agent 23)
render_template('dashboard/promoter.html',
    upcoming_events=upcoming_events, settlement_status=settlement_status)
```

---

## Cross-Boundary Wiring Table

Every cross-module import with exact code. Prevents FC3 (dead wiring).

| Consumer Agent | Consumer File | Import Statement | Used For |
|---------------|---------------|-----------------|----------|
| auth (2) | app/auth/routes.py | `from app.db import get_db` | DB access |
| auth (2) | app/auth/routes.py | `from app.models import create_user, get_user_by_id, get_user_by_username, update_user_profile` | User CRUD |
| auth (2) | app/decorators.py | `from app.models import get_user_by_id` | Session user lookup |
| venue-crud (4) | app/venues/routes.py | `from app.db import get_db` | DB access |
| venue-crud (4) | app/venues/routes.py | `from app.models import create_venue, get_venue, get_venues_by_manager, update_venue, delete_venue, get_rooms_by_venue` | Venue/room CRUD |
| venue-crud (4) | app/venues/routes.py | `from app.decorators import login_required, role_required` | Auth |
| room-crud (5) | app/rooms/routes.py | `from app.db import get_db` | DB access |
| room-crud (5) | app/rooms/routes.py | `from app.models import create_room, get_room, get_rooms_by_venue, get_venue, update_room, delete_room` | Room CRUD |
| room-crud (5) | app/rooms/routes.py | `from app.decorators import login_required, role_required` | Auth |
| availability (6) | app/availability/routes.py | `from app.db import get_db` | DB access |
| availability (6) | app/availability/routes.py | `from app.models import get_availability_windows, create_availability_window, delete_availability_window, get_room, get_venue` | Availability CRUD |
| availability (6) | app/availability/routes.py | `from app.decorators import login_required, role_required` | Auth |
| booking-create (7) | app/booking_create/routes.py | `from app.db import get_db` | DB access |
| booking-create (7) | app/booking_create/routes.py | `from app.models import get_all_venues, get_room, get_venue, get_availability_windows, check_room_available, create_booking, get_bookings_by_musician, get_booking, get_booking_history, get_settlement_by_booking, get_ticket_tiers` | Booking flow |
| booking-create (7) | app/booking_create/routes.py | `from app.decorators import login_required, role_required` | Auth |
| booking-manage (8) | app/booking_manage/routes.py | `from app.db import get_db` | DB access |
| booking-manage (8) | app/booking_manage/routes.py | `from app.models import get_booking, get_pending_bookings_for_venue, get_bookings_by_venue, get_booking_history, get_venues_by_manager, get_settlement_by_booking, get_ticket_tiers` | Booking data |
| booking-manage (8) | app/booking_manage/routes.py | `from app.booking_lifecycle import advance_booking_state` | State transitions |
| booking-manage (8) | app/booking_manage/routes.py | `from app.decorators import login_required, role_required` | Auth |
| promoter-events (10) | app/events/routes.py | `from app.db import get_db` | DB access |
| promoter-events (10) | app/events/routes.py | `from app.models import create_event, get_event, get_events_by_promoter, update_event, get_all_venues, link_booking_to_event, get_bookings_by_event` | Event CRUD |
| promoter-events (10) | app/events/routes.py | `from app.decorators import login_required, role_required` | Auth |
| ticket-tiers (11) | app/tickets/routes.py | `from app.db import get_db` | DB access |
| ticket-tiers (11) | app/tickets/routes.py | `from app.models import get_booking, get_ticket_tiers, create_ticket_tier, update_ticket_tier, delete_ticket_tier` | Ticket CRUD |
| ticket-tiers (11) | app/tickets/routes.py | `from app.decorators import login_required, role_required` | Auth |
| settlement-views (13) | app/settlements/routes.py | `from app.db import get_db` | DB access |
| settlement-views (13) | app/settlements/routes.py | `from app.models import get_booking, get_settlement, get_settlement_by_booking, create_settlement, approve_settlement, get_settlements_list, get_total_door_revenue_cents` | Settlement CRUD |
| settlement-views (13) | app/settlements/routes.py | `from app.settlement_engine import calculate_settlement` | Calculation |
| settlement-views (13) | app/settlements/routes.py | `from app.settlement_pdf import generate_settlement_pdf` | PDF generation |
| settlement-views (13) | app/settlements/routes.py | `from app.booking_lifecycle import advance_booking_state` | State transition |
| settlement-views (13) | app/settlements/routes.py | `from app.decorators import login_required, role_required` | Auth |
| search (15) | app/search/routes.py | `from app.db import get_db` | DB access |
| search (15) | app/search/routes.py | `from app.models import search_venues` | FTS5 search |
| search (15) | app/search/routes.py | `from app.decorators import login_required` | Auth |
| booking-lifecycle (9) | app/booking_lifecycle.py | `from app.notifications import create_notification` | Notifications |
| notification-views (17) | app/notification_views/routes.py | `from app.db import get_db` | DB access |
| notification-views (17) | app/notification_views/routes.py | `from app.notifications import get_notifications, get_unread_count, mark_notification_read, mark_all_read` | Notification CRUD |
| notification-views (17) | app/notification_views/routes.py | `from app.decorators import login_required` | Auth |
| analytics-venue (18) | app/analytics_venue/routes.py | `from app.db import get_db` | DB access |
| analytics-venue (18) | app/analytics_venue/routes.py | `from app.models import get_venue_revenue_by_month, get_venue_occupancy_by_room, get_venue_genre_distribution, get_venues_by_manager` | Analytics data |
| analytics-venue (18) | app/analytics_venue/routes.py | `from app.decorators import login_required, role_required` | Auth |
| analytics-musician (19) | app/analytics_musician/routes.py | `from app.db import get_db` | DB access |
| analytics-musician (19) | app/analytics_musician/routes.py | `from app.models import get_musician_earnings_by_month, get_musician_venues_played, get_musician_booking_success_rate` | Analytics data |
| analytics-musician (19) | app/analytics_musician/routes.py | `from app.decorators import login_required, role_required` | Auth |
| analytics-promoter (20) | app/analytics_promoter/routes.py | `from app.db import get_db` | DB access |
| analytics-promoter (20) | app/analytics_promoter/routes.py | `from app.models import get_promoter_revenue_by_month, get_promoter_settlements_by_venue, get_promoter_event_status_counts` | Analytics data |
| analytics-promoter (20) | app/analytics_promoter/routes.py | `from app.decorators import login_required, role_required` | Auth |
| dashboard-venue (21) | app/dashboard_venue/routes.py | `from app.db import get_db` | DB access |
| dashboard-venue (21) | app/dashboard_venue/routes.py | `from app.models import get_venue_upcoming_bookings, get_venue_pending_count, get_venues_by_manager` | Dashboard data |
| dashboard-venue (21) | app/dashboard_venue/routes.py | `from app.decorators import login_required, role_required` | Auth |
| dashboard-musician (22) | app/dashboard_musician/routes.py | `from app.db import get_db` | DB access |
| dashboard-musician (22) | app/dashboard_musician/routes.py | `from app.models import get_musician_upcoming_gigs, get_musician_pending_count` | Dashboard data |
| dashboard-musician (22) | app/dashboard_musician/routes.py | `from app.notifications import get_notifications` | Recent notifications |
| dashboard-musician (22) | app/dashboard_musician/routes.py | `from app.decorators import login_required, role_required` | Auth |
| dashboard-promoter (23) | app/dashboard_promoter/routes.py | `from app.db import get_db` | DB access |
| dashboard-promoter (23) | app/dashboard_promoter/routes.py | `from app.models import get_promoter_upcoming_events, get_promoter_settlement_status` | Dashboard data |
| dashboard-promoter (23) | app/dashboard_promoter/routes.py | `from app.decorators import login_required, role_required` | Auth |

### FTS5 Search Model Function (app/models.py)

```python
# Returns: list[sqlite3.Row] with venue columns
# Usage:
#   results = search_venues(conn, query)
def search_venues(conn, query):
    if not query or not query.strip():
        return get_all_venues(conn)
    return conn.execute(
        '''SELECT v.* FROM venues v
           JOIN venues_fts ON v.id = venues_fts.rowid
           WHERE venues_fts MATCH ?
           ORDER BY rank LIMIT 50''',
        (query,)
    ).fetchall()
```

---

## Coordinated Behaviors Table

All agents MUST follow these patterns exactly (FC5 prevention).

| Behavior | Pattern | Used By |
|----------|---------|---------|
| Success flash | `flash('<Resource> <action> successfully.', 'success')` | All POST routes that succeed |
| Error flash | `flash('<Error description>.', 'error')` | All validation failures |
| Warning flash | `flash('<Warning>.', 'warning')` | Rejection/cancellation |
| 404 on missing | `if resource is None: abort(404)` | All detail/edit/delete routes |
| 403 on wrong role | Via `@role_required(role)` decorator | All role-restricted routes |
| CSRF in forms | `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` | All POST forms |
| Money display | `{{ amount_cents\|dollars }}` | All templates showing money |
| Money form prefill | `value="{{ (amount_cents // 100) }}.{{ '%02d' % (amount_cents % 100) }}"` | Settlement form, ticket form |
| Money form parse | `int(round(float(request.form.get('field', '0')) * 100))` | Settlement create, ticket add/edit |
| Navbar notification badge | JS fetches `/api/notifications/unread-count` on page load | base.html (scaffold agent) |
| Date format | YYYY-MM-DD (stored and displayed) | All date fields |
| Time format | HH:MM (24-hour, stored and displayed) | All time fields |
| Form validation pattern | Strip + check empty + flash error + re-render form | All POST handlers |
| Redirect after POST | `return redirect(url_for('blueprint.route'))` | All successful POST handlers |
| State transition pattern | BEGIN IMMEDIATE -> advance_booking_state -> check -> commit/rollback | booking-manage (8), settlement-views (13) |

---

## Swarm Agent Assignment

### Agent 1: scaffold

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

### Agent 2: auth

**Files:**
- `venueconnect/app/auth/__init__.py`
- `venueconnect/app/auth/routes.py`
- `venueconnect/app/decorators.py`
- `venueconnect/app/templates/auth/login.html`
- `venueconnect/app/templates/auth/register.html`
- `venueconnect/app/templates/auth/profile.html`

### Agent 3: models

**Files:**
- `venueconnect/app/db.py`
- `venueconnect/app/models.py`
- `venueconnect/app/schema.sql`

### Agent 4: venue-crud

**Files:**
- `venueconnect/app/venues/__init__.py`
- `venueconnect/app/venues/routes.py`
- `venueconnect/app/templates/venues/list.html`
- `venueconnect/app/templates/venues/detail.html`
- `venueconnect/app/templates/venues/form.html`

### Agent 5: room-crud

**Files:**
- `venueconnect/app/rooms/__init__.py`
- `venueconnect/app/rooms/routes.py`
- `venueconnect/app/templates/rooms/list.html`
- `venueconnect/app/templates/rooms/detail.html`
- `venueconnect/app/templates/rooms/form.html`

### Agent 6: availability

**Files:**
- `venueconnect/app/availability/__init__.py`
- `venueconnect/app/availability/routes.py`
- `venueconnect/app/templates/availability/calendar.html`
- `venueconnect/app/templates/availability/form.html`

### Agent 7: booking-create

**Files:**
- `venueconnect/app/booking_create/__init__.py`
- `venueconnect/app/booking_create/routes.py`
- `venueconnect/app/templates/booking_create/browse.html`
- `venueconnect/app/templates/booking_create/room_availability.html`
- `venueconnect/app/templates/booking_create/request_form.html`
- `venueconnect/app/templates/booking_create/my_bookings.html`
- `venueconnect/app/templates/booking_create/detail.html`

### Agent 8: booking-manage

**Files:**
- `venueconnect/app/booking_manage/__init__.py`
- `venueconnect/app/booking_manage/routes.py`
- `venueconnect/app/templates/booking_manage/pending.html`
- `venueconnect/app/templates/booking_manage/detail.html`
- `venueconnect/app/templates/booking_manage/all_bookings.html`

### Agent 9: booking-lifecycle

**Files:**
- `venueconnect/app/booking_lifecycle.py`

### Agent 10: promoter-events

**Files:**
- `venueconnect/app/events/__init__.py`
- `venueconnect/app/events/routes.py`
- `venueconnect/app/templates/events/list.html`
- `venueconnect/app/templates/events/detail.html`
- `venueconnect/app/templates/events/form.html`

### Agent 11: ticket-tiers

**Files:**
- `venueconnect/app/tickets/__init__.py`
- `venueconnect/app/tickets/routes.py`
- `venueconnect/app/templates/tickets/manage.html`
- `venueconnect/app/templates/tickets/form.html`

### Agent 12: settlement-engine

**Files:**
- `venueconnect/app/settlement_engine.py`

### Agent 13: settlement-views

**Files:**
- `venueconnect/app/settlements/__init__.py`
- `venueconnect/app/settlements/routes.py`
- `venueconnect/app/templates/settlements/list.html`
- `venueconnect/app/templates/settlements/detail.html`
- `venueconnect/app/templates/settlements/form.html`

### Agent 14: settlement-pdf

**Files:**
- `venueconnect/app/settlement_pdf.py`

### Agent 15: search

**Files:**
- `venueconnect/app/search/__init__.py`
- `venueconnect/app/search/routes.py`
- `venueconnect/app/templates/search/results.html`

### Agent 16: notifications

**Files:**
- `venueconnect/app/notifications.py`

### Agent 17: notification-views

**Files:**
- `venueconnect/app/notification_views/__init__.py`
- `venueconnect/app/notification_views/routes.py`
- `venueconnect/app/templates/notifications/list.html`

### Agent 18: analytics-venue

**Files:**
- `venueconnect/app/analytics_venue/__init__.py`
- `venueconnect/app/analytics_venue/routes.py`
- `venueconnect/app/templates/analytics/venue.html`

### Agent 19: analytics-musician

**Files:**
- `venueconnect/app/analytics_musician/__init__.py`
- `venueconnect/app/analytics_musician/routes.py`
- `venueconnect/app/templates/analytics/musician.html`

### Agent 20: analytics-promoter

**Files:**
- `venueconnect/app/analytics_promoter/__init__.py`
- `venueconnect/app/analytics_promoter/routes.py`
- `venueconnect/app/templates/analytics/promoter.html`

### Agent 21: dashboard-venue

**Files:**
- `venueconnect/app/dashboard_venue/__init__.py`
- `venueconnect/app/dashboard_venue/routes.py`
- `venueconnect/app/templates/dashboard/venue.html`

### Agent 22: dashboard-musician

**Files:**
- `venueconnect/app/dashboard_musician/__init__.py`
- `venueconnect/app/dashboard_musician/routes.py`
- `venueconnect/app/templates/dashboard/musician.html`

### Agent 23: dashboard-promoter

**Files:**
- `venueconnect/app/dashboard_promoter/__init__.py`
- `venueconnect/app/dashboard_promoter/routes.py`
- `venueconnect/app/templates/dashboard/promoter.html`

### Agent 24: seed

**Files:**
- `venueconnect/seed.py`

### Agent 25: tests

**Files:**
- `venueconnect/test_smoke.py`

---

## Acceptance Tests (EARS Format)

### Happy Path

- WHEN a user registers with valid credentials and role 'musician' THE SYSTEM SHALL create the account and redirect to login
- WHEN a venue_manager creates a venue THE SYSTEM SHALL save it and display it in the venue list
- WHEN a venue_manager adds a room to their venue THE SYSTEM SHALL save the room with capacity and amenity flags
- WHEN a venue_manager adds an availability window THE SYSTEM SHALL display it in the room calendar
- WHEN a musician searches for venues by name THE SYSTEM SHALL return FTS5 results ranked by relevance
- WHEN a musician requests a booking for an available slot THE SYSTEM SHALL create a booking with state 'requested' and notify the venue_manager
- WHEN a venue_manager confirms a booking THE SYSTEM SHALL transition state to 'confirmed' and notify the musician
- WHEN a venue_manager records advance payment THE SYSTEM SHALL transition to 'advanced'
- WHEN a venue_manager marks a show as performed THE SYSTEM SHALL transition to 'performed'
- WHEN a venue_manager creates a settlement sheet THE SYSTEM SHALL calculate musician_payout, venue_share, promoter_fee, and tax using integer cents and transition to 'settled'
- WHEN a user downloads a settlement PDF THE SYSTEM SHALL return a ReportLab-generated PDF with financial breakdown
- WHEN a venue_manager marks a settlement as paid THE SYSTEM SHALL transition to 'paid'
- WHEN a promoter creates an event THE SYSTEM SHALL save it linked to a venue
- WHEN a user views their dashboard THE SYSTEM SHALL show role-appropriate content (upcoming bookings, pending counts, analytics previews)
- WHEN a user views analytics THE SYSTEM SHALL render Chart.js charts with data from aggregate SQL queries

### Error Cases

- WHEN a musician requests a booking for an already-booked slot THE SYSTEM SHALL reject with 'Time slot conflict' and not create the booking
- WHEN a user without venue_manager role tries to access /venues/new THE SYSTEM SHALL return 403
- WHEN a venue_manager tries to transition a booking to an invalid state THE SYSTEM SHALL return False from advance_booking_state and flash an error
- WHEN a settlement calculation has negative net door revenue THE SYSTEM SHALL clamp to 0
- WHEN a POST request is missing the CSRF token THE SYSTEM SHALL return 400 with 'CSRF token missing'

### Verification Commands

```bash
# Initialize and run
cd venueconnect
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
FLASK_APP=app FLASK_DEBUG=1 .venv/bin/flask init-db
.venv/bin/python seed.py
.venv/bin/python run.py

# Smoke tests
.venv/bin/python test_smoke.py
```

---

## Deepened Sections (added by /deepen-plan)

### Base Template (app/templates/base.html -- scaffold agent 1)

Every template extends this. The navbar must include role-based links and
notification badge. Chart.js CDN is included for analytics pages.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}VenueConnect{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    {% block head %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">VenueConnect</a>
            {% if session.get('user_id') %}
            <div class="navbar-nav ms-auto">
                {% if session.get('role') == 'venue_manager' %}
                <a class="nav-link" href="{{ url_for('dashboard_venue.index') }}">Dashboard</a>
                <a class="nav-link" href="{{ url_for('venues.list') }}">My Venues</a>
                <a class="nav-link" href="{{ url_for('booking_manage.pending') }}">Bookings</a>
                <a class="nav-link" href="{{ url_for('settlements.list') }}">Settlements</a>
                <a class="nav-link" href="{{ url_for('analytics_venue.index') }}">Analytics</a>
                {% elif session.get('role') == 'musician' %}
                <a class="nav-link" href="{{ url_for('dashboard_musician.index') }}">Dashboard</a>
                <a class="nav-link" href="{{ url_for('search.index') }}">Find Venues</a>
                <a class="nav-link" href="{{ url_for('booking_create.my_bookings') }}">My Bookings</a>
                <a class="nav-link" href="{{ url_for('analytics_musician.index') }}">Analytics</a>
                {% elif session.get('role') == 'promoter' %}
                <a class="nav-link" href="{{ url_for('dashboard_promoter.index') }}">Dashboard</a>
                <a class="nav-link" href="{{ url_for('events.list') }}">My Events</a>
                <a class="nav-link" href="{{ url_for('settlements.list') }}">Settlements</a>
                <a class="nav-link" href="{{ url_for('analytics_promoter.index') }}">Analytics</a>
                {% endif %}
                <a class="nav-link position-relative" href="{{ url_for('notification_views.list') }}">
                    Notifications
                    <span class="badge bg-danger rounded-pill d-none" id="notif-badge">0</span>
                </a>
                <a class="nav-link" href="{{ url_for('auth.profile') }}">Profile</a>
                <a class="nav-link" href="{{ url_for('auth.logout') }}">Logout</a>
            </div>
            {% else %}
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('auth.login') }}">Login</a>
                <a class="nav-link" href="{{ url_for('auth.register') }}">Register</a>
            </div>
            {% endif %}
        </div>
    </nav>

    <main class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        {% for category, message in messages %}
        <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        {% endfor %}
        {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </main>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    {% block scripts %}{% endblock %}
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>
```

### Notification Badge JS (app/static/js/app.js -- scaffold agent 1)

```javascript
// Poll notification count on page load
document.addEventListener('DOMContentLoaded', function() {
    var badge = document.getElementById('notif-badge');
    if (!badge) return;
    fetch('/notifications/unread-count')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.classList.remove('d-none');
            }
        })
        .catch(function() { /* silently fail */ });
});
```

### Blueprint __init__.py Pattern (all blueprint agents)

Every blueprint __init__.py is an empty file. The blueprint is defined in routes.py.

```python
# app/<blueprint_name>/__init__.py
# Empty file -- blueprint defined in routes.py
```

```python
# app/<blueprint_name>/routes.py (example for venues)
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from app.db import get_db
from app.decorators import login_required, role_required
from app.models import (create_venue, get_venue, get_venues_by_manager,
                         update_venue, delete_venue, get_rooms_by_venue)

venues_bp = Blueprint('venues', __name__)

@venues_bp.route('/')
@login_required
@role_required('venue_manager')
def list():
    conn = get_db()
    venues = get_venues_by_manager(conn, g.user['id'])
    return render_template('venues/list.html', venues=venues)
```

### Chart.js Data Format (analytics agents 18-20)

All analytics templates use the same Chart.js pattern. Data is passed from
Python via `{{ data|tojson }}` Jinja filter.

```html
<!-- analytics/venue.html example (agent 18) -->
{% extends "base.html" %}
{% block title %}Venue Analytics{% endblock %}
{% block head %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
{% endblock %}

{% block content %}
<h1>Venue Analytics: {{ venue['name'] }}</h1>
<div class="row">
    <div class="col-md-6 mb-4">
        <div class="card"><div class="card-body">
            <h5 class="card-title">Revenue by Month</h5>
            <canvas id="revenueChart"></canvas>
        </div></div>
    </div>
    <div class="col-md-6 mb-4">
        <div class="card"><div class="card-body">
            <h5 class="card-title">Genre Distribution</h5>
            <canvas id="genreChart"></canvas>
        </div></div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
// Bar chart -- revenue by month
var revenueData = {{ revenue_data|tojson }};
new Chart(document.getElementById('revenueChart'), {
    type: 'bar',
    data: {
        labels: revenueData.map(function(r) { return r.month; }),
        datasets: [{
            label: 'Revenue',
            data: revenueData.map(function(r) { return r.total_cents / 100; }),
            backgroundColor: 'rgba(54, 162, 235, 0.7)'
        }]
    },
    options: { responsive: true, scales: { y: { beginAtZero: true,
        ticks: { callback: function(v) { return '$' + v.toLocaleString(); } }
    }}}
});

// Doughnut chart -- genre distribution
var genreData = {{ genre_data|tojson }};
new Chart(document.getElementById('genreChart'), {
    type: 'doughnut',
    data: {
        labels: genreData.map(function(r) { return r.genre; }),
        datasets: [{
            data: genreData.map(function(r) { return r.count; }),
            backgroundColor: ['#FF6384','#36A2EB','#FFCE56','#4BC0C0','#9966FF',
                              '#FF9F40','#C9CBCF','#7BC67E','#E7E9ED','#FFB1C1']
        }]
    },
    options: { responsive: true }
});
</script>
{% endblock %}
```

**Analytics route data format** (all analytics agents must return data as list of dicts):
```python
# Convert sqlite3.Row to list of dicts for tojson
revenue_data = [dict(r) for r in get_venue_revenue_by_month(conn, venue_id)]
```

### Seed Data Script (venueconnect/seed.py -- seed agent 24)

```python
"""Seed script -- run with: .venv/bin/python seed.py"""
import os
import sys
os.environ.setdefault('SECRET_KEY', 'seed-dev-key')
sys.path.insert(0, os.path.dirname(__file__))

from werkzeug.security import generate_password_hash
from app import create_app
from app.db import get_db, init_db

app = create_app()

with app.app_context():
    init_db()
    conn = get_db()

    # Demo users (password: 'password123' for all)
    pw = generate_password_hash('password123')
    conn.execute("INSERT OR IGNORE INTO users (username, email, password_hash, role, display_name, bio, genre_tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('bluenote_mgr', 'mgr@bluenote.com', pw, 'venue_manager', 'Blue Note Manager', 'Managing the best jazz venue in town', 'jazz'))
    conn.execute("INSERT OR IGNORE INTO users (username, email, password_hash, role, display_name, bio, genre_tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('jazz_trio', 'trio@music.com', pw, 'musician', 'The Jazz Trio', 'Three-piece jazz ensemble', 'jazz,fusion'))
    conn.execute("INSERT OR IGNORE INTO users (username, email, password_hash, role, display_name, bio, genre_tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('rock_band', 'rock@music.com', pw, 'musician', 'The Amplifiers', 'High-energy rock band', 'rock,alternative'))
    conn.execute("INSERT OR IGNORE INTO users (username, email, password_hash, role, display_name, bio, genre_tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('city_nights', 'promo@citynights.com', pw, 'promoter', 'City Nights Promotions', 'Premier live music promoter', ''))
    conn.commit()

    # Get user IDs
    mgr = conn.execute("SELECT id FROM users WHERE username='bluenote_mgr'").fetchone()
    trio = conn.execute("SELECT id FROM users WHERE username='jazz_trio'").fetchone()
    rock = conn.execute("SELECT id FROM users WHERE username='rock_band'").fetchone()
    promo = conn.execute("SELECT id FROM users WHERE username='city_nights'").fetchone()

    # Venue + rooms
    conn.execute("INSERT OR IGNORE INTO venues (id, user_id, name, location, description, capacity, genre_tags) VALUES (1, ?, 'The Blue Note', '123 Jazz St, New York', 'Premier jazz venue since 1981', 300, 'jazz,blues,fusion')", (mgr['id'],))
    conn.execute("INSERT OR IGNORE INTO rooms (id, venue_id, name, capacity, description, has_pa, has_lighting) VALUES (1, 1, 'Main Stage', 200, 'Full concert stage with grand piano', 1, 1)")
    conn.execute("INSERT OR IGNORE INTO rooms (id, venue_id, name, capacity, description, has_pa, has_lighting) VALUES (2, 1, 'Lounge', 50, 'Intimate lounge setting', 1, 0)")

    # Availability windows (Fri-Sat 7pm-2am for Main Stage)
    conn.execute("INSERT OR IGNORE INTO availability_windows (id, room_id, day_of_week, start_time, end_time) VALUES (1, 1, 4, '19:00', '02:00')")
    conn.execute("INSERT OR IGNORE INTO availability_windows (id, room_id, day_of_week, start_time, end_time) VALUES (2, 1, 5, '19:00', '02:00')")
    conn.execute("INSERT OR IGNORE INTO availability_windows (id, room_id, day_of_week, start_time, end_time) VALUES (3, 2, 3, '20:00', '00:00')")

    # Bookings in various states
    conn.execute("""INSERT OR IGNORE INTO bookings (id, room_id, musician_user_id, event_name, event_date,
        start_time, end_time, state, deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes)
        VALUES (1, 1, ?, 'Jazz Night', '2026-06-06', '20:00', '23:00', 'confirmed', 'door_split', 0, 70, 0, 8, 'Looking forward to it')""",
        (trio['id'],))
    conn.execute("""INSERT OR IGNORE INTO bookings (id, room_id, musician_user_id, event_name, event_date,
        start_time, end_time, state, deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes)
        VALUES (2, 1, ?, 'Rock the House', '2026-05-30', '21:00', '01:00', 'performed', 'hybrid', 50000, 70, 10, 8, '')""",
        (rock['id'],))
    conn.execute("""INSERT OR IGNORE INTO bookings (id, room_id, musician_user_id, event_name, event_date,
        start_time, end_time, state, deal_type, guarantee_cents, door_split_pct, promoter_fee_pct, tax_pct, notes)
        VALUES (3, 2, ?, 'Lounge Sessions', '2026-06-12', '20:00', '23:00', 'requested', 'guarantee', 30000, 0, 0, 8, 'Acoustic set')""",
        (trio['id'],))

    # Booking history
    conn.execute("INSERT OR IGNORE INTO booking_history (booking_id, from_state, to_state, actor_user_id, notes, created_at) VALUES (1, 'requested', 'confirmed', ?, '', datetime('now'))", (mgr['id'],))

    # Ticket tiers for the performed booking
    conn.execute("INSERT OR IGNORE INTO ticket_tiers (id, booking_id, name, price_cents, quantity, sold_count) VALUES (1, 2, 'General Admission', 2500, 150, 120)")
    conn.execute("INSERT OR IGNORE INTO ticket_tiers (id, booking_id, name, price_cents, quantity, sold_count) VALUES (2, 2, 'VIP', 5000, 30, 25)")

    # Settlement for the performed booking
    conn.execute("""INSERT OR IGNORE INTO settlements (id, booking_id, door_revenue_cents, expenses_cents,
        musician_payout_cents, venue_share_cents, promoter_fee_cents, tax_amount_cents,
        status, created_by_user_id)
        VALUES (1, 2, 425000, 15000, 287000, 83000, 42500, 34000, 'draft', ?)""",
        (mgr['id'],))

    # Event for promoter
    conn.execute("INSERT OR IGNORE INTO events (id, promoter_user_id, venue_id, name, description, event_date) VALUES (1, ?, 1, 'Summer Jazz Festival', 'Annual jazz celebration', '2026-07-15')", (promo['id'],))

    # Notifications
    conn.execute("INSERT OR IGNORE INTO notifications (user_id, message, link, is_read) VALUES (?, 'New booking request for Jazz Night', '/manage/bookings/1', 0)", (mgr['id'],))
    conn.execute("INSERT OR IGNORE INTO notifications (user_id, message, link, is_read) VALUES (?, 'Your booking \"Jazz Night\" has been confirmed!', '/bookings/1', 0)", (trio['id'],))
    conn.execute("INSERT OR IGNORE INTO notifications (user_id, message, link, is_read) VALUES (?, 'Settlement sheet ready for \"Rock the House\"', '/settlements/1', 0)", (rock['id'],))

    conn.commit()
    print("Seed data created successfully.")
    print("Demo accounts: bluenote_mgr / jazz_trio / rock_band / city_nights (password: password123)")
```

### Smoke Test Script (venueconnect/test_smoke.py -- tests agent 25)

```python
"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import sys
os.environ.setdefault('SECRET_KEY', 'test-smoke-key')
os.environ.setdefault('FLASK_DEBUG', '1')
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.db import init_db

app = create_app()
client = app.test_client()

with app.app_context():
    init_db()

passed = 0
failed = 0

def check(name, response, expected_status):
    global passed, failed
    if response.status_code == expected_status:
        passed += 1
        print(f"PASS: {name} ({response.status_code})")
    else:
        failed += 1
        print(f"FAIL: {name} -- expected {expected_status}, got {response.status_code}")

# Health check
check("GET /health", client.get("/health"), 200)

# Auth pages (unauthenticated)
check("GET /auth/login", client.get("/auth/login"), 200)
check("GET /auth/register", client.get("/auth/register"), 200)

# Redirect when not logged in
check("GET / redirects", client.get("/", follow_redirects=False), 302)

# Register a test user
r = client.post("/auth/register", data={
    "username": "testuser",
    "email": "test@test.com",
    "password": "TestPass123!",
    "confirm_password": "TestPass123!",
    "role": "venue_manager",
    "display_name": "Test User",
    "csrf_token": "skip"  # CSRF exempt in test mode or get token first
}, follow_redirects=False)
# May be 302 (redirect on success) or 200 (form re-render on error)
print(f"INFO: Register response: {r.status_code}")

# Login
r = client.post("/auth/login", data={
    "username": "testuser",
    "password": "TestPass123!",
    "csrf_token": "skip"
}, follow_redirects=False)
print(f"INFO: Login response: {r.status_code}")

# Dashboard (should work after login)
check("GET /dashboard/venue", client.get("/dashboard/venue"), 200)

# Venue CRUD
check("GET /venues/", client.get("/venues/"), 200)
check("GET /venues/new", client.get("/venues/new"), 200)

# Search
check("GET /search/", client.get("/search/"), 200)
check("GET /search/?q=jazz", client.get("/search/?q=jazz"), 200)

# Notifications
check("GET /notifications/", client.get("/notifications/"), 200)
check("GET /api/notifications/unread-count", client.get("/api/notifications/unread-count"), 200)

# Analytics
check("GET /analytics/venue", client.get("/analytics/venue"), 200)

# Settlements
check("GET /settlements/", client.get("/settlements/"), 200)

# Logout
check("GET /auth/logout redirects", client.get("/auth/logout", follow_redirects=False), 302)

# Role protection (musician trying venue routes)
client.post("/auth/register", data={
    "username": "testmusician",
    "email": "musician@test.com",
    "password": "TestPass123!",
    "confirm_password": "TestPass123!",
    "role": "musician",
    "display_name": "Test Musician",
    "csrf_token": "skip"
}, follow_redirects=True)
client.post("/auth/login", data={
    "username": "testmusician",
    "password": "TestPass123!",
    "csrf_token": "skip"
}, follow_redirects=True)
check("Musician blocked from /venues/new", client.get("/venues/new"), 403)
check("GET /bookings/browse", client.get("/bookings/browse"), 200)
check("GET /bookings/mine", client.get("/bookings/mine"), 200)
check("GET /dashboard/musician", client.get("/dashboard/musician"), 200)

print(f"\n{'='*40}")
print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
if failed > 0:
    print("SOME SMOKE TESTS FAILED")
    sys.exit(1)
else:
    print("ALL SMOKE TESTS PASSED")
```

**IMPORTANT for tests agent:** CSRF will block POST requests in smoke tests.
The scaffold agent must add this to create_app:
```python
if app.debug or app.testing:
    app.config['WTF_CSRF_ENABLED'] = False
```
And the smoke test sets FLASK_DEBUG=1 via os.environ.setdefault.

### Authorization Matrix

Which roles can access which blueprints. Every route agent MUST check this.

| Blueprint | venue_manager | musician | promoter |
|-----------|:---:|:---:|:---:|
| auth (login/register/profile) | Y | Y | Y |
| venues (CRUD) | Y (own only) | - | - |
| rooms (CRUD) | Y (own venue) | - | - |
| availability (CRUD) | Y (own room) | - | - |
| booking_create (browse/request) | - | Y | - |
| booking_manage (approve/reject) | Y (own venue) | - | - |
| events (CRUD) | - | - | Y |
| tickets (CRUD) | Y (own booking) | - | Y (own event) |
| settlements (create/approve) | Y (own venue) | view own | view own |
| search | Y | Y | Y |
| notifications | Y | Y | Y |
| analytics (per role) | Y (own) | Y (own) | Y (own) |
| dashboard (per role) | Y (own) | Y (own) | Y (own) |

### run.py (scaffold agent 1)

```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

### .gitignore (scaffold agent 1)

```
__pycache__/
*.pyc
instance/
.venv/
*.db
test_smoke.py
.env
```

---

## Feed-Forward

- **Hardest decision:** Splitting the booking domain across 3 agents (booking-create, booking-manage, booking-lifecycle). The state machine in agent 9 is consumed by agents 8 and 13, creating the highest-risk cross-boundary surface. Mitigated by prescribing the exact call pattern in the spec and embedding it in each consuming agent's brief.

- **Rejected alternatives:** (1) Single booking agent -- too many files/routes for one agent. (2) WeasyPrint for PDF -- system deps. (3) Many-to-many role table -- over-engineered. (4) WebSocket notifications -- unnecessary. (5) External `transitions` library.

- **Least confident:** Calendar conflict detection atomicity. The BEGIN IMMEDIATE + check_room_available + create_booking must all happen in one transaction. If any agent adds a commit() inside check_room_available or create_booking, the TOCTOU race opens. The spec marks both functions as "does NOT commit" but this is the pattern most likely to be violated because it's counterintuitive (why wouldn't a function that creates a row commit?).

---

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-05-19-venueconnect-brainstorm.md](docs/brainstorms/2026-05-19-venueconnect-brainstorm.md)
- **Spec template:** [docs/templates/shared-spec-flask.md](docs/templates/shared-spec-flask.md)
- **Prior art:** client-music-planner (run 048, 20 agents), solopreneur-command-center (run 047, 16 agents)
- **Agent pitfalls:** FC1-FC34, especially FC3 (dead wiring), FC7 (prefix doubling), FC9 (form field mismatch), FC29 (transaction boundaries), FC31 (cross-flow data integrity)
