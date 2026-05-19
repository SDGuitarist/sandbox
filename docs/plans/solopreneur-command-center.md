---
name: Solopreneur Command Center — Implementation Plan
description: Full-stack Flask + SQLite + Jinja2 business OS for solopreneurs, 16-agent swarm
date: 2026-05-19
status: ready
swarm: true
agents: 16
estimated_spec_lines: 1200
brainstorm: docs/brainstorms/solopreneur-command-center-brainstorm.md
feed_forward:
  risk: "Activity log wiring across 16 agents — every module must INSERT into activity_log with exact same format. FC22 integration wiring gap."
  verify_first: true
---

# Solopreneur Command Center — Implementation Plan

## What is changing?
Building a complete Flask + SQLite + Jinja2 web application in `command-center/` directory. 16 swarm agents build 13 modules in parallel. The app is a single-user business operating system: auth, CRM, pipeline, projects, tasks, time tracking, revenue/expenses, goals, notes, reports, search, settings, and dashboard.

## What must NOT change?
- No modifications to files outside `command-center/` directory
- No changes to existing sandbox apps (client-portal, workshop-registration, etc.)
- No production database access
- No external API calls

## How will we know it worked?

### Acceptance Tests

#### Happy Path
- WHEN a user visits / without login THE SYSTEM SHALL redirect to /auth/login
- WHEN a user registers with valid email+password THE SYSTEM SHALL create account and redirect to /auth/setup
- WHEN a user completes setup wizard THE SYSTEM SHALL save business profile and redirect to /dashboard
- WHEN a user visits /dashboard THE SYSTEM SHALL display revenue snapshot, active projects, pipeline summary, overdue tasks, upcoming deadlines, hours this week, cash flow, and activity feed
- WHEN a user creates a contact THE SYSTEM SHALL save to database and redirect to contact detail page
- WHEN a user creates a deal and moves it to "Won" THE SYSTEM SHALL prompt to create a project pre-filled with client and value
- WHEN a user starts a timer THE SYSTEM SHALL store start time in localStorage and display elapsed time
- WHEN a user stops a timer THE SYSTEM SHALL create a time entry with calculated duration
- WHEN a user visits /reports/revenue THE SYSTEM SHALL display monthly revenue table with CSV export button
- WHEN a user presses "/" THE SYSTEM SHALL focus the search bar

#### Error Cases
- WHEN a user registers with existing email THE SYSTEM SHALL show "Email already registered" flash message
- WHEN a user submits a form without CSRF token THE SYSTEM SHALL return 400
- WHEN a user marks a deal as "Lost" without loss_reason THE SYSTEM SHALL show validation error
- WHEN a user accesses any page without login THE SYSTEM SHALL redirect to /auth/login

#### Verification Commands
- `cd command-center && .venv/bin/python run.py` — app starts without errors
- `curl -s http://localhost:5000/auth/login | grep "Login"` — returns login page
- `curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/dashboard` — returns 302 (redirect to login)

## What is the most likely way this plan is wrong?
The activity log wiring. 16 agents must all INSERT into activity_log with the same format string. The coordinated behaviors table prescribes it, but agents may still forget or diverge. The smoke test can verify the dashboard loads, but can't verify all 13 modules log activity. This will likely surface as "Recent Activity" showing gaps from some modules.

---

## Directory Structure

```
command-center/
  run.py
  config.py
  requirements.txt
  .gitignore
  app/
    __init__.py          # App factory
    db.py                # Database connection, init_db, get_db context manager
    models.py            # All model functions (CRUD for all 21 tables)
    schema.sql           # All CREATE TABLE + FTS5 + seed data
    decorators.py        # login_required, setup_required
    filters.py           # Jinja2 filters (dollars, minutes_to_hours, etc.)
    auth/
      __init__.py        # Blueprint registration
      routes.py          # Login, register, setup, logout
    contacts/
      __init__.py
      routes.py
    companies/
      __init__.py
      routes.py
    pipeline/
      __init__.py
      routes.py
    projects/
      __init__.py
      routes.py
    tasks/
      __init__.py
      routes.py
    time_tracking/
      __init__.py
      routes.py
    revenue/
      __init__.py
      routes.py
    goals/
      __init__.py
      routes.py
    notes/
      __init__.py
      routes.py
    reports/
      __init__.py
      routes.py
    search/
      __init__.py
      routes.py
    settings/
      __init__.py
      routes.py
    dashboard/
      __init__.py
      routes.py
    templates/
      base.html
      sidebar.html
      _flash_messages.html
      _quick_add_contact_modal.html
      _quick_add_task_modal.html
      auth/
        login.html
        register.html
        setup.html
      contacts/
        list.html
        detail.html
        form.html
      companies/
        list.html
        detail.html
        form.html
      pipeline/
        board.html
        list.html
        detail.html
        form.html
        stats.html
      projects/
        list.html
        detail.html
        form.html
        templates.html
      tasks/
        list.html
        my_day.html
        form.html
      time_tracking/
        entries.html
        timesheet.html
      revenue/
        income_list.html
        income_form.html
        expense_list.html
        expense_form.html
        pl.html
        by_client.html
        by_month.html
      goals/
        index.html
        history.html
      notes/
        journal.html
        list.html
        form.html
        search_results.html
      reports/
        index.html
        revenue.html
        client.html
        time.html
        pipeline.html
        utilization.html
        expense.html
      search/
        results.html
      settings/
        profile.html
        financial.html
        targets.html
        categories.html
        export.html
      dashboard/
        index.html
    static/
      css/
        style.css
      js/
        app.js           # Global: search, modals, keyboard shortcuts
        timer.js          # Time tracking timer
        pipeline.js       # Stage move buttons
        sort.js           # Table column sorting
```

---

## Shared Interface Spec

### 1. Database Schema (schema.sql)

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    setup_complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS business_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    business_name TEXT NOT NULL DEFAULT '',
    owner_name TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL DEFAULT 'other',
    currency_symbol TEXT NOT NULL DEFAULT '$',
    fiscal_year_start INTEGER NOT NULL DEFAULT 1,
    logo_url TEXT NOT NULL DEFAULT '',
    tagline TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    tax_id TEXT NOT NULL DEFAULT '',
    default_hourly_rate INTEGER NOT NULL DEFAULT 0,
    weekly_hours_target INTEGER NOT NULL DEFAULT 40,
    monthly_revenue_target INTEGER NOT NULL DEFAULT 0,  -- cents
    quarterly_revenue_target INTEGER NOT NULL DEFAULT 0,  -- cents
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    website TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    company_id INTEGER,
    role_title TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'other',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'lead',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS interaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'email',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS deal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    contact_id INTEGER,
    company_id INTEGER,
    value INTEGER NOT NULL DEFAULT 0,
    stage TEXT NOT NULL DEFAULT 'lead',
    probability_pct INTEGER NOT NULL DEFAULT 10,
    expected_close_date TEXT,
    notes TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    loss_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE SET NULL,
    FOREIGN KEY (company_id) REFERENCES company(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_id INTEGER,
    status TEXT NOT NULL DEFAULT 'not_started',
    type TEXT NOT NULL DEFAULT 'hourly',
    value INTEGER NOT NULL DEFAULT 0,
    hourly_rate INTEGER NOT NULL DEFAULT 0,
    start_date TEXT,
    target_end_date TEXT,
    actual_end_date TEXT,
    description TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    deal_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE SET NULL,
    FOREIGN KEY (deal_id) REFERENCES deal(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS milestone (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    project_id INTEGER,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'todo',
    due_date TEXT,
    estimated_hours REAL NOT NULL DEFAULT 0,
    tags TEXT NOT NULL DEFAULT '',
    is_recurring INTEGER NOT NULL DEFAULT 0,
    recurrence_interval TEXT,
    recurrence_days INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS time_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    project_id INTEGER NOT NULL,
    task_id INTEGER,
    minutes INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    billable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER NOT NULL DEFAULT 0,
    date TEXT NOT NULL,
    contact_id INTEGER,
    project_id INTEGER,
    category TEXT NOT NULL DEFAULT 'other',
    payment_method TEXT NOT NULL DEFAULT 'bank_transfer',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (contact_id) REFERENCES contact(id) ON DELETE SET NULL,
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS expense (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER NOT NULL DEFAULT 0,
    date TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    vendor TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    tax_deductible INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS income_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS expense_category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS goal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL UNIQUE,
    revenue_target INTEGER NOT NULL DEFAULT 0,
    hours_target INTEGER NOT NULL DEFAULT 0,
    revenue_actual INTEGER NOT NULL DEFAULT 0,
    hours_actual INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS journal_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS template_milestone (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    offset_days INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (template_id) REFERENCES project_template(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS template_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'medium',
    estimated_hours REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (template_id) REFERENCES project_template(id) ON DELETE CASCADE
);

-- FTS5 virtual table for notes search
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title, content, tags,
    content='note',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS journal_fts USING fts5(
    content,
    content='journal_entry',
    content_rowid='id'
);

-- Seed default categories
INSERT OR IGNORE INTO income_category (name, is_default) VALUES
    ('project_payment', 1), ('retainer', 1), ('consulting', 1), ('product_sale', 1), ('other', 1);

INSERT OR IGNORE INTO expense_category (name, is_default) VALUES
    ('software', 1), ('hardware', 1), ('office', 1), ('travel', 1),
    ('marketing', 1), ('education', 1), ('contractor', 1), ('other', 1);

-- FTS5 triggers for note sync
CREATE TRIGGER IF NOT EXISTS notes_fts_insert AFTER INSERT ON note BEGIN
    INSERT INTO notes_fts(rowid, title, content, tags) VALUES (new.id, new.title, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS notes_fts_update AFTER UPDATE ON note BEGIN
    UPDATE notes_fts SET title = new.title, content = new.content, tags = new.tags WHERE rowid = new.id;
END;
CREATE TRIGGER IF NOT EXISTS notes_fts_delete AFTER DELETE ON note BEGIN
    DELETE FROM notes_fts WHERE rowid = old.id;
END;

-- FTS5 triggers for journal sync
CREATE TRIGGER IF NOT EXISTS journal_fts_insert AFTER INSERT ON journal_entry BEGIN
    INSERT INTO journal_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS journal_fts_update AFTER UPDATE ON journal_entry BEGIN
    UPDATE journal_fts SET content = new.content WHERE rowid = new.id;
END;
CREATE TRIGGER IF NOT EXISTS journal_fts_delete AFTER DELETE ON journal_entry BEGIN
    DELETE FROM journal_fts WHERE rowid = old.id;
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contact_company ON contact(company_id);
CREATE INDEX IF NOT EXISTS idx_contact_status ON contact(status);
CREATE INDEX IF NOT EXISTS idx_deal_stage ON deal(stage);
CREATE INDEX IF NOT EXISTS idx_deal_contact ON deal(contact_id);
CREATE INDEX IF NOT EXISTS idx_project_contact ON project(contact_id);
CREATE INDEX IF NOT EXISTS idx_project_status ON project(status);
CREATE INDEX IF NOT EXISTS idx_task_project ON task(project_id);
CREATE INDEX IF NOT EXISTS idx_task_status ON task(status);
CREATE INDEX IF NOT EXISTS idx_task_due ON task(due_date);
CREATE INDEX IF NOT EXISTS idx_time_entry_project ON time_entry(project_id);
CREATE INDEX IF NOT EXISTS idx_time_entry_date ON time_entry(date);
CREATE INDEX IF NOT EXISTS idx_income_date ON income(date);
CREATE INDEX IF NOT EXISTS idx_income_contact ON income(contact_id);
CREATE INDEX IF NOT EXISTS idx_expense_date ON expense(date);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at);
CREATE INDEX IF NOT EXISTS idx_interaction_contact ON interaction(contact_id);
```

### 2. Database Connection (db.py)

```python
import sqlite3
from contextlib import contextmanager
from flask import g, current_app

DATABASE = None  # Set by init_app

def init_app(app):
    global DATABASE
    DATABASE = app.config['DATABASE']
    app.teardown_appcontext(close_db)

def get_raw_connection():
    """Get a raw sqlite3 connection. Caller manages lifecycle."""
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def get_db(immediate=False):
    """Context manager for database access. Always use with `with` syntax.

    Usage:
        with get_db() as db:
            rows = db.execute("SELECT * FROM contact").fetchall()

        with get_db(immediate=True) as db:
            db.execute("INSERT INTO contact ...")
            db.execute("INSERT INTO activity_log ...")
            # Auto-commits on exit, rolls back on exception
    """
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        if immediate:
            conn.commit()
    except Exception:
        if immediate:
            conn.rollback()
        raise
    finally:
        conn.close()

def init_db(app):
    """Initialize database schema. Call once at startup."""
    conn = None
    try:
        conn = sqlite3.connect(app.config['DATABASE'], timeout=10)
        result = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        assert result[0] == 'wal', f"WAL mode failed: {result[0]}"
        with open(app.config['SCHEMA_PATH']) as f:
            conn.executescript(f.read())
    finally:
        if conn:
            conn.close()
```

### 3. App Factory (app/__init__.py)

```python
import os
import secrets
from flask import Flask
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(24))
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['DATABASE'] = os.path.join(app.instance_path, 'command_center.db')
    app.config['SCHEMA_PATH'] = os.path.join(os.path.dirname(__file__), 'schema.sql')

    os.makedirs(app.instance_path, exist_ok=True)

    csrf.init_app(app)

    from . import db
    db.init_app(app)
    db.init_db(app)

    from . import filters
    filters.init_app(app)

    # Register blueprints -- paths are RELATIVE to url_prefix
    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from .contacts import bp as contacts_bp
    app.register_blueprint(contacts_bp, url_prefix='/contacts')

    from .companies import bp as companies_bp
    app.register_blueprint(companies_bp, url_prefix='/companies')

    from .pipeline import bp as pipeline_bp
    app.register_blueprint(pipeline_bp, url_prefix='/pipeline')

    from .projects import bp as projects_bp
    app.register_blueprint(projects_bp, url_prefix='/projects')

    from .tasks import bp as tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/tasks')

    from .time_tracking import bp as time_bp
    app.register_blueprint(time_bp, url_prefix='/time')

    from .revenue import bp as revenue_bp
    app.register_blueprint(revenue_bp, url_prefix='/revenue')

    from .goals import bp as goals_bp
    app.register_blueprint(goals_bp, url_prefix='/goals')

    from .notes import bp as notes_bp
    app.register_blueprint(notes_bp, url_prefix='/notes')

    from .reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    from .search import bp as search_bp
    app.register_blueprint(search_bp, url_prefix='/search')

    from .settings import bp as settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')

    from .dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    # Root redirect
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('dashboard.index'))

    return app
```

### 4. Blueprint __init__.py Template

Every blueprint uses this exact pattern:

```python
# app/{module}/__init__.py
from flask import Blueprint

bp = Blueprint('{module}', __name__)

from . import routes  # noqa: E402, F401
```

### 5. Jinja2 Filters (filters.py)

```python
def dollars(cents, symbol='$'):
    """Display integer cents as dollars. Usage: {{ amount|dollars }}"""
    if cents is None:
        return f'{symbol}0.00'
    return f'{symbol}{cents / 100:,.2f}'

def minutes_to_hours(minutes):
    """Display integer minutes as H:MM. Usage: {{ mins|minutes_to_hours }}"""
    if minutes is None:
        return '0:00'
    h = minutes // 60
    m = minutes % 60
    return f'{h}:{m:02d}'

def minutes_to_decimal(minutes):
    """Display integer minutes as decimal hours. Usage: {{ mins|minutes_to_decimal }}"""
    if minutes is None:
        return '0.0'
    return f'{minutes / 60:.1f}'

def init_app(app):
    app.jinja_env.filters['dollars'] = dollars
    app.jinja_env.filters['minutes_to_hours'] = minutes_to_hours
    app.jinja_env.filters['minutes_to_decimal'] = minutes_to_decimal
```

### 6. Decorators (decorators.py)

```python
from functools import wraps
from flask import session, redirect, url_for, flash
from .db import get_db

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def setup_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        with get_db() as db:
            user = db.execute("SELECT setup_complete FROM user WHERE id = ?",
                              (session['user_id'],)).fetchone()
            if not user or not user['setup_complete']:
                return redirect(url_for('auth.setup'))
        return f(*args, **kwargs)
    return decorated
```

### 7. Config (config.py)

```python
# Unused in MVP -- app factory handles config inline.
# Placeholder for future environment-specific configs.
```

### 8. run.py

```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

### 9. requirements.txt

```
flask>=3.0
flask-wtf>=1.2
bcrypt>=4.0
```

---

## Endpoint Registry

**CRITICAL: All agents MUST use these exact function names. Templates use the `url_for Name` column.**

**Route paths are RELATIVE to the blueprint url_prefix. `@bp.route("/")` NOT `@bp.route("/contacts/")`.**

### auth (prefix: /auth)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| login | GET,POST | /login | auth.login |
| register | GET,POST | /register | auth.register |
| setup | GET,POST | /setup | auth.setup |
| logout | POST | /logout | auth.logout |

### contacts (prefix: /contacts)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | contacts.index |
| detail | GET | /\<int:id\> | contacts.detail |
| create | GET,POST | /new | contacts.create |
| edit | GET,POST | /\<int:id\>/edit | contacts.edit |
| delete | POST | /\<int:id\>/delete | contacts.delete |
| add_interaction | POST | /\<int:id\>/interaction | contacts.add_interaction |
| quick_add | POST | /quick-add | contacts.quick_add |

### companies (prefix: /companies)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | companies.index |
| detail | GET | /\<int:id\> | companies.detail |
| create | GET,POST | /new | companies.create |
| edit | GET,POST | /\<int:id\>/edit | companies.edit |
| delete | POST | /\<int:id\>/delete | companies.delete |

### pipeline (prefix: /pipeline)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| board | GET | / | pipeline.board |
| list_view | GET | /list | pipeline.list_view |
| detail | GET | /\<int:id\> | pipeline.detail |
| create | GET,POST | /new | pipeline.create |
| edit | GET,POST | /\<int:id\>/edit | pipeline.edit |
| delete | POST | /\<int:id\>/delete | pipeline.delete |
| move_stage | POST | /\<int:id\>/move | pipeline.move_stage |
| stats | GET | /stats | pipeline.stats |

### projects (prefix: /projects)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | projects.index |
| detail | GET | /\<int:id\> | projects.detail |
| create | GET,POST | /new | projects.create |
| edit | GET,POST | /\<int:id\>/edit | projects.edit |
| delete | POST | /\<int:id\>/delete | projects.delete |
| add_milestone | POST | /\<int:id\>/milestone | projects.add_milestone |
| complete_milestone | POST | /milestone/\<int:id\>/complete | projects.complete_milestone |
| templates | GET | /templates | projects.templates |
| save_template | POST | /\<int:id\>/save-template | projects.save_template |
| create_from_template | POST | /from-template/\<int:template_id\> | projects.create_from_template |

### tasks (prefix: /tasks)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | tasks.index |
| my_day | GET | /my-day | tasks.my_day |
| create | GET,POST | /new | tasks.create |
| edit | GET,POST | /\<int:id\>/edit | tasks.edit |
| delete | POST | /\<int:id\>/delete | tasks.delete |
| complete | POST | /\<int:id\>/complete | tasks.complete |
| quick_add | POST | /quick-add | tasks.quick_add |

### time_tracking (prefix: /time)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | time_tracking.index |
| create | GET,POST | /new | time_tracking.create |
| edit | GET,POST | /\<int:id\>/edit | time_tracking.edit |
| delete | POST | /\<int:id\>/delete | time_tracking.delete |
| timesheet | GET | /timesheet | time_tracking.timesheet |
| start_timer | POST | /start | time_tracking.start_timer |
| stop_timer | POST | /stop | time_tracking.stop_timer |

### revenue (prefix: /revenue)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | revenue.index |
| add_income | GET,POST | /income/new | revenue.add_income |
| edit_income | GET,POST | /income/\<int:id\>/edit | revenue.edit_income |
| delete_income | POST | /income/\<int:id\>/delete | revenue.delete_income |
| add_expense | GET,POST | /expense/new | revenue.add_expense |
| edit_expense | GET,POST | /expense/\<int:id\>/edit | revenue.edit_expense |
| delete_expense | POST | /expense/\<int:id\>/delete | revenue.delete_expense |
| pl | GET | /pl | revenue.pl |
| by_client | GET | /by-client | revenue.by_client |
| by_month | GET | /by-month | revenue.by_month |

### goals (prefix: /goals)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | goals.index |
| update | POST | /update | goals.update |
| history | GET | /history | goals.history |

Note: `goal.hours_target` is stored in plain hours (integer). `goal.hours_actual` is stored in minutes (synced from time_entry totals). Dashboard must convert: `hours_actual / 60` for comparison with `hours_target`.

### notes (prefix: /notes)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| journal | GET | /journal | notes.journal |
| save_journal | POST | /journal | notes.save_journal |
| note_list | GET | / | notes.note_list |
| create_note | GET,POST | /new | notes.create_note |
| edit_note | GET,POST | /\<int:id\>/edit | notes.edit_note |
| delete_note | POST | /\<int:id\>/delete | notes.delete_note |
| search_notes | GET | /search | notes.search_notes |

### reports (prefix: /reports)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | reports.index |
| revenue_report | GET | /revenue | reports.revenue_report |
| client_report | GET | /client | reports.client_report |
| time_report | GET | /time | reports.time_report |
| pipeline_report | GET | /pipeline | reports.pipeline_report |
| utilization_report | GET | /utilization | reports.utilization_report |
| expense_report | GET | /expense | reports.expense_report |
| export_csv | GET | /export/\<module\> | reports.export_csv |

### search (prefix: /search)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| search | GET | / | search.search |
| api_search | GET | /api | search.api_search |

### settings (prefix: /settings)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| profile | GET,POST | /profile | settings.profile |
| financial | GET,POST | /financial | settings.financial |
| targets | GET,POST | /targets | settings.targets |
| categories | GET,POST | /categories | settings.categories |
| export_data | GET | /export | settings.export_data |
| export_module | GET | /export/\<module\> | settings.export_module |

Note: `settings.export_module` is a file download route — returns `Response` with `text/csv` content type and `Content-Disposition: attachment`. No template needed.

### dashboard (prefix: /dashboard)
| Function | Method | Path | url_for Name |
|----------|--------|------|-------------|
| index | GET | / | dashboard.index |

---

## Data Ownership Table

**Writer = the ONLY agent that INSERTs/UPDATEs/DELETEs this table.**
**Reader = agents that SELECT from this table.**

| Table | Writer Agent | Reader Agents |
|-------|-------------|---------------|
| user | auth | all (via session) |
| business_profile | auth, settings | dashboard, reports, revenue |
| company | companies | contacts, pipeline, search |
| contact | contacts | pipeline, projects, time_tracking, revenue, reports, search, dashboard |
| interaction | contacts | contacts (detail page) |
| deal | pipeline | projects (create from won deal), reports, search, dashboard |
| project | projects | tasks, time_tracking, revenue, reports, search, dashboard |
| milestone | projects | projects (detail page), dashboard |
| task | tasks | projects (detail page), time_tracking, dashboard, search |
| time_entry | time_tracking | projects (detail page), revenue, reports, dashboard |
| income | revenue | reports, dashboard, goals |
| expense | revenue | reports, dashboard |
| income_category | core-infra (seed), settings | revenue |
| expense_category | core-infra (seed), settings | revenue |
| goal | goals | dashboard |
| journal_entry | notes | notes, search |
| note | notes | search |
| activity_log | ALL modules (see Coordinated Behaviors) | dashboard |
| project_template | projects | projects |
| template_milestone | projects | projects |
| template_task | projects | projects |
| notes_fts | notes | search, notes |
| journal_fts | notes | search, notes |

---

## Coordinated Behaviors Table

**Every agent that writes to a table MUST follow these patterns exactly.**

### Activity Log Insert
Every create/update/delete operation inserts into activity_log. Use this exact pattern:

```python
db.execute(
    "INSERT INTO activity_log (action, entity_type, entity_id, description) VALUES (?, ?, ?, ?)",
    (action, entity_type, entity_id, description)
)
```

| Module | Action | entity_type | Description Format |
|--------|--------|-------------|-------------------|
| contacts | created | contact | "Created contact {name}" |
| contacts | updated | contact | "Updated contact {name}" |
| contacts | deleted | contact | "Deleted contact {name}" |
| companies | created | company | "Created company {name}" |
| pipeline | created | deal | "Created deal {title}" |
| pipeline | moved | deal | "Moved deal {title} to {stage}" |
| pipeline | won | deal | "Won deal {title} ({value})" |
| pipeline | lost | deal | "Lost deal {title}" |
| projects | created | project | "Created project {name}" |
| projects | updated | project | "Updated project {name}" |
| projects | completed | project | "Completed project {name}" |
| tasks | created | task | "Created task {title}" |
| tasks | completed | task | "Completed task {title}" |
| time_tracking | logged | time_entry | "Logged {hours}h on {project}" |
| revenue | income_added | income | "Added income {amount} from {contact}" |
| revenue | expense_added | expense | "Added expense {amount} for {category}" |
| notes | journal_saved | journal_entry | "Updated journal for {date}" |
| notes | note_created | note | "Created note {title}" |
| goals | updated | goal | "Updated goals for {month}" |
| settings | updated | business_profile | "Updated business profile" |

### Flash Messages
All modules use flash categories: `success`, `error`, `warning`, `info`.

```python
flash("Contact created successfully.", "success")
flash("Invalid email address.", "error")
```

### Validation Pattern
All POST routes validate input before database writes:

```python
@bp.route('/new', methods=['GET', 'POST'])
@setup_required
def create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Name is required.", "error")
            return render_template('{module}/form.html', ...)
        # ... proceed with database write
```

### Money Input Conversion
All money fields convert from form dollars to integer cents:

```python
# Form input → cents
value_str = request.form.get('value', '0')
try:
    value = int(float(value_str) * 100)
except (ValueError, TypeError):
    value = 0

# Cents → form prefill
form_value = '%.2f' % (row['value'] / 100) if row['value'] else '0.00'
```

### Time Input Conversion
Time fields convert from decimal hours to integer minutes:

```python
# Form input → minutes
hours_str = request.form.get('hours', '0')
try:
    minutes = int(float(hours_str) * 60)
except (ValueError, TypeError):
    minutes = 0

# Minutes → form prefill
form_hours = '%.1f' % (row['minutes'] / 60) if row['minutes'] else '0.0'
```

---

## Model Functions (models.py)

All model functions are plain functions (no classes). Each returns either a sqlite3.Row, a list of sqlite3.Row, an integer ID, or None. **Agents must match the return type exactly when naming variables.**

### Key Function Signatures and Usage

```python
# Returns int -- usage: contact_id = create_contact(db, ...)
def create_contact(db, name, email='', phone='', company_id=None,
                   role_title='', tags='', source='other', notes='', status='lead'):

# Returns Row or None -- usage: contact = get_contact(db, contact_id)
def get_contact(db, contact_id):

# Returns list[Row] -- usage: contacts = list_contacts(db, search='', status='', tag='')
def list_contacts(db, search='', status='', tag='', sort='name', order='asc'):

# Returns int -- usage: company_id = create_company(db, ...)
def create_company(db, name, website='', industry='', address='', notes=''):

# Returns int -- usage: deal_id = create_deal(db, ...)
def create_deal(db, title, contact_id=None, company_id=None, value=0,
                stage='lead', probability_pct=10, expected_close_date=None, notes='', source=''):

# Returns int -- usage: project_id = create_project(db, ...)
def create_project(db, name, contact_id=None, status='not_started', type='hourly',
                   value=0, hourly_rate=0, start_date=None, target_end_date=None,
                   description='', notes='', deal_id=None):

# Returns int -- usage: task_id = create_task(db, ...)
def create_task(db, title, description='', project_id=None, priority='medium',
                status='todo', due_date=None, estimated_hours=0, tags='',
                is_recurring=0, recurrence_interval=None, recurrence_days=0):

# Returns int -- usage: entry_id = create_time_entry(db, ...)
def create_time_entry(db, date, project_id, task_id=None, minutes=0,
                      description='', billable=1):

# Returns int -- usage: income_id = create_income(db, ...)
def create_income(db, amount, date, contact_id=None, project_id=None,
                  category='other', payment_method='bank_transfer', notes=''):

# Returns int -- usage: expense_id = create_expense(db, ...)
def create_expense(db, amount, date, category='other', vendor='', notes='',
                   tax_deductible=0):

# -- All create_* functions: db.execute("INSERT ..."); return db.execute("SELECT last_insert_rowid()").fetchone()[0]
# -- All get_* functions: return db.execute("SELECT ... WHERE id = ?", (id,)).fetchone()
# -- All list_* functions: return db.execute("SELECT ...").fetchall()
# -- All update_* functions: db.execute("UPDATE ... WHERE id = ?", ...); return None
# -- All delete_* functions: db.execute("DELETE FROM ... WHERE id = ?", (id,)); return None
```

### Dashboard Query Functions

```python
def get_revenue_snapshot(db):
    """Returns dict with keys: this_month (cents), last_month (cents), ytd (cents), target (cents), pct_to_target (float 0-100).
    Reads monthly_revenue_target from business_profile. No user_id needed (single-user app)."""

def get_active_projects_summary(db):
    """Returns dict with keys: count, total_value"""

def get_pipeline_summary(db):
    """Returns dict with keys: total_deals, total_value, closing_this_month"""

def get_overdue_tasks(db, limit=5):
    """Returns list[Row] of tasks where due_date < today and status != 'done'"""

def get_upcoming_deadlines(db, days=7):
    """Returns list[Row] of tasks+milestones due in next N days"""

def get_hours_this_week(db):
    """Returns dict with keys: logged, target"""

def get_cash_flow(db):
    """Returns dict with keys: income, expenses, net"""

def get_recent_activity(db, limit=10):
    """Returns list[Row] from activity_log ORDER BY created_at DESC LIMIT N"""
```

---

## Pipeline Stage Configuration

```python
PIPELINE_STAGES = [
    ('lead', 'Lead', 10),
    ('discovery', 'Discovery', 25),
    ('proposal_sent', 'Proposal Sent', 50),
    ('negotiation', 'Negotiation', 65),
    ('verbal_yes', 'Verbal Yes', 80),
    ('won', 'Won', 100),
    ('lost', 'Lost', 0),
]

# Usage: defined in models.py, imported by pipeline routes
STAGE_MAP = {s[0]: {'label': s[1], 'probability': s[2]} for s in PIPELINE_STAGES}
```

---

## Swarm Agent Assignment

| Agent | Role | Files Owned |
|-------|------|-------------|
| core-infra | Database, models, app factory | `command-center/app/__init__.py`, `command-center/app/db.py`, `command-center/app/models.py`, `command-center/app/schema.sql`, `command-center/app/decorators.py`, `command-center/app/filters.py`, `command-center/config.py`, `command-center/run.py`, `command-center/requirements.txt`, `command-center/.gitignore` |
| auth | Authentication, setup wizard | `command-center/app/auth/__init__.py`, `command-center/app/auth/routes.py`, `command-center/app/templates/auth/login.html`, `command-center/app/templates/auth/register.html`, `command-center/app/templates/auth/setup.html` |
| layout-static | Base template, sidebar, CSS, JS | `command-center/app/templates/base.html`, `command-center/app/templates/sidebar.html`, `command-center/app/templates/_flash_messages.html`, `command-center/app/templates/_quick_add_contact_modal.html`, `command-center/app/templates/_quick_add_task_modal.html`, `command-center/app/static/css/style.css`, `command-center/app/static/js/app.js`, `command-center/app/static/js/timer.js`, `command-center/app/static/js/pipeline.js`, `command-center/app/static/js/sort.js` |
| contacts | Contact CRUD + interactions | `command-center/app/contacts/__init__.py`, `command-center/app/contacts/routes.py`, `command-center/app/templates/contacts/list.html`, `command-center/app/templates/contacts/detail.html`, `command-center/app/templates/contacts/form.html` |
| companies | Company CRUD | `command-center/app/companies/__init__.py`, `command-center/app/companies/routes.py`, `command-center/app/templates/companies/list.html`, `command-center/app/templates/companies/detail.html`, `command-center/app/templates/companies/form.html` |
| pipeline | Deal CRUD, board, stats | `command-center/app/pipeline/__init__.py`, `command-center/app/pipeline/routes.py`, `command-center/app/templates/pipeline/board.html`, `command-center/app/templates/pipeline/list.html`, `command-center/app/templates/pipeline/detail.html`, `command-center/app/templates/pipeline/form.html`, `command-center/app/templates/pipeline/stats.html` |
| projects | Project CRUD, milestones, templates | `command-center/app/projects/__init__.py`, `command-center/app/projects/routes.py`, `command-center/app/templates/projects/list.html`, `command-center/app/templates/projects/detail.html`, `command-center/app/templates/projects/form.html`, `command-center/app/templates/projects/templates.html` |
| tasks | Task CRUD, My Day, recurring | `command-center/app/tasks/__init__.py`, `command-center/app/tasks/routes.py`, `command-center/app/templates/tasks/list.html`, `command-center/app/templates/tasks/my_day.html`, `command-center/app/templates/tasks/form.html` |
| time-tracking | Time entries, timesheet, timer | `command-center/app/time_tracking/__init__.py`, `command-center/app/time_tracking/routes.py`, `command-center/app/templates/time_tracking/entries.html`, `command-center/app/templates/time_tracking/timesheet.html` |
| revenue | Income/expense CRUD, P&L, reports | `command-center/app/revenue/__init__.py`, `command-center/app/revenue/routes.py`, `command-center/app/templates/revenue/income_list.html`, `command-center/app/templates/revenue/income_form.html`, `command-center/app/templates/revenue/expense_list.html`, `command-center/app/templates/revenue/expense_form.html`, `command-center/app/templates/revenue/pl.html`, `command-center/app/templates/revenue/by_client.html`, `command-center/app/templates/revenue/by_month.html` |
| goals | Goals + targets + history | `command-center/app/goals/__init__.py`, `command-center/app/goals/routes.py`, `command-center/app/templates/goals/index.html`, `command-center/app/templates/goals/history.html` |
| notes | Journal, notes, FTS search | `command-center/app/notes/__init__.py`, `command-center/app/notes/routes.py`, `command-center/app/templates/notes/journal.html`, `command-center/app/templates/notes/list.html`, `command-center/app/templates/notes/form.html`, `command-center/app/templates/notes/search_results.html` |
| reports | All 6 reports + CSV export | `command-center/app/reports/__init__.py`, `command-center/app/reports/routes.py`, `command-center/app/templates/reports/index.html`, `command-center/app/templates/reports/revenue.html`, `command-center/app/templates/reports/client.html`, `command-center/app/templates/reports/time.html`, `command-center/app/templates/reports/pipeline.html`, `command-center/app/templates/reports/utilization.html`, `command-center/app/templates/reports/expense.html` |
| search | Global search + API | `command-center/app/search/__init__.py`, `command-center/app/search/routes.py`, `command-center/app/templates/search/results.html` |
| settings | Profile, financial, categories, export | `command-center/app/settings/__init__.py`, `command-center/app/settings/routes.py`, `command-center/app/templates/settings/profile.html`, `command-center/app/templates/settings/financial.html`, `command-center/app/templates/settings/targets.html`, `command-center/app/templates/settings/categories.html`, `command-center/app/templates/settings/export.html` |
| dashboard | Main dashboard + Chart.js | `command-center/app/dashboard/__init__.py`, `command-center/app/dashboard/routes.py`, `command-center/app/templates/dashboard/index.html` |

**Total: 16 agents, ~100 files**

---

## Template Render Context

**Every render_template call must use these EXACT variable names.**

### auth
```python
# login.html — no extra context
render_template('auth/login.html')

# register.html — no extra context
render_template('auth/register.html')

# setup.html — industries list
render_template('auth/setup.html',
    industries=['consulting', 'design', 'development', 'coaching', 'marketing', 'other'])
```

### contacts
```python
# list.html
render_template('contacts/list.html',
    contacts=contacts,  # list[Row]
    search=search,  # str
    status_filter=status_filter,  # str
    statuses=['lead', 'active_client', 'past_client', 'partner'],
    companies=companies)  # list[Row] for filter dropdown

# detail.html
render_template('contacts/detail.html',
    contact=contact,  # Row
    company=company,  # Row or None
    interactions=interactions,  # list[Row]
    projects=projects,  # list[Row]
    total_revenue=total_revenue,  # int (cents)
    total_hours=total_hours)  # int (minutes)

# form.html (create and edit)
render_template('contacts/form.html',
    contact=contact,  # Row or None (None for create)
    companies=companies,  # list[Row]
    statuses=['lead', 'active_client', 'past_client', 'partner'],
    sources=['referral', 'website', 'social', 'cold_outreach', 'other'])
```

### companies
```python
# list.html
render_template('companies/list.html', companies=companies)

# detail.html
render_template('companies/detail.html',
    company=company,  # Row
    contacts=contacts)  # list[Row]

# form.html
render_template('companies/form.html', company=company)  # Row or None
```

### pipeline
```python
# board.html
render_template('pipeline/board.html',
    stages=stages,  # list of dicts: {key, label, probability, deals, total_value, weighted_value}
    contacts=contacts)  # list[Row] for filter

# list.html
render_template('pipeline/list.html',
    deals=deals,  # list[Row]
    stages=PIPELINE_STAGES)

# detail.html
render_template('pipeline/detail.html',
    deal=deal,  # Row
    contact=contact,  # Row or None
    company=company,  # Row or None
    stages=PIPELINE_STAGES)

# form.html
render_template('pipeline/form.html',
    deal=deal,  # Row or None
    contacts=contacts,  # list[Row]
    companies=companies,  # list[Row]
    stages=PIPELINE_STAGES,
    sources=['referral', 'website', 'social', 'cold_outreach', 'other'])

# stats.html
render_template('pipeline/stats.html',
    stage_stats=stage_stats,  # list of dicts
    total_weighted=total_weighted,  # int (cents)
    closing_this_month=closing_this_month,  # list[Row]
    win_rate=win_rate)  # float (0-100)
```

### projects
```python
# list.html
render_template('projects/list.html',
    projects=projects,  # list[Row]
    contacts=contacts,  # list[Row]
    status_filter=status_filter,
    statuses=['not_started', 'in_progress', 'on_hold', 'completed', 'cancelled'],
    types=['fixed_price', 'hourly', 'retainer', 'pro_bono'])

# detail.html
render_template('projects/detail.html',
    project=project,  # Row
    contact=contact,  # Row or None
    milestones=milestones,  # list[Row]
    tasks=tasks,  # list[Row]
    time_entries=time_entries,  # list[Row]
    total_hours=total_hours,  # int (minutes)
    billable_hours=billable_hours,  # int (minutes)
    budget_spent=budget_spent)  # int (cents)

# form.html
render_template('projects/form.html',
    project=project,  # Row or None
    contacts=contacts,  # list[Row]
    statuses=['not_started', 'in_progress', 'on_hold', 'completed', 'cancelled'],
    types=['fixed_price', 'hourly', 'retainer', 'pro_bono'],
    deal_id=deal_id)  # int or None (pre-fill from won deal)

# templates.html
render_template('projects/templates.html',
    templates=templates)  # list[Row]
```

### tasks
```python
# list.html
render_template('tasks/list.html',
    tasks=tasks,  # list[Row]
    projects=projects,  # list[Row]
    priority_filter=priority_filter,
    status_filter=status_filter,
    priorities=['low', 'medium', 'high', 'urgent'],
    statuses=['todo', 'in_progress', 'done'])

# my_day.html
render_template('tasks/my_day.html',
    tasks=tasks)  # list[Row] — today + overdue, ordered by priority

# form.html
render_template('tasks/form.html',
    task=task,  # Row or None
    projects=projects,  # list[Row]
    priorities=['low', 'medium', 'high', 'urgent'],
    statuses=['todo', 'in_progress', 'done'])
```

### time_tracking
```python
# entries.html
render_template('time_tracking/entries.html',
    entries=entries,  # list[Row]
    projects=projects,  # list[Row]
    tasks=tasks,  # list[Row]
    total_hours=total_hours,  # int (minutes)
    billable_hours=billable_hours)  # int (minutes)

# timesheet.html
render_template('time_tracking/timesheet.html',
    week_data=week_data,  # dict: {project_name: {mon: mins, tue: mins, ...}}
    week_start=week_start,  # str (date)
    week_end=week_end,  # str (date)
    projects=projects,  # list[Row]
    total_week=total_week,  # int (minutes)
    target=target)  # int (minutes)
```

### revenue
```python
# income_list.html
render_template('revenue/income_list.html',
    incomes=incomes,  # list[Row]
    total=total)  # int (cents)

# income_form.html
render_template('revenue/income_form.html',
    income=income,  # Row or None
    contacts=contacts,  # list[Row]
    projects=projects,  # list[Row]
    categories=categories)  # list[Row]

# expense_list.html
render_template('revenue/expense_list.html',
    expenses=expenses,  # list[Row]
    total=total)  # int (cents)

# expense_form.html
render_template('revenue/expense_form.html',
    expense=expense,  # Row or None
    categories=categories)  # list[Row]

# pl.html
render_template('revenue/pl.html',
    months=months,  # list of dicts: {month, income, expenses, profit, margin_pct}
    ytd_income=ytd_income,  # int (cents)
    ytd_expenses=ytd_expenses,  # int (cents)
    ytd_profit=ytd_profit)  # int (cents)

# by_client.html
render_template('revenue/by_client.html',
    clients=clients)  # list of dicts: {contact_name, total_revenue (cents), project_count, avg_value (cents)}

# by_month.html
render_template('revenue/by_month.html',
    months=months)  # list of dicts: {month, income (cents), expenses (cents), profit (cents), margin_pct}
```

### goals
```python
# index.html
render_template('goals/index.html',
    current_month=current_month,  # str (YYYY-MM)
    revenue_target=revenue_target,  # int (cents)
    revenue_actual=revenue_actual,  # int (cents)
    hours_target=hours_target,  # int
    hours_actual=hours_actual,  # int (minutes)
    quarterly_target=quarterly_target)  # int (cents)

# history.html
render_template('goals/history.html',
    goals=goals)  # list[Row]
```

### notes
```python
# journal.html
render_template('notes/journal.html',
    entry=entry,  # Row or None
    date=date)  # str (YYYY-MM-DD, default today)

# list.html
render_template('notes/list.html',
    notes=notes)  # list[Row]

# form.html
render_template('notes/form.html',
    note=note)  # Row or None

# search_results.html
render_template('notes/search_results.html',
    results=results,  # list[Row]
    query=query)  # str
```

### reports
```python
# index.html — links to all reports
render_template('reports/index.html')

# revenue.html
render_template('reports/revenue.html',
    months=months,  # list of dicts
    start_date=start_date,
    end_date=end_date,
    client_filter=client_filter,
    contacts=contacts)  # list[Row]

# client.html
render_template('reports/client.html',
    clients=clients)  # list of dicts: {contact, revenue, projects, avg_value, last_interaction}

# time.html
render_template('reports/time.html',
    by_project=by_project,  # list of dicts
    by_week=by_week,  # list of dicts
    billable_total=billable_total,  # int (minutes)
    non_billable_total=non_billable_total)  # int (minutes)

# pipeline.html
render_template('reports/pipeline.html',
    win_rate=win_rate,  # float
    avg_deal_size=avg_deal_size,  # int (cents)
    avg_days_to_close=avg_days_to_close,  # int
    forecast=forecast)  # list of dicts: {month, weighted_value}

# utilization.html
render_template('reports/utilization.html',
    weeks=weeks,  # list of dicts: {week_start, billable, total, rate, target}
    avg_rate=avg_rate)  # float

# expense.html
render_template('reports/expense.html',
    by_category=by_category,  # list of dicts
    by_month=by_month,  # list of dicts
    tax_deductible_total=tax_deductible_total)  # int (cents)
```

### search
```python
# results.html
render_template('search/results.html',
    query=query,  # str
    contacts=contacts,  # list[Row]
    projects=projects,  # list[Row]
    tasks=tasks,  # list[Row]
    deals=deals,  # list[Row]
    notes=notes)  # list[Row]
```

### settings
```python
# profile.html
render_template('settings/profile.html',
    profile=profile)  # Row

# financial.html
render_template('settings/financial.html',
    profile=profile)  # Row

# targets.html
render_template('settings/targets.html',
    profile=profile)  # Row

# categories.html
render_template('settings/categories.html',
    income_categories=income_categories,  # list[Row]
    expense_categories=expense_categories)  # list[Row]

# export.html
render_template('settings/export.html',
    modules=['contacts', 'companies', 'deals', 'projects', 'tasks',
             'time_entries', 'income', 'expenses', 'notes', 'journal'])
```

### dashboard
```python
# index.html
render_template('dashboard/index.html',
    revenue=revenue,  # dict: {this_month, last_month, ytd, target, pct_to_target}
    projects=projects,  # dict: {count, total_value}
    pipeline=pipeline,  # dict: {total_deals, total_value, closing_this_month}
    overdue_tasks=overdue_tasks,  # list[Row]
    upcoming=upcoming,  # list[Row]
    hours=hours,  # dict: {logged, target}
    cash_flow=cash_flow,  # dict: {income, expenses, net}
    activity=activity,  # list[Row]
    profile=profile)  # Row (for currency_symbol)
```

---

## Transaction Boundary Rules

1. **Default: functions do NOT commit.** The route handler wraps the entire operation in `with get_db(immediate=True) as db:` and commit happens automatically on context exit.
2. **Read-only routes** use `with get_db() as db:` (no immediate, no commit).
3. **Multi-step writes** (e.g., deal→project conversion): wrap in a SINGLE `with get_db(immediate=True) as db:` block. Both the deal update and project creation happen in one transaction.
4. **Activity log insert** is part of the same transaction as the data write. Never in a separate `get_db()` block.

---

## CSS / UI Notes for layout-static Agent

- Dark sidebar: `#1a1d23` background, `#e4e6eb` text, `280px` width fixed
- Active nav item: `#2d3139` background, `#4f8ef7` left border accent
- Content area: `#f8f9fa` background, `#212529` text
- Cards: white background, subtle `box-shadow: 0 1px 3px rgba(0,0,0,0.1)`
- Tables: Bootstrap 5 `.table .table-hover .table-sm`, compact
- Status badges: `.badge` with `bg-success` (active/done/won), `bg-warning text-dark` (in_progress/pending), `bg-danger` (overdue/urgent/lost), `bg-secondary` (inactive/cancelled)
- Bootstrap 5 CDN: `https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css`
- Bootstrap Icons CDN: `https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css`
- Chart.js CDN: `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`

---

## Feed-Forward

- **Hardest decision:** How to split 100 files across 16 agents. Vertical split by blueprint keeps each agent self-contained, but the dashboard agent and reports agent are pure consumers of other agents' data — they can't test until assembly. The core-infra agent owns models.py which every other agent depends on.
- **Rejected alternatives:** (1) Horizontal split (all routes in one agent, all templates in another) — proven to cause naming divergence. (2) Fewer agents (8-10) — would make each agent too large (12+ files). (3) Separate models per blueprint — would prevent shared queries in reports/dashboard.
- **Least confident:** The activity log wiring. Despite the Coordinated Behaviors table prescribing exact INSERT statements, 12 of 16 agents must independently remember to add activity_log inserts on every write operation. If even 2-3 agents forget, the dashboard's "Recent Activity" section will have visible gaps. This is the most likely source of P1 findings in review.

---

## Deepening Notes (Security + Performance + Best Practices)

### Security
1. **CSRF on AJAX**: The search API uses `fetch()`. Flask-WTF requires the CSRF token as a header. In `base.html`, include: `<meta name="csrf-token" content="{{ csrf_token() }}">`. In `app.js`, all fetch POST requests must include header `X-CSRFToken: document.querySelector('meta[name=csrf-token]').content`. For GET-only search API, CSRF is not needed.
2. **Session cookie security**: Set `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'` in app config. `SESSION_COOKIE_SECURE=True` only in production (breaks localhost).
3. **Password hashing**: Use `werkzeug.security.generate_password_hash(password, method='pbkdf2:sha256')` and `check_password_hash()`. Do NOT use the `bcrypt` package — werkzeug's built-in is simpler and sufficient.
4. **SQL injection**: All queries use parameterized `?` placeholders. NEVER use f-strings or `.format()` in SQL. The `ORDER BY` clause cannot be parameterized — use a whitelist: `if sort_col not in ALLOWED_SORTS: sort_col = 'name'`.

### Performance
1. **Dashboard N+1**: The dashboard makes 8 aggregate queries. Each is a single SQL query with GROUP BY — no N+1 risk. But contacts list with company names IS an N+1 risk. Use LEFT JOIN: `SELECT c.*, co.name as company_name FROM contact c LEFT JOIN company co ON c.company_id = co.id`.
2. **FTS5 sync**: Use triggers to keep FTS5 in sync:
   ```sql
   CREATE TRIGGER IF NOT EXISTS notes_fts_insert AFTER INSERT ON note BEGIN
       INSERT INTO notes_fts(rowid, title, content, tags) VALUES (new.id, new.title, new.content, new.tags);
   END;
   CREATE TRIGGER IF NOT EXISTS notes_fts_update AFTER UPDATE ON note BEGIN
       UPDATE notes_fts SET title = new.title, content = new.content, tags = new.tags WHERE rowid = new.id;
   END;
   CREATE TRIGGER IF NOT EXISTS notes_fts_delete AFTER DELETE ON note BEGIN
       DELETE FROM notes_fts WHERE rowid = old.id;
   END;
   ```
   Same pattern for journal_fts. Add these triggers to schema.sql.
3. **Report pagination**: For MVP, no pagination needed (single user, manageable data volume). Add LIMIT 1000 as safety on list queries.
4. **Index coverage**: The existing indexes cover the primary filter/sort columns. Add composite index for timesheet query: `CREATE INDEX IF NOT EXISTS idx_time_entry_date_project ON time_entry(date, project_id)`.

### Flask Best Practices
1. **Blueprint count**: 14 blueprints is fine — Flask handles this. Avoid circular imports by using lazy blueprint imports in app factory (already prescribed in the plan).
2. **Error handlers**: Add 404 and 500 handlers in app factory returning HTML error pages.
3. **Static file caching**: For production, set `SEND_FILE_MAX_AGE_DEFAULT=43200` (12h cache for CSS/JS).
