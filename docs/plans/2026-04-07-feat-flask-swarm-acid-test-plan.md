---
title: "feat: Flask Swarm Acid Test — Task Tracker"
type: feat
status: active
date: 2026-04-07
origin: docs/brainstorms/2026-04-07-flask-swarm-acid-test.md
feed_forward:
  risk: "Python imports between blueprints may cause mismatches that CSS class/ID matching in JS didn't — agents must agree on import paths, function signatures, blueprint variable names, AND Jinja block names"
  verify_first: true
---

# feat: Flask Swarm Acid Test — Task Tracker

## Enhancement Summary

**Deepened on:** 2026-04-07
**Revised on:** 2026-04-07 (Codex Plan Review + Claude Code rev-4 fixes applied)
**Sections enhanced:** 6 (+ comment removal, get_db contract, routing reconciliation, verification upgrade)
**Research agents used:** architecture-strategist, security-sentinel, code-simplicity-reviewer, best-practices-researcher, solution-doc-searcher, Context7 Flask docs

### Deepening Improvements
1. Added `updated_at` handling to all update model functions (architecture review)
2. Added `app.secret_key` and flash message support (security review)
3. Added input validation contract and `executescript()` gotcha (solution docs)
4. Removed unused `extra_css` template block (simplicity review)

### Codex Plan Review Fixes (5 items)
1. Added Section 8: Template Render Context — exact `render_template()` variables for every route/template pair
2. Fixed `get_dashboard_stats` to include project summaries with task counts (dashboard scope mismatch)
3. Added Checkpoint 7: Spec-vs-Code Audit with explicit grep commands for blueprint names, template blocks, render context, and run.py
4. Added Section 9: run.py Contract — exact file content, app discovery method, verification command
5. Shared constants injection pattern defined (how STATUS_LABELS etc. reach templates)

## Overview

Build a Task Tracker Flask app using 4 parallel agents coordinated by a shared
interface spec. This is the acid test before archiving sandbox-auto: if the
shared spec pattern produces 0 mismatches in Python/Flask (as it did in JS),
the pattern is stack-agnostic and sandbox-auto can be archived.

(see brainstorm: docs/brainstorms/2026-04-07-flask-swarm-acid-test.md)

## Plan Quality Gate

1. **What exactly is changing?** A new `task-tracker/` directory with a Flask app
   built by 4 parallel agents. No existing code is modified.
2. **What must not change?** All other apps in the sandbox repo. No modifications
   to docs/solutions/ or existing plans.
3. **How will we know it worked?** 6 acceptance checkpoints all green (see
   Acceptance Criteria). Primary metric: interface mismatch count = 0.
4. **What is the most likely way this plan is wrong?** The shared spec may not
   capture Python-specific integration surfaces (circular imports, blueprint
   registration order, Jinja block name mismatches that fail silently). The
   Feed-Forward risk from the brainstorm.

## Proposed Solution

Each agent receives the Shared Interface Spec (below) as its only input and
builds its assigned files independently. After all 4 agents complete, their
output is assembled and verified against the 6 acceptance checkpoints.

### Directory Structure

```
task-tracker/
  run.py
  requirements.txt
  app/
    __init__.py          (Agent 1)
    models.py            (Agent 1)
    db.py                (Agent 1)
    schema.sql           (Agent 1)
    static/
      style.css          (Agent 4)
    templates/
      layout.html        (Agent 4)
      dashboard/
        index.html       (Agent 4)
      projects/
        list.html        (Agent 2)
        detail.html      (Agent 2)
        form.html        (Agent 2)
      tasks/
        detail.html      (Agent 3)
        form.html        (Agent 3)
    blueprints/
      projects/
        __init__.py      (Agent 2)
        routes.py        (Agent 2)
      tasks/
        __init__.py      (Agent 3)
        routes.py        (Agent 3)
      dashboard/
        __init__.py      (Agent 4)
        routes.py        (Agent 4)
```

---

## Shared Interface Spec

This is the single source of truth for all 4 agents. Every agent reads this
spec and follows it exactly. No agent reads another agent's code.

### 1. Public Function Signatures

#### db.py (Agent 1)

| Function | Signature | Returns | Called by |
|----------|-----------|---------|-----------|
| `get_db` | `@contextmanager` / `get_db(immediate=False)` | yields `sqlite3.Connection` (row_factory=Row) | All blueprints |
| `init_db` | `init_db(app)` | None (uses raw connection, NOT `get_db()`) | `app/__init__.py` |

#### models.py (Agent 1)

| Function | Signature | Returns | Called by |
|----------|-----------|---------|-----------|
| `get_all_projects` | `get_all_projects(conn)` | `list[sqlite3.Row]` | Dashboard, Projects |
| `get_project` | `get_project(conn, project_id)` | `sqlite3.Row` or `None` | Projects, Tasks |
| `create_project` | `create_project(conn, name, description)` | `int` (new id) | Projects |
| `update_project` | `update_project(conn, project_id, name, description)` | `None` (sets `updated_at`) | Projects |
| `delete_project` | `delete_project(conn, project_id)` | `None` | Projects |
| `get_tasks_for_project` | `get_tasks_for_project(conn, project_id)` | `list[sqlite3.Row]` | Projects, Tasks |
| `get_task` | `get_task(conn, task_id)` | `sqlite3.Row` or `None` | Tasks |
| `create_task` | `create_task(conn, project_id, title, description, priority)` | `int` (new id) | Tasks |
| `update_task` | `update_task(conn, task_id, title, description, status, priority)` | `None` (sets `updated_at`) | Tasks |
| `delete_task` | `delete_task(conn, task_id)` | `None` | Tasks |
| `get_dashboard_stats` | `get_dashboard_stats(conn)` | `dict` (see below) | Dashboard |

`get_dashboard_stats` returns:
```python
{
    "total_projects": int,
    "total_tasks": int,
    "tasks_by_status": {"todo": int, "in_progress": int, "done": int},
    "recent_tasks": list[sqlite3.Row],  # 5 most recent, columns: id, title, status, project_name, created_at
    "projects": list[sqlite3.Row]       # all projects with task counts, columns: id, name, task_count, done_count
}
```

`recent_tasks` SQL (joined with project name):
```sql
SELECT t.id, t.title, t.status, p.name AS project_name, t.created_at
FROM tasks t JOIN projects p ON t.project_id = p.id
ORDER BY t.created_at DESC LIMIT 5
```

`projects` SQL (with task counts):
```sql
SELECT p.id, p.name,
       COUNT(t.id) AS task_count,
       SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count
FROM projects p LEFT JOIN tasks t ON t.project_id = p.id
GROUP BY p.id, p.name ORDER BY p.name
```

All model functions receive a `conn` parameter (the sqlite3.Connection from
`get_db()`). They do NOT call `get_db()` themselves.

#### get_db() Usage Contract

`get_db()` is a context manager. **Never** assign it directly (`conn = get_db()` is wrong). Always use `with`:

**Read-only operations** (GET routes):
```python
with get_db() as conn:
    project = get_project(conn, project_id)
```

**Write operations** (POST routes — create, update, delete):
```python
with get_db(immediate=True) as conn:
    create_project(conn, name, description)
```

`immediate=True` acquires a `BEGIN IMMEDIATE` lock, preventing concurrent write conflicts in SQLite. Every POST handler must use `immediate=True`. Every GET handler uses the default `immediate=False`.

**Anti-pattern (will break):**
```python
# WRONG — get_db() returns a context manager, not a connection
conn = get_db()
project = get_project(conn, project_id)
```

### 2. Database Schema

```sql
-- schema.sql (Agent 1 writes this file)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo', 'in_progress', 'done')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

```

**FK semantics:** `ON DELETE CASCADE` on `tasks.project_id`. Deleting a project
cascades to its tasks.

**Status enum values:** `'todo'`, `'in_progress'`, `'done'` (enforced by CHECK constraint).

**Priority enum values:** `'low'`, `'medium'`, `'high'` (enforced by CHECK constraint).

### 3. Shared Constants

| Constant | Value | Defined in | Used by | Purpose |
|----------|-------|-----------|---------|---------|
| `TASK_STATUSES` | `['todo', 'in_progress', 'done']` | `models.py` | Tasks, Dashboard | Status dropdown options |
| `TASK_PRIORITIES` | `['low', 'medium', 'high']` | `models.py` | Tasks | Priority dropdown options |
| `STATUS_LABELS` | `{'todo': 'To Do', 'in_progress': 'In Progress', 'done': 'Done'}` | `models.py` | Tasks, Dashboard, Projects | Display labels for status values |
| `PRIORITY_LABELS` | `{'low': 'Low', 'medium': 'Medium', 'high': 'High'}` | `models.py` | Tasks | Display labels for priority values |
| `DB_NAME` | `'task_tracker.db'` | `db.py` | `__init__.py` | Default database filename |

### 4. Flask Routes

| Method | Path | Blueprint | Handler | Returns |
|--------|------|-----------|---------|---------|
| GET | `/` | dashboard | `index()` | Renders `dashboard/index.html` with stats |
| GET | `/projects/` | projects | `list_projects()` | Renders `projects/list.html` |
| GET | `/projects/<int:project_id>` | projects | `show_project(project_id)` | Renders `projects/detail.html` with tasks |
| GET | `/projects/new` | projects | `new_project()` | Renders `projects/form.html` (empty) |
| POST | `/projects/` | projects | `create_project_route()` | Redirects to `/projects/<id>` |
| GET | `/projects/<int:project_id>/edit` | projects | `edit_project(project_id)` | Renders `projects/form.html` (filled) |
| POST | `/projects/<int:project_id>` | projects | `update_project_route(project_id)` | Redirects to `/projects/<id>` |
| POST | `/projects/<int:project_id>/delete` | projects | `delete_project_route(project_id)` | Redirects to `/projects/` |
| GET | `/tasks/<int:task_id>` | tasks | `show_task(task_id)` | Renders `tasks/detail.html` |
| GET | `/projects/<int:project_id>/tasks/new` | tasks | `new_task(project_id)` | Renders `tasks/form.html` (empty) |
| POST | `/projects/<int:project_id>/tasks` | tasks | `create_task_route(project_id)` | Redirects to `/tasks/<id>` |
| GET | `/tasks/<int:task_id>/edit` | tasks | `edit_task(task_id)` | Renders `tasks/form.html` (filled) |
| POST | `/tasks/<int:task_id>` | tasks | `update_task_route(task_id)` | Redirects to `/tasks/<id>` |
| POST | `/tasks/<int:task_id>/delete` | tasks | `delete_task_route(task_id)` | Redirects to project detail |

**Route ownership:** Tasks blueprint owns `/tasks/*` routes AND the nested
`/projects/<pid>/tasks/new` and `/projects/<pid>/tasks` (POST) routes for
creating tasks within a project. This avoids cross-blueprint route conflicts.

**Routing contract:**
- **Projects blueprint** is registered with `url_prefix='/projects'`. All
  project routes use **relative** route rules (e.g., `@projects_bp.route('/')`
  resolves to `/projects/`). Flask's trailing-slash behavior: `@bp.route('/')`
  with `url_prefix='/projects'` makes the canonical URL `/projects/` (trailing
  slash). Flask auto-redirects `GET /projects` → `/projects/` with a 308.
  `url_for('projects.list_projects')` returns `/projects/`.
- **Tasks blueprint** has no `url_prefix`. All task routes use **absolute** rules
  (e.g., `@tasks_bp.route('/tasks/<int:task_id>')`).
- **Dashboard blueprint** has no `url_prefix`. Single absolute route `'/'`.

**Projects route-rule examples** (relative, because `url_prefix='/projects'`):
```python
@projects_bp.route('/')                                    # → /projects/ (canonical)
@projects_bp.route('/<int:project_id>')                    # → /projects/<id>
@projects_bp.route('/new')                                 # → /projects/new
@projects_bp.route('/', methods=['POST'])                  # → POST /projects/
@projects_bp.route('/<int:project_id>/edit')               # → /projects/<id>/edit
@projects_bp.route('/<int:project_id>', methods=['POST'])  # → POST /projects/<id>
@projects_bp.route('/<int:project_id>/delete', methods=['POST'])  # → POST /projects/<id>/delete
```

### 5. Data Ownership

| Table | Writer (single owner) | Readers |
|-------|----------------------|---------|
| `projects` | Projects blueprint | Dashboard, Tasks (to show project name) |
| `tasks` | Tasks blueprint | Dashboard (stats + recent), Projects (task list on detail) |

**Rule:** Only the writer calls `create_*`, `update_*`, `delete_*` model
functions for its table. Readers only call `get_*` functions.

### 6. Jinja Template Blocks

**`layout.html` (Agent 4) defines these blocks:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Task Tracker{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <nav>
        <a href="{{ url_for('dashboard.index') }}">Dashboard</a>
        <a href="{{ url_for('projects.list_projects') }}">Projects</a>
    </nav>
    <main>
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

**All blueprint templates MUST:**
- Start with `{% extends "layout.html" %}`
- Override `{% block title %}Page Name - Task Tracker{% endblock %}`
- Put all content inside `{% block content %}...{% endblock %}`
- Use `url_for()` for ALL links (never hardcode paths)

**url_for patterns:**
- `url_for('dashboard.index')` → `/`
- `url_for('projects.list_projects')` → `/projects/`
- `url_for('projects.show_project', project_id=p.id)` → `/projects/<id>`
- `url_for('tasks.show_task', task_id=t.id)` → `/tasks/<id>`
- `url_for('tasks.new_task', project_id=p.id)` → `/projects/<id>/tasks/new`

### 7. Implicit Contracts

- **Timestamp format:** `'%Y-%m-%d %H:%M:%S'` (SQLite `strftime` compatible)
- **SQLite connection setup:** WAL mode, `foreign_keys=ON`, `timeout=10`,
  `row_factory=sqlite3.Row`
- **Transaction semantics:** Use `get_db(immediate=True)` for any write
  operation. Read-only operations use `get_db()` (default `immediate=False`).
- **404 handling:** If `get_project()` or `get_task()` returns `None`, the
  route handler calls `abort(404)`.
- **Authentication:** Out of scope. No auth, no users, no sessions.
  This is intentional for the acid test.
- **Input validation:** All required fields (name, title, content) must be
  stripped of whitespace and rejected if empty. Use `request.form.get('field', '').strip()`.
  Return the form with an error message (via `flash()`) if validation fails.
- **Flash messages:** Use `flash('message', 'category')` for success/error
  feedback. Templates must include `get_flashed_messages(with_categories=true)`
  in `layout.html`.
- **updated_at handling:** All `update_*` functions must explicitly set
  `updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now')` in their UPDATE
  statements. The DEFAULT expression only fires on INSERT.
- **Form data:** All form submissions use standard HTML forms with POST method.
  Access via `request.form.get('field', '').strip()`.
- **SQL injection prevention:** All queries use parameterized `?` placeholders,
  never string formatting. Example: `conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))`
- **XSS prevention:** Jinja2 auto-escapes by default. Do not use `|safe` filter
  on user-provided content.
- **Status transitions:** Free-form. Any status can change to any other status
  via the edit form. No enforced state machine.
- **Redirects after writes:** All POST handlers redirect (POST-Redirect-GET
  pattern) using `redirect(url_for(...))`.
- **Form field `name` attributes:** Must match the parameter names in model
  functions. Projects form: `name="name"`, `name="description"`. Tasks form:
  `name="title"`, `name="description"`, `name="status"`, `name="priority"`.
  Never use prefixed names like `project_name`.
- **XSS template rules:** All HTML attributes with template variables MUST use
  double quotes. Never use `|safe`, `Markup()`, or `{% autoescape false %}`.
  For multi-line text, use CSS `white-space: pre-wrap` instead of `<br>|safe`.
- **Import pattern:** All blueprints import from `app.db` and `app.models`:
  ```python
  from app.db import get_db
  from app.models import get_project, get_tasks_for_project  # etc.
  ```

### 8. Template Render Context

Every `render_template()` call must pass exactly these variables. No agent
may invent variable names — they are fixed by this spec.

**Shared constants injection:** All blueprints that render templates with
status or priority displays must import and pass the relevant constants.
The pattern is:

```python
from app.models import STATUS_LABELS, TASK_STATUSES, TASK_PRIORITIES, PRIORITY_LABELS
```

#### dashboard/index.html (Agent 4)

```python
# In dashboard/routes.py → index()
return render_template('dashboard/index.html',
    stats=stats  # dict from get_dashboard_stats()
)
```

Template accesses: `stats.total_projects`, `stats.total_tasks`,
`stats.tasks_by_status.todo`, `stats.tasks_by_status.in_progress`,
`stats.tasks_by_status.done`, `stats.recent_tasks` (loop: `t.id`,
`t.title`, `t.status`, `t.project_name`, `t.created_at`),
`stats.projects` (loop: `p.id`, `p.name`, `p.task_count`, `p.done_count`).

Also pass: `STATUS_LABELS` (for displaying status badges on recent tasks).

```python
return render_template('dashboard/index.html',
    stats=stats,
    STATUS_LABELS=STATUS_LABELS
)
```

#### projects/list.html (Agent 2)

```python
# In projects/routes.py → list_projects()
return render_template('projects/list.html',
    projects=projects  # list[sqlite3.Row] from get_all_projects()
)
```

Template accesses: loop over `projects` — each row: `p.id`, `p.name`,
`p.description`, `p.created_at`.

#### projects/detail.html (Agent 2)

```python
# In projects/routes.py → show_project(project_id)
return render_template('projects/detail.html',
    project=project,   # sqlite3.Row from get_project()
    tasks=tasks,        # list[sqlite3.Row] from get_tasks_for_project()
    STATUS_LABELS=STATUS_LABELS
)
```

Template accesses: `project.id`, `project.name`, `project.description`,
`project.created_at`, `project.updated_at`. Loop over `tasks` — each row:
`t.id`, `t.title`, `t.status`, `t.priority`, `t.created_at`.
`STATUS_LABELS[t.status]` for display labels.

#### projects/form.html (Agent 2)

```python
# In projects/routes.py → new_project()
return render_template('projects/form.html',
    project=None,       # None signals "create" mode
    action_url=url_for('projects.create_project_route')
)

# In projects/routes.py → edit_project(project_id)
return render_template('projects/form.html',
    project=project,    # sqlite3.Row from get_project() — signals "edit" mode
    action_url=url_for('projects.update_project_route', project_id=project.id)
)
```

Template uses `project` to pre-fill fields (or leave empty if `None`).
Form fields: `name="name"`, `name="description"`.
Form `action="{{ action_url }}"` and `method="post"`.
Conditional title: `{% if project %}Edit Project{% else %}New Project{% endif %}`.

#### tasks/detail.html (Agent 3)

```python
# In tasks/routes.py → show_task(task_id)
return render_template('tasks/detail.html',
    task=task,           # sqlite3.Row from get_task()
    project=project,     # sqlite3.Row from get_project(conn, task.project_id)
    STATUS_LABELS=STATUS_LABELS,
    PRIORITY_LABELS=PRIORITY_LABELS
)
```

Template accesses: `task.id`, `task.title`, `task.description`, `task.status`,
`task.priority`, `task.created_at`, `task.updated_at`.
`project.id`, `project.name` (for breadcrumb/link back).
`STATUS_LABELS[task.status]`, `PRIORITY_LABELS[task.priority]`.

#### tasks/form.html (Agent 3)

```python
# In tasks/routes.py → new_task(project_id)
return render_template('tasks/form.html',
    task=None,           # None signals "create" mode
    project=project,     # sqlite3.Row from get_project()
    action_url=url_for('tasks.create_task_route', project_id=project.id),
    TASK_STATUSES=TASK_STATUSES,
    TASK_PRIORITIES=TASK_PRIORITIES,
    STATUS_LABELS=STATUS_LABELS,
    PRIORITY_LABELS=PRIORITY_LABELS
)

# In tasks/routes.py → edit_task(task_id)
return render_template('tasks/form.html',
    task=task,           # sqlite3.Row from get_task() — signals "edit" mode
    project=project,     # sqlite3.Row from get_project(conn, task.project_id)
    action_url=url_for('tasks.update_task_route', task_id=task.id),
    TASK_STATUSES=TASK_STATUSES,
    TASK_PRIORITIES=TASK_PRIORITIES,
    STATUS_LABELS=STATUS_LABELS,
    PRIORITY_LABELS=PRIORITY_LABELS
)
```

Template uses `task` to pre-fill fields (or leave empty/use defaults if `None`).
Form fields: `name="title"`, `name="description"`, `name="status"` (dropdown,
hidden if create mode — new tasks default to `'todo'`), `name="priority"`
(dropdown). Dropdowns iterate `TASK_STATUSES`/`TASK_PRIORITIES` with
`STATUS_LABELS`/`PRIORITY_LABELS` for display text. `selected` attribute
on current value. Form `action="{{ action_url }}"` and `method="post"`.

### 9. run.py Contract

Agent 1 writes `run.py` with exactly this content:

```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=False)
```

**App discovery:** The module-level `app = create_app()` line exposes the
Flask app object for both `python run.py` and `flask --app run run`.

**Verification command:** `flask --app run run` (or `python run.py`). Both
must start the app without errors.

**`requirements.txt`** (Agent 1):
```
flask>=3.0
```

No other dependencies. No flask-wtf (CSRF is out of scope for the acid test).

---

## Blueprint Registration (Agent 1)

Agent 1's `app/__init__.py` must register blueprints exactly as follows:

```python
from flask import Flask
from app.db import init_db


def create_app(db_path=None):
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'dev-acid-test'

    if db_path:
        app.config['DB_PATH'] = db_path
    else:
        app.config['DB_PATH'] = 'task_tracker.db'

    with app.app_context():
        init_db(app)

    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.projects import projects_bp
    from app.blueprints.tasks import tasks_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(tasks_bp)

    return app
```

**Note:** Tasks blueprint does NOT get a url_prefix in `register_blueprint`
because it owns routes under both `/tasks/*` and `/projects/<pid>/tasks/*`.
The routes are defined with full paths in the blueprint itself.

**Blueprint `__init__.py` files (Agents 2, 3, 4):**

```python
# app/blueprints/projects/__init__.py
from flask import Blueprint
projects_bp = Blueprint('projects', __name__)
from app.blueprints.projects import routes  # noqa: E402, F401

# app/blueprints/tasks/__init__.py
from flask import Blueprint
tasks_bp = Blueprint('tasks', __name__)
from app.blueprints.tasks import routes  # noqa: E402, F401

# app/blueprints/dashboard/__init__.py
from flask import Blueprint
dashboard_bp = Blueprint('dashboard', __name__)
from app.blueprints.dashboard import routes  # noqa: E402, F401
```

**Import order matters:** The `Blueprint()` call MUST come before the
`import routes` line to avoid circular imports.

## Agent Assignment

| # | Agent | Files | Key Spec Sections |
|---|-------|-------|-------------------|
| 1 | Core + Models | `run.py`, `requirements.txt`, `app/__init__.py`, `app/db.py`, `app/models.py`, `app/schema.sql` | All sections (implements shared infrastructure) |
| 2 | Projects | `app/blueprints/projects/__init__.py`, `app/blueprints/projects/routes.py`, `app/templates/projects/list.html`, `app/templates/projects/detail.html`, `app/templates/projects/form.html` | Routes (projects rows), Data Ownership, Template Blocks, Function Signatures (project + task getters) |
| 3 | Tasks | `app/blueprints/tasks/__init__.py`, `app/blueprints/tasks/routes.py`, `app/templates/tasks/detail.html`, `app/templates/tasks/form.html` | Routes (tasks rows), Data Ownership, Template Blocks, Function Signatures (task functions), Shared Constants (statuses, priorities) |
| 4 | Dashboard + Layout | `app/blueprints/dashboard/__init__.py`, `app/blueprints/dashboard/routes.py`, `app/templates/layout.html`, `app/templates/dashboard/index.html`, `app/static/style.css` | Routes (dashboard row), Template Blocks (defines layout), Function Signatures (get_dashboard_stats), Shared Constants (STATUS_LABELS) |

All agents depend ONLY on the Shared Interface Spec. No agent depends on
another agent's output.

## Agent Prompt Template

Each agent receives this prompt (with agent-specific sections filled in):

```
You are Agent [N] ([Name]) in a 4-agent parallel build.

## Your Assignment
Build these files for a Flask Task Tracker app:
[FILE LIST]

## Shared Interface Spec
[FULL SPEC FROM ABOVE]

## Rules
1. Read the Shared Interface Spec FIRST and follow it EXACTLY.
2. Only create files listed in your assignment. Do not create any other files.
3. Do not modify or read any files outside your assignment.
4. Use the exact function signatures, variable names, and import paths from the spec.
5. Use url_for() for all links — never hardcode paths.
6. All templates must extend layout.html using the block names from the spec.
7. Follow the implicit contracts (WAL mode, timestamps, 404 handling, PRG pattern).
8. Use the EXACT render_template() variable names from Section 8. Do not invent
   variable names — the template expects specific names.
9. Import shared constants (STATUS_LABELS, etc.) from app.models and pass them
   to templates exactly as shown in Section 8.
10. Do not make design decisions. If something is not in the spec, do not add it.

## Working Directory
task-tracker/
```

## Implementation Phases

### Phase 1: Setup (sequential, before agents)
- Create `task-tracker/` directory structure
- No code yet — just empty directories for agents to write into

### Phase 2: Parallel Agent Build (4 agents simultaneously)
- Launch 4 agents via the Agent tool, each with the prompt template above
- All agents run in parallel with `run_in_background: true`
- Wait for all 4 to complete

### Phase 3: Assembly + Verification (sequential, after agents)
- Run the 6 acceptance checkpoints (see below)
- Count mismatches
- Document results

## Acceptance Criteria

Adapted from DevDash (see brainstorm):

- [ ] **Checkpoint 1: App starts** — `cd task-tracker && flask --app run run`
  starts without import errors, circular import failures, or missing modules.
  This is the first test of the Feed-Forward risk (Python imports).
- [ ] **Checkpoint 2: All routes respond** — curl every endpoint from the
  routes table (Section 4), verify no 500 errors. All GET routes return 200.
- [ ] **Checkpoint 3: Shared DB state works** — POST to `/projects/` to create
  a project, verify it appears on dashboard (`GET /`). POST to
  `/projects/1/tasks` to create a task, verify task count updates on dashboard.
  Note: `GET /projects` will 308-redirect to `/projects/` — this is expected
  Flask behavior, not a mismatch.
- [ ] **Checkpoint 4: Navigation works** — Click through: Dashboard → Projects
  → Project Detail → New Task → Task Detail → back to Dashboard. All
  `url_for()` links resolve correctly.
- [ ] **Checkpoint 5: Invalid routes return 404** — GET `/projects/99999` and
  `/tasks/99999` return 404, not 500.
- [ ] **Checkpoint 6: Spec line count documented** — Record the final spec
  line count and compare to JS benchmarks (60 lines at 3 agents, 190 at 6).

### Checkpoint 7: Spec-vs-Code Audit (Feed-Forward Verification)

This checkpoint directly addresses the Feed-Forward risk. Do NOT rely on
"flask run works" alone — silent mismatches (wrong variable names in
templates, wrong block names, wrong render context) will not crash the app
but will produce blank sections or wrong data.

Run all checks from the `task-tracker/` directory. Every check has an exact
expected output — PASS/FAIL is automated, not "grep then human cross-reference."

**7a. Blueprint variable names (exact names, not just "Blueprint( appears"):**
```bash
# Check: projects_bp exists
grep -c "^projects_bp = Blueprint('projects'" app/blueprints/projects/__init__.py
# PASS if output = 1

# Check: tasks_bp exists
grep -c "^tasks_bp = Blueprint('tasks'" app/blueprints/tasks/__init__.py
# PASS if output = 1

# Check: dashboard_bp exists
grep -c "^dashboard_bp = Blueprint('dashboard'" app/blueprints/dashboard/__init__.py
# PASS if output = 1

# Check: app/__init__.py imports exact variable names
grep -c "from app.blueprints.dashboard import dashboard_bp" app/__init__.py
# PASS if output = 1
grep -c "from app.blueprints.projects import projects_bp" app/__init__.py
# PASS if output = 1
grep -c "from app.blueprints.tasks import tasks_bp" app/__init__.py
# PASS if output = 1

# Check: projects registered with url_prefix='/projects'
grep -c "register_blueprint(projects_bp, url_prefix='/projects')" app/__init__.py
# PASS if output = 1
```

**7b. Template inheritance and allowed block names:**
```bash
# Check: all 6 page templates extend layout.html
grep -r 'extends "layout.html"' app/templates/ --include="*.html" | grep -v layout.html | wc -l
# PASS if output = 6

# Check: all 6 page templates define block content
grep -r "block content" app/templates/ --include="*.html" | grep -v layout.html | wc -l
# PASS if output >= 6

# Check: layout.html defines block title and block content
grep -c "block title" app/templates/layout.html
# PASS if output >= 1
grep -c "block content" app/templates/layout.html
# PASS if output >= 1

# Check: NO invented block names (only title and content allowed)
grep -oP "block \w+" app/templates/**/*.html | grep -v "block title" | grep -v "block content" | wc -l
# PASS if output = 0

# Check: layout.html includes flash-message loop with categories
grep -c "get_flashed_messages(with_categories=true)" app/templates/layout.html
# PASS if output >= 1

# Check: no page template calls get_flashed_messages (layout handles it)
grep -r "get_flashed_messages" app/templates/ --include="*.html" | grep -v layout.html | wc -l
# PASS if output = 0
```

**7c. Render-context producer checks (exact render_template signatures):**
```bash
# Check: dashboard passes stats= and STATUS_LABELS=
grep -c "render_template('dashboard/index.html'" app/blueprints/dashboard/routes.py
# PASS if output = 1
grep "render_template('dashboard/index.html'" app/blueprints/dashboard/routes.py | grep -c "stats="
# PASS if output = 1
grep "render_template('dashboard/index.html'" app/blueprints/dashboard/routes.py | grep -c "STATUS_LABELS="
# PASS if output = 1

# Check: projects/list passes projects=
grep -c "render_template('projects/list.html'.*projects=" app/blueprints/projects/routes.py
# PASS if output = 1

# Check: projects/detail passes project= and tasks= and STATUS_LABELS=
grep -c "render_template('projects/detail.html'" app/blueprints/projects/routes.py
# PASS if output = 1
grep "render_template('projects/detail.html'" app/blueprints/projects/routes.py | grep -c "project=.*tasks=.*STATUS_LABELS="
# PASS if output = 1

# Check: projects/form passes project= and action_url= (2 calls: new + edit)
grep -c "render_template('projects/form.html'.*project=.*action_url=" app/blueprints/projects/routes.py
# PASS if output = 2

# Check: tasks/detail passes task=, project=, STATUS_LABELS=, PRIORITY_LABELS=
grep -c "render_template('tasks/detail.html'" app/blueprints/tasks/routes.py
# PASS if output = 1
grep "render_template('tasks/detail.html'" app/blueprints/tasks/routes.py | grep -c "task=.*project=.*STATUS_LABELS=.*PRIORITY_LABELS="
# PASS if output = 1

# Check: tasks/form passes task=, project=, action_url= (2 calls: new + edit)
grep -c "render_template('tasks/form.html'.*task=.*project=.*action_url=" app/blueprints/tasks/routes.py
# PASS if output = 2
```

**7d. get_db() usage (no bare assignment, always context manager):**
```bash
# Check: no route file uses conn = get_db() (anti-pattern)
grep -r "conn = get_db()" app/blueprints/ --include="*.py" | wc -l
# PASS if output = 0

# Check: all route files use "with get_db" pattern
grep -r "with get_db" app/blueprints/ --include="*.py" | wc -l
# PASS if output >= 1 per blueprint (expect >= 3 total)

# Check: PRAGMA foreign_keys enabled in db.py
grep -c "foreign_keys" app/db.py
# PASS if output >= 1
```

**7e. run.py app discovery:**
```bash
# Check: run.py exposes module-level app object
grep -c "^app = create_app()" run.py
# PASS if output = 1

# Check: flask can discover the app and list routes
flask --app run routes 2>&1 | head -1
# PASS if output shows route listing, not an error
```

**Residual manual risk:** Consumer-side template variable usage (whether
templates reference `{{ stats.total_projects }}` vs `{{ data.total_projects }}`)
cannot be verified by grep — it requires rendering each page and confirming the
expected data appears. This is the only remaining manual verification step. All
other checks are automated with exact PASS/FAIL criteria.

**Mismatch counting:** Each check that does not match its expected output
counts as one mismatch. Record total mismatch count.

**Pass:** All 7 checkpoints green, mismatch count = 0 → pattern is
stack-agnostic → archive sandbox-auto.
**Fail:** Any mismatch > 0 → investigate root cause → document whether it
is a spec gap (fixable) or a Python-specific limitation (pattern needs
adaptation).

## Technical Considerations

### Python Import Risk (Feed-Forward)
The `__init__.py` files in each blueprint are the highest-risk files. The
import pattern (`Blueprint()` before `import routes`) prevents circular imports
but is easy to get wrong. The spec prescribes the exact code for each
`__init__.py` to eliminate ambiguity.

### Tasks Blueprint Routing
The Tasks blueprint owns routes under two prefixes (`/tasks/*` and
`/projects/<pid>/tasks/*`). It is NOT registered with a `url_prefix` — routes
are defined with full paths in the blueprint. This is a deliberate design
choice to avoid the complexity of nested blueprints.

### SQLite Context Manager
Following the repo's established pattern from `dashboard/db.py`: use a
`@contextmanager` wrapper that calls `.close()` in `finally`. The built-in
`with sqlite3.connect()` does NOT close the connection.

## Dependencies & Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Circular imports in blueprint `__init__.py` | Medium | High (app won't start) | Spec prescribes exact import order |
| Jinja block name mismatch (silent failure) | Medium | Medium (blank sections) | Spec defines exact block names + layout code |
| Tasks blueprint dual-prefix routing | Low | Medium (404s on task creation) | Routes defined with full paths, no url_prefix |
| `get_db` usage mismatch (immediate flag) | Low | Low (potential locking) | Spec defines when to use `immediate=True` |
| `executescript()` implicit COMMIT in init_db | Medium | High (corrupts transaction state) | init_db uses raw connection, never `get_db()` |
| `updated_at` stays stale after UPDATE | High | Low (wrong timestamps) | Spec explicitly requires setting `updated_at` in all update functions |
| Empty form submissions create broken records | Medium | Medium (data integrity) | Input validation contract added to spec |

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-04-07-flask-swarm-acid-test.md](docs/brainstorms/2026-04-07-flask-swarm-acid-test.md)
  Key decisions carried forward: 4 agents, vertical split, all parallel, match JS criteria

### Internal References
- Swarm spec origin: `docs/solutions/2026-03-30-swarm-build-alignment.md`
- Spec scaling: `docs/solutions/2026-03-30-swarm-scale-shared-spec.md`
- Data ownership lesson: `docs/solutions/2026-03-30-chain-reaction-inter-service-contracts.md`
- Python spec template: `docs/plans/2026-04-05-sandbox-merge-swarm-integration-plan.md` (Phase 2)
- Flask patterns: `dashboard/db.py`, `dashboard/app.py`

## Feed-Forward

- **Hardest decision:** Whether the Tasks blueprint should own nested routes
  under `/projects/<pid>/tasks/*` or whether those should belong to the
  Projects blueprint. Chose Tasks as owner because it aligns with data
  ownership (Tasks blueprint writes to the tasks table) and avoids
  cross-blueprint write operations. Trade-off: Tasks blueprint has no
  `url_prefix` in registration, which is non-standard but correct.

- **Rejected alternatives:** Centralizing all model functions in `models.py`
  vs distributing them per blueprint. Chose centralized because the spec needs
  one place to define all function signatures, and it's the established
  pattern in this repo (dashboard/app.py). Distributed models would make the
  spec harder to verify.

- **Least confident:** Whether the prescribed `__init__.py` pattern (Blueprint
  creation before route import) will actually prevent circular imports in
  practice. This is the exact pattern Flask docs recommend, but with 4 agents
  writing these files independently, any deviation from the spec will cause
  an import error that prevents the app from starting. This is the #1 thing
  to watch during verification.
