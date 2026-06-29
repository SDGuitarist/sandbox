STATUS: PASS

## Swarm Agent Assignment

**Total agents:** 3
**Total files:** 12
**Validation:** No file appears in multiple assignments. All paths are relative to project root (no leading `/`, no `..`). Every file referenced in the Export Names Table and Cross-Boundary Wiring Table is covered by exactly one agent.

---

### Assignment Table

| Role | Files |
|------|-------|
| scaffold | `validation-notes/app/__init__.py`, `validation-notes/app/db.py`, `validation-notes/app/templates/base.html`, `validation-notes/run.py`, `validation-notes/requirements.txt`, `validation-notes/.gitignore` |
| models | `validation-notes/app/models.py` |
| routes | `validation-notes/app/snippets/__init__.py`, `validation-notes/app/snippets/routes.py`, `validation-notes/app/templates/snippets/list.html`, `validation-notes/app/templates/snippets/new.html`, `validation-notes/app/templates/snippets/edit.html` |

---

### Per-Role Notes

- **scaffold** — owns the Flask app factory (`create_app`), the `get_db` connection helper, blueprint registration wiring, the base Jinja2 template, the entry-point runner, and project config files.
- **models** — owns the `snippets` table DDL and all five CRUD functions (`init_db`, `list_snippets`, `get_snippet`, `create_snippet`, `update_snippet`, `delete_snippet`); has no route or template files.
- **routes** — owns the `snippets` blueprint package, all route handlers, and all three snippets-specific templates (`list.html`, `new.html`, `edit.html`); imports models and `get_db` but never writes them.

---

### Shared Interface Spec (copy for each agent — work independently from this)

All agents MUST implement to this exact spec. Do not deviate; cross-agent calls will break if signatures, import paths, or coordinated behaviors differ.

#### 1. Export Names Table

| Name | Type | Defined By | Used By | Full Signature |
|------|------|-----------|---------|----------------|
| `create_app` | function | scaffold | run.py | `def create_app() -> Flask` |
| `get_db` | function | scaffold (app/db.py) | models, routes | `def get_db() -> sqlite3.Connection` |
| `snippets_bp` | blueprint | routes | scaffold | `Blueprint('snippets', __name__, url_prefix='/')` |
| `init_db` | function | models | scaffold | `def init_db(conn) -> None` |
| `list_snippets` | function | models | routes | `def list_snippets(conn) -> list[sqlite3.Row]` |
| `get_snippet` | function | models | routes | `def get_snippet(conn, snippet_id) -> sqlite3.Row \| None` |
| `create_snippet` | function | models | routes | `def create_snippet(conn, title, body) -> int` |
| `update_snippet` | function | models | routes | `def update_snippet(conn, snippet_id, title, body) -> None` |
| `delete_snippet` | function | models | routes | `def delete_snippet(conn, snippet_id) -> None` |

#### 2. Cross-Boundary Wiring Table

| Call | Producer file | Consumer file | Import path |
|------|---------------|---------------|-------------|
| `get_db()` | `app/__init__.py` (via `app/db.py`) | `app/models.py`, `app/snippets/routes.py` | `from app.db import get_db` |
| `init_db(conn)` | `app/models.py` | `app/__init__.py` | `from app.models import init_db` |
| CRUD fns | `app/models.py` | `app/snippets/routes.py` | `from app.models import list_snippets, get_snippet, create_snippet, update_snippet, delete_snippet` |
| `snippets_bp` | `app/snippets/routes.py` | `app/__init__.py` | `from app.snippets.routes import snippets_bp` |

#### 3. Input Validation Prescriptions

| Route | Input | Validation | Error Response |
|-------|-------|-----------|----------------|
| `POST /new` | `title`, `body` | `title` required, ≤200 chars; `body` ≤10000 chars | re-render `new.html` with `flash('Title is required.', 'error')`, HTTP 200 |
| `POST /<id>/edit` | `title`, `body` | same as above; `id` must exist | missing row → `abort(404)`; invalid input → re-render `edit.html` with flash |
| `POST /<id>/delete` | `id` | `id` must exist | missing row → `abort(404)` |

#### 4. Coordinated Behaviors

- Flash: success `flash('<msg>', 'success')` (green), error `flash('<msg>', 'error')` (red); `base.html` renders flashes at top.
- DB access: always `get_db()`; never open raw connections in routes.
- Every route taking `<int:snippet_id>` fetches first; `if row is None: abort(404)` before use.
- All POST forms include no CSRF (no auth, single-user throwaway) — no agent adds a half-wired CSRF token.

#### 5. Transaction Contracts

- `init_db(conn)` — **commits internally.**
- `create_snippet` / `update_snippet` / `delete_snippet` — **commit internally** (each is a single statement + `conn.commit()`).
- `list_snippets` / `get_snippet` — read-only, no commit.

#### 6. Authorization Matrix

| Route | Mode |
|-------|------|
| `GET /` (list) | public |
| `GET /new`, `POST /new` | public |
| `GET /<id>/edit`, `POST /<id>/edit` | public |
| `POST /<id>/delete` | public |

All routes are public by design — this is a throwaway single-user validation harness.

#### Schema (authoritative)

```sql
CREATE TABLE IF NOT EXISTS snippets (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  title      TEXT    NOT NULL,
  body       TEXT    NOT NULL DEFAULT '',
  created_at TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

---

### Agent Detail Blocks

#### Agent: scaffold

**Files:**
- `validation-notes/app/__init__.py`
- `validation-notes/app/db.py`
- `validation-notes/app/templates/base.html`
- `validation-notes/run.py`
- `validation-notes/requirements.txt`
- `validation-notes/.gitignore`

**Responsibility:** Creates the Flask app factory (`create_app`), the `get_db` SQLite connection helper, blueprint registration, the base Jinja2 template with flash rendering, the entry-point runner, and all project config files.

**Key constraints:**
- `create_app()` must call `init_db(get_db())` on startup to ensure the table exists.
- Register `snippets_bp` imported from `app.snippets.routes`.
- `get_db()` returns a `sqlite3.Connection` with `row_factory = sqlite3.Row`.
- `base.html` must render flash messages at the top (loop over `get_flashed_messages(with_categories=True)`).

---

#### Agent: models

**Files:**
- `validation-notes/app/models.py`

**Responsibility:** Defines the `snippets` table DDL and implements all five CRUD functions that routes will import and call.

**Key constraints:**
- All write functions (`create_snippet`, `update_snippet`, `delete_snippet`) commit internally via `conn.commit()`.
- `init_db(conn)` also commits internally.
- `list_snippets` and `get_snippet` are read-only (no commit).
- `get_snippet` returns `sqlite3.Row | None` — never raises on missing id.
- `create_snippet` returns the new row `id` as `int`.

---

#### Agent: routes

**Files:**
- `validation-notes/app/snippets/__init__.py`
- `validation-notes/app/snippets/routes.py`
- `validation-notes/app/templates/snippets/list.html`
- `validation-notes/app/templates/snippets/new.html`
- `validation-notes/app/templates/snippets/edit.html`

**Responsibility:** Implements the `snippets` Flask blueprint with all CRUD route handlers and the three feature templates; imports `get_db` and all model functions — never writes to those files.

**Key constraints:**
- Blueprint must be named exactly `snippets_bp = Blueprint('snippets', __name__, url_prefix='/')`.
- Import: `from app.db import get_db` and `from app.models import list_snippets, get_snippet, create_snippet, update_snippet, delete_snippet`.
- All `<int:snippet_id>` routes fetch first; `if row is None: abort(404)`.
- Validation errors re-render the form template (do not redirect) with a flash error.
- No CSRF tokens.
- Templates extend `base.html`.

---

STATUS: PASS
