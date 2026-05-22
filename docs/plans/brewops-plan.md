---
date: 2026-05-22
project: brewops
swarm: true
agents: 21
stack: "Flask + SQLite + Jinja2 + Bootstrap 5"
build_method: swarm
feed_forward:
  risk: "sale_models derived state chain: sale -> decrement volume -> check empty -> update batch status -> clear tap. 4-step side effect in one transaction. If any step missing, data integrity breaks silently."
  verify_first: true
---

# BrewOps -- Craft Brewery Manager Plan

## Overview

Single-admin craft brewery management tool. 7 domains (recipes, batches,
ingredients, tanks, taps, sales, staff) + dashboard. Flask + SQLite +
Jinja2 + Bootstrap 5. 21-agent swarm with vertical model/route ownership.

**Primary validation targets (Run 057):**
1. Concurrency Contract -- every write function tagged
2. Defense-in-Depth Matrix -- app + DB enforcement on every constraint
3. Derived State -- every cross-table computed field declared

## Shared Interface Spec

### App Configuration

```python
# app/__init__.py
import os
from flask import Flask
from flask_wtf import CSRFProtect

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    app.config['PERMANENT_SESSION_LIFETIME'] = 28800  # 8 hours
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = not app.debug

    csrf.init_app(app)

    from app.db import init_app
    init_app(app)

    from app.auth import login_required

    # Register blueprints
    from app.routes.auth_routes import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.recipe_routes import bp as recipe_bp
    app.register_blueprint(recipe_bp, url_prefix='/recipes')

    from app.routes.batch_routes import bp as batch_bp
    app.register_blueprint(batch_bp, url_prefix='/batches')

    from app.routes.ingredient_routes import bp as ingredient_bp
    app.register_blueprint(ingredient_bp, url_prefix='/ingredients')

    from app.routes.tank_routes import bp as tank_bp
    app.register_blueprint(tank_bp, url_prefix='/tanks')

    from app.routes.tap_routes import bp as tap_bp
    app.register_blueprint(tap_bp, url_prefix='/taps')

    from app.routes.sale_routes import bp as sale_bp
    app.register_blueprint(sale_bp, url_prefix='/sales')

    from app.routes.staff_routes import bp as staff_bp
    app.register_blueprint(staff_bp, url_prefix='/staff')

    from app.routes.dashboard_routes import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    @app.route('/health')
    def health():
        return {'status': 'ok'}

    # Security headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Brute-force protection state
    app.login_attempts = {'count': 0, 'first_attempt': 0.0}

    return app
```

**Requirements (requirements.txt):**
```
flask>=3.0
flask-wtf>=1.2
```

### Database Connection

```python
# app/db.py
import sqlite3
import os
from flask import g, current_app

DB_PATH = os.environ.get('DATABASE_PATH', 'brewops.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
    with open(schema_path, 'r') as f:
        db.executescript(f.read())
    db.close()

def init_app(app):
    app.teardown_appcontext(close_db)

    @app.cli.command('init-db')
    def init_db_command():
        init_db()
        print('Database initialized.')
```

**Usage -- always call get_db() directly (NOT a context manager):**
```python
conn = get_db()
recipes = get_all_recipes(conn)
```

**Note on isolation_level=None:** With `isolation_level=None`, Python's sqlite3
module does NOT issue implicit BEGIN statements. This means:
- SERIAL-SAFE functions execute in autocommit mode (each statement commits
  individually). Route handlers call `conn.commit()` after the model call
  to ensure the write is flushed, but with autocommit this is a no-op.
  Include the `conn.commit()` call anyway for clarity.
- NEEDS-BEGIN-IMMEDIATE functions issue explicit `BEGIN IMMEDIATE` / `COMMIT`
  / `ROLLBACK` which work correctly because no implicit transaction is open.

**DO NOT rules for model agents:**
- Do NOT set `conn.row_factory` in model functions -- `get_db()` handles it
- Do NOT use Python `datetime.now()` -- use SQL `datetime('now')`
- Do NOT call `conn.commit()` inside functions tagged NEEDS-BEGIN-IMMEDIATE
  -- the function manages its own BEGIN/COMMIT/ROLLBACK
- Do NOT call `conn.commit()` inside SERIAL-SAFE functions -- the route
  handler calls `conn.commit()` after the model function returns

### Auth

```python
# app/auth.py
import functools
from flask import session, redirect, url_for, flash

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated
```

**Session keys:**
| Key | Set By | Value |
|-----|--------|-------|
| `session['logged_in']` | auth_routes (login) | `True` |
| `session.permanent` | auth_routes (login) | `True` (MUST be set or PERMANENT_SESSION_LIFETIME is ignored) |

### Template Filters

```python
# app/filters.py -- registered in create_app()
def dollars(cents):
    """Format integer cents as dollar string: 1250 -> '$12.50'"""
    return f'${cents / 100:.2f}'

def format_date(date_str):
    """Format ISO date string: '2026-05-22' -> 'May 22, 2026'"""
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
        return dt.strftime('%b %d, %Y')
    except (ValueError, TypeError):
        return date_str or ''

# Register in create_app():
# app.jinja_env.filters['dollars'] = dollars
# app.jinja_env.filters['format_date'] = format_date
```

### Database Schema

```sql
-- schema.sql

CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    style TEXT NOT NULL DEFAULT '',
    target_abv REAL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK(category IN ('grain', 'hops', 'yeast', 'adjunct', 'other')),
    stock_qty REAL NOT NULL DEFAULT 0.0 CHECK(stock_qty >= 0),
    unit TEXT NOT NULL DEFAULT 'lb',
    low_stock_threshold REAL NOT NULL DEFAULT 5.0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recipe_ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
    quantity REAL NOT NULL CHECK(quantity > 0),
    unit TEXT NOT NULL DEFAULT 'lb',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe_id ON recipe_ingredients(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient_id ON recipe_ingredients(ingredient_id);

CREATE TABLE IF NOT EXISTS tanks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    capacity_gallons REAL NOT NULL CHECK(capacity_gallons > 0),
    tank_type TEXT NOT NULL CHECK(tank_type IN ('fermenter', 'brite', 'conditioning')),
    current_batch_id INTEGER UNIQUE,  -- FK enforced in application code (circular FK with batches.tank_id is unreliable in SQLite)
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    brew_date TEXT,
    status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned', 'brewing', 'fermenting', 'conditioning', 'ready', 'tapped', 'empty')),
    volume_gallons REAL NOT NULL CHECK(volume_gallons > 0),
    remaining_volume_oz REAL NOT NULL CHECK(remaining_volume_oz >= 0),
    tank_id INTEGER REFERENCES tanks(id) ON DELETE SET NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_batches_recipe_id ON batches(recipe_id);
CREATE INDEX IF NOT EXISTS idx_batches_tank_id ON batches(tank_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);

CREATE TABLE IF NOT EXISTS taps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL UNIQUE,
    batch_id INTEGER UNIQUE REFERENCES batches(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_taps_batch_id ON taps(batch_id);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tap_id INTEGER NOT NULL REFERENCES taps(id) ON DELETE RESTRICT,
    batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
    quantity_oz REAL NOT NULL CHECK(quantity_oz > 0),
    sale_type TEXT NOT NULL CHECK(sale_type IN ('pint', 'half_pint', 'growler', 'case')),
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sales_tap_id ON sales(tap_id);
CREATE INDEX IF NOT EXISTS idx_sales_batch_id ON sales(batch_id);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('brewer', 'server', 'manager')),
    email TEXT UNIQUE,
    phone TEXT NOT NULL DEFAULT '',
    hire_date TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Note on circular reference:** `tanks.current_batch_id` and `batches.tank_id`
form a circular reference. The FK on `tanks.current_batch_id` is removed
(circular FKs are unreliable in SQLite -- the CREATE TABLE order matters and
executescript doesn't guarantee FK resolution). The UNIQUE constraint on
`current_batch_id` is kept to enforce one-batch-per-tank. The relationship
is enforced in application code (`start_brewing`, `advance_batch_status`)
which already validates the batch/tank association inside BEGIN IMMEDIATE.

### Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| recipes | recipe_models | recipe_routes, recipe_ingredient_models, batch_models, dashboard_routes |
| recipe_ingredients | recipe_ingredient_models | recipe_routes, batch_models |
| batches | batch_models | batch_routes, tap_routes, sale_models, dashboard_routes |
| ingredients | ingredient_models | ingredient_routes, batch_models, recipe_routes, dashboard_routes |
| tanks | tank_models | tank_routes, batch_models, dashboard_routes |
| taps | tap_models | tap_routes, sale_routes, batch_models, dashboard_routes |
| sales | sale_models | sale_routes, dashboard_routes |
| staff | staff_models | staff_routes |

**Exception:** `sale_models` writes to `batches` (remaining_volume_oz, status)
and `taps` (batch_id) as derived state updates. This is declared in the
Derived State section and is the ONLY cross-table write exception.
`batch_models` writes to `tanks` (current_batch_id) and `ingredients`
(stock_qty) as derived state updates during start_brewing.

### Model Functions

#### recipe_models.py

```python
# get_all_recipes(conn) -> list[sqlite3.Row]
# Usage: recipes = get_all_recipes(conn)
def get_all_recipes(conn: sqlite3.Connection) -> list:
    return conn.execute('SELECT * FROM recipes ORDER BY name').fetchall()

# get_recipe(conn, recipe_id) -> sqlite3.Row | None
# Usage: recipe = get_recipe(conn, recipe_id)
#        if recipe is None: abort(404)
def get_recipe(conn: sqlite3.Connection, recipe_id: int):
    return conn.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,)).fetchone()

# create_recipe(conn, name, style, target_abv, notes) -> int
# Returns: the new recipe's ID
# Usage: recipe_id = create_recipe(conn, name, style, target_abv, notes)
#        conn.commit()
#        redirect(url_for('recipes.detail', recipe_id=recipe_id))
def create_recipe(conn: sqlite3.Connection, name: str, style: str,
                  target_abv: float | None, notes: str) -> int:
    cur = conn.execute(
        'INSERT INTO recipes (name, style, target_abv, notes) VALUES (?, ?, ?, ?)',
        (name, style, target_abv, notes))
    return cur.lastrowid

# update_recipe(conn, recipe_id, name, style, target_abv, notes) -> None
# Usage: update_recipe(conn, recipe_id, name, style, target_abv, notes)
#        conn.commit()
def update_recipe(conn: sqlite3.Connection, recipe_id: int, name: str,
                  style: str, target_abv: float | None, notes: str) -> None:
    conn.execute(
        "UPDATE recipes SET name=?, style=?, target_abv=?, notes=?, updated_at=datetime('now') WHERE id=?",
        (name, style, target_abv, notes, recipe_id))

# delete_recipe(conn, recipe_id) -> None
# Usage: delete_recipe(conn, recipe_id)
#        conn.commit()
def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> None:
    conn.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
```

#### recipe_ingredient_models.py

```python
# get_recipe_ingredients(conn, recipe_id) -> list[sqlite3.Row]
# Returns: list of recipe_ingredients rows joined with ingredient name
# Usage: ingredients = get_recipe_ingredients(conn, recipe_id)
def get_recipe_ingredients(conn: sqlite3.Connection, recipe_id: int) -> list:
    return conn.execute('''
        SELECT ri.*, i.name as ingredient_name, i.unit as ingredient_unit
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id = ?
        ORDER BY i.name
    ''', (recipe_id,)).fetchall()

# add_recipe_ingredient(conn, recipe_id, ingredient_id, quantity, unit) -> int
# Returns: the new recipe_ingredient's ID
# Usage: ri_id = add_recipe_ingredient(conn, recipe_id, ingredient_id, qty, unit)
#        conn.commit()
def add_recipe_ingredient(conn: sqlite3.Connection, recipe_id: int,
                          ingredient_id: int, quantity: float, unit: str) -> int:
    cur = conn.execute(
        'INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)',
        (recipe_id, ingredient_id, quantity, unit))
    return cur.lastrowid

# remove_recipe_ingredient(conn, ri_id) -> None
# Usage: remove_recipe_ingredient(conn, ri_id)
#        conn.commit()
def remove_recipe_ingredient(conn: sqlite3.Connection, ri_id: int) -> None:
    conn.execute('DELETE FROM recipe_ingredients WHERE id = ?', (ri_id,))
```

#### ingredient_models.py

```python
# get_all_ingredients(conn) -> list[sqlite3.Row]
def get_all_ingredients(conn: sqlite3.Connection) -> list:
    return conn.execute('SELECT * FROM ingredients ORDER BY name').fetchall()

# get_ingredient(conn, ingredient_id) -> sqlite3.Row | None
def get_ingredient(conn: sqlite3.Connection, ingredient_id: int):
    return conn.execute('SELECT * FROM ingredients WHERE id = ?', (ingredient_id,)).fetchone()

# create_ingredient(conn, name, category, stock_qty, unit, low_stock_threshold) -> int
# Returns: the new ingredient's ID
# Usage: ingredient_id = create_ingredient(conn, ...)
#        conn.commit()
def create_ingredient(conn: sqlite3.Connection, name: str, category: str,
                      stock_qty: float, unit: str, low_stock_threshold: float) -> int:
    cur = conn.execute(
        'INSERT INTO ingredients (name, category, stock_qty, unit, low_stock_threshold) VALUES (?, ?, ?, ?, ?)',
        (name, category, stock_qty, unit, low_stock_threshold))
    return cur.lastrowid

# update_ingredient(conn, ingredient_id, name, category, stock_qty, unit, low_stock_threshold) -> None
# Usage: update_ingredient(conn, ingredient_id, ...)
#        conn.commit()
def update_ingredient(conn: sqlite3.Connection, ingredient_id: int, name: str,
                      category: str, stock_qty: float, unit: str,
                      low_stock_threshold: float) -> None:
    conn.execute(
        "UPDATE ingredients SET name=?, category=?, stock_qty=?, unit=?, low_stock_threshold=?, updated_at=datetime('now') WHERE id=?",
        (name, category, stock_qty, unit, low_stock_threshold, ingredient_id))

# delete_ingredient(conn, ingredient_id) -> None
def delete_ingredient(conn: sqlite3.Connection, ingredient_id: int) -> None:
    conn.execute('DELETE FROM ingredients WHERE id = ?', (ingredient_id,))

# get_low_stock_ingredients(conn) -> list[sqlite3.Row]
# Returns ingredients where stock_qty <= low_stock_threshold
def get_low_stock_ingredients(conn: sqlite3.Connection) -> list:
    return conn.execute(
        'SELECT * FROM ingredients WHERE stock_qty <= low_stock_threshold ORDER BY name'
    ).fetchall()
```

#### tank_models.py

```python
# get_all_tanks(conn) -> list[sqlite3.Row]
def get_all_tanks(conn: sqlite3.Connection) -> list:
    return conn.execute('SELECT * FROM tanks ORDER BY name').fetchall()

# get_tank(conn, tank_id) -> sqlite3.Row | None
def get_tank(conn: sqlite3.Connection, tank_id: int):
    return conn.execute('SELECT * FROM tanks WHERE id = ?', (tank_id,)).fetchone()

# get_available_tanks(conn) -> list[sqlite3.Row]
# Returns tanks where current_batch_id IS NULL
def get_available_tanks(conn: sqlite3.Connection) -> list:
    return conn.execute(
        'SELECT * FROM tanks WHERE current_batch_id IS NULL ORDER BY name'
    ).fetchall()

# create_tank(conn, name, capacity_gallons, tank_type, notes) -> int
# Returns: the new tank's ID
def create_tank(conn: sqlite3.Connection, name: str, capacity_gallons: float,
                tank_type: str, notes: str) -> int:
    cur = conn.execute(
        'INSERT INTO tanks (name, capacity_gallons, tank_type, notes) VALUES (?, ?, ?, ?)',
        (name, capacity_gallons, tank_type, notes))
    return cur.lastrowid

# update_tank(conn, tank_id, name, capacity_gallons, tank_type, notes) -> None
def update_tank(conn: sqlite3.Connection, tank_id: int, name: str,
                capacity_gallons: float, tank_type: str, notes: str) -> None:
    conn.execute(
        "UPDATE tanks SET name=?, capacity_gallons=?, tank_type=?, notes=?, updated_at=datetime('now') WHERE id=?",
        (name, capacity_gallons, tank_type, notes, tank_id))

# delete_tank(conn, tank_id) -> None
def delete_tank(conn: sqlite3.Connection, tank_id: int) -> None:
    conn.execute('DELETE FROM tanks WHERE id = ?', (tank_id,))
```

#### tap_models.py

```python
# get_all_taps(conn) -> list[sqlite3.Row]
# Returns taps joined with batch info
def get_all_taps(conn: sqlite3.Connection) -> list:
    return conn.execute('''
        SELECT t.*, b.name as batch_name, b.remaining_volume_oz, b.status as batch_status,
               r.name as recipe_name
        FROM taps t
        LEFT JOIN batches b ON t.batch_id = b.id
        LEFT JOIN recipes r ON b.recipe_id = r.id
        ORDER BY t.position
    ''').fetchall()

# get_tap(conn, tap_id) -> sqlite3.Row | None
def get_tap(conn: sqlite3.Connection, tap_id: int):
    return conn.execute('''
        SELECT t.*, b.name as batch_name, b.remaining_volume_oz, b.status as batch_status,
               r.name as recipe_name
        FROM taps t
        LEFT JOIN batches b ON t.batch_id = b.id
        LEFT JOIN recipes r ON b.recipe_id = r.id
        WHERE t.id = ?
    ''', (tap_id,)).fetchone()

# get_available_taps(conn) -> list[sqlite3.Row]
# Returns taps where batch_id IS NULL
def get_available_taps(conn: sqlite3.Connection) -> list:
    return conn.execute(
        'SELECT * FROM taps WHERE batch_id IS NULL ORDER BY position'
    ).fetchall()

# create_tap(conn, name, position) -> int
def create_tap(conn: sqlite3.Connection, name: str, position: int) -> int:
    cur = conn.execute(
        'INSERT INTO taps (name, position) VALUES (?, ?)', (name, position))
    return cur.lastrowid

# update_tap(conn, tap_id, name, position) -> None
def update_tap(conn: sqlite3.Connection, tap_id: int, name: str, position: int) -> None:
    conn.execute(
        "UPDATE taps SET name=?, position=?, updated_at=datetime('now') WHERE id=?",
        (name, position, tap_id))

# delete_tap(conn, tap_id) -> None
def delete_tap(conn: sqlite3.Connection, tap_id: int) -> None:
    conn.execute('DELETE FROM taps WHERE id = ?', (tap_id,))
```

#### batch_models.py

```python
import sqlite3

# Status transition map -- only these transitions are valid
VALID_TRANSITIONS = {
    'planned': ['brewing'],
    'brewing': ['fermenting'],
    'fermenting': ['conditioning'],
    'conditioning': ['ready'],
    'ready': ['tapped'],
    'tapped': ['empty'],
    'empty': [],
}

# get_all_batches(conn) -> list[sqlite3.Row]
def get_all_batches(conn: sqlite3.Connection) -> list:
    return conn.execute('''
        SELECT b.*, r.name as recipe_name, t.name as tank_name
        FROM batches b
        LEFT JOIN recipes r ON b.recipe_id = r.id
        LEFT JOIN tanks t ON b.tank_id = t.id
        ORDER BY b.created_at DESC
    ''').fetchall()

# get_batch(conn, batch_id) -> sqlite3.Row | None
def get_batch(conn: sqlite3.Connection, batch_id: int):
    return conn.execute('''
        SELECT b.*, r.name as recipe_name, t.name as tank_name
        FROM batches b
        LEFT JOIN recipes r ON b.recipe_id = r.id
        LEFT JOIN tanks t ON b.tank_id = t.id
        WHERE b.id = ?
    ''', (batch_id,)).fetchone()

# get_batches_by_status(conn, status) -> list[sqlite3.Row]
def get_batches_by_status(conn: sqlite3.Connection, status: str) -> list:
    return conn.execute('''
        SELECT b.*, r.name as recipe_name
        FROM batches b
        LEFT JOIN recipes r ON b.recipe_id = r.id
        WHERE b.status = ?
        ORDER BY b.created_at DESC
    ''', (status,)).fetchall()

# create_batch(conn, recipe_id, name, volume_gallons, notes) -> int
# Returns: the new batch's ID
# Remaining_volume_oz is set to volume_gallons * 128 (gallons to oz)
# Usage: batch_id = create_batch(conn, recipe_id, name, volume_gallons, notes)
#        conn.commit()
def create_batch(conn: sqlite3.Connection, recipe_id: int, name: str,
                 volume_gallons: float, notes: str) -> int:
    remaining_oz = volume_gallons * 128  # 1 gallon = 128 oz
    cur = conn.execute(
        'INSERT INTO batches (recipe_id, name, volume_gallons, remaining_volume_oz, notes) VALUES (?, ?, ?, ?, ?)',
        (recipe_id, name, volume_gallons, remaining_oz, notes))
    return cur.lastrowid

# start_brewing(conn, batch_id, tank_id) -> str | None
# NEEDS-BEGIN-IMMEDIATE: assigns tank + decrements all recipe ingredients
# Returns: None on success, error message string on failure
# Usage: error = start_brewing(conn, batch_id, tank_id)
#        if error:
#            flash(error, 'error')
#            return redirect(...)
# DERIVED STATE: updates tanks.current_batch_id, ingredients.stock_qty, batches.status
def start_brewing(conn: sqlite3.Connection, batch_id: int, tank_id: int) -> str | None:
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Re-read batch inside transaction (authoritative)
        batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
        if batch is None:
            conn.execute('ROLLBACK')
            return 'Batch not found'
        if batch['status'] != 'planned':
            conn.execute('ROLLBACK')
            return 'Batch must be in planned status to start brewing'

        # Re-read tank inside transaction (authoritative, TOCTOU-safe)
        tank = conn.execute('SELECT * FROM tanks WHERE id = ?', (tank_id,)).fetchone()
        if tank is None:
            conn.execute('ROLLBACK')
            return 'Tank not found'
        if tank['current_batch_id'] is not None:
            conn.execute('ROLLBACK')
            return 'Tank is already occupied'
        if tank['capacity_gallons'] < batch['volume_gallons']:
            conn.execute('ROLLBACK')
            return 'Batch volume exceeds tank capacity'

        # Check and decrement all recipe ingredients
        recipe_ings = conn.execute(
            'SELECT ri.*, i.stock_qty, i.name as ingredient_name FROM recipe_ingredients ri '
            'JOIN ingredients i ON ri.ingredient_id = i.id WHERE ri.recipe_id = ?',
            (batch['recipe_id'],)).fetchall()

        for ri in recipe_ings:
            if ri['stock_qty'] < ri['quantity']:
                conn.execute('ROLLBACK')
                return f"Insufficient stock for {ri['ingredient_name']}: need {ri['quantity']}, have {ri['stock_qty']}"
            conn.execute(
                "UPDATE ingredients SET stock_qty = stock_qty - ?, updated_at = datetime('now') WHERE id = ?",
                (ri['quantity'], ri['ingredient_id']))

        # Assign tank
        conn.execute(
            "UPDATE tanks SET current_batch_id = ?, updated_at = datetime('now') WHERE id = ?",
            (batch_id, tank_id))

        # Update batch status and tank assignment
        conn.execute(
            "UPDATE batches SET status = 'brewing', tank_id = ?, brew_date = date('now'), updated_at = datetime('now') WHERE id = ?",
            (tank_id, batch_id))

        conn.execute('COMMIT')
        return None
    except Exception:
        conn.execute('ROLLBACK')
        raise

# advance_batch_status(conn, batch_id, new_status) -> str | None
# NEEDS-BEGIN-IMMEDIATE: validates current status before updating
# Returns: None on success, error message on failure
# Valid transitions: brewing->fermenting, fermenting->conditioning, conditioning->ready
# conditioning->ready also releases the tank
# Usage: error = advance_batch_status(conn, batch_id, new_status)
def advance_batch_status(conn: sqlite3.Connection, batch_id: int,
                         new_status: str) -> str | None:
    try:
        conn.execute('BEGIN IMMEDIATE')

        batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
        if batch is None:
            conn.execute('ROLLBACK')
            return 'Batch not found'

        current = batch['status']
        if new_status not in VALID_TRANSITIONS.get(current, []):
            conn.execute('ROLLBACK')
            return f'Cannot transition from {current} to {new_status}'

        conn.execute(
            "UPDATE batches SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, batch_id))

        # Release tank when batch reaches 'ready' status
        if new_status == 'ready' and batch['tank_id'] is not None:
            conn.execute(
                "UPDATE tanks SET current_batch_id = NULL, updated_at = datetime('now') WHERE id = ?",
                (batch['tank_id'],))
            conn.execute(
                "UPDATE batches SET tank_id = NULL, updated_at = datetime('now') WHERE id = ?",
                (batch_id,))

        conn.execute('COMMIT')
        return None
    except Exception:
        conn.execute('ROLLBACK')
        raise

# assign_to_tap(conn, batch_id, tap_id) -> str | None
# NEEDS-BEGIN-IMMEDIATE: checks tap availability + batch status
# DERIVED STATE: updates taps.batch_id, batches.status
# Returns: None on success, error message on failure
# Usage: error = assign_to_tap(conn, batch_id, tap_id)
def assign_to_tap(conn: sqlite3.Connection, batch_id: int,
                  tap_id: int) -> str | None:
    try:
        conn.execute('BEGIN IMMEDIATE')

        batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
        if batch is None:
            conn.execute('ROLLBACK')
            return 'Batch not found'
        if batch['status'] != 'ready':
            conn.execute('ROLLBACK')
            return 'Batch must be in ready status to tap'

        tap = conn.execute('SELECT * FROM taps WHERE id = ?', (tap_id,)).fetchone()
        if tap is None:
            conn.execute('ROLLBACK')
            return 'Tap not found'
        if tap['batch_id'] is not None:
            conn.execute('ROLLBACK')
            return 'Tap already has a batch assigned'

        conn.execute(
            "UPDATE taps SET batch_id = ?, updated_at = datetime('now') WHERE id = ?",
            (batch_id, tap_id))
        conn.execute(
            "UPDATE batches SET status = 'tapped', updated_at = datetime('now') WHERE id = ?",
            (batch_id,))

        conn.execute('COMMIT')
        return None
    except Exception:
        conn.execute('ROLLBACK')
        raise

# update_batch(conn, batch_id, name, notes) -> None
# Only updates name and notes -- status changes go through dedicated functions
def update_batch(conn: sqlite3.Connection, batch_id: int, name: str, notes: str) -> None:
    conn.execute(
        "UPDATE batches SET name=?, notes=?, updated_at=datetime('now') WHERE id=?",
        (name, notes, batch_id))

# delete_batch(conn, batch_id) -> None
def delete_batch(conn: sqlite3.Connection, batch_id: int) -> None:
    conn.execute('DELETE FROM batches WHERE id = ?', (batch_id,))
```

#### sale_models.py

```python
import sqlite3

# get_all_sales(conn) -> list[sqlite3.Row]
def get_all_sales(conn: sqlite3.Connection) -> list:
    return conn.execute('''
        SELECT s.*, t.name as tap_name, b.name as batch_name, r.name as recipe_name
        FROM sales s
        JOIN taps t ON s.tap_id = t.id
        JOIN batches b ON s.batch_id = b.id
        LEFT JOIN recipes r ON b.recipe_id = r.id
        ORDER BY s.created_at DESC
    ''').fetchall()

# get_sale(conn, sale_id) -> sqlite3.Row | None
def get_sale(conn: sqlite3.Connection, sale_id: int):
    return conn.execute('''
        SELECT s.*, t.name as tap_name, b.name as batch_name
        FROM sales s
        JOIN taps t ON s.tap_id = t.id
        JOIN batches b ON s.batch_id = b.id
        WHERE s.id = ?
    ''', (sale_id,)).fetchone()

# get_today_sales_total(conn) -> int
# Returns total sales in cents for today
# Usage: total_cents = get_today_sales_total(conn)
def get_today_sales_total(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(price_cents), 0) as total FROM sales WHERE date(created_at) = date('now')"
    ).fetchone()
    return row['total']

# create_sale(conn, tap_id, quantity_oz, sale_type, price_cents) -> int | None
# NEEDS-BEGIN-IMMEDIATE: decrements batch remaining_volume_oz
# DERIVED STATE: updates batches.remaining_volume_oz, batches.status (if empty), taps.batch_id (if empty)
# Returns: sale ID on success, None if insufficient volume
# Usage: sale_id = create_sale(conn, tap_id, quantity_oz, sale_type, price_cents)
#        if sale_id is None:
#            flash('Insufficient remaining volume', 'error')
def create_sale(conn: sqlite3.Connection, tap_id: int, quantity_oz: float,
                sale_type: str, price_cents: int) -> int | None:
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Get tap and verify it has a batch
        tap = conn.execute('SELECT * FROM taps WHERE id = ?', (tap_id,)).fetchone()
        if tap is None or tap['batch_id'] is None:
            conn.execute('ROLLBACK')
            return None

        batch_id = tap['batch_id']

        # Re-read batch volume inside transaction (authoritative, TOCTOU-safe)
        batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
        if batch is None or batch['remaining_volume_oz'] < quantity_oz:
            conn.execute('ROLLBACK')
            return None

        # Insert sale
        cur = conn.execute(
            'INSERT INTO sales (tap_id, batch_id, quantity_oz, sale_type, price_cents) VALUES (?, ?, ?, ?, ?)',
            (tap_id, batch_id, quantity_oz, sale_type, price_cents))
        sale_id = cur.lastrowid

        # Decrement remaining volume (clamp to 0 for float precision safety)
        new_remaining = max(0, batch['remaining_volume_oz'] - quantity_oz)
        conn.execute(
            "UPDATE batches SET remaining_volume_oz = ?, updated_at = datetime('now') WHERE id = ?",
            (new_remaining, batch_id))

        # If batch is now empty, update status and clear tap
        if new_remaining <= 0:
            conn.execute(
                "UPDATE batches SET status = 'empty', updated_at = datetime('now') WHERE id = ?",
                (batch_id,))
            conn.execute(
                "UPDATE taps SET batch_id = NULL, updated_at = datetime('now') WHERE id = ?",
                (tap_id,))

        conn.execute('COMMIT')
        return sale_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
```

#### staff_models.py

```python
# get_all_staff(conn) -> list[sqlite3.Row]
def get_all_staff(conn: sqlite3.Connection) -> list:
    return conn.execute('SELECT * FROM staff ORDER BY name').fetchall()

# get_staff_member(conn, staff_id) -> sqlite3.Row | None
def get_staff_member(conn: sqlite3.Connection, staff_id: int):
    return conn.execute('SELECT * FROM staff WHERE id = ?', (staff_id,)).fetchone()

# create_staff(conn, name, role, email, phone, hire_date) -> int
# Returns: the new staff member's ID
def create_staff(conn: sqlite3.Connection, name: str, role: str,
                 email: str | None, phone: str, hire_date: str | None) -> int:
    cur = conn.execute(
        'INSERT INTO staff (name, role, email, phone, hire_date) VALUES (?, ?, ?, ?, ?)',
        (name, role, email, phone, hire_date))
    return cur.lastrowid

# update_staff(conn, staff_id, name, role, email, phone, hire_date, status) -> None
def update_staff(conn: sqlite3.Connection, staff_id: int, name: str, role: str,
                 email: str | None, phone: str, hire_date: str | None,
                 status: str) -> None:
    conn.execute(
        "UPDATE staff SET name=?, role=?, email=?, phone=?, hire_date=?, status=?, updated_at=datetime('now') WHERE id=?",
        (name, role, email, phone, hire_date, status, staff_id))

# delete_staff(conn, staff_id) -> None
def delete_staff(conn: sqlite3.Connection, staff_id: int) -> None:
    conn.execute('DELETE FROM staff WHERE id = ?', (staff_id,))
```

### Route Table

| Method | Flask Path | Handler | Status | Template |
|--------|-----------|---------|--------|----------|
| GET | / | dashboard.index | 200 | dashboard/index.html |
| GET | /login | auth.login | 200 | auth/login.html |
| POST | /login | auth.login_post | 302 | redirect |
| POST | /logout | auth.logout | 302 | redirect |
| GET | /recipes/ | recipes.list | 200 | recipes/list.html |
| GET | /recipes/new | recipes.new | 200 | recipes/form.html |
| POST | /recipes/ | recipes.create | 302 | redirect |
| GET | /recipes/<int:recipe_id> | recipes.detail | 200 | recipes/detail.html |
| GET | /recipes/<int:recipe_id>/edit | recipes.edit | 200 | recipes/form.html |
| POST | /recipes/<int:recipe_id>/edit | recipes.update | 302 | redirect |
| POST | /recipes/<int:recipe_id>/delete | recipes.delete | 302 | redirect |
| POST | /recipes/<int:recipe_id>/ingredients | recipes.add_ingredient | 302 | redirect |
| POST | /recipes/<int:recipe_id>/ingredients/<int:ri_id>/delete | recipes.remove_ingredient | 302 | redirect |
| GET | /batches/ | batches.list | 200 | batches/list.html |
| GET | /batches/new | batches.new | 200 | batches/form.html |
| POST | /batches/ | batches.create | 302 | redirect |
| GET | /batches/<int:batch_id> | batches.detail | 200 | batches/detail.html |
| GET | /batches/<int:batch_id>/edit | batches.edit | 200 | batches/form.html |
| POST | /batches/<int:batch_id>/edit | batches.update | 302 | redirect |
| POST | /batches/<int:batch_id>/delete | batches.delete | 302 | redirect |
| POST | /batches/<int:batch_id>/start-brewing | batches.start_brewing | 302 | redirect |
| POST | /batches/<int:batch_id>/advance | batches.advance | 302 | redirect |
| POST | /batches/<int:batch_id>/assign-tap | batches.assign_tap | 302 | redirect |
| GET | /ingredients/ | ingredients.list | 200 | ingredients/list.html |
| GET | /ingredients/new | ingredients.new | 200 | ingredients/form.html |
| POST | /ingredients/ | ingredients.create | 302 | redirect |
| GET | /ingredients/<int:ingredient_id> | ingredients.detail | 200 | ingredients/detail.html |
| GET | /ingredients/<int:ingredient_id>/edit | ingredients.edit | 200 | ingredients/form.html |
| POST | /ingredients/<int:ingredient_id>/edit | ingredients.update | 302 | redirect |
| POST | /ingredients/<int:ingredient_id>/delete | ingredients.delete | 302 | redirect |
| GET | /tanks/ | tanks.list | 200 | tanks/list.html |
| GET | /tanks/new | tanks.new | 200 | tanks/form.html |
| POST | /tanks/ | tanks.create | 302 | redirect |
| GET | /tanks/<int:tank_id> | tanks.detail | 200 | tanks/detail.html |
| GET | /tanks/<int:tank_id>/edit | tanks.edit | 200 | tanks/form.html |
| POST | /tanks/<int:tank_id>/edit | tanks.update | 302 | redirect |
| POST | /tanks/<int:tank_id>/delete | tanks.delete | 302 | redirect |
| GET | /taps/ | taps.list | 200 | taps/list.html |
| GET | /taps/new | taps.new | 200 | taps/form.html |
| POST | /taps/ | taps.create | 302 | redirect |
| GET | /taps/<int:tap_id> | taps.detail | 200 | taps/detail.html |
| GET | /taps/<int:tap_id>/edit | taps.edit | 200 | taps/form.html |
| POST | /taps/<int:tap_id>/edit | taps.update | 302 | redirect |
| POST | /taps/<int:tap_id>/delete | taps.delete | 302 | redirect |
| GET | /sales/ | sales.list | 200 | sales/list.html |
| GET | /sales/new | sales.new | 200 | sales/form.html |
| POST | /sales/ | sales.create | 302 | redirect |
| GET | /sales/<int:sale_id> | sales.detail | 200 | sales/detail.html |
| GET | /staff/ | staff.list | 200 | staff/list.html |
| GET | /staff/new | staff.new | 200 | staff/form.html |
| POST | /staff/ | staff.create | 302 | redirect |
| GET | /staff/<int:staff_id> | staff.detail | 200 | staff/detail.html |
| GET | /staff/<int:staff_id>/edit | staff.edit | 200 | staff/form.html |
| POST | /staff/<int:staff_id>/edit | staff.update | 302 | redirect |
| POST | /staff/<int:staff_id>/delete | staff.delete | 302 | redirect |

### Template Render Context

```python
# dashboard/index.html expects:
render_template('dashboard/index.html',
    active_batches=get_batches_by_status(conn, 'brewing') + get_batches_by_status(conn, 'fermenting') + get_batches_by_status(conn, 'conditioning'),
    ready_batches=get_batches_by_status(conn, 'ready'),
    tapped_batches=get_batches_by_status(conn, 'tapped'),
    low_stock=get_low_stock_ingredients(conn),
    taps=get_all_taps(conn),
    today_sales=get_today_sales_total(conn))

# recipes/detail.html expects:
render_template('recipes/detail.html',
    recipe=recipe,
    ingredients=get_recipe_ingredients(conn, recipe_id),
    all_ingredients=get_all_ingredients(conn))

# batches/detail.html expects:
render_template('batches/detail.html',
    batch=batch,
    available_tanks=get_available_tanks(conn),
    available_taps=get_available_taps(conn),
    valid_transitions=VALID_TRANSITIONS)

# sales/form.html expects:
render_template('sales/form.html',
    active_taps=get_all_taps(conn))  # filter to taps with batch_id in template
```

### Export Names Table

| Name | Type | Defined By | Used By |
|------|------|------------|---------|
| `get_all_recipes` | model function | recipe_models.py | recipe_routes, batch_routes |
| `get_recipe` | model function | recipe_models.py | recipe_routes, batch_routes |
| `create_recipe` | model function | recipe_models.py | recipe_routes |
| `update_recipe` | model function | recipe_models.py | recipe_routes |
| `delete_recipe` | model function | recipe_models.py | recipe_routes |
| `get_recipe_ingredients` | model function | recipe_ingredient_models.py | recipe_routes, batch_models |
| `add_recipe_ingredient` | model function | recipe_ingredient_models.py | recipe_routes |
| `remove_recipe_ingredient` | model function | recipe_ingredient_models.py | recipe_routes |
| `get_all_batches` | model function | batch_models.py | batch_routes, dashboard_routes |
| `get_batch` | model function | batch_models.py | batch_routes, tap_routes, sale_routes |
| `get_batches_by_status` | model function | batch_models.py | dashboard_routes |
| `create_batch` | model function | batch_models.py | batch_routes |
| `start_brewing` | model function | batch_models.py | batch_routes |
| `advance_batch_status` | model function | batch_models.py | batch_routes |
| `assign_to_tap` | model function | batch_models.py | batch_routes |
| `update_batch` | model function | batch_models.py | batch_routes |
| `delete_batch` | model function | batch_models.py | batch_routes |
| `VALID_TRANSITIONS` | constant | batch_models.py | batch_routes |
| `get_all_ingredients` | model function | ingredient_models.py | ingredient_routes, recipe_routes, dashboard_routes |
| `get_ingredient` | model function | ingredient_models.py | ingredient_routes |
| `create_ingredient` | model function | ingredient_models.py | ingredient_routes |
| `update_ingredient` | model function | ingredient_models.py | ingredient_routes |
| `delete_ingredient` | model function | ingredient_models.py | ingredient_routes |
| `get_low_stock_ingredients` | model function | ingredient_models.py | dashboard_routes |
| `get_all_tanks` | model function | tank_models.py | tank_routes, dashboard_routes |
| `get_tank` | model function | tank_models.py | tank_routes |
| `get_available_tanks` | model function | tank_models.py | batch_routes |
| `create_tank` | model function | tank_models.py | tank_routes |
| `update_tank` | model function | tank_models.py | tank_routes |
| `delete_tank` | model function | tank_models.py | tank_routes |
| `get_all_taps` | model function | tap_models.py | tap_routes, sale_routes, dashboard_routes |
| `get_tap` | model function | tap_models.py | tap_routes, sale_routes |
| `get_available_taps` | model function | tap_models.py | batch_routes |
| `create_tap` | model function | tap_models.py | tap_routes |
| `update_tap` | model function | tap_models.py | tap_routes |
| `delete_tap` | model function | tap_models.py | tap_routes |
| `get_all_sales` | model function | sale_models.py | sale_routes, dashboard_routes |
| `get_sale` | model function | sale_models.py | sale_routes |
| `get_today_sales_total` | model function | sale_models.py | dashboard_routes |
| `create_sale` | model function | sale_models.py | sale_routes |
| `get_all_staff` | model function | staff_models.py | staff_routes |
| `get_staff_member` | model function | staff_models.py | staff_routes |
| `create_staff` | model function | staff_models.py | staff_routes |
| `update_staff` | model function | staff_models.py | staff_routes |
| `delete_staff` | model function | staff_models.py | staff_routes |
| `recipes.list` | endpoint | recipe_routes.py | layout (navbar), dashboard_routes |
| `recipes.detail` | endpoint | recipe_routes.py | recipe_routes, batch_routes |
| `batches.list` | endpoint | batch_routes.py | layout (navbar), dashboard_routes |
| `batches.detail` | endpoint | batch_routes.py | batch_routes, dashboard_routes |
| `ingredients.list` | endpoint | ingredient_routes.py | layout (navbar), dashboard_routes |
| `tanks.list` | endpoint | tank_routes.py | layout (navbar) |
| `taps.list` | endpoint | tap_routes.py | layout (navbar), dashboard_routes |
| `sales.list` | endpoint | sale_routes.py | layout (navbar) |
| `sales.new` | endpoint | sale_routes.py | tap_routes (link) |
| `staff.list` | endpoint | staff_routes.py | layout (navbar) |
| `dashboard.index` | endpoint | dashboard_routes.py | layout (navbar), auth_routes (redirect) |
| `auth.login` | endpoint | auth_routes.py | auth.py (login_required redirect) |
| `auth.logout` | endpoint | auth_routes.py | layout (navbar) |
| `recipes` | blueprint | recipe_routes.py | app/__init__.py |
| `batches` | blueprint | batch_routes.py | app/__init__.py |
| `ingredients` | blueprint | ingredient_routes.py | app/__init__.py |
| `tanks` | blueprint | tank_routes.py | app/__init__.py |
| `taps` | blueprint | tap_routes.py | app/__init__.py |
| `sales` | blueprint | sale_routes.py | app/__init__.py |
| `staff` | blueprint | staff_routes.py | app/__init__.py |
| `dashboard` | blueprint | dashboard_routes.py | app/__init__.py |
| `auth` | blueprint | auth_routes.py | app/__init__.py |

### Cross-Boundary Wiring Table

| Producer | Consumer | Import Path |
|----------|----------|-------------|
| app/db.py | ALL route agents | `from app.db import get_db` |
| app/auth.py | ALL route agents (except auth) | `from app.auth import login_required` |
| app/models/recipe_models.py | app/routes/recipe_routes.py | `from app.models.recipe_models import get_all_recipes, get_recipe, create_recipe, update_recipe, delete_recipe` |
| app/models/recipe_ingredient_models.py | app/routes/recipe_routes.py | `from app.models.recipe_ingredient_models import get_recipe_ingredients, add_recipe_ingredient, remove_recipe_ingredient` |
| app/models/ingredient_models.py | app/routes/recipe_routes.py | `from app.models.ingredient_models import get_all_ingredients` |
| app/models/batch_models.py | app/routes/batch_routes.py | `from app.models.batch_models import get_all_batches, get_batch, create_batch, start_brewing, advance_batch_status, assign_to_tap, update_batch, delete_batch, VALID_TRANSITIONS` |
| app/models/recipe_models.py | app/routes/batch_routes.py | `from app.models.recipe_models import get_all_recipes` |
| app/models/tank_models.py | app/routes/batch_routes.py | `from app.models.tank_models import get_available_tanks` |
| app/models/tap_models.py | app/routes/batch_routes.py | `from app.models.tap_models import get_available_taps` |
| app/models/ingredient_models.py | app/routes/ingredient_routes.py | `from app.models.ingredient_models import get_all_ingredients, get_ingredient, create_ingredient, update_ingredient, delete_ingredient` |
| app/models/tank_models.py | app/routes/tank_routes.py | `from app.models.tank_models import get_all_tanks, get_tank, create_tank, update_tank, delete_tank` |
| app/models/tap_models.py | app/routes/tap_routes.py | `from app.models.tap_models import get_all_taps, get_tap, create_tap, update_tap, delete_tap` |
| app/models/sale_models.py | app/routes/sale_routes.py | `from app.models.sale_models import get_all_sales, get_sale, create_sale` |
| app/models/tap_models.py | app/routes/sale_routes.py | `from app.models.tap_models import get_all_taps` |
| app/models/staff_models.py | app/routes/staff_routes.py | `from app.models.staff_models import get_all_staff, get_staff_member, create_staff, update_staff, delete_staff` |
| app/models/batch_models.py | app/routes/dashboard_routes.py | `from app.models.batch_models import get_all_batches, get_batches_by_status` |
| app/models/ingredient_models.py | app/routes/dashboard_routes.py | `from app.models.ingredient_models import get_low_stock_ingredients` |
| app/models/tap_models.py | app/routes/dashboard_routes.py | `from app.models.tap_models import get_all_taps` |
| app/models/sale_models.py | app/routes/dashboard_routes.py | `from app.models.sale_models import get_today_sales_total` |

### Input Validation Prescriptions

| Route | Input | Validation | Error Response |
|-------|-------|------------|----------------|
| POST /recipes/ | name (form) | strip, 1-200 chars, required | Flash "Recipe name is required" |
| POST /recipes/ | style (form) | strip, max 100 chars | Default '' |
| POST /recipes/ | target_abv (form) | float, 0-100, optional | Flash "Invalid ABV" if malformed |
| POST /recipes/<id>/ingredients | ingredient_id (form) | int, must exist | Flash "Invalid ingredient" |
| POST /recipes/<id>/ingredients | quantity (form) | float, > 0 | Flash "Quantity must be positive" |
| POST /batches/ | recipe_id (form) | int, must exist | Flash "Invalid recipe" |
| POST /batches/ | name (form) | strip, 1-200 chars | Flash "Batch name is required" |
| POST /batches/ | volume_gallons (form) | float, > 0, isfinite | Flash "Invalid volume" |
| POST /batches/<id>/start-brewing | tank_id (form) | int, must exist | Flash "Invalid tank" |
| POST /batches/<id>/advance | new_status (form) | must be in VALID_TRANSITIONS[current] | Flash "Invalid status transition" |
| POST /batches/<id>/assign-tap | tap_id (form) | int, must exist | Flash "Invalid tap" |
| POST /ingredients/ | name (form) | strip, 1-200 chars | Flash "Ingredient name is required" |
| POST /ingredients/ | category (form) | must be in enum | Flash "Invalid category" |
| POST /ingredients/ | stock_qty (form) | float, >= 0, isfinite | Flash "Invalid stock quantity" |
| POST /tanks/ | name (form) | strip, 1-100 chars | Flash "Tank name is required" |
| POST /tanks/ | capacity_gallons (form) | float, > 0, isfinite | Flash "Invalid capacity" |
| POST /tanks/ | tank_type (form) | must be in enum | Flash "Invalid tank type" |
| POST /taps/ | name (form) | strip, 1-100 chars | Flash "Tap name is required" |
| POST /taps/ | position (form) | int, > 0 | Flash "Invalid position" |
| POST /sales/ | tap_id (form) | int, tap must have batch | Flash "Invalid tap or no batch assigned" |
| POST /sales/ | quantity_oz (form) | float, > 0, isfinite | Flash "Invalid quantity" |
| POST /sales/ | sale_type (form) | must be in enum | Flash "Invalid sale type" |
| POST /sales/ | price_cents (form) | int via round(float*100), >= 0 | Flash "Invalid price" |
| POST /staff/ | name (form) | strip, 1-200 chars | Flash "Staff name is required" |
| POST /staff/ | role (form) | must be in enum | Flash "Invalid role" |
| POST /staff/ | email (form) | strip, optional, basic format | Flash "Invalid email" if malformed |
| All DELETE routes | entity_id (URL) | int, must exist | abort(404) |
| All EDIT routes | entity_id (URL) | int, must exist | abort(404) |

**Money parsing pattern (for price_cents):**
```python
import math
try:
    val = float(request.form.get('price', '0'))
    if not math.isfinite(val) or val < 0:
        raise ValueError
    price_cents = round(val * 100)
except (ValueError, TypeError):
    flash('Invalid price', 'error')
    return redirect(...)
```

### Coordinated Behaviors

| Surface | Rule | Owner |
|---------|------|-------|
| Blueprint registration | All blueprints registered in `create_app()` with url_prefix as shown in App Configuration | core agent |
| Navbar links | Links to: Dashboard, Recipes, Batches, Ingredients, Tanks, Taps, Sales, Staff, Logout | layout agent |
| CSRF token syntax | `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` -- WITH parentheses | ALL route agents |
| Session keys | `session.get('logged_in')` -- matches auth agent's login key | auth + layout agents |
| Base template | `{% extends "base.html" %}` -- NEVER `layout.html` or `main.html` | ALL route agents |
| Block names | `{% block title %}` and `{% block content %}` | ALL route agents |
| Timestamps | SQL `datetime('now')` -- NEVER Python `datetime.now()` | ALL model agents |
| Flash messages | `flash(message, category)` with categories: 'success', 'error' | ALL route agents |
| Bootstrap 5 | CDN link in base.html. No CSP header (deferred -- FC38 risk) | layout agent |
| Security headers | `@app.after_request`: X-Content-Type-Options, X-Frame-Options, Referrer-Policy | core agent |
| PRAGMA per-connection | WAL + foreign_keys + busy_timeout=5000 in get_db() | core agent |
| Delete via POST | All delete operations use POST forms (never GET links) | ALL route agents |
| Money display | Use `|dollars` filter for cents-to-dollar display | ALL route agents with prices |
| Date display | Use `|format_date` filter for ISO date strings | ALL route agents with dates |
| Error handling | `try: int(val) except ValueError: flash(...) return redirect(...)` for all int URL params | ALL route agents |

### Transaction Contracts

| Function | Commits | Error Handling | Tag |
|----------|---------|---------------|-----|
| create_recipe | does NOT commit (caller commits) | N/A | SERIAL-SAFE |
| update_recipe | does NOT commit | N/A | SERIAL-SAFE |
| delete_recipe | does NOT commit | N/A | SERIAL-SAFE |
| add_recipe_ingredient | does NOT commit | N/A | SERIAL-SAFE |
| remove_recipe_ingredient | does NOT commit | N/A | SERIAL-SAFE |
| create_batch | does NOT commit | N/A | SERIAL-SAFE |
| start_brewing | commits internally (BEGIN IMMEDIATE/COMMIT) | try/except/ROLLBACK | NEEDS-BEGIN-IMMEDIATE |
| advance_batch_status | commits internally | try/except/ROLLBACK | NEEDS-BEGIN-IMMEDIATE |
| assign_to_tap | commits internally | try/except/ROLLBACK | NEEDS-BEGIN-IMMEDIATE |
| update_batch | does NOT commit | N/A | SERIAL-SAFE |
| delete_batch | does NOT commit | N/A | SERIAL-SAFE |
| create_sale | commits internally | try/except/ROLLBACK | NEEDS-BEGIN-IMMEDIATE |
| create_ingredient | does NOT commit | N/A | SERIAL-SAFE |
| update_ingredient | does NOT commit | N/A | SERIAL-SAFE |
| delete_ingredient | does NOT commit | N/A | SERIAL-SAFE |
| create_tank | does NOT commit | N/A | SERIAL-SAFE |
| update_tank | does NOT commit | N/A | SERIAL-SAFE |
| delete_tank | does NOT commit | N/A | SERIAL-SAFE |
| create_tap | does NOT commit | N/A | SERIAL-SAFE |
| update_tap | does NOT commit | N/A | SERIAL-SAFE |
| delete_tap | does NOT commit | N/A | SERIAL-SAFE |
| create_staff | does NOT commit | N/A | SERIAL-SAFE |
| update_staff | does NOT commit | N/A | SERIAL-SAFE |
| delete_staff | does NOT commit | N/A | SERIAL-SAFE |

**Route-level commit rule:** For SERIAL-SAFE functions, the route handler
calls `conn.commit()` AFTER the model function returns. For NEEDS-BEGIN-
IMMEDIATE functions, do NOT call `conn.commit()` -- the function manages
its own transaction.

### Authorization Matrix

| Route | Mode | Notes |
|-------|------|-------|
| GET /health | public | No auth required |
| GET /login | public | Login page |
| POST /login | public | Login action |
| POST /logout | admin-only | CSRF-protected |
| ALL other routes | admin-only | `@login_required` decorator |

Single-admin app -- no ownership checks needed. All authenticated routes
are admin-only via `@login_required`.

### Concurrency Contract (NEW -- Validation Target)

| Function | Tag | Reason | Checks Inside Transaction |
|----------|-----|--------|--------------------------|
| start_brewing | NEEDS-BEGIN-IMMEDIATE | Tank assignment + inventory decrement. Two concurrent calls could claim same tank or overdraw ingredient stock. | Tank available (current_batch_id IS NULL), tank capacity >= batch volume, all ingredients in stock |
| advance_batch_status | NEEDS-BEGIN-IMMEDIATE | Read-then-write with status validation. Concurrent calls could both pass the valid-transition check. | Current status matches expected, transition is valid |
| assign_to_tap | NEEDS-BEGIN-IMMEDIATE | Tap availability check. Two concurrent calls could assign same tap. | Tap has no current batch |
| create_sale | NEEDS-BEGIN-IMMEDIATE | Volume decrement. Two concurrent sales could overdraw batch volume below zero. | Remaining volume >= quantity_oz |
| All SERIAL-SAFE functions | SERIAL-SAFE | Single-row INSERT/UPDATE/DELETE with no cross-table dependencies. No TOCTOU risk. | N/A |

**Defense layers for each NEEDS-BEGIN-IMMEDIATE function:**
1. Route-level pre-check (UX gate): friendly flash messages
2. Model-level re-check inside BEGIN IMMEDIATE (authoritative)
3. DB-level CHECK constraints (last resort: stock_qty >= 0, remaining_volume_oz >= 0)

### Defense-in-Depth Matrix (NEW -- Validation Target)

| Constraint | App Level (Route) | App Level (Model/Transaction) | DB Level | Error Translation |
|-----------|-------------------|------------------------------|----------|-------------------|
| Tank available for batch | Flash "Tank is occupied" | Re-check current_batch_id in BEGIN IMMEDIATE | UNIQUE on current_batch_id (one batch per tank) | Route: flash. Model: return error string. DB: IntegrityError |
| Tank capacity >= batch volume | Flash "Batch exceeds tank capacity" | Re-check in BEGIN IMMEDIATE | CHECK(capacity_gallons > 0) | Route: flash. Model: return error string |
| Sufficient ingredient stock | Flash "Insufficient {name}" per ingredient | Re-check each ingredient in BEGIN IMMEDIATE | CHECK(stock_qty >= 0) | Route: flash per ingredient. DB: IntegrityError -> generic |
| Tap available for batch | Flash "Tap already assigned" | Re-check batch_id in BEGIN IMMEDIATE | UNIQUE on batch_id (one batch per tap) | Route: flash. Model: return error string. DB: IntegrityError |
| Sale doesn't overdraw volume | Flash "Insufficient remaining volume" | Re-check remaining_volume_oz in BEGIN IMMEDIATE | CHECK(remaining_volume_oz >= 0) | Route: flash. DB: IntegrityError -> generic |
| Valid batch status transition | Flash "Invalid transition" | Re-validate via VALID_TRANSITIONS map | CHECK(status IN (...)) | Route: flash. Model: return error string |
| Unique recipe name | Flash "Name already exists" | N/A (single INSERT) | UNIQUE(name) | Catch IntegrityError -> flash |
| Unique ingredient name | Flash "Name already exists" | N/A (single INSERT) | UNIQUE(name) | Catch IntegrityError -> flash |
| Unique tank name | Flash "Name already exists" | N/A | UNIQUE(name) | Catch IntegrityError -> flash |
| Unique tap name/position | Flash "Name/position already in use" | N/A | UNIQUE(name), UNIQUE(position) | Catch IntegrityError -> flash |
| Unique staff email | Flash "Email already in use" | N/A | UNIQUE(email) | Catch IntegrityError -> flash |
| Positive volume/quantity | Flash "Must be positive" | N/A | CHECK(volume_gallons > 0), CHECK(quantity > 0), CHECK(quantity_oz > 0) | Route: flash |

### Derived State (NEW -- Validation Target)

| Derived Field | Source Table(s) | Owning Agent | Trigger Event | Update Logic | Transaction |
|--------------|----------------|--------------|---------------|-------------|-------------|
| batches.status -> 'brewing' | batches, tanks, ingredients | batch_models | start_brewing() | Set status, assign tank, decrement ingredients | Same BEGIN IMMEDIATE |
| batches.status -> 'ready' (tank release) | batches, tanks | batch_models | advance_batch_status('ready') | Set status, clear tank.current_batch_id and batch.tank_id | Same BEGIN IMMEDIATE |
| batches.status -> 'tapped' | batches, taps | batch_models | assign_to_tap() | Set batch status, set tap.batch_id | Same BEGIN IMMEDIATE |
| batches.status -> 'empty' | batches, taps | sale_models | create_sale() when remaining_volume_oz <= 0 | Set batch status='empty', clear tap.batch_id | Same BEGIN IMMEDIATE |
| batches.remaining_volume_oz | sales | sale_models | create_sale() | Decrement by quantity_oz | Same BEGIN IMMEDIATE |
| ingredients.stock_qty | recipe_ingredients | batch_models | start_brewing() | Decrement each ingredient by recipe quantity | Same BEGIN IMMEDIATE |
| tanks.current_batch_id | batches | batch_models | start_brewing() / advance('ready') | Set on brewing start, NULL on ready | Same BEGIN IMMEDIATE |
| taps.batch_id | batches | batch_models / sale_models | assign_to_tap() / create_sale() empty | Set on tap, NULL when batch empties | Same BEGIN IMMEDIATE |

**Key rule:** The agent that writes the SOURCE data owns the derived state
update. Both writes happen in the same BEGIN IMMEDIATE transaction.

### Smoke Test File

As defined in the spec template. Adapt route names:
- Replace `/members/` with `/recipes/`
- Add tests for all 8 blueprints
- Add test for start_brewing flow (create recipe, ingredients, batch, tank, then POST start-brewing)

### File Assignment Boundaries (Swarm Agent Assignment)

| # | Agent | Files |
|---|-------|-------|
| 1 | core | app/__init__.py, app/db.py, app/auth.py, app/filters.py, app/models/__init__.py, schema.sql, requirements.txt, .gitignore, run.py |
| 2 | layout | app/templates/base.html, app/static/style.css |
| 3 | auth | app/routes/auth_routes.py, app/templates/auth/login.html |
| 4 | recipe_models | app/models/recipe_models.py |
| 5 | recipe_ingredient_models | app/models/recipe_ingredient_models.py |
| 6 | batch_models | app/models/batch_models.py |
| 7 | ingredient_models | app/models/ingredient_models.py |
| 8 | tank_models | app/models/tank_models.py |
| 9 | tap_models | app/models/tap_models.py |
| 10 | sale_models | app/models/sale_models.py |
| 11 | staff_models | app/models/staff_models.py |
| 12 | recipe_routes | app/routes/recipe_routes.py, app/templates/recipes/list.html, app/templates/recipes/form.html, app/templates/recipes/detail.html |
| 13 | batch_routes | app/routes/batch_routes.py, app/templates/batches/list.html, app/templates/batches/form.html, app/templates/batches/detail.html |
| 14 | ingredient_routes | app/routes/ingredient_routes.py, app/templates/ingredients/list.html, app/templates/ingredients/form.html, app/templates/ingredients/detail.html |
| 15 | tank_routes | app/routes/tank_routes.py, app/templates/tanks/list.html, app/templates/tanks/form.html, app/templates/tanks/detail.html |
| 16 | tap_routes | app/routes/tap_routes.py, app/templates/taps/list.html, app/templates/taps/form.html, app/templates/taps/detail.html |
| 17 | sale_routes | app/routes/sale_routes.py, app/templates/sales/list.html, app/templates/sales/form.html, app/templates/sales/detail.html |
| 18 | staff_routes | app/routes/staff_routes.py, app/templates/staff/list.html, app/templates/staff/form.html, app/templates/staff/detail.html |
| 19 | dashboard_routes | app/routes/dashboard_routes.py, app/templates/dashboard/index.html |
| 20 | seed | seed.py |
| 21 | tests | test_smoke.py |

## Acceptance Tests (EARS)

### Happy Path
- WHEN the admin visits /login THE SYSTEM SHALL display a login form
- WHEN the admin submits valid credentials THE SYSTEM SHALL redirect to /
- WHEN the admin visits / (dashboard) THE SYSTEM SHALL display active batches, low stock, active taps, today's sales
- WHEN the admin creates a recipe with ingredients THE SYSTEM SHALL store recipe and recipe_ingredients rows
- WHEN the admin creates a batch and starts brewing THE SYSTEM SHALL decrement ingredient stock, assign tank, and set status to 'brewing'
- WHEN the admin advances a batch through fermenting->conditioning->ready THE SYSTEM SHALL release the tank on 'ready'
- WHEN the admin assigns a ready batch to a tap THE SYSTEM SHALL set tap.batch_id and batch status to 'tapped'
- WHEN the admin records a sale THE SYSTEM SHALL decrement remaining_volume_oz and insert a sales row
- WHEN a sale causes remaining_volume_oz to reach 0 THE SYSTEM SHALL set batch status to 'empty' and clear tap.batch_id

### Error Cases
- WHEN the admin tries to start brewing with insufficient ingredient stock THE SYSTEM SHALL flash an error and not change any state
- WHEN the admin tries to assign a batch to an occupied tank THE SYSTEM SHALL flash "Tank is already occupied"
- WHEN the admin tries to record a sale exceeding remaining volume THE SYSTEM SHALL flash "Insufficient remaining volume"
- WHEN the admin tries to assign a batch to an occupied tap THE SYSTEM SHALL flash "Tap already has a batch assigned"
- WHEN the admin tries an invalid status transition THE SYSTEM SHALL flash "Cannot transition from X to Y"

### Verification Commands
- `.venv/bin/python test_smoke.py` -- all smoke tests pass
- `sqlite3 brewops.db ".schema"` -- all tables exist with CHECK constraints
- `sqlite3 brewops.db "SELECT count(*) FROM ingredients WHERE stock_qty < 0"` -- returns 0

## Feed-Forward
- **Hardest decision:** Where to place the derived state update ownership.
  sale_models owns the batch status -> 'empty' transition because it writes
  the source data (the sale that decrements volume). This means sale_models
  writes to the batches and taps tables, violating strict single-writer
  ownership. The alternative was a trigger, but SQLite triggers can't update
  other tables atomically with the INSERT in a way that's debuggable.
- **Rejected alternatives:** SQLite triggers for derived state (opaque errors),
  separate batch_lifecycle module (adds artificial abstraction layer), CSP
  header with Bootstrap CDN domains (deferred to avoid FC38 risk -- simpler
  to omit CSP in v1).
- **Least confident:** The sale_models derived state chain: sale -> decrement
  volume -> check if empty -> update batch status -> clear tap. This is a
  4-step side effect chain inside one transaction. If ANY step is missing or
  ordered wrong, data integrity breaks silently. The Derived State section
  prescribes it explicitly, but whether the agent follows all 4 steps correctly
  is the highest risk.
