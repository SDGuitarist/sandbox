import sqlite3

# Status transition map -- only these transitions are valid
VALID_TRANSITIONS = {
    'planned': ['brewing'],
    'brewing': ['fermenting'],
    'fermenting': ['conditioning'],
    'conditioning': ['ready'],
    'ready': ['tapped'],
    'tapped': [],  # Only create_sale() can transition tapped->empty (clears tap atomically)
    'empty': [],
}


# get_all_batches(conn) -> list[sqlite3.Row]
# Returns all batches joined with recipe name and tank name
# Usage: batches = get_all_batches(conn)
def get_all_batches(conn: sqlite3.Connection) -> list:
    return conn.execute('''
        SELECT b.*, r.name as recipe_name, t.name as tank_name
        FROM batches b
        LEFT JOIN recipes r ON b.recipe_id = r.id
        LEFT JOIN tanks t ON b.tank_id = t.id
        ORDER BY b.created_at DESC
    ''').fetchall()


# get_batch(conn, batch_id) -> sqlite3.Row | None
# Returns a single batch joined with recipe name and tank name
# Usage: batch = get_batch(conn, batch_id)
#        if batch is None: abort(404)
def get_batch(conn: sqlite3.Connection, batch_id: int):
    return conn.execute('''
        SELECT b.*, r.name as recipe_name, t.name as tank_name
        FROM batches b
        LEFT JOIN recipes r ON b.recipe_id = r.id
        LEFT JOIN tanks t ON b.tank_id = t.id
        WHERE b.id = ?
    ''', (batch_id,)).fetchone()


def get_batches_by_statuses(conn: sqlite3.Connection, statuses: list) -> dict:
    """Return batches grouped by status in a single query."""
    placeholders = ','.join('?' * len(statuses))
    rows = conn.execute(f'''
        SELECT b.*, r.name as recipe_name
        FROM batches b
        LEFT JOIN recipes r ON b.recipe_id = r.id
        WHERE b.status IN ({placeholders})
        ORDER BY b.created_at DESC
    ''', statuses).fetchall()
    result = {s: [] for s in statuses}
    for row in rows:
        result[row['status']].append(row)
    return result


# create_batch(conn, recipe_id, name, volume_gallons, notes) -> int
# Returns: the new batch's ID
# Remaining_volume_oz is set to volume_gallons * 128 (gallons to oz)
# SERIAL-SAFE: does NOT call conn.commit() -- caller commits
# Usage: batch_id = create_batch(conn, recipe_id, name, volume_gallons, notes)
#        conn.commit()
#        redirect(url_for('batches.detail', batch_id=batch_id))
def create_batch(conn: sqlite3.Connection, recipe_id: int, name: str,
                 volume_gallons: float, notes: str) -> int:
    remaining_oz = volume_gallons * 128  # 1 gallon = 128 oz
    cur = conn.execute(
        'INSERT INTO batches (recipe_id, name, volume_gallons, remaining_volume_oz, notes) VALUES (?, ?, ?, ?, ?)',
        (recipe_id, name, volume_gallons, remaining_oz, notes))
    return cur.lastrowid


# start_brewing(conn, batch_id, tank_id) -> str | None
# NEEDS-BEGIN-IMMEDIATE: assigns tank + decrements all recipe ingredients
# Returns: None on success, error message string on failure
# DERIVED STATE: updates tanks.current_batch_id, ingredients.stock_qty, batches.status
# All business checks are inside BEGIN IMMEDIATE (TOCTOU-safe, FC43)
# Uses raw SQL to query recipe_ingredients (does NOT import from recipe_ingredient_models)
# Usage: error = start_brewing(conn, batch_id, tank_id)
#        if error:
#            flash(error, 'error')
#            return redirect(...)
def start_brewing(conn: sqlite3.Connection, batch_id: int, tank_id: int) -> str | None:
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Re-read batch inside transaction (authoritative)
        batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
        if batch is None:
            conn.execute('ROLLBACK')
            return 'Batch not found'
        if batch['status'] != 'planned':
            conn.execute('ROLLBACK')
            return 'Batch must be in planned status to start brewing'

        # Re-read tank inside transaction (authoritative, TOCTOU-safe)
        tank = conn.execute('SELECT * FROM tanks WHERE id = ?', (tank_id,)).fetchone()
        if tank is None:
            conn.execute('ROLLBACK')
            return 'Tank not found'
        if tank['current_batch_id'] is not None:
            conn.execute('ROLLBACK')
            return 'Tank is already occupied'
        if tank['capacity_gallons'] < batch['volume_gallons']:
            conn.execute('ROLLBACK')
            return 'Batch volume exceeds tank capacity'

        # Check and decrement all recipe ingredients (raw SQL, no import)
        recipe_ings = conn.execute(
            'SELECT ri.*, i.stock_qty, i.name as ingredient_name FROM recipe_ingredients ri '
            'JOIN ingredients i ON ri.ingredient_id = i.id WHERE ri.recipe_id = ?',
            (batch['recipe_id'],)).fetchall()

        for ri in recipe_ings:
            if ri['stock_qty'] < ri['quantity']:
                conn.execute('ROLLBACK')
                return f"Insufficient stock for {ri['ingredient_name']}: need {ri['quantity']}, have {ri['stock_qty']}"
            conn.execute(
                "UPDATE ingredients SET stock_qty = stock_qty - ?, updated_at = datetime('now') WHERE id = ?",
                (ri['quantity'], ri['ingredient_id']))

        # Assign tank
        conn.execute(
            "UPDATE tanks SET current_batch_id = ?, updated_at = datetime('now') WHERE id = ?",
            (batch_id, tank_id))

        # Update batch status and tank assignment
        conn.execute(
            "UPDATE batches SET status = 'brewing', tank_id = ?, brew_date = date('now'), updated_at = datetime('now') WHERE id = ?",
            (tank_id, batch_id))

        conn.execute('COMMIT')
        return None
    except Exception:
        conn.execute('ROLLBACK')
        raise


# advance_batch_status(conn, batch_id, new_status) -> str | None
# NEEDS-BEGIN-IMMEDIATE: validates current status before updating
# Returns: None on success, error message on failure
# Valid transitions: brewing->fermenting, fermenting->conditioning, conditioning->ready
# conditioning->ready also releases the tank (clears tank.current_batch_id and batch.tank_id)
# All business checks are inside BEGIN IMMEDIATE (TOCTOU-safe, FC43)
# Usage: error = advance_batch_status(conn, batch_id, new_status)
def advance_batch_status(conn: sqlite3.Connection, batch_id: int,
                         new_status: str) -> str | None:
    try:
        conn.execute('BEGIN IMMEDIATE')

        batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
        if batch is None:
            conn.execute('ROLLBACK')
            return 'Batch not found'

        current = batch['status']
        if new_status not in VALID_TRANSITIONS.get(current, []):
            conn.execute('ROLLBACK')
            return f'Cannot transition from {current} to {new_status}'

        conn.execute(
            "UPDATE batches SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, batch_id))

        # Release tank when batch reaches 'ready' status
        if new_status == 'ready' and batch['tank_id'] is not None:
            conn.execute(
                "UPDATE tanks SET current_batch_id = NULL, updated_at = datetime('now') WHERE id = ?",
                (batch['tank_id'],))
            conn.execute(
                "UPDATE batches SET tank_id = NULL, updated_at = datetime('now') WHERE id = ?",
                (batch_id,))

        conn.execute('COMMIT')
        return None
    except Exception:
        conn.execute('ROLLBACK')
        raise


# assign_to_tap(conn, batch_id, tap_id) -> str | None
# NEEDS-BEGIN-IMMEDIATE: checks tap availability + batch status
# DERIVED STATE: updates taps.batch_id, batches.status
# Returns: None on success, error message on failure
# All business checks are inside BEGIN IMMEDIATE (TOCTOU-safe, FC43)
# Usage: error = assign_to_tap(conn, batch_id, tap_id)
def assign_to_tap(conn: sqlite3.Connection, batch_id: int,
                  tap_id: int) -> str | None:
    try:
        conn.execute('BEGIN IMMEDIATE')

        batch = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
        if batch is None:
            conn.execute('ROLLBACK')
            return 'Batch not found'
        if batch['status'] != 'ready':
            conn.execute('ROLLBACK')
            return 'Batch must be in ready status to tap'

        tap = conn.execute('SELECT * FROM taps WHERE id = ?', (tap_id,)).fetchone()
        if tap is None:
            conn.execute('ROLLBACK')
            return 'Tap not found'
        if tap['batch_id'] is not None:
            conn.execute('ROLLBACK')
            return 'Tap already has a batch assigned'

        conn.execute(
            "UPDATE taps SET batch_id = ?, updated_at = datetime('now') WHERE id = ?",
            (batch_id, tap_id))
        conn.execute(
            "UPDATE batches SET status = 'tapped', updated_at = datetime('now') WHERE id = ?",
            (batch_id,))

        conn.execute('COMMIT')
        return None
    except Exception:
        conn.execute('ROLLBACK')
        raise


# update_batch(conn, batch_id, name, notes) -> None
# Only updates name and notes -- status changes go through dedicated functions
# SERIAL-SAFE: does NOT call conn.commit() -- caller commits
# Usage: update_batch(conn, batch_id, name, notes)
#        conn.commit()
def update_batch(conn: sqlite3.Connection, batch_id: int, name: str, notes: str) -> None:
    conn.execute(
        "UPDATE batches SET name=?, notes=?, updated_at=datetime('now') WHERE id=?",
        (name, notes, batch_id))


# delete_batch(conn, batch_id) -> None
# SERIAL-SAFE: does NOT call conn.commit() -- caller commits
# Usage: delete_batch(conn, batch_id)
#        conn.commit()
def delete_batch(conn: sqlite3.Connection, batch_id: int) -> None:
    conn.execute('DELETE FROM batches WHERE id = ?', (batch_id,))
