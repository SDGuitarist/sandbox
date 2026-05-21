"""Inventory and stock movement model functions.

All functions take a sqlite3.Connection as the first parameter.
No function calls conn.commit() -- the caller is responsible for committing.
This is critical because these functions are called inside BEGIN IMMEDIATE
transactions owned by order_models and purchase_order_models.
"""

from __future__ import annotations

import sqlite3


def get_inventory_status(conn: sqlite3.Connection) -> list:
    """Return all ingredients with their current stock levels.

    Returns a list of sqlite3.Row objects with columns:
    ingredient_id, name, current_stock, unit, low_stock_threshold.

    Ingredients without an inventory row show current_stock = 0.
    """
    return conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, COALESCE(inv.current_stock, 0) AS current_stock,
               i.unit, i.low_stock_threshold
        FROM ingredients i
        LEFT JOIN inventory inv ON inv.ingredient_id = i.id
        ORDER BY i.name
        """
    ).fetchall()


def get_low_stock_items(conn: sqlite3.Connection) -> list:
    """Return ingredients where current_stock < low_stock_threshold.

    Returns a list of sqlite3.Row objects with columns:
    ingredient_id, name, current_stock, unit, low_stock_threshold.

    Ingredients without an inventory row are included if their
    low_stock_threshold > 0 (since current_stock defaults to 0).
    """
    return conn.execute(
        """
        SELECT i.id AS ingredient_id, i.name, COALESCE(inv.current_stock, 0) AS current_stock,
               i.unit, i.low_stock_threshold
        FROM ingredients i
        LEFT JOIN inventory inv ON inv.ingredient_id = i.id
        WHERE COALESCE(inv.current_stock, 0) < i.low_stock_threshold
        ORDER BY i.name
        """
    ).fetchall()


def record_stock_movement(
    conn: sqlite3.Connection,
    ingredient_id: int,
    movement_type: str,
    quantity: float,
    reference_type: str | None = None,
    reference_id: int | None = None,
    notes: str | None = None,
) -> None:
    """Create a stock movement row and update inventory.current_stock.

    Does NOT commit -- the caller is responsible for committing.

    Args:
        conn: Database connection (inside a transaction).
        ingredient_id: The ingredient being affected.
        movement_type: One of 'receipt', 'consumption', 'adjustment', 'waste'.
        quantity: Positive for receipt/adjustment-up, negative for consumption/waste.
        reference_type: Optional -- 'purchase_order', 'order', or 'manual'.
        reference_id: Optional -- ID of the PO or order that caused this movement.
        notes: Optional free-text note.
    """
    # Ensure the inventory row exists before updating it
    ensure_inventory_row(conn, ingredient_id)

    # Insert the stock movement record
    conn.execute(
        """
        INSERT INTO stock_movements (ingredient_id, movement_type, quantity,
                                     reference_type, reference_id, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ingredient_id, movement_type, quantity, reference_type, reference_id, notes),
    )

    # Update current stock level
    conn.execute(
        """
        UPDATE inventory
        SET current_stock = current_stock + ?,
            updated_at = datetime('now')
        WHERE ingredient_id = ?
        """,
        (quantity, ingredient_id),
    )


def ensure_inventory_row(conn: sqlite3.Connection, ingredient_id: int) -> None:
    """Ensure an inventory row exists for the given ingredient.

    Uses INSERT OR IGNORE so it is safe to call multiple times.
    Does NOT commit.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO inventory (ingredient_id, current_stock)
        VALUES (?, 0)
        """,
        (ingredient_id,),
    )


def get_stock_movements(conn: sqlite3.Connection, ingredient_id: int) -> list:
    """Return the stock movement history for a specific ingredient.

    Returns a list of sqlite3.Row objects ordered by most recent first,
    with columns: id, ingredient_id, movement_type, quantity,
    reference_type, reference_id, notes, created_at.
    """
    return conn.execute(
        """
        SELECT id, ingredient_id, movement_type, quantity,
               reference_type, reference_id, notes, created_at
        FROM stock_movements
        WHERE ingredient_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (ingredient_id,),
    ).fetchall()


def deduct_order_inventory(conn: sqlite3.Connection, order_id: int) -> None:
    """Deduct inventory for all ingredients used in an order's recipes.

    For each order_item, looks up the linked menu_item's recipe, then
    iterates that recipe's ingredients and creates a 'consumption'
    stock movement with a negative quantity (quantity * order item quantity).

    Does NOT commit -- the caller owns the transaction (BEGIN IMMEDIATE).
    """
    # Get all order items with their linked recipe_id
    order_items = conn.execute(
        """
        SELECT oi.quantity AS item_qty, mi.recipe_id
        FROM order_items oi
        JOIN menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.order_id = ?
        """,
        (order_id,),
    ).fetchall()

    for item in order_items:
        recipe_id = item["recipe_id"]
        if recipe_id is None:
            # Menu item has no recipe -- nothing to deduct
            continue

        item_qty = item["item_qty"]

        # Get the recipe's ingredients
        recipe_ingredients = conn.execute(
            """
            SELECT ingredient_id, quantity
            FROM recipe_ingredients
            WHERE recipe_id = ?
            """,
            (recipe_id,),
        ).fetchall()

        for ri in recipe_ingredients:
            # Consumption is negative: -(recipe qty * number of items ordered)
            consumption_qty = -(ri["quantity"] * item_qty)
            record_stock_movement(
                conn,
                ingredient_id=ri["ingredient_id"],
                movement_type="consumption",
                quantity=consumption_qty,
                reference_type="order",
                reference_id=order_id,
            )


def restore_order_inventory(conn: sqlite3.Connection, order_id: int) -> None:
    """Restore inventory for a cancelled order (reverse of deduct).

    For each order_item, looks up the linked menu_item's recipe, then
    iterates that recipe's ingredients and creates an 'adjustment'
    stock movement with a positive quantity to restore what was deducted.

    Does NOT commit -- the caller owns the transaction (BEGIN IMMEDIATE).
    """
    # Get all order items with their linked recipe_id
    order_items = conn.execute(
        """
        SELECT oi.quantity AS item_qty, mi.recipe_id
        FROM order_items oi
        JOIN menu_items mi ON mi.id = oi.menu_item_id
        WHERE oi.order_id = ?
        """,
        (order_id,),
    ).fetchall()

    for item in order_items:
        recipe_id = item["recipe_id"]
        if recipe_id is None:
            # Menu item has no recipe -- nothing to restore
            continue

        item_qty = item["item_qty"]

        # Get the recipe's ingredients
        recipe_ingredients = conn.execute(
            """
            SELECT ingredient_id, quantity
            FROM recipe_ingredients
            WHERE recipe_id = ?
            """,
            (recipe_id,),
        ).fetchall()

        for ri in recipe_ingredients:
            # Restore is positive: recipe qty * number of items ordered
            restore_qty = ri["quantity"] * item_qty
            record_stock_movement(
                conn,
                ingredient_id=ri["ingredient_id"],
                movement_type="adjustment",
                quantity=restore_qty,
                reference_type="order",
                reference_id=order_id,
                notes="Restored from cancelled order",
            )
