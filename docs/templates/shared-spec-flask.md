# Shared Interface Spec -- [App Name]

Use this template when writing a shared interface spec for a Flask swarm build.
Every section is mandatory. Agents rely on exact names, signatures, and examples.

## App Configuration

```python
# Secret key -- NEVER hardcode in production
import os
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback')

# CSRF protection -- required for all POST forms
from flask_wtf import CSRFProtect
csrf = CSRFProtect(app)
```

**Requirements:** Include `flask-wtf` in requirements.txt for CSRF support.

## Database Schema

```sql
-- Define all tables with explicit types and constraints
-- Include indexes on foreign key columns

CREATE TABLE IF NOT EXISTS [table] (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- columns...
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_[child]_[parent]_id ON [child]([parent]_id);
```

## Data Ownership

Define which module is the SOLE writer for each table. No two modules may
write to the same table.

| Table | Owner Module | Read By |
|-------|-------------|---------|
| [table] | [module].models | [list of readers] |

## Model Functions

For every function, include:
1. Full signature with type hints
2. Return type
3. **Usage example** (critical for scalar returns)

```python
# Returns: int (the new project's ID)
# Usage:
#   project_id = create_project(conn, name, color)
#   redirect(url_for('projects.detail', project_id=project_id))
def create_project(conn: sqlite3.Connection, name: str, color: str) -> int:
    ...

# Returns: sqlite3.Row or None
# Usage:
#   project = get_project(conn, project_id)
#   if project is None: abort(404)
#   return render_template('detail.html', project=project)
def get_project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    ...
```

**Rule:** Every function that returns a scalar (int, str, bool) MUST include
a usage example showing correct variable naming. Without this, agents assume
object returns and access `.id` on ints.

## Context Manager Usage

If using context managers for database connections:

```python
# Usage -- always use `with` syntax:
#   with get_db() as conn:
#       projects = get_all_projects(conn)
```

**Rule:** If `get_db` uses `@contextmanager`, include the `with` usage
example. Without it, agents write `conn = get_db()` (plain function call).

## Route Table

| Method | Path | Handler | Status | Template |
|--------|------|---------|--------|----------|
| GET | / | dashboard.index | 200 | dashboard/index.html |
| GET | /projects | projects.list | 200 | projects/list.html |
| POST | /projects | projects.create | 302 | redirect |

## Template Render Context

For every `render_template()` call, specify exact variable names:

```python
# dashboard/index.html expects:
render_template('dashboard/index.html',
    projects=get_all_projects(conn),
    stats=get_dashboard_stats(conn)
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

## Input Validation

Define validation rules inline with route specs:

```python
# Color: must be valid hex (#RRGGBB)
import re
COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
if not COLOR_RE.match(color):
    color = '#6366f1'  # default

# Name: strip whitespace, max 100 chars
name = request.form.get('name', '').strip()[:100]
if not name:
    flash('Name is required', 'error')
```

## Export Names Table

Every model function, endpoint name (`url_for` target), blueprint name, and
route path that crosses agent boundaries.

| Name | Type | Defined By | Used By |
|------|------|------------|---------|
| `create_item` | model function | `app/models.py` | `items` agent |
| `items.list` | endpoint | `app/blueprints/items/routes.py` | `layout` agent (navbar), `dashboard` agent (links) |

## Cross-Boundary Wiring Table

Every cross-module function call with producer file, consumer file, and import
path.

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `app/models.py` | `app/blueprints/items/routes.py` | `from app.models import create_item, get_all_items` |
| `app/db.py` | `app/blueprints/dashboard/routes.py` | `from app.db import get_db` |

## Input Validation Prescriptions

Every POST/PUT/PATCH/DELETE route and typed URL parameter with prescribed
validation and error response.

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| `POST /items` | `name` (form) | Strip whitespace, 1-100 chars, required | Flash "Name is required", redirect back |
| `DELETE /items/<int:item_id>` | `item_id` (URL) | Must exist in DB, must be owned by current user | `abort(404)` |

## Coordinated Behaviors

Behaviors that must be consistent across agents: blueprint registration, navbar
links, role maps, flash message patterns.

| Surface | Rule | Owner |
|---------|------|-------|
| Blueprint registration | All blueprints registered in `create_app()` with `url_prefix` | `core` agent |
| Navbar links | Every blueprint with user-facing routes gets a navbar entry in `base.html` | `layout` agent |
| CSRF token syntax | All POST forms use `{{ csrf_token() }}` (WITH parentheses) | ALL route agents |
| Session keys | `base.html` reads `session.get('logged_in')` -- must match auth agent's login key exactly | `auth` + `layout` agents |
| Timestamps | All timestamps use SQL `datetime('now')`, never Python `datetime.now()` | ALL model agents |

## Template Contracts

Cross-agent conventions for templates. These prevent FC1 at the template
layer, where agents produce HTML independently and the Export Names Table
doesn't cover template-level conventions.

### Session Keys

The auth agent sets session keys on login. Every other agent that reads
session state (base template, decorators, route handlers) must use the
EXACT same key names.

| Key | Set By | Read By | Example |
|-----|--------|---------|---------|
| `session['logged_in']` | auth agent (login route) | `login_required` decorator, `base.html` navbar | `session['logged_in'] = True` |

**Rule:** List every `session[...]` key in this table. If the layout
agent's `base.html` uses `session.get('user_id')` but the auth agent
sets `session['logged_in']`, the navbar breaks silently (renders empty
instead of crashing). This is a P0 that passes all HTTP 200 smoke tests.

### CSRF Token Syntax

All POST forms MUST use this exact syntax:

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

**Rule:** `csrf_token()` requires parentheses. `{{ csrf_token }}` (no
parens) renders the function object as a string, not the token value.
This produces a CSRF validation failure on every POST. Include this line
in the Coordinated Behaviors table.

### CSS Framework

| Item | Value |
|------|-------|
| Framework | Bootstrap 5.x (CDN with SRI integrity hash) |
| Custom CSS | `app/static/style.css` (layout agent owns) |
| Icons | (none unless specified) |

### Base Template Block Names

The layout agent defines these blocks in `base.html`. All other
template agents extend `base.html` and fill these blocks.

| Block | Purpose | Required? |
|-------|---------|-----------|
| `{% block title %}` | Page title in `<title>` tag | Yes |
| `{% block content %}` | Main page content | Yes |

## Transaction Contracts

Every model function that writes to the DB, annotated with commit behavior.

| Function | SQL | Commits |
|----------|-----|---------|
| `create_item(conn, name)` | `INSERT INTO items ...` | commits internally (`conn.commit()`) |
| `transfer_ownership(conn, item_id, new_owner_id)` | `UPDATE items ...` | does NOT commit (caller manages transaction) |

## Authorization Matrix

Every auth-protected route with access mode and ownership check.

| Route | Mode | Ownership Check |
|-------|------|-----------------|
| `GET /items` | public | N/A |
| `POST /items` | role-only (`user`) | N/A |
| `DELETE /items/<int:item_id>` | role+ownership | `item['user_id'] == current_user.id` |

## Smoke Test File (FC8 Compliance)

Smoke tests MUST be written to a file, never run as inline `python3 -c`.
Inline commands trigger security heuristics above `dangerouslySkipPermissions`.

**Prescribed pattern:**

1. Add `test_smoke.py` to `.gitignore`
2. Write all smoke tests to `test_smoke.py`:

```python
"""Smoke tests -- run with: .venv/bin/python test_smoke.py"""
import os
os.environ.setdefault("SECRET_KEY", "test-smoke-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-strong-pw-123")
os.environ.setdefault("FLASK_DEBUG", "1")

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

# --- Phase 1: HTTP status checks ---

r = client.get("/health")
check("GET /health (200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/login")
check("GET /login (200)", r.status_code == 200, f"got {r.status_code}")

# Unauthenticated access should redirect to login
r = client.get("/")
check("GET / (redirect to login)", r.status_code == 302, f"got {r.status_code}")

# --- Phase 2: Functional login + navigate ---
# This catches session key mismatches (P0 in Run 055) and CSRF issues
# that HTTP-200-only checks miss.

# Login with test client (bypass CSRF for test)
with client.session_transaction() as sess:
    sess['logged_in'] = True  # Must match the EXACT key from Session Keys table

# Dashboard should render (not redirect) when logged in
r = client.get("/")
check("GET / (dashboard, logged in)", r.status_code == 200, f"got {r.status_code}")

# Verify navbar renders with actual content (not empty/broken)
html = r.data.decode()
check("Dashboard has navbar links", "href=" in html and "Members" in html,
      "navbar may be empty or broken -- check session key in base.html")

# Check a protected list page renders
r = client.get("/members/")
check("GET /members/ (200)", r.status_code == 200, f"got {r.status_code}")

# --- Phase 3: Route-specific checks ---
# Add route-specific tests here...

# --- Summary ---
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
```

3. Run with: `.venv/bin/python test_smoke.py`

**Rules:**
- Load secrets via `os.environ.setdefault()` inside the script, NOT as
  command-line env prefixes (`SECRET_KEY=x python ...` triggers heuristics)
- No `#` comments that could be misread as argument hiding
- One `assert` per check with a descriptive failure message
- Phase 2 (functional login) is MANDATORY -- it catches session key
  mismatches and broken navbars that Phase 1 HTTP-200 checks miss
- The session key in `session_transaction()` MUST match the Session Keys
  table in Template Contracts -- this is the test that validates the
  cross-agent session contract

## File Assignment Boundaries

List all files and which agent owns them. No file appears in two agents.

| File | Agent |
|------|-------|
| app/__init__.py | core |
| app/models.py | core |
| app/blueprints/[name]/routes.py | [name] |
| app/templates/[name]/*.html | [name] |
| app/static/style.css | layout |
