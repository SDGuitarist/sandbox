"""Return model agent — owns ``process_return``, the 4-table atomic unit.

``process_return`` is the DENSEST cross-agent write in the spec: inside ONE
``with transaction() as conn:`` (BEGIN IMMEDIATE) it touches four tables owned by
four other agents — ``returns`` (this file), ``shipments.status`` (shipment),
``products.stock`` (product), and ``payments`` (payment) — all-or-nothing. It
imports FOUR peer models plus the shared ``refs`` uniqueness guard, and drives
them on the SAME ``conn`` so the whole unit commits (or rolls back) together.

Transaction discipline (spec §1a / §4 / §5):
- The four getters (``list_returns``, ``list_returns_for``, ``get_return``,
  ``get_return_for``) are read-only; they run on the request connection via
  ``query`` and convert ``sqlite3.Row`` → plain ``dict`` (FC63).
- ``process_return`` is the ONLY class-B unit here: it OWNS one ``transaction()``.
  The in-tx helpers it calls (``refs.assert_ext_ref_unique``,
  ``order_models.order_total``, ``payment_models.refunded_total`` /
  ``add_refund_in_tx``, ``shipment_models.set_shipment_status_in_tx``,
  ``product_models.restock_product_in_tx``) all take this ``conn`` and NEVER
  commit — the context manager owns the single COMMIT/ROLLBACK.
- ``process_return`` does NOT audit; the route records the audit post-commit.

Ownership-Scoped Getter Contract (spec §Model Functions; run-080 IDOR lesson):
returns are a *derived* resource, so customer ownership is transitive through the
order — ``EXISTS (SELECT 1 FROM orders o WHERE o.id = returns.order_id AND
o.user_id = :actor_id)``. Admins see all. The predicate lives in the SQL WHERE
clause (never a fetch-then-compare), so a non-owner gets 0 rows → ``None``/``[]``.
"""

from typing import Callable

from swarmlimit import refs
from swarmlimit.database import query, transaction
from swarmlimit.models import order_models, payment_models, product_models, shipment_models

# Smoke-only fault-injection seam (spec §1a / §5). Default ``None`` (no-op in
# production). ``process_return`` invokes ``if _TX_FAULT: _TX_FAULT()`` at the
# checkpoint AFTER ``add_refund_in_tx`` (the last of the four writes). Smoke sets
# it to a raising callable, drives a VALID return, then resets it to ``None`` to
# prove a TRUE mid-transaction rollback of all four writes.
_TX_FAULT: Callable[[], None] | None = None


def list_returns(order_id=None) -> list[dict]:
    """Return all return rows (optionally filtered by ``order_id``) as plain
    ``dict``s. Unscoped — admin callers only (FC63)."""
    if order_id is None:
        rows = query(
            "SELECT id, order_id, ext_ref, reason, refund_cents, created_at "
            "FROM returns ORDER BY id DESC"
        )
    else:
        rows = query(
            "SELECT id, order_id, ext_ref, reason, refund_cents, created_at "
            "FROM returns WHERE order_id = ? ORDER BY id DESC",
            (order_id,),
        )
    return [dict(row) for row in rows]


def list_returns_for(actor) -> list[dict]:
    """Ownership-Scoped Getter: returns the actor's returns as ``list[dict]``.

    Admin → all rows. Customer → only returns whose order the customer owns
    (transitive via ``orders.user_id``). The ownership check is a SQL WHERE
    predicate, so a non-owner simply gets 0 rows (no 403, no existence leak).
    """
    if actor["role"] == "admin":
        rows = query(
            "SELECT id, order_id, ext_ref, reason, refund_cents, created_at "
            "FROM returns ORDER BY id DESC"
        )
    else:
        rows = query(
            "SELECT id, order_id, ext_ref, reason, refund_cents, created_at "
            "FROM returns "
            "WHERE EXISTS (SELECT 1 FROM orders o "
            "WHERE o.id = returns.order_id AND o.user_id = ?) "
            "ORDER BY id DESC",
            (actor["id"],),
        )
    return [dict(row) for row in rows]


def get_return(rid) -> dict | None:
    """Return one return row by id as a plain ``dict``, or ``None`` (unscoped)."""
    return query(
        "SELECT id, order_id, ext_ref, reason, refund_cents, created_at "
        "FROM returns WHERE id = ?",
        (rid,),
        one=True,
    )


def get_return_for(rid, actor) -> dict | None:
    """Ownership-Scoped Getter: one return by id, or ``None`` for a non-owner.

    Admin → any return. Customer → only if the return's order is theirs. The
    ownership check is a SQL WHERE predicate, so a non-owner gets 0 rows →
    ``None`` (the route maps that to a 404, never a 403).
    """
    if actor["role"] == "admin":
        return query(
            "SELECT id, order_id, ext_ref, reason, refund_cents, created_at "
            "FROM returns WHERE id = ?",
            (rid,),
            one=True,
        )
    return query(
        "SELECT id, order_id, ext_ref, reason, refund_cents, created_at "
        "FROM returns "
        "WHERE id = ? AND EXISTS (SELECT 1 FROM orders o "
        "WHERE o.id = returns.order_id AND o.user_id = ?)",
        (rid, actor["id"]),
        one=True,
    )


def process_return(order_id, ext_ref, reason, refund_cents) -> int:
    """Atomically process a return for ``order_id`` — the 4-table class-B unit.

    OWNS one ``transaction()`` (BEGIN IMMEDIATE). Inside the single ``conn``,
    in order (spec §Model Functions / §5(B)):

      (1) ``refs.assert_ext_ref_unique(conn, ext_ref)`` → ``ValueError`` on
          collision (route → 409).
      (2) select the order's UNIQUE shipment (``UNIQUE(order_id)`` ⇒ at most one);
          require it EXISTS and ``status == 'delivered'``, else
          ``ValueError('shipment not delivered')`` (route → 409).
      (3) refund guard: ``refunded_total(conn, order_id) + refund_cents <=
          order_total(conn, order_id)``, else
          ``ValueError('refund exceeds original')`` → rollback.
      (4) insert the return row.
      (5) ``shipment_models.set_shipment_status_in_tx(conn, shipment_id,
          'returned')``.
      (6) for each order_item: ``product_models.restock_product_in_tx(conn,
          product_id, qty)``.
      (7) ``payment_models.add_refund_in_tx(conn, order_id, refund_cents)``.

    The ``_TX_FAULT`` checkpoint fires immediately AFTER step (7) (the last
    write), before the block exits — the smoke seam that proves a real mid-tx
    rollback of all four writes. Does NOT audit (the route audits post-commit).
    Any failure rolls back all four writes via the context manager. Returns the
    new return row id.
    """
    with transaction() as conn:
        # (1) cross-resource ext_ref uniqueness (orders ∪ returns) — no commit.
        refs.assert_ext_ref_unique(conn, ext_ref)

        # (2) the order's UNIQUE shipment must exist and be 'delivered'.
        shipment = conn.execute(
            "SELECT id, status FROM shipments WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if shipment is None or shipment["status"] != "delivered":
            raise ValueError("shipment not delivered")
        shipment_id = shipment["id"]

        # (3) refund guard: existing refunds + this refund must not exceed the
        #     order total. refunded_total is called positionally on the caller
        #     conn (read-only, no commit); order_total likewise.
        if (
            payment_models.refunded_total(conn, order_id) + refund_cents
            > order_models.order_total(conn, order_id)
        ):
            raise ValueError("refund exceeds original")

        # (4) insert the return row.
        return_id = conn.execute(
            "INSERT INTO returns (order_id, ext_ref, reason, refund_cents) "
            "VALUES (?, ?, ?, ?)",
            (order_id, ext_ref, reason, refund_cents),
        ).lastrowid

        # (5) mark the delivered shipment 'returned' (in-tx helper, same conn).
        shipment_models.set_shipment_status_in_tx(conn, shipment_id, "returned")

        # (6) restock every order_item's product (in-tx helper, same conn).
        items = conn.execute(
            "SELECT product_id, qty FROM order_items WHERE order_id = ?",
            (order_id,),
        ).fetchall()
        for item in items:
            product_models.restock_product_in_tx(conn, item["product_id"], item["qty"])

        # (7) ledger the refund (in-tx helper, same conn) — the last write.
        payment_models.add_refund_in_tx(conn, order_id, refund_cents)

        # _TX_FAULT checkpoint — AFTER add_refund_in_tx, before the block exits.
        # Production: _TX_FAULT is None → no-op. Smoke: a raising callable →
        # the raise propagates out of the ``with`` → transaction() ROLLBACKs all
        # four writes.
        if _TX_FAULT:
            _TX_FAULT()

    return return_id
