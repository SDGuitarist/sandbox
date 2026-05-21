"""Order model functions for customer order lifecycle.

All functions take a conn: sqlite3.Connection parameter.
Only start_preparing_order and cancel_order commit (they own the transaction).
All other functions do NOT commit -- the caller commits.
"""
import sqlite3

from app.models.inventory_models import deduct_order_inventory, restore_order_inventory


def create_order(conn: sqlite3.Connection, table_id: int | None,
                 notes: str) -> int:
    """Create a new order with status 'pending'. Returns the new order ID."""
    cursor = conn.execute(
        "INSERT INTO orders (table_id, notes) VALUES (?, ?)",
        (table_id, notes),
    )
    return cursor.lastrowid


def get_all_orders(conn: sqlite3.Connection, status: str | None = None) -> list:
    """Return all orders, optionally filtered by status."""
    if status is not None:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC",
        ).fetchall()
    return rows


def get_order(conn: sqlite3.Connection, order_id: int):
    """Return a single order by ID, or None if not found."""
    return conn.execute(
        "SELECT * FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()


def get_order_items(conn: sqlite3.Connection, order_id: int) -> list:
    """Return all line items for an order, joined with menu item name."""
    return conn.execute(
        """SELECT oi.*, mi.name AS menu_item_name
           FROM order_items oi
           JOIN menu_items mi ON mi.id = oi.menu_item_id
           WHERE oi.order_id = ?
           ORDER BY oi.id""",
        (order_id,),
    ).fetchall()


def set_order_items(conn: sqlite3.Connection, order_id: int,
                    menu_item_ids: list[int], quantities: list[int]) -> None:
    """Delete existing items, insert new ones with current menu prices, update total.

    Validates that menu_item_ids and quantities have the same length.
    Does NOT commit -- the caller commits.
    """
    if len(menu_item_ids) != len(quantities):
        raise ValueError(
            f"menu_item_ids length ({len(menu_item_ids)}) must equal "
            f"quantities length ({len(quantities)})"
        )

    # Delete existing items for this order
    conn.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))

    # Insert new items with current menu prices
    for menu_item_id, quantity in zip(menu_item_ids, quantities):
        price_row = conn.execute(
            "SELECT price_cents FROM menu_items WHERE id = ?",
            (menu_item_id,),
        ).fetchone()
        if price_row is None:
            raise ValueError(f"Menu item {menu_item_id} not found")
        unit_price_cents = price_row["price_cents"]
        conn.execute(
            """INSERT INTO order_items (order_id, menu_item_id, quantity, unit_price_cents)
               VALUES (?, ?, ?, ?)""",
            (order_id, menu_item_id, quantity, unit_price_cents),
        )

    # Recalculate and update the order total
    update_order_total(conn, order_id)


def update_order_total(conn: sqlite3.Connection, order_id: int) -> None:
    """Recalculate order total from line items and update the orders row.

    Does NOT commit -- the caller commits.
    """
    row = conn.execute(
        "SELECT COALESCE(SUM(quantity * unit_price_cents), 0) AS total "
        "FROM order_items WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    conn.execute(
        "UPDATE orders SET total_cents = ?, updated_at = datetime('now') WHERE id = ?",
        (row["total"], order_id),
    )


def start_preparing_order(conn: sqlite3.Connection, order_id: int) -> None:
    """Transition order from pending to preparing and deduct inventory.

    Owns the transaction: BEGIN IMMEDIATE, verify status=pending,
    update to preparing, deduct inventory, commit.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        order = conn.execute(
            "SELECT status FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order["status"] != "pending":
            raise ValueError(
                f"Order {order_id} must be 'pending' to start preparing, "
                f"currently '{order['status']}'"
            )
        conn.execute(
            "UPDATE orders SET status = 'preparing', updated_at = datetime('now') "
            "WHERE id = ?",
            (order_id,),
        )
        deduct_order_inventory(conn, order_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def mark_order_ready(conn: sqlite3.Connection, order_id: int) -> None:
    """Transition order from preparing to ready.

    Does NOT commit -- the caller commits.
    """
    order = conn.execute(
        "SELECT status FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order["status"] != "preparing":
        raise ValueError(
            f"Order {order_id} must be 'preparing' to mark ready, "
            f"currently '{order['status']}'"
        )
    conn.execute(
        "UPDATE orders SET status = 'ready', updated_at = datetime('now') "
        "WHERE id = ?",
        (order_id,),
    )


def mark_order_served(conn: sqlite3.Connection, order_id: int) -> None:
    """Transition order from ready to served.

    Does NOT commit -- the caller commits.
    """
    order = conn.execute(
        "SELECT status FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order["status"] != "ready":
        raise ValueError(
            f"Order {order_id} must be 'ready' to mark served, "
            f"currently '{order['status']}'"
        )
    conn.execute(
        "UPDATE orders SET status = 'served', updated_at = datetime('now') "
        "WHERE id = ?",
        (order_id,),
    )


def close_order(conn: sqlite3.Connection, order_id: int) -> None:
    """Transition order from served to closed.

    Does NOT commit -- the caller commits.
    """
    order = conn.execute(
        "SELECT status FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()
    if order is None:
        raise ValueError(f"Order {order_id} not found")
    if order["status"] != "served":
        raise ValueError(
            f"Order {order_id} must be 'served' to close, "
            f"currently '{order['status']}'"
        )
    conn.execute(
        "UPDATE orders SET status = 'closed', updated_at = datetime('now') "
        "WHERE id = ?",
        (order_id,),
    )


def cancel_order(conn: sqlite3.Connection, order_id: int) -> None:
    """Cancel an order from any state. If inventory was deducted, restore it.

    Owns the transaction: BEGIN IMMEDIATE, set cancelled,
    restore inventory if previous status was preparing/ready/served, commit.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        order = conn.execute(
            "SELECT status FROM orders WHERE id = ?",
            (order_id,),
        ).fetchone()
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order["status"] == "cancelled":
            raise ValueError(f"Order {order_id} is already cancelled")
        if order["status"] == "closed":
            raise ValueError(f"Order {order_id} is closed and cannot be cancelled")

        previous_status = order["status"]
        conn.execute(
            "UPDATE orders SET status = 'cancelled', updated_at = datetime('now') "
            "WHERE id = ?",
            (order_id,),
        )

        # Restore inventory if it was previously deducted
        # (deduction happens at preparing transition)
        if previous_status in ("preparing", "ready", "served"):
            restore_order_inventory(conn, order_id)

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
