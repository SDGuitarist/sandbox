import sqlite3


# All functions are SERIAL-SAFE: single-row operations with no cross-table
# dependencies. The route handler calls conn.commit() after each call.
# Do NOT call conn.commit() inside these functions.


def get_all_taps(conn: sqlite3.Connection) -> list:
    """Return all taps joined with batch and recipe info, ordered by position."""
    return conn.execute('''
        SELECT t.*, b.name as batch_name, b.remaining_volume_oz, b.status as batch_status,
               r.name as recipe_name
        FROM taps t
        LEFT JOIN batches b ON t.batch_id = b.id
        LEFT JOIN recipes r ON b.recipe_id = r.id
        ORDER BY t.position
    ''').fetchall()


def get_tap(conn: sqlite3.Connection, tap_id: int):
    """Return a single tap joined with batch and recipe info, or None."""
    return conn.execute('''
        SELECT t.*, b.name as batch_name, b.remaining_volume_oz, b.status as batch_status,
               r.name as recipe_name
        FROM taps t
        LEFT JOIN batches b ON t.batch_id = b.id
        LEFT JOIN recipes r ON b.recipe_id = r.id
        WHERE t.id = ?
    ''', (tap_id,)).fetchone()


def get_available_taps(conn: sqlite3.Connection) -> list:
    """Return taps where batch_id IS NULL (available for assignment)."""
    return conn.execute(
        'SELECT * FROM taps WHERE batch_id IS NULL ORDER BY position'
    ).fetchall()


def create_tap(conn: sqlite3.Connection, name: str, position: int) -> int:
    """Insert a new tap and return its ID."""
    cur = conn.execute(
        'INSERT INTO taps (name, position) VALUES (?, ?)', (name, position))
    return cur.lastrowid


def update_tap(conn: sqlite3.Connection, tap_id: int, name: str, position: int) -> None:
    """Update a tap's name and position."""
    conn.execute(
        "UPDATE taps SET name=?, position=?, updated_at=datetime('now') WHERE id=?",
        (name, position, tap_id))


def delete_tap(conn: sqlite3.Connection, tap_id: int) -> None:
    """Delete a tap by ID."""
    conn.execute('DELETE FROM taps WHERE id = ?', (tap_id,))
