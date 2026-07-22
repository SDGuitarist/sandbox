"""Category model (category model agent).

Class-A writers: each write executes directly on the request connection. Because
the connection is opened with ``isolation_level=None`` (SQLite AUTOCOMMIT), the
single statement persists immediately -- these functions NEVER call
``conn.commit()`` and NEVER open ``transaction()`` (that is class-B only; see
spec §5).

Every function converts ``sqlite3.Row`` -> plain ``dict`` before returning so a
``sqlite3.Row`` never leaks across an agent boundary (FC63/FC2). The thin
``query`` helper from ``swarmlimit.database`` already returns plain dicts.
"""

import sqlite3

from swarmlimit.database import get_db, query


def list_categories():
    """Return all categories as a list of dicts (ordered by name)."""
    return query("SELECT * FROM categories ORDER BY name")


def get_category(cid):
    """Return the category row as a dict, or None if absent."""
    return query("SELECT * FROM categories WHERE id = ?", (cid,), one=True)


def create_category(name):
    """Create a category, returning the new category id.

    Persists immediately via SQLite autocommit (``isolation_level=None``) -- does
    NOT call ``conn.commit()`` and does NOT open a transaction (class-A writer,
    spec §5).

    Raises ``ValueError('name exists')`` on a UNIQUE(name) violation.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO categories (name) VALUES (?)",
            (name,),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("name exists") from exc
    return cursor.lastrowid


def update_category(cid, **fields):
    """Update whitelisted category fields. Returns None.

    Whitelist: ``name``. Unknown fields are ignored. A no-op (no whitelisted
    fields supplied) makes no DB write. Persists immediately via SQLite
    autocommit -- does NOT call ``conn.commit()`` and does NOT open a
    transaction (class-A writer, spec §5).

    Raises ``ValueError('name exists')`` on a UNIQUE(name) violation.
    """
    allowed = ("name",)
    updates = {k: fields[k] for k in allowed if k in fields}
    if not updates:
        return None
    columns = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values()) + [cid]
    conn = get_db()
    try:
        conn.execute(
            f"UPDATE categories SET {columns} WHERE id = ?",
            params,
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("name exists") from exc
    return None


def delete_category(cid):
    """Hard-delete a category. Returns None.

    Relies on the FK RESTRICT edge ``product_categories.category_id`` ->
    ``categories(id)``: if any ``product_categories`` row references this
    category, SQLite raises ``IntegrityError``, which we translate to
    ``ValueError('category in use')``. Persists immediately via SQLite
    autocommit -- does NOT call ``conn.commit()`` and does NOT open a
    transaction (class-A writer, spec §5).
    """
    conn = get_db()
    try:
        conn.execute("DELETE FROM categories WHERE id = ?", (cid,))
    except sqlite3.IntegrityError as exc:
        raise ValueError("category in use") from exc
    return None
