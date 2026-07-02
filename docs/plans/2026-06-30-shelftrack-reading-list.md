---
title: ShelfTrack — Flask + SQLite Reading List
date: 2026-06-30
status: ready
swarm: true
feed_forward:
  risk: "A book route queries by id alone (not id AND user_id), creating a silent IDOR — a non-owner can read/edit/delete another user's book. Ownership must be enforced IN the SQL WHERE of every book route, not as a separate check."
  verify_first: true
---

# ShelfTrack — Flask + SQLite Reading List

## Overview

ShelfTrack is a small multi-user reading-list app. A visitor registers, logs in
(session cookie auth), and manages a private list of Books (title, author,
status ∈ want/reading/done). Users can add, edit, delete, and status-filter
**only their own** books. Server-rendered Jinja2 templates, a navbar, flash
messages, CSRF on every POST. No external APIs. Throwaway validation build —
minimal but real (auth + per-user ownership + CRUD + filter is the needed surface).

This is a **swarm build** (4 agents: scaffold / models / auth / books) chosen to
exercise cross-agent ownership boundaries — the vehicle for the G1+G3 Step 3
coexistence re-validation.

## 1. What exactly is changing?

A new Flask app is created under `shelftrack/` (fresh — no prior ShelfTrack files):
- `shelftrack/__init__.py` — app factory, blueprint registration, `/` and `/health` routes, init-db-on-first-run
- `shelftrack/database.py` — `get_db()` connection helper + schema DDL + `init_db()`
- `shelftrack/auth_utils.py` — `login_required` decorator
- `shelftrack/models.py` — user + book model functions
- `shelftrack/auth.py` — `auth` blueprint (register/login/logout)
- `shelftrack/books.py` — `books` blueprint (list/new/create/edit/update/delete)
- `shelftrack/templates/base.html`, `shelftrack/templates/auth/*.html`, `shelftrack/templates/books/*.html`
- `shelftrack/static/style.css`, `run.py`, `requirements.txt`, `.gitignore`

## 2. What must NOT change?

- No external network/API calls (hard requirement).
- No production data — SQLite file `shelftrack.db` (dev-only), overridable via `DATABASE` env.
- The autopilot control plane, firebreak hooks, or any file outside `shelftrack/`, `run.py`,
  `requirements.txt`, `.gitignore` (except the plan/report artifacts the pipeline writes).
- Existing repo files unrelated to ShelfTrack.

## 3. How will we know it worked?

See **Acceptance Tests** (EARS) below + the smoke test file. Core proof: register →
login → add book → filter → edit → delete works for the owner, and a non-owner gets
404 on another user's book.

## 4. Most likely way this plan is wrong

The Feed-Forward risk: a book route that filters by `id` alone (missing `user_id`)
ships a silent IDOR — passes every HTTP-200 smoke test but leaks/edits others' data.
Mitigation: ownership is baked into the SQL `WHERE id=? AND user_id=?` of
`get_book_for_user`, `update_book`, `delete_book`; routes NEVER query a book by id
alone. The review's flow-trace must verify this on every book route.

---

## Acceptance Tests (EARS)

### Happy Path
- WHEN a visitor submits `/register` with a unique username + matching passwords THE SYSTEM SHALL create a user row (hashed password) and redirect (302) to `/login`.
- WHEN a registered user submits `/login` with correct credentials THE SYSTEM SHALL set `session['user_id']` + `session['username']` and redirect (302) to `/books`.
- WHEN a logged-in user submits `/books` (POST) with title, author, status=want THE SYSTEM SHALL insert a book with `user_id` = current user and redirect (302) to `/books`.
- WHEN a logged-in user GETs `/books?status=reading` THE SYSTEM SHALL show only that user's books with status=reading.
- WHEN a logged-in user submits `/books/<id>/edit` (POST) for a book they own THE SYSTEM SHALL update it and redirect (302) to `/books`.
- WHEN a logged-in user submits `/books/<id>/delete` (POST) for a book they own THE SYSTEM SHALL delete it and redirect (302) to `/books`.
- WHEN a logged-in user submits `/logout` (POST) THE SYSTEM SHALL call `session.clear()` and redirect (302) to `/login`.

### Error Cases
- WHEN a visitor submits `/register` with a duplicate username THE SYSTEM SHALL re-render the form with a flash error and create NO row.
- WHEN a visitor submits `/register` with mismatched passwords or blank fields THE SYSTEM SHALL re-render with a flash error and create NO row.
- WHEN a visitor submits `/login` with wrong credentials THE SYSTEM SHALL flash an error, set NO session, and re-render `/login`.
- WHEN an anonymous visitor GETs `/books` (or any book route) THE SYSTEM SHALL redirect (302) to `/login`.
- WHEN a logged-in user requests `/books/<id>/edit` or `/delete` for a book they do NOT own (or that does not exist) THE SYSTEM SHALL `abort(404)` (never 403 — do not leak existence).
- WHEN a book is submitted with `status` not in {want,reading,done} THE SYSTEM SHALL flash an error and NOT write the row.
- WHEN any POST omits a valid CSRF token THE SYSTEM SHALL reject with 400.
- WHEN the app starts without `SECRET_KEY` in the environment THE SYSTEM SHALL raise RuntimeError (fail closed) and not serve.

### Verification Commands
- `.venv/bin/python test_smoke.py` — all smoke checks pass (register/login/CSRF/add/filter/ownership-404).
- `python -c "import ast,glob; [ast.parse(open(f).read()) for f in glob.glob('shelftrack/**/*.py',recursive=True)]"` — all modules parse.
- Manual: register two users, add a book as user A, attempt `/books/<A_book_id>/edit` while logged in as user B → 404.

---

## App Configuration (`shelftrack/__init__.py` — scaffold agent)

```python
import os
from flask import Flask, redirect, url_for, session
from flask_wtf import CSRFProtect
from shelftrack.database import get_db, init_db

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    secret = os.environ.get('SECRET_KEY')
    if not secret:
        raise RuntimeError('SECRET_KEY environment variable is required')
    app.config['SECRET_KEY'] = secret

    app.config['DATABASE'] = os.environ.get('DATABASE', 'shelftrack.db')
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

    csrf.init_app(app)

    from shelftrack.auth import bp as auth_bp
    from shelftrack.books import bp as books_bp
    app.register_blueprint(auth_bp)                       # url_prefix=''
    app.register_blueprint(books_bp, url_prefix='/books')

    app.teardown_appcontext(_close_db)   # register BEFORE init-db block to avoid leaking the init connection

    # init db on first run
    with app.app_context():
        db_path = app.config['DATABASE']
        if db_path == ':memory:' or not os.path.exists(db_path):
            init_db(get_db())

    @app.route('/')
    def index():
        if session.get('user_id'):
            return redirect(url_for('books.list'))
        return redirect(url_for('auth.login'))

    @app.route('/health')
    def health():
        return 'ok', 200

    return app

def _close_db(exc):
    from flask import g
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

**Rules:** SECRET_KEY fail-closed (no dev fallback). DATABASE from env. SESSION_COOKIE_SECURE conditional on production (never unconditional True — breaks local HTTP).

## Database Connection + Schema (`shelftrack/database.py` — scaffold agent)

```python
import sqlite3
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('want','reading','done')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_books_user_id ON books(user_id);
"""

def _connect(db_path):
    if db_path == ':memory:':
        conn = sqlite3.connect('file::memory:?cache=shared', uri=True, autocommit=True)
    else:
        conn = sqlite3.connect(db_path, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA synchronous=NORMAL')
    if db_path != ':memory:':
        conn.execute('PRAGMA journal_mode=WAL')
    return conn

def get_db():
    if 'db' not in g:
        g.db = _connect(current_app.config.get('DATABASE', 'shelftrack.db'))
    return g.db

def init_db(conn):
    conn.executescript(SCHEMA)
```

**Rules:** `autocommit=True` (NOT `isolation_level=None` — silent-commit no-op, BrewOps 3x P1). `get_db()` is a plain function, NOT a context manager. PRAGMAs on every connection. `init_db` uses `executescript` for the multi-statement schema at startup only (idempotent via IF NOT EXISTS; not inside an outer `with conn:`).

**Requires Python ≥ 3.12 for the sqlite3 `autocommit=` kwarg (build env is 3.14.6 — OK). `DATABASE=:memory:` is UNSUPPORTED (shared-cache in-memory DB is destroyed when the last connection closes under per-request open/close); always use a file path (smoke test uses a temp file).**

## login_required decorator (`shelftrack/auth_utils.py` — scaffold agent)

```python
from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped
```

---

## Model Functions (`shelftrack/models.py` — models agent)

All writes run under `autocommit=True` → each single-statement `conn.execute` commits
immediately. Ownership is enforced IN the WHERE clause of every book read/update/delete.

**Password hashing:** The `auth` register route MUST hash passwords with `from werkzeug.security import generate_password_hash` → `generate_password_hash(password)` before passing to `create_user`. The login route MUST verify with `check_password_hash(user['password_hash'], password)`. werkzeug ships with Flask — no new dependency. `create_user` stores the **already-hashed** value it receives; it never hashes raw passwords itself.

```python
import sqlite3

# Returns: int (new user id). Raises sqlite3.IntegrityError on duplicate username.
# Usage: user_id = create_user(conn, username, password_hash)
def create_user(conn: sqlite3.Connection, username: str, password_hash: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash))
    return cur.lastrowid

# Returns: sqlite3.Row or None
# Usage: user = get_user_by_username(conn, username); if user is None: ...
def get_user_by_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

# Returns: int (new book id)
# Usage: book_id = create_book(conn, user_id, title, author, status)
def create_book(conn: sqlite3.Connection, user_id: int, title: str, author: str, status: str) -> int:
    cur = conn.execute(
        "INSERT INTO books (user_id, title, author, status) VALUES (?, ?, ?, ?)",
        (user_id, title, author, status))
    return cur.lastrowid

# Returns: list[sqlite3.Row] (this user's books, optionally filtered by status, newest first)
# Usage: books = get_books_for_user(conn, user_id, status)   # status None = all
def get_books_for_user(conn: sqlite3.Connection, user_id: int, status: str | None = None) -> list:
    if status:
        return conn.execute(
            "SELECT * FROM books WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
            (user_id, status)).fetchall()
    return conn.execute(
        "SELECT * FROM books WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)).fetchall()

# Returns: sqlite3.Row or None — ownership-scoped (id AND user_id). None => not owned/absent.
# Usage: book = get_book_for_user(conn, book_id, user_id); if book is None: abort(404)
def get_book_for_user(conn: sqlite3.Connection, book_id: int, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM books WHERE id = ? AND user_id = ?", (book_id, user_id)).fetchone()

# Returns: int (rowcount; 0 = not owned / not found => caller aborts 404)
# Usage: n = update_book(conn, book_id, user_id, title, author, status); if n == 0: abort(404)
def update_book(conn: sqlite3.Connection, book_id: int, user_id: int, title: str, author: str, status: str) -> int:
    cur = conn.execute(
        "UPDATE books SET title=?, author=?, status=?, updated_at=datetime('now') "
        "WHERE id=? AND user_id=?",
        (title, author, status, book_id, user_id))
    return cur.rowcount

# Returns: int (rowcount; 0 = not owned / not found => caller aborts 404)
# Usage: n = delete_book(conn, book_id, user_id); if n == 0: abort(404)
def delete_book(conn: sqlite3.Connection, book_id: int, user_id: int) -> int:
    cur = conn.execute("DELETE FROM books WHERE id=? AND user_id=?", (book_id, user_id))
    return cur.rowcount
```

---

## Route Table

| Method | Path | Handler (endpoint) | Status | Template | Agent |
|--------|------|--------------------|--------|----------|-------|
| GET | / | index | 302 | redirect | scaffold |
| GET | /health | health | 200 | — | scaffold |
| GET/POST | /register | auth.register | 200 / 302 | auth/register.html | auth |
| GET/POST | /login | auth.login | 200 / 302 | auth/login.html | auth |
| POST | /logout | auth.logout | 302 | redirect | auth |
| GET | /books | books.list | 200 | books/list.html | books |
| GET | /books/new | books.new | 200 | books/form.html | books |
| POST | /books | books.create | 302 | redirect | books |
| GET | /books/<int:book_id>/edit | books.edit | 200 | books/form.html | books |
| POST | /books/<int:book_id>/edit | books.update | 302 | redirect | books |
| POST | /books/<int:book_id>/delete | books.delete | 302 | redirect | books |

(Blueprint `books` has `url_prefix='/books'`; its route decorators are RELATIVE — `@bp.route('')` for list, `@bp.route('/new')`, `@bp.route('/<int:book_id>/edit')`, etc. — never repeat the `/books` prefix, FC7.)

**Explicit `methods=` required on every endpoint** (two endpoints on one path collide or 405 without disjoint methods):
- `books.list` → `@bp.route('', methods=['GET'])`
- `books.create` → `@bp.route('', methods=['POST'])`
- `books.new` → `@bp.route('/new', methods=['GET'])`
- `books.edit` → `@bp.route('/<int:book_id>/edit', methods=['GET'])`
- `books.update` → `@bp.route('/<int:book_id>/edit', methods=['POST'])`
- `books.delete` → `@bp.route('/<int:book_id>/delete', methods=['POST'])`
- `auth.register` / `auth.login` → `methods=['GET', 'POST']`
- `auth.logout` → `methods=['POST']`

## Template Render Context

```python
# auth/register.html expects: (no dynamic vars beyond flash + csrf)
render_template('auth/register.html')

# auth/login.html expects:
render_template('auth/login.html')

# books/list.html expects:
render_template('books/list.html', books=books, current_status=status)   # status: str|None the active filter

# books/form.html expects (shared by new + edit):
render_template('books/form.html', book=book, action=action, statuses=('want','reading','done'))
#   new (GET):         book=None,        action=url_for('books.create')
#   edit (GET):        book=<Row>,       action=url_for('books.update', book_id=book['id'])
#   new validation-error re-render:   book=request.form,  action=url_for('books.create')
#   edit validation-error re-render:  book=request.form,  action=url_for('books.update', book_id=book_id)
#       (use book_id from the URL — NOT book['id'], which may not exist on a form dict)
#
# statuses=('want','reading','done') MUST be passed on EVERY form.html render (new, edit, error re-renders).
#
# None-safe template idiom (build MUST NOT enable StrictUndefined):
#   value="{{ book.title if book else '' }}"
#   {% if book and book.status == s %}selected{% endif %}
```

Every template extends `base.html` via `{% extends "base.html" %}` and fills
`{% block title %}` + `{% block content %}`. `base.html` renders the flash block and
navbar. Book form status `<select>` iterates the `statuses` tuple passed in (or a
literal list) — the three allowed values must match the DB CHECK constraint exactly.

**`books/list.html` empty states:** when `books` is empty, show one of two messages:
- No filter active (`current_status` is None): "You haven't added any books yet."
- Filter active with zero matches: "No books with status '{{ current_status }}'."

**Success flashes (issued by the route before redirect):**
- Book created → `flash('Book added.', 'success')`
- Book updated → `flash('Book updated.', 'success')`
- Book deleted → `flash('Book deleted.', 'success')`
- Registration successful → `flash('Registration successful — please log in.', 'success')` (then redirect to `/login`)

---

## Export Names Table

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `create_app` | factory | `shelftrack/__init__.py` | `run.py`, smoke test | `create_app() -> Flask` |
| `get_db` | model function | `shelftrack/database.py` | `shelftrack/__init__.py` (scaffold), auth agent, books agent | — |
| `init_db` | model function | `shelftrack/database.py` | `shelftrack/__init__.py` (scaffold) | — |
| `login_required` | orchestration entrypoint | `shelftrack/auth_utils.py` | books routes (all), `auth.logout` | `login_required(view: Callable) -> Callable` (decorator) |
| `create_user` | model function | `shelftrack/models.py` | auth agent | — |
| `get_user_by_username` | model function | `shelftrack/models.py` | auth agent | — |
| `create_book` | model function | `shelftrack/models.py` | books agent | — |
| `get_books_for_user` | model function | `shelftrack/models.py` | books agent | — |
| `get_book_for_user` | model function | `shelftrack/models.py` | books agent | — |
| `update_book` | model function | `shelftrack/models.py` | books agent | — |
| `delete_book` | model function | `shelftrack/models.py` | books agent | — |
| `auth` (blueprint) | blueprint | `shelftrack/auth.py` | `shelftrack/__init__.py` | `bp = Blueprint('auth', __name__)` |
| `books` (blueprint) | blueprint | `shelftrack/books.py` | `shelftrack/__init__.py` | `bp = Blueprint('books', __name__)` |
| `auth.register` | endpoint | `shelftrack/auth.py` | `base.html` navbar, login template link | — |
| `auth.login` | endpoint | `shelftrack/auth.py` | `base.html`, index redirect, login_required | — |
| `auth.logout` | endpoint | `shelftrack/auth.py` | `base.html` navbar | — |
| `books.list` | endpoint | `shelftrack/books.py` | `base.html` navbar, index redirect | — |
| `books.new` | endpoint | `shelftrack/books.py` | `base.html` navbar, list template | — |
| `books.create` | orchestration entrypoint | `shelftrack/books.py` | `books/form.html` (action) | `create() -> Response` (route: reads models.create_book) |
| `books.edit` | endpoint | `shelftrack/books.py` | `books/list.html` (edit link) | — |
| `books.update` | orchestration entrypoint | `shelftrack/books.py` | `books/form.html` (action) | `update(book_id: int) -> Response` (route: reads models.update_book) |
| `books.delete` | orchestration entrypoint | `shelftrack/books.py` | `books/list.html` (delete form) | `delete(book_id: int) -> Response` (route: reads models.delete_book) |
| `/` | route path | `shelftrack/__init__.py` | browser, index redirect | — |
| `/health` | route path | `shelftrack/__init__.py` | smoke test | — |
| `/register` | route path | `shelftrack/auth.py` | `base.html` navbar, login link | — |
| `/login` | route path | `shelftrack/auth.py` | `base.html` navbar, index redirect, login_required | — |
| `/logout` | route path | `shelftrack/auth.py` | `base.html` navbar logout form | — |
| `/books` | route path | `shelftrack/books.py` | `base.html` navbar, index redirect | — |
| `/books/new` | route path | `shelftrack/books.py` | `base.html` navbar, list template | — |
| `/books/<int:book_id>/edit` | route path | `shelftrack/books.py` | `books/list.html` (edit link), `books/form.html` (action) | — |
| `/books/<int:book_id>/delete` | route path | `shelftrack/books.py` | `books/list.html` (delete form) | — |

## Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| `shelftrack/database.py` | `shelftrack/__init__.py` | `from shelftrack.database import get_db, init_db` |
| `shelftrack/database.py` | `shelftrack/auth.py` | `from shelftrack.database import get_db` |
| `shelftrack/database.py` | `shelftrack/books.py` | `from shelftrack.database import get_db` |
| `shelftrack/auth_utils.py` | `shelftrack/books.py` | `from shelftrack.auth_utils import login_required` |
| `shelftrack/auth_utils.py` | `shelftrack/auth.py` | `from shelftrack.auth_utils import login_required` (for logout) |
| `shelftrack/models.py` | `shelftrack/auth.py` | `from shelftrack.models import create_user, get_user_by_username` |
| `shelftrack/models.py` | `shelftrack/books.py` | `from shelftrack.models import create_book, get_books_for_user, get_book_for_user, update_book, delete_book` |
| `shelftrack/auth.py` | `shelftrack/__init__.py` | `from shelftrack.auth import bp as auth_bp` |
| `shelftrack/books.py` | `shelftrack/__init__.py` | `from shelftrack.books import bp as books_bp` |

## Input Validation Prescriptions

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| `POST /register` | `username` (form) | strip, 1–50 chars, required | flash "Username is required" (or too long), re-render register.html, no row |
| `POST /register` | `password`, `confirm` (form) | required, len ≥ 6, `password == confirm` | flash "Passwords must match and be ≥6 chars", re-render, no row |
| `POST /register` | duplicate username | caught via `sqlite3.IntegrityError` | flash "Username already taken", re-render, no row |
| `POST /login` | `username`, `password` (form) | required; verify `check_password_hash` | flash "Invalid username or password", re-render login.html, no session |
| `POST /books` | `title`, `author` (form) | strip, 1–200 chars each, required | flash "Title and author are required", re-render form.html, no row |
| `POST /books` | `status` (form) | must be in `('want','reading','done')` | flash "Invalid status", re-render form.html, no row |
| `POST /books/<int:book_id>/edit` | `title`,`author`,`status` + ownership | same field rules; `update_book` rowcount 0 → not owned | flash on field error; `abort(404)` if rowcount 0 |
| `POST /books/<int:book_id>/delete` | `book_id` (URL) + ownership | `delete_book` rowcount 0 → not owned/absent | `abort(404)` if rowcount 0 |
| `GET /books` | `status` (query) | if present must be in allowlist else treat as no filter | ignore invalid value → show all (no error). **Enforcement site pinned to the route:** `status = request.args.get('status'); if status not in ('want','reading','done'): status = None` — then pass sanitized `status` to the model AND to the template as `current_status`. The model receives only a pre-validated value (it uses `if status:` and would silently return an empty list on any typo). |

## Coordinated Behaviors

| Surface | Rule | Owner |
|---------|------|-------|
| Blueprint registration | `auth_bp` (no prefix) + `books_bp` (`url_prefix='/books'`) registered in `create_app()` | scaffold |
| Navbar links | `base.html` shows: logged in → "My Books" (`books.list`), "Add Book" (`books.new`), a POST logout form (`auth.logout`), username; logged out → "Login" (`auth.login`), "Register" (`auth.register`) | scaffold (base.html) |
| CSRF token syntax | ALL POST forms include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` — **WITH parentheses** | ALL route/template agents |
| Session keys | login sets `session['user_id']` (int) + `session['username']` (str); `base.html`, `login_required`, and all book routes read `session.get('user_id')` — exact key match | auth + scaffold |
| Logout method | `/logout` is **POST only** (a form button, never a GET link) — GET logout is CSRF-exploitable | auth |
| Session reset | login does `session.clear()` before setting keys; logout does `session.clear()` (never `session.pop`) — prevents session fixation | auth |
| Flash categories | use `'error'` and `'success'` categories; `base.html` renders `get_flashed_messages(with_categories=true)` | ALL agents |
| Base template | all templates `{% extends "base.html" %}`; blocks `title` + `content` | ALL template agents |
| Timestamps | SQL `datetime('now')`, never Python `datetime.now()` | models |
| Logout CSRF | `base.html` navbar logout form MUST include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` — it is the one POST form not owned by a route agent; CSRFProtect 400s every logout without it | scaffold (base.html) |

## Transaction Contracts

| Function | SQL | Commits |
|----------|-----|---------|
| `create_user` | INSERT users | commits internally (single stmt, autocommit=True) |
| `create_book` | INSERT books | commits internally (single stmt, autocommit=True) |
| `update_book` | UPDATE books WHERE id AND user_id | commits internally (single stmt, autocommit=True) |
| `delete_book` | DELETE books WHERE id AND user_id | commits internally (single stmt, autocommit=True) |
| `get_user_by_username`, `get_books_for_user`, `get_book_for_user` | SELECT | read-only, no commit |
| `init_db` | executescript(SCHEMA) | runs at startup only, idempotent (IF NOT EXISTS) |

## Authorization Matrix

| Route | Mode | Ownership Check |
|-------|------|-----------------|
| `GET /`, `GET /health` | public | N/A |
| `GET/POST /register`, `GET/POST /login` | public | N/A |
| `POST /logout` | role-only (logged in) | N/A |
| `GET /books` | role-only | scoped to `session['user_id']` in query |
| `GET /books/new`, `POST /books` | role-only | new book gets `user_id = session['user_id']` |
| `GET /books/<id>/edit` | role+ownership | `get_book_for_user(conn, book_id, user_id)`; None → `abort(404)` |
| `POST /books/<id>/edit` | role+ownership | `update_book(...)` rowcount 0 → `abort(404)` |
| `POST /books/<id>/delete` | role+ownership | `delete_book(...)` rowcount 0 → `abort(404)` |

**All book routes carry `@login_required` AND scope every query by `session['user_id']`.
Never query a book by `id` alone (Feed-Forward risk / FC35 IDOR).**

---

## Swarm Agent Assignment

| Agent | Role | Files |
|-------|------|-------|
| scaffold | App factory, DB, decorator, base template, static, run/reqs | `shelftrack/__init__.py`, `shelftrack/database.py`, `shelftrack/auth_utils.py`, `shelftrack/templates/base.html`, `shelftrack/static/style.css`, `run.py`, `requirements.txt`, `.gitignore` |
| models | User + book model functions | `shelftrack/models.py` |
| auth | Auth blueprint + templates | `shelftrack/auth.py`, `shelftrack/templates/auth/register.html`, `shelftrack/templates/auth/login.html` |
| books | Books blueprint + templates | `shelftrack/books.py`, `shelftrack/templates/books/list.html`, `shelftrack/templates/books/form.html` |

## File Assignment Boundaries

| File | Agent |
|------|-------|
| shelftrack/__init__.py | scaffold |
| shelftrack/database.py | scaffold |
| shelftrack/auth_utils.py | scaffold |
| shelftrack/templates/base.html | scaffold |
| shelftrack/static/style.css | scaffold |
| run.py | scaffold |
| requirements.txt | scaffold |
| .gitignore | scaffold |
| shelftrack/models.py | models |
| shelftrack/auth.py | auth |
| shelftrack/templates/auth/register.html | auth |
| shelftrack/templates/auth/login.html | auth |
| shelftrack/books.py | books |
| shelftrack/templates/books/list.html | books |
| shelftrack/templates/books/form.html | books |

Note: `shelftrack/__init__.py` is a package marker AND the app factory (scaffold owns it).
No `shelftrack/blueprints/` package is used — blueprints live flat in `shelftrack/auth.py` / `shelftrack/books.py`.
Each template agent creates its own template subdirectory (`shelftrack/templates/auth/`,
`shelftrack/templates/books/`). No file appears under two agents.

**Namespace note (base coexistence):** ShelfTrack lives under its own top-level package
`shelftrack/` — NOT `app/` — because the repo's default branch (the worker worktree base)
already contains an unrelated prior throwaway build under `app/` (a Film Production PM app,
including an `app/models/` package). Using `shelftrack/` avoids import shadowing
(`app/models/` vs `app/models.py`) and any file collision. The pre-existing `app/` tree is
inert for this build — ShelfTrack never imports it — and must NOT be modified (it is outside
ShelfTrack's file assignments). `run.py` imports `from shelftrack import create_app`.

## Smoke Test (FC8 — written to `test_smoke.py`, gitignored, run via `.venv/bin/python test_smoke.py`)

Covers: `/health` 200; `/login` 200 with a rendered `csrf_token` input; register→login
with the extracted CSRF token sets `session['user_id']`; add a book (POST /books) →
302; `/books` lists it; `/books?status=reading` filters; a second user gets 404 editing
the first user's book (ownership). Secrets via `os.environ.setdefault()` inside the file;
`DATABASE` set to a real temp file (never `:memory:`).

---

## Deferred Hardening (throwaway validation build)

The following security items are consciously deferred for this throwaway validation build
and must NOT be mistaken for production-ready omissions:

- **Login timing / username enumeration:** no dummy-hash compare on missing user; timing side-channel exists.
- **Login rate limiting:** no brute-force protection.
- **Security headers:** no CSP, X-Content-Type-Options, X-Frame-Options, or HSTS.
- **Password minimum length:** 6 characters (minimal; not production-grade).
- **Post-login redirect:** always lands on `/books`; no `next`-URL redirect.
- **Custom error templates:** Flask defaults for 404 and CSRF-400 (no branded pages).

---

## Feed-Forward

- **Hardest decision:** 404 vs 403 for non-owner book access. Chose 404 (don't leak
  existence) and enforced it by baking `user_id` into the SQL WHERE of every book
  read/update/delete, so a non-owner naturally gets zero rows. This is the single
  security-critical decision (FC35 IDOR).
- **Rejected alternatives:** Flask-Login (over-engineering vs a plain session + decorator);
  SQLAlchemy (stdlib sqlite3 matches the template, explicit transactions); a monolith
  `app.py` (wouldn't exercise the swarm ownership boundaries this run validates).
- **Least confident:** That EVERY book route scopes by `user_id` — a single route that
  queries by `id` alone is a silent IDOR that passes all 200-status smoke tests. The
  review flow-trace must confirm ownership scoping on list, edit, update, and delete.
