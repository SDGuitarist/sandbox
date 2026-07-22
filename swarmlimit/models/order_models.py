"""Orders + order_items + the ``create_order`` atomic transaction (order agent).

Owns the ``orders`` and ``order_items`` tables and the class-B ``create_order``
unit — the multi-FK atomic write that touches {orders, order_items,
products.stock} in ONE ``transaction()`` (BEGIN IMMEDIATE).

Transaction discipline (spec §5):
- ``create_order`` is the ONLY class-B opener in this file; it owns exactly one
  ``with transaction() as conn:`` and threads that SAME ``conn`` into the in-tx
  helpers (``refs.assert_ext_ref_unique``, ``product_models.decrement_stock_in_tx``).
  It commits exactly once via the context manager and does NOT audit (the route
  audits post-commit).
- ``order_total`` is a class-C read-only helper: it runs on a caller-supplied
  ``conn`` (used in-tx by ``process_return``'s refund guard, and at read time),
  issues only a SELECT, and NEVER commits.
- The listers/getters are read-only; the ``*_for`` variants enforce ownership as
  a SQL WHERE predicate (Ownership-Scoped Getter Contract) — a non-owner gets
  0 rows → ``None``/``[]``, never a post-fetch 403 (run-080 IDOR lesson).

All boundary-crossing returns are plain ``dict`` / ``list[dict]`` / ``int``
(FC63 — never leak ``sqlite3.Row``).
"""

from typing import Callable

from swarmlimit.database import get_db, query, transaction
from swarmlimit.models import product_models
from swarmlimit.refs import assert_ext_ref_unique

# Smoke-only fault-injection seam (spec §1a/§5). Default ``None`` → no-op in
# production. Smoke sets this to a raising callable, drives ``create_order``,
# asserts the exception propagated out of the ``with`` block (→ ROLLBACK), then
# resets it to ``None``. Invoked as ``if _TX_FAULT: _TX_FAULT()`` at the
# checkpoint AFTER the FIRST ``order_item`` insert inside ``create_order``.
_TX_FAULT: Callable[[], None] | None = None


def _order_total_expr() -> str:
    """SQL scalar subquery computing an order's total in cents at read time.

    ``total_cents = SUM(qty * unit_price_cents)`` over the order's
    ``order_items``; ``COALESCE(..., 0)`` so an order with no items reads 0
    rather than NULL. Money is always integer cents (spec §4).
    """
    return (
        "(SELECT COALESCE(SUM(oi.qty * oi.unit_price_cents), 0) "
        "FROM order_items oi WHERE oi.order_id = orders.id)"
    )


def list_orders(user_id=None, status=None) -> list[dict]:
    """Return orders (unscoped; admin callers) as plain dicts.

    Each row includes computed ``total_cents = SUM(qty*unit_price_cents)``.
    Optional filters: ``user_id`` (owner) and ``status``.
    """
    sql = (
        "SELECT orders.id, orders.user_id, orders.ext_ref, orders.status, "
        "orders.created_at, " + _order_total_expr() + " AS total_cents "
        "FROM orders"
    )
    clauses = []
    params: list = []
    if user_id is not None:
        clauses.append("orders.user_id = ?")
        params.append(user_id)
    if status is not None:
        clauses.append("orders.status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY orders.id DESC"
    return [dict(row) for row in query(sql, tuple(params))]


def list_orders_for(actor, status=None) -> list[dict]:
    """Ownership-scoped list of orders (source of ``GET /orders``).

    Admin → all orders; customer → only ``orders.user_id = actor['id']``. The
    ownership check is a SQL WHERE predicate (never a post-fetch compare), so a
    non-owner simply sees fewer rows. Each row includes ``total_cents``.
    """
    if actor["role"] == "admin":
        return list_orders(status=status)
    return list_orders(user_id=actor["id"], status=status)


def _order_row(oid) -> dict | None:
    """Fetch a single order row (with ``total_cents``) as a dict, or ``None``."""
    return query(
        "SELECT orders.id, orders.user_id, orders.ext_ref, orders.status, "
        "orders.created_at, " + _order_total_expr() + " AS total_cents "
        "FROM orders WHERE orders.id = ?",
        (oid,),
        one=True,
    )


def _order_items(oid) -> list[dict]:
    """Return the order's line items as plain dicts (snapshot unit prices)."""
    return [
        dict(row)
        for row in query(
            "SELECT id, order_id, product_id, qty, unit_price_cents "
            "FROM order_items WHERE order_id = ? ORDER BY id",
            (oid,),
        )
    ]


def get_order(oid) -> dict | None:
    """Return a single order (unscoped) including ``items`` + ``total_cents``.

    ``None`` if the order does not exist. ``items`` is a ``list[dict]`` of the
    order's ``order_items`` rows.
    """
    order = _order_row(oid)
    if order is None:
        return None
    order["items"] = _order_items(oid)
    return order


def get_order_for(oid, actor) -> dict | None:
    """Ownership-scoped single-order getter (Ownership-Scoped Getter Contract).

    Admin → any order; customer → only their own. A non-owner (or a missing id)
    gets ``None`` (route → 404, no existence leak). Includes ``items`` +
    ``total_cents``. Also the ownership pre-check for ``POST /returns``.
    """
    if actor["role"] == "admin":
        row = _order_row(oid)
    else:
        row = query(
            "SELECT orders.id, orders.user_id, orders.ext_ref, orders.status, "
            "orders.created_at, " + _order_total_expr() + " AS total_cents "
            "FROM orders WHERE orders.id = ? AND orders.user_id = ?",
            (oid, actor["id"]),
            one=True,
        )
    if row is None:
        return None
    row["items"] = _order_items(oid)
    return row


def order_total(conn, oid) -> int:
    """Return ``SUM(qty*unit_price_cents)`` for an order on a caller ``conn``.

    Class-C read-only helper (spec §5): runs on the caller-supplied in-tx
    ``conn``, issues one SELECT, and NEVER commits. Used in-tx by
    ``process_return``'s refund guard and as the read-time order total.
    """
    row = conn.execute(
        "SELECT COALESCE(SUM(qty * unit_price_cents), 0) AS total "
        "FROM order_items WHERE order_id = ?",
        (oid,),
    ).fetchone()
    return int(row["total"])


def create_order(user_id, ext_ref, items) -> int:
    """Create an order + its line items atomically; return the new order id.

    Class-B (spec §5): owns exactly ONE ``with transaction() as conn:``
    (BEGIN IMMEDIATE) and threads that SAME ``conn`` into every in-tx helper.
    ``items`` is ``list[{product_id, qty}]`` (non-empty; the route validates
    shape). Steps inside the transaction:

    1. ``assert_ext_ref_unique(conn, ext_ref)`` → ``ValueError('ext_ref exists')``
       on collision (route → 409).
    2. Insert the order row (``status='placed'``).
    3. For each item: re-read the product ON ``conn`` — it must EXIST and be live
       (``deleted_at IS NULL``), else ``ValueError('product unavailable')``;
       snapshot ``unit_price_cents = product.price_cents``;
       ``product_models.decrement_stock_in_tx(conn, product_id, qty)`` (stock
       guard → ``ValueError('insufficient stock')``); insert the order_item.

    The fault-injection seam (``if _TX_FAULT: _TX_FAULT()``) fires immediately
    AFTER the FIRST order_item insert (and that item's stock decrement) to let
    smoke prove rollback of a PARTIALLY-written unit. Any raise rolls back the
    WHOLE unit (no order, no partial items, no stock change). Commits exactly
    once via the context manager. Does NOT audit (the route audits post-commit).
    """
    with transaction() as conn:
        # (1) cross-resource ext_ref uniqueness (raises on collision).
        assert_ext_ref_unique(conn, ext_ref)

        # (2) insert the order row.
        order_id = conn.execute(
            "INSERT INTO orders (user_id, ext_ref, status) VALUES (?, ?, 'placed')",
            (user_id, ext_ref),
        ).lastrowid

        # (3) per item: re-read product (live?), snapshot price, decrement stock,
        # insert the line item.
        for index, item in enumerate(items):
            product_id = item["product_id"]
            qty = item["qty"]

            product = conn.execute(
                "SELECT id, price_cents FROM products "
                "WHERE id = ? AND deleted_at IS NULL",
                (product_id,),
            ).fetchone()
            if product is None:
                raise ValueError("product unavailable")

            unit_price_cents = product["price_cents"]

            # Stock guard (in-tx helper on the SAME conn; raises on insufficient
            # stock or a soft-deleted product → rowcount 0).
            product_models.decrement_stock_in_tx(conn, product_id, qty)

            conn.execute(
                "INSERT INTO order_items (order_id, product_id, qty, unit_price_cents) "
                "VALUES (?, ?, ?, ?)",
                (order_id, product_id, qty, unit_price_cents),
            )

            # Fault-injection checkpoint: fire immediately AFTER the FIRST
            # order_item insert (+ its stock decrement) so smoke can prove a
            # partially-written unit rolls back. No-op in production (_TX_FAULT
            # is None).
            if index == 0 and _TX_FAULT:
                _TX_FAULT()

    return order_id
