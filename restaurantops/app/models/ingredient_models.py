"""Ingredient model functions for RestaurantOps.

CRUD operations for the ingredients table plus allergen management
via the ingredient_allergens junction table.

All functions accept a sqlite3.Connection and do NOT commit.
The caller is responsible for committing the transaction.
"""

import sqlite3


def create_ingredient(conn: sqlite3.Connection, name: str, unit: str,
                      unit_cost_cents: int, supplier_id: int | None = None,
                      low_stock_threshold: float = 0) -> int:
    """Insert a new ingredient and return its ID.

    Args:
        conn: Database connection.
        name: Ingredient name (must be unique).
        unit: Unit of measurement (g, kg, ml, l, unit, oz, lb).
        unit_cost_cents: Cost per unit in cents.
        supplier_id: Optional FK to suppliers table.
        low_stock_threshold: Stock level that triggers low-stock warning.

    Returns:
        int: The new ingredient's ID.

    Usage::

        ing_id = create_ingredient(conn, 'Flour', 'kg', 150,
                                   supplier_id=1, low_stock_threshold=5.0)
    """
    cursor = conn.execute(
        """INSERT INTO ingredients (name, unit, unit_cost_cents, supplier_id,
                                    low_stock_threshold)
           VALUES (?, ?, ?, ?, ?)""",
        (name, unit, unit_cost_cents, supplier_id, low_stock_threshold),
    )
    return cursor.lastrowid


def get_all_ingredients(conn: sqlite3.Connection) -> list:
    """Return all ingredients ordered by name.

    Returns:
        list[sqlite3.Row]: Each row has id, name, unit, unit_cost_cents,
        supplier_id, low_stock_threshold, created_at, updated_at.

    Usage::

        ingredients = get_all_ingredients(conn)
        for ing in ingredients:
            print(ing['name'], ing['unit_cost_cents'])
    """
    return conn.execute(
        "SELECT * FROM ingredients ORDER BY name"
    ).fetchall()


def get_ingredient(conn: sqlite3.Connection, ingredient_id: int):
    """Return a single ingredient by ID, or None if not found.

    Args:
        conn: Database connection.
        ingredient_id: The ingredient's primary key.

    Returns:
        sqlite3.Row or None: The ingredient row.

    Usage::

        ing = get_ingredient(conn, 1)
        if ing:
            print(ing['name'])
    """
    return conn.execute(
        "SELECT * FROM ingredients WHERE id = ?",
        (ingredient_id,),
    ).fetchone()


def update_ingredient(conn: sqlite3.Connection, ingredient_id: int,
                      name: str, unit: str, unit_cost_cents: int,
                      supplier_id: int | None, low_stock_threshold: float) -> None:
    """Update an existing ingredient's fields.

    Args:
        conn: Database connection.
        ingredient_id: The ingredient's primary key.
        name: New name.
        unit: New unit of measurement.
        unit_cost_cents: New cost per unit in cents.
        supplier_id: New supplier FK (or None).
        low_stock_threshold: New low-stock threshold.

    Usage::

        update_ingredient(conn, 1, 'All-Purpose Flour', 'kg', 175,
                          supplier_id=2, low_stock_threshold=3.0)
    """
    conn.execute(
        """UPDATE ingredients
           SET name = ?, unit = ?, unit_cost_cents = ?, supplier_id = ?,
               low_stock_threshold = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (name, unit, unit_cost_cents, supplier_id, low_stock_threshold,
         ingredient_id),
    )


def delete_ingredient(conn: sqlite3.Connection, ingredient_id: int) -> None:
    """Delete an ingredient by ID.

    Cascading foreign keys will remove related ingredient_allergens rows.

    Args:
        conn: Database connection.
        ingredient_id: The ingredient's primary key.

    Usage::

        delete_ingredient(conn, 1)
    """
    conn.execute(
        "DELETE FROM ingredients WHERE id = ?",
        (ingredient_id,),
    )


def set_ingredient_allergens(conn: sqlite3.Connection, ingredient_id: int,
                             allergen_ids: list[int]) -> None:
    """Replace all allergens for an ingredient.

    Deletes existing allergen associations and inserts the new set.
    Pass an empty list to clear all allergens.

    Args:
        conn: Database connection.
        ingredient_id: The ingredient's primary key.
        allergen_ids: List of allergen IDs to associate.

    Usage::

        set_ingredient_allergens(conn, ing_id, [1, 3, 5])  # Gluten, Eggs, Shellfish
    """
    conn.execute(
        "DELETE FROM ingredient_allergens WHERE ingredient_id = ?",
        (ingredient_id,),
    )
    for allergen_id in allergen_ids:
        conn.execute(
            """INSERT INTO ingredient_allergens (ingredient_id, allergen_id)
               VALUES (?, ?)""",
            (ingredient_id, allergen_id),
        )


def get_ingredient_allergens(conn: sqlite3.Connection, ingredient_id: int) -> list:
    """Return all allergens associated with an ingredient.

    Joins ingredient_allergens with allergens to get the allergen name.

    Args:
        conn: Database connection.
        ingredient_id: The ingredient's primary key.

    Returns:
        list[sqlite3.Row]: Each row has allergen 'id' and 'name'.

    Usage::

        allergens = get_ingredient_allergens(conn, 1)
        for a in allergens:
            print(a['id'], a['name'])
    """
    return conn.execute(
        """SELECT a.id, a.name
           FROM allergens a
           JOIN ingredient_allergens ia ON a.id = ia.allergen_id
           WHERE ia.ingredient_id = ?
           ORDER BY a.name""",
        (ingredient_id,),
    ).fetchall()
