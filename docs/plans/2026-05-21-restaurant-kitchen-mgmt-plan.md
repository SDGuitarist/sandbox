---
project: restaurant-kitchen-mgmt
date: 2026-05-21
run: "051"
status: plan
swarm: true
agent_count: 29
brainstorm: docs/brainstorms/2026-05-21-restaurant-kitchen-mgmt-brainstorm.md
feed_forward:
  risk: "30+ agent swarm at this feature breadth may produce inconsistent UX patterns across 14 blueprints"
  verify_first: true
---

# Plan: Restaurant & Kitchen Management System (RestaurantOps)

## What exactly is changing?

Building a new Flask + SQLite + Jinja2 app from scratch in `restaurantops/`.
29 swarm agents build vertical slices (blueprint + models + templates each).
Single-location restaurant operations MVP.

## What must not change?

- No modifications to existing apps (gigsheet/, venueconnect/, lead-scraper/, etc.)
- No global config changes outside this build
- No production database access

## How will we know it worked?

See [Acceptance Tests](#acceptance-tests) section below.

## What is the most likely way this plan is wrong?

The Coordinated Behaviors table may not be prescriptive enough for 34 agents,
leading to 14 different form/flash/error patterns. Mitigation: the table
includes exact code blocks for every shared pattern.

---

## Shared Interface Spec -- RestaurantOps

### App Configuration

**Database module (restaurantops/app/db.py):**
```python
import os
import sqlite3
from flask import g, current_app

def get_db():
    """Get database connection for current request.

    Uses isolation_level=None to disable Python's implicit transaction
    management. This is REQUIRED for BEGIN IMMEDIATE to work correctly.
    All write routes must call conn.commit() explicitly.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            isolation_level=None  # REQUIRED: enables manual BEGIN IMMEDIATE
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA busy_timeout=5000")
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
```

**Filters module (restaurantops/app/filters.py):**
```python
def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert integer cents to dollar string."""
        if cents is None:
            return '$0.00'
        return f'${cents / 100:.2f}'

    @app.template_filter('datefmt')
    def datefmt_filter(value):
        """Format datetime string for display."""
        if not value:
            return ''
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(value)
            return dt.strftime('%b %d, %Y %I:%M %p')
        except (ValueError, TypeError):
            return value
```

**App factory (restaurantops/app/__init__.py):**
```python
import os
from flask import Flask, redirect, url_for, session
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

csrf = CSRFProtect()

SECRET_KEY_BLOCKLIST = ['dev-fallback-key', 'change-me', 'secret', '']

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-key')
    app.config['DATABASE'] = os.path.join(app.instance_path, 'restaurant.db')
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Block weak secret keys in production
    if not app.debug and app.config['SECRET_KEY'] in SECRET_KEY_BLOCKLIST:
        raise RuntimeError('Set a strong SECRET_KEY environment variable for production.')

    csrf.init_app(app)

    from app.db import close_db, get_db
    app.teardown_appcontext(close_db)

    from app.filters import register_filters
    register_filters(app)

    # Auth gate: redirect to login if not authenticated
    @app.before_request
    def require_login():
        from flask import request
        allowed = ['/auth/login', '/static/', '/health']
        if any(request.path.startswith(p) for p in allowed):
            return
        if not session.get('authenticated'):
            return redirect(url_for('auth.login'))

    # CSRF error handler: flash friendly message instead of raw 400
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import flash
        flash('Form expired. Please try again.', 'error')
        return redirect(url_for('dashboard.index'))

    # Security headers
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Register blueprints
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.dashboard.routes import bp as dashboard_bp
    from app.blueprints.menu.routes import bp as menu_bp
    from app.blueprints.recipes.routes import bp as recipes_bp
    from app.blueprints.ingredients.routes import bp as ingredients_bp
    from app.blueprints.inventory.routes import bp as inventory_bp
    from app.blueprints.suppliers.routes import bp as suppliers_bp
    from app.blueprints.purchase_orders.routes import bp as po_bp
    from app.blueprints.orders.routes import bp as orders_bp
    from app.blueprints.tables.routes import bp as tables_bp
    from app.blueprints.reservations.routes import bp as reservations_bp
    from app.blueprints.staff.routes import bp as staff_bp
    from app.blueprints.specials.routes import bp as specials_bp
    from app.blueprints.reviews.routes import bp as reviews_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(menu_bp, url_prefix='/menu')
    app.register_blueprint(recipes_bp, url_prefix='/recipes')
    app.register_blueprint(ingredients_bp, url_prefix='/ingredients')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(suppliers_bp, url_prefix='/suppliers')
    app.register_blueprint(po_bp, url_prefix='/purchase-orders')
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(tables_bp, url_prefix='/tables')
    app.register_blueprint(reservations_bp, url_prefix='/reservations')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(specials_bp, url_prefix='/specials')
    app.register_blueprint(reviews_bp, url_prefix='/reviews')

    # Health check (no auth required)
    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200

    return app
```

**Requirements (requirements.txt):**
```
flask>=3.0
flask-wtf>=1.2
```

**Entry point (restaurantops/run.py):**
```python
from app import create_app
app = create_app()
if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

### Database Schema

```sql
-- Allergens (predefined list)
CREATE TABLE IF NOT EXISTS allergens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Menu categories
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Ingredients
CREATE TABLE IF NOT EXISTS ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL DEFAULT 'g',  -- g, kg, ml, l, unit, oz, lb
    unit_cost_cents INTEGER NOT NULL DEFAULT 0,
    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    low_stock_threshold REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ingredients_supplier_id ON ingredients(supplier_id);

-- Ingredient-allergen junction (M2M)
CREATE TABLE IF NOT EXISTS ingredient_allergens (
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    allergen_id INTEGER NOT NULL REFERENCES allergens(id) ON DELETE CASCADE,
    PRIMARY KEY (ingredient_id, allergen_id)
);

-- Recipes
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    instructions TEXT,
    prep_time_minutes INTEGER,
    cook_time_minutes INTEGER,
    servings INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Recipe-ingredient junction (M2M with quantity)
CREATE TABLE IF NOT EXISTS recipe_ingredients (
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL DEFAULT 'g',
    PRIMARY KEY (recipe_id, ingredient_id)
);

-- Menu items
CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    price_cents INTEGER NOT NULL DEFAULT 0,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    is_available INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_menu_items_category_id ON menu_items(category_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_recipe_id ON menu_items(recipe_id);

-- Inventory (current stock per ingredient)
CREATE TABLE IF NOT EXISTS inventory (
    ingredient_id INTEGER PRIMARY KEY REFERENCES ingredients(id) ON DELETE CASCADE,
    current_stock REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Stock movements (audit trail)
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    movement_type TEXT NOT NULL CHECK(movement_type IN ('receipt', 'consumption', 'adjustment', 'waste')),
    quantity REAL NOT NULL,  -- positive for receipt/adjustment-up, negative for consumption/waste
    reference_type TEXT,  -- 'purchase_order', 'order', 'manual'
    reference_id INTEGER,  -- ID of the PO or order that caused this movement
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_ingredient_id ON stock_movements(ingredient_id);

-- Tables (dining room)
CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number TEXT NOT NULL UNIQUE,
    capacity INTEGER NOT NULL DEFAULT 4,
    zone TEXT NOT NULL DEFAULT 'main',
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'reserved', 'occupied', 'needs_cleaning')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Reservations
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    guest_name TEXT NOT NULL,
    guest_phone TEXT,
    party_size INTEGER NOT NULL DEFAULT 2,
    reservation_date TEXT NOT NULL,  -- YYYY-MM-DD
    reservation_time TEXT NOT NULL,  -- HH:MM
    duration_minutes INTEGER NOT NULL DEFAULT 90,
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed', 'seated', 'completed', 'cancelled', 'no_show')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reservations_table_id ON reservations(table_id);
CREATE INDEX IF NOT EXISTS idx_reservations_date ON reservations(reservation_date);

-- Purchase orders
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'submitted', 'received', 'closed')),
    notes TEXT,
    total_cents INTEGER NOT NULL DEFAULT 0,
    ordered_date TEXT,
    received_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier_id ON purchase_orders(supplier_id);

-- Purchase order line items
CREATE TABLE IF NOT EXISTS purchase_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE RESTRICT,
    quantity REAL NOT NULL,
    unit_cost_cents INTEGER NOT NULL DEFAULT 0,
    UNIQUE(purchase_order_id, ingredient_id)
);
CREATE INDEX IF NOT EXISTS idx_po_items_po_id ON purchase_order_items(purchase_order_id);

-- Customer orders
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER REFERENCES tables(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'preparing', 'ready', 'served', 'closed', 'cancelled')),
    notes TEXT,
    total_cents INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_orders_table_id ON orders(table_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- Order line items
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price_cents INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);

-- Staff members
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'server',  -- chef, sous_chef, server, host, busser, manager
    phone TEXT,
    email TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Staff shifts
CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    shift_date TEXT NOT NULL,  -- YYYY-MM-DD
    start_time TEXT NOT NULL,  -- HH:MM
    end_time TEXT NOT NULL,    -- HH:MM
    role TEXT NOT NULL DEFAULT 'server',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_shifts_staff_id ON shifts(staff_id);
CREATE INDEX IF NOT EXISTS idx_shifts_date ON shifts(shift_date);

-- Daily specials
CREATE TABLE IF NOT EXISTS specials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    price_cents INTEGER NOT NULL DEFAULT 0,
    menu_item_id INTEGER REFERENCES menu_items(id) ON DELETE SET NULL,
    start_date TEXT NOT NULL,  -- YYYY-MM-DD
    end_date TEXT NOT NULL,    -- YYYY-MM-DD
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Customer reviews
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_item_id INTEGER REFERENCES menu_items(id) ON DELETE SET NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    guest_name TEXT,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reviews_menu_item_id ON reviews(menu_item_id);

-- Seed allergens
INSERT OR IGNORE INTO allergens (name) VALUES
    ('Gluten'), ('Dairy'), ('Eggs'), ('Fish'), ('Shellfish'),
    ('Tree Nuts'), ('Peanuts'), ('Soy'), ('Sesame'), ('Celery'),
    ('Mustard'), ('Lupin'), ('Molluscs'), ('Sulphites');
```

**Schema init (restaurantops/app/init_db.py):**
```python
"""Initialize the database schema. Run once: .venv/bin/python -m app.init_db"""
import os
import sqlite3

def get_db_path():
    """Return the database path (instance/restaurant.db)."""
    instance_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    return os.path.join(instance_dir, 'restaurant.db')

def init_db():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    # WAL mode is persistent -- only needs to be set once
    result = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    if result[0] != 'wal':
        raise RuntimeError(f"Failed to enable WAL mode, got: {result[0]}")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.close()
    print(f"Database initialized at {db_path}")

if __name__ == '__main__':
    init_db()
```

### Data Ownership

| Table | Owner Module | Read By |
|-------|-------------|---------|
| allergens | schema (seed data) | ingredients, recipes, menu, orders |
| categories | menu | dashboard, menu |
| suppliers | suppliers | ingredients, purchase_orders |
| ingredients | ingredients | recipes, inventory, purchase_orders, orders |
| ingredient_allergens | ingredients | recipes, menu, orders |
| recipes | recipes | menu, orders |
| recipe_ingredients | recipes | menu (cost calc), orders (inventory deduction), inventory |
| menu_items | menu | orders, specials, reviews, dashboard |
| inventory | inventory | dashboard, orders (read stock), purchase_orders (on receive) |
| stock_movements | inventory | purchase_orders (write via inventory helpers), orders (write via inventory helpers) |
| tables | tables | reservations, orders, dashboard |
| reservations | reservations | tables (read), dashboard |
| purchase_orders | purchase_orders | dashboard, suppliers (read) |
| purchase_order_items | purchase_orders | dashboard |
| orders | orders | dashboard, tables |
| order_items | orders | dashboard, reviews |
| staff | staff | dashboard |
| shifts | staff | dashboard |
| specials | specials | dashboard, menu |
| reviews | reviews | dashboard, menu |

**Cross-boundary write rule:** Only the `inventory` module writes to `inventory`
and `stock_movements`. The `orders` and `purchase_orders` blueprints call
inventory helper functions (defined in `app/models/inventory_models.py`) to
create stock movements. They do NOT write directly to these tables.

### Model Functions

All model functions live in `app/models/` organized by domain. Every function
takes a `conn: sqlite3.Connection` parameter. Functions do NOT commit — the
caller commits.

#### Core Models (app/models/core_models.py)

```python
# Returns: list[sqlite3.Row]
# Usage:
#   allergens = get_all_allergens(conn)
#   for a in allergens: print(a['name'])
def get_all_allergens(conn: sqlite3.Connection) -> list:
    ...
```

#### Category Models (app/models/category_models.py)

```python
# Returns: int (new category ID)
# Usage:
#   cat_id = create_category(conn, 'Appetizers', 1)
def create_category(conn: sqlite3.Connection, name: str, sort_order: int = 0) -> int:
    ...

# Returns: list[sqlite3.Row]
def get_all_categories(conn: sqlite3.Connection) -> list:
    ...

# Returns: sqlite3.Row or None
def get_category(conn: sqlite3.Connection, category_id: int):
    ...

def update_category(conn: sqlite3.Connection, category_id: int, name: str, sort_order: int) -> None:
    ...

def delete_category(conn: sqlite3.Connection, category_id: int) -> None:
    ...
```

#### Ingredient Models (app/models/ingredient_models.py)

```python
# Returns: int (new ingredient ID)
# Usage:
#   ing_id = create_ingredient(conn, 'Flour', 'kg', 150, supplier_id=1, low_stock_threshold=5.0)
def create_ingredient(conn: sqlite3.Connection, name: str, unit: str,
                      unit_cost_cents: int, supplier_id: int | None = None,
                      low_stock_threshold: float = 0) -> int:
    ...

# Returns: list[sqlite3.Row]
def get_all_ingredients(conn: sqlite3.Connection) -> list:
    ...

# Returns: sqlite3.Row or None
def get_ingredient(conn: sqlite3.Connection, ingredient_id: int):
    ...

def update_ingredient(conn: sqlite3.Connection, ingredient_id: int,
                      name: str, unit: str, unit_cost_cents: int,
                      supplier_id: int | None, low_stock_threshold: float) -> None:
    ...

def delete_ingredient(conn: sqlite3.Connection, ingredient_id: int) -> None:
    ...

# Allergen management for an ingredient
# Usage:
#   set_ingredient_allergens(conn, ing_id, [1, 3, 5])  # Gluten, Eggs, Shellfish
def set_ingredient_allergens(conn: sqlite3.Connection, ingredient_id: int,
                             allergen_ids: list[int]) -> None:
    """Delete existing allergens and insert new ones."""
    ...

# Returns: list[sqlite3.Row] with allergen id and name
def get_ingredient_allergens(conn: sqlite3.Connection, ingredient_id: int) -> list:
    ...
```

#### Recipe Models (app/models/recipe_models.py)

```python
# Returns: int (new recipe ID)
# Usage:
#   recipe_id = create_recipe(conn, 'Pasta Carbonara', 'Classic Italian', 'Step 1...', 15, 20, 4)
def create_recipe(conn: sqlite3.Connection, name: str, description: str,
                  instructions: str, prep_time_minutes: int,
                  cook_time_minutes: int, servings: int) -> int:
    ...

# Returns: list[sqlite3.Row]
def get_all_recipes(conn: sqlite3.Connection) -> list:
    ...

# Returns: sqlite3.Row or None
def get_recipe(conn: sqlite3.Connection, recipe_id: int):
    ...

def update_recipe(conn: sqlite3.Connection, recipe_id: int, name: str,
                  description: str, instructions: str,
                  prep_time_minutes: int, cook_time_minutes: int,
                  servings: int) -> None:
    ...

def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> None:
    ...

# M2M ingredient management
# Usage:
#   set_recipe_ingredients(conn, recipe_id, [1, 2, 3], [200.0, 50.0, 10.0], ['g', 'ml', 'unit'])
#   MUST validate: len(ingredient_ids) == len(quantities) == len(units)
def set_recipe_ingredients(conn: sqlite3.Connection, recipe_id: int,
                           ingredient_ids: list[int], quantities: list[float],
                           units: list[str]) -> None:
    """Delete existing and insert new recipe ingredients."""
    ...

# Returns: list[sqlite3.Row] with ingredient_id, ingredient name, quantity, unit, unit_cost_cents
def get_recipe_ingredients(conn: sqlite3.Connection, recipe_id: int) -> list:
    ...

# Returns: int (total cost in cents for one serving)
# Usage:
#   cost_cents = calculate_recipe_cost(conn, recipe_id)
#   display: {{ cost_cents|dollars }}
def calculate_recipe_cost(conn: sqlite3.Connection, recipe_id: int) -> int:
    """SUM(ingredient.unit_cost_cents * recipe_ingredient.quantity) / servings"""
    ...

# Returns: list[sqlite3.Row] with allergen id and name (deduplicated across all ingredients)
def get_recipe_allergens(conn: sqlite3.Connection, recipe_id: int) -> list:
    """Join recipe_ingredients -> ingredients -> ingredient_allergens -> allergens"""
    ...
```

#### Menu Models (app/models/menu_models.py)

```python
# Returns: int (new menu item ID)
def create_menu_item(conn: sqlite3.Connection, name: str, description: str,
                     price_cents: int, category_id: int | None,
                     recipe_id: int | None, is_available: int = 1) -> int:
    ...

# Returns: list[sqlite3.Row]
def get_all_menu_items(conn: sqlite3.Connection) -> list:
    ...

# Returns: list[sqlite3.Row] grouped by category
def get_menu_by_category(conn: sqlite3.Connection) -> list:
    ...

# Returns: sqlite3.Row or None
def get_menu_item(conn: sqlite3.Connection, menu_item_id: int):
    ...

def update_menu_item(conn: sqlite3.Connection, menu_item_id: int, name: str,
                     description: str, price_cents: int, category_id: int | None,
                     recipe_id: int | None, is_available: int) -> None:
    ...

def delete_menu_item(conn: sqlite3.Connection, menu_item_id: int) -> None:
    ...

# Returns: list[sqlite3.Row] with allergen name (via recipe -> ingredients -> allergens)
def get_menu_item_allergens(conn: sqlite3.Connection, menu_item_id: int) -> list:
    ...

# Returns: int or None (recipe cost in cents, None if no recipe linked)
def get_menu_item_cost(conn: sqlite3.Connection, menu_item_id: int) -> int | None:
    ...
```

#### Inventory Models (app/models/inventory_models.py)

```python
# Returns: list[sqlite3.Row] with ingredient name, current_stock, unit, low_stock_threshold
def get_inventory_status(conn: sqlite3.Connection) -> list:
    ...

# Returns: list[sqlite3.Row] where current_stock < low_stock_threshold
def get_low_stock_items(conn: sqlite3.Connection) -> list:
    ...

# Creates a stock movement and updates inventory.current_stock
# Does NOT commit -- caller commits.
# Usage:
#   record_stock_movement(conn, ingredient_id=1, movement_type='receipt',
#                         quantity=50.0, reference_type='purchase_order', reference_id=5)
#   conn.commit()
def record_stock_movement(conn: sqlite3.Connection, ingredient_id: int,
                          movement_type: str, quantity: float,
                          reference_type: str | None = None,
                          reference_id: int | None = None,
                          notes: str | None = None) -> None:
    ...

# Ensure inventory row exists for an ingredient (upsert)
def ensure_inventory_row(conn: sqlite3.Connection, ingredient_id: int) -> None:
    ...

# Returns: list[sqlite3.Row] stock movement history for an ingredient
def get_stock_movements(conn: sqlite3.Connection, ingredient_id: int) -> list:
    ...

# Deduct inventory for all ingredients in an order's recipes
# Does NOT commit -- caller commits.
# Usage:
#   with conn: (inside BEGIN IMMEDIATE)
#     deduct_order_inventory(conn, order_id)
def deduct_order_inventory(conn: sqlite3.Connection, order_id: int) -> None:
    """For each order_item, look up recipe_ingredients, create consumption movements."""
    ...

# Restore inventory for a cancelled order (reverse of deduct)
# Does NOT commit -- caller commits.
def restore_order_inventory(conn: sqlite3.Connection, order_id: int) -> None:
    ...
```

#### Supplier Models (app/models/supplier_models.py)

```python
def create_supplier(conn: sqlite3.Connection, name: str, contact_name: str,
                    phone: str, email: str, address: str, notes: str) -> int:
    ...

def get_all_suppliers(conn: sqlite3.Connection) -> list:
    ...

def get_supplier(conn: sqlite3.Connection, supplier_id: int):
    ...

def update_supplier(conn: sqlite3.Connection, supplier_id: int, name: str,
                    contact_name: str, phone: str, email: str,
                    address: str, notes: str) -> None:
    ...

def delete_supplier(conn: sqlite3.Connection, supplier_id: int) -> None:
    ...
```

#### Purchase Order Models (app/models/purchase_order_models.py)

```python
def create_purchase_order(conn: sqlite3.Connection, supplier_id: int,
                          notes: str) -> int:
    ...

def get_all_purchase_orders(conn: sqlite3.Connection) -> list:
    ...

def get_purchase_order(conn: sqlite3.Connection, po_id: int):
    ...

# Returns: list[sqlite3.Row] with ingredient_id, ingredient name, quantity, unit_cost_cents
def get_purchase_order_items(conn: sqlite3.Connection, po_id: int) -> list:
    ...

# Set PO line items (delete + re-insert pattern)
# MUST validate: len(ingredient_ids) == len(quantities) == len(unit_costs)
def set_purchase_order_items(conn: sqlite3.Connection, po_id: int,
                             ingredient_ids: list[int], quantities: list[float],
                             unit_costs: list[int]) -> None:
    ...

def update_purchase_order_total(conn: sqlite3.Connection, po_id: int) -> None:
    """Recalculate total_cents from line items."""
    ...

# Status transitions with validation
# Usage:
#   submit_purchase_order(conn, po_id)  -- draft -> submitted
#   conn.commit()
def submit_purchase_order(conn: sqlite3.Connection, po_id: int) -> None:
    ...

# Receive PO: updates status, creates stock movements for each line item
# Does NOT commit -- caller commits.
def receive_purchase_order(conn: sqlite3.Connection, po_id: int) -> None:
    """Set status='received', set received_date, create receipt stock movements."""
    ...

def close_purchase_order(conn: sqlite3.Connection, po_id: int) -> None:
    ...
```

#### Order Models (app/models/order_models.py)

```python
def create_order(conn: sqlite3.Connection, table_id: int | None,
                 notes: str) -> int:
    ...

def get_all_orders(conn: sqlite3.Connection, status: str | None = None) -> list:
    ...

def get_order(conn: sqlite3.Connection, order_id: int):
    ...

def get_order_items(conn: sqlite3.Connection, order_id: int) -> list:
    ...

# Set order items (delete + re-insert)
# MUST validate: len(menu_item_ids) == len(quantities)
def set_order_items(conn: sqlite3.Connection, order_id: int,
                    menu_item_ids: list[int], quantities: list[int]) -> None:
    """Delete existing items, insert new ones with current menu_item prices, update total."""
    ...

def update_order_total(conn: sqlite3.Connection, order_id: int) -> None:
    ...

# Status transitions -- each validates current state
# pending -> preparing: triggers inventory deduction (BEGIN IMMEDIATE)
# Usage:
#   start_preparing_order(conn, order_id)  -- handles its own transaction
def start_preparing_order(conn: sqlite3.Connection, order_id: int) -> None:
    """BEGIN IMMEDIATE, verify status=pending, set preparing, deduct inventory, commit."""
    ...

def mark_order_ready(conn: sqlite3.Connection, order_id: int) -> None:
    """preparing -> ready. Does NOT commit."""
    ...

def mark_order_served(conn: sqlite3.Connection, order_id: int) -> None:
    """ready -> served. Does NOT commit."""
    ...

def close_order(conn: sqlite3.Connection, order_id: int) -> None:
    """served -> closed. Does NOT commit."""
    ...

# Cancel: any state -> cancelled. If was preparing+, restore inventory.
def cancel_order(conn: sqlite3.Connection, order_id: int) -> None:
    """BEGIN IMMEDIATE, set cancelled, restore inventory if needed, commit."""
    ...
```

#### Table Models (app/models/table_models.py)

```python
def create_table(conn: sqlite3.Connection, table_number: str,
                 capacity: int, zone: str) -> int:
    ...

def get_all_tables(conn: sqlite3.Connection) -> list:
    ...

def get_table(conn: sqlite3.Connection, table_id: int):
    ...

def update_table(conn: sqlite3.Connection, table_id: int, table_number: str,
                 capacity: int, zone: str) -> None:
    ...

def delete_table(conn: sqlite3.Connection, table_id: int) -> None:
    ...

def update_table_status(conn: sqlite3.Connection, table_id: int, status: str) -> None:
    """Validate status is in allowed set before updating."""
    ...

# Returns: list[sqlite3.Row] with table info and current status
def get_table_status_board(conn: sqlite3.Connection) -> list:
    ...
```

#### Reservation Models (app/models/reservation_models.py)

```python
def create_reservation(conn: sqlite3.Connection, table_id: int, guest_name: str,
                       guest_phone: str, party_size: int, reservation_date: str,
                       reservation_time: str, duration_minutes: int,
                       notes: str) -> int:
    ...

def get_all_reservations(conn: sqlite3.Connection, date: str | None = None) -> list:
    ...

def get_reservation(conn: sqlite3.Connection, reservation_id: int):
    ...

def update_reservation(conn: sqlite3.Connection, reservation_id: int,
                       table_id: int, guest_name: str, guest_phone: str,
                       party_size: int, reservation_date: str,
                       reservation_time: str, duration_minutes: int,
                       notes: str) -> None:
    ...

# Status transitions
def seat_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    """confirmed -> seated, update table status to 'occupied'. Does NOT commit."""
    ...

def complete_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    """seated -> completed, update table status to 'needs_cleaning'. Does NOT commit."""
    ...

def cancel_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    """any -> cancelled, update table status to 'available' if was reserved. Does NOT commit."""
    ...

def no_show_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    """confirmed -> no_show, update table status to 'available'. Does NOT commit."""
    ...

# Check table availability for a given date/time
def is_table_available(conn: sqlite3.Connection, table_id: int,
                       reservation_date: str, reservation_time: str,
                       duration_minutes: int,
                       exclude_reservation_id: int | None = None) -> bool:
    ...
```

#### Staff Models (app/models/staff_models.py)

```python
def create_staff(conn: sqlite3.Connection, name: str, role: str,
                 phone: str, email: str) -> int:
    ...

def get_all_staff(conn: sqlite3.Connection, active_only: bool = True) -> list:
    ...

def get_staff_member(conn: sqlite3.Connection, staff_id: int):
    ...

def update_staff(conn: sqlite3.Connection, staff_id: int, name: str,
                 role: str, phone: str, email: str, is_active: int) -> None:
    ...

def delete_staff(conn: sqlite3.Connection, staff_id: int) -> None:
    ...

# Shift management
def create_shift(conn: sqlite3.Connection, staff_id: int, shift_date: str,
                 start_time: str, end_time: str, role: str, notes: str) -> int:
    ...

def get_shifts_by_date(conn: sqlite3.Connection, date: str) -> list:
    ...

def get_shifts_by_staff(conn: sqlite3.Connection, staff_id: int) -> list:
    ...

def get_shift(conn: sqlite3.Connection, shift_id: int):
    ...

def update_shift(conn: sqlite3.Connection, shift_id: int, staff_id: int,
                 shift_date: str, start_time: str, end_time: str,
                 role: str, notes: str) -> None:
    ...

def delete_shift(conn: sqlite3.Connection, shift_id: int) -> None:
    ...
```

#### Specials Models (app/models/specials_models.py)

```python
def create_special(conn: sqlite3.Connection, name: str, description: str,
                   price_cents: int, menu_item_id: int | None,
                   start_date: str, end_date: str) -> int:
    ...

def get_active_specials(conn: sqlite3.Connection) -> list:
    """Specials where start_date <= today <= end_date and is_active=1."""
    ...

def get_all_specials(conn: sqlite3.Connection) -> list:
    ...

def get_special(conn: sqlite3.Connection, special_id: int):
    ...

def update_special(conn: sqlite3.Connection, special_id: int, name: str,
                   description: str, price_cents: int, menu_item_id: int | None,
                   start_date: str, end_date: str, is_active: int) -> None:
    ...

def delete_special(conn: sqlite3.Connection, special_id: int) -> None:
    ...
```

#### Review Models (app/models/review_models.py)

```python
def create_review(conn: sqlite3.Connection, menu_item_id: int | None,
                  rating: int, guest_name: str, comment: str) -> int:
    ...

def get_all_reviews(conn: sqlite3.Connection) -> list:
    ...

def get_reviews_for_menu_item(conn: sqlite3.Connection, menu_item_id: int) -> list:
    ...

def get_review(conn: sqlite3.Connection, review_id: int):
    ...

def delete_review(conn: sqlite3.Connection, review_id: int) -> None:
    ...

# Returns: float or None (average rating for a menu item)
def get_menu_item_avg_rating(conn: sqlite3.Connection, menu_item_id: int) -> float | None:
    ...

# Returns: dict with overall stats (total_reviews, avg_rating, rating_distribution)
def get_review_summary(conn: sqlite3.Connection) -> dict:
    ...
```

#### Dashboard Models (app/models/dashboard_models.py)

```python
# Returns: dict with summary stats for the dashboard
# Usage:
#   stats = get_dashboard_stats(conn)
#   stats['active_orders'], stats['low_stock_count'], stats['todays_reservations'],
#   stats['todays_revenue_cents'], stats['staff_on_shift']
def get_dashboard_stats(conn: sqlite3.Connection) -> dict:
    ...

# Returns: list[sqlite3.Row] of today's active specials
def get_todays_specials(conn: sqlite3.Connection) -> list:
    ...
```

### Route Table

| Method | Path | Blueprint | Handler | Template |
|--------|------|-----------|---------|----------|
| GET | /health | app | health | JSON |
| GET | /auth/login | auth | login | auth/login.html |
| POST | /auth/login | auth | login_post | redirect |
| GET | /auth/logout | auth | logout | redirect |
| GET | / | dashboard | index | dashboard/index.html |
| GET | /menu | menu | list_items | menu/list.html |
| GET | /menu/create | menu | create_form | menu/form.html |
| POST | /menu/create | menu | create | redirect |
| GET | /menu/<int:id> | menu | detail | menu/detail.html |
| GET | /menu/<int:id>/edit | menu | edit_form | menu/form.html |
| POST | /menu/<int:id>/edit | menu | edit | redirect |
| POST | /menu/<int:id>/delete | menu | delete | redirect |
| GET | /menu/categories | menu | list_categories | menu/categories.html |
| POST | /menu/categories | menu | create_category | redirect |
| POST | /menu/categories/<int:id>/edit | menu | edit_category | redirect |
| POST | /menu/categories/<int:id>/delete | menu | delete_category | redirect |
| GET | /recipes | recipes | list_recipes | recipes/list.html |
| GET | /recipes/create | recipes | create_form | recipes/form.html |
| POST | /recipes/create | recipes | create | redirect |
| GET | /recipes/<int:id> | recipes | detail | recipes/detail.html |
| GET | /recipes/<int:id>/edit | recipes | edit_form | recipes/form.html |
| POST | /recipes/<int:id>/edit | recipes | edit | redirect |
| POST | /recipes/<int:id>/delete | recipes | delete | redirect |
| GET | /ingredients | ingredients | list_ingredients | ingredients/list.html |
| GET | /ingredients/create | ingredients | create_form | ingredients/form.html |
| POST | /ingredients/create | ingredients | create | redirect |
| GET | /ingredients/<int:id> | ingredients | detail | ingredients/detail.html |
| GET | /ingredients/<int:id>/edit | ingredients | edit_form | ingredients/form.html |
| POST | /ingredients/<int:id>/edit | ingredients | edit | redirect |
| POST | /ingredients/<int:id>/delete | ingredients | delete | redirect |
| GET | /inventory | inventory | index | inventory/index.html |
| GET | /inventory/low-stock | inventory | low_stock | inventory/low_stock.html |
| GET | /inventory/<int:ingredient_id>/movements | inventory | movements | inventory/movements.html |
| POST | /inventory/<int:ingredient_id>/adjust | inventory | adjust | redirect |
| GET | /suppliers | suppliers | list_suppliers | suppliers/list.html |
| GET | /suppliers/create | suppliers | create_form | suppliers/form.html |
| POST | /suppliers/create | suppliers | create | redirect |
| GET | /suppliers/<int:id> | suppliers | detail | suppliers/detail.html |
| GET | /suppliers/<int:id>/edit | suppliers | edit_form | suppliers/form.html |
| POST | /suppliers/<int:id>/edit | suppliers | edit | redirect |
| POST | /suppliers/<int:id>/delete | suppliers | delete | redirect |
| GET | /purchase-orders | purchase_orders | list_orders | purchase_orders/list.html |
| GET | /purchase-orders/create | purchase_orders | create_form | purchase_orders/form.html |
| POST | /purchase-orders/create | purchase_orders | create | redirect |
| GET | /purchase-orders/<int:id> | purchase_orders | detail | purchase_orders/detail.html |
| GET | /purchase-orders/<int:id>/edit | purchase_orders | edit_form | purchase_orders/form.html |
| POST | /purchase-orders/<int:id>/edit | purchase_orders | edit | redirect |
| POST | /purchase-orders/<int:id>/submit | purchase_orders | submit | redirect |
| POST | /purchase-orders/<int:id>/receive | purchase_orders | receive | redirect |
| POST | /purchase-orders/<int:id>/close | purchase_orders | close | redirect |
| GET | /orders | orders | list_orders | orders/list.html |
| GET | /orders/kitchen | orders | kitchen_board | orders/kitchen.html |
| GET | /orders/create | orders | create_form | orders/form.html |
| POST | /orders/create | orders | create | redirect |
| GET | /orders/<int:id> | orders | detail | orders/detail.html |
| GET | /orders/<int:id>/edit | orders | edit_form | orders/form.html |
| POST | /orders/<int:id>/edit | orders | edit | redirect |
| POST | /orders/<int:id>/prepare | orders | prepare | redirect |
| POST | /orders/<int:id>/ready | orders | ready | redirect |
| POST | /orders/<int:id>/serve | orders | serve | redirect |
| POST | /orders/<int:id>/close | orders | close_order | redirect |
| POST | /orders/<int:id>/cancel | orders | cancel | redirect |
| GET | /tables | tables | list_tables | tables/list.html |
| GET | /tables/board | tables | status_board | tables/board.html |
| GET | /tables/create | tables | create_form | tables/form.html |
| POST | /tables/create | tables | create | redirect |
| GET | /tables/<int:id>/edit | tables | edit_form | tables/form.html |
| POST | /tables/<int:id>/edit | tables | edit | redirect |
| POST | /tables/<int:id>/delete | tables | delete | redirect |
| POST | /tables/<int:id>/status | tables | update_status | redirect |
| GET | /reservations | reservations | list_reservations | reservations/list.html |
| GET | /reservations/create | reservations | create_form | reservations/form.html |
| POST | /reservations/create | reservations | create | redirect |
| GET | /reservations/<int:id> | reservations | detail | reservations/detail.html |
| GET | /reservations/<int:id>/edit | reservations | edit_form | reservations/form.html |
| POST | /reservations/<int:id>/edit | reservations | edit | redirect |
| POST | /reservations/<int:id>/seat | reservations | seat | redirect |
| POST | /reservations/<int:id>/complete | reservations | complete | redirect |
| POST | /reservations/<int:id>/cancel | reservations | cancel | redirect |
| POST | /reservations/<int:id>/no-show | reservations | no_show | redirect |
| GET | /staff | staff | list_staff | staff/list.html |
| GET | /staff/create | staff | create_form | staff/form.html |
| POST | /staff/create | staff | create | redirect |
| GET | /staff/<int:id> | staff | detail | staff/detail.html |
| GET | /staff/<int:id>/edit | staff | edit_form | staff/form.html |
| POST | /staff/<int:id>/edit | staff | edit | redirect |
| POST | /staff/<int:id>/delete | staff | delete | redirect |
| GET | /staff/schedule | staff | schedule | staff/schedule.html |
| GET | /staff/schedule/create | staff | create_shift_form | staff/shift_form.html |
| POST | /staff/schedule/create | staff | create_shift | redirect |
| GET | /staff/schedule/<int:id>/edit | staff | edit_shift_form | staff/shift_form.html |
| POST | /staff/schedule/<int:id>/edit | staff | edit_shift | redirect |
| POST | /staff/schedule/<int:id>/delete | staff | delete_shift | redirect |
| GET | /specials | specials | list_specials | specials/list.html |
| GET | /specials/create | specials | create_form | specials/form.html |
| POST | /specials/create | specials | create | redirect |
| GET | /specials/<int:id> | specials | detail | specials/detail.html |
| GET | /specials/<int:id>/edit | specials | edit_form | specials/form.html |
| POST | /specials/<int:id>/edit | specials | edit | redirect |
| POST | /specials/<int:id>/delete | specials | delete | redirect |
| GET | /reviews | reviews | list_reviews | reviews/list.html |
| GET | /reviews/create | reviews | create_form | reviews/form.html |
| POST | /reviews/create | reviews | create | redirect |
| GET | /reviews/<int:id> | reviews | detail | reviews/detail.html |
| POST | /reviews/<int:id>/delete | reviews | delete | redirect |
| GET | /reviews/summary | reviews | summary | reviews/summary.html |

### url_for Name Registry

| Blueprint | Function | url_for Call |
|-----------|----------|-------------|
| auth | login | `url_for('auth.login')` |
| auth | login_post | `url_for('auth.login_post')` |
| auth | logout | `url_for('auth.logout')` |
| dashboard | index | `url_for('dashboard.index')` |
| menu | list_items | `url_for('menu.list_items')` |
| menu | create_form | `url_for('menu.create_form')` |
| menu | create | `url_for('menu.create')` |
| menu | detail | `url_for('menu.detail', id=item.id)` |
| menu | edit_form | `url_for('menu.edit_form', id=item.id)` |
| menu | edit | `url_for('menu.edit', id=item.id)` |
| menu | delete | `url_for('menu.delete', id=item.id)` |
| menu | list_categories | `url_for('menu.list_categories')` |
| menu | create_category | `url_for('menu.create_category')` |
| menu | edit_category | `url_for('menu.edit_category', id=cat.id)` |
| menu | delete_category | `url_for('menu.delete_category', id=cat.id)` |
| recipes | list_recipes | `url_for('recipes.list_recipes')` |
| recipes | create_form | `url_for('recipes.create_form')` |
| recipes | create | `url_for('recipes.create')` |
| recipes | detail | `url_for('recipes.detail', id=r.id)` |
| recipes | edit_form | `url_for('recipes.edit_form', id=r.id)` |
| recipes | edit | `url_for('recipes.edit', id=r.id)` |
| recipes | delete | `url_for('recipes.delete', id=r.id)` |
| ingredients | list_ingredients | `url_for('ingredients.list_ingredients')` |
| ingredients | create_form | `url_for('ingredients.create_form')` |
| ingredients | create | `url_for('ingredients.create')` |
| ingredients | detail | `url_for('ingredients.detail', id=i.id)` |
| ingredients | edit_form | `url_for('ingredients.edit_form', id=i.id)` |
| ingredients | edit | `url_for('ingredients.edit', id=i.id)` |
| ingredients | delete | `url_for('ingredients.delete', id=i.id)` |
| inventory | index | `url_for('inventory.index')` |
| inventory | low_stock | `url_for('inventory.low_stock')` |
| inventory | movements | `url_for('inventory.movements', ingredient_id=i.id)` |
| inventory | adjust | `url_for('inventory.adjust', ingredient_id=i.id)` |
| suppliers | list_suppliers | `url_for('suppliers.list_suppliers')` |
| suppliers | create_form | `url_for('suppliers.create_form')` |
| suppliers | create | `url_for('suppliers.create')` |
| suppliers | detail | `url_for('suppliers.detail', id=s.id)` |
| suppliers | edit_form | `url_for('suppliers.edit_form', id=s.id)` |
| suppliers | edit | `url_for('suppliers.edit', id=s.id)` |
| suppliers | delete | `url_for('suppliers.delete', id=s.id)` |
| purchase_orders | list_orders | `url_for('purchase_orders.list_orders')` |
| purchase_orders | create_form | `url_for('purchase_orders.create_form')` |
| purchase_orders | create | `url_for('purchase_orders.create')` |
| purchase_orders | detail | `url_for('purchase_orders.detail', id=po.id)` |
| purchase_orders | edit_form | `url_for('purchase_orders.edit_form', id=po.id)` |
| purchase_orders | edit | `url_for('purchase_orders.edit', id=po.id)` |
| purchase_orders | submit | `url_for('purchase_orders.submit', id=po.id)` |
| purchase_orders | receive | `url_for('purchase_orders.receive', id=po.id)` |
| purchase_orders | close | `url_for('purchase_orders.close', id=po.id)` |
| orders | list_orders | `url_for('orders.list_orders')` |
| orders | kitchen_board | `url_for('orders.kitchen_board')` |
| orders | create_form | `url_for('orders.create_form')` |
| orders | create | `url_for('orders.create')` |
| orders | detail | `url_for('orders.detail', id=o.id)` |
| orders | edit_form | `url_for('orders.edit_form', id=o.id)` |
| orders | edit | `url_for('orders.edit', id=o.id)` |
| orders | prepare | `url_for('orders.prepare', id=o.id)` |
| orders | ready | `url_for('orders.ready', id=o.id)` |
| orders | serve | `url_for('orders.serve', id=o.id)` |
| orders | close_order | `url_for('orders.close_order', id=o.id)` |
| orders | cancel | `url_for('orders.cancel', id=o.id)` |
| tables | list_tables | `url_for('tables.list_tables')` |
| tables | status_board | `url_for('tables.status_board')` |
| tables | create_form | `url_for('tables.create_form')` |
| tables | create | `url_for('tables.create')` |
| tables | edit_form | `url_for('tables.edit_form', id=t.id)` |
| tables | edit | `url_for('tables.edit', id=t.id)` |
| tables | delete | `url_for('tables.delete', id=t.id)` |
| tables | update_status | `url_for('tables.update_status', id=t.id)` |
| reservations | list_reservations | `url_for('reservations.list_reservations')` |
| reservations | create_form | `url_for('reservations.create_form')` |
| reservations | create | `url_for('reservations.create')` |
| reservations | detail | `url_for('reservations.detail', id=r.id)` |
| reservations | edit_form | `url_for('reservations.edit_form', id=r.id)` |
| reservations | edit | `url_for('reservations.edit', id=r.id)` |
| reservations | seat | `url_for('reservations.seat', id=r.id)` |
| reservations | complete | `url_for('reservations.complete', id=r.id)` |
| reservations | cancel | `url_for('reservations.cancel', id=r.id)` |
| reservations | no_show | `url_for('reservations.no_show', id=r.id)` |
| staff | list_staff | `url_for('staff.list_staff')` |
| staff | create_form | `url_for('staff.create_form')` |
| staff | create | `url_for('staff.create')` |
| staff | detail | `url_for('staff.detail', id=s.id)` |
| staff | edit_form | `url_for('staff.edit_form', id=s.id)` |
| staff | edit | `url_for('staff.edit', id=s.id)` |
| staff | delete | `url_for('staff.delete', id=s.id)` |
| staff | schedule | `url_for('staff.schedule')` |
| staff | create_shift_form | `url_for('staff.create_shift_form')` |
| staff | create_shift | `url_for('staff.create_shift')` |
| staff | edit_shift_form | `url_for('staff.edit_shift_form', id=sh.id)` |
| staff | edit_shift | `url_for('staff.edit_shift', id=sh.id)` |
| staff | delete_shift | `url_for('staff.delete_shift', id=sh.id)` |
| specials | list_specials | `url_for('specials.list_specials')` |
| specials | create_form | `url_for('specials.create_form')` |
| specials | create | `url_for('specials.create')` |
| specials | detail | `url_for('specials.detail', id=sp.id)` |
| specials | edit_form | `url_for('specials.edit_form', id=sp.id)` |
| specials | edit | `url_for('specials.edit', id=sp.id)` |
| specials | delete | `url_for('specials.delete', id=sp.id)` |
| reviews | list_reviews | `url_for('reviews.list_reviews')` |
| reviews | create_form | `url_for('reviews.create_form')` |
| reviews | create | `url_for('reviews.create')` |
| reviews | detail | `url_for('reviews.detail', id=rv.id)` |
| reviews | delete | `url_for('reviews.delete', id=rv.id)` |
| reviews | summary | `url_for('reviews.summary')` |

### Template Render Context

#### Base Template (app/templates/base.html)

```html
<!-- Bootstrap 5 CDN -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">

<!-- Navigation: links to all major sections -->
<!-- Flash messages: see Coordinated Behaviors -->
<!-- Content block: {% block content %}{% endblock %} -->
<!-- Title block: {% block title %}RestaurantOps{% endblock %} -->
```

**No CSP header.** Bootstrap 5 is loaded from cdn.jsdelivr.net. Adding
`script-src 'self'` would break all Bootstrap JS. (Lesson from GigSheet FC38.)

#### Dashboard (dashboard/index.html)

```python
render_template('dashboard/index.html',
    stats=get_dashboard_stats(conn),        # dict with keys below
    active_specials=get_todays_specials(conn),  # list[Row]
    low_stock=get_low_stock_items(conn),    # list[Row]
    active_orders=get_all_orders(conn, status='pending'),  # list[Row]
    todays_reservations=get_all_reservations(conn, date=today_str)  # list[Row]
)
# stats keys: active_orders, low_stock_count, todays_reservations,
#             todays_revenue_cents, staff_on_shift
```

#### Auth Templates

```python
# auth/login.html
render_template('auth/login.html')
# Form: password field, submit button, csrf_token
```

#### Menu Templates

```python
# menu/list.html
render_template('menu/list.html',
    items=get_all_menu_items(conn),
    categories=get_all_categories(conn)
)

# menu/form.html (create and edit)
render_template('menu/form.html',
    item=get_menu_item(conn, id) if editing else None,
    categories=get_all_categories(conn),
    recipes=get_all_recipes(conn)
)

# menu/detail.html
render_template('menu/detail.html',
    item=get_menu_item(conn, id),
    allergens=get_menu_item_allergens(conn, id),
    cost_cents=get_menu_item_cost(conn, id),
    avg_rating=get_menu_item_avg_rating(conn, id)
)

# menu/categories.html
render_template('menu/categories.html',
    categories=get_all_categories(conn)
)
```

#### Recipe Templates

```python
# recipes/list.html
render_template('recipes/list.html',
    recipes=get_all_recipes(conn)
)

# recipes/form.html
render_template('recipes/form.html',
    recipe=get_recipe(conn, id) if editing else None,
    ingredients=get_all_ingredients(conn),
    recipe_ingredients=get_recipe_ingredients(conn, id) if editing else []
)

# recipes/detail.html
render_template('recipes/detail.html',
    recipe=get_recipe(conn, id),
    ingredients=get_recipe_ingredients(conn, id),
    allergens=get_recipe_allergens(conn, id),
    cost_cents=calculate_recipe_cost(conn, id)
)
```

#### Ingredient Templates

```python
# ingredients/list.html
render_template('ingredients/list.html',
    ingredients=get_all_ingredients(conn)
)

# ingredients/form.html
render_template('ingredients/form.html',
    ingredient=get_ingredient(conn, id) if editing else None,
    suppliers=get_all_suppliers(conn),
    allergens=get_all_allergens(conn),
    ingredient_allergens=get_ingredient_allergens(conn, id) if editing else []
)

# ingredients/detail.html
render_template('ingredients/detail.html',
    ingredient=get_ingredient(conn, id),
    allergens=get_ingredient_allergens(conn, id),
    movements=get_stock_movements(conn, id)
)
```

#### Inventory Templates

```python
# inventory/index.html
render_template('inventory/index.html',
    inventory=get_inventory_status(conn)
)

# inventory/low_stock.html
render_template('inventory/low_stock.html',
    items=get_low_stock_items(conn)
)

# inventory/movements.html
render_template('inventory/movements.html',
    ingredient=get_ingredient(conn, ingredient_id),
    movements=get_stock_movements(conn, ingredient_id)
)
```

#### Supplier Templates

```python
# suppliers/list.html
render_template('suppliers/list.html',
    suppliers=get_all_suppliers(conn)
)

# suppliers/form.html
render_template('suppliers/form.html',
    supplier=get_supplier(conn, id) if editing else None
)

# suppliers/detail.html
render_template('suppliers/detail.html',
    supplier=get_supplier(conn, id)
)
```

#### Purchase Order Templates

```python
# purchase_orders/list.html
render_template('purchase_orders/list.html',
    orders=get_all_purchase_orders(conn)
)

# purchase_orders/form.html
render_template('purchase_orders/form.html',
    order=get_purchase_order(conn, id) if editing else None,
    items=get_purchase_order_items(conn, id) if editing else [],
    suppliers=get_all_suppliers(conn),
    ingredients=get_all_ingredients(conn)
)

# purchase_orders/detail.html
render_template('purchase_orders/detail.html',
    order=get_purchase_order(conn, id),
    items=get_purchase_order_items(conn, id)
)
```

#### Order Templates

```python
# orders/list.html
render_template('orders/list.html',
    orders=get_all_orders(conn)
)

# orders/kitchen.html
render_template('orders/kitchen.html',
    pending=get_all_orders(conn, status='pending'),
    preparing=get_all_orders(conn, status='preparing'),
    ready=get_all_orders(conn, status='ready')
)

# orders/form.html
render_template('orders/form.html',
    order=get_order(conn, id) if editing else None,
    items=get_order_items(conn, id) if editing else [],
    menu_items=get_all_menu_items(conn),
    tables=get_all_tables(conn)
)

# orders/detail.html
render_template('orders/detail.html',
    order=get_order(conn, id),
    items=get_order_items(conn, id)
)
```

#### Table Templates

```python
# tables/list.html
render_template('tables/list.html',
    tables=get_all_tables(conn)
)

# tables/board.html
render_template('tables/board.html',
    tables=get_table_status_board(conn)
)

# tables/form.html
render_template('tables/form.html',
    table=get_table(conn, id) if editing else None
)
```

#### Reservation Templates

```python
# reservations/list.html
render_template('reservations/list.html',
    reservations=get_all_reservations(conn, date=request.args.get('date')),
    tables=get_all_tables(conn)
)

# reservations/form.html
render_template('reservations/form.html',
    reservation=get_reservation(conn, id) if editing else None,
    tables=get_all_tables(conn)
)

# reservations/detail.html
render_template('reservations/detail.html',
    reservation=get_reservation(conn, id)
)
```

#### Staff Templates

```python
# staff/list.html
render_template('staff/list.html',
    staff=get_all_staff(conn)
)

# staff/form.html
render_template('staff/form.html',
    member=get_staff_member(conn, id) if editing else None
)

# staff/detail.html
render_template('staff/detail.html',
    member=get_staff_member(conn, id),
    shifts=get_shifts_by_staff(conn, id)
)

# staff/schedule.html
render_template('staff/schedule.html',
    shifts=get_shifts_by_date(conn, date=request.args.get('date', today_str)),
    staff=get_all_staff(conn)
)

# staff/shift_form.html
render_template('staff/shift_form.html',
    shift=get_shift(conn, id) if editing else None,
    staff=get_all_staff(conn)
)
```

#### Specials Templates

```python
# specials/list.html
render_template('specials/list.html',
    specials=get_all_specials(conn)
)

# specials/form.html
render_template('specials/form.html',
    special=get_special(conn, id) if editing else None,
    menu_items=get_all_menu_items(conn)
)

# specials/detail.html
render_template('specials/detail.html',
    special=get_special(conn, id)
)
```

#### Review Templates

```python
# reviews/list.html
render_template('reviews/list.html',
    reviews=get_all_reviews(conn)
)

# reviews/form.html
render_template('reviews/form.html',
    menu_items=get_all_menu_items(conn)
)

# reviews/detail.html
render_template('reviews/detail.html',
    review=get_review(conn, id)
)

# reviews/summary.html
render_template('reviews/summary.html',
    summary=get_review_summary(conn)
)
```

### CSRF in Templates

Every POST form MUST include:

```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <!-- form fields -->
</form>
```

### Form Field Names (FC9 Prevention)

#### Menu Item Form
- `name` (text), `description` (textarea), `price` (text, decimal dollars — multiply by 100),
  `category_id` (select), `recipe_id` (select), `is_available` (checkbox)

#### Recipe Form
- `name` (text), `description` (textarea), `instructions` (textarea),
  `prep_time_minutes` (number), `cook_time_minutes` (number), `servings` (number)
- Parallel arrays: `ingredient_ids[]` (hidden), `quantities[]` (number), `units[]` (select)

#### Ingredient Form
- `name` (text), `unit` (select), `unit_cost` (text, decimal dollars — multiply by 100),
  `supplier_id` (select), `low_stock_threshold` (number)
- Allergens: `allergen_ids` (multiple checkboxes, use `request.form.getlist('allergen_ids')`)

#### Inventory Adjustment Form
- `quantity` (number, can be negative), `movement_type` (select: adjustment/waste),
  `notes` (textarea)

#### Supplier Form
- `name` (text), `contact_name` (text), `phone` (text), `email` (text),
  `address` (textarea), `notes` (textarea)

#### Purchase Order Form
- `supplier_id` (select), `notes` (textarea)
- Parallel arrays: `ingredient_ids[]` (hidden), `quantities[]` (number), `unit_costs[]` (text, decimal)

#### Order Form
- `table_id` (select), `notes` (textarea)
- Parallel arrays: `menu_item_ids[]` (hidden), `quantities[]` (number)

#### Table Form
- `table_number` (text), `capacity` (number), `zone` (select)

#### Table Status Form
- `status` (select: available/reserved/occupied/needs_cleaning)

#### Reservation Form
- `table_id` (select), `guest_name` (text), `guest_phone` (text),
  `party_size` (number), `reservation_date` (date), `reservation_time` (time),
  `duration_minutes` (number), `notes` (textarea)

#### Staff Form
- `name` (text), `role` (select: chef/sous_chef/server/host/busser/manager),
  `phone` (text), `email` (text), `is_active` (checkbox, edit only)

#### Shift Form
- `staff_id` (select), `shift_date` (date), `start_time` (time),
  `end_time` (time), `role` (select), `notes` (textarea)

#### Special Form
- `name` (text), `description` (textarea), `price` (text, decimal dollars),
  `menu_item_id` (select, optional), `start_date` (date), `end_date` (date),
  `is_active` (checkbox, edit only)

#### Review Form
- `menu_item_id` (select, optional), `rating` (select: 1-5),
  `guest_name` (text), `comment` (textarea)

### Input Validation Rules

```python
# Money: accept decimal dollars, convert to integer cents
# Usage in every route that handles price/cost:
raw = request.form.get('price', '0')
try:
    price_cents = int(round(float(raw) * 100))
    if price_cents < 0:
        price_cents = 0
except (ValueError, TypeError):
    price_cents = 0

# Parallel array length check (MANDATORY before zip):
ids = request.form.getlist('ingredient_ids[]')
qtys = request.form.getlist('quantities[]')
units = request.form.getlist('units[]')
if not (len(ids) == len(qtys) == len(units)):
    flash('Form data mismatch. Please try again.', 'error')
    return redirect(request.url)

# String fields: strip + max length
name = request.form.get('name', '').strip()[:200]
if not name:
    flash('Name is required.', 'error')
    return redirect(request.url)

# Integer fields: safe parsing
try:
    capacity = int(request.form.get('capacity', 4))
    if capacity < 1:
        capacity = 1
except (ValueError, TypeError):
    capacity = 4
```

### Coordinated Behaviors (MANDATORY for all agents)

#### 1. Flash Messages

```python
# Success: green
flash('Item created successfully.', 'success')

# Error: red
flash('Name is required.', 'error')

# Warning: yellow
flash('Low stock warning.', 'warning')

# Info: blue
flash('Order status updated.', 'info')
```

Template display (in base.html):
```html
{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}
<div class="container mt-3">
    {% for category, message in messages %}
    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
    {% endfor %}
</div>
{% endif %}
{% endwith %}
```

#### 2. Error Handling in Routes

```python
# 404 pattern:
item = get_menu_item(conn, id)
if item is None:
    flash('Item not found.', 'error')
    return redirect(url_for('menu.list_items'))

# Never expose raw exception messages to users.
# Log internally, flash generic message.
```

#### 3. Page Titles

Every template sets `{% block title %}Section - RestaurantOps{% endblock %}`.

#### 4. Table Styling

All data tables use Bootstrap classes:
```html
<table class="table table-striped table-hover">
    <thead class="table-dark">
        <tr><th>...</th></tr>
    </thead>
    <tbody>...</tbody>
</table>
```

#### 5. Form Styling

All forms use Bootstrap form classes:
```html
<div class="mb-3">
    <label for="name" class="form-label">Name</label>
    <input type="text" class="form-control" id="name" name="name" required>
</div>
```

Submit buttons: `<button type="submit" class="btn btn-primary">Save</button>`
Cancel links: `<a href="..." class="btn btn-secondary">Cancel</a>`
Delete buttons: `<button type="submit" class="btn btn-danger">Delete</button>`

#### 6. Empty States

When a list is empty:
```html
{% if not items %}
<div class="text-center text-muted py-5">
    <p>No items found.</p>
    <a href="{{ url_for('...create_form') }}" class="btn btn-primary">Add First Item</a>
</div>
{% endif %}
```

#### 7. Navigation

Base template navbar with links to all major sections:
Dashboard, Menu, Recipes, Ingredients, Inventory, Suppliers, Purchase Orders,
Orders, Tables, Reservations, Staff, Specials, Reviews.

Active link highlighted with Bootstrap `active` class based on `request.endpoint`.

#### 8. Database Connection Pattern

**CRITICAL: `isolation_level=None` is set in `get_db()`.** This disables
Python's implicit transaction management. All write routes MUST call
`conn.commit()` explicitly. There are no implicit transactions.

Every route that reads only:
```python
from app.db import get_db
conn = get_db()
# ... SELECT queries, no commit needed ...
```

Every route that writes (INSERT/UPDATE/DELETE):
```python
from app.db import get_db
conn = get_db()
conn.execute("BEGIN")
# ... INSERT/UPDATE/DELETE ...
conn.commit()
```

For atomic multi-table operations (order preparing, PO receiving):
```python
from app.db import get_db
conn = get_db()
conn.execute("BEGIN IMMEDIATE")
try:
    # ... multiple operations ...
    conn.commit()
except Exception:
    conn.rollback()
    flash('Operation failed. Please try again.', 'error')
    return redirect(...)
```

#### 9. SQLite PRAGMAs (per-connection, not per-database)

**Per-connection** (set in `get_db()` on every request):
```python
conn.execute("PRAGMA foreign_keys=ON")
conn.execute("PRAGMA busy_timeout=5000")
```

**Per-database** (set once in `init_db()`, persists forever):
```python
conn.execute("PRAGMA journal_mode=WAL")
```

Do NOT create additional `sqlite3.connect()` calls anywhere. All database
access MUST go through `get_db()` from `app/db.py`. Creating a connection
without the per-connection PRAGMAs causes concurrency bugs (FC40).

#### 10. Status Badge Styling

```html
<!-- Order status -->
<span class="badge bg-warning">pending</span>
<span class="badge bg-primary">preparing</span>
<span class="badge bg-info">ready</span>
<span class="badge bg-success">served</span>
<span class="badge bg-secondary">closed</span>
<span class="badge bg-danger">cancelled</span>

<!-- Table status -->
<span class="badge bg-success">available</span>
<span class="badge bg-warning">reserved</span>
<span class="badge bg-primary">occupied</span>
<span class="badge bg-info">needs_cleaning</span>

<!-- PO status -->
<span class="badge bg-secondary">draft</span>
<span class="badge bg-primary">submitted</span>
<span class="badge bg-success">received</span>
<span class="badge bg-dark">closed</span>
```

### Cross-Boundary Wiring Table

| Caller | Callee Function | Module | Notes |
|--------|----------------|--------|-------|
| orders.prepare | deduct_order_inventory(conn, order_id) | inventory_models | BEGIN IMMEDIATE in caller |
| orders.cancel | restore_order_inventory(conn, order_id) | inventory_models | BEGIN IMMEDIATE in caller |
| purchase_orders.receive | receive_purchase_order(conn, po_id) | purchase_order_models | Calls record_stock_movement internally |
| receive_purchase_order | record_stock_movement(conn, ...) | inventory_models | Does NOT commit |
| menu.detail | calculate_recipe_cost(conn, recipe_id) | recipe_models | Read-only |
| menu.detail | get_menu_item_allergens(conn, id) | menu_models | Read-only JOIN |
| menu.detail | get_menu_item_avg_rating(conn, id) | review_models | Read-only |
| orders.form | get_all_menu_items(conn) | menu_models | Read-only for select |
| orders.form | get_all_tables(conn) | table_models | Read-only for select |
| reservations.seat | update_table_status(conn, table_id, 'occupied') | table_models | Does NOT commit |
| reservations.complete | update_table_status(conn, table_id, 'needs_cleaning') | table_models | Does NOT commit |
| reservations.cancel | update_table_status(conn, table_id, 'available') | table_models | Does NOT commit |
| reservations.no_show | update_table_status(conn, table_id, 'available') | table_models | Does NOT commit |
| dashboard.index | get_dashboard_stats(conn) | dashboard_models | Read-only |
| dashboard.index | get_todays_specials(conn) | dashboard_models | Read-only |
| dashboard.index | get_low_stock_items(conn) | inventory_models | Read-only |
| dashboard.index | get_all_orders(conn, 'pending') | order_models | Read-only |
| dashboard.index | get_all_reservations(conn, today) | reservation_models | Read-only |

### File Assignment Boundaries

#### Agent: core (app factory + database + init)
- `restaurantops/app/__init__.py`
- `restaurantops/app/db.py`
- `restaurantops/app/filters.py`
- `restaurantops/app/schema.sql`
- `restaurantops/app/init_db.py`
- `restaurantops/run.py`
- `restaurantops/requirements.txt`
- `restaurantops/.gitignore`

#### Agent: layout (base template + static)
- `restaurantops/app/templates/base.html`
- `restaurantops/app/static/style.css`

#### Agent: dashboard_models
- `restaurantops/app/models/dashboard_models.py`

#### Agent: dashboard_routes
- `restaurantops/app/blueprints/dashboard/__init__.py`
- `restaurantops/app/blueprints/dashboard/routes.py`
- `restaurantops/app/templates/dashboard/index.html`

#### Agent: auth (routes + templates)
- `restaurantops/app/blueprints/auth/__init__.py`
- `restaurantops/app/blueprints/auth/routes.py`
- `restaurantops/app/templates/auth/login.html`

#### Agent: menu_models
- `restaurantops/app/models/menu_models.py`
- `restaurantops/app/models/category_models.py`

#### Agent: menu_routes
- `restaurantops/app/blueprints/menu/__init__.py`
- `restaurantops/app/blueprints/menu/routes.py`
- `restaurantops/app/templates/menu/list.html`
- `restaurantops/app/templates/menu/form.html`
- `restaurantops/app/templates/menu/detail.html`
- `restaurantops/app/templates/menu/categories.html`

#### Agent: recipe_models
- `restaurantops/app/models/recipe_models.py`

#### Agent: recipe_routes
- `restaurantops/app/blueprints/recipes/__init__.py`
- `restaurantops/app/blueprints/recipes/routes.py`
- `restaurantops/app/templates/recipes/list.html`
- `restaurantops/app/templates/recipes/form.html`
- `restaurantops/app/templates/recipes/detail.html`

#### Agent: ingredient_models
- `restaurantops/app/models/ingredient_models.py`
- `restaurantops/app/models/core_models.py`

#### Agent: ingredient_routes
- `restaurantops/app/blueprints/ingredients/__init__.py`
- `restaurantops/app/blueprints/ingredients/routes.py`
- `restaurantops/app/templates/ingredients/list.html`
- `restaurantops/app/templates/ingredients/form.html`
- `restaurantops/app/templates/ingredients/detail.html`

#### Agent: inventory_models
- `restaurantops/app/models/inventory_models.py`

#### Agent: inventory_routes
- `restaurantops/app/blueprints/inventory/__init__.py`
- `restaurantops/app/blueprints/inventory/routes.py`
- `restaurantops/app/templates/inventory/index.html`
- `restaurantops/app/templates/inventory/low_stock.html`
- `restaurantops/app/templates/inventory/movements.html`

#### Agent: supplier_models
- `restaurantops/app/models/supplier_models.py`

#### Agent: supplier_routes
- `restaurantops/app/blueprints/suppliers/__init__.py`
- `restaurantops/app/blueprints/suppliers/routes.py`
- `restaurantops/app/templates/suppliers/list.html`
- `restaurantops/app/templates/suppliers/form.html`
- `restaurantops/app/templates/suppliers/detail.html`

#### Agent: po_models (purchase order models)
- `restaurantops/app/models/purchase_order_models.py`

#### Agent: po_routes (purchase order routes)
- `restaurantops/app/blueprints/purchase_orders/__init__.py`
- `restaurantops/app/blueprints/purchase_orders/routes.py`
- `restaurantops/app/templates/purchase_orders/list.html`
- `restaurantops/app/templates/purchase_orders/form.html`
- `restaurantops/app/templates/purchase_orders/detail.html`

#### Agent: order_models
- `restaurantops/app/models/order_models.py`

#### Agent: order_routes
- `restaurantops/app/blueprints/orders/__init__.py`
- `restaurantops/app/blueprints/orders/routes.py`
- `restaurantops/app/templates/orders/list.html`
- `restaurantops/app/templates/orders/form.html`
- `restaurantops/app/templates/orders/detail.html`
- `restaurantops/app/templates/orders/kitchen.html`

#### Agent: table_models
- `restaurantops/app/models/table_models.py`

#### Agent: table_routes
- `restaurantops/app/blueprints/tables/__init__.py`
- `restaurantops/app/blueprints/tables/routes.py`
- `restaurantops/app/templates/tables/list.html`
- `restaurantops/app/templates/tables/form.html`
- `restaurantops/app/templates/tables/board.html`

#### Agent: reservation_models
- `restaurantops/app/models/reservation_models.py`

#### Agent: reservation_routes
- `restaurantops/app/blueprints/reservations/__init__.py`
- `restaurantops/app/blueprints/reservations/routes.py`
- `restaurantops/app/templates/reservations/list.html`
- `restaurantops/app/templates/reservations/form.html`
- `restaurantops/app/templates/reservations/detail.html`

#### Agent: staff_models
- `restaurantops/app/models/staff_models.py`

#### Agent: staff_routes
- `restaurantops/app/blueprints/staff/__init__.py`
- `restaurantops/app/blueprints/staff/routes.py`
- `restaurantops/app/templates/staff/list.html`
- `restaurantops/app/templates/staff/form.html`
- `restaurantops/app/templates/staff/detail.html`
- `restaurantops/app/templates/staff/schedule.html`
- `restaurantops/app/templates/staff/shift_form.html`

#### Agent: specials_models
- `restaurantops/app/models/specials_models.py`

#### Agent: specials_routes
- `restaurantops/app/blueprints/specials/__init__.py`
- `restaurantops/app/blueprints/specials/routes.py`
- `restaurantops/app/templates/specials/list.html`
- `restaurantops/app/templates/specials/form.html`
- `restaurantops/app/templates/specials/detail.html`

#### Agent: review_models
- `restaurantops/app/models/review_models.py`

#### Agent: review_routes
- `restaurantops/app/blueprints/reviews/__init__.py`
- `restaurantops/app/blueprints/reviews/routes.py`
- `restaurantops/app/templates/reviews/list.html`
- `restaurantops/app/templates/reviews/form.html`
- `restaurantops/app/templates/reviews/detail.html`
- `restaurantops/app/templates/reviews/summary.html`

**Total: 29 agents.** (core, layout, auth, + 13 model/route pairs for
dashboard, menu, recipes, ingredients, inventory, suppliers, purchase_orders,
orders, tables, reservations, staff, specials, reviews.) Each owns distinct
files. No overlap.

### Swarm Agent Assignment

| # | Agent | Files | Dependencies |
|---|-------|-------|-------------|
| 1 | core | app/__init__.py, app/db.py, app/filters.py, schema.sql, init_db.py, run.py, requirements.txt, .gitignore | None |
| 2 | layout | templates/base.html, static/style.css | None |
| 3 | auth | blueprints/auth/__init__.py, blueprints/auth/routes.py, templates/auth/login.html | core |
| 4 | ingredient_models | models/ingredient_models.py, models/core_models.py | core |
| 5 | supplier_models | models/supplier_models.py | core |
| 6 | recipe_models | models/recipe_models.py | core, ingredient_models |
| 7 | menu_models | models/menu_models.py, models/category_models.py | core, recipe_models |
| 8 | inventory_models | models/inventory_models.py | core |
| 9 | table_models | models/table_models.py | core |
| 10 | reservation_models | models/reservation_models.py | core, table_models |
| 11 | order_models | models/order_models.py | core, inventory_models |
| 12 | staff_models | models/staff_models.py | core |
| 13 | specials_models | models/specials_models.py | core |
| 14 | review_models | models/review_models.py | core |
| 15 | po_models | models/purchase_order_models.py | core, inventory_models |
| 16 | dashboard_models | models/dashboard_models.py | core |
| 17 | ingredient_routes | blueprints/ingredients/__init__.py, blueprints/ingredients/routes.py, templates/ingredients/list.html, templates/ingredients/form.html, templates/ingredients/detail.html | ingredient_models |
| 18 | supplier_routes | blueprints/suppliers/__init__.py, blueprints/suppliers/routes.py, templates/suppliers/list.html, templates/suppliers/form.html, templates/suppliers/detail.html | supplier_models |
| 19 | recipe_routes | blueprints/recipes/__init__.py, blueprints/recipes/routes.py, templates/recipes/list.html, templates/recipes/form.html, templates/recipes/detail.html | recipe_models, ingredient_models |
| 20 | menu_routes | blueprints/menu/__init__.py, blueprints/menu/routes.py, templates/menu/list.html, templates/menu/form.html, templates/menu/detail.html, templates/menu/categories.html | menu_models, recipe_models, review_models |
| 21 | inventory_routes | blueprints/inventory/__init__.py, blueprints/inventory/routes.py, templates/inventory/index.html, templates/inventory/low_stock.html, templates/inventory/movements.html | inventory_models, ingredient_models |
| 22 | table_routes | blueprints/tables/__init__.py, blueprints/tables/routes.py, templates/tables/list.html, templates/tables/form.html, templates/tables/board.html | table_models |
| 23 | reservation_routes | blueprints/reservations/__init__.py, blueprints/reservations/routes.py, templates/reservations/list.html, templates/reservations/form.html, templates/reservations/detail.html | reservation_models, table_models |
| 24 | order_routes | blueprints/orders/__init__.py, blueprints/orders/routes.py, templates/orders/list.html, templates/orders/form.html, templates/orders/detail.html, templates/orders/kitchen.html | order_models, menu_models, table_models |
| 25 | po_routes | blueprints/purchase_orders/__init__.py, blueprints/purchase_orders/routes.py, templates/purchase_orders/list.html, templates/purchase_orders/form.html, templates/purchase_orders/detail.html | po_models, supplier_models, ingredient_models |
| 26 | staff_routes | blueprints/staff/__init__.py, blueprints/staff/routes.py, templates/staff/list.html, templates/staff/form.html, templates/staff/detail.html, templates/staff/schedule.html, templates/staff/shift_form.html | staff_models |
| 27 | specials_routes | blueprints/specials/__init__.py, blueprints/specials/routes.py, templates/specials/list.html, templates/specials/form.html, templates/specials/detail.html | specials_models, menu_models |
| 28 | review_routes | blueprints/reviews/__init__.py, blueprints/reviews/routes.py, templates/reviews/list.html, templates/reviews/form.html, templates/reviews/detail.html, templates/reviews/summary.html | review_models, menu_models |
| 29 | dashboard_routes | blueprints/dashboard/__init__.py, blueprints/dashboard/routes.py, templates/dashboard/index.html | dashboard_models, inventory_models, order_models, reservation_models |

**Revised total: 29 agents.** (Added dashboard_models as separate from dashboard_routes.)

All file paths are relative to `restaurantops/`.

---

## Acceptance Tests

### Happy Path

- WHEN a user visits /auth/login and submits the correct password THE SYSTEM SHALL set session['authenticated'] and redirect to /
- WHEN a user visits / THE SYSTEM SHALL display dashboard with active orders, low stock, today's reservations, and specials
- WHEN a user creates a menu item with price $12.50 THE SYSTEM SHALL store 1250 in price_cents
- WHEN a user creates a recipe with 3 ingredients THE SYSTEM SHALL display calculated cost from ingredient prices
- WHEN a user views a menu item linked to a recipe THE SYSTEM SHALL display all allergens from the recipe's ingredients
- WHEN a user creates a purchase order and marks it received THE SYSTEM SHALL increase inventory for each line item
- WHEN a user creates an order and moves it to "preparing" THE SYSTEM SHALL deduct inventory for all recipe ingredients
- WHEN a user cancels a "preparing" order THE SYSTEM SHALL restore the deducted inventory
- WHEN a user creates a reservation THE SYSTEM SHALL check table availability for the requested time
- WHEN a user seats a reservation THE SYSTEM SHALL update the table status to "occupied"

### Error Cases

- WHEN a user submits an incorrect password THE SYSTEM SHALL flash an error and re-render login
- WHEN a user tries to receive an already-received purchase order THE SYSTEM SHALL flash an error
- WHEN a user tries to prepare an order that is not "pending" THE SYSTEM SHALL flash an error
- WHEN a user submits a recipe form with mismatched parallel arrays THE SYSTEM SHALL flash "Form data mismatch" and redirect back
- WHEN a user tries to reserve an already-reserved table at the same time THE SYSTEM SHALL flash availability error

### Verification Commands

```bash
# Init database
cd restaurantops && .venv/bin/python -m app.init_db

# Run app
cd restaurantops && .venv/bin/python run.py

# Smoke test (write to file first)
cd restaurantops && .venv/bin/python test_smoke.py
```

---

## Feed-Forward

- **Hardest decision:** Splitting models and routes into separate agents (28→29 agents) to keep file ownership clean while maintaining cross-boundary data flows. The alternative (one agent per feature, 14 agents) would mean larger agents with more files but simpler wiring.
- **Rejected alternatives:** Single agent per feature (simpler but too many files per agent at this scale), JavaScript kitchen display (spec says server-rendered), per-user auth (unnecessary for single-location MVP), denormalized allergen/cost columns (staleness risk).
- **Least confident:** Whether the 29-agent model/route split produces correct cross-boundary imports. Each route agent imports from model modules owned by other agents. The Cross-Boundary Wiring Table must be complete, or routes will import nonexistent functions. The inventory deduction flow (orders → inventory_models) is the highest-risk cross-boundary path.
