import sqlite3


def create_payment(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, payment_date: str,
                   payment_method: str, reference_number: str,
                   notes: str) -> int | None:
    """Create payment. Returns payment ID, or None if overpayment rejected.
    Commits: yes (BEGIN IMMEDIATE / COMMIT).
    Auto-updates invoice status to 'paid' when fully paid."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        # Overpayment check INSIDE the transaction (TOCTOU-safe)
        total_paid = get_total_paid_for_invoice(conn, invoice_id)
        invoice = conn.execute(
            "SELECT amount_cents, status FROM invoices WHERE id=?",
            (invoice_id,)).fetchone()
        if invoice is None:
            conn.execute('ROLLBACK')
            return None
        remaining = invoice['amount_cents'] - total_paid
        if amount_cents > remaining:
            conn.execute('ROLLBACK')
            return None
        # Insert the payment
        cursor = conn.execute(
            "INSERT INTO payments (invoice_id, amount_cents, payment_date, "
            "payment_method, reference_number, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (invoice_id, amount_cents, payment_date,
             payment_method, reference_number, notes))
        payment_id = cursor.lastrowid
        # Auto-update invoice status if fully paid (skip cancelled invoices)
        new_total = total_paid + amount_cents
        if new_total >= invoice['amount_cents'] and invoice['status'] != 'cancelled':
            conn.execute(
                "UPDATE invoices SET status='paid', updated_at=datetime('now') "
                "WHERE id=?", (invoice_id,))
        # conn.execute('COMMIT') not conn.commit() because isolation_level=None
        # (autocommit mode -- conn.commit() is a no-op)
        conn.execute('COMMIT')
        return payment_id
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_payment(conn: sqlite3.Connection, payment_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT p.*, i.description AS invoice_description, m.name AS member_name
           FROM payments p
           JOIN invoices i ON p.invoice_id = i.id
           JOIN members m ON i.member_id = m.id
           WHERE p.id = ?""", (payment_id,)).fetchone()


def get_all_payments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT p.*, i.description AS invoice_description, m.name AS member_name
           FROM payments p
           JOIN invoices i ON p.invoice_id = i.id
           JOIN members m ON i.member_id = m.id
           ORDER BY p.payment_date DESC""").fetchall()


def get_payments_by_invoice(conn: sqlite3.Connection, invoice_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM payments WHERE invoice_id=? ORDER BY payment_date DESC",
                        (invoice_id,)).fetchall()


def delete_payment(conn: sqlite3.Connection, payment_id: int) -> None:
    """Delete payment. Reverts invoice to 'pending' if it was auto-set to 'paid'.
    Commits: yes (BEGIN IMMEDIATE / COMMIT)."""
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            "SELECT invoice_id FROM payments WHERE id=?",
            (payment_id,)).fetchone()
        if row is None:
            conn.execute('ROLLBACK')
            return
        invoice_id = row['invoice_id']
        conn.execute("DELETE FROM payments WHERE id=?", (payment_id,))
        # Only revert status if it was auto-set to 'paid'
        invoice = conn.execute(
            "SELECT amount_cents, status FROM invoices WHERE id=?",
            (invoice_id,)).fetchone()
        if invoice is not None and invoice['status'] == 'paid':
            new_total = get_total_paid_for_invoice(conn, invoice_id)
            if new_total < invoice['amount_cents']:
                conn.execute(
                    "UPDATE invoices SET status='pending', "
                    "updated_at=datetime('now') WHERE id=?",
                    (invoice_id,))
        conn.execute('COMMIT')
    except Exception:
        conn.execute('ROLLBACK')
        raise


def get_total_paid_for_invoice(conn: sqlite3.Connection, invoice_id: int) -> int:
    row = conn.execute("SELECT COALESCE(SUM(amount_cents), 0) FROM payments WHERE invoice_id=?",
                       (invoice_id,)).fetchone()
    return row[0]


def get_total_revenue_this_month(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM payments WHERE strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now')"
    ).fetchone()
    return row[0]
