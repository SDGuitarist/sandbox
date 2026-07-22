"""Supplier model (catalog parent — transitive ownership root for products).

All writers here are **class-A** (spec §5): each issues a single
``INSERT/UPDATE/DELETE`` on the request connection, which is opened
``isolation_level=None`` (SQLite AUTOCOMMIT), so the statement persists
**immediately**. No writer calls ``conn.commit()`` and none opens
``transaction()`` (that is class-B only).

Return-shape contract (FC63 / spec Model-Functions convention):
- single-row getter → ``dict | None``
- lister → ``list[dict]``
- creator → new ``int`` id
- mutator → ``None``

``query`` already materialises rows as plain ``dict``s, so no ``sqlite3.Row``
leaks across the agent boundary.
"""

import sqlite3

from swarmlimit.database import get_db, query

# Fields a PATCH may set on a supplier (spec §Model-Functions / §3). Any other
# key in ``**fields`` is ignored — the model never trusts the caller to have
# filtered, and never writes an un-whitelisted column.
_UPDATE_WHITELIST = ("name", "contact_email", "active")


def list_suppliers(active_only=False) -> list[dict]:
    """Return all suppliers as ``list[dict]`` (ordered by id).

    When ``active_only`` is truthy, restrict to ``active = 1``.
    """
    if active_only:
        return query(
            "SELECT id, name, contact_email, active, created_at "
            "FROM suppliers WHERE active = 1 ORDER BY id",
        )
    return query(
        "SELECT id, name, contact_email, active, created_at "
        "FROM suppliers ORDER BY id",
    )


def get_supplier(sid) -> dict | None:
    """Return one supplier as a plain ``dict``, or ``None`` if absent."""
    return query(
        "SELECT id, name, contact_email, active, created_at "
        "FROM suppliers WHERE id = ?",
        (sid,),
        one=True,
    )


def create_supplier(name, contact_email=None) -> int:
    """Insert a supplier (defaults ``active = 1`` via schema) and return its id.

    Class-A: persists immediately via SQLite autocommit; does not call
    ``conn.commit()`` and does not open ``transaction()``.
    """
    cur = get_db().execute(
        "INSERT INTO suppliers (name, contact_email) VALUES (?, ?)",
        (name, contact_email),
    )
    return cur.lastrowid


def update_supplier(sid, **fields) -> None:
    """Update whitelisted columns (name, contact_email, active) on a supplier.

    Only keys in ``_UPDATE_WHITELIST`` are written; any other key is ignored.
    If no whitelisted field is supplied, this is a no-op (the route enforces the
    "at least one field" rule and 400s before calling; §3). Class-A: persists
    immediately via SQLite autocommit; no ``conn.commit()``, no ``transaction()``.
    """
    updates = {k: fields[k] for k in _UPDATE_WHITELIST if k in fields}
    if not updates:
        return
    assignments = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values())
    params.append(sid)
    get_db().execute(
        f"UPDATE suppliers SET {assignments} WHERE id = ?",
        params,
    )


def delete_supplier(sid) -> None:
    """Hard-delete a supplier.

    Relies on the ``products.supplier_id`` FK (``ON DELETE RESTRICT``): if any
    product still references this supplier, SQLite raises ``IntegrityError``,
    which is caught and re-raised as ``ValueError('supplier in use')`` (route →
    409 ``conflict``). Class-A: persists immediately via SQLite autocommit; no
    ``conn.commit()``, no ``transaction()``.
    """
    try:
        get_db().execute("DELETE FROM suppliers WHERE id = ?", (sid,))
    except sqlite3.IntegrityError:
        raise ValueError("supplier in use")
