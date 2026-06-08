---
title: "Film Production PM Tool"
type: feat
status: active
date: 2026-06-02
swarm: true
agents: 16
origin: docs/brainstorms/2026-06-02-film-production-pm-brainstorm.md
feed_forward:
  risk: "Call sheet Cross-Boundary Wiring — 6 cross-module imports is the densest coupling surface attempted. A single name mismatch or wrong return type crashes the call sheet page."
  verify_first: true
---

# Film Production PM Tool — Shared Interface Spec

Film production project management tool for indie/mid-budget producers. Flask + SQLite + Jinja2 + Bootstrap 5 dark theme + SortableJS. 16-agent vertical swarm. (see brainstorm: docs/brainstorms/2026-06-02-film-production-pm-brainstorm.md)

---

## App Configuration

```python
# app/__init__.py (scaffold agent owns this file)
import os
from flask import Flask, session, redirect, url_for
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # SECRET_KEY -- fail closed, never fall back to dev string
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        raise RuntimeError('SECRET_KEY environment variable is required')
    app.config['SECRET_KEY'] = secret
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = True

    csrf.init_app(app)

    # Security headers
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:;"
        )
        return response

    # Database
    from app.database import init_app
    init_app(app)

    # Blueprint registration -- exact order
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.projects.routes import bp as projects_bp
    from app.blueprints.scenes.routes import bp as scenes_bp
    from app.blueprints.cast.routes import bp as cast_bp
    from app.blueprints.crew.routes import bp as crew_bp
    from app.blueprints.departments.routes import bp as departments_bp
    from app.blueprints.locations.routes import bp as locations_bp
    from app.blueprints.schedule.routes import bp as schedule_bp
    from app.blueprints.callsheets.routes import bp as callsheets_bp
    from app.blueprints.budget.routes import bp as budget_bp
    from app.blueprints.expenses.routes import bp as expenses_bp
    from app.blueprints.reports.routes import bp as reports_bp
    from app.blueprints.search.routes import bp as search_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(scenes_bp, url_prefix='/scenes')
    app.register_blueprint(cast_bp, url_prefix='/cast')
    app.register_blueprint(crew_bp, url_prefix='/crew')
    app.register_blueprint(departments_bp, url_prefix='/departments')
    app.register_blueprint(locations_bp, url_prefix='/locations')
    app.register_blueprint(schedule_bp, url_prefix='/schedule')
    app.register_blueprint(callsheets_bp, url_prefix='/call-sheets')
    app.register_blueprint(budget_bp, url_prefix='/budget')
    app.register_blueprint(expenses_bp, url_prefix='/expenses')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(search_bp, url_prefix='/search')

    # Dashboard route on root -- simple redirect, auth checked at destination
    @app.route('/')
    def index():
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        from app.database import get_db
        from app.models.project_models import get_active_project
        conn = get_db()
        project = get_active_project(conn)
        if project is None:
            return redirect(url_for('projects.new'))
        return redirect(url_for('projects.dashboard', project_id=project['id']))

    # Template filters
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert integer cents to dollar string: 150000 -> '$1,500.00'"""
        if cents is None:
            return '$0.00'
        return f'${cents / 100:,.2f}'

    @app.template_filter('page_count')
    def page_count_filter(eighths):
        """Convert 1/8th page count to display: 12 -> '1 4/8'"""
        if eighths is None:
            return '0'
        whole = eighths // 8
        remainder = eighths % 8
        if remainder == 0:
            return str(whole)
        if whole == 0:
            return f'{remainder}/8'
        return f'{whole} {remainder}/8'

    return app
```

**Requirements (requirements.txt):**
```
flask>=3.0
flask-wtf>=1.2
```

---

## Database Schema

```sql
-- schema.sql (database agent owns this file)
-- Seeding order: departments, budget_categories, users, projects, project_members, then domain tables

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

-- ============================================================
-- CORE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    phase TEXT NOT NULL DEFAULT 'development'
        CHECK (phase IN ('development','pre_production','production','post_production','distribution')),
    total_budget_cents INTEGER NOT NULL DEFAULT 0 CHECK (total_budget_cents >= 0),
    start_date TEXT,
    end_date TEXT,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('producer','ad','department_head','crew_member')),
    UNIQUE(project_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members(project_id);
CREATE INDEX IF NOT EXISTS idx_project_members_user ON project_members(user_id);

-- ============================================================
-- DEPARTMENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    head_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE(project_id, name)
);
CREATE INDEX IF NOT EXISTS idx_departments_project ON departments(project_id);

-- ============================================================
-- CREW & CAST
-- ============================================================

CREATE TABLE IF NOT EXISTS crew_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    phone TEXT,
    email TEXT,
    daily_rate_cents INTEGER DEFAULT 0 CHECK (daily_rate_cents >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_crew_project ON crew_members(project_id);
CREATE INDEX IF NOT EXISTS idx_crew_department ON crew_members(department_id);
CREATE INDEX IF NOT EXISTS idx_crew_user ON crew_members(user_id);

CREATE TABLE IF NOT EXISTS cast_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    character_name TEXT NOT NULL,
    cast_id_number INTEGER NOT NULL CHECK (cast_id_number BETWEEN 1 AND 99),
    agent_name TEXT,
    agent_phone TEXT,
    agent_email TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, cast_id_number)
);
CREATE INDEX IF NOT EXISTS idx_cast_project ON cast_members(project_id);

-- ============================================================
-- SCENES
-- ============================================================

CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_number TEXT NOT NULL,
    description TEXT,
    int_ext TEXT NOT NULL CHECK (int_ext IN ('INT','EXT','INT/EXT')),
    day_night TEXT NOT NULL CHECK (day_night IN ('DAY','NIGHT','DAWN','DUSK')),
    page_count_eighths INTEGER NOT NULL DEFAULT 8 CHECK (page_count_eighths > 0),
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'not_started'
        CHECK (status IN ('not_started','in_prep','ready','shooting','wrapped','on_hold')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, scene_number)
);
CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project_id);
CREATE INDEX IF NOT EXISTS idx_scenes_location ON scenes(location_id);

CREATE TABLE IF NOT EXISTS scene_cast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    cast_member_id INTEGER NOT NULL REFERENCES cast_members(id) ON DELETE CASCADE,
    UNIQUE(scene_id, cast_member_id)
);
CREATE INDEX IF NOT EXISTS idx_scene_cast_scene ON scene_cast(scene_id);
CREATE INDEX IF NOT EXISTS idx_scene_cast_cast ON scene_cast(cast_member_id);

CREATE TABLE IF NOT EXISTS scene_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    element_type TEXT NOT NULL CHECK (element_type IN ('prop','wardrobe','sfx','vehicle','animal','special_equipment')),
    description TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scene_elements_scene ON scene_elements(scene_id);

-- ============================================================
-- LOCATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    address TEXT,
    contact_name TEXT,
    contact_phone TEXT,
    permit_status TEXT DEFAULT 'pending' CHECK (permit_status IN ('pending','approved','denied')),
    nearest_hospital TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_locations_project ON locations(project_id);

-- ============================================================
-- SCHEDULE
-- ============================================================

CREATE TABLE IF NOT EXISTS schedule_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    shoot_date TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, scene_id)
);
CREATE INDEX IF NOT EXISTS idx_schedule_project_date ON schedule_entries(project_id, shoot_date);
CREATE INDEX IF NOT EXISTS idx_schedule_scene ON schedule_entries(scene_id);

-- ============================================================
-- CALL SHEETS
-- ============================================================

CREATE TABLE IF NOT EXISTS call_sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sheet_number INTEGER NOT NULL,
    shoot_date TEXT NOT NULL,
    crew_call_time TEXT DEFAULT '07:00',
    weather_note TEXT,
    general_notes TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_id, shoot_date)
);
CREATE INDEX IF NOT EXISTS idx_callsheets_project ON call_sheets(project_id);

CREATE TABLE IF NOT EXISTS call_sheet_scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sheet_id INTEGER NOT NULL REFERENCES call_sheets(id) ON DELETE CASCADE,
    scene_id INTEGER NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cs_scenes_sheet ON call_sheet_scenes(call_sheet_id);

CREATE TABLE IF NOT EXISTS call_sheet_cast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_sheet_id INTEGER NOT NULL REFERENCES call_sheets(id) ON DELETE CASCADE,
    cast_member_id INTEGER NOT NULL REFERENCES cast_members(id) ON DELETE CASCADE,
    pickup_time TEXT,
    makeup_time TEXT,
    on_set_time TEXT,
    -- Call sheets list ONLY cast working that day. Status is the Start/Work/Finish
    -- marker for THIS shoot date: SWF (only working day), SW (first), WF (last), W (mid).
    -- 'H' (hold) is DOOD-grid-only, never a call_sheet_cast value.
    status TEXT NOT NULL DEFAULT 'W' CHECK (status IN ('W','SW','WF','SWF')),
    remarks TEXT
);
CREATE INDEX IF NOT EXISTS idx_cs_cast_sheet ON call_sheet_cast(call_sheet_id);

-- ============================================================
-- BUDGET & EXPENSES
-- ============================================================

CREATE TABLE IF NOT EXISTS budget_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    account_number TEXT NOT NULL,
    name TEXT NOT NULL,
    parent_group TEXT NOT NULL CHECK (parent_group IN ('ATL','BTL_PRODUCTION','BTL_POST','OTHER')),
    UNIQUE(project_id, account_number)
);
CREATE INDEX IF NOT EXISTS idx_budget_cat_project ON budget_categories(project_id);

CREATE TABLE IF NOT EXISTS budget_line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES budget_categories(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    estimated_cents INTEGER NOT NULL DEFAULT 0 CHECK (estimated_cents >= 0),
    actual_cents INTEGER NOT NULL DEFAULT 0 CHECK (actual_cents >= 0),
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_line_items_category ON budget_line_items(category_id);
CREATE INDEX IF NOT EXISTS idx_line_items_project ON budget_line_items(project_id);

CREATE TABLE IF NOT EXISTS department_budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    allocated_cents INTEGER NOT NULL DEFAULT 0 CHECK (allocated_cents >= 0),
    spent_cents INTEGER NOT NULL DEFAULT 0 CHECK (spent_cents >= 0),
    CHECK (spent_cents <= allocated_cents),
    UNIQUE(project_id, department_id)
);
CREATE INDEX IF NOT EXISTS idx_dept_budgets_project ON department_budgets(project_id);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    category_id INTEGER REFERENCES budget_categories(id) ON DELETE SET NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    vendor TEXT NOT NULL,
    description TEXT,
    expense_date TEXT NOT NULL,
    approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id);
CREATE INDEX IF NOT EXISTS idx_expenses_department ON expenses(department_id);

-- ============================================================
-- FTS5 SEARCH (external content)
-- ============================================================

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    entity_type UNINDEXED, entity_id UNINDEXED, title, body,
    content='', contentless_delete=1
);

-- FTS5 index is maintained by EXACTLY ONE writer: explicit index_entity()/remove_entity()
-- calls from the scenes/cast/crew/locations routes (see Search Index Wiring). There are
-- NO database triggers on the source tables (FC52 single-writer). Two writers (triggers +
-- explicit calls) would double-index this contentless table. The database agent does NOT
-- create FTS triggers; the search agent does NOT touch schema.sql.

-- ============================================================
-- SEED DATA (database agent inserts these in init_db)
-- ============================================================
-- See seed_data() function in database.py for seeding order:
-- 1. departments (17 standard)
-- 2. budget_categories (standard film template)
-- 3. users (one producer: admin/from-env)
-- 4. projects (one active production)
-- 5. project_members (admin -> project with role=producer)
```

---

## Database Connection (database.py)

```python
# app/database.py (database agent owns this file)
import sqlite3
import os
from flask import g, current_app
from werkzeug.security import generate_password_hash

DATABASE = 'filmpm.db'

def get_db():
    """Get database connection. Sets PRAGMAs on every connection (FC40)."""
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE', DATABASE)
        g.db = sqlite3.connect(db_path, autocommit=True)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
        g.db.execute('PRAGMA synchronous=NORMAL')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Create tables from schema.sql and seed default data."""
    db_path = os.environ.get('DATABASE', DATABASE)
    conn = sqlite3.connect(db_path, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA synchronous=NORMAL')
    with open(os.path.join(os.path.dirname(__file__), '..', 'schema.sql')) as f:
        conn.executescript(f.read())
    seed_data(conn)
    conn.close()

def seed_data(conn):
    """Seed defaults in FK-safe order. ON CONFLICT DO NOTHING for idempotency."""
    # 1. Departments (17 standard)
    depts = ['Producing','Directing','Camera','Lighting/Electrical','Grip',
             'Sound','Art/Production Design','Wardrobe/Costume','Hair & Makeup',
             'Locations','Transportation','Stunts','SFX','VFX',
             'Editorial/Post','Casting','Accounting']
    # Departments need a project_id -- seeded after project creation below

    # 2. Budget categories (seeded after project creation)

    # 3. Users -- one producer
    admin_pw = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_pw:
        raise RuntimeError('ADMIN_PASSWORD environment variable is required')
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('''INSERT OR IGNORE INTO users (username, password_hash, display_name)
                        VALUES (?, ?, ?)''',
                     ('producer', generate_password_hash(admin_pw), 'Lead Producer'))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    user = conn.execute('SELECT id FROM users WHERE username = ?', ('producer',)).fetchone()
    user_id = user['id']

    # 4. Projects -- one active production
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('''INSERT OR IGNORE INTO projects (id, title, phase, total_budget_cents, created_by)
                        VALUES (1, ?, ?, ?, ?)''',
                     ('Untitled Production', 'development', 0, user_id))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise
    project_id = 1

    # 5. Project members
    conn.execute('BEGIN IMMEDIATE')
    try:
        conn.execute('''INSERT OR IGNORE INTO project_members (project_id, user_id, role)
                        VALUES (?, ?, 'producer')''', (project_id, user_id))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    # 1b. Departments (now with project_id)
    conn.execute('BEGIN IMMEDIATE')
    try:
        for dept_name in depts:
            conn.execute('''INSERT OR IGNORE INTO departments (project_id, name)
                            VALUES (?, ?)''', (project_id, dept_name))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

    # 2b. Budget categories
    categories = [
        ('1100','Story & Rights','ATL'),('1200','Producer','ATL'),
        ('1300','Director','ATL'),('1400','Cast','ATL'),
        ('2000','Production Staff','BTL_PRODUCTION'),('2100','Extras','BTL_PRODUCTION'),
        ('2200','Art Department','BTL_PRODUCTION'),('2300','Construction','BTL_PRODUCTION'),
        ('2400','Set Operations','BTL_PRODUCTION'),('2500','SFX','BTL_PRODUCTION'),
        ('2600','Wardrobe','BTL_PRODUCTION'),('2700','Makeup/Hair','BTL_PRODUCTION'),
        ('2800','Lighting','BTL_PRODUCTION'),('2900','Camera','BTL_PRODUCTION'),
        ('3000','Sound','BTL_PRODUCTION'),('3100','Transport','BTL_PRODUCTION'),
        ('3200','Locations','BTL_PRODUCTION'),('3300','Media/Stock','BTL_PRODUCTION'),
        ('4000','Editing','BTL_POST'),('4100','Music','BTL_POST'),
        ('4200','Post Sound','BTL_POST'),('4300','Deliverables','BTL_POST'),
        ('4400','VFX','BTL_POST'),('4500','Titles','BTL_POST'),
        ('5000','Insurance','OTHER'),('5100','General/Admin','OTHER'),
        ('5200','Publicity','OTHER'),('5300','Contingency 10%','OTHER'),
        ('5400','Completion Bond','OTHER'),('5500','Overhead','OTHER'),
    ]
    conn.execute('BEGIN IMMEDIATE')
    try:
        for acct, name, group in categories:
            conn.execute('''INSERT OR IGNORE INTO budget_categories (project_id, account_number, name, parent_group)
                            VALUES (?, ?, ?, ?)''', (project_id, acct, name, group))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise

def init_app(app):
    app.teardown_appcontext(close_db)
    if not os.path.exists(app.config.get('DATABASE', DATABASE)):
        with app.app_context():
            init_db()
```

---

## Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| users | auth_models | projects, crew, expenses, all (via decorators) |
| projects | project_models | all blueprints |
| project_members | project_models | auth (decorators), all (via g.member) |
| departments | department_models | crew, budget, expenses, callsheets, reports |
| crew_members | crew_models | callsheets, reports, search |
| cast_members | cast_models | scenes (M2M), callsheets, reports, search |
| scenes | scene_models | schedule, callsheets, reports, search |
| scene_cast | cast_models | scenes, callsheets, reports |
| scene_elements | scene_models | scenes |
| locations | location_models | scenes, schedule, callsheets, search |
| schedule_entries | schedule_models | callsheets, reports |
| call_sheets | callsheet_models | reports |
| call_sheet_scenes | callsheet_models | callsheets |
| call_sheet_cast | callsheet_models | callsheets |
| budget_categories | budget_models | expenses, reports |
| budget_line_items | budget_models | reports |
| department_budgets | budget_models | expenses, reports |
| expenses | expense_models | budget (via spent_cents updates in expense_models), reports |
| search_index | search_models | search |

---

## Model Functions

### auth_models.py

```python
# Returns: int (user_id) -- commits internally (BEGIN IMMEDIATE)
# Usage: user_id = create_user(conn, username, password, display_name)
def create_user(conn, username, password, display_name) -> int: ...

# Returns: dict or None
# Usage: user = authenticate(conn, username, password)
#        if user is None: flash('Invalid credentials', 'error')
# SECURITY: Constant-time -- always call check_password_hash even if user not found
#   DUMMY_HASH = generate_password_hash("dummy")
#   user = conn.execute(...).fetchone()
#   if user is None:
#       check_password_hash(DUMMY_HASH, password)  # prevent timing attack
#       return None
def authenticate(conn, username, password) -> dict | None: ...

# Returns: dict or None
# Usage: user = get_user(conn, user_id)
def get_user(conn, user_id) -> dict | None: ...
```

### project_models.py

```python
# Returns: int (project_id) -- commits internally (BEGIN IMMEDIATE)
def create_project(conn, title, description, total_budget_cents, created_by) -> int: ...

# Returns: dict or None
def get_project(conn, project_id) -> dict | None: ...

# Returns: dict or None -- the single active project
def get_active_project(conn) -> dict | None: ...

# Returns: dict with keys: total_scenes, scenes_wrapped, total_budget_cents, spent_cents, shoot_days_count
def get_project_stats(conn, project_id) -> dict: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE + status validation)
def transition_project_phase(conn, project_id, new_phase) -> bool: ...
```

### scene_models.py

```python
# Returns: int (scene_id) -- commits internally
def create_scene(conn, project_id, scene_number, description, int_ext, day_night, page_count_eighths, location_id=None) -> int: ...

# Returns: list[dict] with keys: id, scene_number, description, int_ext, day_night, page_count_eighths, location_name, status
def get_scenes(conn, project_id) -> list: ...

# Returns: list[dict] with keys: id, scene_number, description, int_ext, day_night, page_count_eighths
# Usage: scenes = get_scenes_by_ids(conn, scene_ids)
def get_scenes_by_ids(conn, scene_ids) -> list[dict]: ...

# Returns: dict or None
def get_scene(conn, scene_id) -> dict | None: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE + status validation)
def transition_scene_status(conn, scene_id, new_status) -> bool: ...

# Returns: None -- does NOT commit
def update_scene(conn, scene_id, **kwargs) -> None: ...
```

### cast_models.py

```python
# Returns: int (cast_member_id) -- commits internally
def create_cast_member(conn, project_id, name, character_name, cast_id_number) -> int: ...

# Returns: list[dict] with keys: id, name, character_name, cast_id_number, agent_name
def get_cast_members(conn, project_id) -> list: ...

# Returns: dict or None
def get_cast_member(conn, cast_member_id) -> dict | None: ...

# Returns: list[dict] with keys: id, name, character_name, cast_id_number
# Usage: cast = get_cast_for_scenes(conn, scene_ids)
def get_cast_for_scenes(conn, scene_ids) -> list[dict]: ...

# Returns: None -- does NOT commit
def add_cast_to_scene(conn, scene_id, cast_member_id) -> None: ...

# Returns: None -- does NOT commit
def remove_cast_from_scene(conn, scene_id, cast_member_id) -> None: ...

# Returns: list[dict] -- cast assigned to a specific scene
def get_scene_cast(conn, scene_id) -> list: ...
```

### crew_models.py

```python
# Returns: int (crew_member_id) -- commits internally
def create_crew_member(conn, project_id, name, role_title, department_id, user_id=None, phone=None, email=None, daily_rate_cents=0) -> int: ...

# Returns: list[dict] with keys: id, name, role_title, department_name, phone, email, daily_rate_cents
def get_crew_members(conn, project_id) -> list: ...

# Returns: list[dict] grouped by department: [{department_name, members: [{id, name, role_title, phone}]}]
# Usage: grouped = get_crew_by_department(conn, project_id)
def get_crew_by_department(conn, project_id) -> list[dict]: ...

# Returns: dict or None with keys: id, project_id, name, role_title, department_id, department_name, phone, email, daily_rate_cents
def get_crew_member(conn, crew_member_id) -> dict | None: ...
```

### department_models.py

```python
# Returns: list[dict] with keys: id, name, head_id, head_name
def get_departments(conn, project_id) -> list: ...

# Returns: dict or None
def get_department(conn, department_id) -> dict | None: ...

# Returns: None -- commits internally
def assign_department_head(conn, department_id, user_id) -> None: ...
```

### location_models.py

```python
# Returns: int (location_id) -- commits internally
def create_location(conn, project_id, name, address=None, contact_name=None, contact_phone=None, nearest_hospital=None) -> int: ...

# Returns: list[dict]
def get_locations(conn, project_id) -> list: ...

# Returns: dict or None with keys: id, name, address, contact_name, contact_phone, permit_status, nearest_hospital
# Usage: loc = get_location(conn, location_id)
def get_location(conn, location_id) -> dict | None: ...
```

### schedule_models.py

```python
# Returns: int or None (entry_id, None if duplicate scene) -- commits internally (BEGIN IMMEDIATE + TOCTOU fence)
def create_schedule_entry(conn, project_id, scene_id, location_id, shoot_date, sort_order) -> int | None: ...

# Returns: list[dict] with keys: id, scene_id, scene_number, location_id, location_name, shoot_date, sort_order, int_ext, day_night, page_count_eighths, strip_color_class
# Usage: entries = get_schedule_entries(conn, project_id, shoot_date)
def get_schedule_entries(conn, project_id, shoot_date) -> list[dict]: ...

# Returns: list[str] -- distinct shoot dates in order
def get_shoot_dates(conn, project_id) -> list: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE + full ID set validation)
def reorder_schedule(conn, project_id, shoot_date, ordered_ids) -> bool: ...

# Returns: None -- does NOT commit
def delete_schedule_entry(conn, entry_id) -> None: ...
```

### callsheet_models.py

```python
# Returns: int (call_sheet_id) -- commits internally (BEGIN IMMEDIATE, multi-table)
def generate_call_sheet(conn, project_id, shoot_date) -> int: ...

# Returns: dict or None
def get_call_sheet(conn, call_sheet_id) -> dict | None: ...

# Returns: list[dict] with scene details
def get_call_sheet_scenes(conn, call_sheet_id) -> list: ...

# Returns: list[dict] with cast details + status
def get_call_sheet_cast(conn, call_sheet_id) -> list: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE)
def publish_call_sheet(conn, call_sheet_id) -> bool: ...
```

### budget_models.py

```python
# Returns: dict with keys: total_estimated_cents, total_actual_cents, variance_cents, categories (list)
def get_budget_summary(conn, project_id) -> dict: ...

# Returns: list[dict] -- categories with line items
def get_budget_categories(conn, project_id) -> list: ...

# Returns: dict or None
def get_department_allocation(conn, department_id) -> dict | None: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE + SUM check)
def allocate_budget(conn, project_id, department_id, amount_cents) -> bool: ...

# Returns: int (line_item_id) -- commits internally (BEGIN IMMEDIATE)
def create_line_item(conn, project_id, category_id, description, estimated_cents, actual_cents=0) -> int: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE)
def update_line_item(conn, line_item_id, estimated_cents=None, actual_cents=None) -> bool: ...
```

### expense_models.py

```python
# Returns: int (expense_id) or None if it would exceed the department allocation
#   -- commits internally (BEGIN IMMEDIATE + spent_cents update).
#   Inside the lock: re-read department_budgets.spent_cents/allocated_cents; if
#   spent_cents + amount_cents > allocated_cents, ROLLBACK and return None (do NOT
#   rely on the CHECK constraint raising — that path is a 500). Route flashes the
#   remaining amount on None. Mirrors create_schedule_entry -> int | None.
def create_expense(conn, project_id, department_id, amount_cents, vendor, description, expense_date, category_id, created_by) -> int | None: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE + spent_cents rollback)
def delete_expense(conn, expense_id) -> bool: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE)
def approve_expense(conn, expense_id, approved_by) -> bool: ...

# Returns: list[dict]
def get_expenses(conn, project_id, department_id=None) -> list: ...

# Returns: dict or None with keys: id, project_id, department_id, created_by, approved_by, amount_cents, expense_date, vendor, description, category_id
# Usage: expense = get_expense(conn, expense_id) -- used by expenses routes for ownership/IDOR checks
def get_expense(conn, expense_id) -> dict | None: ...
```

### search_models.py

```python
# Returns: list[dict] with keys: entity_type, entity_id, title, snippet
def search(conn, query, project_id) -> list: ...

# Returns: None -- maintains FTS5 index
def index_entity(conn, entity_type, entity_id, title, body) -> None: ...

# Returns: None -- removes from FTS5 index
def remove_entity(conn, entity_type, entity_id) -> None: ...
```

### report_models.py (reports agent)

```python
# Returns: list[dict] -- DOOD grid data
# Each dict: {cast_member_id, name, character_name, cast_id_number, days: {date: status}}
def get_dood_grid(conn, project_id) -> list: ...

# Returns: dict -- production progress stats
def get_production_progress(conn, project_id) -> dict: ...
```

---

## Transition Maps (FC54 — referenced constants must be defined)

Both transition validators in Input Validation reference these maps (`VALID_PHASE_TRANSITIONS[current_phase]` and `VALID_SCENE_TRANSITIONS[current_status]`).
These maps are defined here, each owned by exactly one agent and imported only within
that agent's own routes (no cross-boundary import). A target phase/status is valid iff
it appears in the list for the current value. Same-value (no-op) and any value not in
the list are rejected with the prescribed flash.

```python
# app/models/project_models.py (projects agent owns this constant)
# Phases are forward-only and linear; 'distribution' is terminal.
VALID_PHASE_TRANSITIONS = {
    'development':     ['pre_production'],
    'pre_production':  ['production'],
    'production':      ['post_production'],
    'post_production': ['distribution'],
    'distribution':    [],
}
# Used by: transition_project_phase() and POST /projects/<id>/phase
```

```python
# app/models/scene_models.py (scenes agent owns this constant)
VALID_SCENE_TRANSITIONS = {
    'not_started': ['in_prep', 'on_hold'],
    'in_prep':     ['ready', 'on_hold'],
    'ready':       ['shooting', 'on_hold'],
    'shooting':    ['wrapped', 'on_hold'],
    'on_hold':     ['in_prep', 'ready', 'shooting'],
    'wrapped':     [],   # terminal
}
# Used by: transition_scene_status() and POST /scenes/<pid>/<sid>/status
```

The route validates `new_value in VALID_*_TRANSITIONS.get(current, [])`; the model
function re-checks the same inside its BEGIN IMMEDIATE lock (TOCTOU fence) and returns
False if invalid.

---

## Context Manager Usage

`get_db()` is NOT a context manager. It returns a connection stored in Flask's `g` object:

```python
# Usage -- plain function call:
conn = get_db()
projects = get_all_projects(conn)
```

**Rule:** Do NOT use `with get_db() as conn:` syntax. `get_db()` is a plain function that returns a connection. The connection is closed in `close_db()` via `teardown_appcontext`.

---

## Auth Decorators

```python
# app/blueprints/auth/routes.py -- decorators exported for all blueprints

from functools import wraps
from flask import session, g, redirect, url_for, flash, abort

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        from app.database import get_db
        from app.models.auth_models import get_user
        conn = get_db()
        g.user = get_user(conn, session['user_id'])
        if g.user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def require_project_member(f):
    """Sets g.project and g.member. All project-scoped routes MUST use this."""
    @wraps(f)
    def decorated(*args, **kwargs):
        project_id = kwargs.get('project_id')
        from app.database import get_db
        conn = get_db()
        from app.models.project_models import get_project
        g.project = get_project(conn, project_id)
        if g.project is None:
            abort(404)
        member = conn.execute(
            'SELECT * FROM project_members WHERE project_id = ? AND user_id = ?',
            (project_id, g.user['id'])
        ).fetchone()
        if member is None:
            abort(403)
        g.member = dict(member)
        return f(*args, **kwargs)
    return decorated

def require_role(*roles):
    """Check g.member['role'] is in allowed roles. Use AFTER require_project_member."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.member['role'] not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
```

---

## Route Table

### auth (url_prefix=/auth)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /login | auth.login | public | auth/login.html |
| POST | /login | auth.login_post | public | redirect |
| GET | /register | auth.register | public | auth/register.html |
| POST | /register | auth.register_post | public | redirect |
| POST | /logout | auth.logout | login_required | redirect |

### projects (url_prefix=/projects)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /new | projects.new | login_required | projects/new.html |
| POST | / | projects.create | login_required | redirect |
| GET | /\<int:project_id\> | projects.dashboard | login+member | projects/dashboard.html |
| GET | /\<int:project_id\>/edit | projects.edit | login+member+producer | projects/edit.html |
| POST | /\<int:project_id\>/edit | projects.update | login+member+producer | redirect |
| POST | /\<int:project_id\>/phase | projects.transition_phase | login+member+producer | redirect |

### scenes (url_prefix=/scenes)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | scenes.list | login+member | scenes/list.html |
| GET | /\<int:project_id\>/new | scenes.new | login+member+producer/ad | scenes/new.html |
| POST | /\<int:project_id\> | scenes.create | login+member+producer/ad | redirect |
| GET | /\<int:project_id\>/\<int:scene_id\> | scenes.detail | login+member | scenes/detail.html |
| GET | /\<int:project_id\>/\<int:scene_id\>/edit | scenes.edit | login+member+producer/ad | scenes/edit.html |
| POST | /\<int:project_id\>/\<int:scene_id\>/edit | scenes.update | login+member+producer/ad | redirect |
| POST | /\<int:project_id\>/\<int:scene_id\>/status | scenes.transition_status | login+member+producer/ad | redirect |

### cast (url_prefix=/cast)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | cast.list | login+member | cast/list.html |
| GET | /\<int:project_id\>/new | cast.new | login+member+producer/ad | cast/new.html |
| POST | /\<int:project_id\> | cast.create | login+member+producer/ad | redirect |
| GET | /\<int:project_id\>/\<int:cast_member_id\> | cast.detail | login+member | cast/detail.html |
| POST | /\<int:project_id\>/\<int:cast_member_id\>/edit | cast.update | login+member+producer/ad | redirect |

### crew (url_prefix=/crew)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | crew.list | login+member | crew/list.html |
| GET | /\<int:project_id\>/new | crew.new | login+member+producer/ad/dept_head | crew/new.html |
| POST | /\<int:project_id\> | crew.create | login+member+producer/ad/dept_head | redirect |
| GET | /\<int:project_id\>/\<int:crew_member_id\> | crew.detail | login+member | crew/detail.html |
| POST | /\<int:project_id\>/\<int:crew_member_id\>/edit | crew.update | login+member+producer/ad/dept_head | redirect |

### departments (url_prefix=/departments)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | departments.list | login+member | departments/list.html |
| GET | /\<int:project_id\>/\<int:department_id\> | departments.detail | login+member | departments/detail.html |
| POST | /\<int:project_id\>/\<int:department_id\>/head | departments.assign_head | login+member+producer | redirect |

### locations (url_prefix=/locations)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | locations.list | login+member | locations/list.html |
| GET | /\<int:project_id\>/new | locations.new | login+member+producer/ad | locations/new.html |
| POST | /\<int:project_id\> | locations.create | login+member+producer/ad | redirect |
| GET | /\<int:project_id\>/\<int:location_id\> | locations.detail | login+member | locations/detail.html |
| POST | /\<int:project_id\>/\<int:location_id\>/edit | locations.update | login+member+producer/ad | redirect |

### schedule (url_prefix=/schedule)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | schedule.index | login+member | schedule/index.html |
| GET | /\<int:project_id\>/day/\<date\> | schedule.day_view | login+member | schedule/day.html |
| GET | /\<int:project_id\>/new | schedule.new | login+member+producer/ad | schedule/new.html |
| POST | /\<int:project_id\> | schedule.create | login+member+producer/ad | redirect |
| POST | /\<int:project_id\>/reorder | schedule.reorder | login+member+producer/ad | JSON |
| POST | /\<int:project_id\>/\<int:entry_id\>/delete | schedule.delete | login+member+producer/ad | redirect |

### callsheets (url_prefix=/call-sheets)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | callsheets.list | login+member | callsheets/list.html |
| POST | /\<int:project_id\>/generate | callsheets.generate | login+member+producer/ad | redirect |
| GET | /\<int:project_id\>/\<int:call_sheet_id\> | callsheets.detail | login+member | callsheets/detail.html |
| POST | /\<int:project_id\>/\<int:call_sheet_id\>/publish | callsheets.publish | login+member+producer/ad | redirect |

### budget (url_prefix=/budget)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | budget.index | login+member+producer | budget/index.html |
| GET | /\<int:project_id\>/top-sheet | budget.top_sheet | login+member+producer | budget/top_sheet.html |
| POST | /\<int:project_id\>/allocate | budget.allocate | login+member+producer | redirect |
| GET | /\<int:project_id\>/line-items/new | budget.new_line_item | login+member+producer | budget/new_line_item.html |
| POST | /\<int:project_id\>/line-items | budget.create_line_item | login+member+producer | redirect |
| POST | /\<int:project_id\>/line-items/\<int:item_id\>/edit | budget.update_line_item | login+member+producer | redirect |

### expenses (url_prefix=/expenses)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | expenses.list | login+member+producer/dept_head | expenses/list.html |
| GET | /\<int:project_id\>/new | expenses.new | login+member+producer/dept_head | expenses/new.html |
| POST | /\<int:project_id\> | expenses.create | login+member+producer/dept_head | redirect |
| POST | /\<int:project_id\>/\<int:expense_id\>/delete | expenses.delete | login+member+producer/dept_head | redirect |
| POST | /\<int:project_id\>/\<int:expense_id\>/approve | expenses.approve | login+member+producer | redirect |

### reports (url_prefix=/reports)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | reports.index | login+member | reports/index.html |
| GET | /\<int:project_id\>/budget-summary | reports.budget_summary | login+member+producer | reports/budget_summary.html |
| GET | /\<int:project_id\>/dood | reports.dood | login+member | reports/dood.html |
| GET | /\<int:project_id\>/progress | reports.progress | login+member | reports/progress.html |

### search (url_prefix=/search)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:project_id\> | search.search_page | login+member | search/results.html |

---

## Template Render Context

```python
# projects/dashboard.html expects:
render_template('projects/dashboard.html',
    project=get_project(conn, project_id),
    stats=get_project_stats(conn, project_id))

# scenes/list.html expects:
render_template('scenes/list.html',
    project=g.project, scenes=get_scenes(conn, project_id))

# schedule/day.html expects:
render_template('schedule/day.html',
    project=g.project, entries=get_schedule_entries(conn, project_id, date),
    shoot_date=date)

# callsheets/detail.html expects:
render_template('callsheets/detail.html',
    project=g.project, call_sheet=get_call_sheet(conn, cs_id),
    scenes=get_call_sheet_scenes(conn, cs_id),
    cast=get_call_sheet_cast(conn, cs_id),
    crew=get_crew_by_department(conn, project_id))

# budget/index.html expects:
render_template('budget/index.html',
    project=g.project, summary=get_budget_summary(conn, project_id),
    categories=get_budget_categories(conn, project_id))

# reports/dood.html expects:
render_template('reports/dood.html',
    project=g.project, dood=get_dood_grid(conn, project_id),
    shoot_dates=get_shoot_dates(conn, project_id))
```

---

## CSRF in Templates

Every POST form MUST include:

```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <!-- form fields -->
</form>
```

**For JSON POST (schedule reorder):**

```javascript
// Extract CSRF token from meta tag in base.html
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
    body: JSON.stringify(data)
});
```

**base.html must include:**
```html
<meta name="csrf-token" content="{{ csrf_token() }}">
```

---

## Export Names Table

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `get_db` | function | app/database.py | ALL agents |
| `init_db` | function | app/database.py | app factory |
| `login_required` | decorator | auth routes | ALL route agents |
| `require_project_member` | decorator | auth routes | ALL project-scoped route agents |
| `require_role` | decorator | auth routes | ALL project-scoped route agents |
| `create_user` | model fn | auth_models | auth routes |
| `authenticate` | model fn | auth_models | auth routes |
| `get_user` | model fn | auth_models | auth routes, decorators |
| `create_project` | model fn | project_models | projects routes |
| `get_project` | model fn | project_models | auth routes (decorator), projects routes |
| `get_active_project` | model fn | project_models | app factory (index route) |
| `get_project_stats` | model fn | project_models | projects routes |
| `transition_project_phase` | model fn | project_models | projects routes |
| `create_scene` | model fn | scene_models | scenes routes |
| `get_scenes` | model fn | scene_models | scenes routes, schedule routes |
| `get_scenes_by_ids` | model fn | scene_models | callsheet_models |
| `get_scene` | model fn | scene_models | scenes routes |
| `transition_scene_status` | model fn | scene_models | scenes routes |
| `update_scene` | model fn | scene_models | scenes routes |
| `create_cast_member` | model fn | cast_models | cast routes |
| `get_cast_members` | model fn | cast_models | cast routes, reports routes |
| `get_cast_member` | model fn | cast_models | cast routes |
| `get_cast_for_scenes` | model fn | cast_models | callsheet_models |
| `add_cast_to_scene` | model fn | cast_models | scenes routes |
| `remove_cast_from_scene` | model fn | cast_models | scenes routes |
| `get_scene_cast` | model fn | cast_models | scenes routes |
| `create_crew_member` | model fn | crew_models | crew routes |
| `get_crew_members` | model fn | crew_models | crew routes |
| `get_crew_by_department` | model fn | crew_models | callsheets routes |
| `get_crew_member` | model fn | crew_models | crew routes |
| `get_departments` | model fn | department_models | departments routes, callsheets routes, crew routes, expenses routes |
| `get_department` | model fn | department_models | departments routes |
| `assign_department_head` | model fn | department_models | departments routes |
| `create_location` | model fn | location_models | locations routes |
| `get_locations` | model fn | location_models | locations routes, scenes routes, schedule routes |
| `get_location` | model fn | location_models | locations routes, callsheet_models |
| `create_schedule_entry` | model fn | schedule_models | schedule routes |
| `get_schedule_entries` | model fn | schedule_models | schedule routes, callsheet_models, reports routes |
| `get_shoot_dates` | model fn | schedule_models | schedule routes, callsheets routes, reports routes |
| `reorder_schedule` | model fn | schedule_models | schedule routes |
| `delete_schedule_entry` | model fn | schedule_models | schedule routes |
| `generate_call_sheet` | model fn | callsheet_models | callsheets routes |
| `get_call_sheet` | model fn | callsheet_models | callsheets routes |
| `get_call_sheet_scenes` | model fn | callsheet_models | callsheets routes |
| `get_call_sheet_cast` | model fn | callsheet_models | callsheets routes |
| `publish_call_sheet` | model fn | callsheet_models | callsheets routes |
| `get_budget_summary` | model fn | budget_models | budget routes, reports routes |
| `get_budget_categories` | model fn | budget_models | budget routes |
| `get_department_allocation` | model fn | budget_models | budget routes, expenses routes |
| `allocate_budget` | model fn | budget_models | budget routes |
| `create_line_item` | model fn | budget_models | budget routes |
| `update_line_item` | model fn | budget_models | budget routes |
| `create_expense` | model fn | expense_models | expenses routes |
| `delete_expense` | model fn | expense_models | expenses routes |
| `approve_expense` | model fn | expense_models | expenses routes |
| `get_expenses` | model fn | expense_models | expenses routes, reports routes |
| `get_expense` | model fn | expense_models | expenses routes (ownership/IDOR checks) |
| `search` | model fn | search_models | search routes |
| `index_entity` | model fn | search_models | scenes, cast, crew, locations routes |
| `remove_entity` | model fn | search_models | scenes, cast, crew, locations routes |
| `get_dood_grid` | model fn | report_models | reports routes |
| `get_production_progress` | model fn | report_models | reports routes |
| `auth.login` | endpoint | auth routes | base.html navbar, redirect targets |
| `auth.logout` | endpoint | auth routes | base.html navbar |
| `auth.register` | endpoint | auth routes | login page link |
| `projects.dashboard` | endpoint | projects routes | navbar, index redirect |
| `projects.new` | endpoint | projects routes | index redirect |
| `scenes.list` | endpoint | scenes routes | navbar, dashboard links |
| `cast.list` | endpoint | cast routes | navbar |
| `crew.list` | endpoint | crew routes | navbar |
| `departments.list` | endpoint | departments routes | navbar |
| `locations.list` | endpoint | locations routes | navbar |
| `schedule.index` | endpoint | schedule routes | navbar |
| `callsheets.list` | endpoint | callsheets routes | navbar |
| `budget.index` | endpoint | budget routes | navbar (producer only) |
| `expenses.list` | endpoint | expenses routes | navbar (producer/dept_head) |
| `reports.index` | endpoint | reports routes | navbar |
| `search.search_page` | endpoint | search routes | navbar search form |
| `scaffold` | blueprint | app/__init__.py | -- |
| `auth` | blueprint | auth routes | app/__init__.py |
| `projects` | blueprint | projects routes | app/__init__.py |
| `scenes` | blueprint | scenes routes | app/__init__.py |
| `cast` | blueprint | cast routes | app/__init__.py |
| `crew` | blueprint | crew routes | app/__init__.py |
| `departments` | blueprint | departments routes | app/__init__.py |
| `locations` | blueprint | locations routes | app/__init__.py |
| `schedule` | blueprint | schedule routes | app/__init__.py |
| `callsheets` | blueprint | callsheets routes | app/__init__.py |
| `budget` | blueprint | budget routes | app/__init__.py |
| `expenses` | blueprint | expenses routes | app/__init__.py |
| `reports` | blueprint | reports routes | app/__init__.py |
| `search` | blueprint | search routes | app/__init__.py |

### Orchestration Entrypoints (FC50 — cross-boundary calls pinned with full signatures)

These are the cross-boundary consumption points where a wrong import name, arity, or
return type crashes the consumer (the Run-069 B3/C1/C6 failure mode). The call sheet
surface is the densest (6 imports). Signatures here are AUTHORITATIVE — producers and
consumers must match character-for-character.

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `get_schedule_entries` | orchestration entrypoint | schedule_models | callsheet_models, reports routes | `get_schedule_entries(conn, project_id, shoot_date) -> list[dict]` (keys: id, scene_id, scene_number, location_id, location_name, shoot_date, sort_order, int_ext, day_night, page_count_eighths, strip_color_class) |
| `get_cast_for_scenes` | orchestration entrypoint | cast_models | callsheet_models | `get_cast_for_scenes(conn, scene_ids) -> list[dict]` (keys: id, name, character_name, cast_id_number) |
| `get_scenes_by_ids` | orchestration entrypoint | scene_models | callsheet_models | `get_scenes_by_ids(conn, scene_ids) -> list[dict]` (keys: id, scene_number, description, int_ext, day_night, page_count_eighths) |
| `get_location` | orchestration entrypoint | location_models | callsheet_models | `get_location(conn, location_id) -> dict \| None` (keys: id, name, address, contact_name, contact_phone, permit_status, nearest_hospital) |
| `get_crew_by_department` | orchestration entrypoint | crew_models | callsheets routes | `get_crew_by_department(conn, project_id) -> list[dict]` (shape: [{department_name, members: [{id, name, role_title, phone}]}]) |
| `get_departments` | orchestration entrypoint | department_models | callsheets routes, crew routes, expenses routes | `get_departments(conn, project_id) -> list[dict]` (keys: id, name, head_id, head_name) |
| `login_required` | orchestration entrypoint | auth routes | ALL route agents | `login_required(f) -> Callable` (sets g.user; redirects to auth.login if no session) |
| `require_project_member` | orchestration entrypoint | auth routes | ALL project-scoped route agents | `require_project_member(f) -> Callable` (sets g.project, g.member; 404/403) |
| `require_role` | orchestration entrypoint | auth routes | ALL project-scoped route agents | `require_role(*roles) -> Callable` (checks g.member['role'] in roles AFTER require_project_member) |
| `get_db` | orchestration entrypoint | app/database.py | ALL route agents | `get_db() -> sqlite3.Connection` (row_factory=Row; PRAGMAs set; NOT a context manager) |

---

## Cross-Boundary Wiring Table

### Call Sheet Wiring (HIGHEST RISK — 6 cross-boundary imports)

| Producer | Consumer | Import Path | Return Type |
|----------|----------|-------------|-------------|
| app/models/schedule_models.py | app/models/callsheet_models.py | `from app.models.schedule_models import get_schedule_entries` | `list[dict]` |
| app/models/cast_models.py | app/models/callsheet_models.py | `from app.models.cast_models import get_cast_for_scenes` | `list[dict]` with id, name, character_name, cast_id_number |
| app/models/crew_models.py | app/blueprints/callsheets/routes.py | `from app.models.crew_models import get_crew_by_department` | `list[dict]` grouped by department |
| app/models/location_models.py | app/models/callsheet_models.py | `from app.models.location_models import get_location` | `dict` with name, address, nearest_hospital |
| app/models/scene_models.py | app/models/callsheet_models.py | `from app.models.scene_models import get_scenes_by_ids` | `list[dict]` with scene_number, int_ext, day_night, page_count_eighths |
| app/models/department_models.py | app/blueprints/callsheets/routes.py | `from app.models.department_models import get_departments` | `list[dict]` with id, name |

### Scene/Schedule Form Dropdowns (missing from initial spec)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/location_models.py | app/blueprints/scenes/routes.py | `from app.models.location_models import get_locations` |
| app/models/scene_models.py | app/blueprints/schedule/routes.py | `from app.models.scene_models import get_scenes` |
| app/models/location_models.py | app/blueprints/schedule/routes.py | `from app.models.location_models import get_locations` |
| app/models/schedule_models.py | app/blueprints/callsheets/routes.py | `from app.models.schedule_models import get_shoot_dates` |

### Budget/Expense Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/budget_models.py | app/blueprints/expenses/routes.py | `from app.models.budget_models import get_department_allocation` |
| app/models/department_models.py | app/blueprints/expenses/routes.py | `from app.models.department_models import get_departments` |
| app/models/expense_models.py | app/blueprints/reports/routes.py | `from app.models.expense_models import get_expenses` |
| app/models/budget_models.py | app/blueprints/reports/routes.py | `from app.models.budget_models import get_budget_summary` |

### Schedule/Reports Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/schedule_models.py | app/blueprints/reports/routes.py | `from app.models.schedule_models import get_shoot_dates, get_schedule_entries` |
| app/models/cast_models.py | app/blueprints/reports/routes.py | `from app.models.cast_models import get_cast_members` |

### App Factory Internal Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/project_models.py | app/__init__.py | `from app.models.project_models import get_active_project` |

### Cast-Scene Cross-Agent Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/cast_models.py | app/blueprints/scenes/routes.py | `from app.models.cast_models import add_cast_to_scene, remove_cast_from_scene, get_scene_cast` |

### Decorator Internal Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/project_models.py | app/blueprints/auth/routes.py | `from app.models.project_models import get_project` |

### Form Dropdown Wiring (crew)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/department_models.py | app/blueprints/crew/routes.py | `from app.models.department_models import get_departments` |

### Auth Decorator Wiring (all route agents consume)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/blueprints/auth/routes.py | ALL route agents | `from app.blueprints.auth.routes import login_required, require_project_member, require_role` |

### Database Wiring (all agents consume)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/database.py | ALL route agents | `from app.database import get_db` |

### Search Index Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/search_models.py | scenes, cast, crew, locations routes | `from app.models.search_models import index_entity, remove_entity` |

---

## Input Validation Prescriptions

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| POST /auth/logout | -- | login_required | redirect to login |
| POST /auth/login | username, password | required, strip | Flash "Invalid credentials", redirect |
| POST /auth/register | username, password, display_name | username 3-50 chars, password 8+ chars, display_name 1-100 | Flash specific error, redirect |
| POST /projects | title | required, strip, 1-200 chars | Flash "Title is required", redirect |
| POST /projects/\<id\>/edit | title, description, total_budget_cents | title required 1-200, budget int() try/except >= 0 | Flash error, redirect |
| POST /projects/\<id\>/phase | new_phase | must be in VALID_PHASE_TRANSITIONS[current_phase] | Flash "Invalid transition", redirect |
| POST /scenes/\<pid\> | scene_number, int_ext, day_night, page_count_eighths | scene_number required unique-per-project, int_ext in set, day_night in set, page_count int > 0 | Flash specific, redirect |
| POST /scenes/\<pid\>/\<sid\>/status | new_status | must be in VALID_SCENE_TRANSITIONS[current_status] | Flash "Invalid transition", redirect |
| POST /cast/\<pid\> | name, character_name, cast_id_number | name required, character required, cast_id int 1-99 unique-per-project | Flash specific, redirect |
| POST /crew/\<pid\> | name, role_title, department_id | name required, role_title required, department_id must exist in project | Flash specific, redirect |
| POST /locations/\<pid\> | name | required 1-200 chars | Flash "Name is required", redirect |
| POST /schedule/\<pid\> | scene_id, location_id, shoot_date | scene_id must exist, location_id must exist, date YYYY-MM-DD format | Flash specific, redirect |
| POST /schedule/\<pid\>/\<eid\>/delete | -- | entry must exist, entry.project_id == pid | 404 |
| POST /schedule/\<pid\>/reorder | JSON: order (list[int]), shoot_date | all IDs belong to project+date, no missing/extra vs DB set | JSON 400 with error |
| POST /call-sheets/\<pid\>/generate | shoot_date (form) | date must have schedule entries | Flash "No scenes scheduled", redirect |
| POST /budget/\<pid\>/allocate | department_id, amount_cents | department must exist in project, amount int >= 0, SUM <= total_budget | Flash with remaining, redirect |
| POST /budget/\<pid\>/line-items | category_id, description, estimated_cents | category must exist, description required, cents int >= 0 | Flash specific, redirect |
| POST /expenses/\<pid\> | department_id, amount_cents, vendor, expense_date, category_id | amount int > 0, vendor required, date YYYY-MM-DD, dept must exist, spent+amount <= allocated | Flash with remaining, redirect |
| POST /expenses/\<pid\>/\<eid\>/delete | -- | expense must exist, ownership check | 404 or 403 |
| POST /scenes/\<pid\>/\<sid\>/edit | scene_number, int_ext, day_night, page_count_eighths | same as create: scene_number unique, int_ext in set, day_night in set, page_count int > 0 | Flash specific, redirect |
| POST /cast/\<pid\>/\<cid\>/edit | name, character_name, cast_id_number | same as create: name required, character required, cast_id 1-99 | Flash specific, redirect |
| POST /crew/\<pid\>/\<cid\>/edit | name, role_title, department_id | same as create: name required, role_title required, dept exists | Flash specific, redirect |
| POST /departments/\<pid\>/\<did\>/head | user_id | user_id must exist and be a project member | Flash "User not found", redirect |
| POST /locations/\<pid\>/\<lid\>/edit | name | required 1-200 chars | Flash "Name is required", redirect |
| POST /budget/\<pid\>/line-items/\<iid\>/edit | estimated_cents, actual_cents | int() try/except >= 0 for each | Flash "Invalid amount", redirect |
| POST /expenses/\<pid\>/\<eid\>/approve | -- | expense must exist, expense.project_id == pid | 404 |
| POST /call-sheets/\<pid\>/\<csid\>/publish | -- | call_sheet must exist, cs.project_id == pid, cs.status == 'draft' | Flash "Already published", redirect |
| GET /search/\<pid\>?q= | q (query param) | strip, sanitize FTS5 operators, wrap in quotes | Empty results if empty |

**Money unit convention (FC55 — single units rule):**
- **Forms submit DOLLARS** in fields named WITHOUT a `_cents` suffix: `amount`,
  `estimated`, `actual`, `total_budget`. Templates use these exact field names.
- **Routes parse dollars → integer cents** via the pattern below before calling any
  model function. **Model functions ALWAYS receive and store integer `*_cents`.**
- The `amount_cents` references in the Input Validation table above denote the *parsed*
  value passed to the model — NOT the form field name.

```python
# Generic money parse — `field` is the dollars form field ('amount', 'estimated', ...)
try:
    cents = int(round(float(request.form[field]) * 100))
except (ValueError, TypeError, KeyError):
    flash('Invalid amount', 'error')
    return redirect(...)
if cents < 0:                      # use `<= 0` for expense amount (must be positive)
    flash('Amount must be non-negative', 'error')
    return redirect(...)
```

---

## Coordinated Behaviors

| Surface | Rule | Owner |
|---------|------|-------|
| Blueprint registration | All blueprints registered in `create_app()` with exact `url_prefix` from Route Table | scaffold agent |
| CSRF token syntax | All POST forms: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` (WITH parentheses) | ALL route agents |
| CSRF meta tag | `base.html` includes `<meta name="csrf-token" content="{{ csrf_token() }}">` for JS | scaffold agent |
| Base template | All templates extend `base.html` via `{% extends "base.html" %}` | ALL template agents |
| Base template blocks | `{% block title %}` and `{% block content %}` | scaffold agent defines, all fill |
| Session keys | `session['user_id']` (int), `session['username']` (str) | auth agent sets, all read |
| Flash categories | `success` (green), `error` (red), `warning` (yellow), `info` (blue) | ALL route agents |
| Flash pattern | `flash('Message text', 'category')` — no HTML in messages | ALL route agents |
| Money display | `{{ amount_cents \| dollars }}` — renders "$1,500.00" | ALL template agents |
| Page count display | `{{ eighths \| page_count }}` — renders "1 4/8" | scenes, schedule template agents |
| Date format | Display dates as `{{ date }}` (YYYY-MM-DD stored, displayed as-is in Phase 1) | ALL template agents |
| Timestamps | All timestamps use SQL `datetime('now')`, NEVER Python `datetime.now()` | ALL model agents |
| Navbar links | Ordered: Dashboard, Scenes, Cast, Crew, Departments, Locations, Schedule, Call Sheets, Budget*, Expenses*, Reports, Search. *Budget/Expenses only for producer/dept_head | scaffold agent (base.html) |
| Navbar role check | `{% if session.get('user_id') %}` for logged-in items. Budget: check g.member.role via context processor | scaffold agent |
| Strip colors | CSS classes: `strip-day-ext` (yellow), `strip-day-int` (white), `strip-night-int` (blue), `strip-night-ext` (green). NEVER use Bootstrap `bg-*` | scaffold agent (CSS), schedule agent (templates) |
| Status badges | Use `escape()` before `Markup()` per FC47 | ALL agents using status display |
| Logout | POST form with CSRF, never GET | auth agent + base.html |
| Table styling | Bootstrap table classes: `table table-dark table-striped table-hover` | ALL template agents |
| Card styling | Bootstrap dark: `card bg-dark border-secondary` | ALL template agents |
| Empty states | Show "No [items] yet. Add one?" with link to create page | ALL list template agents |
| Error 404 | Use `abort(404)` after failed DB lookups, before any writes | ALL route agents |
| Error 403 | Use `abort(403)` after role/ownership check failure | ALL route agents |

---

## Template Contracts

### Session Keys

| Key | Set By | Read By | Example |
|-----|--------|---------|---------|
| `session['user_id']` | auth agent (login route) | `login_required` decorator, base.html navbar | `session.clear()` then `session['user_id'] = user['id']` |
| `session['username']` | auth agent (login route) | base.html greeting | `session['username'] = user['username']` |

### Base Template

| Item | Value |
|------|-------|
| Filename | `app/templates/base.html` |
| Owner | scaffold agent |
| Extended by | ALL template agents via `{% extends "base.html" %}` |
| Bootstrap theme | Dark: `<html data-bs-theme="dark">` |
| CDN | Bootstrap 5.3 + SortableJS from cdn.jsdelivr.net |

### Block Names

| Block | Purpose | Required? |
|-------|---------|-----------|
| `{% block title %}` | Page title in `<title>` tag | Yes |
| `{% block content %}` | Main page content | Yes |
| `{% block scripts %}` | Page-specific JS (after Bootstrap JS) | No (schedule agent uses this) |

---

## Transaction Contracts

| Function | Transaction | Commits? | Error Handling |
|----------|-------------|----------|----------------|
| `create_user` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `create_project` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `transition_project_phase` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK (re-check current phase inside lock) |
| `create_scene` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `update_scene` | none | NO | caller commits |
| `transition_scene_status` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK (re-check current status inside lock) |
| `create_cast_member` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `add_cast_to_scene` | none | NO | caller commits |
| `remove_cast_from_scene` | none | NO | caller commits |
| `create_crew_member` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `assign_department_head` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `create_location` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `create_schedule_entry` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK (TOCTOU duplicate check inside lock) |
| `reorder_schedule` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK (full ID set validation inside lock) |
| `delete_schedule_entry` | none | NO | caller commits |
| `generate_call_sheet` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK (multi-table: call_sheets + call_sheet_scenes + call_sheet_cast) |
| `publish_call_sheet` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `allocate_budget` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK (SUM check inside lock) |
| `create_line_item` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `update_line_item` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `create_expense` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK; returns None (not raise) on overspend — re-check spent+amount<=allocated inside lock, spent_cents update in same txn |
| `delete_expense` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK (spent_cents rollback in same txn) |
| `approve_expense` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `index_entity` | none | NO | caller commits (fire-and-forget, no transaction needed for FTS5 insert) |
| `remove_entity` | none | NO | caller commits |

**Compound write guidance for scenes routes:**
When a scenes route calls `update_scene` + `add_cast_to_scene` + `index_entity` in sequence, wrap all three in a single transaction:
```python
conn.execute('BEGIN IMMEDIATE')
try:
    update_scene(conn, scene_id, ...)
    add_cast_to_scene(conn, scene_id, cast_member_id)
    index_entity(conn, 'scene', scene_id, ...)
    conn.execute('COMMIT')
except Exception:
    conn.execute('ROLLBACK')
    raise
```

**Pattern for all BEGIN IMMEDIATE functions:**
```python
def some_write_function(conn, ...):
    try:
        conn.execute('BEGIN IMMEDIATE')
        # ... re-check constraints inside lock ...
        # ... perform writes ...
        conn.execute('COMMIT')
        return result
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

---

## Authorization Matrix

| Route | Mode | Roles Allowed | Ownership Check |
|-------|------|---------------|-----------------|
| GET /auth/login | public | all | N/A |
| POST /auth/login | public | all | N/A |
| GET /auth/register | public | all | N/A |
| POST /auth/register | public | all | N/A |
| POST /auth/logout | login_required | all | N/A |
| GET /projects/new | login_required | all | N/A |
| POST /projects | login_required | all | N/A |
| GET /projects/\<id\> | role-only | all members | `require_project_member` |
| GET /projects/\<id\>/edit | role-only | producer | `require_role('producer')` |
| POST /projects/\<id\>/edit | role-only | producer | `require_role('producer')` |
| POST /projects/\<id\>/phase | role-only | producer | `require_role('producer')` |
| GET /scenes/\<pid\> | role-only | all members | `require_project_member` |
| POST /scenes/\<pid\> | role-only | producer, ad | `require_role('producer','ad')` |
| GET /scenes/\<pid\>/\<sid\> | role-only | all members | `require_project_member` + scene.project_id == pid |
| POST /scenes/\<pid\>/\<sid\>/edit | role-only | producer, ad | `require_role` + scene.project_id == pid |
| POST /scenes/\<pid\>/\<sid\>/status | role-only | producer, ad | `require_role` + scene.project_id == pid |
| GET /cast/\<pid\> | role-only | all members | `require_project_member` |
| POST /cast/\<pid\> | role-only | producer, ad | `require_role('producer','ad')` |
| POST /cast/\<pid\>/\<cid\>/edit | role-only | producer, ad | `require_role` + cast.project_id == pid |
| GET /crew/\<pid\> | role-only | all members | `require_project_member` |
| POST /crew/\<pid\> | role-only | producer, ad, department_head | `require_role` + dept_head: own dept only |
| POST /crew/\<pid\>/\<cid\>/edit | role-only | producer, ad, department_head | `require_role` + crew.project_id == pid + dept_head: own dept only |
| GET /departments/\<pid\> | role-only | all members | `require_project_member` |
| GET /departments/\<pid\>/\<did\> | role-only | all members | `require_project_member` + dept.project_id == pid |
| POST /departments/\<pid\>/\<did\>/head | role-only | producer | `require_role('producer')` + dept.project_id == pid |
| GET /locations/\<pid\> | role-only | all members | `require_project_member` |
| POST /locations/\<pid\> | role-only | producer, ad | `require_role('producer','ad')` |
| POST /locations/\<pid\>/\<lid\>/edit | role-only | producer, ad | `require_role` + loc.project_id == pid |
| GET /schedule/\<pid\> | role-only | all members | `require_project_member` |
| POST /schedule/\<pid\> | role-only | producer, ad | `require_role('producer','ad')` |
| POST /schedule/\<pid\>/reorder | role-only | producer, ad | `require_role('producer','ad')` |
| POST /schedule/\<pid\>/\<eid\>/delete | role-only | producer, ad | `require_role` + entry.project_id == pid |
| GET /call-sheets/\<pid\> | role-only | all members | `require_project_member` |
| POST /call-sheets/\<pid\>/generate | role-only | producer, ad | `require_role('producer','ad')` |
| GET /call-sheets/\<pid\>/\<csid\> | role-only | all members | `require_project_member` + cs.project_id == pid |
| POST /call-sheets/\<pid\>/\<csid\>/publish | role-only | producer, ad | `require_role` + cs.project_id == pid |
| GET /budget/\<pid\> | role-only | producer | `require_role('producer')` |
| GET /budget/\<pid\>/top-sheet | role-only | producer | `require_role('producer')` |
| POST /budget/\<pid\>/allocate | role-only | producer | `require_role('producer')` |
| POST /budget/\<pid\>/line-items | role-only | producer | `require_role('producer')` |
| POST /budget/\<pid\>/line-items/\<iid\>/edit | role-only | producer | `require_role('producer')` + item.project_id == pid |
| GET /expenses/\<pid\> | role+ownership | producer, department_head | producer: all; dept_head: own dept (dept.head_id == g.user['id']) |
| POST /expenses/\<pid\> | role+ownership | producer, department_head | producer: any dept; dept_head: own dept only |
| POST /expenses/\<pid\>/\<eid\>/delete | role+ownership | producer, department_head | producer: any; dept_head: own dept + created_by == g.user['id'] |
| POST /expenses/\<pid\>/\<eid\>/approve | role-only | producer | `require_role('producer')` |
| GET /reports/\<pid\> | role-only | all members | `require_project_member` |
| GET /reports/\<pid\>/budget-summary | role-only | producer | `require_role('producer')` |
| GET /reports/\<pid\>/dood | role-only | all members | `require_project_member` |
| GET /reports/\<pid\>/progress | role-only | all members | `require_project_member` |
| GET /search/\<pid\> | role-only | all members | `require_project_member` |
| GET /scenes/\<pid\>/new | role-only | producer, ad | `require_role('producer','ad')` |
| GET /scenes/\<pid\>/\<sid\>/edit | role-only | producer, ad | `require_role` + scene.project_id == pid |
| GET /cast/\<pid\>/new | role-only | producer, ad | `require_role('producer','ad')` |
| GET /cast/\<pid\>/\<cid\> | role-only | all members | `require_project_member` + cast.project_id == pid |
| GET /crew/\<pid\>/new | role-only | producer, ad, department_head | `require_role` + dept_head: own dept |
| GET /crew/\<pid\>/\<cid\> | role-only | all members | `require_project_member` + crew.project_id == pid |
| GET /locations/\<pid\>/new | role-only | producer, ad | `require_role('producer','ad')` |
| GET /locations/\<pid\>/\<lid\> | role-only | all members | `require_project_member` + loc.project_id == pid |
| GET /schedule/\<pid\>/day/\<date\> | role-only | all members | `require_project_member` |
| GET /schedule/\<pid\>/new | role-only | producer, ad | `require_role('producer','ad')` |
| GET /budget/\<pid\>/line-items/new | role-only | producer | `require_role('producer')` |
| GET /expenses/\<pid\>/new | role+ownership | producer, department_head | producer: any; dept_head: own dept |

**IDOR Prevention Pattern (FC35):**
After every database lookup on a detail/edit/delete route, verify the resource belongs to the current project:
```python
scene = get_scene(conn, scene_id)
if scene is None:
    abort(404)
if scene['project_id'] != project_id:
    abort(404)  # Use 404 not 403 to avoid info leak
```

### Department-Head Ownership Enforcement (F-H6 — exact code, not prose)

`require_role(...)` only checks the role string. The `department_head` scope ("own dept
only") MUST be enforced in the route body with the code below. **Producer and AD are
unrestricted** — these checks apply ONLY when `g.member['role'] == 'department_head'`.
A head owns a department iff `departments.head_id == g.user['id']`.

```python
# Shared helpers (crew routes + expenses routes)
def _allowed_dept_ids(conn, project_id):
    """Set of department ids this user heads. Empty for non-heads."""
    return {d['id'] for d in get_departments(conn, project_id)
            if d['head_id'] == g.user['id']}

def _is_head():
    return g.member['role'] == 'department_head'
```

**Crew — `GET /crew/<pid>/new` and `POST /crew/<pid>`:**
```python
allowed = _allowed_dept_ids(conn, project_id)
if _is_head() and not allowed:
    abort(403)                                   # head of nothing
# GET /new: if _is_head(), pass only [d for d in get_departments(...) if d['id'] in allowed]
#           to the form dropdown; otherwise pass all departments.
# POST: target department must be permitted for a head
if _is_head() and int(request.form['department_id']) not in allowed:
    abort(403)
```

**Crew — `POST /crew/<pid>/<cid>/edit`:**
```python
crew = get_crew_member(conn, cid)
if crew is None or crew['project_id'] != project_id:
    abort(404)
if _is_head():
    allowed = _allowed_dept_ids(conn, project_id)
    if not allowed:
        abort(403)
    if crew['department_id'] not in allowed:                 # existing dept must be owned
        abort(404)
    if int(request.form['department_id']) not in allowed:    # target dept must be owned
        abort(403)
```

**Expenses — `GET /expenses/<pid>` (list):**
```python
if _is_head():
    allowed = _allowed_dept_ids(conn, project_id)
    if not allowed:
        abort(403)
    expenses = [e for d in allowed for e in get_expenses(conn, project_id, department_id=d)]
else:                                                        # producer: all
    expenses = get_expenses(conn, project_id)
```

**Expenses — `GET /expenses/<pid>/new`:**
```python
if _is_head():
    allowed = _allowed_dept_ids(conn, project_id)
    if not allowed:
        abort(403)
    departments = [d for d in get_departments(conn, project_id) if d['id'] in allowed]
else:
    departments = get_departments(conn, project_id)
```

**Expenses — `POST /expenses/<pid>` (create):**
```python
dept_id = int(request.form['department_id'])
if _is_head() and dept_id not in _allowed_dept_ids(conn, project_id):
    abort(403)
# ...then the money parse + create_expense(...) -> None on overspend -> flash remaining.
```

**Expenses — `POST /expenses/<pid>/<eid>/delete`:**
```python
expense = get_expense(conn, eid)
if expense is None or expense['project_id'] != project_id:
    abort(404)
if _is_head():
    allowed = _allowed_dept_ids(conn, project_id)
    if expense['department_id'] not in allowed or expense['created_by'] != g.user['id']:
        abort(403)                          # head: own dept AND own expense
```

---

## Negative Constraints (Do NOT Rules)

1. Do NOT use Bootstrap `bg-*` utilities for strip colors — use `.strip-day-ext`, `.strip-day-int`, `.strip-night-int`, `.strip-night-ext`
2. Do NOT store `remaining` in department_budgets — always compute as `allocated_cents - spent_cents`
3. Do NOT use Python `datetime.now()` — use SQL `datetime('now')` for all timestamps
4. Do NOT set `conn.row_factory` in model functions — `get_db()` sets it once
5. Do NOT commit inside model functions unless the Transaction Contracts table says "commits internally"
6. Do NOT use `with get_db() as conn:` — `get_db()` is NOT a context manager
7. Do NOT use `executescript()` for any runtime operations — only in `init_db()`
8. Do NOT hardcode passwords — read from environment variables
9. Do NOT use bare `except Exception` when catching `IntegrityError` — catch `sqlite3.IntegrityError` specifically
10. Do NOT use `{{ csrf_token }}` (no parens) — always `{{ csrf_token() }}`
11. Do NOT add routes that duplicate the blueprint url_prefix — paths are RELATIVE to prefix
12. Do NOT use `Markup()` without `escape()` on interpolated variables
13. Do NOT create ANY database triggers for FTS5 sync — the index has a single writer: explicit `index_entity()`/`remove_entity()` calls from routes (FC52). Routes MUST call them in the same transaction as the source-row write.
14. Do NOT pass unsanitized user input to FTS5 MATCH — strip operators, wrap in quotes
15. Do NOT use `session['logged_in']` — use `session['user_id']` (integer, not boolean)

---

## SortableJS Class-Name Contract

These 3 names MUST match across HTML template, JavaScript, and Python exactly:

| Surface | HTML Template (schedule agent) | JavaScript (schedule agent) | Python Route (schedule agent) |
|---------|------|------|------|
| Container ID | `id="schedule-list"` | `document.getElementById('schedule-list')` | -- |
| Item class | `class="schedule-item"` | `.querySelectorAll('.schedule-item')` | -- |
| Drag handle | `class="drag-handle"` | `handle: '.drag-handle'` | -- |
| Item data-id | `data-id="{{ entry['id'] }}"` | `el.dataset.id` | `request.json['order']` (list of int IDs) |
| Strip badge class | `class="strip-badge {{ entry['strip_color_class'] }}"` | -- | `strip_color_class` from model |
| Move buttons (a11y) | `<button class="btn-move-up">` / `<button class="btn-move-down">` | `.btn-move-up`, `.btn-move-down` click handlers call same reorder endpoint | Same reorder endpoint |
| Reorder endpoint | -- | `fetch('/schedule/<pid>/reorder', ...)` | `@bp.route('/<int:project_id>/reorder', methods=['POST'])` |
| JSON body | -- | `JSON.stringify({order: ids, shoot_date: currentDate})` | `request.json['order']`, `request.json['shoot_date']` |
| CSRF header | -- | `'X-CSRFToken': csrfToken` | validated by flask-wtf |

**strip_color_class derivation (in schedule_models):**
```python
def _strip_color(int_ext, day_night):
    if day_night == 'NIGHT':
        return 'strip-night-ext' if int_ext == 'EXT' else 'strip-night-int'
    return 'strip-day-ext' if int_ext == 'EXT' else 'strip-day-int'
```

---

## Call Sheet Generation Algorithm

Prescribed exactly. The callsheets agent MUST implement `generate_call_sheet` per this
algorithm. **A call sheet lists ONLY cast working on `shoot_date`** (no held cast — `H` is
DOOD-only). Each listed cast member's `status` is the Start/Work/Finish marker for that
date, computed over their distinct scheduled shoot dates across the whole project.

```python
def generate_call_sheet(conn, project_id, shoot_date):
    """Returns call_sheet_id. Commits internally (BEGIN IMMEDIATE, multi-table:
    call_sheets + call_sheet_scenes + call_sheet_cast)."""
    try:
        conn.execute('BEGIN IMMEDIATE')

        # 1. Scenes scheduled that day, in schedule order
        entries = conn.execute('''
            SELECT scene_id, sort_order FROM schedule_entries
            WHERE project_id = ? AND shoot_date = ? ORDER BY sort_order
        ''', (project_id, shoot_date)).fetchall()
        # (caller/route already validated entries is non-empty -> "No scenes scheduled")
        scene_ids = [r['scene_id'] for r in entries]

        # 2. Header row (sheet_number = next per project)
        n = conn.execute('SELECT COALESCE(MAX(sheet_number),0)+1 AS n FROM call_sheets WHERE project_id = ?',
                         (project_id,)).fetchone()['n']
        cs_id = conn.execute('''INSERT INTO call_sheets (project_id, sheet_number, shoot_date)
                                VALUES (?, ?, ?)''', (project_id, n, shoot_date)).lastrowid

        # 3. Scene rows
        for r in entries:
            conn.execute('''INSERT INTO call_sheet_scenes (call_sheet_id, scene_id, sort_order)
                            VALUES (?, ?, ?)''', (cs_id, r['scene_id'], r['sort_order']))

        # 4. Working cast = cast assigned to any scene scheduled that day
        working_cast = conn.execute('''
            SELECT DISTINCT sc.cast_member_id
            FROM scene_cast sc
            JOIN schedule_entries se ON se.scene_id = sc.scene_id
            WHERE se.project_id = ? AND se.shoot_date = ?
        ''', (project_id, shoot_date)).fetchall()

        # 5. Per-member Start/Work/Finish status for THIS date
        for row in working_cast:
            cm_id = row['cast_member_id']
            dates = [d['shoot_date'] for d in conn.execute('''
                SELECT DISTINCT se.shoot_date
                FROM schedule_entries se
                JOIN scene_cast sc ON sc.scene_id = se.scene_id
                WHERE se.project_id = ? AND sc.cast_member_id = ?
                ORDER BY se.shoot_date
            ''', (project_id, cm_id)).fetchall()]
            first, last = dates[0], dates[-1]
            if first == last:
                status = 'SWF'
            elif shoot_date == first:
                status = 'SW'
            elif shoot_date == last:
                status = 'WF'
            else:
                status = 'W'
            conn.execute('''INSERT INTO call_sheet_cast (call_sheet_id, cast_member_id, status)
                            VALUES (?, ?, ?)''', (cs_id, cm_id, status))

        conn.execute('COMMIT')
        return cs_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

`get_call_sheet_cast(conn, call_sheet_id)` returns these rows joined to cast_members
(keys: cast_member_id, name, character_name, cast_id_number, status, pickup_time,
makeup_time, on_set_time, remarks). All statuses are in {W, SW, WF, SWF}.

---

## DOOD Derivation Algorithm

Prescribed exactly. The reports agent MUST implement this algorithm verbatim:

```python
def get_dood_grid(conn, project_id):
    """Generate Day Out of Days grid.
    Returns: list[dict] with keys: cast_member_id, name, character_name,
             cast_id_number, days: {shoot_date: status}
    Status values: W, SW, WF, SWF, H, or '' (blank)
    """
    # 1. Get all shoot dates in order
    shoot_dates = [row['shoot_date'] for row in conn.execute(
        'SELECT DISTINCT shoot_date FROM schedule_entries WHERE project_id = ? ORDER BY shoot_date',
        (project_id,)).fetchall()]

    # 2. Get all cast members
    cast = conn.execute(
        'SELECT id, name, character_name, cast_id_number FROM cast_members WHERE project_id = ? ORDER BY cast_id_number',
        (project_id,)).fetchall()

    # 3. For each cast member, find working days
    result = []
    for member in cast:
        working_days = set()
        for row in conn.execute('''
            SELECT DISTINCT se.shoot_date
            FROM schedule_entries se
            JOIN scene_cast sc ON sc.scene_id = se.scene_id
            WHERE se.project_id = ? AND sc.cast_member_id = ?
            ORDER BY se.shoot_date
        ''', (project_id, member['id'])).fetchall():
            working_days.add(row['shoot_date'])

        if not working_days:
            result.append({
                'cast_member_id': member['id'],
                'name': member['name'],
                'character_name': member['character_name'],
                'cast_id_number': member['cast_id_number'],
                'days': {d: '' for d in shoot_dates}
            })
            continue

        sorted_working = sorted(working_days)
        first_day = sorted_working[0]
        last_day = sorted_working[-1]

        days = {}
        for d in shoot_dates:
            if d in working_days:
                if first_day == last_day and d == first_day:
                    days[d] = 'SWF'
                elif d == first_day:
                    days[d] = 'SW'
                elif d == last_day:
                    days[d] = 'WF'
                else:
                    days[d] = 'W'
            elif first_day < d < last_day:
                days[d] = 'H'
            else:
                days[d] = ''

        result.append({
            'cast_member_id': member['id'],
            'name': member['name'],
            'character_name': member['character_name'],
            'cast_id_number': member['cast_id_number'],
            'days': days
        })

    return result
```

---

## Critical-Flow Tests

The tests agent MUST implement all 10 test cases from the brief. These go in `tests/test_critical_flows.py`:

```python
# Test 1: Call sheet generation end-to-end
# Create project -> add scenes -> add cast to scenes -> create schedule entries
# -> generate call sheet -> verify call sheet contains correct scenes, cast with statuses, and location

# Test 2: DOOD grid accuracy
# Schedule 3 scenes across 5 days with overlapping cast
# -> verify W/SW/WF/SWF/H statuses are correct for each cast member

# Test 3: Budget overspend rejection
# Allocate 1000 cents to department -> create expense for 1001 cents -> verify rejection

# Test 4: Expense rollback
# Create expense -> verify spent_cents incremented -> delete expense -> verify spent_cents restored

# Test 5: Department-head IDOR
# Log in as dept_head for Camera -> attempt to create expense for Sound -> verify 403

# Test 6: Crew-member budget IDOR
# Log in as crew member -> attempt GET /budget/<pid> -> verify 403

# Test 7: Schedule reorder validation
# POST /schedule/<pid>/reorder with IDs from wrong project -> verify rejection

# Test 8: FTS5 sanitization
# Search with '")(DROP TABLE' -> verify no 500, results returned safely

# Test 9: CSRF on JSON POST
# POST /schedule/<pid>/reorder without X-CSRFToken -> verify rejection (400 or 403) and order is not mutated

# Test 10: CSP allows SortableJS
# Verify Content-Security-Policy header includes script-src allowing cdn.jsdelivr.net
```

---

## Smoke Test File (FC8 Compliance)

```python
"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re
os.environ.setdefault("SECRET_KEY", "test-smoke-key-not-production")
os.environ.setdefault("ADMIN_PASSWORD", "test-strong-pw-123")
os.environ.setdefault("DATABASE", ":memory:")

from app import create_app

app = create_app()
client = app.test_client()

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS: {name}")
        passed += 1
    else:
        print(f"FAIL: {name} -- {detail}")
        failed += 1

# Phase 1: Public routes
r = client.get("/auth/login")
check("GET /auth/login (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/auth/register")
check("GET /auth/register (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/")
check("GET / (redirect to login)", r.status_code == 302, f"got {r.status_code}")

# Phase 2a: Auth with real CSRF
r = client.get("/auth/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Login form has CSRF token", m is not None, "csrf_token input not found")

csrf_token = m.group(1) if m else ""
r = client.post("/auth/login", data={
    "username": "producer",
    "password": os.environ["ADMIN_PASSWORD"],
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /auth/login (redirect)", r.status_code == 302, f"got {r.status_code}")

with client.session_transaction() as sess:
    check("Login sets session['user_id']",
          sess.get('user_id') is not None,
          f"session keys: {list(sess.keys())}")

# Phase 2b: Authenticated routes
r = client.get("/")
check("GET / (logged in, redirect to dashboard)", r.status_code in (200, 302), f"got {r.status_code}")

# Phase 3: Project-scoped routes (project_id=1 from seed)
project_routes = [
    "/scenes/1", "/cast/1", "/crew/1", "/departments/1",
    "/locations/1", "/schedule/1", "/call-sheets/1",
    "/budget/1", "/expenses/1", "/reports/1"
]
for route in project_routes:
    r = client.get(route)
    check(f"GET {route}", r.status_code == 200, f"got {r.status_code}")

# Phase 4: CSP header check
r = client.get("/auth/login")
csp = r.headers.get('Content-Security-Policy', '')
check("CSP includes cdn.jsdelivr.net", 'cdn.jsdelivr.net' in csp, f"CSP: {csp[:100]}")

# Summary
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
```

---

## File Assignment Boundaries

### Agent 1: scaffold

| File | Purpose |
|------|---------|
| app/__init__.py | App factory, blueprint registration, security headers, filters |
| app/templates/base.html | Base template with Bootstrap 5 dark, navbar, flash messages |
| app/static/css/style.css | Custom CSS (strip colors, dark theme overrides) |
| app/static/js/app.js | Shared JS utilities (CSRF token extraction) |
| run.py | `python run.py` entry point |
| requirements.txt | Python dependencies |
| .gitignore | Standard Python + test_smoke.py |

### Agent 2: auth

| File | Purpose |
|------|---------|
| app/blueprints/auth/__init__.py | empty |
| app/blueprints/auth/routes.py | Login, register, logout, decorators (login_required, require_project_member, require_role) |
| app/models/auth_models.py | create_user, authenticate, get_user |
| app/templates/auth/login.html | Login form |
| app/templates/auth/register.html | Registration form |

### Agent 3: projects

| File | Purpose |
|------|---------|
| app/blueprints/projects/__init__.py | empty |
| app/blueprints/projects/routes.py | Project CRUD, dashboard, phase transitions |
| app/models/project_models.py | create_project, get_project, get_active_project, get_project_stats, transition_project_phase |
| app/templates/projects/dashboard.html | Project overview with stats |
| app/templates/projects/new.html | New project form |
| app/templates/projects/edit.html | Edit project form |

### Agent 4: scenes

| File | Purpose |
|------|---------|
| app/blueprints/scenes/__init__.py | empty |
| app/blueprints/scenes/routes.py | Scene CRUD, element tagging, status transitions, cast assignment |
| app/models/scene_models.py | create_scene, get_scenes, get_scene, get_scenes_by_ids, transition_scene_status, update_scene |
| app/templates/scenes/list.html | Scene list with filters |
| app/templates/scenes/new.html | New scene form |
| app/templates/scenes/detail.html | Scene detail with elements and cast |
| app/templates/scenes/edit.html | Edit scene form |

### Agent 5: cast

| File | Purpose |
|------|---------|
| app/blueprints/cast/__init__.py | empty |
| app/blueprints/cast/routes.py | Cast member CRUD |
| app/models/cast_models.py | create_cast_member, get_cast_members, get_cast_member, get_cast_for_scenes, add_cast_to_scene, remove_cast_from_scene, get_scene_cast |
| app/templates/cast/list.html | Cast list |
| app/templates/cast/new.html | New cast member form |
| app/templates/cast/detail.html | Cast member detail |

### Agent 6: crew

| File | Purpose |
|------|---------|
| app/blueprints/crew/__init__.py | empty |
| app/blueprints/crew/routes.py | Crew member CRUD |
| app/models/crew_models.py | create_crew_member, get_crew_members, get_crew_by_department, get_crew_member |
| app/templates/crew/list.html | Crew list with department filter |
| app/templates/crew/new.html | New crew member form |
| app/templates/crew/detail.html | Crew member detail |

### Agent 7: departments

| File | Purpose |
|------|---------|
| app/blueprints/departments/__init__.py | empty |
| app/blueprints/departments/routes.py | Department list, detail, head assignment |
| app/models/department_models.py | get_departments, get_department, assign_department_head |
| app/templates/departments/list.html | Department list |
| app/templates/departments/detail.html | Department detail with crew roster |

### Agent 8: locations

| File | Purpose |
|------|---------|
| app/blueprints/locations/__init__.py | empty |
| app/blueprints/locations/routes.py | Location CRUD |
| app/models/location_models.py | create_location, get_locations, get_location |
| app/templates/locations/list.html | Location list |
| app/templates/locations/new.html | New location form |
| app/templates/locations/detail.html | Location detail |

### Agent 9: schedule

| File | Purpose |
|------|---------|
| app/blueprints/schedule/__init__.py | empty |
| app/blueprints/schedule/routes.py | Schedule CRUD, reorder endpoint |
| app/models/schedule_models.py | create_schedule_entry, get_schedule_entries, get_shoot_dates, reorder_schedule, delete_schedule_entry |
| app/templates/schedule/index.html | Shoot day list |
| app/templates/schedule/day.html | Day view with SortableJS drag-and-drop |
| app/templates/schedule/new.html | Add scene to schedule |
| app/static/js/schedule.js | SortableJS initialization and reorder POST |

### Agent 10: callsheets

| File | Purpose |
|------|---------|
| app/blueprints/callsheets/__init__.py | empty |
| app/blueprints/callsheets/routes.py | Call sheet generation, detail, publish |
| app/models/callsheet_models.py | generate_call_sheet, get_call_sheet, get_call_sheet_scenes, get_call_sheet_cast, publish_call_sheet |
| app/templates/callsheets/list.html | Call sheet list |
| app/templates/callsheets/detail.html | Formatted call sheet view |

### Agent 11: budget

| File | Purpose |
|------|---------|
| app/blueprints/budget/__init__.py | empty |
| app/blueprints/budget/routes.py | Budget overview, allocation, line items |
| app/models/budget_models.py | get_budget_summary, get_budget_categories, get_department_allocation, allocate_budget, create_line_item, update_line_item |
| app/templates/budget/index.html | Budget overview with categories |
| app/templates/budget/top_sheet.html | Top sheet summary |
| app/templates/budget/new_line_item.html | New line item form |

### Agent 12: expenses

| File | Purpose |
|------|---------|
| app/blueprints/expenses/__init__.py | empty |
| app/blueprints/expenses/routes.py | Expense CRUD, approval |
| app/models/expense_models.py | create_expense, delete_expense, approve_expense, get_expenses |
| app/templates/expenses/list.html | Expense list with filters |
| app/templates/expenses/new.html | New expense form |

### Agent 13: reports

| File | Purpose |
|------|---------|
| app/blueprints/reports/__init__.py | empty |
| app/blueprints/reports/routes.py | Reports index, budget summary, DOOD, progress |
| app/models/report_models.py | get_dood_grid, get_production_progress |
| app/templates/reports/index.html | Reports index |
| app/templates/reports/budget_summary.html | Budget summary report |
| app/templates/reports/dood.html | DOOD grid display |
| app/templates/reports/progress.html | Production progress |

### Agent 14: search

| File | Purpose |
|------|---------|
| app/blueprints/search/__init__.py | empty |
| app/blueprints/search/routes.py | Search page |
| app/models/search_models.py | search, index_entity, remove_entity |
| app/templates/search/results.html | Search results page |

### Agent 15: database

| File | Purpose |
|------|---------|
| schema.sql | All CREATE TABLE statements, indexes, FTS5 virtual table |
| app/database.py | get_db, close_db, init_db, seed_data, init_app |
| app/models/__init__.py | Re-export all model functions from all model files |

### Agent 16: tests

| File | Purpose |
|------|---------|
| test_smoke.py | FC8-compliant smoke tests |
| tests/__init__.py | empty |
| tests/test_critical_flows.py | 10 critical-flow tests from brief |
| tests/conftest.py | Test fixtures (app, client, auth helpers) |

---

## Swarm Agent Assignment

| # | Agent Name | Branch | Files (relative to project root) |
|---|-----------|--------|------|
| 1 | scaffold | swarm-070-scaffold | app/__init__.py, app/templates/base.html, app/static/css/style.css, app/static/js/app.js, run.py, requirements.txt, .gitignore |
| 2 | auth | swarm-070-auth | app/blueprints/auth/__init__.py, app/blueprints/auth/routes.py, app/models/auth_models.py, app/templates/auth/login.html, app/templates/auth/register.html |
| 3 | projects | swarm-070-projects | app/blueprints/projects/__init__.py, app/blueprints/projects/routes.py, app/models/project_models.py, app/templates/projects/dashboard.html, app/templates/projects/new.html, app/templates/projects/edit.html |
| 4 | scenes | swarm-070-scenes | app/blueprints/scenes/__init__.py, app/blueprints/scenes/routes.py, app/models/scene_models.py, app/templates/scenes/list.html, app/templates/scenes/new.html, app/templates/scenes/detail.html, app/templates/scenes/edit.html |
| 5 | cast | swarm-070-cast | app/blueprints/cast/__init__.py, app/blueprints/cast/routes.py, app/models/cast_models.py, app/templates/cast/list.html, app/templates/cast/new.html, app/templates/cast/detail.html |
| 6 | crew | swarm-070-crew | app/blueprints/crew/__init__.py, app/blueprints/crew/routes.py, app/models/crew_models.py, app/templates/crew/list.html, app/templates/crew/new.html, app/templates/crew/detail.html |
| 7 | departments | swarm-070-departments | app/blueprints/departments/__init__.py, app/blueprints/departments/routes.py, app/models/department_models.py, app/templates/departments/list.html, app/templates/departments/detail.html |
| 8 | locations | swarm-070-locations | app/blueprints/locations/__init__.py, app/blueprints/locations/routes.py, app/models/location_models.py, app/templates/locations/list.html, app/templates/locations/new.html, app/templates/locations/detail.html |
| 9 | schedule | swarm-070-schedule | app/blueprints/schedule/__init__.py, app/blueprints/schedule/routes.py, app/models/schedule_models.py, app/templates/schedule/index.html, app/templates/schedule/day.html, app/templates/schedule/new.html, app/static/js/schedule.js |
| 10 | callsheets | swarm-070-callsheets | app/blueprints/callsheets/__init__.py, app/blueprints/callsheets/routes.py, app/models/callsheet_models.py, app/templates/callsheets/list.html, app/templates/callsheets/detail.html |
| 11 | budget | swarm-070-budget | app/blueprints/budget/__init__.py, app/blueprints/budget/routes.py, app/models/budget_models.py, app/templates/budget/index.html, app/templates/budget/top_sheet.html, app/templates/budget/new_line_item.html |
| 12 | expenses | swarm-070-expenses | app/blueprints/expenses/__init__.py, app/blueprints/expenses/routes.py, app/models/expense_models.py, app/templates/expenses/list.html, app/templates/expenses/new.html |
| 13 | reports | swarm-070-reports | app/blueprints/reports/__init__.py, app/blueprints/reports/routes.py, app/models/report_models.py, app/templates/reports/index.html, app/templates/reports/budget_summary.html, app/templates/reports/dood.html, app/templates/reports/progress.html |
| 14 | search | swarm-070-search | app/blueprints/search/__init__.py, app/blueprints/search/routes.py, app/models/search_models.py, app/templates/search/results.html |
| 15 | database | swarm-070-database | schema.sql, app/database.py, app/models/__init__.py |
| 16 | tests | swarm-070-tests | test_smoke.py, tests/__init__.py, tests/test_critical_flows.py, tests/conftest.py |

---

## Acceptance Tests (EARS Notation)

### Happy Path
- WHEN a producer logs in with valid credentials THE SYSTEM SHALL redirect to the project dashboard
- WHEN a producer creates a scene and adds cast members THE SYSTEM SHALL display them in the scene detail view
- WHEN a producer schedules scenes to a shoot day THE SYSTEM SHALL display them in the stripboard with correct strip colors
- WHEN a producer drags to reorder schedule entries THE SYSTEM SHALL persist the new order via JSON POST
- WHEN a producer generates a call sheet for a shoot day THE SYSTEM SHALL include all scheduled scenes, only the cast working that day each with a call status in {W, SW, WF, SWF}, and the location
- WHEN a producer views the DOOD grid THE SYSTEM SHALL show correct W/SW/WF/SWF/H statuses per the derivation algorithm
- WHEN a producer allocates budget and logs an expense THE SYSTEM SHALL update spent_cents atomically

### Error Cases
- WHEN an expense would exceed department allocation THE SYSTEM SHALL reject with flash error showing remaining amount
- WHEN a department head attempts to create an expense for another department THE SYSTEM SHALL return 403
- WHEN a crew member attempts to access /budget THE SYSTEM SHALL return 403
- WHEN schedule reorder receives IDs from a different project THE SYSTEM SHALL return JSON 400
- WHEN a user searches with FTS5 operator characters THE SYSTEM SHALL return results safely without 500
- WHEN a JSON POST arrives without X-CSRFToken THE SYSTEM SHALL reject with 400 or 403

### Verification Commands
- `.venv/bin/python test_smoke.py` — all smoke tests pass
- `.venv/bin/python -m pytest tests/ -v` — all critical-flow tests pass

---

## Feed-Forward

- **Hardest decision:** Prescribing exact function signatures and return types for the 6 call sheet cross-boundary imports. Each must match character-for-character across the producer and consumer agents.
- **Rejected alternatives:** Centralizing all call sheet data aggregation in a single "call sheet service" module (rejected because it would require a 17th agent or violate vertical ownership).
- **Least confident:** Whether the SortableJS class-name contract (3-file match: HTML, JS, Python) will survive agent implementation without drift. The spec prescribes exact names, but this has produced P1s in 2 prior builds (Client Music Planner, GigSheet).

---

## Sources

- **Origin brainstorm:** docs/brainstorms/2026-06-02-film-production-pm-brainstorm.md
- **Authoritative brief:** docs/briefs/film-production-pm-autopilot-brief.md
- **Spec template:** docs/templates/shared-spec-flask.md
- **Prior builds:** RestaurantOps (29-agent), BrewOps (21-agent), GymFlow (26-agent), Flask Acid Test
