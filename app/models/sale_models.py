import sqlite3


def get_all_sales(conn: sqlite3.Connection) -> list:
    """Return all sales joined with tap, batch, and recipe info, newest first."""
    return conn.execute('''
        SELECT s.*, t.name as tap_name, b.name as batch_name, r.name as recipe_name
        FROM sales s
        JOIN taps t ON s.tap_id = t.id
        JOIN batches b ON s.batch_id = b.id
        LEFT JOIN recipes r ON b.recipe_id = r.id
        ORDER BY s.created_at DESC
    ''').fetchall()


def get_sale(conn: sqlite3.Connection, sale_id: int):
    """Return a single sale joined with tap and batch info, or None."""
    return conn.execute('''
        SELECT s.*, t.name as tap_name, b.name as batch_name
        FROM sales s
        JOIN taps t ON s.tap_id = t.id
        JOIN batches b ON s.batch_id = b.id
        WHERE s.id = ?
    ''', (sale_id,)).fetchone()


def get_today_sales_total(conn: sqlite3.Connection) -> int:
    """Return total sales in cents for today. Returns 0 if no sales."""
    row = conn.execute(
        "SELECT COALESCE(SUM(price_cents), 0) as total FROM sales WHERE date(created_at) = date('now')"
    ).fetchone()
    return row['total']


def create_sale(conn: sqlite3.Connection, tap_id: int, quantity_oz: float,
                sale_type: str, price_cents: int) -> int | None:
    """Record a sale and update derived state.

    NEEDS-BEGIN-IMMEDIATE: decrements batch remaining_volume_oz.
    DERIVED STATE: updates batches.remaining_volume_oz, batches.status
    (if empty), taps.batch_id (if empty).

    The derived state chain (all 7 steps):
      1. Check tap exists and has batch_id
      2. Re-read batch remaining_volume_oz inside transaction
      3. Check sufficient volume
      4. INSERT sale
      5. Decrement remaining_volume_oz with max(0, ...) float clamping
      6. IF remaining <= 0: SET batch status='empty' AND CLEAR tap.batch_id
      7. COMMIT (or ROLLBACK on any exception)

    Returns: sale ID on success, None if tap invalid or insufficient volume.
    """
    try:
        conn.execute('BEGIN IMMEDIATE')

        # Step 1: Check tap exists and has a batch assigned
        tap = conn.execute(
            'SELECT * FROM taps WHERE id = ?', (tap_id,)
        ).fetchone()
        if tap is None or tap['batch_id'] is None:
            conn.execute('ROLLBACK')
            return None

        batch_id = tap['batch_id']

        # Step 2: Re-read batch remaining_volume_oz inside transaction
        # (authoritative, TOCTOU-safe)
        batch = conn.execute(
            'SELECT * FROM batches WHERE id = ?', (batch_id,)
        ).fetchone()

        # Step 3: Check sufficient volume
        if batch is None or batch['remaining_volume_oz'] < quantity_oz:
            conn.execute('ROLLBACK')
            return None

        # Step 4: INSERT sale
        cur = conn.execute(
            'INSERT INTO sales (tap_id, batch_id, quantity_oz, sale_type, price_cents) VALUES (?, ?, ?, ?, ?)',
            (tap_id, batch_id, quantity_oz, sale_type, price_cents))
        sale_id = cur.lastrowid

        # Step 5: Decrement remaining volume (clamp to 0 for float precision
        # safety)
        new_remaining = max(0, batch['remaining_volume_oz'] - quantity_oz)
        conn.execute(
            "UPDATE batches SET remaining_volume_oz = ?, updated_at = datetime('now') WHERE id = ?",
            (new_remaining, batch_id))

        # Step 6: If batch is now empty, update status and clear tap
        if new_remaining <= 0:
            conn.execute(
                "UPDATE batches SET status = 'empty', updated_at = datetime('now') WHERE id = ?",
                (batch_id,))
            conn.execute(
                "UPDATE taps SET batch_id = NULL, updated_at = datetime('now') WHERE id = ?",
                (tap_id,))

        # Step 7: COMMIT
        conn.execute('COMMIT')
        return sale_id
    except Exception:
        conn.execute('ROLLBACK')
        raise
