---
title: "PlantPal — Flask plant-care tracker (swarm plan + shared interface spec)"
date: 2026-07-23
status: ready
swarm: true
waves: 2
run_type: autopilot-swarm
build_namespace: plantpal/
feed_forward:
  risk: "the cross-wave dict-KEY set is the genuine seam most likely to diverge: the Wave-1 models agent produces the get_dashboard_plants return dict, and the Wave-2 dashboard template consumes its keys — if those drift the dashboard silently renders wrong status or 500s. The needs_water / get_dashboard_plants internal compute (days_since vs status) is an INTERNAL consistency risk owned entirely by the models agent; both functions are in the same file so the only external seam is the dict-key contract (pinned in §6, §9, §10, §13)."
  verify_first: true
---

# PlantPal — Swarm Plan + Shared Interface Spec

> **Build type:** autopilot-swarm, **2 dependent waves**, ~7 worker agents. THROWAWAY
> P4-dress-rehearsal validation build. Minimal but real. ALL application code is
> namespaced under `plantpal/` (never the shared `app/`) per FC59.
>
> **Wave 1 (foundation):** app-factory/scaffold + db lifecycle (`core`), models
> (`models`), session auth + auth templates (`auth`), base template + CSS (`layout`).
> **Wave 2 (feature layer, CONSUMES Wave 1):** plant CRUD (`plants`), watering log
> (`watering`), needs-water dashboard + feature-blueprint registration (`dashboard`).
> Every Wave-2 file imports at least one Wave-1 symbol (`get_db`, `login_required`, a
> `plantpal.models` function, or `{% extends "base.html" %}`).

## 1. Four-Question Quality Gate

- **What exactly is changing?** A brand-new Flask+SQLite app under `plantpal/`: session
  auth (register/login/logout), per-user Plant CRUD, per-plant append-only Watering log,
  and a needs-water dashboard/filter. Nothing else in the repo changes (docs/tools/skills
  untouched).
- **What must NOT change?** No file outside `plantpal/`, `docs/`, `BUILD_TRACKING.md`,
  `.gitignore` (test_smoke ignore). No edits to autopilot SKILL/tools/hooks. No push to
  `origin/master` of build code (Design X). No external APIs/network.
- **How will we know it worked?** The Acceptance Tests (§16, EARS) all pass via the
  prescribed `plantpal/test_smoke.py` (run `.venv/bin/python plantpal/test_smoke.py`),
  and every §5 dress-rehearsal criterion holds (0 interventions, barrier fired from SKILL).
- **Most likely way this plan is wrong?** The cross-wave render-context seam (feed_forward
  risk): the Wave-1 `get_dashboard_plants` dict keys and the Wave-2 dashboard template
  access keys diverge. Mitigated by pinning the exact key set in §9 + §10 + §13.

## 2. App Configuration (`plantpal/__init__.py` — owner: core)

```python
import importlib.util
import os
import sqlite3
from flask import Flask, redirect, url_for
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # SECRET_KEY — env only, fail CLOSED, NO dev fallback, validated BEFORE config (FC69/FC56/FC10)
    # CROSS-NOTE (see §17): any wave-gate import-smoke that calls create_app() MUST first set
    # os.environ.setdefault('SECRET_KEY', 'test-smoke-key') — a bare create_app() raises here.
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        raise RuntimeError('SECRET_KEY environment variable is required')
    app.config['SECRET_KEY'] = secret

    # DATABASE — mapped from env so smoke tests can override (FC49 lesson)
    app.config['DATABASE'] = os.environ.get('DATABASE', 'plantpal.db')

    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'

    csrf.init_app(app)

    from plantpal.database import init_db, close_db
    app.teardown_appcontext(close_db)          # FC3: register the db teardown
    with app.app_context():                    # FC39: init inside an app context
        init_db()

    from plantpal.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    @app.route('/health')
    def health():
        return 'ok', 200

    # Feature blueprints (Wave 2). Late-bound so a Wave-1-only assembly still boots.
    # find_spec distinguishes "module absent" (Wave 1 — skip) from "module present but
    # broken" (import error PROPAGATES — never swallowed, so it is NOT fail-open, FC10).
    if importlib.util.find_spec('plantpal.features') is not None:
        from plantpal.features import register_features
        register_features(app)

    return app
```

**Requirements** (`plantpal/requirements.txt` — owner: core): `Flask`, `flask-wtf`, `Werkzeug`.

## 3. Database Schema (`plantpal/schema.sql` — owner: core)

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    species TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    watering_interval_days INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_plants_user_id ON plants(user_id);

CREATE TABLE IF NOT EXISTS watering_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    watered_at TEXT NOT NULL DEFAULT (datetime('now')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_watering_logs_plant_id ON watering_logs(plant_id);
```

## 4. Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| users | `plantpal/models.py` (models) | auth |
| plants | `plantpal/models.py` (models) | plants, watering, dashboard |
| watering_logs | `plantpal/models.py` (models) | watering, dashboard |

`plantpal/models.py` is the SOLE writer for all three tables. Route modules call model
functions; they never execute SQL directly.

## 5. Database Connection (`plantpal/database.py` — owner: core)

```python
import sqlite3
from flask import current_app, g

def _connect(db_path):
    conn = sqlite3.connect(db_path, autocommit=True)   # Python 3.12+; NOT isolation_level=None
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def get_db():
    if 'db' not in g:
        g.db = _connect(current_app.config['DATABASE'])
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    import os
    conn = get_db()
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, 'schema.sql'), encoding='utf-8') as f:
        conn.executescript(f.read())   # standalone DDL script, NOT inside an outer `with conn:` (FC14)
```

**Usage — plain call, NOT a context manager:** `conn = get_db()`.

## 6. Model Functions (`plantpal/models.py` — owner: models)

All take `conn: sqlite3.Connection` as the first arg. Connection is `autocommit=True`, so
every write commits internally per statement.

```python
# Users
# Usage: user_id = create_user(conn, username, password_hash); session['user_id'] = user_id
def create_user(conn, username: str, password_hash: str) -> int   # returns new user id; raises sqlite3.IntegrityError on dup username
def get_user_by_username(conn, username: str) -> sqlite3.Row | None
def get_user_by_id(conn, user_id: int) -> sqlite3.Row | None

# Plants (all ownership-scoped by user_id)
# Usage: plant_id = create_plant(conn, user_id, name, species, location, interval)
def create_plant(conn, user_id: int, name: str, species: str, location: str, watering_interval_days: int) -> int
def get_plants_for_user(conn, user_id: int) -> list[sqlite3.Row]
# Usage: plant = get_plant_for_user(conn, plant_id, user_id);  if plant is None: abort(404)
def get_plant_for_user(conn, plant_id: int, user_id: int) -> sqlite3.Row | None
# returns rowcount (0 if not owned / not found) — caller treats 0 as 404
def update_plant(conn, plant_id: int, user_id: int, name: str, species: str, location: str, watering_interval_days: int) -> int
def delete_plant(conn, plant_id: int, user_id: int) -> int   # rowcount; cascade deletes watering_logs

# Watering logs (append-only)
# Usage: log_id = create_watering_log(conn, plant_id, note)
def create_watering_log(conn, plant_id: int, note: str) -> int   # watered_at defaults to SQL datetime('now')
def get_watering_logs_for_plant(conn, plant_id: int) -> list[sqlite3.Row]   # newest first
def get_last_watering(conn, plant_id: int) -> sqlite3.Row | None   # most recent, or None

# Needs-water helper (PURE — the load-bearing cross-wave seam, feed_forward risk)
# Returns True if never watered (last_watered_at is None) OR days elapsed >= interval.
# last_watered_at is a SQL 'YYYY-MM-DD HH:MM:SS' UTC string. now defaults to datetime.utcnow().
# EXACT formula (pin — both candidate implementations must produce identical results):
#   parsed = datetime.strptime(last_watered_at, '%Y-%m-%d %H:%M:%S')
#   days_since = (now - parsed).days   # integer timedelta days, floored — NOT calendar-date diff
#   now defaults to datetime.utcnow()
#   returns: last_watered_at is None or days_since >= watering_interval_days
def needs_water(last_watered_at: str | None, watering_interval_days: int, now=None) -> bool

# Dashboard aggregate — returns a list of dicts with EXACTLY these keys (pin: §9, §10, §13):
#   {'id': int, 'name': str, 'species': str, 'location': str,
#    'watering_interval_days': int, 'last_watered_at': str | None,
#    'days_since': int | None, 'status': 'needs_water' | 'ok'}
# INTERNAL CONSISTENCY REQUIREMENT (both fields from ONE shared computation):
#   days_since = (now - parsed).days when last_watered_at is not None, else None
#   status == 'needs_water' iff needs_water(last_watered_at, watering_interval_days) is True
#   Both 'days_since' and 'status' are derived from ONE shared elapsed-days value so
#   the rendered count and status never disagree (all owned by models agent — no cross-agent split).
def get_dashboard_plants(conn, user_id: int) -> list[dict]
```

## 7. Auth (`plantpal/auth.py` — owner: auth)

- `bp = Blueprint('auth', __name__)` (no url_prefix).
- `login_required(view)` decorator: if `'user_id' not in session` → `redirect(url_for('auth.login'))`.
  Exported for Wave-2 route modules.
- Passwords hashed with `werkzeug.security.generate_password_hash` / `check_password_hash`.
- Routes: `GET/POST /register` (`auth.register`), `GET/POST /login` (`auth.login`),
  `POST /logout` (`auth.logout`). On successful register/login: `session['user_id'] = user_id`.
  Logout: `session.clear()`.

## 8. Route Table

| Method | Path | Handler (endpoint) | Status | Template | Owner |
|--------|------|--------------------|--------|----------|-------|
| GET | /health | (core `health`) | 200 | none | core |
| GET | /register | auth.register | 200 | auth/register.html | auth |
| POST | /register | auth.register | 302 | redirect | auth |
| GET | /login | auth.login | 200 | auth/login.html | auth |
| POST | /login | auth.login | 302 | redirect | auth |
| POST | /logout | auth.logout | 302 | redirect | auth |
| GET | / | dashboard.index | 200 | dashboard/index.html | dashboard |
| GET | /plants/ | plants.list | 200 | plants/list.html | plants |
| GET | /plants/new | plants.new | 200 | plants/form.html | plants |
| POST | /plants/ | plants.create | 302 | redirect | plants |
| GET | /plants/<int:plant_id>/edit | plants.edit | 200 | plants/form.html | plants |
| POST | /plants/<int:plant_id>/edit | plants.update | 302 | redirect | plants |
| POST | /plants/<int:plant_id>/delete | plants.delete | 302 | redirect | plants |
| GET | /plants/<int:plant_id>/waterings | watering.list | 200 | watering/list.html | watering |
| POST | /plants/<int:plant_id>/waterings | watering.create | 302 | redirect | watering |

Blueprint url_prefixes: `plants` → `/plants`, `watering` → `/plants`, `dashboard` → (none, `/`),
`auth` → (none). Route decorator paths are RELATIVE to the prefix (FC7): e.g. `plants.list` is
`@bp.route('/')`, not `@bp.route('/plants/')`.

## 9. Template Render Context (exact variable names — cross-wave seam)

```python
# dashboard/index.html (owner: dashboard) expects:
render_template('dashboard/index.html',
    plants=<list[dict] from get_dashboard_plants, optionally filtered>,
    current_filter=<'all' | 'needs_water' | 'ok'>)
# each plant dict is accessed as: plant['id'], plant['name'], plant['species'],
#   plant['location'], plant['watering_interval_days'], plant['last_watered_at'],
#   plant['days_since'], plant['status']   (subscript, NOT attribute — FC62)

# plants/list.html (owner: plants) expects:
render_template('plants/list.html', plants=<list[sqlite3.Row] from get_plants_for_user>)
#   row access: plant['id'], plant['name'], plant['species'], plant['location'], plant['watering_interval_days']

# plants/form.html (owner: plants) expects:
render_template('plants/form.html', plant=<sqlite3.Row | None>, mode=<'new' | 'edit'>, action=<url str>)

# watering/list.html (owner: watering) expects:
render_template('watering/list.html', plant=<sqlite3.Row>, logs=<list[sqlite3.Row] from get_watering_logs_for_plant>)
#   log access: log['watered_at'], log['note']

# auth/login.html, auth/register.html (owner: auth): no special context (flash + csrf only)
```

## 10. Export Names Table

Orchestration-entrypoint rows (FC50) carry a non-empty Full Signature. Noun rows use `—`.
Every **Defined By** first token is an agent role (`core`/`models`/`auth`/`layout`/`plants`/
`watering`/`dashboard`) or `framework`/`all`.

**Route-path coverage note:** raw route path strings from §8 are represented here by their
endpoint-name rows (e.g. `auth.login` covers `/login`, `plants.list` covers `/plants/`,
`dashboard.index` covers `/`); `health` (below) covers `/health`. There is no separate raw-path
row class — the endpoint name is the cross-boundary `url_for` target agents actually use.

| Name | Type | Defined By | Used By | Full Signature |
|------|------|------------|---------|----------------|
| `create_app` | orchestration entrypoint | core | smoke, framework | `create_app() -> Flask` |
| `get_db` | orchestration entrypoint | core | auth, plants, watering, dashboard | `get_db() -> sqlite3.Connection` |
| `close_db` | orchestration entrypoint | core | core (`create_app` teardown) | `close_db(e=None) -> None` |
| `init_db` | orchestration entrypoint | core | core (`create_app`) | `init_db() -> None` |
| `register_features` | orchestration entrypoint | dashboard | core (`create_app`, find_spec-guarded) | `register_features(app: Flask) -> None` |
| `login_required` | orchestration entrypoint | auth | plants, watering, dashboard | `login_required(view: Callable) -> Callable` |
| `needs_water` | model function (helper) | models | models (internal — computes `status` in `get_dashboard_plants`); smoke (asserts formula) | `needs_water(last_watered_at: str \| None, watering_interval_days: int, now=None) -> bool` |
| `get_dashboard_plants` | orchestration entrypoint | models | dashboard | `get_dashboard_plants(conn, user_id: int) -> list[dict]` |
| `create_user` | model function | models | auth | `create_user(conn, username: str, password_hash: str) -> int` |
| `get_user_by_username` | model function | models | auth | `get_user_by_username(conn, username: str) -> sqlite3.Row \| None` |
| `get_user_by_id` | model function | models | auth (session→user lookup) | `get_user_by_id(conn, user_id: int) -> sqlite3.Row \| None` |
| `create_plant` | model function | models | plants | `create_plant(conn, user_id, name, species, location, watering_interval_days) -> int` |
| `get_plants_for_user` | model function | models | plants | `get_plants_for_user(conn, user_id: int) -> list[sqlite3.Row]` |
| `get_plant_for_user` | model function | models | plants, watering | `get_plant_for_user(conn, plant_id, user_id) -> sqlite3.Row \| None` |
| `update_plant` | model function | models | plants | `update_plant(conn, plant_id, user_id, name, species, location, watering_interval_days) -> int` |
| `delete_plant` | model function | models | plants | `delete_plant(conn, plant_id, user_id) -> int` |
| `create_watering_log` | model function | models | watering | `create_watering_log(conn, plant_id, note) -> int` |
| `get_watering_logs_for_plant` | model function | models | watering | `get_watering_logs_for_plant(conn, plant_id) -> list[sqlite3.Row]` |
| `get_last_watering` | model function | models | models (internal — feeds `get_dashboard_plants` last_watered_at) | `get_last_watering(conn, plant_id) -> sqlite3.Row \| None` |
| `auth` | blueprint | auth | core (register) | — |
| `plants` | blueprint | plants | dashboard (features register) | — |
| `watering` | blueprint | watering | dashboard (features register) | — |
| `dashboard` | blueprint | dashboard | dashboard (features register) | — |
| `auth.login` | endpoint | auth | layout (navbar), all templates | — |
| `auth.register` | endpoint | auth | layout (navbar) | — |
| `auth.logout` | endpoint | auth | layout (navbar) | — |
| `plants.list` | endpoint | plants | layout (navbar), dashboard | — |
| `plants.new` | endpoint | plants | plants, layout | — |
| `plants.create` | endpoint | plants | plants | — |
| `plants.edit` | endpoint | plants | plants, dashboard | — |
| `plants.update` | endpoint | plants | plants | — |
| `plants.delete` | endpoint | plants | plants, dashboard | — |
| `watering.list` | endpoint | watering | plants, dashboard | — |
| `watering.create` | endpoint | watering | watering | — |
| `dashboard.index` | endpoint | dashboard | layout (navbar) | — |
| `health` | endpoint | core | smoke (`GET /health`) | — |
| `/health` | route path | core | framework (routing) | — |
| `/register` | route path | auth | framework (routing) | — |
| `/login` | route path | auth | framework (routing) | — |
| `/logout` | route path | auth | framework (routing) | — |
| `/` | route path | dashboard | framework (routing) | — |
| `/plants/` | route path | plants | framework (routing) | — |
| `/plants/new` | route path | plants | framework (routing) | — |
| `/plants/<int:plant_id>/edit` | route path | plants | framework (routing) | — |
| `/plants/<int:plant_id>/delete` | route path | plants | framework (routing) | — |
| `/plants/<int:plant_id>/waterings` | route path | watering | framework (routing) | — |
| `base.html` | template | layout | all template agents (`{% extends %}`) | — |

## 11. Cross-Boundary Wiring Table

Columns: `Symbol | Producer File | Consumer File | Build-Order-Sensitive | Import Path`.
Every producer/consumer is a concrete owned file. No consumer wave precedes its producer wave.
**Within-wave imports are Build-Order-Sensitive = No:** agents in the same wave are authored
blind and in parallel, so their cross-file imports resolve at that wave's ASSEMBLY import-smoke,
not during authoring — a within-wave cross-agent build-order dependency is unsatisfiable and is
rejected by `--validate-schema`. Cross-wave ordering is already enforced by the Wave numbers.

> **Note on the feature-registration hook (intentionally excluded):** `plantpal/__init__.py`
> (core, Wave 1) late-binds to `plantpal/features.py` (dashboard, Wave 2) via a
> `find_spec`-guarded call. That is a REVERSE (Wave1→Wave2) late-bound edge that is NOT
> build-order-sensitive (Wave 1 boots without it), so it is specified in Coordinated
> Behaviors (§13, "Feature blueprint registration"), not here — listing it would misrepresent
> a graceful late-bind as a forward build dependency.

| Symbol | Producer File | Consumer File | Build-Order-Sensitive | Import Path |
|--------|---------------|---------------|-----------------------|-------------|
| `init_db, close_db` | `plantpal/database.py` | `plantpal/__init__.py` | No | `from plantpal.database import init_db, close_db` |
| `create_user, get_user_by_username, get_user_by_id` | `plantpal/models.py` | `plantpal/auth.py` | No | `from plantpal.models import create_user, get_user_by_username, get_user_by_id` |
| `bp (auth)` | `plantpal/auth.py` | `plantpal/__init__.py` | No | `from plantpal.auth import bp as auth_bp` |
| `get_db` | `plantpal/database.py` | `plantpal/auth.py` | No | `from plantpal.database import get_db` |
| `get_db` | `plantpal/database.py` | `plantpal/plants.py` | No | `from plantpal.database import get_db` |
| `get_db` | `plantpal/database.py` | `plantpal/watering.py` | No | `from plantpal.database import get_db` |
| `get_db` | `plantpal/database.py` | `plantpal/dashboard.py` | No | `from plantpal.database import get_db` |
| `login_required` | `plantpal/auth.py` | `plantpal/plants.py` | No | `from plantpal.auth import login_required` |
| `login_required` | `plantpal/auth.py` | `plantpal/watering.py` | No | `from plantpal.auth import login_required` |
| `login_required` | `plantpal/auth.py` | `plantpal/dashboard.py` | No | `from plantpal.auth import login_required` |
| `create_plant, get_plants_for_user, get_plant_for_user, update_plant, delete_plant` | `plantpal/models.py` | `plantpal/plants.py` | No | `from plantpal.models import create_plant, get_plants_for_user, get_plant_for_user, update_plant, delete_plant` |
| `get_plant_for_user, create_watering_log, get_watering_logs_for_plant` | `plantpal/models.py` | `plantpal/watering.py` | No | `from plantpal.models import get_plant_for_user, create_watering_log, get_watering_logs_for_plant` |
| `get_dashboard_plants` | `plantpal/models.py` | `plantpal/dashboard.py` | No | `from plantpal.models import get_dashboard_plants` |
| `bp (plants)` | `plantpal/plants.py` | `plantpal/features.py` | No | `from plantpal.plants import bp as plants_bp` |
| `bp (watering)` | `plantpal/watering.py` | `plantpal/features.py` | No | `from plantpal.watering import bp as watering_bp` |
| `bp (dashboard)` | `plantpal/dashboard.py` | `plantpal/features.py` | No | `from plantpal.dashboard import bp as dashboard_bp` |

## 12. Input Validation Prescriptions

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| `POST /register` | `username` (form) | strip, 1–50 chars, required, unique | flash 'Username taken'/'Username required' ('error'), re-render register |
| `POST /register` | `password` (form) | ≥ 8 chars, required | flash 'Password must be at least 8 characters' ('error'), re-render |
| `POST /login` | `username`, `password` | required; verify hash | flash 'Invalid credentials' ('error'), re-render login |
| `POST /logout` | (none) | no application-level inputs — CSRF token handled globally by flask-wtf | N/A (clears session, redirects to login) |
| `POST /plants/` | `name` | strip, 1–100 chars, required | flash 'Name is required' ('error'), redirect back to form |
| `POST /plants/` | `species`, `location` | strip, 0–100 chars | truncate to 100 |
| `POST /plants/` | `watering_interval_days` | int, 1–365 | flash 'Watering interval must be 1–365 days' ('error'), redirect back |
| `POST /plants/<int:plant_id>/edit` | `plant_id` + fields | ownership (get_plant_for_user) + same field rules | `abort(404)` if not owned; flash on invalid field |
| `POST /plants/<int:plant_id>/delete` | `plant_id` (URL) | ownership | `abort(404)` if delete_plant rowcount == 0 |
| `POST /plants/<int:plant_id>/waterings` | `plant_id` + `note` | ownership; note strip 0–500 | `abort(404)` if not owned |
| any `<int:plant_id>` | URL param | Flask `int` converter | 404 auto on non-int |

## 13. Coordinated Behaviors

| Surface | Rule | Owner |
|---------|------|-------|
| SECRET_KEY | `os.environ.get('SECRET_KEY')`, `raise RuntimeError` if absent, validated BEFORE config; NO fallback (FC69/FC56) | core |
| DB connection | `sqlite3.connect(path, autocommit=True)` + `row_factory=sqlite3.Row` + PRAGMAs foreign_keys=ON, busy_timeout=5000, synchronous=NORMAL, journal_mode=WAL (FC40) | core |
| DB lifecycle | `init_db()` runs inside `with app.app_context()`; `close_db` registered via `app.teardown_appcontext` (FC3/FC39) | core |
| Blueprint registration | `auth` registered in `create_app` (core); `plants`/`watering`/`dashboard` registered by `register_features(app)` | core + dashboard |
| Feature blueprint registration | `create_app` calls `register_features(app)` ONLY if `importlib.util.find_spec('plantpal.features') is not None`; a real ImportError inside `features.py` PROPAGATES (never swallowed — not fail-open, FC10). `register_features` calls `app.register_blueprint` for plants, watering, dashboard bps (each carries its own url_prefix) | core (hook) + dashboard (features.py) |
| Session key | `session['user_id']` (int) is the ONLY session key; set by `auth.login`/`auth.register`, read by `login_required`, `base.html` navbar, and every ownership check | auth + all |
| Navbar links | `base.html` shows Dashboard (`url_for('dashboard.index')`), Plants (`url_for('plants.list')`), Logout (POST form) when `session.get('user_id')`; else Login/Register | layout |
| CSRF token syntax | every POST form includes `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` — WITH parentheses (FC1) | all route/template agents |
| Flash categories | EXACTLY two: `'success'`, `'error'`. Bare `flash('msg')` with no category is a CONTRACT VIOLATION. `base.html` styles by category | all route agents |
| Base template | filename ALWAYS `base.html`; all templates `{% extends "base.html" %}`; blocks `{% block title %}` and `{% block content %}` | layout + all |
| Timestamps | SQL `datetime('now')` for `watered_at`/`created_at`, never Python `datetime.now()` | models |
| Jinja truthiness | after `is`, lowercase `none`/`true`/`false` (FC53); dict keys via subscript `plant['status']` never `plant.status` (FC62) | all template agents |

## 14. Transaction Contracts

Connection is `autocommit=True`, so each `execute()` is its own committed transaction.

| Function | SQL | Commits |
|----------|-----|---------|
| `create_user` | INSERT users | commits internally (autocommit) |
| `create_plant` | INSERT plants | commits internally (autocommit) |
| `update_plant` | UPDATE plants WHERE id AND user_id | commits internally; returns `rowcount` |
| `delete_plant` | DELETE plants WHERE id AND user_id (FK cascade → watering_logs) | commits internally; returns `rowcount` |
| `create_watering_log` | INSERT watering_logs | commits internally (autocommit) |
| `init_db` | `executescript(schema.sql)` | standalone DDL script (NOT inside outer `with conn:`) (FC14) |
| all `get_*` | SELECT | no write |

No multi-table atomic write exists (delete cascade is a single FK-driven statement).

## 15. Authorization Matrix

| Route | Mode | Ownership Check |
|-------|------|-----------------|
| `GET /health` | public | N/A |
| `GET/POST /register` | public | N/A |
| `GET/POST /login` | public | N/A |
| `POST /logout` | role-only (logged-in) | N/A |
| `GET /` (dashboard) | role-only | scoped: only `session['user_id']`'s plants via `get_dashboard_plants` |
| `GET /plants/` | role-only | scoped: `get_plants_for_user(session['user_id'])` |
| `GET /plants/new`, `POST /plants/` | role-only | create bound to `session['user_id']` |
| `GET /plants/<id>/edit`, `POST /plants/<id>/edit` | role+ownership | `get_plant_for_user(plant_id, user_id)` → 404 if None |
| `POST /plants/<id>/delete` | role+ownership | `delete_plant` rowcount == 0 → 404 |
| `GET /plants/<id>/waterings`, `POST /plants/<id>/waterings` | role+ownership | `get_plant_for_user(plant_id, user_id)` → 404 if None |

IDOR rule (FC35): ownership is enforced with `WHERE ... AND user_id = ?` in the model query;
a foreign/missing row returns **404** (not 403) so existence is not leaked.

## 16. Acceptance Tests (EARS)

Verified by `plantpal/test_smoke.py` (§17). `Verify:` gives the exact check.

**Happy path**
- WHEN a new user submits a unique username + ≥8-char password to `POST /register` THE SYSTEM SHALL create the user, set `session['user_id']`, and redirect (302).
  Verify: smoke registers, asserts 302 + `session['user_id']` set.
- WHEN a logged-in user submits a valid plant to `POST /plants/` THE SYSTEM SHALL insert it owned by that user and redirect to the plant list (302).
  Verify: smoke creates a plant, asserts 302 + it appears in `GET /plants/`.
- WHEN a logged-in user logs a watering via `POST /plants/<id>/waterings` on an owned plant THE SYSTEM SHALL append a watering_log row and redirect (302).
  Verify: smoke posts a watering, asserts 302 + it appears in `GET /plants/<id>/waterings`.
- WHEN a plant's days-since-last-watering ≥ its interval (or it was never watered) THE SYSTEM SHALL show it as "needs water" on `GET /` and as "ok" otherwise.
  Verify: smoke asserts `needs_water(None, 7)` is True; a just-watered plant renders status "ok";
  `needs_water('2026-07-16 00:00:00', 7, now=datetime(2026,7,23,0,0,0)) is True` (exactly at the 7-day boundary);
  `needs_water('2026-07-16 00:00:00', 8, now=datetime(2026,7,23,0,0,0)) is False` (strictly below boundary).
- WHEN a logged-in user opens `GET /` THE SYSTEM SHALL render the dashboard (200) with a navbar containing Dashboard/Plants/Logout.
  Verify: smoke asserts 200 + navbar links present.

**Error cases**
- WHEN registration uses an existing username THE SYSTEM SHALL NOT create a duplicate and SHALL flash an error and re-render (200).
  Verify: smoke double-registers, asserts second attempt does not create a 2nd row.
- WHEN a plant is submitted with an empty name OR a non-1..365 interval THE SYSTEM SHALL reject it with a flashed error and no insert.
  Verify: smoke posts empty name, asserts plant count unchanged.
- WHEN user B requests `GET/POST /plants/<id>/edit|delete|waterings` for user A's plant THE SYSTEM SHALL return 404 (IDOR).
  Verify: smoke as user B hits user A's plant id, asserts 404 on edit + delete + waterings.
- WHEN any protected route is requested without a session THE SYSTEM SHALL redirect to `/login` (302).
  Verify: smoke (fresh client) GETs `/plants/`, asserts 302 → `/login`.
- WHEN a POST form omits/uses a malformed CSRF token THE SYSTEM SHALL reject it (400).
  Verify: smoke POSTs `/plants/` without token, asserts 400.

**Verification commands**
- `.venv/bin/python plantpal/test_smoke.py` → prints `ALL SMOKE TESTS PASSED`, exit 0.
- `python3 tools/verify_wave.py --validate-schema --plan <this> --spec-path <this> --root <MAIN>` → `STATUS: CLEARED`.

## 17. Smoke Test File (FC8 compliance — owner: assembly/swarm-runner)

`plantpal/test_smoke.py` follows the template pattern: `os.environ.setdefault('SECRET_KEY', ...)`
and a real `tempfile.NamedTemporaryFile` DATABASE (never `:memory:`, FC49) set inside the file;
`from plantpal import create_app`; a `check(name, cond)` harness; Phase 2a extracts the rendered
`csrf_token` from the login page HTML and POSTs it back (validates `{{ csrf_token() }}`); exits 1
on any failure. Added to `.gitignore` before writing. Run: `.venv/bin/python plantpal/test_smoke.py`.

**Wave-gate import-smoke preamble (MANDATORY):** ANY wave-gate import-smoke that calls
`create_app()` MUST first set `os.environ.setdefault('SECRET_KEY', 'test-smoke-key')` and set a
temp-file `DATABASE` path (reusing the same harness preamble above) — never a bare `create_app()`
call. A bare `create_app()` without `SECRET_KEY` raises `RuntimeError` (fail-closed by design, §2)
and would also write `plantpal.db` into the repo root. This applies to every wave-gate smoke check,
not just the final full smoke test.

## 18. File Assignment Boundaries

No file appears under two agents. Wave-2 agents consume Wave-1 symbols only.

| Agent | Wave | Required | Files |
|-------|------|----------|-------|
| core | 1 | yes | `plantpal/__init__.py`, `plantpal/database.py`, `plantpal/schema.sql`, `plantpal/requirements.txt` |
| models | 1 | yes | `plantpal/models.py` |
| auth | 1 | yes | `plantpal/auth.py`, `plantpal/templates/auth/login.html`, `plantpal/templates/auth/register.html` |
| layout | 1 | yes | `plantpal/templates/base.html`, `plantpal/static/style.css` |
| plants | 2 | yes | `plantpal/plants.py`, `plantpal/templates/plants/list.html`, `plantpal/templates/plants/form.html` |
| watering | 2 | yes | `plantpal/watering.py`, `plantpal/templates/watering/list.html` |
| dashboard | 2 | yes | `plantpal/dashboard.py`, `plantpal/features.py`, `plantpal/templates/dashboard/index.html` |

## Feed-Forward

- **Hardest decision:** How Wave-1's app factory registers Wave-2 blueprints without a
  forward-reference or an ownership violation. Resolved with a `find_spec`-guarded late-bound
  `register_features` hook: Wave 1 boots standalone (feature module absent → skipped), Wave 2
  supplies `plantpal/features.py` (dashboard-owned), and a genuine import error propagates
  (not fail-open). The reverse edge is documented in Coordinated Behaviors, excluded from the
  build-order wiring table.
- **Rejected alternatives:** (1) Wave-2 editing `__init__.py` to add registrations — rejected
  (ownership boundary). (2) Bare `try/except ImportError: pass` around the feature import —
  rejected (fail-open, masks real breakage, FC10). (3) A materialized `needs_water` column —
  rejected (derived state across agent boundaries, FC44); computed on read instead.
- **Least confident:** The cross-wave dict-KEY contract (feed_forward risk). Both `needs_water`
  and `get_dashboard_plants` are owned by the `models` agent (Wave 1, same file), so the
  `days_since`/`status` internal consistency is an intra-agent compute risk — pinned in §6 with
  the exact formula to eliminate it. The genuine cross-wave seam is the dict-key set that the
  Wave-1 `models` agent produces and the Wave-2 `dashboard` template consumes: if those keys
  drift, the dashboard silently renders wrong status or 500s. Pinned in §6, §9, §10, §13; the
  smoke test asserts `needs_water(None, 7) is True`, the 7-day boundary case, and a status render.

## Swarm Agent Assignment

**Total agents:** 7
**Total files:** 19
**Validation:** No file appears in multiple assignments

> **Shared Interface Spec Reference:** All agents must implement against the shared interface
> spec defined in this plan. The authoritative sections are:
> - §2 App Configuration (create_app factory contract, SECRET_KEY fail-closed, feature late-bind)
> - §3 Database Schema (exact DDL — do not alter column names or types)
> - §5 Database Connection (get_db/close_db/init_db signatures and PRAGMA set)
> - §6 Model Functions (every function signature, return type, and the exact needs_water formula)
> - §7 Auth (blueprint name, login_required export, session key = 'user_id')
> - §8 Route Table (handler endpoint names, url_prefixes — FC7: paths are RELATIVE to prefix)
> - §9 Template Render Context (exact variable names and access pattern — subscript not attribute)
> - §10 Export Names Table (all orchestration entrypoints with full signatures — FC50)
> - §11 Cross-Boundary Wiring Table (exact import paths)
> - §12 Input Validation Prescriptions (flash message text, error categories)
> - §13 Coordinated Behaviors (CSRF syntax with parentheses FC1; flash categories 'success'/'error' only; base.html blocks; Jinja subscript FC62; Jinja none/true/false lowercase FC53)
> - §14 Transaction Contracts (autocommit=True — no explicit commit calls needed)
> - §15 Authorization Matrix (ownership via get_plant_for_user → 404 not 403; IDOR rule FC35)
> - §17 Smoke Test preamble (wave-gate import-smoke MUST set SECRET_KEY env before create_app)

---

### Agent: core
**Wave:** 1
**Required:** yes
**Files:**
- `plantpal/__init__.py`
- `plantpal/database.py`
- `plantpal/schema.sql`
- `plantpal/requirements.txt`

**Responsibility:** Implement the Flask app factory (`create_app`), SQLite connection helpers (`get_db`, `close_db`, `init_db`), schema DDL, and the `find_spec`-guarded feature-blueprint late-bind hook — all per §2, §3, §5, §13.

---

### Agent: models
**Wave:** 1
**Required:** yes
**Files:**
- `plantpal/models.py`

**Responsibility:** Implement every model function from §6 including the pure `needs_water` helper (exact formula pinned in §6) and the `get_dashboard_plants` aggregate (exact dict-key set pinned in §6, §9, §13) — the load-bearing cross-wave seam.

---

### Agent: auth
**Wave:** 1
**Required:** yes
**Files:**
- `plantpal/auth.py`
- `plantpal/templates/auth/login.html`
- `plantpal/templates/auth/register.html`

**Responsibility:** Implement the `auth` Blueprint with register/login/logout routes (§7, §8, §12, §15), the exported `login_required` decorator (§10), and the auth templates with CSRF tokens (FC1) and flash-category-aware messages per §13.

---

### Agent: layout
**Wave:** 1
**Required:** yes
**Files:**
- `plantpal/templates/base.html`
- `plantpal/static/style.css`

**Responsibility:** Implement the `base.html` master template with `{% block title %}` and `{% block content %}` blocks, session-conditional navbar links (`dashboard.index`, `plants.list`, logout POST form) per §13, and a minimal CSS stylesheet.

---

### Agent: plants
**Wave:** 2
**Required:** yes
**Files:**
- `plantpal/plants.py`
- `plantpal/templates/plants/list.html`
- `plantpal/templates/plants/form.html`

**Responsibility:** Implement the `plants` Blueprint (url_prefix `/plants`) with list/new/create/edit/update/delete routes (§8, §12, §15), importing `get_db` from `plantpal.database`, `login_required` from `plantpal.auth`, and the plant model functions from `plantpal.models` per §11.

---

### Agent: watering
**Wave:** 2
**Required:** yes
**Files:**
- `plantpal/watering.py`
- `plantpal/templates/watering/list.html`

**Responsibility:** Implement the `watering` Blueprint (url_prefix `/plants`) with list and create watering-log routes (§8, §12, §15), importing `get_db`, `login_required`, and `get_plant_for_user`/`create_watering_log`/`get_watering_logs_for_plant` from their Wave-1 owners per §11.

---

### Agent: dashboard
**Wave:** 2
**Required:** yes
**Files:**
- `plantpal/dashboard.py`
- `plantpal/features.py`
- `plantpal/templates/dashboard/index.html`

**Responsibility:** Implement the `dashboard` Blueprint (no url_prefix, owns `/`), the `register_features(app)` entrypoint that registers all three Wave-2 blueprints (§13 feature registration), and the dashboard template consuming the exact `get_dashboard_plants` dict keys (`id`, `name`, `species`, `location`, `watering_interval_days`, `last_watered_at`, `days_since`, `status`) via subscript per §9, §13 (FC62).

---

STATUS: PASS
