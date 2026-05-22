import sqlite3


def get_all_recipes(conn: sqlite3.Connection) -> list:
    """Return all recipes ordered by name."""
    return conn.execute('SELECT * FROM recipes ORDER BY name').fetchall()


def get_recipe(conn: sqlite3.Connection, recipe_id: int):
    """Return a single recipe by ID, or None if not found."""
    return conn.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,)).fetchone()


def create_recipe(conn: sqlite3.Connection, name: str, style: str,
                  target_abv: float | None, notes: str) -> int:
    """Insert a new recipe and return its ID. SERIAL-SAFE: caller commits."""
    cur = conn.execute(
        'INSERT INTO recipes (name, style, target_abv, notes) VALUES (?, ?, ?, ?)',
        (name, style, target_abv, notes))
    return cur.lastrowid


def update_recipe(conn: sqlite3.Connection, recipe_id: int, name: str,
                  style: str, target_abv: float | None, notes: str) -> None:
    """Update an existing recipe. SERIAL-SAFE: caller commits."""
    conn.execute(
        "UPDATE recipes SET name=?, style=?, target_abv=?, notes=?, updated_at=datetime('now') WHERE id=?",
        (name, style, target_abv, notes, recipe_id))


def delete_recipe(conn: sqlite3.Connection, recipe_id: int) -> None:
    """Delete a recipe by ID. SERIAL-SAFE: caller commits."""
    conn.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
