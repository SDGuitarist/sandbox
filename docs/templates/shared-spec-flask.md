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

## File Assignment Boundaries

List all files and which agent owns them. No file appears in two agents.

| File | Agent |
|------|-------|
| app/__init__.py | core |
| app/models.py | core |
| app/blueprints/[name]/routes.py | [name] |
| app/templates/[name]/*.html | [name] |
| app/static/style.css | layout |
