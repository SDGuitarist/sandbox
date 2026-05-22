import sqlite3


# get_all_tanks(conn) -> list[sqlite3.Row]
# SERIAL-SAFE: single SELECT, no cross-table dependencies
def get_all_tanks(conn: sqlite3.Connection) -> list:
    return conn.execute('SELECT * FROM tanks ORDER BY name').fetchall()


# get_tank(conn, tank_id) -> sqlite3.Row | None
# SERIAL-SAFE: single SELECT by primary key
def get_tank(conn: sqlite3.Connection, tank_id: int):
    return conn.execute('SELECT * FROM tanks WHERE id = ?', (tank_id,)).fetchone()


# get_available_tanks(conn) -> list[sqlite3.Row]
# Returns tanks where current_batch_id IS NULL (not occupied by a batch)
# SERIAL-SAFE: single SELECT with filter
def get_available_tanks(conn: sqlite3.Connection) -> list:
    return conn.execute(
        'SELECT * FROM tanks WHERE current_batch_id IS NULL ORDER BY name'
    ).fetchall()


# create_tank(conn, name, capacity_gallons, tank_type, notes) -> int
# Returns: the new tank's ID
# SERIAL-SAFE: single INSERT, caller commits
def create_tank(conn: sqlite3.Connection, name: str, capacity_gallons: float,
                tank_type: str, notes: str) -> int:
    cur = conn.execute(
        'INSERT INTO tanks (name, capacity_gallons, tank_type, notes) VALUES (?, ?, ?, ?)',
        (name, capacity_gallons, tank_type, notes))
    return cur.lastrowid


# update_tank(conn, tank_id, name, capacity_gallons, tank_type, notes) -> None
# SERIAL-SAFE: single UPDATE, caller commits
def update_tank(conn: sqlite3.Connection, tank_id: int, name: str,
                capacity_gallons: float, tank_type: str, notes: str) -> None:
    conn.execute(
        "UPDATE tanks SET name=?, capacity_gallons=?, tank_type=?, notes=?, updated_at=datetime('now') WHERE id=?",
        (name, capacity_gallons, tank_type, notes, tank_id))


# delete_tank(conn, tank_id) -> None
# SERIAL-SAFE: single DELETE, caller commits
def delete_tank(conn: sqlite3.Connection, tank_id: int) -> None:
    conn.execute('DELETE FROM tanks WHERE id = ?', (tank_id,))
