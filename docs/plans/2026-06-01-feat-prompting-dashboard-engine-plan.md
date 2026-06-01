---
title: "feat: Prompting Dashboard Engine"
type: feat
status: active
date: 2026-06-01
origin: docs/brainstorms/2026-06-01-prompting-dashboard-engine-brainstorm.md
swarm: true
feed_forward:
  risk: "Claude API synchronous calls may timeout in Flask request cycle (brainstorm least-confident)"
  verify_first: true
---

# feat: Prompting Dashboard Engine

## Enhancement Summary

**Deepened on:** 2026-06-01
**Research agents used:** framework-docs-researcher, security-sentinel, performance-oracle, architecture-strategist

### P1 Fixes Applied (7)
1. FTS5 DELETE/UPDATE triggers changed from AFTER to BEFORE (corrupted search index)
2. `close_db` teardown added to `create_app()` code block (connection leak)
3. `threaded=True` prescribed in Flask run config (UI freeze during API calls)
4. `isolation_level` comment added to `get_db()` (3-build recurrence prevention)
5. Blueprint `__init__.py` contents prescribed (spec ambiguity)
6. `get_prompt` removed from `dashboard_routes` Used By (stale cross-section entry)
7. `difflib.HtmlDiff` labels escaped with `html.escape()` (XSS vector)

### P2 Improvements Applied (8)
1. FTS5 sanitization: backslash added to strip set, empty-query returns None
2. BEGIN IMMEDIATE transaction pattern with full code example
3. Seed agent: CLI registration, imports, and wiring prescribed
4. `extract_variables` ownership clarified (internal to create/update_prompt)
5. Template filenames added to Export Names Table
6. 5 GET routes added to Input Validation Prescriptions
7. API key reads from os.environ directly (not visible in debugger)
8. Redundant per-connection WAL pragma removed from get_db()

## Overview

A local-first prompt engineering workbench. Create prompt templates with `{{variable}}` placeholders, test them against the Claude API, track version history with side-by-side diffs, and browse a prompt library with FTS5 search and tag filtering. Flask + SQLite + Jinja2 + Bootstrap 5 dark theme. Single-user, no auth.

(see brainstorm: docs/brainstorms/2026-06-01-prompting-dashboard-engine-brainstorm.md)

## What Exactly Is Changing?

New app at `prompt-dashboard/` with:
- 3 blueprints: `prompts`, `testing`, `dashboard`
- 6 database tables (including FTS5 virtual table)
- 12 routes, 9 templates, ~20 model functions
- Claude API integration via `anthropic` Python SDK

## What Must Not Change?

- No modifications to existing sandbox apps or shared files
- No production API calls — `ANTHROPIC_API_KEY` must be user-provided via environment
- No auth system — all routes are public (single-user local tool)

## How Will We Know It Worked?

### Acceptance Tests (EARS)

#### Happy Path
- WHEN a user visits `/` THE SYSTEM SHALL display all prompts with name, description, version count, last-tested date, and tags
- WHEN a user creates a prompt with name "Test Prompt" and system prompt "You are helpful" THE SYSTEM SHALL save it and redirect to the detail page showing version 1
- WHEN a user edits a prompt THE SYSTEM SHALL create a new version and increment the version count
- WHEN a user visits `/prompts/<id>/versions` THE SYSTEM SHALL list all versions with timestamps
- WHEN a user visits `/prompts/<id>/diff?v1=1&v2=2` THE SYSTEM SHALL display a side-by-side diff of the two versions
- WHEN a user fills variables and submits a test THE SYSTEM SHALL send the substituted prompt to Claude API, display the response, and store the test run
- WHEN a user searches "hello" on the dashboard THE SYSTEM SHALL return only prompts matching the FTS5 query
- WHEN a user filters by tag "coding" THE SYSTEM SHALL return only prompts with that tag

#### Error Cases
- WHEN `ANTHROPIC_API_KEY` is not set THE SYSTEM SHALL display a warning banner and disable the test runner
- WHEN a user submits a test and the Claude API times out THE SYSTEM SHALL store the error in `test_runs.error` and display a user-friendly message
- WHEN a user searches with FTS5 operators like `name:*` THE SYSTEM SHALL sanitize the input and return results safely (FC36)
- WHEN a user submits a create form with an empty name THE SYSTEM SHALL flash "Name is required" and redirect back

#### Verification Commands
- `.venv/bin/python test_smoke.py` — all smoke tests pass
- `curl http://localhost:5050/` — returns 200 with prompt listing
- `curl http://localhost:5050/prompts/new` — returns 200 with create form

## What Is the Most Likely Way This Plan Is Wrong?

The Claude API timeout risk (brainstorm Feed-Forward). If Claude takes >30s, the synchronous Flask request may appear hung. Mitigation: 60s timeout on API call, `anthropic.APITimeoutError` caught distinctly, stored in `test_runs.error`. If this is insufficient, Phase 2 adds async execution.

---

# Shared Interface Spec

## App Configuration

```python
# prompt-dashboard/app/__init__.py
import os
from flask import Flask
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']  # NO fallback (FC10)
    # NOTE: ANTHROPIC_API_KEY is NOT stored in app.config (visible in debugger).
    # Testing routes read it directly from os.environ.

    csrf.init_app(app)

    from .database import init_db, close_db
    init_db()
    app.teardown_appcontext(close_db)  # MANDATORY — closes SQLite connections

    from .blueprints.dashboard.routes import bp as dashboard_bp
    from .blueprints.prompts.routes import bp as prompts_bp
    from .blueprints.testing.routes import bp as testing_bp

    app.register_blueprint(dashboard_bp)          # url_prefix='/'
    app.register_blueprint(prompts_bp)             # url_prefix='/prompts'
    app.register_blueprint(testing_bp)             # url_prefix='/testing'

    @app.context_processor
    def inject_api_key_status():
        return dict(api_key_configured=bool(os.environ.get('ANTHROPIC_API_KEY', '')))

    from .seed import register_seed_command
    register_seed_command(app)

    return app
```

**Requirements (requirements.txt):**
```
flask>=3.0
flask-wtf>=1.2
anthropic>=0.39
markupsafe>=2.1
```

**Environment (.env.example):**
```
SECRET_KEY=change-me-to-random-string
ANTHROPIC_API_KEY=sk-ant-...
FLASK_DEBUG=1
```

**App Runner (prompt-dashboard/run.py):**
```python
# Run with: .venv/bin/python run.py
from app import create_app

app = create_app()
app.run(host='127.0.0.1', port=5050, debug=True, threaded=True)
# threaded=True REQUIRED — without it, Claude API calls (up to 60s)
# block the single-threaded dev server, freezing the entire UI.
# SQLite WAL mode + per-request connections (flask.g) are thread-safe.
```

## Database Schema

```sql
-- prompt-dashboard/app/schema.sql

CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    user_prompt TEXT NOT NULL DEFAULT '',
    variables TEXT NOT NULL DEFAULT '[]',
    version_count INTEGER NOT NULL DEFAULT 1,
    last_tested_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    system_prompt TEXT NOT NULL DEFAULT '',
    user_prompt TEXT NOT NULL DEFAULT '',
    variables TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(prompt_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_prompt_id ON prompt_versions(prompt_id);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS prompt_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE(prompt_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_prompt_tags_prompt_id ON prompt_tags(prompt_id);
CREATE INDEX IF NOT EXISTS idx_prompt_tags_tag_id ON prompt_tags(tag_id);

CREATE TABLE IF NOT EXISTS test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_version_id INTEGER NOT NULL REFERENCES prompt_versions(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    variables_used TEXT NOT NULL DEFAULT '{}',
    response_text TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    duration_ms INTEGER,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_test_runs_prompt_version_id ON test_runs(prompt_version_id);

-- FTS5 virtual table for search (external content)
CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts USING fts5(
    name, description, system_prompt, user_prompt,
    content=prompts, content_rowid=id
);

-- Triggers to keep FTS5 in sync with prompts table
-- CRITICAL: DELETE and UPDATE delete-half MUST be BEFORE triggers.
-- FTS5 external content fetches old values from the content table to remove
-- tokens. If the row is already deleted/updated, FTS5 reads wrong values
-- and corrupts the index. (Deepening: framework-docs-researcher)
CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, name, description, system_prompt, user_prompt)
    VALUES (new.id, new.name, new.description, new.system_prompt, new.user_prompt);
END;

CREATE TRIGGER IF NOT EXISTS prompts_bd BEFORE DELETE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, name, description, system_prompt, user_prompt)
    VALUES ('delete', old.id, old.name, old.description, old.system_prompt, old.user_prompt);
END;

CREATE TRIGGER IF NOT EXISTS prompts_bu BEFORE UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, name, description, system_prompt, user_prompt)
    VALUES ('delete', old.id, old.name, old.description, old.system_prompt, old.user_prompt);
END;

CREATE TRIGGER IF NOT EXISTS prompts_au AFTER UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, name, description, system_prompt, user_prompt)
    VALUES (new.id, new.name, new.description, new.system_prompt, new.user_prompt);
END;
```

## Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| prompts | models agent (`app/models.py`) | prompts_routes, dashboard_routes, testing_routes |
| prompt_versions | models agent (`app/models.py`) | prompts_routes, testing_routes |
| tags | models agent (`app/models.py`) | prompts_routes, dashboard_routes |
| prompt_tags | models agent (`app/models.py`) | prompts_routes, dashboard_routes |
| test_runs | models agent (`app/models.py`) | testing_routes, prompts_routes (detail page) |
| prompts_fts | models agent (via triggers) | dashboard_routes |

## Database Connection

```python
# prompt-dashboard/app/database.py
import sqlite3
import os
from contextlib import contextmanager
from flask import g, current_app

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts.db')

@contextmanager
def get_db():
    """Context manager for database connections.
    Usage:
        with get_db() as conn:
            rows = conn.execute('SELECT ...').fetchall()
    """
    if 'db' not in g:
        # isolation_level left as default ("") — DO NOT use isolation_level=None,
        # which makes conn.commit() a no-op (3-build recurrence: runs 054, 056, 057)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # WAL mode persists on the DB file — set only in init_db(), not per-connection
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=5000')
        g.db = conn
    try:
        yield g.db
    finally:
        pass  # Connection closed in teardown

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize database schema.
    Uses raw sqlite3.connect(), NOT get_db() — executescript() issues
    implicit COMMIT that breaks context manager contract (brainstorm refinement #1).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    result = conn.execute('PRAGMA journal_mode').fetchone()
    assert result[0] == 'wal', f'WAL mode failed: got {result[0]}'
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
```

**Context manager rule:** All route handlers use `with get_db() as conn:`. Never `conn = get_db()`.

## Model Functions

All functions live in `prompt-dashboard/app/models.py`. Every cross-agent function includes return type + usage example.

### Prompt CRUD

```python
import json
import re
import sqlite3

def create_prompt(conn: sqlite3.Connection, name: str, description: str,
                  system_prompt: str, user_prompt: str, tag_names: list[str]) -> int:
    """Create a prompt and its initial version. Sets tags.
    Calls extract_variables() internally on system_prompt + user_prompt
    to compute the variables JSON field. Routes do NOT call extract_variables.
    Returns: int (the new prompt's ID)
    Usage:
        prompt_id = create_prompt(conn, name, desc, sys, usr, tags)
        redirect(url_for('prompts.detail', prompt_id=prompt_id))
    Commits: internally (BEGIN IMMEDIATE)
    Transaction pattern:
        try:
            conn.execute('BEGIN IMMEDIATE')
            variables = json.dumps(extract_variables(system_prompt + ' ' + user_prompt))
            cursor = conn.execute('INSERT INTO prompts ...', (...,))
            prompt_id = cursor.lastrowid
            conn.execute('INSERT INTO prompt_versions ...', (...,))
            set_prompt_tags(conn, prompt_id, tag_names)
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
        return prompt_id
    """

def get_prompt(conn: sqlite3.Connection, prompt_id: int) -> sqlite3.Row | None:
    """Get a single prompt by ID.
    Returns: sqlite3.Row or None
    Usage:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None: abort(404)
    Commits: no (read-only)
    """

def get_all_prompts(conn: sqlite3.Connection,
                    search_query: str | None = None,
                    tag_name: str | None = None) -> list[sqlite3.Row]:
    """List all prompts, optionally filtered by FTS5 search and/or tag.
    Calls sanitize_fts_query() internally. FTS5 MATCH uses parameterized
    binding (MATCH ?) — never string interpolation, even with sanitized input.
    If sanitize_fts_query returns None, skips MATCH and returns all prompts.
    Returns: list[sqlite3.Row]
    Usage:
        prompts = get_all_prompts(conn, search_query='hello', tag_name='coding')
    Commits: no (read-only)
    """

def update_prompt(conn: sqlite3.Connection, prompt_id: int, name: str,
                  description: str, system_prompt: str, user_prompt: str,
                  tag_names: list[str]) -> int:
    """Update prompt and create a new version. Returns new version_id.
    Calls extract_variables() internally (same as create_prompt).
    Returns: int (the new version's ID)
    Usage:
        version_id = update_prompt(conn, prompt_id, name, desc, sys, usr, tags)
        redirect(url_for('prompts.detail', prompt_id=prompt_id))
    Commits: internally (BEGIN IMMEDIATE — same transaction pattern as create_prompt)
    """

def delete_prompt(conn: sqlite3.Connection, prompt_id: int) -> None:
    """Delete a prompt and all its versions, tags, and test runs (CASCADE).
    Returns: None
    Usage:
        delete_prompt(conn, prompt_id)
        redirect(url_for('dashboard.index'))
    Commits: internally
    """
```

### Version History

```python
def get_prompt_versions(conn: sqlite3.Connection,
                        prompt_id: int) -> list[sqlite3.Row]:
    """Get all versions for a prompt, newest first.
    Returns: list[sqlite3.Row] (version_number, system_prompt, user_prompt, variables, created_at)
    Usage:
        versions = get_prompt_versions(conn, prompt_id)
    Commits: no (read-only)
    """

def get_prompt_version(conn: sqlite3.Connection,
                       version_id: int) -> sqlite3.Row | None:
    """Get a specific version by ID.
    Returns: sqlite3.Row or None
    Usage:
        version = get_prompt_version(conn, version_id)
        if version is None: abort(404)
    Commits: no (read-only)
    """
```

### Variable System

```python
def extract_variables(text: str) -> list[str]:
    """Extract {{variable_name}} placeholders from text.
    Returns: list[str] (unique variable names, preserving first-occurrence order)
    Usage:
        vars = extract_variables('Hello {{name}}, you are {{role}}')
        # vars = ['name', 'role']
    """

def substitute_variables(text: str, variables: dict[str, str]) -> str:
    """Replace {{variable_name}} with values from variables dict.
    Returns: str (text with variables substituted)
    Usage:
        result = substitute_variables('Hello {{name}}', {'name': 'Alice'})
        # result = 'Hello Alice'
    """
```

### Tags

```python
def get_all_tags(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all tags, ordered by name.
    Returns: list[sqlite3.Row] (id, name)
    Usage:
        tags = get_all_tags(conn)
    Commits: no (read-only)
    """

def set_prompt_tags(conn: sqlite3.Connection, prompt_id: int,
                    tag_names: list[str]) -> None:
    """Replace all tags for a prompt. Creates new tags as needed.
    Returns: None
    Usage:
        set_prompt_tags(conn, prompt_id, ['coding', 'creative'])
    Commits: does NOT commit (called within create_prompt/update_prompt transaction)
    """

def get_prompt_tags(conn: sqlite3.Connection,
                    prompt_id: int) -> list[sqlite3.Row]:
    """Get tags for a prompt.
    Returns: list[sqlite3.Row] (id, name)
    Usage:
        tags = get_prompt_tags(conn, prompt_id)
    Commits: no (read-only)
    """
```

### Test Runs

```python
def create_test_run(conn: sqlite3.Connection, prompt_version_id: int,
                    model_name: str, variables_used: dict,
                    response_text: str | None, input_tokens: int | None,
                    output_tokens: int | None, duration_ms: int | None,
                    error: str | None = None) -> int:
    """Create a test run record. Updates prompt.last_tested_at.
    Returns: int (the new run's ID)
    Usage:
        run_id = create_test_run(conn, version_id, 'claude-sonnet-4-5-20250514',
                                 {'name': 'Alice'}, 'Hello!', 100, 50, 1200)
    Commits: internally
    """

def get_test_run(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    """Get a test run by ID.
    Returns: sqlite3.Row or None
    Usage:
        run = get_test_run(conn, run_id)
        if run is None: abort(404)
    Commits: no (read-only)
    """

def get_test_runs_for_prompt(conn: sqlite3.Connection,
                             prompt_id: int,
                             limit: int = 50) -> list[sqlite3.Row]:
    """Get test runs for a prompt (across all versions), newest first.
    Returns: list[sqlite3.Row] (up to `limit` rows)
    Usage:
        runs = get_test_runs_for_prompt(conn, prompt_id, limit=5)
    Note: push LIMIT into SQL, do NOT fetch all + slice in Python.
    Commits: no (read-only)
    """
```

### Dashboard Stats

```python
def get_dashboard_stats(conn: sqlite3.Connection) -> dict:
    """Get dashboard summary stats.
    Returns: dict with keys: total_prompts, total_versions, total_tests
    Usage:
        stats = get_dashboard_stats(conn)
        # stats = {'total_prompts': 5, 'total_versions': 12, 'total_tests': 30}
    Commits: no (read-only)
    """
```

### FTS5 Search Sanitization (FC36)

```python
def sanitize_fts_query(query: str) -> str | None:
    """Sanitize user input for FTS5 MATCH to prevent operator injection.
    Strips * " ( ) : ^ \\ characters, collapses whitespace, wraps in quotes.
    Returns None if query is empty after sanitization (caller skips MATCH).
    Returns: str | None (safe query string, or None to skip search)
    Usage:
        safe = sanitize_fts_query('name:* OR "hack"')
        # safe = '"name OR hack"'
        safe = sanitize_fts_query('\\')
        # safe = None (all chars stripped — skip FTS5 MATCH, return all prompts)
    Implementation:
        cleaned = re.sub(r'[*"():^\\\]', '', query).strip()
        if not cleaned:
            return None
        return f'"{cleaned}"'
    """
```

## Route Table

| Method | Path | Handler | Status | Template |
|--------|------|---------|--------|----------|
| GET | `/` | `dashboard.index` | 200 | `dashboard/index.html` |
| GET | `/prompts/new` | `prompts.create_form` | 200 | `prompts/create.html` |
| POST | `/prompts/create` | `prompts.create` | 302 → `prompts.detail` | redirect |
| GET | `/prompts/<int:prompt_id>` | `prompts.detail` | 200 | `prompts/detail.html` |
| GET | `/prompts/<int:prompt_id>/edit` | `prompts.edit_form` | 200 | `prompts/edit.html` |
| POST | `/prompts/<int:prompt_id>/edit` | `prompts.update` | 302 → `prompts.detail` | redirect |
| POST | `/prompts/<int:prompt_id>/delete` | `prompts.delete` | 302 → `dashboard.index` | redirect |
| GET | `/prompts/<int:prompt_id>/versions` | `prompts.versions` | 200 | `prompts/versions.html` |
| GET | `/prompts/<int:prompt_id>/diff` | `prompts.diff` | 200 | `prompts/diff.html` |
| GET | `/testing/<int:prompt_id>` | `testing.test_form` | 200 | `testing/run.html` |
| POST | `/testing/<int:prompt_id>` | `testing.execute` | 200 | `testing/result.html` |
| GET | `/testing/runs/<int:run_id>` | `testing.view_run` | 200 | `testing/result.html` |

**Blueprint registration:**
- `dashboard_bp`: `url_prefix='/'`
- `prompts_bp`: `url_prefix='/prompts'`
- `testing_bp`: `url_prefix='/testing'`

**Route decorator paths are RELATIVE to blueprint prefix (FC7):**
- `dashboard.index`: `@bp.route('/')`
- `prompts.create_form`: `@bp.route('/new')`
- `prompts.detail`: `@bp.route('/<int:prompt_id>')`
- `testing.test_form`: `@bp.route('/<int:prompt_id>')`

## Template Render Context

Every `render_template()` call with exact variable names:

```python
# dashboard/index.html expects:
render_template('dashboard/index.html',
    prompts=get_all_prompts(conn, search_query, tag_name),
    tags=get_all_tags(conn),
    stats=get_dashboard_stats(conn),
    search_query=search_query,       # str | None — current search term
    selected_tag=tag_name             # str | None — current tag filter
)

# prompts/create.html expects:
render_template('prompts/create.html',
    tags=get_all_tags(conn)           # list[Row] — for tag checkboxes
)

# prompts/detail.html expects:
render_template('prompts/detail.html',
    prompt=prompt,                     # Row — the prompt
    tags=get_prompt_tags(conn, prompt_id),  # list[Row] — prompt's tags
    versions=get_prompt_versions(conn, prompt_id),  # list[Row] — version history
    recent_runs=get_test_runs_for_prompt(conn, prompt_id, limit=5)  # list[Row] — last 5 runs
)

# prompts/edit.html expects:
render_template('prompts/edit.html',
    prompt=prompt,                     # Row — the prompt
    tags=get_all_tags(conn),           # list[Row] — all tags for checkboxes
    prompt_tags=[t['name'] for t in get_prompt_tags(conn, prompt_id)]  # list[str] — selected tag names
)

# prompts/versions.html expects:
render_template('prompts/versions.html',
    prompt=prompt,                     # Row — the prompt
    versions=get_prompt_versions(conn, prompt_id)  # list[Row] — all versions
)

# prompts/diff.html expects:
render_template('prompts/diff.html',
    prompt=prompt,                     # Row — the prompt
    v1=version1,                       # Row — first version
    v2=version2,                       # Row — second version
    system_diff=system_diff_html,      # str — HTML diff of system prompts
    user_diff=user_diff_html           # str — HTML diff of user prompts
)

# testing/run.html expects:
render_template('testing/run.html',
    prompt=prompt,                     # Row — the prompt being tested
    variables=json.loads(prompt['variables'])  # list[str] — variable names to fill
)

# testing/result.html expects:
render_template('testing/result.html',
    prompt=prompt,                     # Row — the prompt
    run=run                            # Row — the test run with response/error
)
```

## Export Names Table

| Name | Type | Defined By | Used By |
|------|------|------------|---------|
| `create_prompt` | model function | `app/models.py` | `prompts_routes` agent |
| `get_prompt` | model function | `app/models.py` | `prompts_routes`, `testing_routes` |
| `get_all_prompts` | model function | `app/models.py` | `dashboard_routes` agent |
| `update_prompt` | model function | `app/models.py` | `prompts_routes` agent |
| `delete_prompt` | model function | `app/models.py` | `prompts_routes` agent |
| `get_prompt_versions` | model function | `app/models.py` | `prompts_routes` agent |
| `get_prompt_version` | model function | `app/models.py` | `prompts_routes` agent |
| `extract_variables` | model function | `app/models.py` | (internal — called by create/update_prompt) |
| `substitute_variables` | model function | `app/models.py` | `testing_routes` agent |
| `get_all_tags` | model function | `app/models.py` | `prompts_routes`, `dashboard_routes` |
| `set_prompt_tags` | model function | `app/models.py` | (internal — called by create/update_prompt) |
| `get_prompt_tags` | model function | `app/models.py` | `prompts_routes` agent |
| `create_test_run` | model function | `app/models.py` | `testing_routes` agent |
| `get_test_run` | model function | `app/models.py` | `testing_routes` agent |
| `get_test_runs_for_prompt` | model function | `app/models.py` | `prompts_routes` agent |
| `get_dashboard_stats` | model function | `app/models.py` | `dashboard_routes` agent |
| `sanitize_fts_query` | model function | `app/models.py` | (internal — called by get_all_prompts) |
| `get_db` | db function | `app/database.py` | ALL route agents |
| `init_db` | db function | `app/database.py` | `core` agent (app factory) |
| `close_db` | db function | `app/database.py` | `core` agent (app factory) |
| `dashboard.index` | endpoint | `app/blueprints/dashboard/routes.py` | `layout` (navbar), `prompts_routes` (redirect after delete) |
| `prompts.create_form` | endpoint | `app/blueprints/prompts/routes.py` | `layout` (navbar), `dashboard_templates` (new button) |
| `prompts.create` | endpoint | `app/blueprints/prompts/routes.py` | `prompts_templates` (create form action) |
| `prompts.detail` | endpoint | `app/blueprints/prompts/routes.py` | `prompts_routes` (redirect after create/update), `dashboard_templates` (prompt links) |
| `prompts.edit_form` | endpoint | `app/blueprints/prompts/routes.py` | `prompts_templates` (detail page edit button) |
| `prompts.update` | endpoint | `app/blueprints/prompts/routes.py` | `prompts_templates` (edit form action) |
| `prompts.delete` | endpoint | `app/blueprints/prompts/routes.py` | `prompts_templates` (detail page delete button) |
| `prompts.versions` | endpoint | `app/blueprints/prompts/routes.py` | `prompts_templates` (detail page versions link) |
| `prompts.diff` | endpoint | `app/blueprints/prompts/routes.py` | `prompts_templates` (versions page diff links) |
| `testing.test_form` | endpoint | `app/blueprints/testing/routes.py` | `prompts_templates` (detail page test button) |
| `testing.execute` | endpoint | `app/blueprints/testing/routes.py` | `testing_templates` (run form action) |
| `testing.view_run` | endpoint | `app/blueprints/testing/routes.py` | `prompts_templates` (detail page run links), `testing_templates` (redirect after test) |
| `dashboard` | blueprint name | `app/blueprints/dashboard/routes.py` | `core` agent (registration) |
| `prompts` | blueprint name | `app/blueprints/prompts/routes.py` | `core` agent (registration) |
| `testing` | blueprint name | `app/blueprints/testing/routes.py` | `core` agent (registration) |
| `register_seed_command` | CLI function | `app/seed.py` | `core` agent (app factory) |
| `templates/base.html` | template | `layout` agent | ALL template agents (extends) |
| `templates/dashboard/index.html` | template | `dashboard_templates` agent | `dashboard_routes` agent |
| `templates/prompts/create.html` | template | `prompts_templates` agent | `prompts_routes` agent |
| `templates/prompts/edit.html` | template | `prompts_templates` agent | `prompts_routes` agent |
| `templates/prompts/detail.html` | template | `prompts_templates` agent | `prompts_routes` agent |
| `templates/prompts/versions.html` | template | `prompts_templates` agent | `prompts_routes` agent |
| `templates/prompts/diff.html` | template | `prompts_templates` agent | `prompts_routes` agent |
| `templates/testing/run.html` | template | `testing_templates` agent | `testing_routes` agent |
| `templates/testing/result.html` | template | `testing_templates` agent | `testing_routes` agent |

## Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `app/database.py` | `app/blueprints/prompts/routes.py` | `from app.database import get_db` |
| `app/database.py` | `app/blueprints/testing/routes.py` | `from app.database import get_db` |
| `app/database.py` | `app/blueprints/dashboard/routes.py` | `from app.database import get_db` |
| `app/database.py` | `app/__init__.py` | `from .database import init_db, close_db` |
| `app/models.py` | `app/blueprints/prompts/routes.py` | `from app.models import create_prompt, get_prompt, update_prompt, delete_prompt, get_prompt_versions, get_prompt_version, get_prompt_tags, get_all_tags, get_test_runs_for_prompt` |
| `app/models.py` | `app/blueprints/testing/routes.py` | `from app.models import get_prompt, substitute_variables, create_test_run, get_test_run` |
| `app/models.py` | `app/blueprints/dashboard/routes.py` | `from app.models import get_all_prompts, get_all_tags, get_dashboard_stats` |
| `app/models.py` | `app/seed.py` | `from app.models import create_prompt` |
| `app/database.py` | `app/seed.py` | `from app.database import get_db` |
| `app/seed.py` | `app/__init__.py` | `from .seed import register_seed_command` |

## Input Validation Prescriptions

| Route | Input | Form Field Name | Validation | Error Response |
|-------|-------|-----------------|------------|----------------|
| `POST /prompts/create` | `name` | `name` | Strip whitespace, 1-200 chars, required | Flash "Name is required", redirect to `prompts.create_form` |
| `POST /prompts/create` | `description` | `description` | Strip whitespace, max 1000 chars, optional | Truncate silently |
| `POST /prompts/create` | `system_prompt` | `system_prompt` | Strip, optional (can be empty) | None |
| `POST /prompts/create` | `user_prompt` | `user_prompt` | Strip, optional (can be empty) | None |
| `POST /prompts/create` | `tags` | `tags` | Comma-separated string, strip each, max 50 chars per tag | Ignore empty tags |
| `POST /prompts/<id>/edit` | same as create | same as create | same as create | same as create, redirect to `prompts.edit_form` |
| `POST /prompts/<id>/delete` | `prompt_id` (URL) | N/A | Must exist in DB | `abort(404)` |
| `GET /prompts/<id>/diff` | `v1`, `v2` (query) | N/A | Both must be int, both must exist, both must belong to prompt_id | Flash "Invalid version", redirect to `prompts.versions` |
| `POST /testing/<id>` | `model` | `model` | Must be one of: `claude-sonnet-4-5-20250514`, `claude-haiku-4-5-20251001` | Default to `claude-sonnet-4-5-20250514` |
| `POST /testing/<id>` | `var_<name>` | `var_<name>` | One field per variable, string, optional (empty = empty string) | None |
| `GET /prompts/<id>` | `prompt_id` (URL) | N/A | Must exist in DB | `abort(404)` |
| `GET /prompts/<id>/edit` | `prompt_id` (URL) | N/A | Must exist in DB | `abort(404)` |
| `GET /prompts/<id>/versions` | `prompt_id` (URL) | N/A | Must exist in DB | `abort(404)` |
| `GET /testing/<id>` | `prompt_id` (URL) | N/A | Must exist in DB | `abort(404)` |
| `GET /testing/runs/<run_id>` | `run_id` (URL) | N/A | Must exist in DB | `abort(404)` |
| `GET /` | `q` (query) | N/A | Sanitize for FTS5 (FC36): strip `*"():^\`, wrap in quotes | Return all prompts if empty/None |
| `GET /` | `tag` (query) | N/A | Must match existing tag name | Ignore if not found |

## Coordinated Behaviors

| Surface | Rule | Owner |
|---------|------|-------|
| Blueprint registration | All 3 blueprints registered in `create_app()` with `url_prefix` | `core` agent |
| Navbar links | Dashboard (`/`), New Prompt (`/prompts/new`) in navbar | `layout` agent |
| CSRF token syntax | All POST forms use `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` (WITH parentheses) | ALL route agents |
| Base template | All templates extend `base.html` via `{% extends "base.html" %}` | ALL template agents |
| Base template blocks | `{% block title %}`, `{% block content %}` | ALL template agents |
| Timestamps | All timestamps use SQL `datetime('now')`, never Python `datetime.now()` | `models` agent |
| Flash messages | Use `flash(message, category)` with categories: `success`, `error`, `warning`, `info` | ALL route agents |
| Flash display | `base.html` iterates `get_flashed_messages(with_categories=true)` with Bootstrap alerts | `layout` agent |
| API key banner | `base.html` shows warning alert if `not api_key_configured` (from context processor) | `layout` agent |
| CSS framework | Bootstrap 5.3 CDN with `data-bs-theme="dark"` on `<html>` tag | `layout` agent |
| Monospace text | All prompt/code textareas use `font-family: monospace` via CSS class `.mono` | `layout` agent (CSS), ALL template agents (class usage) |
| Delete confirmation | All delete buttons use `onclick="return confirm('Are you sure?')"` | ALL template agents |
| Connection teardown | `app.teardown_appcontext(close_db)` in `create_app()` | `core` agent |
| Context processor | `inject_api_key_status` provides `api_key_configured` to all templates | `core` agent |

## Transaction Contracts

| Function | SQL Operations | Commits | Error Handling |
|----------|---------------|---------|----------------|
| `create_prompt` | INSERT prompts + INSERT prompt_versions + set_prompt_tags | commits internally (BEGIN IMMEDIATE → COMMIT) | try/except/ROLLBACK |
| `update_prompt` | UPDATE prompts + INSERT prompt_versions + set_prompt_tags | commits internally (BEGIN IMMEDIATE → COMMIT) | try/except/ROLLBACK |
| `delete_prompt` | DELETE prompts (CASCADE handles children) | commits internally | try/except/ROLLBACK |
| `set_prompt_tags` | DELETE prompt_tags + INSERT tags + INSERT prompt_tags | does NOT commit (called within create/update transaction) | N/A (caller handles) |
| `create_test_run` | INSERT test_runs + UPDATE prompts.last_tested_at | commits internally | try/except/ROLLBACK |
| All read functions | SELECT only | no commit needed | N/A |

## Authorization Matrix

| Route | Mode | Notes |
|-------|------|-------|
| ALL routes | public | Single-user local tool. No auth. No session keys. No login_required. |

## Claude API Integration

```python
# Testing routes — prescribed exception handling (brainstorm refinement #5)
import anthropic
import time

# Read API key directly from environment, NOT from app.config
# (app.config is visible in Werkzeug debugger when FLASK_DEBUG=1)
import os
api_key = os.environ.get('ANTHROPIC_API_KEY', '')
client = anthropic.Anthropic(api_key=api_key)

AVAILABLE_MODELS = [
    ('claude-sonnet-4-5-20250514', 'Claude Sonnet 4.5'),
    ('claude-haiku-4-5-20251001', 'Claude Haiku 4.5'),
]

start_ms = int(time.time() * 1000)
try:
    response = client.messages.create(
        model=model_name,
        max_tokens=4096,
        system=system_text,       # substituted system prompt
        messages=[{"role": "user", "content": user_text}],  # substituted user prompt
        timeout=60.0,             # 60s timeout (Feed-Forward risk mitigation)
    )
    duration_ms = int(time.time() * 1000) - start_ms
    response_text = response.content[0].text
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    error = None
except anthropic.APITimeoutError:
    duration_ms = int(time.time() * 1000) - start_ms
    response_text = None
    input_tokens = None
    output_tokens = None
    error = "Request timed out after 60 seconds. Try a shorter prompt or a faster model."
except anthropic.APIConnectionError:
    duration_ms = int(time.time() * 1000) - start_ms
    response_text = None
    input_tokens = None
    output_tokens = None
    error = "Could not connect to Claude API. Check your internet connection."
except anthropic.APIStatusError as e:
    duration_ms = int(time.time() * 1000) - start_ms
    response_text = None
    input_tokens = None
    output_tokens = None
    error = f"API error ({e.status_code}). Check your API key and try again."
```

**Rule:** Never expose raw `e.message` to the user. Log full error server-side, show user-friendly message. Store in `test_runs.error`.

## Diff Generation

```python
# In prompts routes — prescribed difflib pattern
import difflib

def generate_diff_html(text1: str, text2: str, label1: str, label2: str) -> str:
    """Generate side-by-side HTML diff using difflib.
    Returns Markup()-wrapped HTML safe for |safe in templates.
    difflib.HtmlDiff escapes content lines internally in Python 3.
    Labels (fromdesc/todesc) are NOT escaped by difflib — we escape them here.
    Usage:
        diff_html = generate_diff_html(v1['system_prompt'], v2['system_prompt'],
                                        f'Version {v1["version_number"]}',
                                        f'Version {v2["version_number"]}')
    Template: {{ system_diff|safe }} — intentional, value is pre-sanitized Markup().
    """
    import html as html_module
    from markupsafe import Markup
    differ = difflib.HtmlDiff(wrapcolumn=80)
    table = differ.make_table(
        text1.splitlines(), text2.splitlines(),
        fromdesc=html_module.escape(label1),
        todesc=html_module.escape(label2),
        context=True, numlines=3
    )
    return Markup(table)
```

**Note:** `generate_diff_html` is defined in `prompts/routes.py`, not in `models.py`, because it's a presentation concern (HTML output), not a data concern.

## Smoke Test File (FC8 Compliance)

```python
# prompt-dashboard/test_smoke.py
"""Smoke tests — run with: .venv/bin/python test_smoke.py"""
import os
import re
os.environ.setdefault("SECRET_KEY", "test-smoke-key")
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

r = client.get("/")
check("GET / (dashboard, 200)", r.status_code == 200, f"got {r.status_code}")

r = client.get("/prompts/new")
check("GET /prompts/new (200)", r.status_code == 200, f"got {r.status_code}")

# --- Phase 2a: CRUD write-side with real CSRF ---

r = client.get("/prompts/new")
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
check("Create form has CSRF token", m is not None,
      "csrf_token input not found -- check {{ csrf_token() }} syntax")

csrf_token = m.group(1) if m else ""

r = client.post("/prompts/create", data={
    "name": "Smoke Test Prompt",
    "description": "A test prompt",
    "system_prompt": "You are {{role}}",
    "user_prompt": "Hello {{name}}",
    "tags": "test, smoke",
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /prompts/create (redirect)", r.status_code == 302,
      f"got {r.status_code}")

# Follow redirect to detail page
r = client.get(r.headers.get('Location', '/prompts/1'))
check("GET /prompts/1 (detail, 200)", r.status_code == 200,
      f"got {r.status_code}")
html = r.data.decode()
check("Detail shows prompt name", "Smoke Test Prompt" in html,
      "prompt name not in detail page")

# --- Phase 2b: Read-side verification ---

r = client.get("/")
html = r.data.decode()
check("Dashboard shows prompt", "Smoke Test Prompt" in html,
      "prompt not on dashboard")
check("Dashboard has navbar", "href=" in html,
      "navbar may be missing")

# --- Phase 3: Version + Edit ---

r = client.get("/prompts/1/edit")
check("GET /prompts/1/edit (200)", r.status_code == 200,
      f"got {r.status_code}")

r = client.get("/prompts/1/versions")
check("GET /prompts/1/versions (200)", r.status_code == 200,
      f"got {r.status_code}")

# --- Phase 4: Search ---

r = client.get("/?q=Smoke")
check("Search returns results", r.status_code == 200,
      f"got {r.status_code}")

# --- Phase 5: Testing page (no API key, should show warning) ---

r = client.get("/testing/1")
check("GET /testing/1 (200)", r.status_code == 200,
      f"got {r.status_code}")

# --- Phase 6: Delete ---

r = client.get("/prompts/1")  # Get CSRF from the detail page where delete button lives
html = r.data.decode()
m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
csrf_token = m.group(1) if m else ""

r = client.post("/prompts/1/delete", data={
    "csrf_token": csrf_token,
}, follow_redirects=False)
check("POST /prompts/1/delete (redirect)", r.status_code == 302,
      f"got {r.status_code}")

# --- Summary ---
print(f"\n{'=' * 40}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SMOKE TESTS FAILED")
    exit(1)
```

## Swarm Agent Assignment

**Total agents:** 10
**Total files:** 26
**Validation:** No file appears in multiple assignments

### Validation Log

Three issues found and resolved in the original assignment:

1. **P1 — Missing file:** `test_smoke.py` was fully specified in the plan (Smoke Test File section) but assigned to no agent. Assigned to `core` (natural owner: exercises `create_app()`, lives in project root alongside `run.py`). File count corrected from 24 to 26 (25 original + `test_smoke.py` = 26; recount of original 24 also reveals the count was off by one — actual was 25, now 26 with the addition).
2. **P3 — Intra-agent wiring row:** The Cross-Boundary Wiring Table lists `app/database.py` → `app/__init__.py` as a cross-boundary import. Both files are owned by the `core` agent, so this is an intra-agent import. No conflict. No files reassigned; the spec annotation is harmless but noted here.
3. **P2 — Footer count:** Original said "24 files across 10 agents." Actual corrected count is 26.

---

### Agent: core

**Files:**
- `prompt-dashboard/app/__init__.py`
- `prompt-dashboard/app/database.py`
- `prompt-dashboard/app/schema.sql`
- `prompt-dashboard/run.py`
- `prompt-dashboard/requirements.txt`
- `prompt-dashboard/.env.example`
- `prompt-dashboard/.gitignore`
- `prompt-dashboard/test_smoke.py`

**Responsibility:** App factory, database init/teardown, schema, runner, dependencies, environment config, and smoke tests — all project-root and infrastructure files.

---

### Agent: layout

**Files:**
- `prompt-dashboard/app/templates/base.html`
- `prompt-dashboard/app/static/style.css`

**Responsibility:** Base Jinja2 template with navbar, Bootstrap 5 dark CDN, flash message display, API key warning banner, and shared CSS including `.mono` class.

---

### Agent: models

**Files:**
- `prompt-dashboard/app/models.py`

**Responsibility:** All ~20 model functions: prompt CRUD, version history, variable extraction/substitution, tags, test runs, dashboard stats, and FTS5 sanitization.

---

### Agent: prompts_routes

**Files:**
- `prompt-dashboard/app/blueprints/prompts/__init__.py`
- `prompt-dashboard/app/blueprints/prompts/routes.py`

**Responsibility:** Prompt CRUD routes, version listing, diff generation, and all `/prompts/*` URL handlers.

---

### Agent: testing_routes

**Files:**
- `prompt-dashboard/app/blueprints/testing/__init__.py`
- `prompt-dashboard/app/blueprints/testing/routes.py`

**Responsibility:** Test execution routes including Claude API integration, result viewing, and all `/testing/*` URL handlers.

---

### Agent: dashboard_routes

**Files:**
- `prompt-dashboard/app/blueprints/dashboard/__init__.py`
- `prompt-dashboard/app/blueprints/dashboard/routes.py`

**Responsibility:** Dashboard index route with FTS5 search and tag filtering at `/`.

---

### Agent: prompts_templates

**Files:**
- `prompt-dashboard/app/templates/prompts/create.html`
- `prompt-dashboard/app/templates/prompts/edit.html`
- `prompt-dashboard/app/templates/prompts/detail.html`
- `prompt-dashboard/app/templates/prompts/versions.html`
- `prompt-dashboard/app/templates/prompts/diff.html`

**Responsibility:** All Jinja2 templates for prompt CRUD, version history, and side-by-side diff views.

---

### Agent: testing_templates

**Files:**
- `prompt-dashboard/app/templates/testing/run.html`
- `prompt-dashboard/app/templates/testing/result.html`

**Responsibility:** Test runner form template and result/error display template.

---

### Agent: dashboard_templates

**Files:**
- `prompt-dashboard/app/templates/dashboard/index.html`

**Responsibility:** Dashboard index template with search bar, tag filter UI, prompt cards, and stats display.

---

### Agent: seed

**Files:**
- `prompt-dashboard/app/seed.py`

**Responsibility:** CLI seed command registration and 3 sample prompts with 5 tags for development data.

---

STATUS: PASS

## Feed-Forward

- **Hardest decision:** Two-table version storage. Adds complexity to create/update (must write both tables atomically) but makes dashboard queries trivial. Decision carried from brainstorm.
- **Rejected alternatives:** (1) Jinja2 template engine for variables — too powerful. (2) Single version table — slow dashboard. (3) SPA frontend — overkill. (see brainstorm for full rationale)
- **Least confident:** Claude API synchronous timeout. If 60s timeout + distinct exception handling isn't sufficient, Phase 2 adds async. This is the `verify_first` item — smoke tests should exercise the timeout path with a mock.

## Sources

- **Origin brainstorm:** [docs/brainstorms/2026-06-01-prompting-dashboard-engine-brainstorm.md](docs/brainstorms/2026-06-01-prompting-dashboard-engine-brainstorm.md) — Key decisions: two-table versioning, regex variables, Blueprint modular, Claude-only MVP
- **Spec template:** [docs/templates/shared-spec-flask.md](docs/templates/shared-spec-flask.md)
- **Prior build lessons:** flask-swarm-acid-test (context manager usage), solopreneur-command-center (endpoint registry), client-intake-dashboard (CSRF + XSS), spec-completeness-checker (6 mandatory sections)
