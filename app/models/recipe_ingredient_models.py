import sqlite3


# get_recipe_ingredients(conn, recipe_id) -> list[sqlite3.Row]
# Returns: list of recipe_ingredients rows joined with ingredient name
# Usage: ingredients = get_recipe_ingredients(conn, recipe_id)
# Tag: SERIAL-SAFE
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
# Tag: SERIAL-SAFE
def add_recipe_ingredient(conn: sqlite3.Connection, recipe_id: int,
                          ingredient_id: int, quantity: float, unit: str) -> int:
    cur = conn.execute(
        'INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)',
        (recipe_id, ingredient_id, quantity, unit))
    return cur.lastrowid


# remove_recipe_ingredient(conn, ri_id) -> None
# Usage: remove_recipe_ingredient(conn, ri_id)
#        conn.commit()
# Tag: SERIAL-SAFE
def remove_recipe_ingredient(conn: sqlite3.Connection, ri_id: int, recipe_id: int) -> bool:
    """Delete a recipe ingredient. Returns True if deleted, False if not found or wrong recipe."""
    cur = conn.execute(
        'DELETE FROM recipe_ingredients WHERE id = ? AND recipe_id = ?',
        (ri_id, recipe_id))
    return cur.rowcount > 0
