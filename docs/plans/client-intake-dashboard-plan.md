---
title: Client Intake Dashboard
date: 2026-05-22
swarm: true
agents: 15
app_dir: intake-dashboard
feed_forward:
  risk: "Multiple blueprints sharing /admin/submissions url_prefix -- route registration order matters; wrong order could shadow routes"
  verify_first: true
---

# Client Intake Dashboard -- Shared Interface Spec

## 1. Overview

Flask + SQLite + Jinja2 + Bootstrap 5 app for the Amplify AI consulting
business's $500 Audit tier. Public workshop attendees submit an intake form.
Admin (Alex) reviews submissions, creates bottleneck assessments, and decides
whether to schedule a paid audit.

- **Brainstorm:** docs/brainstorms/2026-05-22-client-intake-dashboard-brainstorm.md
- **Brief:** docs/briefs/2026-05-22-client-intake-dashboard-brief.md

## 2. Directory Structure

```
intake-dashboard/
  run.py
  requirements.txt
  schema.sql
  seed.py
  test_smoke.py          # in .gitignore
  .gitignore
  instance/              # auto-created by create_app
    intake.db
  app/
    __init__.py
    db.py
    auth.py
    filters.py
    models/
      __init__.py         # empty
      submissions.py
      assessments.py
      notes.py
    blueprints/
      intake/
        __init__.py       # empty
        routes.py
      submissions/
        __init__.py       # empty
        routes.py
      detail/
        __init__.py       # empty
        routes.py
      status/
        __init__.py       # empty
        routes.py
      assessments/
        __init__.py       # empty
        routes.py
      dashboard/
        __init__.py       # empty
        routes.py
    templates/
      base.html
      auth/
        login.html
      intake/
        form.html
        thank_you.html
      submissions/
        list.html
      detail/
        show.html
      assessments/
        form.html
      dashboard/
        index.html
    static/
      style.css
```

## 2a. requirements.txt

```
flask>=3.0
flask-wtf>=1.2
flask-limiter>=3.5
email-validator>=2.0
markupsafe>=2.1
werkzeug>=3.0
```

**Critical:** `email-validator` is required by the intake form's email
validation (FC33 -- transitive dependency). Without it, `validate_email()`
import crashes at runtime.

## 2b. .gitignore

```
__pycache__/
*.pyc
instance/
.env
test_smoke.py
venv/
.venv/
```

## 2c. run.py

```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

## 3. Database Schema (schema.sql)

```sql
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_name TEXT NOT NULL,
    email TEXT NOT NULL,
    business_name TEXT NOT NULL,
    business_type TEXT NOT NULL,
    team_size TEXT NOT NULL,
    current_workflows TEXT NOT NULL,
    pain_points TEXT NOT NULL,
    tools_used TEXT NOT NULL,
    goals TEXT NOT NULL,
    urgency TEXT NOT NULL,
    submitter_notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'reviewed', 'assessment-ready',
               'audit-scheduled', 'completed', 'declined', 'archived')),
    is_audit_fit INTEGER NOT NULL DEFAULT 0
        CHECK (is_audit_fit IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL UNIQUE,
    summary TEXT NOT NULL DEFAULT '',
    bottlenecks TEXT NOT NULL DEFAULT '',
    root_causes TEXT NOT NULL DEFAULT '',
    next_steps TEXT NOT NULL DEFAULT '',
    audit_fit_recommendation TEXT NOT NULL DEFAULT '',
    admin_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_assessments_submission_id
    ON assessments(submission_id);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notes_submission_id
    ON notes(submission_id);
```

## 4. Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| submissions | app/models/submissions.py | intake_routes, submissions_routes, detail_routes, status_routes, assessment_routes, dashboard_routes, seed |
| assessments | app/models/assessments.py | detail_routes, assessment_routes, seed |
| notes | app/models/notes.py | detail_routes, seed |

## 5. App Configuration (app/__init__.py)

```python
import os
from datetime import timedelta
from flask import Flask
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash

csrf = CSRFProtect()
limiter = Limiter(get_remote_address, storage_uri="memory://")


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # Secret key
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-insecure')

    # Session security
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Request size limit (prevent DoS via large form submissions)
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB

    # Database path
    app.config['DATABASE'] = os.path.join(app.instance_path, 'intake.db')

    # Admin credentials -- fail closed on missing password
    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_password:
        raise RuntimeError("ADMIN_PASSWORD environment variable is required")
    app.config['ADMIN_PASSWORD_HASH'] = generate_password_hash(admin_password)
    app.config['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'admin')

    # Initialize extensions
    csrf.init_app(app)
    limiter.init_app(app)

    # Database teardown
    from app.db import close_db, init_db
    app.teardown_appcontext(close_db)

    # Initialize database tables
    with app.app_context():
        init_db()

    # Register filters
    from app.filters import register_filters
    register_filters(app)

    # Register blueprints -- ORDER MATTERS
    # auth first (no prefix), then intake (public), then admin blueprints
    from app.auth import auth_bp
    from app.blueprints.intake.routes import intake_bp
    from app.blueprints.dashboard.routes import dashboard_bp
    from app.blueprints.submissions.routes import submissions_bp
    from app.blueprints.detail.routes import detail_bp
    from app.blueprints.status.routes import status_bp
    from app.blueprints.assessments.routes import assessments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(intake_bp, url_prefix='/intake')
    app.register_blueprint(dashboard_bp, url_prefix='/admin')
    app.register_blueprint(submissions_bp, url_prefix='/admin/submissions')
    app.register_blueprint(detail_bp, url_prefix='/admin/submissions')
    app.register_blueprint(status_bp, url_prefix='/admin/submissions')
    app.register_blueprint(assessments_bp, url_prefix='/admin/submissions')

    # Health check
    @app.route('/health')
    def health():
        return {'status': 'ok'}

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net; "
            "style-src 'self' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    return app
```

**Critical:** `csrf` and `limiter` are module-level so other agents can import
them: `from app import limiter` (intake_routes needs this).

## 6. Database Connection (app/db.py)

```python
import sqlite3
from flask import g, current_app


def get_db():
    """Get database connection. Stored on g, closed at teardown.

    Usage -- plain function call (NOT a context manager):
        conn = get_db()
        result = some_model_function(conn, ...)

    Row factory: sqlite3.Row (set here, do NOT set in model functions)
    PRAGMAs: journal_mode=WAL, foreign_keys=ON, busy_timeout=5000
    isolation_level: default (Python auto-transaction management)
    """
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
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
    """Create tables from schema.sql if they don't exist."""
    conn = get_db()
    schema_path = current_app.root_path + '/../schema.sql'
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
```

**Rules:**
- Use default `isolation_level` (empty string). Do NOT use `isolation_level=None`.
  Default mode: Python auto-starts transactions before DML (INSERT/UPDATE/DELETE)
  but NOT before SELECT. This means `conn.commit()` works correctly for simple
  writes AND `BEGIN IMMEDIATE` works in model functions because no implicit
  transaction is started by preceding SELECT calls. (Validated by Flask ACID test;
  isolation_level=None causes conn.commit() to be a no-op per BrewOps FC40.)
- Do NOT set `conn.row_factory` in model functions (already set here)
- All timestamps use SQL `datetime('now')`, never Python `datetime.now()`
- `get_db()` is a plain function call, NOT a context manager

## 7. Authentication (app/auth.py)

```python
import functools
from flask import (
    Blueprint, flash, redirect, render_template, request,
    session, url_for, current_app
)
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)


def login_required(view):
    """Decorator: redirect to login if not authenticated."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if (username == current_app.config['ADMIN_USERNAME']
                and check_password_hash(
                    current_app.config['ADMIN_PASSWORD_HASH'], password)):
            session.clear()  # prevent session fixation
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('dashboard.index'))
        flash('Invalid credentials', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('auth.login'))
```

**Session keys:**
- `session['logged_in'] = True` on login
- `session.pop('logged_in', None)` on logout
- `session.get('logged_in')` to check auth status

**Template: auth/login.html**

```html
{% extends "base.html" %}
{% block title %}Login{% endblock %}
{% block content %}
<div class="row justify-content-center mt-5">
  <div class="col-md-4">
    <h2>Admin Login</h2>
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
        <div class="alert alert-{{ 'danger' if category == 'error' else category }}">
          {{ message }}
        </div>
      {% endfor %}
    {% endwith %}
    <form method="POST">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <div class="mb-3">
        <label for="username" class="form-label">Username</label>
        <input type="text" class="form-control" id="username" name="username" required>
      </div>
      <div class="mb-3">
        <label for="password" class="form-label">Password</label>
        <input type="password" class="form-control" id="password" name="password" required>
      </div>
      <button type="submit" class="btn btn-primary w-100">Log In</button>
    </form>
  </div>
</div>
{% endblock %}
```

## 8. Jinja2 Filters (app/filters.py)

```python
from markupsafe import Markup


def register_filters(app):
    @app.template_filter('status_badge')
    def status_badge(status):
        """Render a Bootstrap badge for submission status."""
        colors = {
            'new': 'primary',
            'reviewed': 'info',
            'assessment-ready': 'warning',
            'audit-scheduled': 'success',
            'completed': 'secondary',
            'declined': 'danger',
            'archived': 'dark',
        }
        color = colors.get(status, 'secondary')
        return Markup(f'<span class="badge bg-{color}">{status}</span>')

    @app.template_filter('datetime_format')
    def datetime_format(value):
        """Format ISO datetime for display: '2026-05-22 14:30:00' -> 'May 22, 2026 02:30 PM'"""
        if not value:
            return ''
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime('%b %d, %Y %I:%M %p')
        except (ValueError, TypeError):
            return value
```

## 9. Model Functions

### 9.1 Submission Models (app/models/submissions.py)

```python
import sqlite3

VALID_STATUSES = [
    'new', 'reviewed', 'assessment-ready', 'audit-scheduled',
    'completed', 'declined', 'archived'
]
TERMINAL_STATUSES = ['completed', 'declined', 'archived']


def create_submission(conn: sqlite3.Connection, data: dict) -> int:
    """Insert a new submission. Commits internally.

    Usage:
        submission_id = create_submission(conn, {
            'contact_name': 'Jane Doe',
            'email': 'jane@example.com',
            'business_name': 'Acme Corp',
            'business_type': 'SaaS',
            'team_size': '10-50',
            'current_workflows': 'Manual spreadsheets',
            'pain_points': 'Data entry takes 4 hours/day',
            'tools_used': 'Excel, Google Docs',
            'goals': 'Automate data entry',
            'urgency': 'Next 30 days',
            'submitter_notes': 'Optional extra context'
        })
        # submission_id is an int, NOT a Row

    Returns: int (the new submission's ID)
    Transaction: commits internally
    """
    cursor = conn.execute(
        """INSERT INTO submissions
           (contact_name, email, business_name, business_type, team_size,
            current_workflows, pain_points, tools_used, goals, urgency,
            submitter_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data['contact_name'], data['email'], data['business_name'],
         data['business_type'], data['team_size'], data['current_workflows'],
         data['pain_points'], data['tools_used'], data['goals'],
         data['urgency'], data.get('submitter_notes', ''))
    )
    conn.commit()
    return cursor.lastrowid


def get_submission(conn: sqlite3.Connection, submission_id: int) -> sqlite3.Row | None:
    """Fetch a single submission by ID.

    Usage:
        submission = get_submission(conn, submission_id)
        if submission is None:
            abort(404)

    Returns: sqlite3.Row or None
    Transaction: does NOT commit (read-only)
    """
    return conn.execute(
        "SELECT * FROM submissions WHERE id = ?", (submission_id,)
    ).fetchone()


def list_submissions(conn: sqlite3.Connection,
                     status_filter: str | None = None) -> list[sqlite3.Row]:
    """List all submissions, optionally filtered by status.

    Usage:
        submissions = list_submissions(conn)
        submissions = list_submissions(conn, status_filter='new')

    Returns: list of sqlite3.Row, ordered by created_at DESC
    Transaction: does NOT commit (read-only)
    """
    if status_filter and status_filter in VALID_STATUSES:
        return conn.execute(
            "SELECT * FROM submissions WHERE status = ? ORDER BY created_at DESC",
            (status_filter,)
        ).fetchall()
    return conn.execute(
        "SELECT * FROM submissions ORDER BY created_at DESC"
    ).fetchall()


def update_status(conn: sqlite3.Connection, submission_id: int,
                  new_status: str) -> bool:
    """Update submission status with terminal-state enforcement.
    Uses BEGIN IMMEDIATE to prevent TOCTOU race.

    Usage:
        success = update_status(conn, submission_id, 'reviewed')
        if not success:
            flash('Cannot change status of a terminal submission', 'error')

    Returns: bool (True if updated, False if in terminal state or not found)
    Transaction: commits internally with BEGIN IMMEDIATE + try/except/ROLLBACK
    """
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT status FROM submissions WHERE id = ?",
            (submission_id,)
        ).fetchone()
        if row is None or row['status'] in TERMINAL_STATUSES:
            conn.rollback()
            return False
        conn.execute(
            """UPDATE submissions
               SET status = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (new_status, submission_id)
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def toggle_audit_fit(conn: sqlite3.Connection, submission_id: int) -> None:
    """Toggle the is_audit_fit flag. Commits internally.

    Usage:
        toggle_audit_fit(conn, submission_id)

    Returns: None
    Transaction: commits internally
    """
    conn.execute(
        """UPDATE submissions
           SET is_audit_fit = CASE WHEN is_audit_fit = 0 THEN 1 ELSE 0 END,
               updated_at = datetime('now')
           WHERE id = ?""",
        (submission_id,)
    )
    conn.commit()


def count_by_status(conn: sqlite3.Connection) -> dict:
    """Count submissions grouped by status.

    Usage:
        stats = count_by_status(conn)
        # stats = {'new': 3, 'reviewed': 1, 'assessment-ready': 0, ...}
        # Always includes all valid statuses (0 for missing)

    Returns: dict[str, int]
    Transaction: does NOT commit (read-only)
    """
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM submissions GROUP BY status"
    ).fetchall()
    counts = {s: 0 for s in VALID_STATUSES}
    for row in rows:
        counts[row['status']] = row['cnt']
    return counts
```

### 9.2 Assessment Models (app/models/assessments.py)

```python
import sqlite3


def create_assessment(conn: sqlite3.Connection, submission_id: int,
                      data: dict) -> int:
    """Create a new assessment for a submission. Commits internally.

    Usage:
        assessment_id = create_assessment(conn, submission_id, {
            'summary': '...',
            'bottlenecks': '...',
            'root_causes': '...',
            'next_steps': '...',
            'audit_fit_recommendation': '...',
            'admin_notes': '...'
        })
        # assessment_id is an int, NOT a Row

    Returns: int (the new assessment's ID)
    Transaction: commits internally
    """
    cursor = conn.execute(
        """INSERT INTO assessments
           (submission_id, summary, bottlenecks, root_causes,
            next_steps, audit_fit_recommendation, admin_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (submission_id, data.get('summary', ''),
         data.get('bottlenecks', ''), data.get('root_causes', ''),
         data.get('next_steps', ''),
         data.get('audit_fit_recommendation', ''),
         data.get('admin_notes', ''))
    )
    conn.commit()
    return cursor.lastrowid


def get_assessment_by_submission(conn: sqlite3.Connection,
                                 submission_id: int) -> sqlite3.Row | None:
    """Fetch the assessment for a submission (1:1 relationship).

    Usage:
        assessment = get_assessment_by_submission(conn, submission_id)
        if assessment is None:
            # No assessment yet -- show create form

    Returns: sqlite3.Row or None
    Transaction: does NOT commit (read-only)
    """
    return conn.execute(
        "SELECT * FROM assessments WHERE submission_id = ?",
        (submission_id,)
    ).fetchone()


def update_assessment(conn: sqlite3.Connection, assessment_id: int,
                      data: dict) -> None:
    """Update an existing assessment. Commits internally.

    Usage:
        update_assessment(conn, assessment['id'], {
            'summary': '...',
            'bottlenecks': '...',
            'root_causes': '...',
            'next_steps': '...',
            'audit_fit_recommendation': '...',
            'admin_notes': '...'
        })

    Returns: None
    Transaction: commits internally
    """
    conn.execute(
        """UPDATE assessments
           SET summary = ?, bottlenecks = ?, root_causes = ?,
               next_steps = ?, audit_fit_recommendation = ?,
               admin_notes = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (data.get('summary', ''), data.get('bottlenecks', ''),
         data.get('root_causes', ''), data.get('next_steps', ''),
         data.get('audit_fit_recommendation', ''),
         data.get('admin_notes', ''), assessment_id)
    )
    conn.commit()
```

### 9.3 Note Models (app/models/notes.py)

```python
import sqlite3


def create_note(conn: sqlite3.Connection, submission_id: int,
                content: str) -> int:
    """Add a note to a submission. Commits internally.

    Usage:
        note_id = create_note(conn, submission_id, 'Looks promising')
        # note_id is an int, NOT a Row

    Returns: int (the new note's ID)
    Transaction: commits internally
    """
    cursor = conn.execute(
        "INSERT INTO notes (submission_id, content) VALUES (?, ?)",
        (submission_id, content)
    )
    conn.commit()
    return cursor.lastrowid


def list_notes(conn: sqlite3.Connection,
               submission_id: int) -> list[sqlite3.Row]:
    """List all notes for a submission, newest first.

    Usage:
        notes = list_notes(conn, submission_id)

    Returns: list of sqlite3.Row, ordered by created_at DESC
    Transaction: does NOT commit (read-only)
    """
    return conn.execute(
        "SELECT * FROM notes WHERE submission_id = ? ORDER BY created_at DESC",
        (submission_id,)
    ).fetchall()
```

## 10. Route Table

| Method | Path | Blueprint | Handler | url_for | Template |
|--------|------|-----------|---------|---------|----------|
| GET/POST | /intake | intake | intake_form | `intake.intake_form` | intake/form.html |
| GET | /intake/thank-you | intake | thank_you | `intake.thank_you` | intake/thank_you.html |
| GET/POST | /login | auth | login | `auth.login` | auth/login.html |
| POST | /logout | auth | logout | `auth.logout` | redirect |
| GET | /admin/ | dashboard | index | `dashboard.index` | dashboard/index.html |
| GET | /admin/submissions | submissions | list_view | `submissions.list_view` | submissions/list.html |
| GET | /admin/submissions/&lt;int:submission_id&gt; | detail | view_submission | `detail.view_submission` | detail/show.html |
| POST | /admin/submissions/&lt;int:submission_id&gt;/notes | detail | add_note | `detail.add_note` | redirect |
| POST | /admin/submissions/&lt;int:submission_id&gt;/status | status | change_status | `status.change_status` | redirect |
| POST | /admin/submissions/&lt;int:submission_id&gt;/audit-fit | status | toggle_fit | `status.toggle_fit` | redirect |
| GET/POST | /admin/submissions/&lt;int:submission_id&gt;/assessment | assessments | assessment_form | `assessments.assessment_form` | assessments/form.html |
| GET | /health | (app) | health | `health` | JSON |

## 11. Template Render Context

Every `render_template()` call with exact variable names:

```python
# intake/form.html expects:
render_template('intake/form.html')
# No extra context -- form fields are static HTML

# intake/thank_you.html expects:
render_template('intake/thank_you.html')
# No extra context

# auth/login.html expects:
render_template('auth/login.html')
# No extra context -- uses get_flashed_messages()

# dashboard/index.html expects:
render_template('dashboard/index.html',
    stats=count_by_status(conn),
    total=sum(count_by_status(conn).values())
)
# stats is dict: {'new': 3, 'reviewed': 1, ...}
# total is int: sum of all counts

# submissions/list.html expects:
render_template('submissions/list.html',
    submissions=list_submissions(conn, status_filter=status_filter),
    status_filter=status_filter,
    statuses=VALID_STATUSES
)
# submissions is list of sqlite3.Row
# status_filter is str or None
# statuses is list of str (for filter dropdown)

# detail/show.html expects:
render_template('detail/show.html',
    submission=submission,
    assessment=get_assessment_by_submission(conn, submission_id),
    notes=list_notes(conn, submission_id),
    statuses=VALID_STATUSES,
    terminal_statuses=TERMINAL_STATUSES
)
# submission is sqlite3.Row
# assessment is sqlite3.Row or None
# notes is list of sqlite3.Row
# statuses and terminal_statuses are lists of str

# assessments/form.html expects:
render_template('assessments/form.html',
    submission=submission,
    assessment=assessment
)
# submission is sqlite3.Row
# assessment is sqlite3.Row or None (None = create, Row = edit)
```

## 12. Export Names Table

| Name | Type | Defined By | Used By |
|------|------|------------|---------|
| `create_submission` | model function | submission_models | intake_routes, seed |
| `get_submission` | model function | submission_models | detail_routes, status_routes, assessment_routes, seed |
| `list_submissions` | model function | submission_models | submissions_routes |
| `update_status` | model function | submission_models | status_routes |
| `toggle_audit_fit` | model function | submission_models | status_routes |
| `count_by_status` | model function | submission_models | dashboard_routes |
| `VALID_STATUSES` | constant (list) | submission_models | submissions_routes, detail_routes, status_routes |
| `TERMINAL_STATUSES` | constant (list) | submission_models | detail_routes, status_routes |
| `create_assessment` | model function | assessment_models | assessment_routes |
| `get_assessment_by_submission` | model function | assessment_models | detail_routes, assessment_routes |
| `update_assessment` | model function | assessment_models | assessment_routes |
| `create_note` | model function | note_models | detail_routes |
| `list_notes` | model function | note_models | detail_routes |
| `get_db` | db function | core (db.py) | ALL route agents, seed |
| `close_db` | db function | core (db.py) | core (__init__.py) |
| `init_db` | db function | core (db.py) | core (__init__.py) |
| `login_required` | decorator | auth | submissions_routes, detail_routes, status_routes, assessment_routes, dashboard_routes |
| `csrf` | extension | core (__init__.py) | (auto-applied) |
| `limiter` | extension | core (__init__.py) | intake_routes |
| `register_filters` | function | filters | core (__init__.py) |
| `auth_bp` | blueprint | auth | core (__init__.py) |
| `intake_bp` | blueprint | intake_routes | core (__init__.py) |
| `dashboard_bp` | blueprint | dashboard_routes | core (__init__.py) |
| `submissions_bp` | blueprint | submissions_routes | core (__init__.py) |
| `detail_bp` | blueprint | detail_routes | core (__init__.py) |
| `status_bp` | blueprint | status_routes | core (__init__.py) |
| `assessments_bp` | blueprint | assessment_routes | core (__init__.py) |
| `intake.intake_form` | endpoint | intake_routes | layout (navbar) |
| `intake.thank_you` | endpoint | intake_routes | intake_routes (redirect) |
| `auth.login` | endpoint | auth | auth (redirect), ALL admin routes (login_required redirect) |
| `auth.logout` | endpoint | auth | layout (navbar) |
| `dashboard.index` | endpoint | dashboard_routes | auth (redirect after login), layout (navbar) |
| `submissions.list_view` | endpoint | submissions_routes | layout (navbar), dashboard_routes (link) |
| `detail.view_submission` | endpoint | detail_routes | submissions_routes (link), detail_routes (redirect), status_routes (redirect), assessment_routes (redirect) |
| `detail.add_note` | endpoint | detail_routes | detail/show.html (form action) |
| `status.change_status` | endpoint | status_routes | detail/show.html (form action) |
| `status.toggle_fit` | endpoint | status_routes | detail/show.html (form action) |
| `assessments.assessment_form` | endpoint | assessment_routes | detail/show.html (link) |
| `health` | endpoint | core | tests |
| `/intake` | route path | intake_routes | layout (navbar link) |
| `/intake/thank-you` | route path | intake_routes | intake_routes (redirect) |
| `/login` | route path | auth | auth (redirect), login_required |
| `/logout` | route path | auth | layout (navbar form) |
| `/admin/` | route path | dashboard_routes | auth (redirect after login) |
| `/admin/submissions` | route path | submissions_routes | layout (navbar link) |
| `/admin/submissions/<int:submission_id>` | route path | detail_routes | submissions_routes (link) |
| `/admin/submissions/<int:submission_id>/notes` | route path | detail_routes | detail/show.html (form) |
| `/admin/submissions/<int:submission_id>/status` | route path | status_routes | detail/show.html (form) |
| `/admin/submissions/<int:submission_id>/audit-fit` | route path | status_routes | detail/show.html (form) |
| `/admin/submissions/<int:submission_id>/assessment` | route path | assessment_routes | detail/show.html (link) |
| `/health` | route path | core | tests |

## 13. Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/db.py | app/blueprints/intake/routes.py | `from app.db import get_db` |
| app/db.py | app/blueprints/submissions/routes.py | `from app.db import get_db` |
| app/db.py | app/blueprints/detail/routes.py | `from app.db import get_db` |
| app/db.py | app/blueprints/status/routes.py | `from app.db import get_db` |
| app/db.py | app/blueprints/assessments/routes.py | `from app.db import get_db` |
| app/db.py | app/blueprints/dashboard/routes.py | `from app.db import get_db` |
| app/db.py | seed.py | `from app.db import get_db` |
| app/__init__.py | app/blueprints/intake/routes.py | `from app import limiter` |
| app/auth.py | app/blueprints/submissions/routes.py | `from app.auth import login_required` |
| app/auth.py | app/blueprints/detail/routes.py | `from app.auth import login_required` |
| app/auth.py | app/blueprints/status/routes.py | `from app.auth import login_required` |
| app/auth.py | app/blueprints/assessments/routes.py | `from app.auth import login_required` |
| app/auth.py | app/blueprints/dashboard/routes.py | `from app.auth import login_required` |
| app/models/submissions.py | app/blueprints/intake/routes.py | `from app.models.submissions import create_submission` |
| app/models/submissions.py | app/blueprints/submissions/routes.py | `from app.models.submissions import list_submissions, VALID_STATUSES` |
| app/models/submissions.py | app/blueprints/detail/routes.py | `from app.models.submissions import get_submission, VALID_STATUSES, TERMINAL_STATUSES` |
| app/models/submissions.py | app/blueprints/status/routes.py | `from app.models.submissions import get_submission, update_status, toggle_audit_fit, VALID_STATUSES, TERMINAL_STATUSES` |
| app/models/submissions.py | app/blueprints/assessments/routes.py | `from app.models.submissions import get_submission` |
| app/models/submissions.py | app/blueprints/dashboard/routes.py | `from app.models.submissions import count_by_status` |
| app/models/assessments.py | app/blueprints/detail/routes.py | `from app.models.assessments import get_assessment_by_submission` |
| app/models/assessments.py | app/blueprints/assessments/routes.py | `from app.models.assessments import create_assessment, get_assessment_by_submission, update_assessment` |
| app/models/notes.py | app/blueprints/detail/routes.py | `from app.models.notes import create_note, list_notes` |
| app/models/submissions.py | seed.py | `from app.models.submissions import create_submission` |
| app/models/assessments.py | seed.py | `from app.models.assessments import create_assessment` |
| app/models/notes.py | seed.py | `from app.models.notes import create_note` |
| app/filters.py | app/__init__.py | `from app.filters import register_filters` |
| app/db.py | app/__init__.py | `from app.db import close_db, init_db` |

## 14. Input Validation Prescriptions

| Route | Input | Form Field | Validation | Error Response |
|-------|-------|------------|------------|----------------|
| POST /intake | contact_name | `contact_name` | Strip, 1-100 chars, required | Flash 'Contact name is required', re-render form |
| POST /intake | email | `email` | Strip, 1-254 chars, email format via `email_validator.validate_email()`, required | Flash 'Valid email is required', re-render form |
| POST /intake | business_name | `business_name` | Strip, 1-200 chars, required | Flash 'Business name is required', re-render form |
| POST /intake | business_type | `business_type` | Strip, 1-200 chars, required | Flash 'Business type / industry is required', re-render form |
| POST /intake | team_size | `team_size` | Strip, 1-100 chars, required | Flash 'Team size is required', re-render form |
| POST /intake | current_workflows | `current_workflows` | Strip, 1-2000 chars, required | Flash 'Current workflows description is required', re-render form |
| POST /intake | pain_points | `pain_points` | Strip, 1-2000 chars, required | Flash 'Pain points description is required', re-render form |
| POST /intake | tools_used | `tools_used` | Strip, 1-2000 chars, required | Flash 'Tools currently used is required', re-render form |
| POST /intake | goals | `goals` | Strip, 1-2000 chars, required | Flash 'Goals / desired outcomes is required', re-render form |
| POST /intake | urgency | `urgency` | Strip, 1-200 chars, required | Flash 'Urgency / timeline is required', re-render form |
| POST /intake | submitter_notes | `submitter_notes` | Strip, 0-2000 chars, optional | (none -- always valid) |
| POST /intake | website (honeypot) | `website` | Must be empty string | Silently redirect to thank-you (do NOT flash error) |
| POST /login | username | `username` | Strip, required | Flash 'Invalid credentials', re-render |
| POST /login | password | `password` | Required, non-empty | Flash 'Invalid credentials', re-render |
| POST .../notes | content | `content` | Strip, 1-2000 chars, required | Flash 'Note content is required', redirect to detail |
| POST .../status | new_status | `new_status` | Must be in VALID_STATUSES | Flash 'Invalid status', redirect to detail |
| POST .../status | (business rule) | N/A | Submission must NOT be in TERMINAL_STATUSES | Flash 'Cannot change status of completed/declined/archived submission', redirect to detail |
| POST .../assessment | summary | `summary` | Strip, 0-5000 chars, optional | (none) |
| POST .../assessment | bottlenecks | `bottlenecks` | Strip, 0-5000 chars, optional | (none) |
| POST .../assessment | root_causes | `root_causes` | Strip, 0-5000 chars, optional | (none) |
| POST .../assessment | next_steps | `next_steps` | Strip, 0-5000 chars, optional | (none) |
| POST .../assessment | audit_fit_recommendation | `audit_fit_recommendation` | Strip, 0-5000 chars, optional | (none) |
| POST .../assessment | admin_notes | `admin_notes` | Strip, 0-5000 chars, optional | (none) |
| POST /logout | (none) | N/A | No user inputs (CSRF only) | N/A |
| GET .../&lt;int:submission_id&gt; | submission_id | URL param | Must be valid int (Flask enforces), must exist in DB | `abort(404)` |
| POST .../audit-fit | (none) | N/A | No user inputs beyond CSRF. Submission must exist | `abort(404)` if not found |

**Email validation prescriptive code:**

```python
from email_validator import validate_email, EmailNotValidError

email = request.form.get('email', '').strip()[:254]
try:
    valid = validate_email(email, check_deliverability=False)
    email = valid.normalized
except EmailNotValidError:
    flash('Valid email is required', 'error')
    return render_template('intake/form.html')
```

**Honeypot prescriptive code:**

```python
# Check honeypot BEFORE other validation
website = request.form.get('website', '')
if website:
    # Bot detected -- silently redirect (don't reveal honeypot)
    return redirect(url_for('intake.thank_you'))
```

## 15. Coordinated Behaviors

| Surface | Rule | Owner |
|---------|------|-------|
| Blueprint registration | Registered in create_app() in this order: auth, intake, dashboard, submissions, detail, status, assessments | core |
| Blueprint prefixes | auth: none, intake: /intake, dashboard: /admin, submissions+detail+status+assessments: /admin/submissions | core |
| Navbar links | When logged in: Dashboard, Submissions, Logout form. When not logged in: Login. Always: Intake Form link. | layout |
| CSRF token | `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` -- WITH parentheses on `csrf_token()` | ALL route agents |
| Session key: logged_in | `session['logged_in'] = True` on login, `session.pop('logged_in', None)` on logout, `session.get('logged_in')` to check | auth + layout |
| Base template | ALL templates use `{% extends "base.html" %}` (not layout.html, not main.html) | ALL route agents |
| Block names | `{% block title %}` and `{% block content %}` | ALL route agents |
| Timestamps | SQL `datetime('now')` in all INSERT/UPDATE. NEVER Python `datetime.now()` | ALL model agents |
| Row factory | Set ONLY in `get_db()`. Do NOT set `conn.row_factory` in model functions | core (db.py) |
| Flash messages | `flash(message, 'error')` for errors, `flash(message, 'success')` for success | ALL route agents |
| Flash rendering | `get_flashed_messages(with_categories=true)` in base.html | layout |
| Status constants | Import `VALID_STATUSES` and `TERMINAL_STATUSES` from `app.models.submissions` -- do NOT redefine | ALL route agents that need them |
| Login redirect | `login_required` redirects to `url_for('auth.login')` | auth |
| Post-action redirects | Successful POST handlers redirect with `redirect(url_for(...))`. Validation failures may re-render the form (intake, login) | ALL route agents |
| 404 pattern | `if submission is None: abort(404)` after `get_submission()` | ALL detail/status/assessment routes |

## 16. Template Contracts

### Session Keys

| Key | Set By | Read By | Value |
|-----|--------|---------|-------|
| `session['logged_in']` | auth (login) | `login_required` decorator, base.html navbar | `True` |

### CSRF Token Syntax

All POST forms MUST use this exact line:
```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```
`csrf_token()` requires parentheses. Without them, the template renders the
function object as a string, and every POST gets a CSRF validation failure.

### CSS Framework

| Item | Value |
|------|-------|
| Framework | Bootstrap 5.3 from cdn.jsdelivr.net (with SRI integrity hash) |
| Custom CSS | app/static/style.css (layout agent owns) |

### Base Template

| Item | Value |
|------|-------|
| Filename | app/templates/base.html |
| Owner | layout agent |
| Extended by | ALL template agents via `{% extends "base.html" %}` |
| Blocks | `{% block title %}` (page title), `{% block content %}` (main content) |

### Base Template Structure (prescriptive)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Client Intake Dashboard{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
          rel="stylesheet"
          integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YcnS/1p0OQIU8kFlDkCCTlJV8OAVZ7MQHCW"
          crossorigin="anonymous">
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{% if session.get('logged_in') %}{{ url_for('dashboard.index') }}{% else %}{{ url_for('intake.intake_form') }}{% endif %}">
                Intake Dashboard
            </a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="{{ url_for('intake.intake_form') }}">Intake Form</a>
                {% if session.get('logged_in') %}
                    <a class="nav-link" href="{{ url_for('dashboard.index') }}">Dashboard</a>
                    <a class="nav-link" href="{{ url_for('submissions.list_view') }}">Submissions</a>
                    <form method="POST" action="{{ url_for('auth.logout') }}" class="d-inline">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                        <button type="submit" class="btn btn-link nav-link">Logout</button>
                    </form>
                {% else %}
                    <a class="nav-link" href="{{ url_for('auth.login') }}">Login</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <main class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
            integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz"
            crossorigin="anonymous"></script>
</body>
</html>
```

## 17. Transaction Contracts

| Function | SQL Operations | Commits | Error Handling |
|----------|---------------|---------|----------------|
| `create_submission` | INSERT submissions | commits internally (`conn.commit()`) | N/A (single INSERT) |
| `get_submission` | SELECT submissions | does NOT commit (read-only) | N/A |
| `list_submissions` | SELECT submissions | does NOT commit (read-only) | N/A |
| `update_status` | SELECT + UPDATE submissions | commits internally with BEGIN IMMEDIATE | try/except/ROLLBACK |
| `toggle_audit_fit` | UPDATE submissions | commits internally (`conn.commit()`) | N/A (single UPDATE) |
| `count_by_status` | SELECT submissions | does NOT commit (read-only) | N/A |
| `create_assessment` | INSERT assessments | commits internally (`conn.commit()`) | N/A (single INSERT) |
| `get_assessment_by_submission` | SELECT assessments | does NOT commit (read-only) | N/A |
| `update_assessment` | UPDATE assessments | commits internally (`conn.commit()`) | N/A (single UPDATE) |
| `create_note` | INSERT notes | commits internally (`conn.commit()`) | N/A (single INSERT) |
| `list_notes` | SELECT notes | does NOT commit (read-only) | N/A |

**Rule:** Only `update_status` uses BEGIN IMMEDIATE (read-then-write with
business rule check). All other write functions are single-statement operations
that commit immediately. No function leaves an uncommitted transaction.

## 18. Authorization Matrix

| Route | Method | Mode | Check |
|-------|--------|------|-------|
| GET /intake | GET | public | N/A |
| POST /intake | POST | public (rate limited: 5/min/IP) | N/A |
| GET /intake/thank-you | GET | public | N/A |
| GET /login | GET | public | N/A |
| POST /login | POST | public | N/A |
| POST /logout | POST | public | N/A (unauthenticated logout is safe) |
| GET /admin/ | GET | login-required | `@login_required` |
| GET /admin/submissions | GET | login-required | `@login_required` |
| GET /admin/submissions/&lt;id&gt; | GET | login-required | `@login_required` |
| POST /admin/submissions/&lt;id&gt;/notes | POST | login-required | `@login_required` |
| POST /admin/submissions/&lt;id&gt;/status | POST | login-required | `@login_required` |
| POST /admin/submissions/&lt;id&gt;/audit-fit | POST | login-required | `@login_required` |
| GET/POST /admin/submissions/&lt;id&gt;/assessment | GET/POST | login-required | `@login_required` |
| GET /health | GET | public | N/A |

**Note:** Single admin, no ownership checks needed. All admin routes use
`@login_required` only. No IDOR risk because there is only one admin user.

## 19. Smoke Test File (test_smoke.py)

```python
"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
import re

os.environ.setdefault("SECRET_KEY", "test-smoke-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-strong-pw-123")
os.environ.setdefault("ADMIN_USERNAME", "admin")

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


# --- Phase 1: Public routes (no auth) ---

r = client.get("/health")
check("GET /health (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/intake")
check("GET /intake (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/intake/thank-you")
check("GET /intake/thank-you (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/login")
check("GET /login (200)", r.status_code == 200, f"got {r.status_code}")

# Admin routes redirect to login when not authenticated
r = client.get("/admin/")
check("GET /admin/ (302 to login)", r.status_code == 302, f"got {r.status_code}")

r = client.get("/admin/submissions")
check("GET /admin/submissions (302 to login)", r.status_code == 302, f"got {r.status_code}")

# --- Phase 2a: Auth write-side with real CSRF ---

r = client.get("/login")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Login form has CSRF token", m is not None,
      "csrf_token input not found -- check {{ csrf_token() }} syntax")

csrf_tok = m.group(1) if m else ""

r = client.post("/login", data={
    "username": "admin",
    "password": os.environ["ADMIN_PASSWORD"],
    "csrf_token": csrf_tok,
}, follow_redirects=False)
check("POST /login (redirect)", r.status_code == 302,
      f"got {r.status_code} -- CSRF token may be invalid")

with client.session_transaction() as sess:
    check("Login sets session['logged_in']",
          sess.get('logged_in') is True,
          f"session keys after login: {list(sess.keys())}")

# --- Phase 2b: Admin routes accessible after login ---

r = client.get("/admin/")
check("GET /admin/ (200, logged in)", r.status_code == 200, f"got {r.status_code}")

html = r.data.decode()
check("Dashboard has navbar links",
      "Submissions" in html and "Dashboard" in html,
      "navbar may be broken -- check session key in base.html")

r = client.get("/admin/submissions")
check("GET /admin/submissions (200)", r.status_code == 200, f"got {r.status_code}")

# --- Phase 3: Intake form submission with CSRF ---

r = client.get("/intake")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Intake form has CSRF token", m is not None)
csrf_tok = m.group(1) if m else ""

r = client.post("/intake", data={
    "contact_name": "Test User",
    "email": "test@example.com",
    "business_name": "Test Corp",
    "business_type": "SaaS",
    "team_size": "5-10",
    "current_workflows": "Manual data entry in spreadsheets",
    "pain_points": "Too slow, error-prone",
    "tools_used": "Excel, Google Docs",
    "goals": "Automate repetitive tasks",
    "urgency": "Next 30 days",
    "submitter_notes": "",
    "website": "",
    "csrf_token": csrf_tok,
}, follow_redirects=False)
check("POST /intake (302 to thank-you)", r.status_code == 302, f"got {r.status_code}")

# --- Phase 4: Verify submission appears in admin ---

r = client.get("/admin/submissions")
html = r.data.decode()
check("Submission visible in list", "Test Corp" in html,
      "submitted business_name not found in list")

# Find the submission link
m = re.search(r'href="(/admin/submissions/\d+)"', html)
check("Submission has detail link", m is not None)

if m:
    detail_url = m.group(1)
    r = client.get(detail_url)
    check("GET submission detail (200)", r.status_code == 200, f"got {r.status_code}")
    html = r.data.decode()
    check("Detail shows contact name", "Test User" in html)
    check("Detail shows email", "test@example.com" in html)
    check("Detail shows status badge", "new" in html.lower())

    # Extract submission_id from URL
    sub_id = detail_url.split("/")[-1]

    # --- Phase 5: Add a note ---
    r = client.get(detail_url)
    html = r.data.decode()
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/notes", data={
        "content": "Looks like a strong lead",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST add note (302)", r.status_code == 302, f"got {r.status_code}")

    r = client.get(detail_url)
    html = r.data.decode()
    check("Note visible on detail", "Looks like a strong lead" in html)

    # --- Phase 6: Change status ---
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/status", data={
        "new_status": "reviewed",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST change status (302)", r.status_code == 302, f"got {r.status_code}")

    r = client.get(detail_url)
    html = r.data.decode()
    check("Status updated to reviewed", "reviewed" in html.lower())

    # --- Phase 7: Create assessment ---
    r = client.get(f"/admin/submissions/{sub_id}/assessment")
    check("GET assessment form (200)", r.status_code == 200, f"got {r.status_code}")

    html = r.data.decode()
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/assessment", data={
        "summary": "Strong candidate for automation audit",
        "bottlenecks": "Manual data entry, no integration",
        "root_causes": "Legacy spreadsheet workflows",
        "next_steps": "Schedule 60-min audit call",
        "audit_fit_recommendation": "High fit -- clear ROI",
        "admin_notes": "Follow up by Friday",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST create assessment (302)", r.status_code == 302, f"got {r.status_code}")

    r = client.get(detail_url)
    html = r.data.decode()
    check("Assessment visible on detail", "Strong candidate" in html)

    # --- Phase 8: Toggle audit fit ---
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/audit-fit", data={
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST toggle audit-fit (302)", r.status_code == 302, f"got {r.status_code}")

    # --- Phase 9: Filter by status ---
    r = client.get("/admin/submissions?status=reviewed")
    html = r.data.decode()
    check("Filter by status=reviewed shows result", "Test Corp" in html)

    r = client.get("/admin/submissions?status=completed")
    html = r.data.decode()
    check("Filter by status=completed shows no result", "Test Corp" not in html)

    # --- Phase 10: Terminal status enforcement ---
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', client.get(detail_url).data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/status", data={
        "new_status": "completed",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST set terminal status (302)", r.status_code == 302, f"got {r.status_code}")

    # Try to change from terminal status
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', client.get(detail_url).data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post(f"/admin/submissions/{sub_id}/status", data={
        "new_status": "new",
        "csrf_token": csrf_tok,
    }, follow_redirects=True)
    html = r.data.decode()
    check("Terminal status blocks change", "cannot" in html.lower() or "Cannot" in html)

    # --- Phase 11: Honeypot rejection ---
    r = client.get("/intake")
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post("/intake", data={
        "contact_name": "Bot User",
        "email": "bot@spam.com",
        "business_name": "Spam Corp",
        "business_type": "Spam",
        "team_size": "1",
        "current_workflows": "Spam",
        "pain_points": "Spam",
        "tools_used": "Spam",
        "goals": "Spam",
        "urgency": "Now",
        "submitter_notes": "",
        "website": "http://spam.com",
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("Honeypot submission redirects (302)", r.status_code == 302, f"got {r.status_code}")

    # Verify honeypot submission was NOT saved
    r = client.get("/admin/submissions")
    html = r.data.decode()
    check("Honeypot submission not in list", "Spam Corp" not in html)

    # --- Phase 12: Logout ---
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', client.get("/admin/").data.decode())
    csrf_tok = m.group(1) if m else ""

    r = client.post("/logout", data={
        "csrf_token": csrf_tok,
    }, follow_redirects=False)
    check("POST /logout (302)", r.status_code == 302, f"got {r.status_code}")

    r = client.get("/admin/")
    check("Admin redirects after logout", r.status_code == 302, f"got {r.status_code}")


# --- Summary ---
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
```

## 20. File Assignment Boundaries

| File | Agent |
|------|-------|
| app/__init__.py | core |
| app/db.py | core |
| schema.sql | core |
| requirements.txt | core |
| .gitignore | core |
| run.py | core |
| app/models/__init__.py | core |
| app/blueprints/intake/__init__.py | core |
| app/blueprints/submissions/__init__.py | core |
| app/blueprints/detail/__init__.py | core |
| app/blueprints/status/__init__.py | core |
| app/blueprints/assessments/__init__.py | core |
| app/blueprints/dashboard/__init__.py | core |
| app/templates/base.html | layout |
| app/static/style.css | layout |
| app/auth.py | auth |
| app/templates/auth/login.html | auth |
| app/models/submissions.py | submission_models |
| app/models/assessments.py | assessment_models |
| app/models/notes.py | note_models |
| app/blueprints/intake/routes.py | intake_routes |
| app/templates/intake/form.html | intake_routes |
| app/templates/intake/thank_you.html | intake_routes |
| app/blueprints/submissions/routes.py | submissions_routes |
| app/templates/submissions/list.html | submissions_routes |
| app/blueprints/detail/routes.py | detail_routes |
| app/templates/detail/show.html | detail_routes |
| app/blueprints/status/routes.py | status_routes |
| app/blueprints/assessments/routes.py | assessment_routes |
| app/templates/assessments/form.html | assessment_routes |
| app/blueprints/dashboard/routes.py | dashboard_routes |
| app/templates/dashboard/index.html | dashboard_routes |
| app/filters.py | filters |
| seed.py | seed |
| test_smoke.py | tests |

## 21. Swarm Agent Assignment

| # | Agent | Files | Dependencies |
|---|-------|-------|-------------|
| 1 | core | app/__init__.py, app/db.py, schema.sql, requirements.txt, .gitignore, run.py, app/models/__init__.py, app/blueprints/intake/__init__.py, app/blueprints/submissions/__init__.py, app/blueprints/detail/__init__.py, app/blueprints/status/__init__.py, app/blueprints/assessments/__init__.py, app/blueprints/dashboard/__init__.py | None |
| 2 | layout | app/templates/base.html, app/static/style.css | None |
| 3 | auth | app/auth.py, app/templates/auth/login.html | None |
| 4 | submission_models | app/models/submissions.py | None |
| 5 | assessment_models | app/models/assessments.py | None |
| 6 | note_models | app/models/notes.py | None |
| 7 | intake_routes | app/blueprints/intake/routes.py, app/templates/intake/form.html, app/templates/intake/thank_you.html | submission_models, db.py, limiter |
| 8 | submissions_routes | app/blueprints/submissions/routes.py, app/templates/submissions/list.html | submission_models, db.py, auth |
| 9 | detail_routes | app/blueprints/detail/routes.py, app/templates/detail/show.html | submission_models, assessment_models, note_models, db.py, auth |
| 10 | status_routes | app/blueprints/status/routes.py | submission_models, db.py, auth |
| 11 | assessment_routes | app/blueprints/assessments/routes.py, app/templates/assessments/form.html | submission_models, assessment_models, db.py, auth |
| 12 | dashboard_routes | app/blueprints/dashboard/routes.py, app/templates/dashboard/index.html | submission_models, db.py, auth |
| 13 | filters | app/filters.py | None |
| 14 | seed | seed.py | submission_models, assessment_models, note_models, db.py |
| 15 | tests | test_smoke.py | None (self-contained) |

## 22. Acceptance Tests (EARS)

### Happy Path

- WHEN a public user visits /intake THE SYSTEM SHALL display the intake form with all 11 fields
- WHEN a public user submits a valid intake form THE SYSTEM SHALL save the submission and redirect to /intake/thank-you
- WHEN an admin logs in with correct credentials THE SYSTEM SHALL set session['logged_in'] and redirect to /admin/
- WHEN an admin visits /admin/ THE SYSTEM SHALL display status counts for all submission statuses
- WHEN an admin visits /admin/submissions THE SYSTEM SHALL display all submissions ordered by created_at DESC
- WHEN an admin filters by status THE SYSTEM SHALL display only submissions matching that status
- WHEN an admin views a submission detail THE SYSTEM SHALL display all form fields, notes, assessment (if exists), and status controls
- WHEN an admin adds a note THE SYSTEM SHALL save the note and redirect to the detail page showing the new note
- WHEN an admin changes status to a non-terminal value THE SYSTEM SHALL update the status and redirect to detail
- WHEN an admin creates an assessment THE SYSTEM SHALL save it and redirect to detail showing assessment content
- WHEN an admin edits an assessment THE SYSTEM SHALL update it and redirect to detail
- WHEN an admin toggles audit-fit THE SYSTEM SHALL flip the is_audit_fit flag and redirect to detail

### Error Cases

- WHEN a public user submits a form with missing required fields THE SYSTEM SHALL flash an error and re-render the form
- WHEN a public user submits an invalid email THE SYSTEM SHALL flash 'Valid email is required' and re-render
- WHEN a bot fills the honeypot field THE SYSTEM SHALL silently redirect to thank-you without saving
- WHEN a public user exceeds 5 submissions per minute THE SYSTEM SHALL return 429
- WHEN an unauthenticated user visits /admin/* THE SYSTEM SHALL redirect to /login
- WHEN an admin enters wrong credentials THE SYSTEM SHALL flash 'Invalid credentials' and re-render login
- WHEN an admin tries to change status of a completed/declined/archived submission THE SYSTEM SHALL flash an error and not change the status
- WHEN an admin provides an invalid new_status value THE SYSTEM SHALL flash 'Invalid status' and redirect

### Verification Commands

```
cd intake-dashboard
.venv/bin/python test_smoke.py
```

## 23. Feed-Forward

- **Hardest decision:** Splitting submissions, detail, status, and assessments
  into 4 separate blueprints all sharing the /admin/submissions url_prefix.
  This is unusual but necessary for clean agent ownership boundaries. The
  alternative (one large blueprint) would make one agent too complex.
- **Rejected alternatives:** (1) Single admin blueprint -- too many routes for
  one agent. (2) Different URL prefixes (/admin/detail/<id>, /admin/assessments/<id>)
  -- less semantic, breaks RESTful sub-resource pattern. (3) Strict state machine
  enforcement -- over-engineered for single-admin manual workflow.
- **Least confident:** Route registration order with multiple blueprints on
  the same url_prefix. Flask registers routes by blueprint order, and if two
  blueprints define routes that could match the same URL pattern, the first
  registration wins. The current split has no overlapping routes, but review
  should verify no shadowing occurs.
