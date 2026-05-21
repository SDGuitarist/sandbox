"""Purchase order lifecycle models.

All functions take a conn parameter and do NOT commit -- the caller commits.
"""

import sqlite3

from app.models.inventory_models import record_stock_movement


def create_purchase_order(conn: sqlite3.Connection, supplier_id: int,
                          notes: str) -> int:
    """Create a new purchase order in draft status.

    Returns the new purchase order ID.
    """
    cursor = conn.execute(
        """INSERT INTO purchase_orders (supplier_id, notes)
           VALUES (?, ?)""",
        (supplier_id, notes),
    )
    return cursor.lastrowid


def get_all_purchase_orders(conn: sqlite3.Connection) -> list:
    """Return all purchase orders joined with supplier name, ordered by newest first."""
    return conn.execute(
        """SELECT po.*, s.name AS supplier_name
           FROM purchase_orders po
           JOIN suppliers s ON s.id = po.supplier_id
           ORDER BY po.created_at DESC"""
    ).fetchall()


def get_purchase_order(conn: sqlite3.Connection, po_id: int):
    """Return a single purchase order joined with supplier name, or None."""
    return conn.execute(
        """SELECT po.*, s.name AS supplier_name
           FROM purchase_orders po
           JOIN suppliers s ON s.id = po.supplier_id
           WHERE po.id = ?""",
        (po_id,),
    ).fetchone()


def get_purchase_order_items(conn: sqlite3.Connection, po_id: int) -> list:
    """Return line items for a purchase order with ingredient details.

    Each row has: id, purchase_order_id, ingredient_id, ingredient name,
    quantity, unit_cost_cents.
    """
    return conn.execute(
        """SELECT poi.*, i.name AS ingredient_name
           FROM purchase_order_items poi
           JOIN ingredients i ON i.id = poi.ingredient_id
           WHERE poi.purchase_order_id = ?
           ORDER BY poi.id""",
        (po_id,),
    ).fetchall()


def set_purchase_order_items(conn: sqlite3.Connection, po_id: int,
                             ingredient_ids: list[int], quantities: list[float],
                             unit_costs: list[int]) -> None:
    """Set PO line items using delete + re-insert pattern.

    Validates that all three lists have the same length. Raises ValueError
    if they do not match.
    """
    if not (len(ingredient_ids) == len(quantities) == len(unit_costs)):
        raise ValueError(
            f"List length mismatch: ingredient_ids={len(ingredient_ids)}, "
            f"quantities={len(quantities)}, unit_costs={len(unit_costs)}"
        )

    # Delete existing items
    conn.execute(
        "DELETE FROM purchase_order_items WHERE purchase_order_id = ?",
        (po_id,),
    )

    # Re-insert new items
    for ingredient_id, quantity, unit_cost in zip(
        ingredient_ids, quantities, unit_costs
    ):
        conn.execute(
            """INSERT INTO purchase_order_items
               (purchase_order_id, ingredient_id, quantity, unit_cost_cents)
               VALUES (?, ?, ?, ?)""",
            (po_id, ingredient_id, quantity, unit_cost),
        )


def update_purchase_order_total(conn: sqlite3.Connection, po_id: int) -> None:
    """Recalculate total_cents from line items.

    total_cents = SUM(quantity * unit_cost_cents) across all line items,
    rounded to the nearest integer.
    """
    row = conn.execute(
        """SELECT COALESCE(SUM(ROUND(quantity * unit_cost_cents)), 0) AS total
           FROM purchase_order_items
           WHERE purchase_order_id = ?""",
        (po_id,),
    ).fetchone()

    conn.execute(
        """UPDATE purchase_orders
           SET total_cents = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (int(row["total"]), po_id),
    )


def submit_purchase_order(conn: sqlite3.Connection, po_id: int) -> None:
    """Transition a purchase order from draft to submitted.

    Sets ordered_date to now. Raises ValueError if the PO is not in draft status.
    """
    po = get_purchase_order(conn, po_id)
    if po is None:
        raise ValueError(f"Purchase order {po_id} not found")
    if po["status"] != "draft":
        raise ValueError(
            f"Cannot submit PO {po_id}: status is '{po['status']}', expected 'draft'"
        )

    conn.execute(
        """UPDATE purchase_orders
           SET status = 'submitted',
               ordered_date = datetime('now'),
               updated_at = datetime('now')
           WHERE id = ?""",
        (po_id,),
    )


def receive_purchase_order(conn: sqlite3.Connection, po_id: int) -> None:
    """Receive a purchase order: set status='received', set received_date,
    and create receipt stock movements for each line item.

    Calls record_stock_movement from inventory_models for each line item.
    Does NOT commit -- caller commits.

    Raises ValueError if the PO is not in submitted status.
    """
    po = get_purchase_order(conn, po_id)
    if po is None:
        raise ValueError(f"Purchase order {po_id} not found")
    if po["status"] != "submitted":
        raise ValueError(
            f"Cannot receive PO {po_id}: status is '{po['status']}', expected 'submitted'"
        )

    # Update PO status and received_date
    conn.execute(
        """UPDATE purchase_orders
           SET status = 'received',
               received_date = datetime('now'),
               updated_at = datetime('now')
           WHERE id = ?""",
        (po_id,),
    )

    # Create stock movements for each line item
    items = get_purchase_order_items(conn, po_id)
    for item in items:
        record_stock_movement(
            conn,
            ingredient_id=item["ingredient_id"],
            movement_type="receipt",
            quantity=item["quantity"],
            reference_type="purchase_order",
            reference_id=po_id,
        )


def close_purchase_order(conn: sqlite3.Connection, po_id: int) -> None:
    """Transition a purchase order from received to closed.

    Raises ValueError if the PO is not in received status.
    """
    po = get_purchase_order(conn, po_id)
    if po is None:
        raise ValueError(f"Purchase order {po_id} not found")
    if po["status"] != "received":
        raise ValueError(
            f"Cannot close PO {po_id}: status is '{po['status']}', expected 'received'"
        )

    conn.execute(
        """UPDATE purchase_orders
           SET status = 'closed',
               updated_at = datetime('now')
           WHERE id = ?""",
        (po_id,),
    )
