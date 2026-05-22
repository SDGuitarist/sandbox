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
    current_batch_id INTEGER UNIQUE,
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
