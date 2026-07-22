"""Database connection, schema init/seed, and query/transaction helpers.

Stdlib ``sqlite3`` only. The request connection is opened in AUTOCOMMIT mode
(``isolation_level=None``): each bare statement commits immediately, so class-A
writers persist without any ``conn.commit()``. The ONLY explicit transaction
boundary is the ``BEGIN IMMEDIATE`` issued by ``transaction()`` (class-B units).
"""

import os
import sqlite3
from contextlib import contextmanager

from flask import current_app, g
from werkzeug.security import generate_password_hash

# Schema DDL lives beside this module (database agent owns both files).
_SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def _db_path():
    """Resolve the on-disk SQLite path from Flask config (real file, never :memory:)."""
    return current_app.config["DATABASE"]


def get_db() -> sqlite3.Connection:
    """Return the one connection for this request, opening it on first use.

    Opened with ``isolation_level=None`` (AUTOCOMMIT); ``row_factory`` is
    ``sqlite3.Row``. Sets the three per-connection pragmas every time a
    connection is opened (pragmas are per-connection, not per-database).
    Cached on Flask ``g`` so every model function in a request shares it.
    """
    if "db" not in g:
        conn = sqlite3.connect(_db_path(), isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        g.db = conn
    return g.db


def close_db(exception=None) -> None:
    """Teardown hook: close the request connection if one was opened."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql, params=(), one=False):
    """Run ``sql`` on the request connection and return plain dicts.

    ``one=True`` returns a single ``dict`` or ``None`` (never a ``sqlite3.Row``
    across a boundary); otherwise a ``list[dict]``.
    """
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(row) for row in rows]


@contextmanager
def transaction():
    """Explicit atomic unit on the single request connection (class-B only).

    Because the connection is AUTOCOMMIT (``isolation_level=None``), this
    ``BEGIN IMMEDIATE`` is the ONLY transaction boundary — it takes the write
    lock up front so concurrent class-B writers serialize. On a clean exit the
    unit is committed; on ANY exception it is rolled back and the exception is
    re-raised. Nested ``transaction()`` is forbidden.
    """
    conn = get_db()
    conn.execute("BEGIN IMMEDIATE;")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK;")
        raise
    else:
        conn.execute("COMMIT;")


def init_db() -> None:
    """Create the schema from ``schema.sql`` and insert seed rows.

    Called by the app factory only when the DB file is absent (the DDL is
    ``CREATE TABLE``, run exactly once). Runs the whole thing on a fresh
    connection so it works before any request context exists.
    """
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as fh:
        schema_sql = fh.read()

    conn = sqlite3.connect(_db_path(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.executescript(schema_sql)
        _seed(conn)
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    """Insert seed rows. Every row satisfies all NOT NULL / CHECK / UNIQUE.

    Passwords are hashed with the SAME library ``verify_credentials`` uses
    (werkzeug), so seeded users can log in.
    """
    # --- users: 1 admin + 2 customers ---
    admin_id = conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'admin', ?)",
        ("admin@swarm.test", generate_password_hash("swarmpass"), "Swarm Admin"),
    ).lastrowid
    customer1_id = conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'customer', ?)",
        ("customer1@swarm.test", generate_password_hash("custpass1"), "Customer One"),
    ).lastrowid
    conn.execute(
        "INSERT INTO users (email, password_hash, role, name) VALUES (?, ?, 'customer', ?)",
        ("customer2@swarm.test", generate_password_hash("custpass2"), "Customer Two"),
    )

    # --- suppliers: 2 ---
    supplier1_id = conn.execute(
        "INSERT INTO suppliers (name, contact_email, active) VALUES (?, ?, 1)",
        ("Acme Supply Co", "sales@acme.test"),
    ).lastrowid
    supplier2_id = conn.execute(
        "INSERT INTO suppliers (name, contact_email, active) VALUES (?, ?, 1)",
        ("Globex Distribution", "orders@globex.test"),
    ).lastrowid

    # --- categories: 3 ---
    cat_widgets = conn.execute(
        "INSERT INTO categories (name) VALUES (?)", ("Widgets",)
    ).lastrowid
    cat_gadgets = conn.execute(
        "INSERT INTO categories (name) VALUES (?)", ("Gadgets",)
    ).lastrowid
    cat_accessories = conn.execute(
        "INSERT INTO categories (name) VALUES (?)", ("Accessories",)
    ).lastrowid

    # --- products: 4 (each supplier + >=1 category; stock >= 5; deleted_at NULL) ---
    product1_id = conn.execute(
        "INSERT INTO products (sku, name, supplier_id, price_cents, stock) "
        "VALUES (?, ?, ?, ?, ?)",
        ("SKU-WIDGET-01", "Standard Widget", supplier1_id, 1999, 50),
    ).lastrowid
    product2_id = conn.execute(
        "INSERT INTO products (sku, name, supplier_id, price_cents, stock) "
        "VALUES (?, ?, ?, ?, ?)",
        ("SKU-GADGET-01", "Deluxe Gadget", supplier1_id, 4999, 25),
    ).lastrowid
    product3_id = conn.execute(
        "INSERT INTO products (sku, name, supplier_id, price_cents, stock) "
        "VALUES (?, ?, ?, ?, ?)",
        ("SKU-CABLE-01", "USB-C Cable", supplier2_id, 899, 200),
    ).lastrowid
    product4_id = conn.execute(
        "INSERT INTO products (sku, name, supplier_id, price_cents, stock) "
        "VALUES (?, ?, ?, ?, ?)",
        ("SKU-CASE-01", "Protective Case", supplier2_id, 1499, 75),
    ).lastrowid

    # --- product_categories: each product has >= 1 category ---
    conn.executemany(
        "INSERT INTO product_categories (product_id, category_id) VALUES (?, ?)",
        [
            (product1_id, cat_widgets),
            (product2_id, cat_gadgets),
            (product3_id, cat_accessories),
            (product4_id, cat_accessories),
            (product4_id, cat_gadgets),
        ],
    )

    # --- 1 order for customer-1 with 2 order_items (snapshot unit prices) ---
    order1_id = conn.execute(
        "INSERT INTO orders (user_id, ext_ref, status) VALUES (?, ?, 'placed')",
        (customer1_id, "ORD-SEED-0001"),
    ).lastrowid
    conn.executemany(
        "INSERT INTO order_items (order_id, product_id, qty, unit_price_cents) "
        "VALUES (?, ?, ?, ?)",
        [
            (order1_id, product1_id, 2, 1999),
            (order1_id, product3_id, 1, 899),
        ],
    )

    # NO shipments / returns / payments seeded — created by smoke's Path-B cases.
    # admin_id is bound above for clarity even though it is not referenced again.
    _ = admin_id
