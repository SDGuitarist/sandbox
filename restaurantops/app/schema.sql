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
