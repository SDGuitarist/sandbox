"""Payment model (refund ledger).

``payments`` is a **refund-only** ledger: the schema CHECK is
``kind IN ('refund')`` and ``create_order`` writes NO payments row. The order's
"original amount" is ``order_total`` (SUM of order_items), NOT a payments row --
so the refund guard reference (see spec §5 pin) is
``refunded_total(conn, order_id) + refund_cents <= order_total(conn, order_id)``.

Class split (spec §5):
- ``list_payments`` / ``list_payments_for`` / ``get_payment`` / ``get_payment_for``
  are read-only queries via the thin ``query`` helper (plain dicts, never a
  ``sqlite3.Row`` across a boundary -- FC63/FC2).
- ``refunded_total(conn, order_id)`` is a **class-C in-tx read** on the
  caller-supplied ``conn`` (used by ``process_return``'s refund guard). NO commit.
- ``add_refund_in_tx(conn, order_id, amount_cents)`` is a **class-C in-tx write**
  on the caller-supplied ``conn``. It NEVER calls ``conn.commit()`` and NEVER
  opens ``transaction()`` -- the caller (``process_return``) owns the atomic unit.

Ownership scoping (spec Ownership-Scoped Getter Contract; run-080 IDOR lesson):
``payments`` ownership is **transitive through the order** -- admins see all,
customers are restricted by a SQL ``EXISTS`` predicate over ``orders`` (never a
fetch-then-compare in Python). A non-owner gets 0 rows -> ``None``/``[]``.
"""

from swarmlimit.database import query


def list_payments(order_id=None):
    """Return payment rows as dicts (unscoped; admin callers).

    When ``order_id`` is given, restrict to that order; otherwise return every
    payment. Ordered newest-first for a stable admin view.
    """
    if order_id is None:
        return query("SELECT * FROM payments ORDER BY id DESC")
    return query(
        "SELECT * FROM payments WHERE order_id = ? ORDER BY id DESC",
        (order_id,),
    )


def list_payments_for(actor):
    """Return payments visible to ``actor`` (Ownership-Scoped Getter Contract).

    Admins see every payment; a customer sees only payments whose order they own
    (ownership is transitive through ``orders`` via a SQL ``EXISTS`` predicate).
    A non-owner therefore gets 0 rows -> ``[]``.
    """
    if actor["role"] == "admin":
        return query("SELECT * FROM payments ORDER BY id DESC")
    return query(
        "SELECT * FROM payments p "
        "WHERE EXISTS (SELECT 1 FROM orders o "
        "WHERE o.id = p.order_id AND o.user_id = ?) "
        "ORDER BY p.id DESC",
        (actor["id"],),
    )


def get_payment(pid):
    """Return the payment row for ``pid`` as a dict, or None if absent."""
    return query("SELECT * FROM payments WHERE id = ?", (pid,), one=True)


def get_payment_for(pid, actor):
    """Return payment ``pid`` if ``actor`` may see it, else None.

    Ownership-Scoped Getter Contract: admins see all; a customer sees the row
    only if they own its order (SQL ``EXISTS`` predicate -- never a post-fetch
    403). A non-owner gets 0 rows -> ``None`` (the route maps that to 404, no
    existence leak).
    """
    if actor["role"] == "admin":
        return query("SELECT * FROM payments WHERE id = ?", (pid,), one=True)
    return query(
        "SELECT * FROM payments p "
        "WHERE p.id = ? AND EXISTS (SELECT 1 FROM orders o "
        "WHERE o.id = p.order_id AND o.user_id = ?)",
        (pid, actor["id"]),
        one=True,
    )


def refunded_total(conn, order_id):
    """Return the cents already refunded for ``order_id`` (class-C in-tx read).

    ``SUM(amount_cents) WHERE kind='refund'`` for the order, on the
    caller-supplied ``conn`` so the read sees the transaction's own uncommitted
    writes. Read-only; NO commit. Used by ``process_return``'s refund guard:
    ``refunded_total + refund_cents <= order_total``. Returns 0 when the order
    has no refunds yet (``SUM`` over 0 rows is NULL -> coalesced to 0).
    """
    cur = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS total "
        "FROM payments WHERE order_id = ? AND kind = 'refund'",
        (order_id,),
    )
    row = cur.fetchone()
    cur.close()
    return int(row["total"])


def add_refund_in_tx(conn, order_id, amount_cents):
    """Insert a refund payment row and return its new id (class-C in-tx write).

    Runs on the caller-supplied ``conn`` inside the caller's ``transaction()``;
    it NEVER calls ``conn.commit()`` and NEVER opens a transaction -- the caller
    (``process_return``) owns the atomic unit (spec §5). Writes a
    ``kind='refund'`` row with ``amount_cents = amount_cents`` (always ``> 0``;
    the route + ``returns.refund_cents > 0`` CHECK enforce that, so the
    ``payments.amount_cents > 0`` CHECK is only a backstop). Called ONLY by
    ``process_return``.
    """
    cur = conn.execute(
        "INSERT INTO payments (order_id, kind, amount_cents) "
        "VALUES (?, 'refund', ?)",
        (order_id, amount_cents),
    )
    return int(cur.lastrowid)
