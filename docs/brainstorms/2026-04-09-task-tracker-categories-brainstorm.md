---
title: "Task Tracker with Project Categories"
date: 2026-04-09
status: complete
origin: "autopilot-swarm-integration-test"
swarm_candidate: true
---

# Task Tracker with Project Categories -- Brainstorm

## Problem
Manage tasks organized by project categories through a web interface. Users
want to create projects, add tasks to them, mark tasks complete, and see a
dashboard overview of progress across all projects.

## Context
- Greenfield project in `task-tracker-categories/` subdirectory of sandbox
- Python 3.12+ / Flask (sandbox standard for web apps)
- Storage: SQLite via sqlite3 stdlib module
- No ORM -- raw SQL (sandbox convention, proven in existing task-tracker app)
- Multi-file structure: routes, models, templates, static CSS
- **This is the swarm path integration test** -- the app must be complex
  enough to split across 3+ parallel agents, but simple enough to build
  in one session

## What We're Building

A Flask web app with:

### Projects (categories)
- Create a project with name and optional color tag
- List all projects with task counts
- Edit project name/color
- Delete project (cascades to tasks)

### Tasks
- Create a task within a project (title, optional description)
- Mark task as complete/incomplete (toggle)
- Delete a task
- Filter tasks by project
- Sort by created date (newest first)

### Dashboard
- Total tasks / completed / pending counts
- Per-project progress bars
- Quick-add task form (select project from dropdown)

## Schema

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#6366f1',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
```

AUTOINCREMENT handles ID generation (no `max(ids)+1` needed -- lesson from
todo app solution doc). Foreign key with CASCADE handles project deletion
atomicity (lesson from migrator solution doc).

## Why This Approach

### SQLite over JSON
Multiple tables with relationships (projects -> tasks) need a relational
store. JSON would require manual joins and cascade logic. SQLite is stdlib.

### Raw SQL over ORM
Sandbox convention. Keeps the code transparent and teaches SQL. Flask-
SQLAlchemy would add a dependency and hide the queries.

### Server-rendered HTML over SPA
Flask + Jinja2 templates with minimal vanilla JS for toggles. No build step,
no frontend framework. HTMX considered but adds a dependency -- plain form
submissions are fine for this scope.

### Multi-file structure for swarm testing
The app naturally splits into:
- **Database layer**: schema, init, query functions
- **Routes**: Flask blueprints for projects, tasks, dashboard
- **Templates**: Jinja2 HTML files
- **Static**: CSS styling

This maps cleanly to 3-4 parallel swarm agents.

## Swarm Suitability

This app is a good swarm candidate because:
1. **Clear file boundaries** -- db, routes, templates, static are independent
2. **Shared interface is small** -- db function signatures + route URLs
3. **No complex cross-cutting logic** -- each layer talks to the one below
4. **Enough files** (10-15) to justify parallelism over solo execution

Suggested agent split:
- Agent A: Database layer (db.py, schema)
- Agent B: Route handlers (Flask blueprints)
- Agent C: Templates + static CSS

## Key Decisions

1. **SQLite** -- relational data needs relational DB. Stdlib, zero config.
2. **AUTOINCREMENT** -- avoids `max(ids)+1` empty-list bug from todo app.
3. **CASCADE delete** -- project deletion removes its tasks atomically.
4. **PRAGMA foreign_keys = ON** -- SQLite disables FK enforcement by default.
5. **Server-rendered** -- Jinja2 templates, no JS framework.
6. **Color tags** -- hex color per project for visual distinction. Default
   indigo (#6366f1). Simple but makes the dashboard readable.
7. **No auth** -- single-user local app. No login, no sessions beyond CSRF.
8. **No file locking** -- single-user Flask dev server. Not needed (lesson
   from todo app solution doc).

## Patterns from Solution Docs

| Pattern | Source | How it applies |
|---------|--------|----------------|
| Integer IDs via AUTOINCREMENT | cli-todo-app | Avoids max()+1 empty-list bug |
| Computed stats, not stored | cli-habit-tracker | Dashboard counts computed via SQL COUNT/SUM |
| CASCADE for multi-table ops | db-migration-runner | Project delete cascades to tasks |
| PRAGMA foreign_keys = ON | db-migration-runner | SQLite FK enforcement |

## Open Questions
(All resolved during brainstorm)

1. Should projects have descriptions? -- No. Name + color is enough. YAGNI.
2. Task priorities? -- No. Sort by created_at. Priorities add UI complexity
   for zero value at this scope.
3. Due dates? -- No. This is a simple tracker, not a project management tool.

## Feed-Forward
- **Hardest decision:** Whether to use HTMX for interactivity (toggle
  complete, inline edit) vs plain form submissions. Chose plain forms to
  avoid the dependency. HTMX would make the UX smoother but adds complexity
  the swarm test doesn't need.
- **Rejected alternatives:** JSON storage (can't handle relations), ORM
  (sandbox convention is raw SQL), SPA frontend (overkill), task priorities
  and due dates (YAGNI).
- **Least confident:** Whether the template agent can produce working HTML
  without seeing the actual route return values. The shared spec must define
  exact template variable names and structures passed to each template.

## Refinement Findings

Gaps found by searching all 21 solution docs in `docs/solutions/`. Each item
is a lesson that applies to this brainstorm but is NOT in the "Patterns from
Solution Docs" table above.

### Gap 1: `init_db()` must use a raw connection, not `get_db()`

**Lesson:** `executescript()` issues an implicit COMMIT. If `init_db` calls
`executescript` through a `get_db()` context manager, it silently commits and
releases any pending transaction. Always use a raw `sqlite3.connect()` for
schema initialization.

**Source:** flask-url-shortener-api, chat-room-api, feature-flag-service,
db-migration-runner (all four Flask+SQLite apps hit this).

**Relevance:** The task tracker uses `executescript` for the two-table schema.
If the db layer agent routes `init_db` through `get_db`, schema creation will
have the implicit COMMIT footgun.

**Plan should:** Specify in the shared spec that `init_db()` uses a raw
`sqlite3.connect()` call, not `get_db()`. Include the exact code block.

### Gap 2: WAL mode + busy timeout for concurrent writes

**Lesson:** Default SQLite journal mode causes `OperationalError: database is
locked` under concurrent writes. Enable WAL mode and set a busy timeout on
every connection.

**Source:** flask-url-shortener-api (`PRAGMA journal_mode=WAL` + `timeout=10`),
chat-room-api (WAL mode), db-migration-runner (WAL + verify return value).

**Relevance:** The task tracker has write operations (create/edit/delete for
both projects and tasks, toggle complete). Even on a dev server, rapid form
submissions can trigger the lock error. WAL mode is a zero-cost safety net.

**Plan should:** Add `PRAGMA journal_mode=WAL` to `get_db()` and specify it in
the shared spec so the db agent implements it.

### Gap 3: Context manager usage examples are mandatory in the shared spec

**Lesson:** When a shared spec defines a `@contextmanager` function (like
`get_db`), agents will use `db = get_db()` instead of `with get_db() as db:`
unless the spec includes an explicit usage example. All 3 blueprint agents in
the Flask swarm acid test made this identical mistake.

**Source:** flask-swarm-acid-test (the most directly relevant solution doc --
it built a nearly identical task tracker app with swarm agents).

**Relevance:** This brainstorm's "Least confident" item is exactly this risk:
template agent producing working code without seeing route return values. The
acid test proves the spec needs usage examples, not just function signatures.

**Plan should:** Include explicit `with get_db() as db:` usage examples for
both read and write operations in the shared spec. This is the #1 lesson from
the acid test and directly addresses the Feed-Forward concern.

### Gap 4: Template Render Context section is mandatory for Python/Flask specs

**Lesson:** Python/Flask specs are 3x larger than JS specs, and the growth is
mostly from Section 8 (Template Render Context) -- 150+ lines defining exact
`render_template()` keyword arguments for every route/template pair. Without
this section, the template agent cannot produce working HTML.

**Source:** flask-swarm-acid-test (spec was 584 lines for 4 agents; 150+ lines
were template render context).

**Relevance:** The brainstorm identifies 3 agents (db, routes, templates+CSS).
The template agent needs to know exactly what variables each route passes to
each template. This is the most critical section of the shared spec for Flask
swarm builds.

**Plan should:** Allocate a dedicated Template Render Context section in the
spec listing every `render_template()` call with its exact keyword arguments.

### Gap 5: Prescriptive code blocks for integration surface files

**Lesson:** For files touched by multiple agents' imports (like `__init__.py`,
`app.py`, blueprint registration), the spec must include the exact code, not a
description. Prescriptive blocks produced 0 mismatches in the acid test for the
highest-risk files.

**Source:** flask-swarm-acid-test ("For files that are integration surfaces,
include the exact code in the spec. Don't describe it -- write it.")

**Relevance:** The task tracker's `app.py` (or `__init__.py`) will be imported
by all blueprint agents. Blueprint registration order, import paths, and app
factory pattern are all integration surfaces.

**Plan should:** Include exact code for the app factory / main app file and all
blueprint `__init__.py` files in the shared spec.

### Gap 6: Data ownership section needed for shared tables

**Lesson:** For every shared table, the spec must declare which agent/module
WRITES to it. Without this, two modules will independently write to the same
table and conflict.

**Source:** chain-reaction-inter-service-contracts (Bug 2: double
`status_update` writes because the spec was ambiguous about ownership).

**Relevance:** The `tasks` table is written by both the tasks routes and
potentially the dashboard's quick-add form. The spec must clarify that task
creation/update/delete is owned by the tasks blueprint, and the dashboard
quick-add form POSTs to the tasks endpoint (not a separate dashboard route).

**Plan should:** Add a Data Ownership table to the spec: which agent owns
writes to `projects`, which owns writes to `tasks`, and how the dashboard
quick-add routes through the tasks blueprint.

### Gap 7: ON DELETE SET NULL for audit/event tables (not CASCADE everywhere)

**Lesson:** CASCADE is wrong for audit-style records. When a parent row is
deleted, CASCADE deletes the audit trail too. Use SET NULL to preserve records
while clearing the dangling FK.

**Source:** service-mesh-dashboard ("CASCADE deletes the service.deleted event
along with the service -- audit records must survive").

**Relevance:** The brainstorm uses CASCADE for project->tasks, which is
correct (deleting a project should delete its tasks). This is informational
only -- the brainstorm made the right call. But the plan should document WHY
CASCADE is correct here (tasks are owned data, not audit records) to prevent
a reviewer from reflexively changing it to SET NULL.

**Plan should:** Add a brief note in the schema section explaining that
CASCADE is intentional because tasks are owned data, not audit records.

### Gap 8: `executescript()` must never be used inside transactions

**Lesson:** Beyond `init_db`, `executescript()` must never appear in any
transactional code path. It issues an implicit COMMIT that silently breaks
transaction semantics.

**Source:** db-migration-runner ("executescript() NEVER used" -- individual
`conn.execute()` calls used instead), feature-flag-service (same pattern).

**Relevance:** If the db layer agent uses `executescript` for any multi-
statement operation (e.g., creating both tables), it must only be in `init_db`
with a raw connection. The shared spec should ban `executescript` outside of
`init_db`.

**Plan should:** Add an explicit constraint to the spec: "`executescript()`
is only allowed in `init_db()`. All other SQL uses `conn.execute()`."

### Summary

| # | Gap | Severity | Source |
|---|-----|----------|--------|
| 1 | `init_db` raw connection | High | 4 Flask solution docs |
| 2 | WAL mode + busy timeout | Medium | 3 Flask solution docs |
| 3 | Context manager usage examples | High | flask-swarm-acid-test |
| 4 | Template Render Context section | High | flask-swarm-acid-test |
| 5 | Prescriptive code for integration files | High | flask-swarm-acid-test |
| 6 | Data ownership in spec | Medium | chain-reaction-contracts |
| 7 | CASCADE vs SET NULL rationale | Low | service-mesh-dashboard |
| 8 | Ban `executescript` outside init_db | Medium | db-migration-runner |

Gaps 3, 4, and 5 are the most critical -- they come from the flask-swarm-acid-
test solution doc, which built a nearly identical app with the same swarm
pattern. The brainstorm's "Least confident" item (template agent producing
working HTML) is directly addressed by these three gaps.

No blocking issues found. All gaps are addressable in the plan phase.

**STATUS: PASS**
