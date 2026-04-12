---
title: "feat: Project Tracker -- 5-Agent Swarm Scale Test"
type: feat
status: active
date: 2026-04-12
swarm: true
origin: docs/brainstorms/2026-04-12-project-tracker-brainstorm.md
deepened: 2026-04-12
feed_forward:
  risk: "Whether the cross-module write pattern (log_activity called from 3 agents) works cleanly, and whether spec readability holds at 700+ lines with 5 agents"
  verify_first: true
---

# feat: Project Tracker -- 5-Agent Swarm Scale Test

Web-based project tracker with tasks, categories, team members, activity log,
and dashboard. Flask + SQLite + Jinja2. Primary goal: validate swarm pattern
at 5 agents (prior max was 4).

(see brainstorm: docs/brainstorms/2026-04-12-project-tracker-brainstorm.md)

## Acceptance Criteria

- [ ] CRUD tasks (title, description, status, due_date, category)
- [ ] CRUD categories (name, color)
- [ ] CRUD team members (name, role)
- [ ] Assign/remove members on task detail page
- [ ] Activity log auto-recorded on create/update/delete
- [ ] Dashboard: task counts by status, by category, recent activity, overdue
- [ ] CSRF on all POST forms, SECRET_KEY from env
- [ ] Input validation with flash messages
- [ ] All routes respond in smoke test

## File List

```
project-tracker/
  app.py                          # Flask app factory, get_db, close_db
  schema.sql                      # All CREATE TABLEs
  requirements.txt                # Flask, flask-wtf
  models/
    tasks.py                      # Task CRUD + task_members
    categories.py                 # Category CRUD
    members.py                    # Member CRUD
    activity.py                   # log_activity (write-only)
  routes/
    tasks.py                      # /tasks blueprint
    categories.py                 # /categories blueprint
    members.py                    # /members blueprint
    dashboard.py                  # / blueprint (dashboard + activity)
  templates/
    base.html                     # Shared layout with nav
    tasks/
      list.html                   # Task list
      detail.html                 # Task detail + assign members
      form.html                   # Create/edit task form
    categories/
      list.html                   # Category list with task counts
      detail.html                 # Category detail showing tasks
      form.html                   # Create/edit category form
    members/
      list.html                   # Member list with task counts
      detail.html                 # Member detail showing tasks
      form.html                   # Create/edit member form
    dashboard/
      index.html                  # Dashboard with stats + activity
  static/
    style.css                     # Basic styling
```

## Shared Interface Spec

### Database Schema

```sql
-- schema.sql
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#6366f1',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'done')),
    due_date TEXT,
    category_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS task_members (
    task_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    PRIMARY KEY (task_id, member_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('created', 'updated', 'deleted')),
    description TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_category_id ON tasks(category_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_task_members_member_id ON task_members(member_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_created_at ON activity_log(created_at);
```

**Key constraints:**
- `category_id` is NOT NULL -- a task must have a category
- No ON DELETE CASCADE from categories to tasks -- deletion is RESTRICTED at the application level (check for tasks before deleting)
- `task_members` uses composite PK, CASCADE on both FKs
- `members` deletion: CASCADE removes junction rows only, not tasks
- `status` uses CHECK constraint for enum values

### App Factory

```python
# app.py
import os
import sqlite3
from contextlib import contextmanager
from flask import Flask, g

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('project-tracker.db')
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-prod')
    app.teardown_appcontext(close_db)

    from flask_wtf import CSRFProtect
    CSRFProtect(app)

    with app.app_context():
        db = get_db()
        with open('schema.sql') as f:
            db.executescript(f.read())

    from routes.tasks import bp as tasks_bp
    from routes.categories import bp as categories_bp
    from routes.members import bp as members_bp
    from routes.dashboard import bp as dashboard_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tasks_bp, url_prefix='/tasks')
    app.register_blueprint(categories_bp, url_prefix='/categories')
    app.register_blueprint(members_bp, url_prefix='/members')

    return app

if __name__ == '__main__':
    create_app().run(debug=True)
```

**Rules:**
- `get_db()` returns `sqlite3.Connection` with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- `get_db()` is NOT a context manager. Call it directly: `db = get_db()`. Do NOT use `with get_db() as db:`.
- All routes import `get_db` from `app`: `from app import get_db`
- Blueprint URL prefixes: dashboard at `/`, tasks at `/tasks`, categories at `/categories`, members at `/members`
- Route files MUST use relative paths in their blueprint decorators (no prefix duplication)

### Data Ownership

| Table | Owner (writes) | Read By | Called By |
|-------|---------------|---------|-----------|
| tasks | models/tasks.py | routes/tasks.py, routes/dashboard.py, routes/categories.py, routes/members.py | — |
| categories | models/categories.py | routes/categories.py, routes/tasks.py, routes/dashboard.py | — |
| members | models/members.py | routes/members.py, routes/tasks.py, routes/dashboard.py | — |
| task_members | models/tasks.py | routes/tasks.py, routes/members.py, routes/dashboard.py | — |
| activity_log | models/activity.py | routes/dashboard.py | routes/tasks.py, routes/categories.py, routes/members.py |

**Cross-module write rule:** `log_activity()` is owned by models/activity.py but CALLED from task, category, and member routes. The calling route passes its existing `db` connection. `log_activity()` runs in the caller's transaction -- it does NOT call `get_db()` itself.

### Model Functions -- tasks (models/tasks.py)

```python
# All functions take db (sqlite3.Connection) as first arg

def get_all_tasks(db):
    """Returns: list[sqlite3.Row] -- all tasks with category name"""
    # JOIN categories to include category_name
    # ORDER BY created_at DESC

def get_task(db, task_id):
    """Returns: sqlite3.Row or None"""

def create_task(db, title, description, status, due_date, category_id):
    """Returns: int (new task ID)
    Usage:
        task_id = create_task(db, title, description, status, due_date, category_id)
        flash('Task created', 'success')
        return redirect(url_for('tasks.detail', task_id=task_id))
    """

def update_task(db, task_id, title, description, status, due_date, category_id):
    """Returns: None -- raises if not found
    Sets updated_at = datetime('now')
    """

def delete_task(db, task_id):
    """Returns: None -- CASCADE removes task_members rows"""

def get_task_members(db, task_id):
    """Returns: list[sqlite3.Row] -- members assigned to this task"""

def get_available_members(db, task_id):
    """Returns: list[sqlite3.Row] -- members NOT assigned to this task"""

def assign_member(db, task_id, member_id):
    """Returns: None -- INSERT OR IGNORE (idempotent)"""

def unassign_member(db, task_id, member_id):
    """Returns: None -- idempotent"""

def get_tasks_by_category(db, category_id):
    """Returns: list[sqlite3.Row] -- tasks in a category"""

def get_tasks_by_member(db, member_id):
    """Returns: list[sqlite3.Row] -- tasks assigned to a member"""

def count_tasks_by_status(db):
    """Returns: dict -- {'todo': N, 'in_progress': N, 'done': N}
    Usage:
        counts = count_tasks_by_status(db)
        # counts is a plain dict, NOT a Row
    """

def count_tasks_by_category(db):
    """Returns: list[sqlite3.Row] -- [{category_name, color, count}]"""

def get_overdue_tasks(db):
    """Returns: list[sqlite3.Row]
    Query: due_date IS NOT NULL AND due_date < date('now') AND status != 'done'
    ORDER BY due_date ASC
    """
```

### Model Functions -- categories (models/categories.py)

```python
def get_all_categories(db):
    """Returns: list[sqlite3.Row] -- all categories ordered by name"""

def get_category(db, category_id):
    """Returns: sqlite3.Row or None"""

def create_category(db, name, color):
    """Returns: int (new category ID)
    Usage:
        category_id = create_category(db, name, color)
        flash('Category created', 'success')
        return redirect(url_for('categories.list'))
    """

def update_category(db, category_id, name, color):
    """Returns: None"""

def delete_category(db, category_id):
    """Returns: None -- MUST check for tasks first
    Raises ValueError if category has tasks.
    Usage:
        try:
            delete_category(db, category_id)
            flash('Category deleted', 'success')
        except ValueError:
            flash('Cannot delete category with existing tasks', 'error')
    """

def category_has_tasks(db, category_id):
    """Returns: bool -- True if any tasks reference this category"""
```

### Model Functions -- members (models/members.py)

```python
def get_all_members(db):
    """Returns: list[sqlite3.Row] -- all members ordered by name"""

def get_member(db, member_id):
    """Returns: sqlite3.Row or None"""

def create_member(db, name, role):
    """Returns: int (new member ID)
    Usage:
        member_id = create_member(db, name, role)
        flash('Member added', 'success')
        return redirect(url_for('members.list'))
    """

def update_member(db, member_id, name, role):
    """Returns: None"""

def delete_member(db, member_id):
    """Returns: None -- CASCADE removes task_members rows"""

def count_tasks_for_member(db, member_id):
    """Returns: int
    Usage:
        task_count = count_tasks_for_member(db, member_id)
        # task_count is a plain int, NOT a Row
    """
```

### Model Functions -- activity (models/activity.py)

```python
def log_activity(db, entity_type, entity_id, action, description):
    """Write a single activity log entry. Called from other routes.

    Args:
        db: sqlite3.Connection -- the CALLER'S connection (same transaction)
        entity_type: str -- 'task', 'category', or 'member'
        entity_id: int -- the entity's ID
        action: str -- 'created', 'updated', or 'deleted'
        description: str -- human-readable, e.g. "Created task 'Fix login bug'"

    Returns: None (fire-and-forget, raises on failure)

    Usage (from a task route):
        db = get_db()
        task_id = create_task(db, title, description, status, due_date, category_id)
        log_activity(db, 'task', task_id, 'created', f"Created task '{title}'")
        db.commit()
    """

def get_recent_activity(db, limit=10):
    """Returns: list[sqlite3.Row] -- most recent activity entries
    ORDER BY created_at DESC LIMIT ?
    """
```

**CRITICAL:** `log_activity()` does NOT call `get_db()`. It uses the caller's `db` connection. The caller commits after both the entity write and the log write, making them atomic.

**Description format:** `"{Action} {entity_type} '{entity_name}'"` -- e.g.:
- `"Created task 'Fix login bug'"`
- `"Updated category 'Backend'"`
- `"Deleted member 'Alice'"`

### Route Table

| Method | Path | Handler | Blueprint | Status | Template/Redirect |
|--------|------|---------|-----------|--------|-------------------|
| GET | / | dashboard.index | dashboard | 200 | dashboard/index.html |
| GET | /tasks | tasks.list | tasks | 200 | tasks/list.html |
| GET | /tasks/new | tasks.new | tasks | 200 | tasks/form.html |
| POST | /tasks/new | tasks.create | tasks | 302 | redirect to tasks.detail |
| GET | /tasks/\<int:task_id\> | tasks.detail | tasks | 200 | tasks/detail.html |
| GET | /tasks/\<int:task_id\>/edit | tasks.edit_form | tasks | 200 | tasks/form.html |
| POST | /tasks/\<int:task_id\>/edit | tasks.edit | tasks | 302 | redirect to tasks.detail |
| POST | /tasks/\<int:task_id\>/delete | tasks.delete | tasks | 302 | redirect to tasks.list |
| POST | /tasks/\<int:task_id\>/assign | tasks.assign | tasks | 302 | redirect to tasks.detail |
| POST | /tasks/\<int:task_id\>/unassign | tasks.unassign | tasks | 302 | redirect to tasks.detail |
| GET | /categories | categories.list | categories | 200 | categories/list.html |
| GET | /categories/new | categories.new | categories | 200 | categories/form.html |
| POST | /categories/new | categories.create | categories | 302 | redirect to categories.list |
| GET | /categories/\<int:category_id\> | categories.detail | categories | 200 | categories/detail.html |
| GET | /categories/\<int:category_id\>/edit | categories.edit_form | categories | 200 | categories/form.html |
| POST | /categories/\<int:category_id\>/edit | categories.edit | categories | 302 | redirect to categories.detail |
| POST | /categories/\<int:category_id\>/delete | categories.delete | categories | 302 | redirect to categories.list |
| GET | /members | members.list | members | 200 | members/list.html |
| GET | /members/new | members.new | members | 200 | members/form.html |
| POST | /members/new | members.create | members | 302 | redirect to members.list |
| GET | /members/\<int:member_id\> | members.detail | members | 200 | members/detail.html |
| GET | /members/\<int:member_id\>/edit | members.edit_form | members | 200 | members/form.html |
| POST | /members/\<int:member_id\>/edit | members.edit | members | 302 | redirect to members.detail |
| POST | /members/\<int:member_id\>/delete | members.delete | members | 302 | redirect to members.list |

### Endpoint Registry

| Blueprint | Function | url_for Name | Method | Path |
|-----------|----------|-------------|--------|------|
| dashboard | index | dashboard.index | GET | / |
| tasks | list | tasks.list | GET | /tasks |
| tasks | new | tasks.new | GET | /tasks/new |
| tasks | create | tasks.create | POST | /tasks/new |
| tasks | detail | tasks.detail | GET | /tasks/\<task_id\> |
| tasks | edit_form | tasks.edit_form | GET | /tasks/\<task_id\>/edit |
| tasks | edit | tasks.edit | POST | /tasks/\<task_id\>/edit |
| tasks | delete | tasks.delete | POST | /tasks/\<task_id\>/delete |
| tasks | assign | tasks.assign | POST | /tasks/\<task_id\>/assign |
| tasks | unassign | tasks.unassign | POST | /tasks/\<task_id\>/unassign |
| categories | list | categories.list | GET | /categories |
| categories | new | categories.new | GET | /categories/new |
| categories | create | categories.create | POST | /categories/new |
| categories | detail | categories.detail | GET | /categories/\<category_id\> |
| categories | edit_form | categories.edit_form | GET | /categories/\<category_id\>/edit |
| categories | edit | categories.edit | POST | /categories/\<category_id\>/edit |
| categories | delete | categories.delete | POST | /categories/\<category_id\>/delete |
| members | list | members.list | GET | /members |
| members | new | members.new | GET | /members/new |
| members | create | members.create | POST | /members/new |
| members | detail | members.detail | GET | /members/\<member_id\> |
| members | edit_form | members.edit_form | GET | /members/\<member_id\>/edit |
| members | edit | members.edit | POST | /members/\<member_id\>/edit |
| members | delete | members.delete | POST | /members/\<member_id\>/delete |

**CRITICAL:** All routes use paths RELATIVE to the blueprint's url_prefix. The tasks blueprint is mounted at `/tasks`, so use `@bp.route('/new')` NOT `@bp.route('/tasks/new')`.

### Template Render Context

```python
# dashboard/index.html expects:
render_template('dashboard/index.html',
    status_counts=count_tasks_by_status(db),    # dict: {'todo': N, ...}
    category_counts=count_tasks_by_category(db), # list of Rows
    overdue_tasks=get_overdue_tasks(db),         # list of Rows
    recent_activity=get_recent_activity(db)       # list of Rows
)

# tasks/list.html expects:
render_template('tasks/list.html', tasks=get_all_tasks(db))

# tasks/detail.html expects:
render_template('tasks/detail.html',
    task=task,                                    # Row
    assigned=get_task_members(db, task_id),       # list of Rows
    available=get_available_members(db, task_id)  # list of Rows
)

# tasks/form.html expects:
render_template('tasks/form.html',
    task=task,                                    # Row or None (None = create)
    categories=get_all_categories(db)             # list of Rows (for dropdown)
)

# categories/list.html expects:
render_template('categories/list.html', categories=get_all_categories(db))

# categories/detail.html expects:
render_template('categories/detail.html',
    category=category,                            # Row
    tasks=get_tasks_by_category(db, category_id)  # list of Rows
)

# categories/form.html expects:
render_template('categories/form.html', category=category)  # Row or None

# members/list.html expects:
render_template('members/list.html', members=get_all_members(db))

# members/detail.html expects:
render_template('members/detail.html',
    member=member,                                # Row
    tasks=get_tasks_by_member(db, member_id)      # list of Rows
)

# members/form.html expects:
render_template('members/form.html', member=member)  # Row or None
```

### CSRF in Templates

Every POST form MUST include:
```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <!-- fields -->
</form>
```

### Input Validation Rules

```python
# Title/Name: strip, required, max 100 chars
name = request.form.get('name', '').strip()[:100]
if not name:
    flash('Name is required', 'error')
    return redirect(request.url)

# Color: must be valid hex (#RRGGBB), default if invalid
import re
COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
color = request.form.get('color', '#6366f1').strip()
if not COLOR_RE.match(color):
    color = '#6366f1'

# Status: must be valid enum
status = request.form.get('status', 'todo')
if status not in ('todo', 'in_progress', 'done'):
    status = 'todo'

# Due date: optional, must be YYYY-MM-DD if provided
due_date = request.form.get('due_date', '').strip() or None
if due_date:
    try:
        datetime.strptime(due_date, '%Y-%m-%d')
    except ValueError:
        due_date = None

# Category ID: must be valid integer
try:
    category_id = int(request.form.get('category_id', 0))
except (ValueError, TypeError):
    flash('Invalid category', 'error')
    return redirect(request.url)

# Member ID (for assign/unassign): must be valid integer
try:
    member_id = int(request.form.get('member_id', 0))
except (ValueError, TypeError):
    flash('Invalid member', 'error')
    return redirect(url_for('tasks.detail', task_id=task_id))
```

### Error Pattern

All routes use flash + redirect (POST/Redirect/GET):
```python
# On validation error:
flash('Name is required', 'error')
return redirect(request.url)

# On success:
flash('Task created', 'success')
return redirect(url_for('tasks.detail', task_id=task_id))

# On not found:
task = get_task(db, task_id)
if task is None:
    abort(404)
```

### Transaction Pattern

Entity writes and activity logging happen in one transaction:
```python
# Example: create task with activity log
db = get_db()
task_id = create_task(db, title, description, status, due_date, category_id)
log_activity(db, 'task', task_id, 'created', f"Created task '{title}'")
db.commit()
flash('Task created', 'success')
return redirect(url_for('tasks.detail', task_id=task_id))
```

**Rule:** `db.commit()` is called ONCE after both the entity write and `log_activity()`. This makes them atomic.

### CSS Classes

| Class | Element | Purpose |
|-------|---------|---------|
| `.container` | `<main>` | Max-width centered layout |
| `.nav` | `<nav>` | Top navigation |
| `.nav-link` | `<a>` in nav | Navigation links |
| `.nav-link.active` | Current page | Active nav highlight |
| `.card` | `<div>` | Dashboard stat card |
| `.card-grid` | `<div>` | Grid of stat cards |
| `.table` | `<table>` | Data tables |
| `.btn` | `<button/a>` | Button base |
| `.btn-primary` | Create buttons | Blue primary action |
| `.btn-danger` | Delete buttons | Red destructive action |
| `.btn-sm` | Small buttons | Compact inline buttons |
| `.flash` | `<div>` | Flash message |
| `.flash-success` | Success flash | Green |
| `.flash-error` | Error flash | Red |
| `.form-group` | `<div>` | Form field wrapper |
| `.form-control` | `<input/select/textarea>` | Form inputs |
| `.status-badge` | `<span>` | Task status pill |
| `.status-todo` | Todo badge | Gray |
| `.status-in_progress` | In progress badge | Blue |
| `.status-done` | Done badge | Green |
| `.color-dot` | `<span>` | Category color indicator |
| `.overdue` | `<tr>` | Overdue task row highlight |

### base.html Template Contract

```html
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Project Tracker{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <nav class="nav">
        <a class="nav-link" href="{{ url_for('dashboard.index') }}">Dashboard</a>
        <a class="nav-link" href="{{ url_for('tasks.list') }}">Tasks</a>
        <a class="nav-link" href="{{ url_for('categories.list') }}">Categories</a>
        <a class="nav-link" href="{{ url_for('members.list') }}">Members</a>
    </nav>
    <main class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        {% for category, message in messages %}
        <div class="flash flash-{{ category }}">{{ message }}</div>
        {% endfor %}
        {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Category delete | RESTRICT (app-level check) | Prevent accidental data loss. Flash error if tasks exist. |
| category_id nullable | NOT NULL | Tasks must have a category. Create category first. |
| log_activity transaction | Same connection, caller commits | Atomic -- both succeed or both roll back. |
| log_activity return | None | Fire-and-forget. Raises on failure (rolls back transaction). |
| Cascade log entries | One per top-level delete | Description notes cascade impact. |
| Description format | `"{Action} {type} '{name}'"` | Consistent across all 3 entity agents. |
| Overdue query | `due_date < date('now') AND status != 'done'` | Excludes done tasks and null due dates. |
| Error pattern | Flash + redirect (PRG) | Simple, no sticky forms. Consistent. |
| Assignment UX | On task detail page | Dropdown of available + remove buttons. |
| get_db() | Plain function, NOT context manager | Simpler for agents. `db = get_db()`, not `with`. |
| Agent count | 5 | Scale test target. Dashboard+activity combined for balance. |

## Plan Quality Gate

1. **What exactly is changing?** New `project-tracker/` directory with 23 files (app, schema, requirements, 4 model files, 4 route files, 10 template files, 1 CSS, 1 base template).
2. **What must not change?** No files outside `project-tracker/`. No changes to autopilot skill, agents, templates, or notes-api.
3. **How will we know it worked?** All 24 routes respond in smoke test. Activity log records entries. Dashboard shows correct counts.
4. **What is the most likely way this plan is wrong?** The cross-module write pattern (`log_activity()` called from 3 different agent-owned routes with a shared `db` connection) may cause import confusion or transaction issues. If an agent forgets `db.commit()` after `log_activity()`, activity entries silently disappear.

## Feed-Forward

- **Hardest decision:** Combining dashboard and activity log into one agent. This creates the largest read surface (reads from all 5 tables) but keeps agent count at 5 and gives the agent a clear write domain (activity_log).
- **Rejected alternatives:** (1) 6 agents with separate dashboard -- too few files per dashboard agent. (2) Activity log as middleware -- too implicit for a swarm spec. (3) Each agent logs its own activity -- violates data ownership (3 writers to activity_log).
- **Least confident:** Whether the 700+ line spec remains readable for agents. Prior max was 584 lines (4 agents). The spec includes model functions, route table, endpoint registry, template render context, and CSS classes. If agents lose coherence on long specs, the fix is to extract the spec sections relevant to each agent and include only those in their prompt.

## Swarm Agent Assignment

**Total agents:** 5
**Total files:** 23
**Validation:** No file appears in multiple assignments

### Validation Checks

| Check | Result |
|-------|--------|
| File count matches file list | 23 / 23 |
| Duplicate file assignments | None found |
| All files covered | Yes |
| Data ownership boundaries respected | Yes |
| Cross-module write pattern (log_activity) | Correct -- `models/activity.py` owned by `dashboard-activity`; task/category/member route agents call `log_activity()` as an import, pass their own `db`, commit once after both writes |
| Agents within target range (2-5) | Yes (5 agents) |

---

### Agent: core

**Files:**
- `project-tracker/app.py`
- `project-tracker/schema.sql`
- `project-tracker/requirements.txt`
- `project-tracker/templates/base.html`
- `project-tracker/static/style.css`

**Responsibility:** App factory, database schema, base template with nav, CSS, and requirements. Produces the foundation all other agents depend on. Does not create any model or route files.

**Shared Interface Spec:** See the full `## Shared Interface Spec` section above (Database Schema, App Factory, Data Ownership, Model Functions, Route Table, Endpoint Registry, Template Render Context, Input Validation, Transaction Pattern, CSS Classes, base.html Template Contract). That section is your coordination contract with the other four agents.

---

### Agent: tasks

**Files:**
- `project-tracker/models/tasks.py`
- `project-tracker/routes/tasks.py`
- `project-tracker/templates/tasks/list.html`
- `project-tracker/templates/tasks/detail.html`
- `project-tracker/templates/tasks/form.html`

**Responsibility:** Task CRUD model functions + task_members writes, all `/tasks` routes (including assign/unassign), and all task templates. Calls `log_activity()` imported from `models.activity` after every entity write; passes its own `db` and calls `db.commit()` once after both writes. Route paths are RELATIVE to the `/tasks` prefix.

**Cross-module write note:** Import `log_activity` from `models.activity`. Call pattern:
```python
from models.activity import log_activity
db = get_db()
task_id = create_task(db, ...)
log_activity(db, 'task', task_id, 'created', f"Created task '{title}'")
db.commit()
```
Do NOT call `get_db()` inside `log_activity`. Do NOT commit before `log_activity`.

**Shared Interface Spec:** See the full `## Shared Interface Spec` section above. That section is your coordination contract with the other four agents.

---

### Agent: categories

**Files:**
- `project-tracker/models/categories.py`
- `project-tracker/routes/categories.py`
- `project-tracker/templates/categories/list.html`
- `project-tracker/templates/categories/detail.html`
- `project-tracker/templates/categories/form.html`

**Responsibility:** Category CRUD model functions, all `/categories` routes, and all category templates. Calls `log_activity()` imported from `models.activity` after every entity write. Imports `get_tasks_by_category` from `models.tasks` for the detail page (read-only -- does not write to tasks). Route paths are RELATIVE to the `/categories` prefix.

**Cross-module write note:** Same `log_activity` pattern as the tasks agent -- pass your `db`, commit once after both writes.

**Shared Interface Spec:** See the full `## Shared Interface Spec` section above. That section is your coordination contract with the other four agents.

---

### Agent: members

**Files:**
- `project-tracker/models/members.py`
- `project-tracker/routes/members.py`
- `project-tracker/templates/members/list.html`
- `project-tracker/templates/members/detail.html`
- `project-tracker/templates/members/form.html`

**Responsibility:** Member CRUD model functions, all `/members` routes, and all member templates. Calls `log_activity()` imported from `models.activity` after every entity write. Imports `get_tasks_by_member` from `models.tasks` for the detail page (read-only -- does not write to tasks). Route paths are RELATIVE to the `/members` prefix.

**Cross-module write note:** Same `log_activity` pattern as the tasks agent -- pass your `db`, commit once after both writes.

**Shared Interface Spec:** See the full `## Shared Interface Spec` section above. That section is your coordination contract with the other four agents.

---

### Agent: dashboard-activity

**Files:**
- `project-tracker/models/activity.py`
- `project-tracker/routes/dashboard.py`
- `project-tracker/templates/dashboard/index.html`

**Responsibility:** Activity log model (`log_activity` + `get_recent_activity`), dashboard route at `/`, and dashboard template. Owns the only writer to `activity_log`. Imports task model functions for aggregate queries (`count_tasks_by_status`, `count_tasks_by_category`, `get_overdue_tasks`) -- read-only, does not modify files owned by other agents.

**Cross-module write note:** `log_activity()` in `models/activity.py` MUST NOT call `get_db()`. It receives `db` as its first argument from the caller. The caller (task/category/member route) owns the transaction and calls `db.commit()`.

**Shared Interface Spec:** See the full `## Shared Interface Spec` section above. That section is your coordination contract with the other four agents.

---

STATUS: PASS

---

## Enhancement Summary (Deepened 2026-04-12)

**Research agents used:** 7 (solutions-reader, kieran-python-reviewer, security-sentinel, architecture-strategist, performance-oracle, data-integrity-guardian, pattern-recognition-specialist)
**Sections enhanced:** 6 (File List, Schema, Transaction Pattern, Input Validation, Design Decisions, Scaling Notes)
**Findings:** 28 total (3 blocker/high, 8 medium, 11 low, 6 informational)

### Key Improvements

1. **Missing `__init__.py` files (BLOCKER)** -- `models/` and `routes/` need empty `__init__.py` files or all cross-module imports fail. Add to core agent.
2. **Template safety rule** -- 5 agents writing templates independently need an explicit "Never use `| safe` or `Markup()`" rule to prevent stored XSS.
3. **Transaction error handling** -- The write+log+commit block needs explicit `try/except/rollback` or an explicit "do NOT catch exceptions from log_activity" rule.

### Research Insights by Domain

#### Python / Flask (kieran-python-reviewer)

**Blockers:**
- Add `project-tracker/models/__init__.py` and `project-tracker/routes/__init__.py` to core agent file list (empty files). Without these, `from models.activity import log_activity` fails with `ModuleNotFoundError`.
- `schema.sql` path is relative -- breaks if app is run from parent directory. Use `Path(__file__).parent / 'schema.sql'` in production; acceptable as-is for sandbox.
- Unused `contextmanager` import in app factory spec (line 138) -- remove to prevent agents from copying dead code.

**Recommendations:**
- Add type hints to model function signatures in spec (e.g., `def log_activity(db: sqlite3.Connection, ...) -> None`). Agents copy what the spec shows.
- Note that `flask-wtf` is used solely for `CSRFProtect`, not WTForms form classes, to prevent agents from creating `FlaskForm` subclasses.

#### Security (security-sentinel)

**High:**
- SECRET_KEY hardcoded fallback (`'dev-key-change-in-prod'`) teaches bad pattern. For sandbox: acceptable but add to Design Decisions as intentional. For reuse: fail loudly if `SECRET_KEY` not set outside debug mode.

**Medium:**
- No explicit Jinja2 `| safe` filter ban. Add to Shared Interface Spec: "Never use the `| safe` filter or `Markup()` in any template. Jinja2 autoescapes by default."
- `description` field has no max length -- add `[:2000]` truncation matching the title/name pattern.
- No security headers (X-Content-Type-Options, X-Frame-Options, CSP) -- low priority for local app.

**Low:**
- CSRF failure shows raw 400 page (no custom error handler).
- `debug=True` is on by default (expected for sandbox).
- No rate limiting (irrelevant for local app).
- Invalid `category_id` causes unhandled `IntegrityError` instead of flash message.

#### Architecture (architecture-strategist)

**Positive:**
- Data ownership model is sound. Cross-module write pattern is the strongest part of the plan.
- Hard rule validated: max 1 cross-module write function per swarm build.

**Medium:**
- `log_activity()` exception behavior must be explicit. Add to spec: "Do NOT catch exceptions from `log_activity()`. If it raises, the transaction rolls back. This is intentional."
- Route table and endpoint registry overlap (~50 lines). Acceptable at 5 agents; consolidate at 7+.

**Scaling notes:**
- `models/tasks.py` is read dependency for 3/4 non-core agents (star topology). At 8+ agents, consider splitting into query modules.
- Spec scales to ~8-10 agents before needing per-agent extraction. Feed-Forward already proposes the correct fix.
- Cross-module write count should remain at 1. If a 2nd appears, reconsider agent boundaries.

#### Performance (performance-oracle)

**P1:**
- Add composite index: `CREATE INDEX IF NOT EXISTS idx_tasks_due_date_status ON tasks(due_date, status);` -- prevents full table scan on dashboard overdue query.

**P2:**
- N+1 risk on members list: `count_tasks_for_member(db, member_id)` called per-row. Add `get_all_members_with_task_counts(db)` using LEFT JOIN + GROUP BY.
- Same risk on categories list. Plan should state list pages use aggregate queries, not per-row lookups.

**P3:**
- No pagination on any list page. Tasks most likely to grow. Not a blocker for sandbox.
- Activity log grows unbounded. Add note about retention policy for production use.
- Dashboard 4-query pattern is acceptable for SQLite (in-process, no network RTT).

#### Data Integrity (data-integrity-guardian)

**P1:**
- No explicit `try/except/rollback` around write+log+commit. If `log_activity()` raises, route crashes with 500. Add error handling pattern to spec.
- No schema migration strategy. `CREATE TABLE IF NOT EXISTS` silently skips column additions. Acceptable for sandbox; document as known limitation.

**P2:**
- `activity_log.entity_id` becomes orphaned on entity deletion (no FK back to polymorphic tables). Document as known limitation.
- No CHECK constraint on `activity_log.entity_type`. Add `CHECK(entity_type IN ('task', 'category', 'member'))`.
- Member deletion silently removes task assignments via CASCADE with no audit trail. Consider logging affected count.
- No duplicate protection on activity log entries (append-only, no dedup).

**P3:**
- `executescript` is not atomic (each statement commits independently). Safe for IF NOT EXISTS.
- TOCTOU race on category deletion is safe only because SQLite single-writer. Would break on Postgres.

#### Pattern Recognition (pattern-recognition-specialist)

**Strong adherence:** All 7 prior build lessons correctly applied (scalar returns, endpoint registry, composite PK, route prefix doubling, context manager clarity, CSRF+flash+PRG, spec template compliance).

**New pattern to document:** Cross-module write via shared function (`log_activity`) is genuinely novel. Rules for the pattern:
1. Function MUST live in the owning module
2. Function MUST accept `db` as first argument (never call `get_db()` internally)
3. Caller MUST commit after calling the function
4. Data ownership table MUST have "Called By" column

**Minor observations:**
- `list` as route handler name shadows Python built-in (internally consistent across blueprints)
- `dashboard-activity` agent name breaks single-word naming convention (code-level: no impact)

### Recommended Fix Order (Plan-Level)

| # | Issue | Priority | Why this order | Agent findings |
|---|-------|----------|---------------|----------------|
| 1 | Add `__init__.py` files to file list | Blocker | All cross-module imports fail without these | Python, Architecture, Pattern |
| 2 | Add template safety rule (no `\| safe`) | High | 5 agents writing templates = XSS risk if any one uses it | Security |
| 3 | Clarify `log_activity()` exception behavior | High | Prevents agents from breaking atomicity with try/except | Architecture, Data Integrity |
| 4 | Add composite index on tasks(due_date, status) | Medium | Dashboard full table scan on every load | Performance |
| 5 | Add description/role max length to validation | Medium | Unbounded text fields | Security |
| 6 | Add CHECK on activity_log.entity_type | Medium | Catches typos at DB level | Data Integrity |
| 7 | Document SECRET_KEY fallback as intentional | Low | Pattern reuse concern | Security |
| 8 | Add aggregate query for members list | Low | N+1 prevention | Performance |
| 9 | Remove unused contextmanager import from spec | Low | Prevents agent copy-paste of dead code | Python |
| 10 | Document orphaned activity_log entries as known limitation | Low | Data governance awareness | Data Integrity |

### Items NOT Changed (Out of Scope for Sandbox)

- No migration strategy added (sandbox uses fresh DBs)
- No pagination added (acceptance criteria don't require large datasets)
- No security headers added (local-only app)
- No rate limiting added (local-only app)
- No type hints added to spec (would inflate 728-line spec further)
- No activity log retention policy (not needed at sandbox scale)

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-04-12-project-tracker-brainstorm.md](docs/brainstorms/2026-04-12-project-tracker-brainstorm.md) -- 5 agents, cross-module writes, scale test
- **Spec template:** [docs/templates/shared-spec-flask.md](docs/templates/shared-spec-flask.md)
- **Prior lessons:** task-tracker-categories (scalar returns, 4-agent Flask), flask-swarm-acid-test (context manager, spec size), recipe-organizer (composite PK, junction tables), bookmark-manager (endpoint registry, YAGNI), personal-finance-tracker (route prefix doubling), autopilot-swarm-orchestration (verification pipeline), notes-api (stack-agnostic validation)
