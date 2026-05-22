import sqlite3


def create_payment(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, payment_date: str,
                   payment_method: str, reference_number: str, notes: str) -> int:
    cursor = conn.execute(
        "INSERT INTO payments (invoice_id, amount_cents, payment_date, payment_method, reference_number, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (invoice_id, amount_cents, payment_date, payment_method, reference_number, notes))
    conn.commit()
    return cursor.lastrowid


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
    conn.execute("DELETE FROM payments WHERE id=?", (payment_id,))
    conn.commit()


def get_total_paid_for_invoice(conn: sqlite3.Connection, invoice_id: int) -> int:
    row = conn.execute("SELECT COALESCE(SUM(amount_cents), 0) FROM payments WHERE invoice_id=?",
                       (invoice_id,)).fetchone()
    return row[0]


def get_total_revenue_this_month(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM payments WHERE strftime('%Y-%m', payment_date) = strftime('%Y-%m', 'now')"
    ).fetchone()
    return row[0]
