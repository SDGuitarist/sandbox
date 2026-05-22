import sqlite3


# get_all_ingredients(conn) -> list[sqlite3.Row]
def get_all_ingredients(conn: sqlite3.Connection) -> list:
    return conn.execute('SELECT * FROM ingredients ORDER BY name').fetchall()


# get_ingredient(conn, ingredient_id) -> sqlite3.Row | None
def get_ingredient(conn: sqlite3.Connection, ingredient_id: int):
    return conn.execute('SELECT * FROM ingredients WHERE id = ?', (ingredient_id,)).fetchone()


# create_ingredient(conn, name, category, stock_qty, unit, low_stock_threshold) -> int
# Returns: the new ingredient's ID
# Usage: ingredient_id = create_ingredient(conn, ...)
#        conn.commit()
def create_ingredient(conn: sqlite3.Connection, name: str, category: str,
                      stock_qty: float, unit: str, low_stock_threshold: float) -> int:
    cur = conn.execute(
        'INSERT INTO ingredients (name, category, stock_qty, unit, low_stock_threshold) VALUES (?, ?, ?, ?, ?)',
        (name, category, stock_qty, unit, low_stock_threshold))
    return cur.lastrowid


# update_ingredient(conn, ingredient_id, name, category, stock_qty, unit, low_stock_threshold) -> None
# Usage: update_ingredient(conn, ingredient_id, ...)
#        conn.commit()
def update_ingredient(conn: sqlite3.Connection, ingredient_id: int, name: str,
                      category: str, stock_qty: float, unit: str,
                      low_stock_threshold: float) -> None:
    conn.execute(
        "UPDATE ingredients SET name=?, category=?, stock_qty=?, unit=?, low_stock_threshold=?, updated_at=datetime('now') WHERE id=?",
        (name, category, stock_qty, unit, low_stock_threshold, ingredient_id))


# delete_ingredient(conn, ingredient_id) -> None
def delete_ingredient(conn: sqlite3.Connection, ingredient_id: int) -> None:
    conn.execute('DELETE FROM ingredients WHERE id = ?', (ingredient_id,))


# get_low_stock_ingredients(conn) -> list[sqlite3.Row]
# Returns ingredients where stock_qty <= low_stock_threshold
def get_low_stock_ingredients(conn: sqlite3.Connection) -> list:
    return conn.execute(
        'SELECT * FROM ingredients WHERE stock_qty <= low_stock_threshold ORDER BY name'
    ).fetchall()
