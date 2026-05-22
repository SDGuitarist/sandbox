import sqlite3


def create_invoice(conn: sqlite3.Connection, member_id: int,
                   amount_cents: int, description: str, due_date: str) -> int:
    cursor = conn.execute(
        "INSERT INTO invoices (member_id, amount_cents, description, due_date) VALUES (?, ?, ?, ?)",
        (member_id, amount_cents, description, due_date))
    conn.commit()
    return cursor.lastrowid


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """SELECT i.*, m.name AS member_name
           FROM invoices i JOIN members m ON i.member_id = m.id
           WHERE i.id = ?""", (invoice_id,)).fetchone()


def get_all_invoices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT i.*, m.name AS member_name
           FROM invoices i JOIN members m ON i.member_id = m.id
           ORDER BY i.billing_date DESC""").fetchall()


def get_invoices_by_member(conn: sqlite3.Connection, member_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM invoices WHERE member_id=? ORDER BY billing_date DESC",
                        (member_id,)).fetchall()


def get_invoices_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT i.*, m.name AS member_name
           FROM invoices i JOIN members m ON i.member_id = m.id
           WHERE i.status = ? ORDER BY i.billing_date DESC""", (status,)).fetchall()


def update_invoice(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, description: str,
                   due_date: str, status: str) -> None:
    conn.execute(
        """UPDATE invoices SET amount_cents=?, description=?, due_date=?,
           status=?, updated_at=datetime('now') WHERE id=?""",
        (amount_cents, description, due_date, status, invoice_id))
    conn.commit()


def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Raises sqlite3.IntegrityError if invoice has payments (ON DELETE RESTRICT)."""
    conn.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
    conn.commit()


def get_pending_invoice_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM invoices WHERE status='pending'").fetchone()
    return row[0]
