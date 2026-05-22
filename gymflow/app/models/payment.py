import sqlite3
from datetime import datetime


def create_payment(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, payment_date: str,
                   payment_method: str, reference_number: str,
                   notes: str) -> int:
    """Create payment. Returns new payment ID.

    Usage:
        payment_id = create_payment(conn, 1, 4999, '2026-05-21',
                                    'card', 'REF-001', '')
        return redirect(url_for('billing.detail', invoice_id=invoice_id))
    Commits: yes (conn.commit())
    """
    cursor = conn.execute(
        """INSERT INTO payments (invoice_id, amount_cents, payment_date,
               payment_method, reference_number, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (invoice_id, amount_cents, payment_date, payment_method,
         reference_number, notes),
    )
    conn.commit()
    return cursor.lastrowid


def get_payment(conn: sqlite3.Connection, payment_id: int) -> sqlite3.Row | None:
    """Get payment by ID."""
    return conn.execute(
        "SELECT * FROM payments WHERE id = ?",
        (payment_id,),
    ).fetchone()


def get_payments_by_invoice(conn: sqlite3.Connection,
                             invoice_id: int) -> list[sqlite3.Row]:
    """Get payments for an invoice. Ordered by payment_date DESC."""
    return conn.execute(
        "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date DESC",
        (invoice_id,),
    ).fetchall()


def get_all_payments(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all payments with invoice description and member_name joined.
    Ordered by payment_date DESC."""
    return conn.execute(
        """SELECT p.*, i.description AS invoice_description,
                  m.name AS member_name
           FROM payments p
           JOIN invoices i ON p.invoice_id = i.id
           JOIN members m ON i.member_id = m.id
           ORDER BY p.payment_date DESC""",
    ).fetchall()


def delete_payment(conn: sqlite3.Connection, payment_id: int) -> None:
    """Delete payment. Commits: yes."""
    conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    conn.commit()


def get_invoice_paid_amount(conn: sqlite3.Connection, invoice_id: int) -> int:
    """Sum of all payment amounts for an invoice. Returns int (cents).

    Usage:
        paid = get_invoice_paid_amount(conn, invoice_id)
        # paid is an int, NOT a Row
    """
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) AS total FROM payments WHERE invoice_id = ?",
        (invoice_id,),
    ).fetchone()
    return row["total"]


def get_revenue_this_month(conn: sqlite3.Connection) -> int:
    """Sum of all payment amounts in current month. Returns int (cents).

    Usage:
        revenue = get_revenue_this_month(conn)
        # revenue is an int, NOT a Row
    """
    now = datetime.now()
    month_start = now.strftime("%Y-%m-01")
    # Last day: use first day of next month
    if now.month == 12:
        next_month_start = f"{now.year + 1}-01-01"
    else:
        next_month_start = f"{now.year}-{now.month + 1:02d}-01"
    row = conn.execute(
        """SELECT COALESCE(SUM(amount_cents), 0) AS total
           FROM payments
           WHERE payment_date >= ? AND payment_date < ?""",
        (month_start, next_month_start),
    ).fetchone()
    return row["total"]
