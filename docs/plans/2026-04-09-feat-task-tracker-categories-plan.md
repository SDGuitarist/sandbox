---
title: "feat: Task Tracker with Project Categories"
type: feat
status: active
date: 2026-04-09
swarm: true
origin: docs/brainstorms/2026-04-09-task-tracker-categories-brainstorm.md
feed_forward:
  risk: "Whether the template agent can produce working HTML without seeing the actual route return values. The shared spec must define exact template variable names and structures passed to each template."
  verify_first: true
---

# feat: Task Tracker with Project Categories

## Enhancement Summary

Build a Flask web app for managing tasks organized by project categories.
Each project has a color tag. Tasks belong to a project and can be toggled
complete/incomplete. A dashboard shows progress across all projects.

This is the **swarm path integration test** (Phase 5 part 2).

(see brainstorm: docs/brainstorms/2026-04-09-task-tracker-categories-brainstorm.md)

## Plan Quality Gate

1. **What exactly is changing?** A new `task-tracker-categories/` directory with
   a Flask app built by 4 parallel agents. No existing code is modified.
2. **What must not change?** All other apps in the sandbox repo. No modifications
   to docs/solutions/ or existing plans. The existing `task-tracker/` is untouched.
3. **How will we know it worked?** 6 acceptance checkpoints all green (see
   Acceptance Criteria). Primary metric: interface mismatch count = 0.
4. **What is the most likely way this plan is wrong?** The template agent may
   produce HTML that references variables not passed by the route agent. The
   Template Render Context section (Section 8) is the mitigation. Secondary
   risk: color hex values in CSS may not be handled correctly if templates
   use inline styles while CSS expects classes.

## Proposed Solution

Each agent receives the Shared Interface Spec as its only input and builds
its assigned files independently. After all 4 agents complete, their output
is assembled and verified.

### Directory Structure

```
task-tracker-categories/
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
| `create_project` | `create_project(conn, name, color)` | `int` (new id) | Projects |
| `update_project` | `update_project(conn, project_id, name, color)` | `None` | Projects |
| `delete_project` | `delete_project(conn, project_id)` | `None` | Projects |
| `get_tasks_for_project` | `get_tasks_for_project(conn, project_id)` | `list[sqlite3.Row]` | Projects |
| `get_task` | `get_task(conn, task_id)` | `sqlite3.Row` or `None` | Tasks |
| `create_task` | `create_task(conn, project_id, title, description)` | `int` (new id) | Tasks |
| `update_task` | `update_task(conn, task_id, title, description)` | `None` | Tasks |
| `toggle_task` | `toggle_task(conn, task_id)` | `None` (flips completed 0<->1, sets/clears completed_at) | Tasks |
| `delete_task` | `delete_task(conn, task_id)` | `None` | Tasks |
| `get_dashboard_stats` | `get_dashboard_stats(conn)` | `dict` (see below) | Dashboard |

`get_dashboard_stats` returns:
```python
{
    "total_tasks": int,
    "completed_tasks": int,
    "pending_tasks": int,
    "projects": list[sqlite3.Row]  # all projects with task counts
    # columns: id, name, color, task_count, completed_count
}
```

`projects` SQL (with task counts):
```sql
SELECT p.id, p.name, p.color,
       COUNT(t.id) AS task_count,
       SUM(CASE WHEN t.completed = 1 THEN 1 ELSE 0 END) AS completed_count
FROM projects p LEFT JOIN tasks t ON t.project_id = p.id
GROUP BY p.id, p.name, p.color ORDER BY p.name
```

Total/completed/pending SQL:
```sql
SELECT COUNT(*) AS total_tasks,
       SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed_tasks,
       SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) AS pending_tasks
FROM tasks
```

All model functions receive a `conn` parameter (the sqlite3.Connection from
`get_db()`). They do NOT call `get_db()` themselves.

`toggle_task` implementation:
```python
def toggle_task(conn, task_id):
    task = conn.execute("SELECT completed FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        return
    if task['completed']:
        conn.execute("UPDATE tasks SET completed = 0, completed_at = NULL WHERE id = ?", (task_id,))
    else:
        conn.execute("UPDATE tasks SET completed = 1, completed_at = datetime('now') WHERE id = ?", (task_id,))
```

#### get_db() Usage Contract

`get_db()` is a context manager. **Never** assign it directly (`conn = get_db()` is wrong). Always use `with`:

**Read-only operations** (GET routes):
```python
with get_db() as conn:
    project = get_project(conn, project_id)
```

**Write operations** (POST routes -- create, update, delete, toggle):
```python
with get_db(immediate=True) as conn:
    create_project(conn, name, color)
```

`immediate=True` acquires a `BEGIN IMMEDIATE` lock, preventing concurrent
write conflicts in SQLite. Every POST handler must use `immediate=True`.
Every GET handler uses the default `immediate=False`.

**Anti-pattern (will break):**
```python
# WRONG -- get_db() returns a context manager, not a connection
conn = get_db()
project = get_project(conn, project_id)
```

### 2. Database Schema

```sql
-- schema.sql (Agent 1 writes this file)

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#6366f1',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);
```

**FK semantics:** `ON DELETE CASCADE` on `tasks.project_id`. Deleting a project
cascades to its tasks. CASCADE is correct here because tasks are owned data,
not audit records (see brainstorm refinement Gap 7).

**`executescript()` rule:** Only allowed in `init_db()` with a raw connection.
All other SQL uses `conn.execute()` (see brainstorm refinement Gap 8).

### 3. Shared Constants

| Constant | Value | Defined in | Used by | Purpose |
|----------|-------|-----------|---------|---------|
| `DEFAULT_COLOR` | `'#6366f1'` | `models.py` | Projects | Default project color |
| `DB_NAME` | `'task_tracker_categories.db'` | `db.py` | `__init__.py` | Default database filename |

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
| POST | `/projects/<int:project_id>/tasks` | tasks | `create_task_route(project_id)` | Redirects to `/projects/<id>` |
| POST | `/tasks/<int:task_id>/toggle` | tasks | `toggle_task_route(task_id)` | Redirects back to project detail |
| GET | `/tasks/<int:task_id>/edit` | tasks | `edit_task(task_id)` | Renders `tasks/form.html` (filled) |
| POST | `/tasks/<int:task_id>` | tasks | `update_task_route(task_id)` | Redirects to `/projects/<id>` |
| POST | `/tasks/<int:task_id>/delete` | tasks | `delete_task_route(task_id)` | Redirects to `/projects/<id>` |

**Route ownership:** Tasks blueprint owns `/tasks/*` routes AND the nested
`/projects/<pid>/tasks` (POST) route for creating tasks within a project.

**Routing contract:**
- **Projects blueprint** is registered with `url_prefix='/projects'`. All
  project routes use **relative** route rules (e.g., `@projects_bp.route('/')`
  resolves to `/projects/`).
- **Tasks blueprint** has no `url_prefix`. All task routes use **absolute** rules.
- **Dashboard blueprint** has no `url_prefix`. Single absolute route `'/'`.

**Projects route-rule examples** (relative, because `url_prefix='/projects'`):
```python
@projects_bp.route('/')                                    # -> /projects/
@projects_bp.route('/<int:project_id>')                    # -> /projects/<id>
@projects_bp.route('/new')                                 # -> /projects/new
@projects_bp.route('/', methods=['POST'])                  # -> POST /projects/
@projects_bp.route('/<int:project_id>/edit')               # -> /projects/<id>/edit
@projects_bp.route('/<int:project_id>', methods=['POST'])  # -> POST /projects/<id>
@projects_bp.route('/<int:project_id>/delete', methods=['POST'])  # -> POST /projects/<id>/delete
```

### 5. Data Ownership

| Table | Writer (single owner) | Readers |
|-------|----------------------|---------|
| `projects` | Projects blueprint | Dashboard (stats), Tasks (project name for redirects) |
| `tasks` | Tasks blueprint | Dashboard (stats), Projects (task list on detail page) |

**Rule:** Only the writer calls `create_*`, `update_*`, `delete_*`, `toggle_*`
model functions for its table. Readers only call `get_*` functions.

**Dashboard quick-add:** There is NO quick-add form on the dashboard. Tasks
are created from the project detail page only (via the Tasks blueprint).

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
        <div class="nav-brand">Task Tracker</div>
        <div class="nav-links">
            <a href="{{ url_for('dashboard.index') }}">Dashboard</a>
            <a href="{{ url_for('projects.list_projects') }}">Projects</a>
        </div>
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
- `url_for('dashboard.index')` -> `/`
- `url_for('projects.list_projects')` -> `/projects/`
- `url_for('projects.show_project', project_id=p.id)` -> `/projects/<id>`
- `url_for('projects.new_project')` -> `/projects/new`
- `url_for('tasks.create_task_route', project_id=p.id)` -> `/projects/<id>/tasks`
- `url_for('tasks.toggle_task_route', task_id=t.id)` -> `/tasks/<id>/toggle`
- `url_for('tasks.edit_task', task_id=t.id)` -> `/tasks/<id>/edit`
- `url_for('tasks.delete_task_route', task_id=t.id)` -> `/tasks/<id>/delete`

### 7. Implicit Contracts

- **Timestamp format:** SQLite `datetime('now')` default
- **SQLite connection setup:** WAL mode, `foreign_keys=ON`, `timeout=10`,
  `row_factory=sqlite3.Row`
- **Transaction semantics:** `get_db(immediate=True)` for writes, `get_db()` for reads
- **404 handling:** If `get_project()` or `get_task()` returns `None`, call `abort(404)`
- **Authentication:** Out of scope. No auth.
- **Input validation:** Strip whitespace, reject empty required fields via `flash('error message', 'error')`
- **Flash messages:** `flash('message', 'category')` for success/error. Layout handles display.
- **Form data:** `request.form.get('field', '').strip()` for all fields
- **SQL injection prevention:** Parameterized `?` placeholders only
- **XSS prevention:** Jinja2 auto-escaping. No `|safe` filter on user content.
- **Color handling:** Project colors are stored as hex strings (e.g., `'#6366f1'`).
  Templates use inline `style="background-color: {{ project.color }}"` for color
  indicators, NOT CSS classes. This avoids generating dynamic CSS.
- **Redirects after writes:** POST-Redirect-GET pattern using `redirect(url_for(...))`
- **Form field `name` attributes:** Projects: `name="name"`, `name="color"`.
  Tasks: `name="title"`, `name="description"`.
- **Import pattern:** All blueprints import from `app.db` and `app.models`:
  ```python
  from app.db import get_db
  from app.models import get_project, get_tasks_for_project  # etc.
  ```

### 8. Template Render Context

Every `render_template()` call must pass exactly these variables.

#### dashboard/index.html (Agent 4)

```python
# In dashboard/routes.py -> index()
return render_template('dashboard/index.html',
    stats=stats  # dict from get_dashboard_stats()
)
```

Template accesses: `stats.total_tasks`, `stats.completed_tasks`,
`stats.pending_tasks`, `stats.projects` (loop: `p.id`, `p.name`, `p.color`,
`p.task_count`, `p.completed_count`).

Progress bar per project: width = `(p.completed_count / p.task_count * 100)`
if `p.task_count > 0` else `0`.

#### projects/list.html (Agent 2)

```python
# In projects/routes.py -> list_projects()
return render_template('projects/list.html',
    projects=projects  # list[sqlite3.Row] from get_all_projects()
)
```

Template accesses: loop over `projects` -- each row: `p.id`, `p.name`,
`p.color`, `p.created_at`.

#### projects/detail.html (Agent 2)

```python
# In projects/routes.py -> show_project(project_id)
return render_template('projects/detail.html',
    project=project,   # sqlite3.Row from get_project()
    tasks=tasks         # list[sqlite3.Row] from get_tasks_for_project()
)
```

Template accesses: `project.id`, `project.name`, `project.color`,
`project.created_at`. Loop over `tasks` -- each row: `t.id`, `t.title`,
`t.description`, `t.completed`, `t.created_at`, `t.completed_at`.

Task display: use `t.completed` (0 or 1) to show checkbox state. Each task
has a toggle form (POST to toggle endpoint) and edit/delete links.

New task form inline on the project detail page:
```html
<form method="post" action="{{ url_for('tasks.create_task_route', project_id=project.id) }}">
    <input type="text" name="title" placeholder="New task..." required>
    <input type="hidden" name="description" value="">
    <button type="submit">Add Task</button>
</form>
```

#### projects/form.html (Agent 2)

```python
# In projects/routes.py -> new_project()
return render_template('projects/form.html',
    project=None,
    action_url=url_for('projects.create_project_route')
)

# In projects/routes.py -> edit_project(project_id)
return render_template('projects/form.html',
    project=project,
    action_url=url_for('projects.update_project_route', project_id=project.id)
)
```

Template uses `project` to pre-fill fields (or leave empty/defaults if `None`).
Form fields: `name="name"`, `name="color"` (type="color" input).
Form `action="{{ action_url }}"` and `method="post"`.
Conditional title: `{% if project %}Edit Project{% else %}New Project{% endif %}`.

#### tasks/form.html (Agent 3)

```python
# In tasks/routes.py -> edit_task(task_id)
return render_template('tasks/form.html',
    task=task,
    project=project,
    action_url=url_for('tasks.update_task_route', task_id=task.id)
)
```

Template: form with `name="title"`, `name="description"` (textarea).
Pre-filled from `task.title`, `task.description`.
Shows project name as context: `project.name`.
Form `action="{{ action_url }}"` and `method="post"`.

### 9. run.py Contract

Agent 1 writes `run.py` with exactly this content:

```python
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=False)
```

**`requirements.txt`** (Agent 1):
```
flask>=3.0
```

---

## Blueprint Registration (Agent 1)

Agent 1's `app/__init__.py` must contain exactly:

```python
from flask import Flask
from app.db import init_db


def create_app(db_path=None):
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'dev-task-tracker'

    if db_path:
        app.config['DB_PATH'] = db_path
    else:
        app.config['DB_PATH'] = 'task_tracker_categories.db'

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

## Swarm Agent Assignment

| # | Agent | Files | Key Spec Sections |
|---|-------|-------|-------------------|
| 1 | Core + Models | `task-tracker-categories/run.py`, `task-tracker-categories/requirements.txt`, `task-tracker-categories/app/__init__.py`, `task-tracker-categories/app/db.py`, `task-tracker-categories/app/models.py`, `task-tracker-categories/app/schema.sql` | All sections (implements shared infrastructure) |
| 2 | Projects | `task-tracker-categories/app/blueprints/projects/__init__.py`, `task-tracker-categories/app/blueprints/projects/routes.py`, `task-tracker-categories/app/templates/projects/list.html`, `task-tracker-categories/app/templates/projects/detail.html`, `task-tracker-categories/app/templates/projects/form.html` | Routes (projects rows), Data Ownership, Template Blocks, Render Context |
| 3 | Tasks | `task-tracker-categories/app/blueprints/tasks/__init__.py`, `task-tracker-categories/app/blueprints/tasks/routes.py`, `task-tracker-categories/app/templates/tasks/form.html` | Routes (tasks rows), Data Ownership, Template Blocks, Render Context |
| 4 | Dashboard + Layout | `task-tracker-categories/app/blueprints/dashboard/__init__.py`, `task-tracker-categories/app/blueprints/dashboard/routes.py`, `task-tracker-categories/app/templates/layout.html`, `task-tracker-categories/app/templates/dashboard/index.html`, `task-tracker-categories/app/static/style.css` | Routes (dashboard row), Template Blocks (defines layout), Render Context |

## Acceptance Criteria

- [ ] **Checkpoint 1: App starts** -- `cd task-tracker-categories && flask --app run run` starts without errors
- [ ] **Checkpoint 2: All routes respond** -- curl every GET endpoint, verify no 500 errors
- [ ] **Checkpoint 3: CRUD works** -- Create project, create task in project, toggle task, verify on dashboard
- [ ] **Checkpoint 4: Navigation works** -- Dashboard -> Projects -> Project Detail -> Edit Task -> back
- [ ] **Checkpoint 5: Invalid routes return 404** -- GET `/projects/99999` returns 404
- [ ] **Checkpoint 6: Cascade delete** -- Delete a project, verify its tasks are also deleted

## Feed-Forward
- **Hardest decision:** Keeping the schema simple (no status enum, just completed toggle) vs matching the acid test's richer schema. Simpler is better for testing the swarm path without conflating schema complexity with swarm complexity.
- **Rejected alternatives:** Quick-add on dashboard (complicates data ownership), HTMX for toggle (adds dependency), status enum (YAGNI for this scope).
- **Least confident:** Whether 3-file Agent 3 (Tasks) has enough work to justify a separate agent vs folding it into Agent 2 (Projects). Kept it separate because merging would create a 8-file agent, violating the "balanced workload" principle.
