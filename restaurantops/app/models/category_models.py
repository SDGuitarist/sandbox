"""Category model functions for RestaurantOps.

CRUD operations for menu categories. Functions do NOT commit --
the caller is responsible for committing the transaction.
"""
import sqlite3


def create_category(conn: sqlite3.Connection, name: str, sort_order: int = 0) -> int:
    """Create a new category and return its ID.

    Args:
        conn: Database connection.
        name: Category name (must be unique).
        sort_order: Display order (lower = first).

    Returns:
        int: The new category's ID.
    """
    cursor = conn.execute(
        "INSERT INTO categories (name, sort_order) VALUES (?, ?)",
        (name, sort_order),
    )
    return cursor.lastrowid


def get_all_categories(conn: sqlite3.Connection) -> list:
    """Return all categories ordered by sort_order then name.

    Returns:
        list[sqlite3.Row]: All category rows.
    """
    return conn.execute(
        "SELECT * FROM categories ORDER BY sort_order, name"
    ).fetchall()


def get_category(conn: sqlite3.Connection, category_id: int):
    """Return a single category by ID, or None if not found.

    Returns:
        sqlite3.Row or None
    """
    return conn.execute(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    ).fetchone()


def update_category(conn: sqlite3.Connection, category_id: int, name: str, sort_order: int) -> None:
    """Update an existing category's name and sort order."""
    conn.execute(
        "UPDATE categories SET name = ?, sort_order = ? WHERE id = ?",
        (name, sort_order, category_id),
    )


def delete_category(conn: sqlite3.Connection, category_id: int) -> None:
    """Delete a category by ID.

    Menu items referencing this category will have category_id set to NULL
    (ON DELETE SET NULL in the schema).
    """
    conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
