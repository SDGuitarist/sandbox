---
title: "GymFlow -- Gym/Fitness Center Manager"
date: 2026-05-21
brainstorm: docs/brainstorms/2026-05-21-gym-manager-brainstorm.md
swarm: true
agents: 26
feed_forward:
  risk: "Attendance capacity check with BEGIN IMMEDIATE -- transaction boundary between attendance_models and attendance_routes agents (FC29 territory)"
  verify_first: true
---

# Shared Interface Spec -- GymFlow

Single-location gym management system. Admin-only (one user). Flask + SQLite +
Jinja2 + Bootstrap 5 (CDN). 26-agent model/route vertical split.

## App Configuration

```python
# gymflow/app/__init__.py
import os
from flask import Flask
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    if not app.debug and app.config['SECRET_KEY'] == 'dev-fallback-key':
        raise RuntimeError('SECRET_KEY must be set in production')
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
    from app.blueprints.trainers.routes import bp as trainers_bp
    from app.blueprints.membership_types.routes import bp as membership_types_bp
    from app.blueprints.class_types.routes import bp as class_types_bp
    from app.blueprints.schedules.routes import bp as schedules_bp
    from app.blueprints.attendance.routes import bp as attendance_bp
    from app.blueprints.equipment.routes import bp as equipment_bp
    from app.blueprints.maintenance.routes import bp as maintenance_bp
    from app.blueprints.billing.routes import bp as billing_bp
    from app.blueprints.payments.routes import bp as payments_bp
    from app.blueprints.assessments.routes import bp as assessments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(members_bp, url_prefix='/members')
    app.register_blueprint(trainers_bp, url_prefix='/trainers')
    app.register_blueprint(membership_types_bp, url_prefix='/membership-types')
    app.register_blueprint(class_types_bp, url_prefix='/class-types')
    app.register_blueprint(schedules_bp, url_prefix='/schedules')
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    app.register_blueprint(equipment_bp, url_prefix='/equipment')
    app.register_blueprint(maintenance_bp, url_prefix='/maintenance')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(payments_bp, url_prefix='/payments')
    app.register_blueprint(assessments_bp, url_prefix='/assessments')

    return app
```

**Requirements (requirements.txt):**
```
flask>=3.0
flask-wtf>=1.2
```

## Database Connection

```python
# gymflow/app/db.py
import sqlite3
import os
from flask import g

DATABASE = os.environ.get('DATABASE_PATH', 'gymflow.db')

def get_db():
    """Get database connection. Returns a plain connection (NOT a context manager).

    Usage:
        conn = get_db()
        members = get_all_members(conn)
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

## Authentication

```python
# gymflow/app/auth.py
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

**Rule:** Every route except `auth.login_page` and `auth.login` MUST use
`@login_required`. The `GET /health` route is exempt.

## Jinja Filters

```python
# gymflow/app/filters.py
from datetime import datetime

def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert cents to dollar display: 1500 -> '$15.00'"""
        if cents is None:
            return '$0.00'
        return f'${cents / 100:.2f}'

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

## Database Schema

```sql
-- gymflow/schema.sql

CREATE TABLE IF NOT EXISTS membership_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    duration_months INTEGER NOT NULL,
    price_cents INTEGER NOT NULL,
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
    emergency_contact TEXT NOT NULL DEFAULT '',
    membership_type_id INTEGER REFERENCES membership_types(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'frozen', 'cancelled')),
    join_date TEXT NOT NULL DEFAULT (date('now')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_members_membership_type_id ON members(membership_type_id);
CREATE INDEX IF NOT EXISTS idx_members_status ON members(status);

CREATE TABLE IF NOT EXISTS trainers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL DEFAULT '',
    specializations TEXT NOT NULL DEFAULT '',
    bio TEXT NOT NULL DEFAULT '',
    hire_date TEXT NOT NULL DEFAULT (date('now')),
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS class_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    default_capacity INTEGER NOT NULL DEFAULT 20,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS class_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_type_id INTEGER NOT NULL REFERENCES class_types(id) ON DELETE RESTRICT,
    trainer_id INTEGER REFERENCES trainers(id) ON DELETE SET NULL,
    session_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    room TEXT NOT NULL DEFAULT '',
    capacity INTEGER NOT NULL DEFAULT 20,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_class_schedules_class_type_id ON class_schedules(class_type_id);
CREATE INDEX IF NOT EXISTS idx_class_schedules_trainer_id ON class_schedules(trainer_id);
CREATE INDEX IF NOT EXISTS idx_class_schedules_session_date ON class_schedules(session_date);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    class_schedule_id INTEGER REFERENCES class_schedules(id) ON DELETE RESTRICT,
    check_in_time TEXT NOT NULL DEFAULT (datetime('now')),
    check_out_time TEXT,
    attendance_type TEXT NOT NULL DEFAULT 'class' CHECK(attendance_type IN ('class', 'open_gym')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_attendance_member_id ON attendance(member_id);
CREATE INDEX IF NOT EXISTS idx_attendance_class_schedule_id ON attendance(class_schedule_id);

CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    serial_number TEXT NOT NULL DEFAULT '',
    purchase_date TEXT,
    purchase_price_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'in_use', 'maintenance', 'retired')),
    location TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS maintenance_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id INTEGER NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
    description TEXT NOT NULL,
    maintenance_date TEXT NOT NULL DEFAULT (date('now')),
    cost_cents INTEGER NOT NULL DEFAULT 0,
    performed_by TEXT NOT NULL DEFAULT '',
    next_due_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_maintenance_log_equipment_id ON maintenance_log(equipment_id);

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

CREATE TABLE IF NOT EXISTS fitness_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
    trainer_id INTEGER REFERENCES trainers(id) ON DELETE SET NULL,
    assessment_date TEXT NOT NULL DEFAULT (date('now')),
    weight_kg REAL,
    height_cm REAL,
    body_fat_pct REAL,
    bmi REAL,
    resting_heart_rate INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_fitness_assessments_member_id ON fitness_assessments(member_id);
CREATE INDEX IF NOT EXISTS idx_fitness_assessments_trainer_id ON fitness_assessments(trainer_id);
```

## Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| membership_types | models/membership_type.py | member_routes (dropdown) |
| members | models/member.py | attendance_routes (dropdown), billing_routes (dropdown), assessment_routes (dropdown), dashboard_routes (stats) |
| trainers | models/trainer.py | schedule_routes (dropdown), assessment_routes (dropdown) |
| class_types | models/class_type.py | schedule_routes (dropdown) |
| class_schedules | models/schedule.py | attendance_routes (dropdown), dashboard_routes (today) |
| attendance | models/attendance.py | schedule_routes (count), dashboard_routes (recent) |
| equipment | models/equipment.py | maintenance_routes (dropdown), dashboard_routes (needs maintenance) |
| maintenance_log | models/maintenance.py | equipment_routes (history display) |
| invoices | models/invoice.py | payment_routes (dropdown), dashboard_routes (revenue) |
| payments | models/payment.py | billing_routes (payment history on detail) |
| fitness_assessments | models/assessment.py | member_routes (latest assessment display) |

## Model Functions

### models/member.py (member_models agent)

```python
import sqlite3

def create_member(conn: sqlite3.Connection, name: str, email: str,
                  phone: str, emergency_contact: str,
                  membership_type_id: int | None, notes: str) -> int:
    """Create a new member. Returns the new member's ID.
    Usage:
        member_id = create_member(conn, 'John Doe', 'john@example.com',
                                  '555-0100', 'Jane Doe 555-0101', 1, '')
        return redirect(url_for('members.detail', member_id=member_id))
    Commits: yes (conn.commit())
    """

def get_member(conn: sqlite3.Connection, member_id: int) -> sqlite3.Row | None:
    """Get member by ID with membership type name joined.
    Returns Row with columns: id, name, email, phone, emergency_contact,
    membership_type_id, status, join_date, notes, created_at, updated_at,
    membership_type_name (from JOIN, may be NULL).
    Usage:
        member = get_member(conn, member_id)
        if member is None:
            abort(404)
    """

def get_all_members(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all members ordered by name. Includes membership_type_name JOIN."""

def get_members_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    """Get members filtered by status ('active', 'frozen', 'cancelled')."""

def update_member(conn: sqlite3.Connection, member_id: int, name: str,
                  email: str, phone: str, emergency_contact: str,
                  membership_type_id: int | None, status: str,
                  notes: str) -> None:
    """Update member fields. Commits: yes."""

def delete_member(conn: sqlite3.Connection, member_id: int) -> None:
    """Delete member. Commits: yes.
    Raises sqlite3.IntegrityError if member has attendance/invoices/assessments.
    """

def count_active_members(conn: sqlite3.Connection) -> int:
    """Count members with status='active'. Returns int.
    Usage:
        active_count = count_active_members(conn)
        # active_count is an int, NOT a Row
    """

def count_new_members_this_month(conn: sqlite3.Connection) -> int:
    """Count members with join_date in current month. Returns int."""

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

### models/trainer.py (trainer_models agent)

```python
import sqlite3

def create_trainer(conn: sqlite3.Connection, name: str, email: str,
                   phone: str, specializations: str, bio: str) -> int:
    """Create trainer. Returns new trainer ID.
    Usage:
        trainer_id = create_trainer(conn, 'Jane Smith', 'jane@gym.com',
                                    '555-0200', 'Yoga, Pilates', 'Bio text')
        return redirect(url_for('trainers.detail', trainer_id=trainer_id))
    Commits: yes
    """

def get_trainer(conn: sqlite3.Connection, trainer_id: int) -> sqlite3.Row | None:
    """Get trainer by ID. Returns Row or None."""

def get_all_trainers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all trainers ordered by name."""

def get_active_trainers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get trainers with status='active'."""

def update_trainer(conn: sqlite3.Connection, trainer_id: int, name: str,
                   email: str, phone: str, specializations: str,
                   bio: str, status: str) -> None:
    """Update trainer fields. Commits: yes."""

def delete_trainer(conn: sqlite3.Connection, trainer_id: int) -> None:
    """Delete trainer. Commits: yes.
    FK constraints are SET NULL -- trainer_id on schedules/assessments
    becomes NULL automatically. No IntegrityError raised.
    """
```

### models/membership_type.py (membership_type_models agent)

```python
import sqlite3

def create_membership_type(conn: sqlite3.Connection, name: str,
                           duration_months: int, price_cents: int,
                           description: str) -> int:
    """Create membership type. Returns new type ID.
    Usage:
        type_id = create_membership_type(conn, 'Monthly', 1, 4999, 'Basic monthly')
        return redirect(url_for('membership_types.list_types'))
    Commits: yes
    """

def get_membership_type(conn: sqlite3.Connection, type_id: int) -> sqlite3.Row | None:
    """Get membership type by ID."""

def get_all_membership_types(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all membership types ordered by name."""

def get_active_membership_types(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get membership types with is_active=1."""

def update_membership_type(conn: sqlite3.Connection, type_id: int, name: str,
                           duration_months: int, price_cents: int,
                           description: str, is_active: int) -> None:
    """Update membership type. Commits: yes."""

def delete_membership_type(conn: sqlite3.Connection, type_id: int) -> None:
    """Delete membership type. Commits: yes.
    FK constraint is SET NULL -- membership_type_id on members becomes
    NULL automatically. No IntegrityError raised.
    """
```

### models/class_type.py (class_type_models agent)

```python
import sqlite3

def create_class_type(conn: sqlite3.Connection, name: str,
                      description: str, duration_minutes: int,
                      default_capacity: int) -> int:
    """Create class type. Returns new type ID.
    Usage:
        type_id = create_class_type(conn, 'Yoga Basics', 'Beginner yoga', 60, 20)
        return redirect(url_for('class_types.list_types'))
    Commits: yes
    """

def get_class_type(conn: sqlite3.Connection, type_id: int) -> sqlite3.Row | None:
    """Get class type by ID."""

def get_all_class_types(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all class types ordered by name."""

def update_class_type(conn: sqlite3.Connection, type_id: int, name: str,
                      description: str, duration_minutes: int,
                      default_capacity: int) -> None:
    """Update class type. Commits: yes."""

def delete_class_type(conn: sqlite3.Connection, type_id: int) -> None:
    """Delete class type. Commits: yes.
    Raises sqlite3.IntegrityError if schedules reference this type.
    """
```

### models/schedule.py (schedule_models agent)

```python
import sqlite3

def create_schedule(conn: sqlite3.Connection, class_type_id: int,
                    trainer_id: int | None, session_date: str,
                    start_time: str, end_time: str, room: str,
                    capacity: int, notes: str) -> int:
    """Create class schedule. Returns new schedule ID.
    Usage:
        schedule_id = create_schedule(conn, 1, 2, '2026-05-22', '09:00',
                                      '10:00', 'Studio A', 20, '')
        return redirect(url_for('schedules.list_schedules'))
    Commits: yes
    """

def get_schedule(conn: sqlite3.Connection, schedule_id: int) -> sqlite3.Row | None:
    """Get schedule by ID with class_type_name and trainer_name joined.
    Returns Row with: id, class_type_id, trainer_id, session_date, start_time,
    end_time, room, capacity, notes, created_at, updated_at,
    class_type_name, trainer_name (may be NULL).
    """

def get_schedules_by_date(conn: sqlite3.Connection, date: str) -> list[sqlite3.Row]:
    """Get schedules for a specific date. Includes class_type_name, trainer_name.
    Ordered by start_time."""

def get_schedules_by_date_range(conn: sqlite3.Connection, start_date: str,
                                 end_date: str) -> list[sqlite3.Row]:
    """Get schedules between start_date and end_date (inclusive).
    Ordered by session_date, start_time."""

def get_schedules_by_trainer(conn: sqlite3.Connection, trainer_id: int) -> list[sqlite3.Row]:
    """Get schedules for a specific trainer. Includes class_type_name."""

def update_schedule(conn: sqlite3.Connection, schedule_id: int,
                    class_type_id: int, trainer_id: int | None,
                    session_date: str, start_time: str, end_time: str,
                    room: str, capacity: int, notes: str) -> None:
    """Update schedule. Commits: yes."""

def delete_schedule(conn: sqlite3.Connection, schedule_id: int) -> None:
    """Delete schedule. Commits: yes.
    Raises sqlite3.IntegrityError if attendance records exist.
    """

def copy_week_schedules(conn: sqlite3.Connection, source_date: str,
                        target_date: str) -> int:
    """Copy all schedules from source week (Mon-Sun) to target week.
    source_date and target_date are any dates within their respective weeks.
    Returns count of schedules created.
    Usage:
        count = copy_week_schedules(conn, '2026-05-18', '2026-05-25')
        flash(f'Copied {count} classes to next week.', 'success')
    Commits: yes
    """

def get_schedule_attendance_count(conn: sqlite3.Connection,
                                   schedule_id: int) -> int:
    """Count attendance records for a schedule. Returns int.
    Usage:
        count = get_schedule_attendance_count(conn, schedule_id)
        # count is an int, NOT a Row
    """
```

### models/attendance.py (attendance_models agent)

```python
import sqlite3

def check_in_class(conn: sqlite3.Connection, member_id: int,
                   class_schedule_id: int) -> int:
    """Check in member to a class. Returns new attendance ID.
    Uses BEGIN IMMEDIATE for atomic capacity check.
    Raises ValueError if class is full.
    Usage:
        try:
            attendance_id = check_in_class(conn, member_id, schedule_id)
            flash('Checked in successfully.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
    Commits: yes (via BEGIN IMMEDIATE ... COMMIT)

    Implementation MUST:
    1. conn.execute('BEGIN IMMEDIATE')
    2. SELECT COUNT(*) FROM attendance WHERE class_schedule_id = ?
    3. SELECT capacity FROM class_schedules WHERE id = ?
    4. If count >= capacity: conn.execute('ROLLBACK'), raise ValueError('Class is full')
    5. INSERT INTO attendance
    6. conn.execute('COMMIT')
    """

def check_in_open_gym(conn: sqlite3.Connection, member_id: int) -> int:
    """Check in member for open gym (no class). Returns new attendance ID.
    Usage:
        attendance_id = check_in_open_gym(conn, member_id)
    Commits: yes
    """

def check_out(conn: sqlite3.Connection, attendance_id: int) -> None:
    """Record check-out time. Commits: yes."""

def get_attendance(conn: sqlite3.Connection, attendance_id: int) -> sqlite3.Row | None:
    """Get attendance record by ID with member_name joined."""

def get_attendance_by_schedule(conn: sqlite3.Connection,
                                schedule_id: int) -> list[sqlite3.Row]:
    """Get all attendance for a class schedule. Includes member_name."""

def get_attendance_by_member(conn: sqlite3.Connection,
                              member_id: int) -> list[sqlite3.Row]:
    """Get all attendance for a member. Includes class_type_name (may be NULL for open_gym)."""

def get_recent_checkins(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    """Get most recent check-ins. Includes member_name, class_type_name.
    Usage:
        recent = get_recent_checkins(conn, 10)
    """

def get_today_checkins(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get today's check-ins. Includes member_name."""

def delete_attendance(conn: sqlite3.Connection, attendance_id: int) -> None:
    """Delete attendance record. Commits: yes."""
```

### models/equipment.py (equipment_models agent)

```python
import sqlite3

def create_equipment(conn: sqlite3.Connection, name: str, category: str,
                     serial_number: str, purchase_date: str | None,
                     purchase_price_cents: int, status: str,
                     location: str, notes: str) -> int:
    """Create equipment. Returns new equipment ID.
    Usage:
        equip_id = create_equipment(conn, 'Treadmill X500', 'Cardio',
                                    'SN-12345', '2026-01-15', 150000,
                                    'available', 'Main Floor', '')
        return redirect(url_for('equipment.detail', equipment_id=equip_id))
    Commits: yes
    """

def get_equipment(conn: sqlite3.Connection, equipment_id: int) -> sqlite3.Row | None:
    """Get equipment by ID."""

def get_all_equipment(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all equipment ordered by name."""

def get_equipment_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    """Get equipment filtered by status."""

def update_equipment(conn: sqlite3.Connection, equipment_id: int, name: str,
                     category: str, serial_number: str,
                     purchase_date: str | None, purchase_price_cents: int,
                     status: str, location: str, notes: str) -> None:
    """Update equipment. Commits: yes."""

def delete_equipment(conn: sqlite3.Connection, equipment_id: int) -> None:
    """Delete equipment. Commits: yes.
    Raises sqlite3.IntegrityError if maintenance records exist.
    """

def get_equipment_needing_maintenance(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get equipment where latest maintenance_log.next_due_date <= date('now').
    Returns equipment rows with next_due_date column added.
    Usage:
        needs_maint = get_equipment_needing_maintenance(conn)
    """
```

### models/maintenance.py (maintenance_models agent)

```python
import sqlite3

def create_maintenance(conn: sqlite3.Connection, equipment_id: int,
                       description: str, maintenance_date: str,
                       cost_cents: int, performed_by: str,
                       next_due_date: str | None) -> int:
    """Create maintenance record. Returns new record ID.
    Usage:
        maint_id = create_maintenance(conn, 1, 'Belt replaced',
                                      '2026-05-21', 5000, 'Bob', '2026-08-21')
        return redirect(url_for('maintenance.list_maintenance'))
    Commits: yes
    """

def get_maintenance(conn: sqlite3.Connection, maintenance_id: int) -> sqlite3.Row | None:
    """Get maintenance record by ID with equipment_name joined."""

def get_maintenance_by_equipment(conn: sqlite3.Connection,
                                  equipment_id: int) -> list[sqlite3.Row]:
    """Get maintenance records for equipment. Ordered by maintenance_date DESC."""

def get_all_maintenance(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all maintenance records with equipment_name. Ordered by date DESC."""

def update_maintenance(conn: sqlite3.Connection, maintenance_id: int,
                       equipment_id: int, description: str,
                       maintenance_date: str, cost_cents: int,
                       performed_by: str, next_due_date: str | None) -> None:
    """Update maintenance record. Commits: yes."""

def delete_maintenance(conn: sqlite3.Connection, maintenance_id: int) -> None:
    """Delete maintenance record. Commits: yes."""
```

### models/invoice.py (billing_models agent)

```python
import sqlite3

def create_invoice(conn: sqlite3.Connection, member_id: int,
                   amount_cents: int, description: str,
                   due_date: str) -> int:
    """Create invoice. Returns new invoice ID.
    Usage:
        invoice_id = create_invoice(conn, 1, 4999, 'Monthly membership - June', '2026-06-01')
        return redirect(url_for('billing.detail', invoice_id=invoice_id))
    Commits: yes
    """

def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> sqlite3.Row | None:
    """Get invoice by ID with member_name joined.
    Returns Row with: id, member_id, amount_cents, description, billing_date,
    due_date, status, created_at, updated_at, member_name.
    """

def get_invoices_by_member(conn: sqlite3.Connection, member_id: int) -> list[sqlite3.Row]:
    """Get invoices for a member. Ordered by billing_date DESC."""

def get_all_invoices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all invoices with member_name. Ordered by billing_date DESC."""

def get_invoices_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    """Get invoices filtered by status. Includes member_name."""

def update_invoice(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, description: str, due_date: str,
                   status: str) -> None:
    """Update invoice. Commits: yes."""

def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Delete invoice. Commits: yes.
    Raises sqlite3.IntegrityError if payments exist for this invoice.
    """
```

### models/payment.py (payment_models agent)

```python
import sqlite3

def create_payment(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, payment_date: str,
                   payment_method: str, reference_number: str,
                   notes: str) -> int:
    """Create payment. Returns new payment ID.
    Usage:
        payment_id = create_payment(conn, 1, 4999, '2026-05-21',
                                    'card', 'REF-001', '')
        return redirect(url_for('billing.detail', invoice_id=invoice_id))
    Commits: yes
    """

def get_payment(conn: sqlite3.Connection, payment_id: int) -> sqlite3.Row | None:
    """Get payment by ID."""

def get_payments_by_invoice(conn: sqlite3.Connection,
                             invoice_id: int) -> list[sqlite3.Row]:
    """Get payments for an invoice. Ordered by payment_date DESC."""

def get_all_payments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all payments with invoice description and member_name joined.
    Ordered by payment_date DESC."""

def delete_payment(conn: sqlite3.Connection, payment_id: int) -> None:
    """Delete payment. Commits: yes."""

def get_invoice_paid_amount(conn: sqlite3.Connection, invoice_id: int) -> int:
    """Sum of all payment amounts for an invoice. Returns int (cents).
    Usage:
        paid = get_invoice_paid_amount(conn, invoice_id)
        # paid is an int, NOT a Row
    """

def get_revenue_this_month(conn: sqlite3.Connection) -> int:
    """Sum of all payment amounts in current month. Returns int (cents).
    Usage:
        revenue = get_revenue_this_month(conn)
        # revenue is an int, NOT a Row
    """
```

### models/assessment.py (assessment_models agent)

```python
import sqlite3

def create_assessment(conn: sqlite3.Connection, member_id: int,
                      trainer_id: int | None, assessment_date: str,
                      weight_kg: float | None, height_cm: float | None,
                      body_fat_pct: float | None,
                      resting_heart_rate: int | None,
                      notes: str) -> int:
    """Create fitness assessment. Computes BMI automatically if weight and height provided.
    BMI = weight_kg / (height_cm / 100) ** 2
    Returns new assessment ID.
    Usage:
        assess_id = create_assessment(conn, 1, 2, '2026-05-21',
                                      80.0, 175.0, 15.5, 68, 'Good form')
        return redirect(url_for('assessments.detail', assessment_id=assess_id))
    Commits: yes
    """

def get_assessment(conn: sqlite3.Connection, assessment_id: int) -> sqlite3.Row | None:
    """Get assessment by ID with member_name and trainer_name joined."""

def get_assessments_by_member(conn: sqlite3.Connection,
                               member_id: int) -> list[sqlite3.Row]:
    """Get assessments for a member. Ordered by assessment_date DESC.
    Includes trainer_name."""

def get_all_assessments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all assessments with member_name and trainer_name. Ordered by date DESC."""

def update_assessment(conn: sqlite3.Connection, assessment_id: int,
                      member_id: int, trainer_id: int | None,
                      assessment_date: str, weight_kg: float | None,
                      height_cm: float | None, body_fat_pct: float | None,
                      resting_heart_rate: int | None,
                      notes: str) -> None:
    """Update assessment. Recomputes BMI. Commits: yes."""

def delete_assessment(conn: sqlite3.Connection, assessment_id: int) -> None:
    """Delete assessment. Commits: yes."""

def get_latest_assessment(conn: sqlite3.Connection,
                           member_id: int) -> sqlite3.Row | None:
    """Get most recent assessment for a member. Returns Row or None.
    Usage:
        latest = get_latest_assessment(conn, member_id)
        if latest is not None:
            weight = latest['weight_kg']
    """
```

### models/__init__.py (core agent -- barrel re-exports)

```python
# app/models/__init__.py -- Barrel file
# ALL model functions re-exported here.
# Route agents import: from app.models import function_name

from app.models.member import (
    create_member, get_member, get_all_members, get_members_by_status,
    update_member, delete_member, count_active_members,
    count_new_members_this_month, search_members,
)
from app.models.trainer import (
    create_trainer, get_trainer, get_all_trainers, get_active_trainers,
    update_trainer, delete_trainer,
)
from app.models.membership_type import (
    create_membership_type, get_membership_type, get_all_membership_types,
    get_active_membership_types, update_membership_type, delete_membership_type,
)
from app.models.class_type import (
    create_class_type, get_class_type, get_all_class_types,
    update_class_type, delete_class_type,
)
from app.models.schedule import (
    create_schedule, get_schedule, get_schedules_by_date,
    get_schedules_by_date_range, get_schedules_by_trainer,
    update_schedule, delete_schedule, copy_week_schedules,
    get_schedule_attendance_count,
)
from app.models.attendance import (
    check_in_class, check_in_open_gym, check_out, get_attendance,
    get_attendance_by_schedule, get_attendance_by_member,
    get_recent_checkins, get_today_checkins, delete_attendance,
)
from app.models.equipment import (
    create_equipment, get_equipment, get_all_equipment,
    get_equipment_by_status, update_equipment, delete_equipment,
    get_equipment_needing_maintenance,
)
from app.models.maintenance import (
    create_maintenance, get_maintenance, get_maintenance_by_equipment,
    get_all_maintenance, update_maintenance, delete_maintenance,
)
from app.models.invoice import (
    create_invoice, get_invoice, get_invoices_by_member,
    get_all_invoices, get_invoices_by_status, update_invoice,
    delete_invoice,
)
from app.models.payment import (
    create_payment, get_payment, get_payments_by_invoice,
    get_all_payments, delete_payment, get_invoice_paid_amount,
    get_revenue_this_month,
)
from app.models.assessment import (
    create_assessment, get_assessment, get_assessments_by_member,
    get_all_assessments, update_assessment, delete_assessment,
    get_latest_assessment,
)
```

## Route Table

All routes require `@login_required` except auth routes and GET /health.

| Method | Route Path | Endpoint Name | Template | Agent |
|--------|-----------|---------------|----------|-------|
| GET | /health | health | — (JSON) | core |
| GET | /login | auth.login_page | auth/login.html | auth |
| POST | /login | auth.login | redirect | auth |
| POST | /logout | auth.logout | redirect | auth |
| GET | / | dashboard.index | dashboard/index.html | dashboard_routes |
| GET | /members/ | members.list_members | members/list.html | member_routes |
| GET | /members/new | members.new_member | members/form.html | member_routes |
| POST | /members/ | members.create_member | redirect | member_routes |
| GET | /members/\<int:member_id\> | members.detail | members/detail.html | member_routes |
| GET | /members/\<int:member_id\>/edit | members.edit_member | members/form.html | member_routes |
| POST | /members/\<int:member_id\>/edit | members.update_member | redirect | member_routes |
| POST | /members/\<int:member_id\>/delete | members.delete_member | redirect | member_routes |
| GET | /trainers/ | trainers.list_trainers | trainers/list.html | trainer_routes |
| GET | /trainers/new | trainers.new_trainer | trainers/form.html | trainer_routes |
| POST | /trainers/ | trainers.create_trainer | redirect | trainer_routes |
| GET | /trainers/\<int:trainer_id\> | trainers.detail | trainers/detail.html | trainer_routes |
| GET | /trainers/\<int:trainer_id\>/edit | trainers.edit_trainer | trainers/form.html | trainer_routes |
| POST | /trainers/\<int:trainer_id\>/edit | trainers.update_trainer | redirect | trainer_routes |
| POST | /trainers/\<int:trainer_id\>/delete | trainers.delete_trainer | redirect | trainer_routes |
| GET | /membership-types/ | membership_types.list_types | membership_types/list.html | membership_type_routes |
| GET | /membership-types/new | membership_types.new_type | membership_types/form.html | membership_type_routes |
| POST | /membership-types/ | membership_types.create_type | redirect | membership_type_routes |
| GET | /membership-types/\<int:type_id\>/edit | membership_types.edit_type | membership_types/form.html | membership_type_routes |
| POST | /membership-types/\<int:type_id\>/edit | membership_types.update_type | redirect | membership_type_routes |
| POST | /membership-types/\<int:type_id\>/delete | membership_types.delete_type | redirect | membership_type_routes |
| GET | /class-types/ | class_types.list_types | class_types/list.html | class_type_routes |
| GET | /class-types/new | class_types.new_type | class_types/form.html | class_type_routes |
| POST | /class-types/ | class_types.create_type | redirect | class_type_routes |
| GET | /class-types/\<int:type_id\>/edit | class_types.edit_type | class_types/form.html | class_type_routes |
| POST | /class-types/\<int:type_id\>/edit | class_types.update_type | redirect | class_type_routes |
| POST | /class-types/\<int:type_id\>/delete | class_types.delete_type | redirect | class_type_routes |
| GET | /schedules/ | schedules.list_schedules | schedules/list.html | schedule_routes |
| GET | /schedules/new | schedules.new_schedule | schedules/form.html | schedule_routes |
| POST | /schedules/ | schedules.create_schedule | redirect | schedule_routes |
| GET | /schedules/\<int:schedule_id\> | schedules.detail | schedules/detail.html | schedule_routes |
| GET | /schedules/\<int:schedule_id\>/edit | schedules.edit_schedule | schedules/form.html | schedule_routes |
| POST | /schedules/\<int:schedule_id\>/edit | schedules.update_schedule | redirect | schedule_routes |
| POST | /schedules/\<int:schedule_id\>/delete | schedules.delete_schedule | redirect | schedule_routes |
| POST | /schedules/copy-week | schedules.copy_week | redirect | schedule_routes |
| GET | /attendance/ | attendance.list_attendance | attendance/list.html | attendance_routes |
| GET | /attendance/check-in | attendance.check_in_form | attendance/check_in.html | attendance_routes |
| POST | /attendance/check-in | attendance.check_in | redirect | attendance_routes |
| POST | /attendance/\<int:attendance_id\>/check-out | attendance.check_out | redirect | attendance_routes |
| POST | /attendance/\<int:attendance_id\>/delete | attendance.delete_attendance | redirect | attendance_routes |
| GET | /equipment/ | equipment.list_equipment | equipment/list.html | equipment_routes |
| GET | /equipment/new | equipment.new_equipment | equipment/form.html | equipment_routes |
| POST | /equipment/ | equipment.create_equipment | redirect | equipment_routes |
| GET | /equipment/\<int:equipment_id\> | equipment.detail | equipment/detail.html | equipment_routes |
| GET | /equipment/\<int:equipment_id\>/edit | equipment.edit_equipment | equipment/form.html | equipment_routes |
| POST | /equipment/\<int:equipment_id\>/edit | equipment.update_equipment | redirect | equipment_routes |
| POST | /equipment/\<int:equipment_id\>/delete | equipment.delete_equipment | redirect | equipment_routes |
| GET | /maintenance/ | maintenance.list_maintenance | maintenance/list.html | maintenance_routes |
| GET | /maintenance/new | maintenance.new_maintenance | maintenance/form.html | maintenance_routes |
| POST | /maintenance/ | maintenance.create_maintenance | redirect | maintenance_routes |
| GET | /maintenance/\<int:maintenance_id\>/edit | maintenance.edit_maintenance | maintenance/form.html | maintenance_routes |
| POST | /maintenance/\<int:maintenance_id\>/edit | maintenance.update_maintenance | redirect | maintenance_routes |
| POST | /maintenance/\<int:maintenance_id\>/delete | maintenance.delete_maintenance | redirect | maintenance_routes |
| GET | /billing/ | billing.list_invoices | billing/list.html | billing_routes |
| GET | /billing/new | billing.new_invoice | billing/form.html | billing_routes |
| POST | /billing/ | billing.create_invoice | redirect | billing_routes |
| GET | /billing/\<int:invoice_id\> | billing.detail | billing/detail.html | billing_routes |
| GET | /billing/\<int:invoice_id\>/edit | billing.edit_invoice | billing/form.html | billing_routes |
| POST | /billing/\<int:invoice_id\>/edit | billing.update_invoice | redirect | billing_routes |
| POST | /billing/\<int:invoice_id\>/delete | billing.delete_invoice | redirect | billing_routes |
| GET | /payments/ | payments.list_payments | payments/list.html | payment_routes |
| GET | /payments/new | payments.new_payment | payments/form.html | payment_routes |
| POST | /payments/ | payments.create_payment | redirect | payment_routes |
| POST | /payments/\<int:payment_id\>/delete | payments.delete_payment | redirect | payment_routes |
| GET | /assessments/ | assessments.list_assessments | assessments/list.html | assessment_routes |
| GET | /assessments/new | assessments.new_assessment | assessments/form.html | assessment_routes |
| POST | /assessments/ | assessments.create_assessment | redirect | assessment_routes |
| GET | /assessments/\<int:assessment_id\> | assessments.detail | assessments/detail.html | assessment_routes |
| GET | /assessments/\<int:assessment_id\>/edit | assessments.edit_assessment | assessments/form.html | assessment_routes |
| POST | /assessments/\<int:assessment_id\>/edit | assessments.update_assessment | redirect | assessment_routes |
| POST | /assessments/\<int:assessment_id\>/delete | assessments.delete_assessment | redirect | assessment_routes |

## Template Render Context

### auth/login.html (auth agent)
```python
render_template('auth/login.html')
# No context variables. Form posts to url_for('auth.login').
```

### dashboard/index.html (dashboard_routes agent)
```python
render_template('dashboard/index.html',
    active_members=count_active_members(conn),
    new_this_month=count_new_members_this_month(conn),
    revenue_this_month=get_revenue_this_month(conn),
    todays_schedule=get_schedules_by_date(conn, today),
    recent_checkins=get_recent_checkins(conn, 10),
    needs_maintenance=get_equipment_needing_maintenance(conn),
)
```

### members/list.html (member_routes agent)
```python
render_template('members/list.html', members=members)
# members is list[Row] from get_all_members(conn)
```

### members/detail.html (member_routes agent)
```python
render_template('members/detail.html',
    member=member,
    latest_assessment=get_latest_assessment(conn, member_id),
)
```

### members/form.html (member_routes agent)
```python
# New: member=None, membership_types from get_active_membership_types(conn)
# Edit: member=Row, membership_types from get_active_membership_types(conn)
render_template('members/form.html',
    member=member,  # None for new, Row for edit
    membership_types=get_active_membership_types(conn),
)
```

### trainers/list.html (trainer_routes agent)
```python
render_template('trainers/list.html', trainers=trainers)
```

### trainers/detail.html (trainer_routes agent)
```python
render_template('trainers/detail.html', trainer=trainer)
```

### trainers/form.html (trainer_routes agent)
```python
render_template('trainers/form.html', trainer=trainer)
# trainer is None for new, Row for edit
```

### membership_types/list.html (membership_type_routes agent)
```python
render_template('membership_types/list.html', types=types)
```

### membership_types/form.html (membership_type_routes agent)
```python
render_template('membership_types/form.html', mtype=mtype)
# mtype is None for new, Row for edit
```

### class_types/list.html (class_type_routes agent)
```python
render_template('class_types/list.html', types=types)
```

### class_types/form.html (class_type_routes agent)
```python
render_template('class_types/form.html', ctype=ctype)
# ctype is None for new, Row for edit
```

### schedules/list.html (schedule_routes agent)
```python
render_template('schedules/list.html',
    schedules=schedules,
    selected_date=selected_date,
)
```

### schedules/detail.html (schedule_routes agent)
```python
render_template('schedules/detail.html',
    schedule=schedule,
    attendees=get_attendance_by_schedule(conn, schedule_id),
    attendance_count=get_schedule_attendance_count(conn, schedule_id),
)
```

### schedules/form.html (schedule_routes agent)
```python
render_template('schedules/form.html',
    schedule=schedule,  # None for new, Row for edit
    class_types=get_all_class_types(conn),
    trainers=get_active_trainers(conn),
)
```

### attendance/list.html (attendance_routes agent)
```python
render_template('attendance/list.html', records=records)
# records from get_today_checkins(conn)
```

### attendance/check_in.html (attendance_routes agent)
```python
render_template('attendance/check_in.html',
    members=get_all_members(conn),
    schedules=get_schedules_by_date(conn, today),
)
```

### equipment/list.html (equipment_routes agent)
```python
render_template('equipment/list.html', equipment_list=equipment_list)
```

### equipment/detail.html (equipment_routes agent)
```python
render_template('equipment/detail.html',
    item=item,
    maintenance_history=get_maintenance_by_equipment(conn, equipment_id),
)
```

### equipment/form.html (equipment_routes agent)
```python
render_template('equipment/form.html', item=item)
# item is None for new, Row for edit
```

### maintenance/list.html (maintenance_routes agent)
```python
render_template('maintenance/list.html', records=records)
```

### maintenance/form.html (maintenance_routes agent)
```python
render_template('maintenance/form.html',
    record=record,  # None for new, Row for edit
    equipment_list=get_all_equipment(conn),
)
```

### billing/list.html (billing_routes agent)
```python
render_template('billing/list.html', invoices=invoices)
```

### billing/detail.html (billing_routes agent)
```python
render_template('billing/detail.html',
    invoice=invoice,
    payments=get_payments_by_invoice(conn, invoice_id),
    paid_amount=get_invoice_paid_amount(conn, invoice_id),
)
```

### billing/form.html (billing_routes agent)
```python
render_template('billing/form.html',
    invoice=invoice,  # None for new, Row for edit
    members=get_all_members(conn),
)
```

### payments/list.html (payment_routes agent)
```python
render_template('payments/list.html', payments=payments)
```

### payments/form.html (payment_routes agent)
```python
render_template('payments/form.html',
    invoices=get_all_invoices(conn),
    selected_invoice_id=request.args.get('invoice_id', type=int),
)
```

### assessments/list.html (assessment_routes agent)
```python
render_template('assessments/list.html', assessments=assessments)
```

### assessments/detail.html (assessment_routes agent)
```python
render_template('assessments/detail.html', assessment=assessment)
```

### assessments/form.html (assessment_routes agent)
```python
render_template('assessments/form.html',
    assessment=assessment,  # None for new, Row for edit
    members=get_all_members(conn),
    trainers=get_active_trainers(conn),
)
```

## CSRF in Templates

Every POST form MUST include:
```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <!-- form fields -->
</form>
```

## Export Names Table

| Name | Type | Defined By | Used By |
|------|------|------------|---------|
| `create_member` | model function | `app/models/member.py` | `member_routes` |
| `get_member` | model function | `app/models/member.py` | `member_routes`, `assessment_routes` |
| `get_all_members` | model function | `app/models/member.py` | `member_routes`, `attendance_routes`, `billing_routes`, `assessment_routes`, `payment_routes` |
| `get_members_by_status` | model function | `app/models/member.py` | `member_routes` |
| `update_member` | model function | `app/models/member.py` | `member_routes` |
| `delete_member` | model function | `app/models/member.py` | `member_routes` |
| `count_active_members` | model function | `app/models/member.py` | `dashboard_routes` |
| `count_new_members_this_month` | model function | `app/models/member.py` | `dashboard_routes` |
| `search_members` | model function | `app/models/member.py` | `member_routes` |
| `create_trainer` | model function | `app/models/trainer.py` | `trainer_routes` |
| `get_trainer` | model function | `app/models/trainer.py` | `trainer_routes` |
| `get_all_trainers` | model function | `app/models/trainer.py` | `trainer_routes` |
| `get_active_trainers` | model function | `app/models/trainer.py` | `schedule_routes`, `assessment_routes` |
| `update_trainer` | model function | `app/models/trainer.py` | `trainer_routes` |
| `delete_trainer` | model function | `app/models/trainer.py` | `trainer_routes` |
| `create_membership_type` | model function | `app/models/membership_type.py` | `membership_type_routes` |
| `get_membership_type` | model function | `app/models/membership_type.py` | `membership_type_routes` |
| `get_all_membership_types` | model function | `app/models/membership_type.py` | `membership_type_routes` |
| `get_active_membership_types` | model function | `app/models/membership_type.py` | `member_routes` |
| `update_membership_type` | model function | `app/models/membership_type.py` | `membership_type_routes` |
| `delete_membership_type` | model function | `app/models/membership_type.py` | `membership_type_routes` |
| `create_class_type` | model function | `app/models/class_type.py` | `class_type_routes` |
| `get_class_type` | model function | `app/models/class_type.py` | `class_type_routes` |
| `get_all_class_types` | model function | `app/models/class_type.py` | `class_type_routes`, `schedule_routes` |
| `update_class_type` | model function | `app/models/class_type.py` | `class_type_routes` |
| `delete_class_type` | model function | `app/models/class_type.py` | `class_type_routes` |
| `create_schedule` | model function | `app/models/schedule.py` | `schedule_routes` |
| `get_schedule` | model function | `app/models/schedule.py` | `schedule_routes` |
| `get_schedules_by_date` | model function | `app/models/schedule.py` | `schedule_routes`, `attendance_routes`, `dashboard_routes` |
| `get_schedules_by_date_range` | model function | `app/models/schedule.py` | `schedule_routes` |
| `get_schedules_by_trainer` | model function | `app/models/schedule.py` | `schedule_routes` |
| `update_schedule` | model function | `app/models/schedule.py` | `schedule_routes` |
| `delete_schedule` | model function | `app/models/schedule.py` | `schedule_routes` |
| `copy_week_schedules` | model function | `app/models/schedule.py` | `schedule_routes` |
| `get_schedule_attendance_count` | model function | `app/models/schedule.py` | `schedule_routes` |
| `check_in_class` | model function | `app/models/attendance.py` | `attendance_routes` |
| `check_in_open_gym` | model function | `app/models/attendance.py` | `attendance_routes` |
| `check_out` | model function | `app/models/attendance.py` | `attendance_routes` |
| `get_attendance` | model function | `app/models/attendance.py` | `attendance_routes` |
| `get_attendance_by_schedule` | model function | `app/models/attendance.py` | `schedule_routes` |
| `get_attendance_by_member` | model function | `app/models/attendance.py` | `attendance_routes` |
| `get_recent_checkins` | model function | `app/models/attendance.py` | `dashboard_routes` |
| `get_today_checkins` | model function | `app/models/attendance.py` | `attendance_routes` |
| `delete_attendance` | model function | `app/models/attendance.py` | `attendance_routes` |
| `create_equipment` | model function | `app/models/equipment.py` | `equipment_routes` |
| `get_equipment` | model function | `app/models/equipment.py` | `equipment_routes` |
| `get_all_equipment` | model function | `app/models/equipment.py` | `equipment_routes`, `maintenance_routes` |
| `get_equipment_by_status` | model function | `app/models/equipment.py` | `equipment_routes` |
| `update_equipment` | model function | `app/models/equipment.py` | `equipment_routes` |
| `delete_equipment` | model function | `app/models/equipment.py` | `equipment_routes` |
| `get_equipment_needing_maintenance` | model function | `app/models/equipment.py` | `dashboard_routes` |
| `create_maintenance` | model function | `app/models/maintenance.py` | `maintenance_routes` |
| `get_maintenance` | model function | `app/models/maintenance.py` | `maintenance_routes` |
| `get_maintenance_by_equipment` | model function | `app/models/maintenance.py` | `equipment_routes` |
| `get_all_maintenance` | model function | `app/models/maintenance.py` | `maintenance_routes` |
| `update_maintenance` | model function | `app/models/maintenance.py` | `maintenance_routes` |
| `delete_maintenance` | model function | `app/models/maintenance.py` | `maintenance_routes` |
| `create_invoice` | model function | `app/models/invoice.py` | `billing_routes` |
| `get_invoice` | model function | `app/models/invoice.py` | `billing_routes`, `payment_routes` |
| `get_invoices_by_member` | model function | `app/models/invoice.py` | `billing_routes` |
| `get_all_invoices` | model function | `app/models/invoice.py` | `billing_routes`, `payment_routes` |
| `get_invoices_by_status` | model function | `app/models/invoice.py` | `billing_routes` |
| `update_invoice` | model function | `app/models/invoice.py` | `billing_routes` |
| `delete_invoice` | model function | `app/models/invoice.py` | `billing_routes` |
| `create_payment` | model function | `app/models/payment.py` | `payment_routes` |
| `get_payment` | model function | `app/models/payment.py` | (internal use only) |
| `get_payments_by_invoice` | model function | `app/models/payment.py` | `billing_routes` |
| `get_all_payments` | model function | `app/models/payment.py` | `payment_routes` |
| `delete_payment` | model function | `app/models/payment.py` | `payment_routes` |
| `get_invoice_paid_amount` | model function | `app/models/payment.py` | `billing_routes` |
| `get_revenue_this_month` | model function | `app/models/payment.py` | `dashboard_routes` |
| `create_assessment` | model function | `app/models/assessment.py` | `assessment_routes` |
| `get_assessment` | model function | `app/models/assessment.py` | `assessment_routes` |
| `get_assessments_by_member` | model function | `app/models/assessment.py` | `assessment_routes` |
| `get_all_assessments` | model function | `app/models/assessment.py` | `assessment_routes` |
| `update_assessment` | model function | `app/models/assessment.py` | `assessment_routes` |
| `delete_assessment` | model function | `app/models/assessment.py` | `assessment_routes` |
| `get_latest_assessment` | model function | `app/models/assessment.py` | `member_routes` |
| `get_db` | db function | `app/db.py` | ALL route agents, ALL model agents |
| `login_required` | decorator | `app/auth.py` | ALL route agents (except auth) |
| `check_password` | auth function | `app/auth.py` | `auth` agent |
| `dashboard.index` | endpoint | `app/blueprints/dashboard/routes.py` | `layout` (navbar) |
| `auth.login_page` | endpoint | `app/blueprints/auth/routes.py` | `layout` (navbar), `auth.py` (redirect) |
| `auth.login` | endpoint | `app/blueprints/auth/routes.py` | `auth` (form action) |
| `auth.logout` | endpoint | `app/blueprints/auth/routes.py` | `layout` (navbar) |
| `members.list_members` | endpoint | `app/blueprints/members/routes.py` | `layout` (navbar) |
| `members.detail` | endpoint | `app/blueprints/members/routes.py` | `member_routes`, `dashboard_routes` |
| `trainers.list_trainers` | endpoint | `app/blueprints/trainers/routes.py` | `layout` (navbar) |
| `trainers.detail` | endpoint | `app/blueprints/trainers/routes.py` | `trainer_routes` |
| `membership_types.list_types` | endpoint | `app/blueprints/membership_types/routes.py` | `layout` (navbar) |
| `class_types.list_types` | endpoint | `app/blueprints/class_types/routes.py` | `layout` (navbar) |
| `schedules.list_schedules` | endpoint | `app/blueprints/schedules/routes.py` | `layout` (navbar) |
| `schedules.detail` | endpoint | `app/blueprints/schedules/routes.py` | `schedule_routes` |
| `attendance.list_attendance` | endpoint | `app/blueprints/attendance/routes.py` | `layout` (navbar) |
| `attendance.check_in_form` | endpoint | `app/blueprints/attendance/routes.py` | `attendance_routes` |
| `equipment.list_equipment` | endpoint | `app/blueprints/equipment/routes.py` | `layout` (navbar) |
| `equipment.detail` | endpoint | `app/blueprints/equipment/routes.py` | `equipment_routes` |
| `maintenance.list_maintenance` | endpoint | `app/blueprints/maintenance/routes.py` | `layout` (navbar) |
| `billing.list_invoices` | endpoint | `app/blueprints/billing/routes.py` | `layout` (navbar) |
| `billing.detail` | endpoint | `app/blueprints/billing/routes.py` | `billing_routes`, `payment_routes` |
| `payments.list_payments` | endpoint | `app/blueprints/payments/routes.py` | `layout` (navbar) |
| `payments.new_payment` | endpoint | `app/blueprints/payments/routes.py` | `billing_routes` (link from detail) |
| `assessments.list_assessments` | endpoint | `app/blueprints/assessments/routes.py` | `layout` (navbar) |
| `assessments.detail` | endpoint | `app/blueprints/assessments/routes.py` | `assessment_routes` |

## Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `app/db.py` | ALL routes | `from app.db import get_db` |
| `app/auth.py` | ALL routes except auth | `from app.auth import login_required` |
| `app/auth.py` | `app/blueprints/auth/routes.py` | `from app.auth import login_required, check_password` |
| `app/models/__init__.py` | `app/blueprints/members/routes.py` | `from app.models import create_member, get_member, get_all_members, get_members_by_status, update_member, delete_member, search_members, get_active_membership_types, get_latest_assessment` |
| `app/models/__init__.py` | `app/blueprints/trainers/routes.py` | `from app.models import create_trainer, get_trainer, get_all_trainers, update_trainer, delete_trainer` |
| `app/models/__init__.py` | `app/blueprints/membership_types/routes.py` | `from app.models import create_membership_type, get_membership_type, get_all_membership_types, update_membership_type, delete_membership_type` |
| `app/models/__init__.py` | `app/blueprints/class_types/routes.py` | `from app.models import create_class_type, get_class_type, get_all_class_types, update_class_type, delete_class_type` |
| `app/models/__init__.py` | `app/blueprints/schedules/routes.py` | `from app.models import create_schedule, get_schedule, get_schedules_by_date, get_schedules_by_date_range, get_schedules_by_trainer, update_schedule, delete_schedule, copy_week_schedules, get_schedule_attendance_count, get_all_class_types, get_active_trainers, get_attendance_by_schedule` |
| `app/models/__init__.py` | `app/blueprints/attendance/routes.py` | `from app.models import check_in_class, check_in_open_gym, check_out, get_attendance, get_attendance_by_member, get_today_checkins, delete_attendance, get_all_members, get_schedules_by_date` |
| `app/models/__init__.py` | `app/blueprints/equipment/routes.py` | `from app.models import create_equipment, get_equipment, get_all_equipment, get_equipment_by_status, update_equipment, delete_equipment, get_maintenance_by_equipment` |
| `app/models/__init__.py` | `app/blueprints/maintenance/routes.py` | `from app.models import create_maintenance, get_maintenance, get_all_maintenance, update_maintenance, delete_maintenance, get_all_equipment` |
| `app/models/__init__.py` | `app/blueprints/billing/routes.py` | `from app.models import create_invoice, get_invoice, get_invoices_by_member, get_all_invoices, get_invoices_by_status, update_invoice, delete_invoice, get_all_members, get_payments_by_invoice, get_invoice_paid_amount` |
| `app/models/__init__.py` | `app/blueprints/payments/routes.py` | `from app.models import create_payment, get_all_payments, delete_payment, get_all_invoices, get_invoice` |
| `app/models/__init__.py` | `app/blueprints/assessments/routes.py` | `from app.models import create_assessment, get_assessment, get_all_assessments, get_assessments_by_member, update_assessment, delete_assessment, get_all_members, get_active_trainers` |
| `app/models/__init__.py` | `app/blueprints/dashboard/routes.py` | `from app.models import count_active_members, count_new_members_this_month, get_revenue_this_month, get_schedules_by_date, get_recent_checkins, get_equipment_needing_maintenance` |

## Input Validation Prescriptions

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| `POST /login` | `password` (form) | Required, non-empty | Flash "Invalid password", redirect to login |
| `POST /members/` | `name` (form) | Strip, 1-100 chars, required | Flash "Name is required", redirect back |
| `POST /members/` | `email` (form) | Strip, 1-200 chars, required, basic format check | Flash "Valid email is required", redirect back |
| `POST /members/` | `phone` (form) | Strip, 0-50 chars | N/A (optional) |
| `POST /members/` | `emergency_contact` (form) | Strip, 0-200 chars | N/A (optional) |
| `POST /members/` | `membership_type_id` (form) | int or empty string -> None | Flash "Invalid membership type", redirect back |
| `POST /members/` | `notes` (form) | Strip, 0-1000 chars | N/A (optional) |
| `POST /members/<id>/edit` | `status` (form) | Must be in ('active', 'frozen', 'cancelled') | Flash "Invalid status", redirect back |
| `POST /members/<id>/delete` | `member_id` (URL) | Must exist | `abort(404)` |
| `POST /trainers/` | `name` (form) | Strip, 1-100 chars, required | Flash "Name is required", redirect back |
| `POST /trainers/` | `email` (form) | Strip, 1-200 chars, required | Flash "Valid email is required", redirect back |
| `POST /trainers/` | `specializations` (form) | Strip, 0-500 chars | N/A (optional) |
| `POST /trainers/<id>/edit` | `status` (form) | Must be in ('active', 'inactive') | Flash "Invalid status", redirect back |
| `POST /membership-types/` | `name` (form) | Strip, 1-100 chars, required, unique | Flash error, redirect back |
| `POST /membership-types/` | `duration_months` (form) | int, >= 1 | Flash "Duration must be at least 1 month", redirect back |
| `POST /membership-types/` | `price` (form) | float -> cents via `round(float(val) * 100)`, >= 0 | Flash "Valid price is required", redirect back |
| `POST /class-types/` | `name` (form) | Strip, 1-100 chars, required, unique | Flash error, redirect back |
| `POST /class-types/` | `duration_minutes` (form) | int, >= 1 | Flash "Duration must be at least 1 minute", redirect back |
| `POST /class-types/` | `default_capacity` (form) | int, >= 1 | Flash "Capacity must be at least 1", redirect back |
| `POST /schedules/` | `class_type_id` (form) | int, required, must exist | Flash "Class type is required", redirect back |
| `POST /schedules/` | `trainer_id` (form) | int or empty -> None | Flash "Invalid trainer", redirect back |
| `POST /schedules/` | `session_date` (form) | Required, YYYY-MM-DD format | Flash "Valid date is required", redirect back |
| `POST /schedules/` | `start_time` (form) | Required, HH:MM format | Flash "Valid start time is required", redirect back |
| `POST /schedules/` | `end_time` (form) | Required, HH:MM format | Flash "Valid end time is required", redirect back |
| `POST /schedules/` | `capacity` (form) | int, >= 1 | Flash "Capacity must be at least 1", redirect back |
| `POST /schedules/copy-week` | `source_date` (form) | Required, YYYY-MM-DD | Flash "Source date is required", redirect back |
| `POST /schedules/copy-week` | `target_date` (form) | Required, YYYY-MM-DD | Flash "Target date is required", redirect back |
| `POST /attendance/check-in` | `member_id` (form) | int, required, must exist | Flash "Member is required", redirect back |
| `POST /attendance/check-in` | `attendance_type` (form) | Must be 'class' or 'open_gym' | Flash "Invalid type", redirect back |
| `POST /attendance/check-in` | `class_schedule_id` (form) | int, required if type='class' | Flash "Class is required for class check-in", redirect back |
| `POST /equipment/` | `name` (form) | Strip, 1-100 chars, required | Flash "Name is required", redirect back |
| `POST /equipment/` | `purchase_price` (form) | float -> cents via `round(float(val) * 100)`, >= 0 | Flash "Valid price is required", redirect back |
| `POST /equipment/` | `status` (form) | Must be in ('available', 'in_use', 'maintenance', 'retired') | Flash "Invalid status", redirect back |
| `POST /maintenance/` | `equipment_id` (form) | int, required, must exist | Flash "Equipment is required", redirect back |
| `POST /maintenance/` | `description` (form) | Strip, 1-500 chars, required | Flash "Description is required", redirect back |
| `POST /maintenance/` | `cost` (form) | float -> cents via `round(float(val) * 100)`, >= 0 | Flash "Valid cost is required", redirect back |
| `POST /billing/` | `member_id` (form) | int, required, must exist | Flash "Member is required", redirect back |
| `POST /billing/` | `amount` (form) | float -> cents via `round(float(val) * 100)`, > 0 | Flash "Amount must be positive", redirect back |
| `POST /billing/` | `description` (form) | Strip, 1-500 chars, required | Flash "Description is required", redirect back |
| `POST /billing/` | `due_date` (form) | Required, YYYY-MM-DD | Flash "Due date is required", redirect back |
| `POST /billing/<id>/edit` | `status` (form) | Must be in ('pending', 'paid', 'overdue', 'cancelled') | Flash "Invalid status", redirect back |
| `POST /payments/` | `invoice_id` (form) | int, required, must exist | Flash "Invoice is required", redirect back |
| `POST /payments/` | `amount` (form) | float -> cents via `round(float(val) * 100)`, > 0 | Flash "Amount must be positive", redirect back |
| `POST /payments/` | `payment_method` (form) | Must be in ('cash', 'card', 'bank_transfer', 'other') | Flash "Invalid payment method", redirect back |
| `POST /assessments/` | `member_id` (form) | int, required, must exist | Flash "Member is required", redirect back |
| `POST /assessments/` | `assessment_date` (form) | Required, YYYY-MM-DD | Flash "Date is required", redirect back |
| `POST /assessments/` | `weight_kg` (form) | float or empty -> None, if present >= 0 | Flash "Invalid weight", redirect back |
| `POST /assessments/` | `height_cm` (form) | float or empty -> None, if present >= 0 | Flash "Invalid height", redirect back |
| `POST /assessments/` | `body_fat_pct` (form) | float or empty -> None, if present 0-100 | Flash "Body fat % must be 0-100", redirect back |
| `POST /assessments/` | `resting_heart_rate` (form) | int or empty -> None, if present >= 0 | Flash "Invalid heart rate", redirect back |
| `POST /membership-types/<id>/edit` | all fields | Same validation as create, plus `is_active` must be 0 or 1 | Same flash patterns as create |
| `POST /class-types/<id>/edit` | all fields | Same validation as create | Same flash patterns as create |
| `POST /schedules/<id>/edit` | all fields | Same validation as create | Same flash patterns as create |
| `POST /attendance/<id>/check-out` | `attendance_id` (URL) | Must exist, check_out_time must be NULL | Flash "Already checked out", redirect back |
| `POST /equipment/<id>/edit` | all fields | Same validation as create | Same flash patterns as create |
| `POST /maintenance/<id>/edit` | all fields | Same validation as create | Same flash patterns as create |
| `POST /assessments/<id>/edit` | all fields | Same validation as create | Same flash patterns as create |
| ALL `<int:*_id>` URL params | URL param | Must exist in DB after int parse | `abort(404)` |
| ALL delete routes | `*_id` (URL) | Must exist, try/except `sqlite3.IntegrityError` | Flash "Cannot delete: referenced by other records", redirect to list |

**Money parsing pattern (all agents MUST use this exact pattern):**
```python
import math
try:
    raw = float(request.form.get('amount', '0'))
    if math.isnan(raw) or math.isinf(raw):
        raise ValueError('Invalid amount')
    amount_cents = round(raw * 100)
    if amount_cents <= 0:
        flash('Amount must be positive.', 'error')
        return redirect(request.url)
    if amount_cents > 99999999:  # Cap at $999,999.99
        flash('Amount too large.', 'error')
        return redirect(request.url)
except (ValueError, TypeError):
    flash('Valid amount is required.', 'error')
    return redirect(request.url)
```

## Coordinated Behaviors

| # | Surface | Rule | Owner |
|---|---------|------|-------|
| 1 | Blueprint registration | All blueprints registered in `create_app()` with exact `url_prefix` values from Route Table | `core` agent |
| 2 | Navbar links | `base.html` includes links to ALL list endpoints with trailing slash. Grouped: Dashboard, Members, Trainers, Classes (types + schedules), Attendance, Equipment (+ maintenance), Billing (+ payments), Assessments | `layout` agent |
| 3 | Flash message display | `base.html` renders `get_flashed_messages(with_categories=true)`. Categories: 'success' (green), 'error' (red), 'info' (blue) | `layout` agent |
| 4 | Flash message authoring | Success: `flash('...created/updated/deleted successfully.', 'success')`. Error: `flash('...', 'error')`. ALL agents use EXACTLY these categories | ALL route agents |
| 5 | Login required | Every route handler (except auth + health) decorated with `@login_required` BEFORE `@bp.route` | ALL route agents |
| 6 | Delete confirmation | All delete buttons use a form with `onclick="return confirm('Are you sure?')"` | ALL route agents |
| 7 | 404 pattern | `item = get_item(conn, item_id)` then `if item is None: abort(404)` | ALL route agents |
| 8 | IntegrityError handling | Delete routes with RESTRICT FKs catch `sqlite3.IntegrityError` and flash "Cannot delete: referenced by other records." Routes where all child FKs are SET NULL or CASCADE do NOT need IntegrityError handling (delete_trainer, delete_membership_type). | Route agents with RESTRICT FK children |
| 9 | Trailing slashes | All navbar links and `url_for()` calls produce URLs with trailing slash for list endpoints (Flask handles this with `@bp.route('/')`) | ALL |
| 10 | No CSP header | Do NOT add Content-Security-Policy header. Bootstrap 5 loads from CDN. CSP would block it (FC38). | `core` agent |
| 11 | SQLite PRAGMAs | `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000` -- set in `get_db()`. No other connection paths exist. | `core` agent |
| 12 | Money display | All monetary values stored as INTEGER cents, displayed with `{{ value|dollars }}` filter | ALL agents with money |
| 13 | Date display | All dates displayed with `{{ value|date_format }}`, times with `{{ value|time_format }}` | ALL route agents |
| 14 | Form field naming | Form field `name` attributes must match exactly what `request.form.get()` uses in routes. Money fields: form has `name="price"` or `name="amount"` or `name="cost"`, route reads `request.form.get('price')` etc. | ALL route agents |
| 15 | Logout form | Navbar logout is a POST form with CSRF token, not a GET link | `layout` agent |

## Transaction Contracts

| Function | SQL Operations | Commits |
|----------|---------------|---------|
| `create_member` | INSERT INTO members | commits internally (`conn.commit()`) |
| `update_member` | UPDATE members | commits internally |
| `delete_member` | DELETE FROM members | commits internally |
| `create_trainer` | INSERT INTO trainers | commits internally |
| `update_trainer` | UPDATE trainers | commits internally |
| `delete_trainer` | DELETE FROM trainers | commits internally |
| `create_membership_type` | INSERT INTO membership_types | commits internally |
| `update_membership_type` | UPDATE membership_types | commits internally |
| `delete_membership_type` | DELETE FROM membership_types | commits internally |
| `create_class_type` | INSERT INTO class_types | commits internally |
| `update_class_type` | UPDATE class_types | commits internally |
| `delete_class_type` | DELETE FROM class_types | commits internally |
| `create_schedule` | INSERT INTO class_schedules | commits internally |
| `update_schedule` | UPDATE class_schedules | commits internally |
| `delete_schedule` | DELETE FROM class_schedules | commits internally |
| `copy_week_schedules` | Multiple INSERTs into class_schedules | commits internally (single transaction) |
| `check_in_class` | BEGIN IMMEDIATE + SELECT + INSERT + COMMIT | requires BEGIN IMMEDIATE (atomic capacity check) |
| `check_in_open_gym` | INSERT INTO attendance | commits internally |
| `check_out` | UPDATE attendance | commits internally |
| `delete_attendance` | DELETE FROM attendance | commits internally |
| `create_equipment` | INSERT INTO equipment | commits internally |
| `update_equipment` | UPDATE equipment | commits internally |
| `delete_equipment` | DELETE FROM equipment | commits internally |
| `create_maintenance` | INSERT INTO maintenance_log | commits internally |
| `update_maintenance` | UPDATE maintenance_log | commits internally |
| `delete_maintenance` | DELETE FROM maintenance_log | commits internally |
| `create_invoice` | INSERT INTO invoices | commits internally |
| `update_invoice` | UPDATE invoices | commits internally |
| `delete_invoice` | DELETE FROM invoices | commits internally |
| `create_payment` | INSERT INTO payments | commits internally |
| `delete_payment` | DELETE FROM payments | commits internally |
| `create_assessment` | INSERT INTO fitness_assessments | commits internally |
| `update_assessment` | UPDATE fitness_assessments | commits internally |
| `delete_assessment` | DELETE FROM fitness_assessments | commits internally |

**All read-only functions (get_*, count_*, search_*) do NOT commit.**

## Authorization Matrix

All routes are admin-only (single-user system). No role distinctions needed.

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
| `gymflow/app/__init__.py` | App factory with blueprint registration |
| `gymflow/app/db.py` | Database connection, init_db, close_db |
| `gymflow/app/auth.py` | login_required decorator, check_password |
| `gymflow/app/filters.py` | Jinja template filters (dollars, date_format, time_format) |
| `gymflow/app/models/__init__.py` | Barrel re-exports of ALL model functions |
| `gymflow/schema.sql` | Complete database schema |
| `gymflow/requirements.txt` | Python dependencies |
| `gymflow/.gitignore` | Git ignore patterns (include `*.db`, `__pycache__/`, `.venv/`, `test_smoke.py`) |

### layout agent
| File | Purpose |
|------|---------|
| `gymflow/app/templates/base.html` | Base template with navbar, flash messages, Bootstrap 5 CDN |
| `gymflow/app/static/style.css` | Custom styles |

### auth agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/auth/__init__.py` | Empty init |
| `gymflow/app/blueprints/auth/routes.py` | Login/logout routes |
| `gymflow/app/templates/auth/login.html` | Login form |

### member_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/member.py` | Member CRUD functions |

### trainer_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/trainer.py` | Trainer CRUD functions |

### membership_type_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/membership_type.py` | Membership type CRUD functions |

### class_type_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/class_type.py` | Class type CRUD functions |

### schedule_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/schedule.py` | Schedule CRUD + copy_week + attendance_count |

### attendance_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/attendance.py` | Attendance check-in/out + queries |

### equipment_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/equipment.py` | Equipment CRUD + needs_maintenance query |

### maintenance_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/maintenance.py` | Maintenance log CRUD |

### billing_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/invoice.py` | Invoice CRUD |

### payment_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/payment.py` | Payment CRUD + paid_amount + revenue |

### assessment_models agent
| File | Purpose |
|------|---------|
| `gymflow/app/models/assessment.py` | Fitness assessment CRUD + latest |

### member_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/members/__init__.py` | Empty init |
| `gymflow/app/blueprints/members/routes.py` | Member routes |
| `gymflow/app/templates/members/list.html` | Member list page |
| `gymflow/app/templates/members/detail.html` | Member detail with latest assessment |
| `gymflow/app/templates/members/form.html` | New/edit member form |

### trainer_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/trainers/__init__.py` | Empty init |
| `gymflow/app/blueprints/trainers/routes.py` | Trainer routes |
| `gymflow/app/templates/trainers/list.html` | Trainer list |
| `gymflow/app/templates/trainers/detail.html` | Trainer detail |
| `gymflow/app/templates/trainers/form.html` | New/edit trainer form |

### membership_type_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/membership_types/__init__.py` | Empty init |
| `gymflow/app/blueprints/membership_types/routes.py` | Membership type routes |
| `gymflow/app/templates/membership_types/list.html` | Types list with prices |
| `gymflow/app/templates/membership_types/form.html` | New/edit type form |

### class_type_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/class_types/__init__.py` | Empty init |
| `gymflow/app/blueprints/class_types/routes.py` | Class type routes |
| `gymflow/app/templates/class_types/list.html` | Class types list |
| `gymflow/app/templates/class_types/form.html` | New/edit class type form |

### schedule_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/schedules/__init__.py` | Empty init |
| `gymflow/app/blueprints/schedules/routes.py` | Schedule routes + copy week |
| `gymflow/app/templates/schedules/list.html` | Schedule list with date picker |
| `gymflow/app/templates/schedules/detail.html` | Schedule detail with attendees |
| `gymflow/app/templates/schedules/form.html` | New/edit schedule form |

### attendance_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/attendance/__init__.py` | Empty init |
| `gymflow/app/blueprints/attendance/routes.py` | Attendance check-in/out routes |
| `gymflow/app/templates/attendance/list.html` | Today's attendance list |
| `gymflow/app/templates/attendance/check_in.html` | Check-in form (member + class/open gym) |

### equipment_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/equipment/__init__.py` | Empty init |
| `gymflow/app/blueprints/equipment/routes.py` | Equipment routes |
| `gymflow/app/templates/equipment/list.html` | Equipment list |
| `gymflow/app/templates/equipment/detail.html` | Equipment detail with maintenance history |
| `gymflow/app/templates/equipment/form.html` | New/edit equipment form |

### maintenance_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/maintenance/__init__.py` | Empty init |
| `gymflow/app/blueprints/maintenance/routes.py` | Maintenance routes |
| `gymflow/app/templates/maintenance/list.html` | Maintenance log list |
| `gymflow/app/templates/maintenance/form.html` | New/edit maintenance form |

### billing_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/billing/__init__.py` | Empty init |
| `gymflow/app/blueprints/billing/routes.py` | Invoice routes |
| `gymflow/app/templates/billing/list.html` | Invoice list |
| `gymflow/app/templates/billing/detail.html` | Invoice detail with payments |
| `gymflow/app/templates/billing/form.html` | New/edit invoice form |

### payment_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/payments/__init__.py` | Empty init |
| `gymflow/app/blueprints/payments/routes.py` | Payment routes |
| `gymflow/app/templates/payments/list.html` | All payments list |
| `gymflow/app/templates/payments/form.html` | New payment form |

### assessment_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/assessments/__init__.py` | Empty init |
| `gymflow/app/blueprints/assessments/routes.py` | Assessment routes |
| `gymflow/app/templates/assessments/list.html` | Assessments list |
| `gymflow/app/templates/assessments/detail.html` | Assessment detail |
| `gymflow/app/templates/assessments/form.html` | New/edit assessment form |

### dashboard_routes agent
| File | Purpose |
|------|---------|
| `gymflow/app/blueprints/dashboard/__init__.py` | Empty init |
| `gymflow/app/blueprints/dashboard/routes.py` | Dashboard route |
| `gymflow/app/templates/dashboard/index.html` | Dashboard with stats and today's schedule |

## Swarm Agent Assignment

| # | Agent Name | Role | Files |
|---|-----------|------|-------|
| 1 | core | Infrastructure | `gymflow/app/__init__.py`, `gymflow/app/db.py`, `gymflow/app/auth.py`, `gymflow/app/filters.py`, `gymflow/app/models/__init__.py`, `gymflow/schema.sql`, `gymflow/requirements.txt`, `gymflow/.gitignore` |
| 2 | layout | Templates/CSS | `gymflow/app/templates/base.html`, `gymflow/app/static/style.css` |
| 3 | auth | Auth routes | `gymflow/app/blueprints/auth/__init__.py`, `gymflow/app/blueprints/auth/routes.py`, `gymflow/app/templates/auth/login.html` |
| 4 | member_models | Models | `gymflow/app/models/member.py` |
| 5 | trainer_models | Models | `gymflow/app/models/trainer.py` |
| 6 | membership_type_models | Models | `gymflow/app/models/membership_type.py` |
| 7 | class_type_models | Models | `gymflow/app/models/class_type.py` |
| 8 | schedule_models | Models | `gymflow/app/models/schedule.py` |
| 9 | attendance_models | Models | `gymflow/app/models/attendance.py` |
| 10 | equipment_models | Models | `gymflow/app/models/equipment.py` |
| 11 | maintenance_models | Models | `gymflow/app/models/maintenance.py` |
| 12 | billing_models | Models | `gymflow/app/models/invoice.py` |
| 13 | payment_models | Models | `gymflow/app/models/payment.py` |
| 14 | assessment_models | Models | `gymflow/app/models/assessment.py` |
| 15 | member_routes | Routes/Templates | `gymflow/app/blueprints/members/__init__.py`, `gymflow/app/blueprints/members/routes.py`, `gymflow/app/templates/members/list.html`, `gymflow/app/templates/members/detail.html`, `gymflow/app/templates/members/form.html` |
| 16 | trainer_routes | Routes/Templates | `gymflow/app/blueprints/trainers/__init__.py`, `gymflow/app/blueprints/trainers/routes.py`, `gymflow/app/templates/trainers/list.html`, `gymflow/app/templates/trainers/detail.html`, `gymflow/app/templates/trainers/form.html` |
| 17 | membership_type_routes | Routes/Templates | `gymflow/app/blueprints/membership_types/__init__.py`, `gymflow/app/blueprints/membership_types/routes.py`, `gymflow/app/templates/membership_types/list.html`, `gymflow/app/templates/membership_types/form.html` |
| 18 | class_type_routes | Routes/Templates | `gymflow/app/blueprints/class_types/__init__.py`, `gymflow/app/blueprints/class_types/routes.py`, `gymflow/app/templates/class_types/list.html`, `gymflow/app/templates/class_types/form.html` |
| 19 | schedule_routes | Routes/Templates | `gymflow/app/blueprints/schedules/__init__.py`, `gymflow/app/blueprints/schedules/routes.py`, `gymflow/app/templates/schedules/list.html`, `gymflow/app/templates/schedules/detail.html`, `gymflow/app/templates/schedules/form.html` |
| 20 | attendance_routes | Routes/Templates | `gymflow/app/blueprints/attendance/__init__.py`, `gymflow/app/blueprints/attendance/routes.py`, `gymflow/app/templates/attendance/list.html`, `gymflow/app/templates/attendance/check_in.html` |
| 21 | equipment_routes | Routes/Templates | `gymflow/app/blueprints/equipment/__init__.py`, `gymflow/app/blueprints/equipment/routes.py`, `gymflow/app/templates/equipment/list.html`, `gymflow/app/templates/equipment/detail.html`, `gymflow/app/templates/equipment/form.html` |
| 22 | maintenance_routes | Routes/Templates | `gymflow/app/blueprints/maintenance/__init__.py`, `gymflow/app/blueprints/maintenance/routes.py`, `gymflow/app/templates/maintenance/list.html`, `gymflow/app/templates/maintenance/form.html` |
| 23 | billing_routes | Routes/Templates | `gymflow/app/blueprints/billing/__init__.py`, `gymflow/app/blueprints/billing/routes.py`, `gymflow/app/templates/billing/list.html`, `gymflow/app/templates/billing/detail.html`, `gymflow/app/templates/billing/form.html` |
| 24 | payment_routes | Routes/Templates | `gymflow/app/blueprints/payments/__init__.py`, `gymflow/app/blueprints/payments/routes.py`, `gymflow/app/templates/payments/list.html`, `gymflow/app/templates/payments/form.html` |
| 25 | assessment_routes | Routes/Templates | `gymflow/app/blueprints/assessments/__init__.py`, `gymflow/app/blueprints/assessments/routes.py`, `gymflow/app/templates/assessments/list.html`, `gymflow/app/templates/assessments/detail.html`, `gymflow/app/templates/assessments/form.html` |
| 26 | dashboard_routes | Routes/Templates | `gymflow/app/blueprints/dashboard/__init__.py`, `gymflow/app/blueprints/dashboard/routes.py`, `gymflow/app/templates/dashboard/index.html` |

## Acceptance Tests

### Happy Path
- WHEN admin visits /login THE SYSTEM SHALL display a login form
- WHEN admin submits correct password THE SYSTEM SHALL redirect to dashboard
- WHEN admin visits / (dashboard) THE SYSTEM SHALL display active member count, revenue, today's schedule, recent check-ins, and equipment needing maintenance
- WHEN admin creates a new member THE SYSTEM SHALL store the member and redirect to detail page
- WHEN admin creates a new trainer THE SYSTEM SHALL store the trainer and redirect to detail page
- WHEN admin creates a membership type with price $49.99 THE SYSTEM SHALL store 4999 cents
- WHEN admin creates a class type THE SYSTEM SHALL store the type and redirect to list
- WHEN admin creates a class schedule THE SYSTEM SHALL store the session with date, time, trainer, capacity
- WHEN admin checks in a member to a class THE SYSTEM SHALL verify capacity and create attendance record
- WHEN admin checks in a member for open gym THE SYSTEM SHALL create attendance with null class_schedule_id
- WHEN admin checks out a member THE SYSTEM SHALL record check_out_time
- WHEN admin creates equipment THE SYSTEM SHALL store with price in cents
- WHEN admin logs a maintenance record THE SYSTEM SHALL store with cost in cents and link to equipment
- WHEN admin creates an invoice THE SYSTEM SHALL store amount in cents with due date
- WHEN admin records a payment THE SYSTEM SHALL store amount in cents linked to invoice
- WHEN admin creates a fitness assessment THE SYSTEM SHALL compute BMI automatically
- WHEN admin copies a week of schedules THE SYSTEM SHALL duplicate all sessions with updated dates

### Error Cases
- WHEN admin submits wrong password THE SYSTEM SHALL flash error and stay on login
- WHEN admin tries to check in to a full class THE SYSTEM SHALL flash "Class is full" and not create record
- WHEN admin tries to delete a member with attendance records THE SYSTEM SHALL flash "Cannot delete" error
- WHEN admin tries to delete equipment with maintenance records THE SYSTEM SHALL flash "Cannot delete" error
- WHEN admin tries to delete an invoice with payments THE SYSTEM SHALL flash "Cannot delete" error
- WHEN admin submits a form with missing required fields THE SYSTEM SHALL flash specific error and not create record
- WHEN admin visits a non-existent resource ID THE SYSTEM SHALL return 404

### Verification Commands
```
# Setup
cd gymflow
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Smoke test (see Smoke Test File section)
.venv/bin/python test_smoke.py
```

## Feed-Forward

- **Hardest decision:** Schedule model as individual sessions (not recurring).
  Simplifies queries and attendance tracking but requires admin to manually
  create or copy sessions. The copy-week feature mitigates the UX cost.
- **Rejected alternatives:** Multi-role auth (too complex for single-admin MVP),
  API-first architecture (unnecessary), automated billing (needs cron/email),
  recurring schedule engine (adds generator complexity).
- **Least confident:** Transaction boundary for `check_in_class` with BEGIN
  IMMEDIATE. The spec prescribes the exact 6-step implementation to prevent
  FC29, but the attendance_models agent must follow it precisely. If the
  agent skips BEGIN IMMEDIATE or adds conn.commit() in check_in_open_gym
  while using isolation_level=None, the behavior diverges. The
  spec-completeness-checker should catch this in the Transaction Contracts
  table.
