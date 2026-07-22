"""Shipment model (shipment model agent -- STATE MACHINE).

The ``shipments`` table is the fulfillment state machine. Its legal, client-
reachable transitions are ``pending -> shipped -> delivered`` ONLY, encoded in
the ``LEGAL_TRANSITIONS`` module constant. The ``-> 'returned'`` transition is
DELIBERATELY ABSENT here: it is reachable ONLY via ``set_shipment_status_in_tx``
called inside ``return_models.process_return`` (a return event sets it
atomically; a customer/staff can never "advance" a shipment to ``returned``).

Class-A writers (``create_shipment``, ``advance_shipment``): each write executes
directly on the request connection. Because the connection is opened with
``isolation_level=None`` (SQLite AUTOCOMMIT), the single statement persists
immediately -- these functions NEVER call ``conn.commit()`` and NEVER open
``transaction()`` (that is class-B only; see spec §5).

Class-C in-tx helper (``set_shipment_status_in_tx``): takes the caller's ``conn``
and NEVER commits nor opens a transaction -- it runs inside the class-B
``process_return`` unit which owns the transaction boundary.

Every function converts ``sqlite3.Row`` -> plain ``dict`` before returning so a
``sqlite3.Row`` never leaks across an agent boundary (FC63/FC2). The thin
``query`` helper from ``swarmlimit.database`` already returns plain dicts.
"""

import sqlite3

from swarmlimit.database import get_db, query

# The ONLY legal, client-reachable state transitions (spec §5 state machine).
# ``('...', 'returned')`` is DELIBERATELY ABSENT for every source status -- a
# client ``advance`` to ``returned`` therefore always raises 'illegal
# transition' (route -> 409). Only ``process_return`` sets ``'returned'`` via
# ``set_shipment_status_in_tx``.
LEGAL_TRANSITIONS = {("pending", "shipped"), ("shipped", "delivered")}


def list_shipments(order_id=None, status=None):
    """Return shipments as a list of dicts, optionally filtered.

    Unscoped (admin callers). ``order_id`` / ``status`` are optional AND filters.
    """
    sql = "SELECT * FROM shipments"
    clauses = []
    params = []
    if order_id is not None:
        clauses.append("order_id = ?")
        params.append(order_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    return query(sql, tuple(params))


def get_shipment(sid):
    """Return the shipment row as a dict, or None if absent (unscoped)."""
    return query("SELECT * FROM shipments WHERE id = ?", (sid,), one=True)


def get_shipment_for(sid, actor):
    """Return the shipment as a dict scoped to ``actor``, or None.

    Ownership-Scoped Getter Contract (spec §Model Functions). The ownership
    check is a SQL WHERE predicate, never a fetch-then-compare in Python:

    - admin -> no ownership restriction (sees all);
    - customer -> ownership is transitive through the order:
      ``EXISTS (SELECT 1 FROM orders o WHERE o.id = shipments.order_id
      AND o.user_id = :actor_id)``.

    A non-owner gets 0 rows -> ``None`` (the route maps that to 404 -- no 403,
    no existence leak). ``actor`` is a non-``None`` ``current_user()`` dict
    (the route's ``login_required`` guarantees it).
    """
    if actor["role"] == "admin":
        return query("SELECT * FROM shipments WHERE id = ?", (sid,), one=True)
    return query(
        "SELECT * FROM shipments WHERE id = ? AND EXISTS ("
        "SELECT 1 FROM orders o WHERE o.id = shipments.order_id "
        "AND o.user_id = ?)",
        (sid, actor["id"]),
        one=True,
    )


def create_shipment(order_id, carrier=None, tracking=None):
    """Create the single shipment for ``order_id``, returning the new id.

    Validates the order exists (else ``ValueError('order not found')``). Inserts
    ``status='pending'``. Exactly one shipment per order: the ``UNIQUE(order_id)``
    constraint fires an ``IntegrityError`` on a second attempt, caught and
    re-raised as ``ValueError('shipment exists')`` (route -> 409 ``conflict``) --
    including after the first shipment has been advanced to ``returned``, so no
    fresh shipment can be minted to bypass the once-per-order return bound.

    Class-A writer: persists immediately via SQLite autocommit
    (``isolation_level=None``) -- does NOT call ``conn.commit()`` and does NOT
    open a transaction (spec §5).
    """
    conn = get_db()
    order = query("SELECT id FROM orders WHERE id = ?", (order_id,), one=True)
    if order is None:
        raise ValueError("order not found")
    try:
        cursor = conn.execute(
            "INSERT INTO shipments (order_id, status, carrier, tracking) "
            "VALUES (?, 'pending', ?, ?)",
            (order_id, carrier, tracking),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("shipment exists") from exc
    return cursor.lastrowid


def advance_shipment(sid, to_status):
    """Advance shipment ``sid`` to ``to_status`` if the transition is legal.

    The ROUTE has already checked ``to_status`` is one of the four stored
    statuses (``{pending, shipped, delivered, returned}``, else 400). This reads
    the current status; if ``(current, to_status)`` is NOT in
    ``LEGAL_TRANSITIONS`` it raises ``ValueError('illegal transition')`` and
    LEAVES THE STATUS UNCHANGED (route -> 409). On a legal transition it updates
    ``status`` and ``updated_at``.

    NEVER succeeds for ``'returned'``: ``(x, 'returned')`` is not in
    ``LEGAL_TRANSITIONS`` for any ``x``, so a client ``advance`` to ``returned``
    always 409s -- only ``process_return`` sets ``'returned'``.

    Class-A writer: persists immediately via SQLite autocommit -- does NOT call
    ``conn.commit()`` and does NOT open a transaction (spec §5).
    """
    conn = get_db()
    shipment = query(
        "SELECT status FROM shipments WHERE id = ?", (sid,), one=True
    )
    if shipment is None:
        raise ValueError("shipment not found")
    current = shipment["status"]
    if (current, to_status) not in LEGAL_TRANSITIONS:
        # Illegal transition -- raise and leave the status UNCHANGED.
        raise ValueError("illegal transition")
    conn.execute(
        "UPDATE shipments SET status = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (to_status, sid),
    )


def set_shipment_status_in_tx(conn, sid, status):
    """Unconditionally set shipment ``sid``'s status on the caller's ``conn``.

    In-tx helper (class-C, spec §5): runs on the caller-supplied ``conn`` and
    NEVER commits nor opens a transaction. Called ONLY by
    ``return_models.process_return`` (to set ``'returned'``); the caller has
    already validated the shipment is ``'delivered'``, so this bypasses
    ``LEGAL_TRANSITIONS`` on purpose -- ``returned`` is unreachable through the
    client-facing ``advance_shipment`` path.
    """
    conn.execute(
        "UPDATE shipments SET status = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (status, sid),
    )
