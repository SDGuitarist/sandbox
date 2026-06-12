---
title: "StackRx — Client Pain-Point Diagnostic & Stack Prescriber"
type: feat
status: planned
date: 2026-06-11
swarm: true
agents: 11
origin: docs/briefs/2026-06-11-stack-rx-brief.md
spec_version: 2026-06-11-stack-rx-spec
feed_forward:
  risk: "Seed-data web consistency — 26 questions x option scores x 8 pain categories x 23 rules x 18 solutions x hand-computed demo severities. One wrong points value silently shifts a demo severity and breaks the pinned acceptance numbers."
  verify_first: true
---

# StackRx — Shared Interface Spec

Sales-demo diagnostic tool for a tech consultant: create a client engagement, send a
token-gated adaptive interview (goals, operations, tools, bottlenecks, customers,
constraints), score answers into a pain-point diagnosis, generate a rule-based tech-stack
prescription (Quick Wins / Core Stack / Growth), and present a polished printable report.
Flask 3 + SQLite + Jinja2 + Bootstrap 5 dark + print CSS. 11-agent vertical swarm.
**No LLM, no external API calls — the engine is deterministic and table-driven (declared
constraint).** (authoritative brief: docs/briefs/2026-06-11-stack-rx-brief.md)

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
    # Default OFF: the sales demo runs over plain http on localhost/LAN. Set
    # SECURE_COOKIES=1 when serving behind TLS.
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SECURE_COOKIES', '0') == '1'

    csrf.init_app(app)

    # Security headers
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:;"
        )
        return response

    # Database (also runs idempotent init + seed -- see Database Connection)
    from app.database import init_app
    init_app(app)

    # Blueprint registration -- exact order
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.engagements.routes import bp as engagements_bp
    from app.blueprints.interview.routes import bp as interview_bp
    from app.blueprints.diagnosis.routes import bp as diagnosis_bp
    from app.blueprints.prescription.routes import bp as prescription_bp
    from app.blueprints.catalog.routes import bp as catalog_bp
    from app.blueprints.questions.routes import bp as questions_bp
    from app.blueprints.reports.routes import bp as reports_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(engagements_bp, url_prefix='/engagements')
    app.register_blueprint(interview_bp, url_prefix='/i')
    app.register_blueprint(diagnosis_bp, url_prefix='/diagnosis')
    app.register_blueprint(prescription_bp, url_prefix='/prescription')
    app.register_blueprint(catalog_bp, url_prefix='/catalog')
    app.register_blueprint(questions_bp, url_prefix='/questions')
    app.register_blueprint(reports_bp)  # NO url_prefix -- routes use absolute paths /reports/... and /r/...

    # Index route -- simple redirect
    @app.route('/')
    def index():
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        return redirect(url_for('engagements.index'))

    return app
```

**Requirements (requirements.txt):**
```
flask>=3.0
flask-wtf>=1.2
```

**Entry point (run.py):** `from app import create_app; app = create_app(); app.run(debug=os.environ.get('FLASK_DEBUG', '0') == '1', port=5000)` guarded by `if __name__ == '__main__':` — debug NEVER defaults on (this app runs live in client meetings).

**Trailing-slash convention (Werkzeug):** list routes are defined as `'/'` under their
blueprint prefix, so the canonical URLs are `/engagements/`, `/catalog/`, `/questions/`
(WITH trailing slash; a request without it gets a Werkzeug 308 redirect first). Every
URL in the Smoke Table, tests, and `url_for` redirects in this spec uses the canonical
trailing-slash form for these three pages.

---

## Database Schema

```sql
-- schema.sql (database agent owns this file)
-- All statements idempotent (IF NOT EXISTS). Seeding only runs when users table is empty.

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS engagements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    industry TEXT,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'created'
        CHECK (status IN ('created','in_progress','completed','published')),
    interview_token TEXT NOT NULL UNIQUE,
    report_token TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_engagements_status ON engagements(status);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qkey TEXT NOT NULL UNIQUE,
    section TEXT NOT NULL
        CHECK (section IN ('goals','operations','tools','bottlenecks','customers','constraints')),
    prompt TEXT NOT NULL,
    qtype TEXT NOT NULL CHECK (qtype IN ('single_choice','multi_choice','free_text')),
    sort_order INTEGER NOT NULL UNIQUE,
    depends_on_qkey TEXT REFERENCES questions(qkey),
    depends_on_value TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS question_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    value TEXT NOT NULL,
    label TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    UNIQUE(question_id, value)
);
CREATE INDEX IF NOT EXISTS idx_options_question ON question_options(question_id);

CREATE TABLE IF NOT EXISTS option_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    option_id INTEGER NOT NULL REFERENCES question_options(id) ON DELETE CASCADE,
    pain_category TEXT NOT NULL CHECK (pain_category IN
        ('manual_processes','disconnected_tools','no_visibility','customer_communication',
         'scheduling_booking','billing_invoicing','marketing_leads','team_coordination')),
    points INTEGER NOT NULL CHECK (points >= 0),
    UNIQUE(option_id, pain_category)
);
CREATE INDEX IF NOT EXISTS idx_scores_option ON option_scores(option_id);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    option_id INTEGER REFERENCES question_options(id) ON DELETE CASCADE,
    value_text TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(engagement_id, question_id, option_id)
);
CREATE INDEX IF NOT EXISTS idx_answers_engagement ON answers(engagement_id);

CREATE TABLE IF NOT EXISTS diagnoses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL UNIQUE REFERENCES engagements(id) ON DELETE CASCADE,
    computed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS diagnosis_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnosis_id INTEGER NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,
    pain_category TEXT NOT NULL CHECK (pain_category IN
        ('manual_processes','disconnected_tools','no_visibility','customer_communication',
         'scheduling_booking','billing_invoicing','marketing_leads','team_coordination')),
    raw_points INTEGER NOT NULL CHECK (raw_points >= 0),
    max_points INTEGER NOT NULL CHECK (max_points >= 0),
    severity_pct INTEGER NOT NULL CHECK (severity_pct BETWEEN 0 AND 100),
    UNIQUE(diagnosis_id, pain_category)
);

CREATE TABLE IF NOT EXISTS solutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skey TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('quick_win','core','growth')),
    description TEXT NOT NULL,
    cost_band TEXT NOT NULL CHECK (cost_band IN ('low','medium','high')),
    url TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pain_category TEXT NOT NULL CHECK (pain_category IN
        ('manual_processes','disconnected_tools','no_visibility','customer_communication',
         'scheduling_booking','billing_invoicing','marketing_leads','team_coordination')),
    min_severity_pct INTEGER NOT NULL CHECK (min_severity_pct BETWEEN 0 AND 100),
    budget_min TEXT CHECK (budget_min IN ('minimal','moderate','substantial')),
    maturity_min TEXT CHECK (maturity_min IN ('low','medium','high')),
    solution_id INTEGER NOT NULL REFERENCES solutions(id) ON DELETE RESTRICT,
    rationale TEXT NOT NULL,
    priority INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_rules_category ON rules(pain_category);

CREATE TABLE IF NOT EXISTS prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id INTEGER NOT NULL UNIQUE REFERENCES engagements(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prescription_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id INTEGER NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    solution_id INTEGER NOT NULL REFERENCES solutions(id) ON DELETE RESTRICT,
    pain_category TEXT CHECK (pain_category IN
        ('manual_processes','disconnected_tools','no_visibility','customer_communication',
         'scheduling_booking','billing_invoicing','marketing_leads','team_coordination')),
    rationale TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    is_overridden INTEGER NOT NULL DEFAULT 0,
    UNIQUE(prescription_id, solution_id)
);
CREATE INDEX IF NOT EXISTS idx_items_prescription ON prescription_items(prescription_id);
```

Notes:
- `prescription_items.pain_category` is NULL for consultant-added (manual) items; NULL passes the CHECK by SQL three-valued logic — intentional.
- `answers.option_id` is NULL for free_text answers. The `UNIQUE(engagement_id, question_id, option_id)` constraint does not dedupe NULL rows; `save_answer` enforces one-answer-per-question by delete-then-insert.
- No FTS5, no triggers, no virtual tables in this build.

---

## Database Connection (app/database.py)

```python
# database agent owns this file
import sqlite3
import os
from flask import g

DATABASE = os.environ.get('DATABASE', 'stackrx.db')
# NOTE: ':memory:' is NOT supported — get_db opens a new connection per request, and a
# plain in-memory SQLite DB is private to one connection. Tests MUST use a temp file
# (see Critical-Flow Tests / Smoke Table preambles).

def get_db():
    """Returns sqlite3.Connection with row_factory=sqlite3.Row and PRAGMAs set.
    NOT a context manager. One connection per request via flask.g."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Executes schema.sql (idempotent), then calls seed_all(conn) ONLY when the users
    table is empty. Commits once at the end.
    schema.sql is resolved PACKAGE-RELATIVE, never CWD-relative:
    os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
    IMPORT RULE: `from app.seeds import seed_all` happens INSIDE this function body
    (lazy import) -- seeds imports model modules; keeping it lazy prevents any
    database -> seeds -> models import chain from running at module-import time."""

def init_app(app):
    """Registers close_db on teardown and runs init_db() inside app context at startup."""
```

- `init_db` is the ONLY place `executescript()` is allowed.
- Seeding is guarded by `SELECT COUNT(*) FROM users` == 0 → run `seed_all`, single commit.
- `seed_all(conn)` lives in `app/seeds.py` (database agent) and requires `ADMIN_PASSWORD`
  env (raises `RuntimeError` if missing — fail closed). `ADMIN_USERNAME` defaults to
  `'consultant'`.

---

## Data Ownership

One writer module per table. "Seed" = `app/seeds.py` (database agent) writes at init time
only — this is the single documented exception to one-writer-per-table.

| Table | Owner (runtime writer) | Read By | Seeded? |
|-------|------------------------|---------|---------|
| users | auth_models | auth routes | YES (via auth_models.create_consultant) |
| engagements | engagement_models | interview, diagnosis, prescription, reports routes | YES (demo row, direct SQL) |
| questions | question_models | interview_models, diagnosis_models, questions routes | YES (direct SQL) |
| question_options | question_models | interview_models, diagnosis_models | YES (direct SQL) |
| option_scores | question_models (no runtime writes in v1 — seed-only) | diagnosis_models | YES (direct SQL) |
| answers | interview_models | diagnosis_models, reports routes (via get_answers), prescription_models (via get_constraint_profile) | YES (demo answers, direct SQL) |
| diagnoses | diagnosis_models | prescription_models, reports routes, diagnosis routes | YES (via diagnosis_models.compute_diagnosis) |
| diagnosis_scores | diagnosis_models | prescription_models, reports routes | YES (via compute_diagnosis) |
| solutions | solution_models | prescription_models, catalog routes, reports routes | YES (direct SQL, explicit IDs 1-18) |
| rules | rule_models (no runtime writes in v1 — seed-only) | prescription_models | YES (direct SQL, explicit IDs 1-23) |
| prescriptions | prescription_models | reports routes | YES (via prescription_models.generate_prescription) |
| prescription_items | prescription_models | reports routes | YES (via generate_prescription) |

---

## Constants & Enumerations

```python
# app/models/diagnosis_models.py (diagnosis agent) -- AUTHORITATIVE definitions
PAIN_CATEGORIES = {            # definition order only; ALL tie-breaks use pain_category ASC
                               # (see get_diagnosis ordering contract -- never insertion order)
    'manual_processes':       'Manual & Repetitive Work',
    'disconnected_tools':     'Disconnected Tools & Data Silos',
    'no_visibility':          'No Visibility / Reporting Gaps',
    'customer_communication': 'Customer Communication Gaps',
    'scheduling_booking':     'Scheduling & Booking Friction',
    'billing_invoicing':      'Billing & Payment Friction',
    'marketing_leads':        'Lead Generation & Follow-Up Gaps',
    'team_coordination':      'Team Coordination Overhead',
}
REPORTED_MIN_SEVERITY = 25     # categories below this never appear in reported list
REPORTED_CAP = 5               # max categories in reported list

def band_for(severity_pct) -> str:
    """0-24 'low', 25-49 'moderate', 50-74 'high', 75-100 'critical'. Bands are ALWAYS
    derived from severity_pct at read time -- never stored."""
```

```python
# app/models/engagement_models.py (engagements agent)
VALID_ENGAGEMENT_TRANSITIONS = {
    'created':     ('in_progress',),
    'in_progress': ('completed',),
    'completed':   ('published',),
    'published':   (),
}
```

```python
# app/models/prescription_models.py (prescription agent)
BUDGET_ORDER   = {'minimal': 0, 'moderate': 1, 'substantial': 2}
MATURITY_ORDER = {'low': 0, 'medium': 1, 'high': 2}
TIER_ORDER     = ('quick_win', 'core', 'growth')
TIER_LABELS    = {'quick_win': 'Quick Wins', 'core': 'Core Stack', 'growth': 'Growth'}
```

```python
# app/models/interview_models.py (interview agent)
CONSTRAINT_QKEYS = ('budget_tier', 'team_size', 'tech_maturity', 'timeline')
```

- `timeline` AND `team_size` are captured and displayed on the report; NEITHER is used
  in rule matching (v1 rules filter on budget_min/maturity_min only).
- Severity math: `severity_pct = (raw_points * 100) // max_points` (integer floor;
  `0` when `max_points == 0`). Never use `round()` — banker's rounding breaks tests.

---

## Model Functions

### auth_models.py (auth agent)

```python
# Returns: int (user_id) -- does NOT commit (called only by seeds inside the init transaction)
def create_consultant(conn, username, password) -> int: ...

# Returns: dict or None
# SECURITY: Constant-time -- always call check_password_hash even if user not found
#   DUMMY_HASH = generate_password_hash("dummy")
def authenticate(conn, username, password) -> dict | None: ...

# Returns: dict or None
def get_consultant(conn, user_id) -> dict | None: ...
```

### engagement_models.py (engagements agent)

```python
# Returns: int (engagement_id) -- commits internally (BEGIN IMMEDIATE).
# Generates interview_token = secrets.token_urlsafe(32).
def create_engagement(conn, business_name, contact_name, contact_email, industry, notes) -> int: ...

# Returns: list[dict] ordered created_at DESC (keys: all engagement columns)
def list_engagements(conn) -> list[dict]: ...

# Returns: dict or None (keys: id, business_name, contact_name, contact_email, industry,
#          notes, status, interview_token, report_token, created_at, updated_at)
def get_engagement(conn, engagement_id) -> dict | None: ...

# Returns: dict or None -- exact token match, any status
def get_engagement_by_token(conn, interview_token) -> dict | None: ...

# Returns: dict or None -- exact token match AND status == 'published'; else None.
# This function is the single enforcement point for public report visibility.
def get_engagement_by_report_token(conn, report_token) -> dict | None: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE); also sets updated_at
def update_engagement(conn, engagement_id, business_name, contact_name, contact_email, industry, notes) -> bool: ...

# Returns: bool -- does NOT commit (used inside compound transactions).
# Validates new_status against VALID_ENGAGEMENT_TRANSITIONS[current]; False if invalid.
# Also sets updated_at = datetime('now').
def transition_engagement_status(conn, engagement_id, new_status) -> bool: ...

# Returns: str (report_token) or None -- commits internally (BEGIN IMMEDIATE).
# Only valid when status == 'completed' (re-checked inside lock); transitions to
# 'published' and sets report_token = secrets.token_urlsafe(32). None if invalid status.
def publish_report(conn, engagement_id) -> str | None: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE); FK cascades remove answers,
# diagnoses, prescriptions.
def delete_engagement(conn, engagement_id) -> bool: ...
```

### question_models.py (questions agent)

```python
# Returns: list[dict] ordered sort_order ASC (keys: id, qkey, section, prompt, qtype,
#          sort_order, depends_on_qkey, depends_on_value, is_active)
def get_active_questions(conn) -> list[dict]: ...

# Returns: list[dict] -- all questions incl. inactive, ordered sort_order ASC
def get_all_questions(conn) -> list[dict]: ...

# Returns: dict or None
def get_question(conn, question_id) -> dict | None: ...

# Returns: list[dict] ordered sort_order ASC (keys: id, question_id, value, label, sort_order)
def get_options(conn, question_id) -> list[dict]: ...

# Returns: list[dict] (keys: option_id, option_value, pain_category, points) -- score
# rows for one question, for the admin score display on questions/list.html
def get_option_scores(conn, question_id) -> list[dict]: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE). v1 admin edit scope is prompt +
# is_active ONLY (structure and scoring change via seed data only).
def update_question(conn, question_id, prompt, is_active) -> bool: ...
```

### interview_models.py (interview agent)

```python
# Returns: dict or None -- the next VISIBLE unanswered active question, ordered by
# sort_order ASC. Visible = no dependency, OR the single_choice answer to
# depends_on_qkey equals depends_on_value. None = interview complete.
# Shape: question dict (as question_models.get_question) + 'options': list[dict].
def get_next_question(conn, engagement_id) -> dict | None: ...

# Returns: None -- does NOT commit (caller wraps in BEGIN IMMEDIATE).
# Deletes ALL existing answer rows for (engagement_id, question_id), then inserts:
#   single_choice: one row (option_id set, value_text NULL)
#   multi_choice:  one row per selected option (option_id set, value_text NULL)
#   free_text:     one row (option_id NULL, value_text set)
# option_values is list[str] (option `value` strings, empty for free_text).
# Raises ValueError on invalid option values (routes validate first; this is defensive).
def save_answer(conn, engagement_id, question_id, option_values, value_text) -> None: ...

# Returns: list[dict] -- one row per answer row, ordered question sort_order ASC then
# option sort_order ASC. Keys: question_id, qkey, section, prompt, qtype, sort_order,
# option_value, option_label, value_text.
def get_answers(conn, engagement_id) -> list[dict]: ...

# Returns: dict (keys: answered, total). total = count of currently VISIBLE active
# questions (dependency-satisfied or dependency-free); answered = count of those with
# at least one answer row.
def get_progress(conn, engagement_id) -> dict: ...

# Returns: dict (keys: budget_tier, team_size, tech_maturity, timeline) -- each the
# selected option `value` for the matching CONSTRAINT_QKEYS question, or None if
# unanswered. Derived at read time, NEVER stored.
def get_constraint_profile(conn, engagement_id) -> dict: ...
```

### diagnosis_models.py (diagnosis agent)

```python
# Returns: int (diagnosis_id) -- does NOT commit. Callers: compound blocks 1-2 wrap it
# in BEGIN IMMEDIATE; seeds call it inside init_db's implicit transaction (no BEGIN).
# Deletes any prior diagnosis for the engagement (cascade clears scores), recomputes
# from answers + option_scores per the Diagnosis Algorithm, inserts diagnoses +
# 8 diagnosis_scores rows (one per PAIN_CATEGORIES key).
def compute_diagnosis(conn, engagement_id) -> int: ...

# Returns: dict or None. Shape:
# { 'id', 'engagement_id', 'computed_at',
#   'scores':   [ {pain_category, label, raw_points, max_points, severity_pct, band} x8,
#                 ordered severity_pct DESC, raw_points DESC, pain_category ASC ],
#   'reported': same ordering, filtered severity_pct >= REPORTED_MIN_SEVERITY,
#               capped at REPORTED_CAP }
# 'reported' is the SINGLE shared definition consumed by both the prescription engine
# and the report -- never re-derive it elsewhere.
def get_diagnosis(conn, engagement_id) -> dict | None: ...

def band_for(severity_pct) -> str: ...   # see Constants
```

### prescription_models.py (prescription agent)

```python
# Returns: int (prescription_id) -- does NOT commit. Callers: compound blocks 1-2 wrap
# it in BEGIN IMMEDIATE; seeds call it inside init_db's implicit transaction (no BEGIN).
# Reads get_diagnosis(...)['reported'] + get_constraint_profile(...) + get_active_rules(...).
# See Prescription Algorithm.
def generate_prescription(conn, engagement_id) -> int: ...

# Returns: dict or None. Shape:
# { 'id', 'engagement_id', 'created_at',
#   'items': [ {id, solution_id, skey, name, tier, description, cost_band, url,
#               pain_category, category_label, rationale, sort_order, is_overridden,
#               is_manual} ordered sort_order ASC ],
#   'tiers': { 'quick_win': [...], 'core': [...], 'growth': [...] } -- same item dicts
#            grouped by tier, each list ordered sort_order ASC }
# is_manual = (pain_category IS NULL); category_label = PAIN_CATEGORIES[pain_category]
# or None for manual items.
def get_prescription(conn, engagement_id) -> dict | None: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE). Sets rationale, is_overridden=1.
def override_item(conn, item_id, rationale) -> bool: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE).
def remove_item(conn, item_id) -> bool: ...

# Returns: int (item_id) or None on duplicate solution -- commits internally
# (BEGIN IMMEDIATE). INSERT OR IGNORE on UNIQUE(prescription_id, solution_id);
# pain_category NULL, is_overridden=1, sort_order = MAX(sort_order)+1 (or 1 if empty).
# Duplicate detection: check cursor.rowcount == 0 after the INSERT OR IGNORE --
# lastrowid is UNRELIABLE after an ignored insert (may hold a stale rowid).
def add_item(conn, prescription_id, solution_id, rationale) -> int | None: ...
```

### rule_models.py (prescription agent)

```python
# Returns: list[dict] ordered priority ASC, id ASC (keys: id, pain_category,
# min_severity_pct, budget_min, maturity_min, solution_id, rationale, priority)
def get_active_rules(conn) -> list[dict]: ...
```

### solution_models.py (catalog agent)

```python
# Returns: list[dict] ordered tier (TIER_ORDER), then name ASC.
def list_solutions(conn, include_archived=False) -> list[dict]: ...

# Returns: dict or None (keys: id, skey, name, tier, description, cost_band, url,
#          is_archived, created_at)
def get_solution(conn, solution_id) -> dict | None: ...

# Returns: int (solution_id) or None on duplicate skey -- commits internally (BEGIN IMMEDIATE)
def create_solution(conn, skey, name, tier, description, cost_band, url) -> int | None: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE). skey is immutable.
def update_solution(conn, solution_id, name, tier, description, cost_band, url) -> bool: ...

# Returns: bool -- commits internally (BEGIN IMMEDIATE). Sets is_archived=1.
# Archived solutions are skipped by the prescription engine and hidden from add-item
# dropdowns; existing prescription items referencing them remain (FK RESTRICT).
def archive_solution(conn, solution_id) -> bool: ...
```

---

## Diagnosis Algorithm (exact — diagnosis agent implements verbatim)

```python
def compute_diagnosis(conn, engagement_id):
    """Returns diagnosis_id. Does NOT commit -- caller wraps in BEGIN IMMEDIATE."""
    # raw points: ONLY answers to active questions count, so raw <= max always holds
    # even after the consultant deactivates a question and recomputes (the schema CHECK
    # severity_pct <= 100 can never trip).
    raw = {key: 0 for key in PAIN_CATEGORIES}
    for r in conn.execute(
        "SELECT os.pain_category, SUM(os.points) AS pts "
        "FROM answers a "
        "JOIN questions q ON q.id = a.question_id AND q.is_active = 1 "
        "JOIN option_scores os ON os.option_id = a.option_id "
        "WHERE a.engagement_id = ? GROUP BY os.pain_category", (engagement_id,)):
        raw[r['pain_category']] = r['pts']

    # max_points: fixed denominator over ALL active questions, independent of branching
    # visibility. single_choice -> MAX(points) per category; multi_choice -> SUM(points)
    # per category (every option is selectable).
    maxes = {key: 0 for key in PAIN_CATEGORIES}
    for r in conn.execute(
        "SELECT q.id, os.pain_category, "
        "  CASE q.qtype WHEN 'multi_choice' THEN SUM(os.points) ELSE MAX(os.points) END AS contrib "
        "FROM questions q "
        "JOIN question_options o ON o.question_id = q.id "
        "JOIN option_scores os ON os.option_id = o.id "
        "WHERE q.is_active = 1 GROUP BY q.id, os.pain_category"):
        maxes[r['pain_category']] += r['contrib']

    conn.execute("DELETE FROM diagnoses WHERE engagement_id = ?", (engagement_id,))
    cur = conn.execute("INSERT INTO diagnoses (engagement_id) VALUES (?)", (engagement_id,))
    diagnosis_id = cur.lastrowid
    for key in PAIN_CATEGORIES:
        m = maxes[key]
        pct = (raw[key] * 100) // m if m > 0 else 0
        conn.execute(
            "INSERT INTO diagnosis_scores (diagnosis_id, pain_category, raw_points, "
            "max_points, severity_pct) VALUES (?, ?, ?, ?, ?)",
            (diagnosis_id, key, raw[key], m, pct))
    return diagnosis_id
```

Ordering contract for `get_diagnosis` lists: `severity_pct DESC, raw_points DESC,
pain_category ASC`. `reported` = first `REPORTED_CAP` entries with
`severity_pct >= REPORTED_MIN_SEVERITY`.

---

## Prescription Algorithm (exact — prescription agent implements verbatim)

```python
def generate_prescription(conn, engagement_id):
    """Returns prescription_id. Does NOT commit -- caller wraps in BEGIN IMMEDIATE."""
    diagnosis = get_diagnosis(conn, engagement_id)            # diagnosis_models (cross-boundary)
    profile = get_constraint_profile(conn, engagement_id)     # interview_models (cross-boundary)
    rules = get_active_rules(conn)                            # rule_models (priority ASC, id ASC)

    conn.execute("DELETE FROM prescriptions WHERE engagement_id = ?", (engagement_id,))
    cur = conn.execute("INSERT INTO prescriptions (engagement_id) VALUES (?)", (engagement_id,))
    prescription_id = cur.lastrowid

    sort_order = 0
    for score in diagnosis['reported']:                       # severity order is authoritative
        for rule in rules:
            if rule['pain_category'] != score['pain_category']:
                continue
            if rule['min_severity_pct'] > score['severity_pct']:
                continue
            if rule['budget_min'] is not None and (
                    profile['budget_tier'] is None
                    or BUDGET_ORDER[profile['budget_tier']] < BUDGET_ORDER[rule['budget_min']]):
                continue
            if rule['maturity_min'] is not None and (
                    profile['tech_maturity'] is None
                    or MATURITY_ORDER[profile['tech_maturity']] < MATURITY_ORDER[rule['maturity_min']]):
                continue
            archived = conn.execute("SELECT is_archived FROM solutions WHERE id = ?",
                                    (rule['solution_id'],)).fetchone()
            if archived is None or archived['is_archived']:
                continue
            sort_order += 1
            conn.execute(
                "INSERT OR IGNORE INTO prescription_items "
                "(prescription_id, solution_id, pain_category, rationale, sort_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (prescription_id, rule['solution_id'], score['pain_category'],
                 rule['rationale'], sort_order))
    return prescription_id
```

- Duplicate solutions across categories: first insertion wins (`INSERT OR IGNORE`);
  `sort_order` may have gaps — display order is `sort_order ASC`, gaps are fine.
- Zero reported categories → prescription row exists with zero items; report and
  prescription pages render the "no critical pain detected" empty-state block (200).

---

## Auth Decorator (auth agent — exact)

```python
# app/blueprints/auth/routes.py
from functools import wraps
from flask import session, redirect, url_for, g

def login_required(f):
    """Sets g.user (consultant dict); redirects to auth.login when no session."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        user_id = session.get('user_id')
        if user_id is None:
            return redirect(url_for('auth.login'))
        from app.database import get_db
        from app.models.auth_models import get_consultant
        g.user = get_consultant(get_db(), user_id)
        if g.user is None:
            session.clear()
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapped
```

There is only ONE role (the consultant). No require_role / membership decorators exist.
Client access is token-scoped, never session-scoped.

---

## Route Table

### auth (url_prefix=/auth)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /login | auth.login | public | auth/login.html |
| POST | /login | auth.login_post | public | redirect |
| POST | /logout | auth.logout | login_required | redirect |

### engagements (url_prefix=/engagements)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | / | engagements.index | login_required | engagements/list.html |
| GET | /new | engagements.new | login_required | engagements/new.html |
| POST | / | engagements.create | login_required | redirect |
| GET | /\<int:engagement_id\> | engagements.detail | login_required | engagements/detail.html |
| GET | /\<int:engagement_id\>/edit | engagements.edit | login_required | engagements/edit.html |
| POST | /\<int:engagement_id\>/edit | engagements.update | login_required | redirect |
| POST | /\<int:engagement_id\>/delete | engagements.delete | login_required | redirect |

### interview (url_prefix=/i) — public, token-gated

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<token\> | interview.welcome | public-token | interview/welcome.html |
| GET | /\<token\>/q | interview.question | public-token | interview/question.html (302 → done when complete) |
| POST | /\<token\>/answer | interview.answer | public-token | redirect |
| GET | /\<token\>/done | interview.done | public-token | interview/done.html |

### diagnosis (url_prefix=/diagnosis)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:engagement_id\> | diagnosis.detail | login_required | diagnosis/detail.html (200 with empty state if no diagnosis yet) |
| POST | /\<int:engagement_id\>/recompute | diagnosis.recompute | login_required | redirect |

### prescription (url_prefix=/prescription)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /\<int:engagement_id\> | prescription.detail | login_required | prescription/detail.html (200 with empty state if none yet) |
| POST | /items/\<int:item_id\>/override | prescription.override | login_required | redirect |
| POST | /items/\<int:item_id\>/remove | prescription.remove | login_required | redirect |
| POST | /\<int:engagement_id\>/items | prescription.add | login_required | redirect |
| POST | /\<int:engagement_id\>/publish | prescription.publish | login_required | redirect |

### catalog (url_prefix=/catalog)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | / | catalog.index | login_required | catalog/list.html |
| GET | /new | catalog.new | login_required | catalog/new.html |
| POST | / | catalog.create | login_required | redirect |
| GET | /\<int:solution_id\>/edit | catalog.edit | login_required | catalog/edit.html |
| POST | /\<int:solution_id\>/edit | catalog.update | login_required | redirect |
| POST | /\<int:solution_id\>/archive | catalog.archive | login_required | redirect |

### questions (url_prefix=/questions)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | / | questions.index | login_required | questions/list.html |
| GET | /\<int:question_id\>/edit | questions.edit | login_required | questions/edit.html |
| POST | /\<int:question_id\>/edit | questions.update | login_required | redirect |

### reports (NO url_prefix — absolute paths)

| Method | Path | Handler | Auth | Template |
|--------|------|---------|------|----------|
| GET | /reports/\<int:engagement_id\> | reports.engagement_report | login_required | reports/report.html |
| GET | /r/\<report_token\> | reports.public_report | public-token (published only) | reports/public_report.html |

Both report templates include `reports/_report_body.html` (shared partial, reports agent).

---

## Seed Data (database agent implements verbatim in app/seeds.py)

Seeds run in ONE transaction, committed once by `init_db`, only when `users` is empty.
Question/option/score inserts resolve foreign keys by `qkey`/`value` lookups — NEVER by
hardcoded question or option IDs. Solutions and rules use the explicit IDs below.

### Consultant user

`create_consultant(conn, os.environ.get('ADMIN_USERNAME', 'consultant'), os.environ['ADMIN_PASSWORD'])`
— raises RuntimeError if `ADMIN_PASSWORD` unset.

### Question Bank (26 questions; sections in order: goals, operations, tools, bottlenecks, customers, constraints)

Category abbreviations: MP=manual_processes, DT=disconnected_tools, NV=no_visibility,
CC=customer_communication, SB=scheduling_booking, BI=billing_invoicing,
ML=marketing_leads, TC=team_coordination.

| sort | qkey | section | qtype | prompt | options `value`: label (scores) |
|------|------|---------|-------|--------|---------------------------------|
| 10 | goal_primary | goals | single_choice | What is your #1 business goal for the next 12 months? | `grow_revenue`: Grow revenue (ML 5) · `save_time`: Save time / reduce busywork (MP 5) · `improve_cx`: Improve customer experience (CC 5) · `scale_team`: Scale the team (TC 5) |
| 20 | goal_blocker | goals | free_text | What's the single biggest thing standing between you and that goal? | — |
| 30 | growth_stage | goals | single_choice | Where is the business right now? | `starting`: Just starting out (—) · `steady`: Steady and established (—) · `growing_fast`: Growing fast (TC 3, NV 3) |
| 40 | manual_hours | operations | single_choice | How many hours per week does your team spend on manual data tasks (entry, copying, formatting)? | `under_2`: Under 2 (—) · `h2_5`: 2–5 (MP 3) · `h5_10`: 5–10 (MP 6) · `h10_20`: 10–20 (MP 8) · `over_20`: Over 20 (MP 10) |
| 50 | repetitive_tasks | operations | multi_choice | Which repetitive tasks eat the most time? (select all that apply) | `data_entry`: Data entry (MP 4) · `copy_between_tools`: Copying data between tools (DT 4, MP 2) · `manual_reporting`: Building reports by hand (NV 4, MP 2) · `chasing_payments`: Chasing payments/invoices (BI 4) · `scheduling_back_forth`: Scheduling back-and-forth (SB 4) · `lead_follow_up`: Following up with leads (ML 4) · `none`: None of these (—) |
| 60 | process_docs | operations | single_choice | Are your core processes documented? | `documented`: Yes, documented (—) · `partially`: Partially (TC 2) · `tribal`: It's all in people's heads (TC 4) |
| 70 | ops_pain_story | operations | free_text | Describe the most frustrating operational moment from the last month. | — |
| 80 | tool_count | tools | single_choice | How many separate software tools does the business run on? | `t0_2`: 0–2 (—) · `t3_5`: 3–5 (DT 2) · `t6_10`: 6–10 (DT 5) · `over_10`: More than 10 (DT 8) |
| 90 | tool_integration | tools | single_choice | Do those tools talk to each other? | `mostly`: Mostly integrated (—) · `some`: Some are connected (DT 4) · `none`: Nothing is connected (DT 8) |
| 100 | spreadsheet_reliance | tools | single_choice | How often does a spreadsheet hold business-critical data? | `rarely`: Rarely (—) · `sometimes`: Sometimes (MP 3, NV 2) · `constantly`: Constantly (MP 6, NV 4) |
| 110 | source_of_truth | tools | single_choice | Is there ONE place where you can see the true state of the business? | `yes`: Yes (—) · `no`: No (NV 6, DT 3) |
| 120 | tools_list | tools | free_text | List the main tools you use today. | — |
| 130 | bottleneck_area | bottlenecks | single_choice | Where does work pile up first? | `sales_pipeline`: Sales pipeline (ML 5) · `operations`: Operations/fulfillment (MP 5) · `communication`: Customer communication (CC 5) · `finances`: Invoicing/finances (BI 5) · `staffing`: Staffing/coordination (TC 5) |
| 140 | missed_opportunities | bottlenecks | single_choice | How often do leads or orders slip through the cracks? | `never`: Never (—) · `occasionally`: Occasionally (ML 4) · `regularly`: Regularly (ML 8) |
| 150 | reporting_time | bottlenecks | single_choice | How long does it take to answer "how did we do last month?" | `instant`: Minutes — it's on a dashboard (—) · `hours`: Hours of digging (NV 4) · `days_or_never`: Days, or we never really know (NV 8) |
| 160 | double_entry | bottlenecks | single_choice | Does the same data get typed into more than one system? | `no`: No (—) · `yes`: Yes (DT 5, MP 3) |
| 170 | bottleneck_story | bottlenecks | free_text | Tell me about the last time a bottleneck cost you money or a customer. | — |
| 180 | response_time | customers | single_choice | What's your typical response time to a customer inquiry? | `under_hour`: Under an hour (—) · `same_day`: Same day (CC 3) · `days`: A few days (CC 7) |
| 190 | booking_method | customers | single_choice | How do customers book or buy from you? | `online_self_serve`: Online, self-serve (—) · `email_phone`: Email / phone / DM back-and-forth (SB 6) · `in_person`: In person only (SB 4) |
| 195 | booking_hours | customers | single_choice — depends_on `booking_method` = `email_phone` | How many hours a week go to scheduling back-and-forth? | `few`: A couple (SB 2) · `several`: Several (SB 4) · `many`: Too many to count (SB 6) |
| 200 | payment_collection | customers | single_choice | How do you collect payment? | `automated`: Automated (online checkout / auto-invoice) (—) · `manual_invoices`: Manual invoices (BI 6) · `cash_checks`: Cash, checks, or memo apps (BI 8) |
| 210 | followup_system | customers | single_choice | What happens after a sale or a visit? | `automated_followup`: Automated follow-up (—) · `manual_followup`: Manual follow-up when we remember (ML 4, CC 2) · `no_followup`: Nothing (ML 8, CC 4) |
| 220 | budget_tier | constraints | single_choice | What monthly budget could you commit to tools and automation? | `minimal`: Minimal (under ~$100/mo) (—) · `moderate`: Moderate (~$100–500/mo) (—) · `substantial`: Substantial ($500+/mo) (—) |
| 230 | team_size | constraints | single_choice | How big is the team? | `solo`: Just me (—) · `small`: 2–5 people (—) · `medium`: 6–20 people (—) |
| 240 | tech_maturity | constraints | single_choice | How comfortable is the team with adopting new tech? | `low`: Hesitant (—) · `medium`: Comfortable with the basics (—) · `high`: Eager early adopters (—) |
| 250 | timeline | constraints | single_choice | When do you want improvements live? | `urgent`: Yesterday (—) · `quarter`: This quarter (—) · `flexible`: Flexible (—) |

Derived **max_points** per category (the build must reproduce these from the table above;
critical-flow test 3 asserts them): MP 37, DT 28, NV 25, CC 21, SB 16, BI 17, ML 30, TC 17.
(multi_choice q50 contributes its SUM per category: MP 4+2+2=8, DT 4, NV 4, BI 4, SB 4, ML 4.)

### Solution Catalog (explicit IDs — seeds insert with these exact IDs)

| id | skey | name | tier | cost_band | description (one sentence) |
|----|------|------|------|-----------|----------------------------|
| 1 | automation_glue | Automation Glue (Zapier / Make) | quick_win | low | Connect existing tools and kill copy-paste with no-code automations. |
| 2 | scheduling_tool | Self-Serve Scheduling (Calendly / Cal.com) | quick_win | low | Let customers book themselves and end the back-and-forth. |
| 3 | payment_automation | Payment Automation (Stripe Invoicing + Auto-Pay) | quick_win | low | Automated invoices, payment links, and reminders. |
| 4 | email_templates_sequences | Email Templates & Sequences | quick_win | low | Saved replies and simple sequences for consistent fast responses. |
| 5 | forms_intake | Smart Intake Forms (Tally / Jotform) | quick_win | low | Structured intake that routes leads instead of losing them. |
| 6 | shared_inbox | Shared Team Inbox (Front / Missive) | quick_win | medium | One inbox the whole team can see, assign, and never drop. |
| 7 | crm_core | CRM Core (HubSpot / Pipedrive) | core | medium | A real pipeline with stages, tasks, and follow-up automation. |
| 8 | ops_hub | Operations Hub (Airtable / Notion) | core | medium | One structured home for operational data to replace scattered spreadsheets. |
| 9 | accounting_suite | Accounting Suite (QuickBooks / Xero) | core | medium | Books, invoicing, and cash visibility in one system. |
| 10 | project_mgmt | Project Management (Asana / Trello) | core | low | Shared task boards so coordination stops living in chat threads. |
| 11 | dashboard_reporting | Live Dashboards (Looker Studio / Metabase) | core | medium | Always-current numbers instead of hand-built reports. |
| 12 | booking_platform | Full Booking Platform (Acuity / Squarespace Scheduling) | core | medium | End-to-end scheduling with payments, reminders, and packages. |
| 13 | sop_knowledge_base | SOP Knowledge Base (Notion / Trainual) | core | low | Documented processes so the business runs without tribal knowledge. |
| 14 | custom_integration | Custom Integration Layer | growth | high | Bespoke API sync where off-the-shelf connectors run out. |
| 15 | custom_webapp | Custom Web Application | growth | high | Purpose-built software for the workflow that defines the business. |
| 16 | ai_agent_assistant | AI Agent Assistant | growth | high | Agentic AI workflows that handle the repetitive load end-to-end. |
| 17 | data_warehouse_lite | Light Data Warehouse + BI | growth | high | Unified analytics across every system for real decision support. |
| 18 | customer_portal | Customer Self-Service Portal | growth | high | Clients check status, book, and pay without touching your inbox. |

### Rule Set (explicit IDs — seeds insert with these exact IDs; `—` = NULL)

| id | pain_category | min_sev | budget_min | maturity_min | solution_id | priority | rationale (one sentence, client-facing) |
|----|---------------|---------|------------|--------------|-------------|----------|------------------------------------------|
| 1 | manual_processes | 25 | — | — | 1 | 10 | Hours of manual work can be automated away with no-code glue between your existing tools. |
| 2 | manual_processes | 50 | substantial | — | 14 | 20 | At this volume of manual work, a bespoke integration layer pays for itself quickly. |
| 3 | manual_processes | 75 | — | high | 16 | 30 | Your manual load is critical and your team is ready — an AI agent can take the repetitive work end-to-end. |
| 4 | disconnected_tools | 25 | — | — | 1 | 10 | Connecting your existing tools stops the copy-paste between systems. |
| 5 | disconnected_tools | 50 | — | — | 8 | 20 | A single operations hub gives your scattered data one structured home. |
| 6 | disconnected_tools | 75 | substantial | — | 14 | 30 | Your stack is fragmented enough to justify a custom integration layer. |
| 7 | no_visibility | 25 | — | — | 11 | 10 | A live dashboard replaces hand-built reports with always-current numbers. |
| 8 | no_visibility | 50 | — | — | 8 | 20 | Centralizing operational data is the prerequisite for trustworthy reporting. |
| 9 | no_visibility | 75 | substantial | — | 17 | 30 | A light data warehouse unifies every system into real decision support. |
| 10 | customer_communication | 25 | — | — | 4 | 10 | Templates and sequences make every response fast and consistent. |
| 11 | customer_communication | 50 | — | — | 6 | 20 | A shared inbox means no customer message is ever dropped or double-answered. |
| 12 | customer_communication | 75 | — | — | 7 | 30 | A CRM puts every customer conversation and follow-up in one accountable place. |
| 13 | scheduling_booking | 25 | — | — | 2 | 10 | Self-serve scheduling ends the booking back-and-forth immediately. |
| 14 | scheduling_booking | 60 | moderate | — | 12 | 20 | Your booking friction is severe enough for a full platform with payments and reminders. |
| 15 | billing_invoicing | 25 | — | — | 3 | 10 | Automated invoicing and payment links stop the chasing. |
| 16 | billing_invoicing | 50 | — | — | 9 | 20 | A proper accounting suite gives you clean books and cash visibility. |
| 17 | billing_invoicing | 75 | substantial | — | 18 | 30 | A client portal lets customers pay and self-serve without touching your inbox. |
| 18 | marketing_leads | 25 | — | — | 5 | 10 | Structured intake forms route every lead instead of losing them. |
| 19 | marketing_leads | 50 | — | — | 7 | 20 | A real CRM pipeline makes sure no lead slips through the cracks. |
| 20 | marketing_leads | 75 | — | medium | 16 | 30 | An AI assistant can qualify and follow up with every lead automatically. |
| 21 | team_coordination | 25 | — | — | 10 | 10 | Shared task boards get coordination out of chat threads. |
| 22 | team_coordination | 50 | — | — | 13 | 20 | Documented SOPs stop the business depending on tribal knowledge. |
| 23 | team_coordination | 75 | substantial | — | 15 | 30 | Your coordination overhead justifies purpose-built software. |

### Demo Engagement (the sales-ready fixture; fixed tokens are SEED-ONLY)

Engagement row (direct SQL): `business_name='Sunset Yoga Studio'`,
`contact_name='Maya Torres'`, `contact_email='maya@sunsetyoga.example'`,
`industry='Fitness & Wellness'`, `notes='Referral from chamber mixer'`,
`status='published'`, `interview_token='demo-interview-token-0001'`,
`report_token='demo-report-token-0001'`.

Demo answers (by qkey; multi values comma-separated; free-text verbatim):

| qkey | answer |
|------|--------|
| goal_primary | save_time |
| goal_blocker | "We spend our evenings answering booking texts and chasing class payments." |
| growth_stage | steady |
| manual_hours | h10_20 |
| repetitive_tasks | data_entry, scheduling_back_forth, chasing_payments |
| process_docs | partially |
| ops_pain_story | "Last month we double-booked two private sessions and had to refund one." |
| tool_count | t3_5 |
| tool_integration | none |
| spreadsheet_reliance | constantly |
| source_of_truth | no |
| tools_list | "Google Sheets, Instagram DMs, Venmo, paper waivers, Mailchimp" |
| bottleneck_area | operations |
| missed_opportunities | occasionally |
| reporting_time | days_or_never |
| double_entry | yes |
| bottleneck_story | "A new client gave up after three days of back-and-forth trying to book an intro class." |
| response_time | same_day |
| booking_method | email_phone |
| booking_hours | many |
| payment_collection | cash_checks |
| followup_system | manual_followup |
| budget_tier | moderate |
| team_size | small |
| tech_maturity | medium |
| timeline | quarter |

After inserting the answers, seeds call `compute_diagnosis(conn, demo_id)` then
`generate_prescription(conn, demo_id)` (through the owner modules — the engine seeds its
own tables).

**Pinned expected demo diagnosis (the oracle — tests assert these EXACT values):**

| pain_category | raw | max | severity_pct | band |
|---------------|-----|-----|--------------|------|
| scheduling_booking | 16 | 16 | 100 | critical |
| manual_processes | 31 | 37 | 83 | critical |
| no_visibility | 18 | 25 | 72 | high |
| billing_invoicing | 12 | 17 | 70 | high |
| disconnected_tools | 18 | 28 | 64 | high |
| marketing_leads | 8 | 30 | 26 | moderate |
| customer_communication | 5 | 21 | 23 | low |
| team_coordination | 2 | 17 | 11 | low |

`reported` = top 5: scheduling_booking, manual_processes, no_visibility,
billing_invoicing, disconnected_tools (marketing_leads at 26 is 6th — excluded by cap).

**Pinned expected demo prescription (7 items, insertion order; budget=moderate, maturity=medium):**

| sort_order | solution (skey) | tier | triggering category | from rule |
|------------|-----------------|------|---------------------|-----------|
| 1 | scheduling_tool | quick_win | scheduling_booking | 13 |
| 2 | booking_platform | core | scheduling_booking | 14 |
| 3 | automation_glue | quick_win | manual_processes | 1 |
| 4 | dashboard_reporting | core | no_visibility | 7 |
| 5 | ops_hub | core | no_visibility | 8 |
| 6 | payment_automation | quick_win | billing_invoicing | 15 |
| 7 | accounting_suite | core | billing_invoicing | 16 |

(disconnected_tools rules 4 and 5 fire but their solutions are already prescribed —
dropped by INSERT OR IGNORE. Rules 2, 3, 6, 9, and 17 fail their budget/maturity/
severity filters. Tiers: 3 Quick Wins, 4 Core, 0 Growth.)

---

## Export Names Table

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `get_db` | function | app/database.py | ALL agents | |
| `init_db` | function | app/database.py | app factory (via init_app) | |
| `init_app` | function | app/database.py | app factory | |
| `seed_all` | function | app/seeds.py | app/database.py (init_db) | |
| `login_required` | decorator | auth routes | engagements, diagnosis, prescription, catalog, questions, reports route agents | |
| `create_consultant` | model fn | auth_models | seeds | |
| `authenticate` | model fn | auth_models | auth routes | |
| `get_consultant` | model fn | auth_models | auth routes (decorator) | |
| `create_engagement` | model fn | engagement_models | engagements routes | |
| `list_engagements` | model fn | engagement_models | engagements routes | |
| `get_engagement` | model fn | engagement_models | engagements, diagnosis, prescription, reports routes | |
| `get_engagement_by_token` | model fn | engagement_models | interview routes | |
| `get_engagement_by_report_token` | model fn | engagement_models | reports routes | |
| `update_engagement` | model fn | engagement_models | engagements routes | |
| `transition_engagement_status` | model fn | engagement_models | interview routes | |
| `publish_report` | model fn | engagement_models | prescription routes | |
| `delete_engagement` | model fn | engagement_models | engagements routes | |
| `get_active_questions` | model fn | question_models | questions routes | |
| `get_all_questions` | model fn | question_models | questions routes | |
| `get_question` | model fn | question_models | questions routes | |
| `get_options` | model fn | question_models | questions routes | |
| `get_option_scores` | model fn | question_models | questions routes | |
| `update_question` | model fn | question_models | questions routes | |
| `get_next_question` | model fn | interview_models | interview routes | |
| `save_answer` | model fn | interview_models | interview routes | |
| `get_answers` | model fn | interview_models | reports routes | |
| `get_progress` | model fn | interview_models | interview routes, engagements routes | |
| `get_constraint_profile` | model fn | interview_models | prescription_models, reports routes | |
| `compute_diagnosis` | model fn | diagnosis_models | interview routes, diagnosis routes, seeds | |
| `get_diagnosis` | model fn | diagnosis_models | prescription_models, diagnosis routes, reports routes | |
| `band_for` | model fn | diagnosis_models | diagnosis routes (templates receive band pre-computed) | |
| `PAIN_CATEGORIES` | constant | diagnosis_models | prescription_models, questions routes | |
| `generate_prescription` | model fn | prescription_models | interview routes, diagnosis routes, seeds | |
| `get_prescription` | model fn | prescription_models | prescription routes, reports routes | |
| `override_item` | model fn | prescription_models | prescription routes | |
| `remove_item` | model fn | prescription_models | prescription routes | |
| `add_item` | model fn | prescription_models | prescription routes | |
| `get_active_rules` | model fn | rule_models | prescription_models | |
| `list_solutions` | model fn | solution_models | catalog routes, prescription routes (add-item dropdown) | |
| `get_solution` | model fn | solution_models | catalog routes, prescription routes | |
| `create_solution` | model fn | solution_models | catalog routes | |
| `update_solution` | model fn | solution_models | catalog routes | |
| `archive_solution` | model fn | solution_models | catalog routes | |
| `auth.login` | endpoint | auth routes | base.html, decorator redirect, index redirect | |
| `auth.logout` | endpoint | auth routes | base.html navbar | |
| `engagements.index` | endpoint | engagements routes | base.html navbar, index redirect, post-login redirect | |
| `engagements.new` | endpoint | engagements routes | engagements/list.html | |
| `engagements.detail` | endpoint | engagements routes | list/new/edit redirects, diagnosis + prescription back-links | |
| `interview.welcome` | endpoint | interview routes | engagements/detail.html (copyable link via `_external=True`) | |
| `interview.question` | endpoint | interview routes | interview welcome/answer redirects | |
| `interview.done` | endpoint | interview routes | interview answer/question redirects | |
| `diagnosis.detail` | endpoint | diagnosis routes | engagements/detail.html, recompute redirect | |
| `prescription.detail` | endpoint | prescription routes | engagements/detail.html, diagnosis/detail.html, item-action redirects | |
| `reports.engagement_report` | endpoint | reports routes | engagements/detail.html, prescription/detail.html | |
| `reports.public_report` | endpoint | reports routes | prescription/detail.html (copyable link after publish, `_external=True`) | |
| `catalog.index` | endpoint | catalog routes | base.html navbar | |
| `questions.index` | endpoint | questions routes | base.html navbar | |
| `auth` | blueprint | auth routes | app/__init__.py | |
| `engagements` | blueprint | engagements routes | app/__init__.py | |
| `interview` | blueprint | interview routes | app/__init__.py | |
| `diagnosis` | blueprint | diagnosis routes | app/__init__.py | |
| `prescription` | blueprint | prescription routes | app/__init__.py | |
| `catalog` | blueprint | catalog routes | app/__init__.py | |
| `questions` | blueprint | questions routes | app/__init__.py | |
| `reports` | blueprint | reports routes | app/__init__.py | |
| `GET /` | route path | app/__init__.py | smoke tests, login redirects | |
| `GET /auth/login` | route path | auth routes | smoke tests, login_required redirect | |
| `POST /auth/login` | route path | auth routes | login.html form action | |
| `POST /auth/logout` | route path | auth routes | base.html logout form | |
| `GET /engagements/` | route path | engagements routes | navbar, index redirect, smoke tests | |
| `GET /engagements/new` | route path | engagements routes | list.html | |
| `POST /engagements/` | route path | engagements routes | new.html form action | |
| `GET /engagements/<int:engagement_id>` | route path | engagements routes | list.html, redirects | |
| `GET /engagements/<int:engagement_id>/edit` | route path | engagements routes | detail.html | |
| `POST /engagements/<int:engagement_id>/edit` | route path | engagements routes | edit.html form action | |
| `POST /engagements/<int:engagement_id>/delete` | route path | engagements routes | detail.html delete form | |
| `GET /i/<token>` | route path | interview routes | engagements/detail.html copyable link | |
| `GET /i/<token>/q` | route path | interview routes | welcome.html, answer redirect | |
| `POST /i/<token>/answer` | route path | interview routes | question.html form action | |
| `GET /i/<token>/done` | route path | interview routes | answer/question redirects | |
| `GET /diagnosis/<int:engagement_id>` | route path | diagnosis routes | engagements/detail.html | |
| `POST /diagnosis/<int:engagement_id>/recompute` | route path | diagnosis routes | diagnosis/detail.html form | |
| `GET /prescription/<int:engagement_id>` | route path | prescription routes | engagements/detail.html, diagnosis/detail.html | |
| `POST /prescription/items/<int:item_id>/override` | route path | prescription routes | prescription/detail.html forms | |
| `POST /prescription/items/<int:item_id>/remove` | route path | prescription routes | prescription/detail.html forms | |
| `POST /prescription/<int:engagement_id>/items` | route path | prescription routes | prescription/detail.html add form | |
| `POST /prescription/<int:engagement_id>/publish` | route path | prescription routes | prescription/detail.html publish form | |
| `GET /catalog/` | route path | catalog routes | navbar, smoke tests | |
| `GET /catalog/new` | route path | catalog routes | catalog/list.html | |
| `POST /catalog/` | route path | catalog routes | new.html form action | |
| `GET /catalog/<int:solution_id>/edit` | route path | catalog routes | catalog/list.html | |
| `POST /catalog/<int:solution_id>/edit` | route path | catalog routes | edit.html form action | |
| `POST /catalog/<int:solution_id>/archive` | route path | catalog routes | edit.html archive form | |
| `GET /questions/` | route path | questions routes | navbar, smoke tests | |
| `GET /questions/<int:question_id>/edit` | route path | questions routes | questions/list.html | |
| `POST /questions/<int:question_id>/edit` | route path | questions routes | edit.html form action | |
| `GET /reports/<int:engagement_id>` | route path | reports routes | engagements/detail.html, prescription/detail.html | |
| `GET /r/<report_token>` | route path | reports routes | prescription/detail.html copyable link | |

### Orchestration Entrypoints (FC50 — cross-boundary calls pinned with full signatures)

Signatures are AUTHORITATIVE — producers and consumers must match
character-for-character. These are every route→non-model-owner call and
module→module call/constants import that crosses an agent boundary.

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `get_db` | orchestration entrypoint | app/database.py | ALL route agents (routes ONLY — model functions take `conn` and NEVER import get_db) | `get_db() -> sqlite3.Connection` (row_factory=Row; PRAGMAs set; NOT a context manager) |
| `login_required` | orchestration entrypoint | auth routes | engagements, diagnosis, prescription, catalog, questions, reports route agents | `login_required(f) -> Callable` (sets g.user; redirects to auth.login if no session) |
| `get_engagement_by_token` | orchestration entrypoint | engagement_models | interview routes | `get_engagement_by_token(conn, interview_token) -> dict \| None` (keys: id, business_name, contact_name, contact_email, industry, notes, status, interview_token, report_token, created_at, updated_at) |
| `get_engagement_by_report_token` | orchestration entrypoint | engagement_models | reports routes | `get_engagement_by_report_token(conn, report_token) -> dict \| None` (same keys; None unless status == 'published') |
| `get_engagement` | orchestration entrypoint | engagement_models | diagnosis routes, prescription routes, reports routes | `get_engagement(conn, engagement_id) -> dict \| None` (same keys) |
| `transition_engagement_status` | orchestration entrypoint | engagement_models | interview routes | `transition_engagement_status(conn, engagement_id, new_status) -> bool` (does NOT commit; validates VALID_ENGAGEMENT_TRANSITIONS; sets updated_at) |
| `publish_report` | orchestration entrypoint | engagement_models | prescription routes | `publish_report(conn, engagement_id) -> str \| None` (commits internally BEGIN IMMEDIATE; only from status 'completed'; returns report_token) |
| `compute_diagnosis` | orchestration entrypoint | diagnosis_models | interview routes, diagnosis routes, seeds | `compute_diagnosis(conn, engagement_id) -> int` (does NOT commit; deletes + recomputes; returns diagnosis_id) |
| `get_diagnosis` | orchestration entrypoint | diagnosis_models | prescription_models, reports routes, diagnosis routes | `get_diagnosis(conn, engagement_id) -> dict \| None` (keys: id, engagement_id, computed_at, scores: list[dict], reported: list[dict]; score dict keys: pain_category, label, raw_points, max_points, severity_pct, band) |
| `PAIN_CATEGORIES` | orchestration entrypoint | diagnosis_models | prescription_models (category_label), questions routes (score display labels) | `PAIN_CATEGORIES: dict[str, str]` (8 keys, insertion-ordered; constants import) |
| `generate_prescription` | orchestration entrypoint | prescription_models | interview routes, diagnosis routes, seeds | `generate_prescription(conn, engagement_id) -> int` (does NOT commit; deletes + regenerates; returns prescription_id) |
| `get_prescription` | orchestration entrypoint | prescription_models | reports routes | `get_prescription(conn, engagement_id) -> dict \| None` (keys: id, engagement_id, created_at, items: list[dict], tiers: dict[str, list[dict]]; item dict keys: id, solution_id, skey, name, tier, description, cost_band, url, pain_category, category_label, rationale, sort_order, is_overridden, is_manual) |
| `get_constraint_profile` | orchestration entrypoint | interview_models | prescription_models, reports routes | `get_constraint_profile(conn, engagement_id) -> dict` (keys: budget_tier, team_size, tech_maturity, timeline; values: option value str or None) |
| `get_answers` | orchestration entrypoint | interview_models | reports routes | `get_answers(conn, engagement_id) -> list[dict]` (keys: question_id, qkey, section, prompt, qtype, sort_order, option_value, option_label, value_text; ordered question sort_order ASC, option sort_order ASC) |
| `get_progress` | orchestration entrypoint | interview_models | engagements routes | `get_progress(conn, engagement_id) -> dict` (keys: answered, total — both int) |
| `get_solution` | orchestration entrypoint | solution_models | prescription routes (add-item validation) | `get_solution(conn, solution_id) -> dict \| None` (keys: id, skey, name, tier, description, cost_band, url, is_archived, created_at) |
| `list_solutions` | orchestration entrypoint | solution_models | prescription routes (add-item dropdown) | `list_solutions(conn, include_archived=False) -> list[dict]` (same keys; ordered TIER_ORDER then name ASC) |
| `create_consultant` | orchestration entrypoint | auth_models | seeds | `create_consultant(conn, username, password) -> int` (does NOT commit; werkzeug generate_password_hash) |
| `TIER_ORDER` / `TIER_LABELS` | orchestration entrypoint | prescription_models | reports routes (tier grouping/headings on the report) | `TIER_ORDER: tuple[str, str, str] = ('quick_win', 'core', 'growth')`; `TIER_LABELS: dict[str, str]` ('Quick Wins', 'Core Stack', 'Growth') — constants import |

---

## Cross-Boundary Wiring Table

### Completion Chain (HIGHEST RISK — interview routes drive 3 modules in one transaction)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/engagement_models.py | app/blueprints/interview/routes.py | `from app.models.engagement_models import get_engagement_by_token, transition_engagement_status` |
| app/models/diagnosis_models.py | app/blueprints/interview/routes.py | `from app.models.diagnosis_models import compute_diagnosis` |
| app/models/prescription_models.py | app/blueprints/interview/routes.py | `from app.models.prescription_models import generate_prescription` |

### Prescription Engine Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/diagnosis_models.py | app/models/prescription_models.py | `from app.models.diagnosis_models import get_diagnosis, PAIN_CATEGORIES` |
| app/models/interview_models.py | app/models/prescription_models.py | `from app.models.interview_models import get_constraint_profile` |
| app/models/rule_models.py | app/models/prescription_models.py | `from app.models.rule_models import get_active_rules` |

### Report Assembly Wiring (4 cross-module reads)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/engagement_models.py | app/blueprints/reports/routes.py | `from app.models.engagement_models import get_engagement, get_engagement_by_report_token` |
| app/models/diagnosis_models.py | app/blueprints/reports/routes.py | `from app.models.diagnosis_models import get_diagnosis` |
| app/models/prescription_models.py | app/blueprints/reports/routes.py | `from app.models.prescription_models import get_prescription, TIER_ORDER, TIER_LABELS` |
| app/models/interview_models.py | app/blueprints/reports/routes.py | `from app.models.interview_models import get_answers, get_constraint_profile` |

### Diagnosis/Prescription Routes Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/engagement_models.py | app/blueprints/diagnosis/routes.py | `from app.models.engagement_models import get_engagement` |
| app/models/prescription_models.py | app/blueprints/diagnosis/routes.py | `from app.models.prescription_models import generate_prescription` (recompute regenerates both) |
| app/models/engagement_models.py | app/blueprints/prescription/routes.py | `from app.models.engagement_models import get_engagement, publish_report` |
| app/models/solution_models.py | app/blueprints/prescription/routes.py | `from app.models.solution_models import get_solution, list_solutions` |

### Engagement Detail Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/interview_models.py | app/blueprints/engagements/routes.py | `from app.models.interview_models import get_progress` |

### Questions Admin Wiring

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/diagnosis_models.py | app/blueprints/questions/routes.py | `from app.models.diagnosis_models import PAIN_CATEGORIES` |

### Seeds Wiring (init-time)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/models/auth_models.py | app/seeds.py | `from app.models.auth_models import create_consultant` |
| app/models/diagnosis_models.py | app/seeds.py | `from app.models.diagnosis_models import compute_diagnosis` |
| app/models/prescription_models.py | app/seeds.py | `from app.models.prescription_models import generate_prescription` |
| app/seeds.py | app/database.py | `from app.seeds import seed_all` (called inside init_db) |

### Auth Decorator Wiring (admin route agents consume)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/blueprints/auth/routes.py | engagements, diagnosis, prescription, catalog, questions, reports route agents | `from app.blueprints.auth.routes import login_required` |

### Database Wiring (route agents consume)

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/database.py | ALL route agents (routes ONLY — model functions take `conn` as their first argument and NEVER import get_db) | `from app.database import get_db` |

---

## Input Validation Prescriptions

Every POST route and every typed URL/path param. "Flash" = `flash('msg', 'error')` +
redirect back to the originating form/page.

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| POST /auth/login | username, password | required, strip | Flash "Invalid credentials", redirect to login (same message for unknown user vs wrong password) |
| POST /auth/logout | — | login_required | redirect to login |
| POST /engagements/ | business_name; contact_name, contact_email, industry, notes optional | business_name required strip 1–200; contact_name ≤120; contact_email ≤254 and must contain '@' if non-empty; industry ≤120; notes ≤2000 | Flash specific error, redirect to /engagements/new |
| POST /engagements/\<id\>/edit | same fields | same rules; engagement must exist | Flash specific / 404 |
| POST /engagements/\<id\>/delete | — | engagement must exist | 404 |
| GET /i/\<token\>, /q, /done | token (path) | `get_engagement_by_token` exact match | 404 if unknown |
| POST /i/\<token\>/answer | question_id; option_value (single/multi via getlist) or value_text | token resolves else 404; status in ('created','in_progress') else redirect to done with NO write; question_id must be int (else flash) and EQUAL the current `get_next_question` id (no skipping — else flash "Unexpected question" + redirect to /q); single_choice: exactly 1 value, must be in question's option values; multi_choice: ≥1 distinct valid values; free_text: value_text stripped non-empty, ≤2000 | Flash specific, redirect to /i/\<token\>/q |
| GET /r/\<report_token\> | token (path) | `get_engagement_by_report_token` (published only) | 404 if unknown or not published |
| GET /diagnosis/\<id\>, /prescription/\<id\>, /reports/\<id\> | engagement_id (int path) | engagement must exist | 404 |
| GET /engagements/\<id\>, /engagements/\<id\>/edit | engagement_id (int path) | engagement must exist | 404 |
| GET /catalog/\<sid\>/edit | solution_id (int path) | solution must exist | 404 |
| GET /questions/\<qid\>/edit | question_id (int path) | question must exist | 404 |
| POST /diagnosis/\<id\>/recompute | — | engagement exists else 404; status in ('completed','published') | Flash "Interview not completed yet", redirect to diagnosis.detail |
| POST /prescription/\<id\>/publish | — | engagement exists else 404; status == 'completed' (publish_report re-checks in lock) | Flash "Interview not completed yet" or "Report already published", redirect to prescription.detail |
| POST /prescription/items/\<iid\>/override | rationale | item must exist else 404; rationale required strip 1–1000 | Flash "Rationale is required", redirect to prescription.detail |
| POST /prescription/items/\<iid\>/remove | — | item must exist | 404 |
| POST /prescription/\<id\>/items | solution_id, rationale | engagement + prescription must exist else 404; solution_id int (try/except) and exists and not archived; rationale required 1–1000; duplicate solution → add_item returns None | Flash "Invalid solution" / "Rationale is required" / "Already prescribed", redirect to prescription.detail |
| POST /catalog/ | skey, name, tier, cost_band, description, url | skey matches `^[a-z0-9_]{1,50}$` and unique (create_solution returns None on dup); name 1–120; tier in TIER_ORDER; cost_band in ('low','medium','high'); description 1–2000; url ≤300 optional | Flash specific, redirect to /catalog/new |
| POST /catalog/\<sid\>/edit | name, tier, cost_band, description, url | solution exists else 404; same field rules (skey immutable, not in form) | Flash specific, redirect to edit |
| POST /catalog/\<sid\>/archive | — | solution exists | 404 |
| POST /questions/\<qid\>/edit | prompt, is_active | question exists else 404; prompt required strip 1–500; is_active checkbox → 0/1 | Flash "Prompt is required", redirect to edit |

**Form field name conventions (templates use these exact names):** `username`,
`password`, `business_name`, `contact_name`, `contact_email`, `industry`, `notes`,
`question_id`, `option_value` (single select/radio AND multi checkboxes — multi read via
`request.form.getlist('option_value')`), `value_text`, `rationale`, `solution_id`,
`skey`, `name`, `tier`, `cost_band`, `description`, `url`, `prompt`, `is_active`.

---

## Coordinated Behaviors

| Surface | Rule | Owner |
|---------|------|-------|
| Blueprint registration | All 8 blueprints registered in `create_app()` with exact prefixes from Route Table (reports with NO prefix) | scaffold agent |
| CSRF token syntax | All POST forms (INCLUDING public interview forms): `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` (WITH parentheses) | ALL route agents |
| Admin base template | Admin templates extend `base.html` (`{% block title %}`, `{% block content %}`); Bootstrap 5 dark navbar: Engagements, Catalog, Questions, Logout (POST form) | scaffold agent defines; engagements, diagnosis, prescription, catalog, questions, reports fill |
| Client base template | interview/welcome, question, done AND reports/public_report extend `interview/base_client.html` — standalone, NO navbar, no admin links, Bootstrap 5 + style.css only | interview agent defines; reports agent reuses |
| Session keys | `session['user_id']` (int) — consultant only. Clients get NO session identity keys | auth agent sets; login_required reads |
| Flash categories | `success` (green), `error` (red), `warning` (yellow), `info` (blue); pattern `flash('Message', 'category')`, no HTML in messages | ALL route agents |
| Severity bands | Derived ONLY via `band_for(severity_pct)`; never stored, never re-implemented | diagnosis agent defines; all consumers receive band in dicts |
| Severity band CSS | `.band-low` (gray), `.band-moderate` (yellow), `.band-high` (orange), `.band-critical` (red); severity bars: `<div class="severity-bar band-{{ score['band'] }}" style="width: {{ score['severity_pct'] }}%">` | scaffold agent (style.css); diagnosis + reports templates |
| Status badges | CSS classes `status-created` (gray), `status-in_progress` (blue), `status-published` (green), `status-completed` (teal) | scaffold agent (CSS); engagements templates |
| Tier display | Order quick_win → core → growth using `TIER_ORDER`; headings from `TIER_LABELS` ("Quick Wins", "Core Stack", "Growth"); skip empty tiers | prescription + reports templates |
| Cost band display | `{{ {'low': '$', 'medium': '$$', 'high': '$$$'}[item['cost_band']] }}` | prescription, catalog, reports templates |
| Client quotes on report | free_text answers rendered as blockquotes ("In their own words"), grouped under their section, auto-escaped by Jinja (no `\|safe`) | reports agent |
| Interview progress | `get_progress` → "Question {{ answered + 1 }} of {{ total }}" + Bootstrap progress bar. question.html renders ONLY when get_next_question is non-None (the route redirects to done first), so answered + 1 <= total always | interview agent |
| Recompute warning | Recompute button copy pinned: "Recompute — this regenerates the diagnosis and prescription and removes your overrides." | diagnosis agent (button lives on diagnosis/detail.html) |
| Demo tokens | `demo-interview-token-0001` / `demo-report-token-0001` are seed-only; runtime tokens ALWAYS `secrets.token_urlsafe(32)` | database (seeds), engagement_models |
| Timestamps | All timestamps use SQL `datetime('now')`, NEVER Python `datetime.now()` | ALL model agents |
| Empty states | "No [items] yet." + create link on list pages; diagnosis, prescription, AND report pages (GET /reports/\<id\> included) show "Interview not completed yet" (200, not 404) when the engagement exists but diagnosis/prescription don't — `_report_body.html` must handle `diagnosis is None` / `prescription is None` without erroring; zero-item prescription/report shows pinned copy "No critical pain detected — talk to us about a tune-up." | ALL template agents |
| Error 404 | `abort(404)` after failed DB lookups (unknown ids/tokens), before any writes | ALL route agents |
| Print stylesheet | `static/css/print.css` loaded by report.html + public_report.html via `media="print"`; hides buttons/nav, white background | reports agent |
| Report CTA | `_report_body.html` ends with a pinned "Next Steps" block; copy: heading "Next Steps", body "Ready to fix this? Reply to the consultant who shared this report to scope your first Quick Win." Contact line appended from optional `CONSULTANT_CONTACT` env (omitted when unset) — no consultant data is stored in the DB | reports agent |

---

## Transaction Contracts

Data Ownership (one writer per table) is recorded in the **Data Ownership** section
above and is incorporated into this mandatory section by reference.

| Function | Transaction | Commits? | Error Handling |
|----------|-------------|----------|----------------|
| `create_consultant` | none | NO | seeds-only; init_db commits once |
| `create_engagement` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `update_engagement` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `transition_engagement_status` | none | NO | caller wraps; returns False on invalid transition (no write) |
| `publish_report` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK; re-checks status == 'completed' inside lock; returns None if invalid |
| `delete_engagement` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK (FK cascades) |
| `save_answer` | none | NO | caller wraps (answer route compound block) |
| `compute_diagnosis` | none | NO | caller wraps (compound blocks 1–2, seeds) |
| `generate_prescription` | none | NO | caller wraps (compound blocks 1–2, seeds) |
| `override_item` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `remove_item` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `add_item` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK; INSERT OR IGNORE → returns None on duplicate |
| `update_question` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `create_solution` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK; returns None on duplicate skey (catch sqlite3.IntegrityError specifically) |
| `update_solution` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `archive_solution` | BEGIN IMMEDIATE | YES | try/except/ROLLBACK |
| `seed_all` | none (init_db wraps) | NO | init_db commits once after schema + seeds |

**Compound write block 1 — answer submission AND completion (interview routes, exact —
ONE transaction; the final answer, status transition, diagnosis, and prescription are
atomic, satisfying the EARS criterion "in one transaction"):**
```python
# POST /i/<token>/answer -- after validation passes
completed = False
conn.execute('BEGIN IMMEDIATE')
try:
    save_answer(conn, engagement['id'], question_id, option_values, value_text)
    if engagement['status'] == 'created':
        transition_engagement_status(conn, engagement['id'], 'in_progress')
    # Uncommitted reads on the SAME connection see the new answer + status, so this
    # check and the completion chain run inside the same transaction.
    if get_next_question(conn, engagement['id']) is None:
        transition_engagement_status(conn, engagement['id'], 'completed')
        compute_diagnosis(conn, engagement['id'])
        generate_prescription(conn, engagement['id'])
        completed = True
    conn.execute('COMMIT')
except Exception:
    conn.execute('ROLLBACK')
    raise
return redirect(url_for('interview.done', token=token) if completed
                else url_for('interview.question', token=token))
```

**Compound write block 2 — recompute (diagnosis routes):**
```python
# POST /diagnosis/<engagement_id>/recompute -- status verified in ('completed','published')
conn.execute('BEGIN IMMEDIATE')
try:
    compute_diagnosis(conn, engagement_id)
    generate_prescription(conn, engagement_id)   # wipes overrides + manual items by design
    conn.execute('COMMIT')
except Exception:
    conn.execute('ROLLBACK')
    raise
```

---

## Authorization Matrix

Modes: `public` (no gate), `public-token` (unguessable token lookup is the gate),
`admin-only` (`login_required`; there is exactly one role). No role/ownership matrix is
needed beyond this — single consultant, no client accounts.

| Route | Mode | Gate |
|-------|------|------|
| GET /auth/login | public | — |
| POST /auth/login | public | CSRF + constant-time authenticate |
| POST /auth/logout | admin-only | login_required |
| GET / | public | redirects only (login or engagements.index) |
| GET /engagements/ | admin-only | login_required |
| GET /engagements/new | admin-only | login_required |
| POST /engagements/ | admin-only | login_required |
| GET /engagements/\<id\> | admin-only | login_required + 404 unknown id |
| GET /engagements/\<id\>/edit | admin-only | login_required + 404 |
| POST /engagements/\<id\>/edit | admin-only | login_required + 404 |
| POST /engagements/\<id\>/delete | admin-only | login_required + 404 |
| GET /i/\<token\> | public-token | get_engagement_by_token else 404 |
| GET /i/\<token\>/q | public-token | get_engagement_by_token else 404 |
| POST /i/\<token\>/answer | public-token | get_engagement_by_token else 404; CSRF; status guard (no writes once completed) |
| GET /i/\<token\>/done | public-token | get_engagement_by_token else 404 |
| GET /diagnosis/\<id\> | admin-only | login_required + 404 |
| POST /diagnosis/\<id\>/recompute | admin-only | login_required + 404 + status guard |
| GET /prescription/\<id\> | admin-only | login_required + 404 |
| POST /prescription/items/\<iid\>/override | admin-only | login_required + 404 |
| POST /prescription/items/\<iid\>/remove | admin-only | login_required + 404 |
| POST /prescription/\<id\>/items | admin-only | login_required + 404 |
| POST /prescription/\<id\>/publish | admin-only | login_required + 404 + status guard |
| GET /catalog/ | admin-only | login_required |
| GET /catalog/new | admin-only | login_required |
| POST /catalog/ | admin-only | login_required |
| GET /catalog/\<sid\>/edit | admin-only | login_required + 404 |
| POST /catalog/\<sid\>/edit | admin-only | login_required + 404 |
| POST /catalog/\<sid\>/archive | admin-only | login_required + 404 |
| GET /questions/ | admin-only | login_required |
| GET /questions/\<qid\>/edit | admin-only | login_required + 404 |
| POST /questions/\<qid\>/edit | admin-only | login_required + 404 |
| GET /reports/\<id\> | admin-only | login_required + 404 |
| GET /r/\<report_token\> | public-token | get_engagement_by_report_token (None unless published) else 404 |

**Token-scoping invariants (the IDOR surface here):**
- Interview pages must render ZERO consultant data and ZERO data from any other
  engagement — only this engagement's questions/answers/progress.
- The public report must never render `interview_token`, consultant notes, or any
  admin link. It renders: business_name, diagnosis, prescription, quotes, constraint
  profile, and the consultant's contact CTA.
- Unknown token → 404 (never 403 — no information leak about token validity).

---

## Negative Constraints (Do NOT Rules)

1. Do NOT call any LLM or external API — the engine is rule-based and offline by design.
2. Do NOT store severity bands, constraint profiles, or any derived value — bands via
   `band_for()`, profiles via `get_constraint_profile()`, always at read time.
3. Do NOT use Python `datetime.now()` — use SQL `datetime('now')` for all timestamps.
4. Do NOT set `conn.row_factory` in model functions — `get_db()` sets it once.
5. Do NOT commit inside model functions unless the Transaction Contracts table says so —
   `save_answer`, `compute_diagnosis`, `generate_prescription`,
   `transition_engagement_status`, `create_consultant` NEVER commit.
6. Do NOT use `with get_db() as conn:` — `get_db()` is NOT a context manager.
7. Do NOT use `executescript()` outside `init_db()`.
8. Do NOT hardcode credentials — `SECRET_KEY` and `ADMIN_PASSWORD` come from env,
   fail-closed.
9. Do NOT use bare `except Exception` when catching `IntegrityError` — catch
   `sqlite3.IntegrityError` specifically.
10. Do NOT use `{{ csrf_token }}` (no parens) — always `{{ csrf_token() }}`.
11. Do NOT duplicate the blueprint url_prefix inside route paths — paths are RELATIVE
    to the prefix (reports blueprint is the exception: it has NO prefix and uses
    absolute paths).
12. Do NOT re-implement the reported-categories filter or band thresholds anywhere —
    single sources: `get_diagnosis(...)['reported']` and `band_for()`.
13. Do NOT round severity with `round()` — integer floor division only.
14. Do NOT use `random` for tokens — `secrets.token_urlsafe(32)` only (seed fixtures are
    the sole fixed-token exception).
15. Do NOT render free-text client answers with `| safe` or `Markup()` — rely on Jinja
    auto-escaping.
16. Do NOT expose `interview_token` or any admin URL on the public report page.
17. Do NOT add client accounts, sessions, or cookies carrying client identity — token
    in URL path is the only client credential.
18. Do NOT create database triggers — all writes are explicit function calls.
19. Do NOT issue any INSERT/UPDATE/DELETE outside either (a) a commits-internally model
    function or (b) an explicit `BEGIN IMMEDIATE` block — under sqlite3's default
    legacy autocommit, a stray pre-BEGIN write opens an implicit transaction and the
    next explicit `BEGIN IMMEDIATE` raises "cannot start a transaction within a
    transaction". (Seeds are the exception: init_db runs them in the implicit
    transaction and commits once — seeds must therefore contain NO explicit BEGIN.)

---

## Critical-Flow Tests

The tests agent MUST implement all 12 test cases in `tests/test_critical_flows.py`
(pytest; fixtures in `tests/conftest.py` build a fresh app per test backed by a fresh
temp-file DB — NEVER `:memory:`, which is private per connection. MECHANISM (pinned —
the env var is read once at module import, so setting `os.environ` later is a no-op):
each test monkeypatches the module global, `monkeypatch.setattr(app.database,
'DATABASE', tmp_path / 'test.db' as str)`, BEFORE calling `create_app()`; `get_db`
reads the global at call time so every connection hits the per-test file. `SECRET_KEY`
and `ADMIN_PASSWORD` set; CSRF disabled via `WTF_CSRF_ENABLED=False` except test 11
which enables it; temp files removed on teardown):

```python
# Test 1: Full interview end-to-end
# Create engagement via model fn -> walk GET /i/<token>/q + POST answer for every
# question (booking_method=email_phone so the dependent question appears) -> after final
# answer verify status == 'completed' AND diagnosis exists AND prescription exists.

# Test 2: Branching both ways
# Engagement A answers booking_method=online_self_serve -> booking_hours NEVER returned
# by get_next_question. Engagement B answers email_phone -> booking_hours IS returned.

# Test 3: Demo scoring oracle
# get_diagnosis(conn, demo_engagement_id) reproduces the pinned table EXACTLY:
# SB 16/16/100, MP 31/37/83, NV 18/25/72, BI 12/17/70, DT 18/28/64, ML 8/30/26,
# CC 5/21/23, TC 2/17/11; reported == [SB, MP, NV, BI, DT].

# Test 4: Band boundaries
# band_for(0)=='low', band_for(24)=='low', band_for(25)=='moderate', band_for(49)=='moderate',
# band_for(50)=='high', band_for(74)=='high', band_for(75)=='critical', band_for(100)=='critical'.

# Test 5: Constraint filter
# Clone demo answers but budget_tier=substantial -> custom_integration (rule 2) appears;
# with budget_tier=moderate (demo) it does not.

# Test 6: Dedup first-wins
# Demo prescription contains ops_hub exactly once, attributed to no_visibility (rule 8),
# even though disconnected_tools rule 5 also matched.

# Test 7: Recompute wipes overrides
# Override an item rationale + add a manual item on demo -> POST recompute -> prescription
# matches the pinned 7-item table again (no manual item, no override flags).

# Test 8: Token security
# GET /i/bogus -> 404. Create engagement, complete interview but do NOT publish ->
# GET /r/<its report_token... none exists> and GET /r/bogus -> 404. Demo (published)
# GET /r/demo-report-token-0001 -> 200.

# Test 9: Auth gate
# Anonymous GET /engagements/, /diagnosis/1, /prescription/1, /reports/1, /catalog/,
# /questions/ -> all 302 to /auth/login (trailing-slash URLs exactly as listed, so no
# Werkzeug 308 intervenes).

# Test 10: Empty prescription path -- uses the PINNED minimal-pain answer set:
# goal_primary=save_time, growth_stage=steady, manual_hours=under_2,
# repetitive_tasks=[none], process_docs=documented, tool_count=t0_2,
# tool_integration=mostly, spreadsheet_reliance=rarely, source_of_truth=yes,
# bottleneck_area=sales_pipeline, missed_opportunities=never, reporting_time=instant,
# double_entry=no, response_time=under_hour, booking_method=online_self_serve
# (dependent question never shown), payment_collection=automated,
# followup_system=automated_followup, constraints minimal/solo/low/flexible, any
# non-empty free texts. (q10 and q130 have NO zero-score option by design -- this set
# yields MP 5/37=13, ML 5/30=16, all other categories 0; every severity < 25.)
# -> prescription has 0 items -> GET /prescription/<id> and /reports/<id> render 200
# with the pinned empty-state copy.

# Test 11: CSRF enforced on public interview
# With WTF_CSRF_ENABLED=True, POST /i/<token>/answer without csrf_token -> 400.

# Test 12: Answer validation
# POST answer with question_id != current next question -> flash + redirect, no row
# written. POST multi_choice with no option_value values -> flash + redirect, no row.
```

---

## Route Smoke Table (FC8 — test_smoke.py asserts EXACTLY these)

`test_smoke.py` (tests agent) sets `DATABASE` to a fresh temp file
(`tempfile.mkstemp(suffix='.db')` — NEVER `:memory:`, which is private per connection
and incompatible with the per-request connection model), plus `SECRET_KEY` and
`ADMIN_PASSWORD=test-strong-pw-123`, all BEFORE importing `create_app`; extracts the
real CSRF token from the login form, logs in as the seeded consultant, then asserts
(trailing slashes are exact — see the trailing-slash convention):

| # | Method | Route | Expected |
|---|--------|-------|----------|
| 1 | GET | /auth/login | 200 |
| 2 | GET | / (anonymous) | 302 |
| 3 | GET | /engagements/ (anonymous) | 302 (to /auth/login) |
| 4 | POST | /auth/login (valid creds + CSRF) | 302 |
| 5 | GET | / (logged in) | 302 → /engagements/ |
| 6 | GET | /engagements/ | 200 |
| 7 | GET | /engagements/new | 200 |
| 8 | GET | /engagements/1 | 200 |
| 9 | GET | /engagements/1/edit | 200 |
| 10 | GET | /diagnosis/1 | 200 |
| 11 | GET | /prescription/1 | 200 |
| 12 | GET | /reports/1 | 200 |
| 13 | GET | /catalog/ | 200 |
| 14 | GET | /catalog/new | 200 |
| 15 | GET | /catalog/1/edit | 200 |
| 16 | GET | /questions/ | 200 |
| 17 | GET | /questions/1/edit | 200 |
| 18 | GET | /i/demo-interview-token-0001 | 200 |
| 19 | GET | /i/demo-interview-token-0001/q | 302 (interview complete → done) |
| 20 | GET | /i/demo-interview-token-0001/done | 200 |
| 21 | GET | /r/demo-report-token-0001 | 200 |
| 22 | GET | /i/bogus-token | 404 |
| 23 | GET | /r/bogus-token | 404 |
| 24 | GET | /engagements/9999 | 404 |
| 25 | GET | /auth/login — CSP header includes cdn.jsdelivr.net | header check |

Smoke file follows the house pattern: `check(name, condition, detail)` helper, PASS/FAIL
lines, exit(1) on any failure, run with `.venv/bin/python test_smoke.py`.

---

## File Assignment Boundaries

### Agent 1: scaffold
| File | Purpose |
|------|---------|
| app/__init__.py | App factory, blueprint registration, security headers, index route |
| app/blueprints/__init__.py | empty (package marker) |
| app/templates/base.html | Admin base: Bootstrap 5 dark, navbar (Engagements, Catalog, Questions, Logout), flash messages |
| app/static/css/style.css | Dark theme, severity band classes, status badges, severity bars |
| app/static/js/app.js | Shared JS (CSRF helper; minimal — no SPA behavior) |
| run.py | Entry point |
| requirements.txt | flask>=3.0, flask-wtf>=1.2 |
| .gitignore | Python standard + *.db |

### Agent 2: database
| File | Purpose |
|------|---------|
| schema.sql | All CREATE TABLE/INDEX statements |
| app/database.py | get_db, close_db, init_db, init_app |
| app/seeds.py | seed_all — consultant user, 26 questions + options + scores, 18 solutions, 23 rules, demo engagement + answers, demo compute calls |
| app/models/__init__.py | EMPTY — all imports use full module paths (no re-exports) |

### Agent 3: auth
| File | Purpose |
|------|---------|
| app/blueprints/auth/__init__.py | empty |
| app/blueprints/auth/routes.py | login, login_post, logout, login_required decorator |
| app/models/auth_models.py | create_consultant, authenticate, get_consultant |
| app/templates/auth/login.html | Login form |

### Agent 4: engagements
| File | Purpose |
|------|---------|
| app/blueprints/engagements/__init__.py | empty |
| app/blueprints/engagements/routes.py | index, new, create, detail, edit, update, delete |
| app/models/engagement_models.py | create/list/get x3 tokens/update/transition/publish_report/delete |
| app/templates/engagements/list.html | Engagement list with status badges |
| app/templates/engagements/new.html | New engagement form |
| app/templates/engagements/detail.html | Detail: status, copyable interview link, progress, links to diagnosis/prescription/report |
| app/templates/engagements/edit.html | Edit form |

### Agent 5: interview
| File | Purpose |
|------|---------|
| app/blueprints/interview/__init__.py | empty |
| app/blueprints/interview/routes.py | welcome, question, answer (compound block 1), done |
| app/models/interview_models.py | get_next_question, save_answer, get_answers, get_progress, get_constraint_profile, CONSTRAINT_QKEYS |
| app/templates/interview/base_client.html | Standalone client base (no navbar) WITH flash-message block — interview validation errors render through it |
| app/templates/interview/welcome.html | Branded welcome + begin button (or completed notice) |
| app/templates/interview/question.html | One question per page + progress bar |
| app/templates/interview/done.html | Thank-you page |

### Agent 6: questions
| File | Purpose |
|------|---------|
| app/blueprints/questions/__init__.py | empty |
| app/blueprints/questions/routes.py | index, edit, update |
| app/models/question_models.py | get_active_questions, get_all_questions, get_question, get_options, get_option_scores, update_question |
| app/templates/questions/list.html | Question bank by section with active toggles shown |
| app/templates/questions/edit.html | Edit prompt + is_active |

### Agent 7: diagnosis
| File | Purpose |
|------|---------|
| app/blueprints/diagnosis/__init__.py | empty |
| app/blueprints/diagnosis/routes.py | detail, recompute (compound block 2) |
| app/models/diagnosis_models.py | PAIN_CATEGORIES, band_for, compute_diagnosis, get_diagnosis |
| app/templates/diagnosis/detail.html | All 8 scores with severity bars + reported highlight + recompute button |

### Agent 8: prescription
| File | Purpose |
|------|---------|
| app/blueprints/prescription/__init__.py | empty |
| app/blueprints/prescription/routes.py | detail, override, remove, add, publish |
| app/models/prescription_models.py | generate_prescription, get_prescription, override_item, remove_item, add_item, orders/labels |
| app/models/rule_models.py | get_active_rules |
| app/templates/prescription/detail.html | Tiered items, override/remove/add forms, publish button + public link |

### Agent 9: catalog
| File | Purpose |
|------|---------|
| app/blueprints/catalog/__init__.py | empty |
| app/blueprints/catalog/routes.py | index, new, create, edit, update, archive |
| app/models/solution_models.py | list_solutions, get_solution, create_solution, update_solution, archive_solution |
| app/templates/catalog/list.html | Catalog grouped by tier |
| app/templates/catalog/new.html | New solution form |
| app/templates/catalog/edit.html | Edit form + archive |

### Agent 10: reports
| File | Purpose |
|------|---------|
| app/blueprints/reports/__init__.py | empty |
| app/blueprints/reports/routes.py | engagement_report, public_report |
| app/templates/reports/report.html | Consultant view (extends base.html, print button) |
| app/templates/reports/public_report.html | Public view (extends interview/base_client.html) |
| app/templates/reports/_report_body.html | Shared report body partial |
| app/static/css/print.css | Print stylesheet |

### Agent 11: tests
| File | Purpose |
|------|---------|
| test_smoke.py | FC8-compliant smoke tests per the Route Smoke Table |
| tests/__init__.py | empty |
| tests/conftest.py | app/client fixtures (fresh temp-file DB per test via monkeypatching app.database.DATABASE, seeded), login helper, CSRF toggle |
| tests/test_critical_flows.py | The 12 critical-flow tests |

---

## Swarm Agent Assignment

| # | Agent Name | Branch | Files (relative to project root) |
|---|-----------|--------|------|
| 1 | scaffold | swarm-071-scaffold | app/__init__.py, app/blueprints/__init__.py, app/templates/base.html, app/static/css/style.css, app/static/js/app.js, run.py, requirements.txt, .gitignore |
| 2 | database | swarm-071-database | schema.sql, app/database.py, app/seeds.py, app/models/__init__.py |
| 3 | auth | swarm-071-auth | app/blueprints/auth/__init__.py, app/blueprints/auth/routes.py, app/models/auth_models.py, app/templates/auth/login.html |
| 4 | engagements | swarm-071-engagements | app/blueprints/engagements/__init__.py, app/blueprints/engagements/routes.py, app/models/engagement_models.py, app/templates/engagements/list.html, app/templates/engagements/new.html, app/templates/engagements/detail.html, app/templates/engagements/edit.html |
| 5 | interview | swarm-071-interview | app/blueprints/interview/__init__.py, app/blueprints/interview/routes.py, app/models/interview_models.py, app/templates/interview/base_client.html, app/templates/interview/welcome.html, app/templates/interview/question.html, app/templates/interview/done.html |
| 6 | questions | swarm-071-questions | app/blueprints/questions/__init__.py, app/blueprints/questions/routes.py, app/models/question_models.py, app/templates/questions/list.html, app/templates/questions/edit.html |
| 7 | diagnosis | swarm-071-diagnosis | app/blueprints/diagnosis/__init__.py, app/blueprints/diagnosis/routes.py, app/models/diagnosis_models.py, app/templates/diagnosis/detail.html |
| 8 | prescription | swarm-071-prescription | app/blueprints/prescription/__init__.py, app/blueprints/prescription/routes.py, app/models/prescription_models.py, app/models/rule_models.py, app/templates/prescription/detail.html |
| 9 | catalog | swarm-071-catalog | app/blueprints/catalog/__init__.py, app/blueprints/catalog/routes.py, app/models/solution_models.py, app/templates/catalog/list.html, app/templates/catalog/new.html, app/templates/catalog/edit.html |
| 10 | reports | swarm-071-reports | app/blueprints/reports/__init__.py, app/blueprints/reports/routes.py, app/templates/reports/report.html, app/templates/reports/public_report.html, app/templates/reports/_report_body.html, app/static/css/print.css |
| 11 | tests | swarm-071-tests | test_smoke.py, tests/__init__.py, tests/conftest.py, tests/test_critical_flows.py |

No file appears in two agents' lists. Merge order: scaffold, database, auth, then 4–10 in
any order, tests last.

---

## Acceptance Tests (EARS Notation)

### Happy Path
- WHEN the consultant logs in with valid credentials THE SYSTEM SHALL redirect to the engagements list
- WHEN the consultant creates an engagement THE SYSTEM SHALL generate a unique `secrets.token_urlsafe(32)` interview token and display a copyable interview link
- WHEN a client opens a valid interview link THE SYSTEM SHALL show the branded welcome page without requiring any login
- WHEN a client submits the first answer THE SYSTEM SHALL transition the engagement to in_progress
- WHEN a client answers `booking_method` with `email_phone` THE SYSTEM SHALL subsequently present `booking_hours`
- WHEN a client submits the final visible question THE SYSTEM SHALL store the answer, transition to completed, and compute the diagnosis and prescription in one transaction
- WHEN the consultant views the demo diagnosis THE SYSTEM SHALL show severity_pct exactly 100/83/72/70/64/26/23/11 per the pinned oracle
- WHEN the consultant views the demo prescription THE SYSTEM SHALL show exactly the 7 pinned items grouped 3 Quick Wins / 4 Core / 0 Growth
- WHEN the consultant publishes a completed engagement THE SYSTEM SHALL generate a report token and make GET /r/\<token\> render the report
- WHEN the report renders THE SYSTEM SHALL quote the client's free-text answers verbatim (escaped) under "In their own words"

### Error Cases
- WHEN a request carries an unknown interview or report token THE SYSTEM SHALL return 404
- WHEN a /r/ lookup does not resolve to a PUBLISHED engagement THE SYSTEM SHALL return 404 (defensive — report tokens are minted only at publish time, so a live unpublished token is unreachable by construction; `get_engagement_by_report_token` enforces the status filter anyway)
- WHEN an anonymous user requests any admin route THE SYSTEM SHALL redirect (302) to /auth/login
- WHEN a client answers `booking_method` with `online_self_serve` THE SYSTEM SHALL never present `booking_hours`
- WHEN an answer POST carries a question_id that is not the current next question THE SYSTEM SHALL flash an error and write nothing
- WHEN a multi_choice answer arrives with zero selections THE SYSTEM SHALL flash an error and write nothing
- WHEN an answer POST arrives for a completed engagement THE SYSTEM SHALL redirect to the done page and write nothing
- WHEN any POST arrives without a CSRF token THE SYSTEM SHALL reject it (400)
- WHEN every category severity is below 25 THE SYSTEM SHALL produce a zero-item prescription and render the pinned empty-state copy without error
- WHEN recompute runs THE SYSTEM SHALL regenerate diagnosis and prescription deterministically and remove overrides and manual items

### Verification Commands
- `.venv/bin/python test_smoke.py` — all rows of the Route Smoke Table pass
- `.venv/bin/python -m pytest tests/ -v` — all 12 critical-flow tests pass

---

## Feed-Forward

- **Hardest decision:** Fixed-denominator scoring (`max_points` over ALL active questions regardless of branching visibility) vs. visible-only denominators. Fixed won: comparable severities across engagements and a denominator computable without per-engagement state — and it is semantically right (an invisible scheduling question means no scheduling pain).
- **Rejected alternatives:** LLM-driven interviewing (offline-demo reliability + declared-API contract); top-rule-only prescription matching (starves the tier narrative); storing bands/profiles (derived-value drift P1 class); per-engagement question snapshots (YAGNI for v1 — question edits are prompt/is_active only).
- **Least confident:** The seed-data web — 26 questions × option scores × 23 rules × 18 solutions × the hand-computed demo oracle (severities 100/83/72/70/64 and the 7-item prescription). One wrong points value breaks the pinned acceptance numbers. Reviewers and the tests agent must re-derive the oracle from the seed tables, not trust this spec's arithmetic.

---

## Sources

- **Authoritative brief:** docs/briefs/2026-06-11-stack-rx-brief.md (12-layer, same date)
- **Operating contract:** CLAUDE.md (sandbox) — 6 mandatory spec sections, autonomy classes, escalation rules
- **Structure exemplar:** docs/plans/film-production-pm-plan.md (Run 070 converged spec)
- **Lessons applied:** docs/solutions/2026-04-30-spec-convergence-loop.md (cross-section P0s), docs/solutions/2026-05-21-spec-completeness-checker-pre-swarm-gate.md (6 sections), docs/solutions/2026-06-07-cpaa-event-replay-simulator-24-agent-swarm-build.md (FC50 pinned signatures), docs/solutions/2026-06-07-autopilot-orchestration-hardening.md (FC51 spec pre-load), docs/solutions/2026-06-01-prompting-dashboard-engine.md (prescriptive code blocks)
