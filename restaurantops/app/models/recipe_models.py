"""Recipe model functions for RestaurantOps.

All functions take a conn parameter and do NOT commit -- the caller commits.
"""

import sqlite3


def create_recipe(conn: sqlite3.Connection, name: str, description: str,
                  instructions: str, prep_time_minutes: int,
                  cook_time_minutes: int, servings: int) -> int:
    """Create a new recipe and return its ID.

    Usage:
        recipe_id = create_recipe(conn, 'Pasta Carbonara', 'Classic Italian',
                                  'Step 1...', 15, 20, 4)
    """
    cursor = conn.execute(
        """INSERT INTO recipes (name, description, instructions,
           prep_time_minutes, cook_time_minutes, servings)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, description, instructions, prep_time_minutes,
         cook_time_minutes, servings),
    )
    return cursor.lastrowid


def get_all_recipes(conn: sqlite3.Connection) -> list:
    """Return all recipes as a list of sqlite3.Row."""
    return conn.execute(
        "SELECT * FROM recipes ORDER BY name"
    ).fetchall()


def get_recipe(conn: sqlite3.Connection, recipe_id: int):
    """Return a single recipe by ID, or None if not found."""
    return conn.execute(
        "SELECT * FROM recipes WHERE id = ?", (recipe_id,)
    ).fetchone()


def update_recipe(conn: sqlite3.Connection, recipe_id: int, name: str,
                  description: str, instructions: str,
                  prep_time_minutes: int, cook_time_minutes: int,
                  servings: int) -> None:
    """Update an existing recipe's fields."""
    conn.execute(
        """UPDATE recipes
           SET name = ?, description = ?, instructions = ?,
               prep_time_minutes = ?, cook_time_minutes = ?,
               servings = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (name, description, instructions, prep_time_minutes,
         cook_time_minutes, servings, recipe_id),
    )


def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> None:
    """Delete a recipe by ID. CASCADE removes recipe_ingredients rows."""
    conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))


def set_recipe_ingredients(conn: sqlite3.Connection, recipe_id: int,
                           ingredient_ids: list[int], quantities: list[float],
                           units: list[str]) -> None:
    """Delete existing and insert new recipe ingredients.

    Takes parallel lists: ingredient_ids, quantities, units.
    MUST validate that all three lists have the same length.

    Usage:
        set_recipe_ingredients(conn, recipe_id,
                               [1, 2, 3], [200.0, 50.0, 10.0], ['g', 'ml', 'unit'])
    """
    if len(ingredient_ids) != len(quantities) or len(quantities) != len(units):
        raise ValueError("ingredient_ids, quantities, and units must have the same length")

    # Remove existing ingredients for this recipe
    conn.execute(
        "DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,)
    )

    # Insert new ingredients
    for ingredient_id, quantity, unit in zip(ingredient_ids, quantities, units):
        conn.execute(
            """INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit)
               VALUES (?, ?, ?, ?)""",
            (recipe_id, ingredient_id, quantity, unit),
        )


def get_recipe_ingredients(conn: sqlite3.Connection, recipe_id: int) -> list:
    """Return recipe ingredients joined with ingredient name and unit_cost_cents.

    Each row has: ingredient_id, name (ingredient name), quantity, unit, unit_cost_cents.
    """
    return conn.execute(
        """SELECT ri.ingredient_id, i.name, ri.quantity, ri.unit, i.unit_cost_cents
           FROM recipe_ingredients ri
           JOIN ingredients i ON i.id = ri.ingredient_id
           WHERE ri.recipe_id = ?
           ORDER BY i.name""",
        (recipe_id,),
    ).fetchall()


def calculate_recipe_cost(conn: sqlite3.Connection, recipe_id: int) -> int:
    """Calculate total cost of a recipe in cents (integer).

    Formula: SUM(ingredient.unit_cost_cents * recipe_ingredient.quantity) / servings
    Returns 0 if the recipe has no ingredients or doesn't exist.
    """
    row = conn.execute(
        """SELECT COALESCE(SUM(i.unit_cost_cents * ri.quantity), 0) AS total,
                  r.servings
           FROM recipes r
           LEFT JOIN recipe_ingredients ri ON ri.recipe_id = r.id
           LEFT JOIN ingredients i ON i.id = ri.ingredient_id
           WHERE r.id = ?
           GROUP BY r.id""",
        (recipe_id,),
    ).fetchone()

    if row is None:
        return 0

    total = row["total"]
    servings = row["servings"] if row["servings"] and row["servings"] > 0 else 1
    # Integer arithmetic: round to nearest cent
    return int(total // servings)


def get_recipe_allergens(conn: sqlite3.Connection, recipe_id: int) -> list:
    """Return deduplicated allergens for a recipe.

    Joins: recipe_ingredients -> ingredients -> ingredient_allergens -> allergens.
    Each row has: id (allergen id), name (allergen name).
    """
    return conn.execute(
        """SELECT DISTINCT a.id, a.name
           FROM recipe_ingredients ri
           JOIN ingredient_allergens ia ON ia.ingredient_id = ri.ingredient_id
           JOIN allergens a ON a.id = ia.allergen_id
           WHERE ri.recipe_id = ?
           ORDER BY a.name""",
        (recipe_id,),
    ).fetchall()
