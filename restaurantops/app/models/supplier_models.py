"""Supplier CRUD model functions.

All functions receive a sqlite3.Connection and do NOT commit.
The caller is responsible for committing the transaction.
"""

import sqlite3


def create_supplier(conn: sqlite3.Connection, name: str, contact_name: str,
                    phone: str, email: str, address: str, notes: str) -> int:
    """Insert a new supplier and return its ID. Does not commit."""
    cursor = conn.execute(
        """INSERT INTO suppliers (name, contact_name, phone, email, address, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, contact_name, phone, email, address, notes),
    )
    return cursor.lastrowid


def get_all_suppliers(conn: sqlite3.Connection) -> list:
    """Return all suppliers ordered by name."""
    return conn.execute(
        "SELECT * FROM suppliers ORDER BY name"
    ).fetchall()


def get_supplier(conn: sqlite3.Connection, supplier_id: int):
    """Return a single supplier by ID, or None."""
    return conn.execute(
        "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
    ).fetchone()


def update_supplier(conn: sqlite3.Connection, supplier_id: int, name: str,
                    contact_name: str, phone: str, email: str,
                    address: str, notes: str) -> None:
    """Update all editable fields on a supplier. Does not commit."""
    conn.execute(
        """UPDATE suppliers
           SET name = ?, contact_name = ?, phone = ?, email = ?,
               address = ?, notes = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (name, contact_name, phone, email, address, notes, supplier_id),
    )


def delete_supplier(conn: sqlite3.Connection, supplier_id: int) -> None:
    """Delete a supplier by ID. Does not commit."""
    conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
