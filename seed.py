"""
Seed script for BrewOps development database.

Populates the database with sample data: recipes, ingredients,
recipe_ingredients, tanks, taps, staff, and batches.

Usage:
    python seed.py

Idempotent -- safe to run multiple times (uses ON CONFLICT DO NOTHING).
"""

import sqlite3
import os


DB_PATH = os.environ.get('DATABASE_PATH', 'brewops.db')
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')


def seed():
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')

    # Read and execute schema first (creates tables if they don't exist)
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())

    # Re-enable foreign keys after executescript (executescript resets PRAGMAs)
    conn.execute('PRAGMA foreign_keys=ON')

    # --- Recipes ---
    conn.execute(
        "INSERT OR IGNORE INTO recipes (id, name, style, target_abv, notes) "
        "VALUES (1, 'Hop Rocket IPA', 'IPA', 6.5, 'West Coast style with citrus hop character')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipes (id, name, style, target_abv, notes) "
        "VALUES (2, 'Midnight Stout', 'Stout', 5.8, 'Rich and roasty with chocolate notes')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipes (id, name, style, target_abv, notes) "
        "VALUES (3, 'Golden Wheat', 'Wheat', 4.5, 'Light and refreshing summer wheat ale')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipes (id, name, style, target_abv, notes) "
        "VALUES (4, 'Czech Pilsner', 'Pilsner', 4.8, 'Crisp and clean with noble hop bitterness')"
    )

    # --- Ingredients ---
    conn.execute(
        "INSERT OR IGNORE INTO ingredients (id, name, category, stock_qty, unit, low_stock_threshold) "
        "VALUES (1, 'Pale Malt', 'grain', 100.0, 'lb', 20.0)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO ingredients (id, name, category, stock_qty, unit, low_stock_threshold) "
        "VALUES (2, 'Cascade Hops', 'hops', 15.0, 'oz', 4.0)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO ingredients (id, name, category, stock_qty, unit, low_stock_threshold) "
        "VALUES (3, 'US-05 Yeast', 'yeast', 10.0, 'pkg', 3.0)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO ingredients (id, name, category, stock_qty, unit, low_stock_threshold) "
        "VALUES (4, 'Chocolate Malt', 'grain', 25.0, 'lb', 5.0)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO ingredients (id, name, category, stock_qty, unit, low_stock_threshold) "
        "VALUES (5, 'White Wheat Malt', 'grain', 40.0, 'lb', 10.0)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO ingredients (id, name, category, stock_qty, unit, low_stock_threshold) "
        "VALUES (6, 'Saaz Hops', 'hops', 8.0, 'oz', 3.0)"
    )

    # --- Recipe Ingredients (linking recipes to ingredients with quantities) ---
    # Hop Rocket IPA: Pale Malt 12 lb, Cascade Hops 3 oz, US-05 Yeast 1 pkg
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (1, 1, 1, 12.0, 'lb')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (2, 1, 2, 3.0, 'oz')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (3, 1, 3, 1.0, 'pkg')"
    )
    # Midnight Stout: Pale Malt 10 lb, Chocolate Malt 3 lb, US-05 Yeast 1 pkg
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (4, 2, 1, 10.0, 'lb')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (5, 2, 4, 3.0, 'lb')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (6, 2, 3, 1.0, 'pkg')"
    )
    # Golden Wheat: Pale Malt 5 lb, White Wheat Malt 5 lb, US-05 Yeast 1 pkg
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (7, 3, 1, 5.0, 'lb')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (8, 3, 5, 5.0, 'lb')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (9, 3, 3, 1.0, 'pkg')"
    )
    # Czech Pilsner: Pale Malt 9 lb, Saaz Hops 2 oz, US-05 Yeast 1 pkg
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (10, 4, 1, 9.0, 'lb')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (11, 4, 6, 2.0, 'oz')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO recipe_ingredients (id, recipe_id, ingredient_id, quantity, unit) "
        "VALUES (12, 4, 3, 1.0, 'pkg')"
    )

    # --- Tanks ---
    conn.execute(
        "INSERT OR IGNORE INTO tanks (id, name, capacity_gallons, tank_type, notes) "
        "VALUES (1, 'Fermenter 1', 15.0, 'fermenter', '15-gallon stainless conical')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO tanks (id, name, capacity_gallons, tank_type, notes) "
        "VALUES (2, 'Brite Tank 1', 15.0, 'brite', '15-gallon brite tank for carbonation')"
    )

    # --- Taps ---
    conn.execute(
        "INSERT OR IGNORE INTO taps (id, name, position) "
        "VALUES (1, 'Tap 1', 1)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO taps (id, name, position) "
        "VALUES (2, 'Tap 2', 2)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO taps (id, name, position) "
        "VALUES (3, 'Tap 3', 3)"
    )

    # --- Staff ---
    conn.execute(
        "INSERT OR IGNORE INTO staff (id, name, role, email, phone, hire_date, status) "
        "VALUES (1, 'Alex Brewmaster', 'brewer', 'alex@brewops.local', '555-0101', '2025-01-15', 'active')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO staff (id, name, role, email, phone, hire_date, status) "
        "VALUES (2, 'Jordan Server', 'server', 'jordan@brewops.local', '555-0102', '2025-03-01', 'active')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO staff (id, name, role, email, phone, hire_date, status) "
        "VALUES (3, 'Sam Manager', 'manager', 'sam@brewops.local', '555-0103', '2024-11-01', 'active')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO staff (id, name, role, email, phone, hire_date, status) "
        "VALUES (4, 'Riley Brewer', 'brewer', 'riley@brewops.local', '555-0104', '2025-06-10', 'active')"
    )

    # --- Batches ---
    # Batch 1: IPA, status 'fermenting', assigned to Fermenter 1
    # remaining_volume_oz = 10 gallons * 128 = 1280 oz
    conn.execute(
        "INSERT OR IGNORE INTO batches (id, recipe_id, name, brew_date, status, volume_gallons, remaining_volume_oz, tank_id, notes) "
        "VALUES (1, 1, 'IPA Batch #001', '2026-05-15', 'fermenting', 10.0, 1280.0, 1, 'First IPA batch of the season')"
    )
    # Link Fermenter 1 to Batch 1 (derived state: tanks.current_batch_id)
    conn.execute(
        "UPDATE tanks SET current_batch_id = 1 WHERE id = 1 AND current_batch_id IS NULL"
    )

    # Batch 2: Stout, status 'planned', not yet assigned to a tank
    # remaining_volume_oz = 5 gallons * 128 = 640 oz
    conn.execute(
        "INSERT OR IGNORE INTO batches (id, recipe_id, name, brew_date, status, volume_gallons, remaining_volume_oz, tank_id, notes) "
        "VALUES (2, 2, 'Stout Batch #001', NULL, 'planned', 5.0, 640.0, NULL, 'Waiting for fermenter availability')"
    )

    conn.close()
    print(f'Seed data loaded into {DB_PATH}')


if __name__ == '__main__':
    seed()
