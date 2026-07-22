"""Product model — soft-delete + stock guard + M2M categories + in-tx helpers.

Owns the ``products`` table plus its M2M join ``product_categories``. The two
distinguishing behaviours of this file (spec §Model Functions / §5):

- **Soft-delete filter:** ``list_products`` / ``get_product`` EXCLUDE rows with a
  non-NULL ``deleted_at`` unless ``include_deleted=True`` (admin history only).
  ``soft_delete_product`` sets ``deleted_at`` and NEVER touches ``order_items``
  (history preserved); it is idempotent (already-deleted → no-op).
- **Stock guard (class-C in-tx):** ``decrement_stock_in_tx`` runs a conditional
  ``UPDATE ... WHERE ... AND deleted_at IS NULL AND stock >= :qty`` and requires
  exactly one row changed, else raises ``ValueError('insufficient stock')`` (also
  fires when the product is soft-deleted → 0 rows).

Transaction discipline (spec §5):
- Class-A writers (``create_product``, ``update_product``, ``soft_delete_product``,
  ``set_product_categories``) execute directly on the request connection which is
  opened ``isolation_level=None`` (SQLite AUTOCOMMIT), so each statement persists
  IMMEDIATELY. They do NOT call ``conn.commit()`` and NEVER open ``transaction()``.
- Class-C in-tx helpers (``decrement_stock_in_tx``, ``restock_product_in_tx``) take
  the caller's transaction ``conn`` (the SAME connection the class-B opener holds
  under ``BEGIN IMMEDIATE``), do NOT commit, and are called ONLY from within a
  class-B ``transaction()``.

All getters convert ``sqlite3.Row`` → plain ``dict`` (FC63 — never leak Row across
a boundary).
"""

from swarmlimit.database import get_db, query
from swarmlimit.models.supplier_models import get_supplier


def _category_ids(pid) -> list[int]:
    """Return the ordered list of category ids attached to product ``pid``."""
    rows = query(
        "SELECT category_id FROM product_categories "
        "WHERE product_id = ? ORDER BY category_id",
        (pid,),
    )
    return [row["category_id"] for row in rows]


def list_products(q=None, category_id=None, include_deleted=False) -> list[dict]:
    """List products as plain dicts.

    Excludes soft-deleted rows (``deleted_at IS NOT NULL``) unless
    ``include_deleted=True``. ``q`` LIKE-matches name OR sku; ``category_id``
    restricts to products joined to that category via ``product_categories``.
    """
    clauses = []
    params: list = []

    if category_id is not None:
        # Join to the M2M table to filter by category membership.
        clauses.append(
            "id IN (SELECT product_id FROM product_categories WHERE category_id = ?)"
        )
        params.append(category_id)

    if q is not None:
        clauses.append("(name LIKE ? OR sku LIKE ?)")
        like = f"%{q}%"
        params.append(like)
        params.append(like)

    if not include_deleted:
        clauses.append("deleted_at IS NULL")

    sql = (
        "SELECT id, sku, name, supplier_id, price_cents, stock, deleted_at, created_at "
        "FROM products"
    )
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"

    return query(sql, tuple(params))


def get_product(pid, include_deleted=False) -> dict | None:
    """Return one product dict (with ``category_ids: list[int]``), or ``None``.

    Returns ``None`` for a soft-deleted product unless ``include_deleted=True``,
    and ``None`` when the id never existed.
    """
    if include_deleted:
        row = query(
            "SELECT id, sku, name, supplier_id, price_cents, stock, deleted_at, created_at "
            "FROM products WHERE id = ?",
            (pid,),
            one=True,
        )
    else:
        row = query(
            "SELECT id, sku, name, supplier_id, price_cents, stock, deleted_at, created_at "
            "FROM products WHERE id = ? AND deleted_at IS NULL",
            (pid,),
            one=True,
        )
    if row is None:
        return None
    row["category_ids"] = _category_ids(pid)
    return row


def create_product(sku, name, supplier_id, price_cents, stock=0, category_ids=None) -> int:
    """Insert a product and attach its M2M category rows; return the new id.

    Validates the supplier exists (raises ``ValueError('supplier not found')``),
    raises ``ValueError('sku exists')` on the UNIQUE(sku) violation. Class-A:
    persists immediately via SQLite autocommit; does not call ``conn.commit()``.
    """
    if get_supplier(supplier_id) is None:
        raise ValueError("supplier not found")

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO products (sku, name, supplier_id, price_cents, stock) "
            "VALUES (?, ?, ?, ?, ?)",
            (sku, name, supplier_id, price_cents, stock),
        )
    except Exception as exc:  # sqlite3.IntegrityError on the UNIQUE(sku)
        if "UNIQUE" in str(exc).upper():
            raise ValueError("sku exists") from exc
        raise
    pid = cur.lastrowid

    for cid in category_ids or []:
        conn.execute(
            "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
            (pid, cid),
        )
    return pid


def update_product(pid, **fields) -> None:
    """Update whitelisted product columns. Class-A (autocommit, no commit call).

    Whitelist: ``name``, ``price_cents``, ``stock``, ``supplier_id``. Unknown keys
    are ignored; an empty/whitelist-free update is a no-op.
    """
    allowed = ("name", "price_cents", "stock", "supplier_id")
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values())
    params.append(pid)
    get_db().execute(
        f"UPDATE products SET {set_clause} WHERE id = ?",
        tuple(params),
    )


def soft_delete_product(pid) -> None:
    """Soft-delete a product: set ``deleted_at = datetime('now')``.

    Does NOT touch ``order_items`` (history preserved). Idempotent — an
    already-deleted product is a no-op because the WHERE clause requires
    ``deleted_at IS NULL``. Class-A (autocommit, no commit call).
    """
    get_db().execute(
        "UPDATE products SET deleted_at = datetime('now') "
        "WHERE id = ? AND deleted_at IS NULL",
        (pid,),
    )


def set_product_categories(pid, category_ids) -> None:
    """Replace the product's M2M category rows with ``category_ids``.

    Class-A: each statement autocommits independently (not atomicity-critical;
    the route validates the ids up front — spec §5(A)).
    """
    conn = get_db()
    conn.execute("DELETE FROM product_categories WHERE product_id = ?", (pid,))
    for cid in category_ids or []:
        conn.execute(
            "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
            (pid, cid),
        )


def decrement_stock_in_tx(conn, pid, qty) -> None:
    """Stock guard (class-C in-tx helper): decrement product stock atomically.

    Runs on the caller-supplied transaction ``conn`` (NO commit). The conditional
    ``UPDATE`` changes a row ONLY if the product is live AND has enough stock; if
    ``rowcount != 1`` (insufficient stock OR soft-deleted → 0 rows) it raises
    ``ValueError('insufficient stock')``. Called ONLY by
    ``order_models.create_order`` inside its ``transaction()``.
    """
    cur = conn.execute(
        "UPDATE products SET stock = stock - :qty "
        "WHERE id = :pid AND deleted_at IS NULL AND stock >= :qty",
        {"qty": qty, "pid": pid},
    )
    if cur.rowcount != 1:
        raise ValueError("insufficient stock")


def restock_product_in_tx(conn, pid, qty) -> None:
    """Restock a product (class-C in-tx helper): add ``qty`` back to stock.

    Runs on the caller-supplied transaction ``conn`` (NO commit). Restocks
    regardless of ``deleted_at`` — a returned unit re-enters inventory even if the
    SKU was since retired. Called ONLY by ``return_models.process_return`` inside
    its ``transaction()``.
    """
    conn.execute(
        "UPDATE products SET stock = stock + :qty WHERE id = :pid",
        {"qty": qty, "pid": pid},
    )
