"""Core model functions shared across the RestaurantOps application.

Provides access to predefined reference data (allergens, etc.) that multiple
blueprints depend on.
"""

import sqlite3


def get_all_allergens(conn: sqlite3.Connection) -> list:
    """Return all allergens ordered by name.

    Returns:
        list[sqlite3.Row]: Each row has 'id' and 'name' columns.

    Usage::

        allergens = get_all_allergens(conn)
        for a in allergens:
            print(a['name'])
    """
    return conn.execute(
        "SELECT id, name FROM allergens ORDER BY name"
    ).fetchall()
