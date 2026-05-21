"""Menu item model functions for RestaurantOps.

CRUD operations for menu items plus cross-model helpers for allergens
and cost lookups. Functions do NOT commit -- the caller is responsible
for committing the transaction.
"""
import sqlite3

from app.models.recipe_models import calculate_recipe_cost


def create_menu_item(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    price_cents: int,
    category_id: int | None,
    recipe_id: int | None,
    is_available: int = 1,
) -> int:
    """Create a new menu item and return its ID.

    Args:
        conn: Database connection.
        name: Display name on the menu.
        description: Short description shown to diners.
        price_cents: Price stored as integer cents (e.g. 1299 = $12.99).
        category_id: FK to categories table, or None for uncategorized.
        recipe_id: FK to recipes table, or None if no recipe linked.
        is_available: 1 = available, 0 = unavailable.

    Returns:
        int: The new menu item's ID.
    """
    cursor = conn.execute(
        """INSERT INTO menu_items
           (name, description, price_cents, category_id, recipe_id, is_available)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, description, price_cents, category_id, recipe_id, is_available),
    )
    return cursor.lastrowid


def get_all_menu_items(conn: sqlite3.Connection) -> list:
    """Return all menu items ordered by name.

    Returns:
        list[sqlite3.Row]: All menu item rows.
    """
    return conn.execute(
        "SELECT * FROM menu_items ORDER BY name"
    ).fetchall()


def get_menu_by_category(conn: sqlite3.Connection) -> list:
    """Return all menu items with their category name, ordered by category
    sort_order then item name.

    Items without a category appear last (NULL sort_order treated as high).

    Returns:
        list[sqlite3.Row]: Rows with menu item columns plus category_name.
    """
    return conn.execute(
        """SELECT mi.*, c.name AS category_name
           FROM menu_items mi
           LEFT JOIN categories c ON mi.category_id = c.id
           ORDER BY COALESCE(c.sort_order, 999999), c.name, mi.name"""
    ).fetchall()


def get_menu_item(conn: sqlite3.Connection, menu_item_id: int):
    """Return a single menu item by ID, or None if not found.

    Returns:
        sqlite3.Row or None
    """
    return conn.execute(
        "SELECT * FROM menu_items WHERE id = ?", (menu_item_id,)
    ).fetchone()


def update_menu_item(
    conn: sqlite3.Connection,
    menu_item_id: int,
    name: str,
    description: str,
    price_cents: int,
    category_id: int | None,
    recipe_id: int | None,
    is_available: int,
) -> None:
    """Update an existing menu item."""
    conn.execute(
        """UPDATE menu_items
           SET name = ?, description = ?, price_cents = ?,
               category_id = ?, recipe_id = ?, is_available = ?,
               updated_at = datetime('now')
           WHERE id = ?""",
        (name, description, price_cents, category_id, recipe_id, is_available, menu_item_id),
    )


def delete_menu_item(conn: sqlite3.Connection, menu_item_id: int) -> None:
    """Delete a menu item by ID.

    Order items referencing this menu item use ON DELETE RESTRICT,
    so deletion will fail if the item has been ordered.
    """
    conn.execute("DELETE FROM menu_items WHERE id = ?", (menu_item_id,))


def get_menu_item_allergens(conn: sqlite3.Connection, menu_item_id: int) -> list:
    """Return deduplicated allergens for a menu item by traversing:
    menu_items -> recipes -> recipe_ingredients -> ingredients ->
    ingredient_allergens -> allergens.

    Returns:
        list[sqlite3.Row]: Rows with allergen id and name.
        Empty list if the menu item has no linked recipe.
    """
    return conn.execute(
        """SELECT DISTINCT a.id, a.name
           FROM menu_items mi
           JOIN recipes r ON mi.recipe_id = r.id
           JOIN recipe_ingredients ri ON r.id = ri.recipe_id
           JOIN ingredients i ON ri.ingredient_id = i.id
           JOIN ingredient_allergens ia ON i.id = ia.ingredient_id
           JOIN allergens a ON ia.allergen_id = a.id
           WHERE mi.id = ?
           ORDER BY a.name""",
        (menu_item_id,),
    ).fetchall()


def get_menu_item_cost(conn: sqlite3.Connection, menu_item_id: int) -> int | None:
    """Return the recipe cost in cents for a menu item, or None if no recipe
    is linked.

    Delegates to calculate_recipe_cost from recipe_models for the actual
    cost calculation.

    Returns:
        int or None: Cost in cents, or None if no recipe.
    """
    item = get_menu_item(conn, menu_item_id)
    if item is None or item["recipe_id"] is None:
        return None
    return calculate_recipe_cost(conn, item["recipe_id"])
