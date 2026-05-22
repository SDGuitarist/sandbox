import sqlite3


def create_invoice(conn: sqlite3.Connection, member_id: int,
                   amount_cents: int, description: str,
                   due_date: str) -> int:
    """Create invoice. Returns new invoice ID.

    Usage:
        invoice_id = create_invoice(conn, 1, 4999, 'Monthly membership - June', '2026-06-01')
        return redirect(url_for('billing.detail', invoice_id=invoice_id))
    Commits: yes (autocommit via isolation_level=None).
    """
    cursor = conn.execute(
        """INSERT INTO invoices (member_id, amount_cents, description, due_date)
           VALUES (?, ?, ?, ?)""",
        (member_id, amount_cents, description, due_date),
    )
    return cursor.lastrowid


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> sqlite3.Row | None:
    """Get invoice by ID with member_name joined.

    Returns Row with: id, member_id, amount_cents, description, billing_date,
    due_date, status, created_at, updated_at, member_name.
    """
    return conn.execute(
        """SELECT i.id, i.member_id, i.amount_cents, i.description,
                  i.billing_date, i.due_date, i.status,
                  i.created_at, i.updated_at,
                  m.name AS member_name
           FROM invoices i
           JOIN members m ON m.id = i.member_id
           WHERE i.id = ?""",
        (invoice_id,),
    ).fetchone()


def get_invoices_by_member(conn: sqlite3.Connection, member_id: int) -> list[sqlite3.Row]:
    """Get invoices for a member. Ordered by billing_date DESC."""
    return conn.execute(
        """SELECT id, member_id, amount_cents, description,
                  billing_date, due_date, status,
                  created_at, updated_at
           FROM invoices
           WHERE member_id = ?
           ORDER BY billing_date DESC""",
        (member_id,),
    ).fetchall()


def get_all_invoices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Get all invoices with member_name. Ordered by billing_date DESC."""
    return conn.execute(
        """SELECT i.id, i.member_id, i.amount_cents, i.description,
                  i.billing_date, i.due_date, i.status,
                  i.created_at, i.updated_at,
                  m.name AS member_name
           FROM invoices i
           JOIN members m ON m.id = i.member_id
           ORDER BY i.billing_date DESC""",
    ).fetchall()


def get_invoices_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    """Get invoices filtered by status. Includes member_name."""
    return conn.execute(
        """SELECT i.id, i.member_id, i.amount_cents, i.description,
                  i.billing_date, i.due_date, i.status,
                  i.created_at, i.updated_at,
                  m.name AS member_name
           FROM invoices i
           JOIN members m ON m.id = i.member_id
           WHERE i.status = ?
           ORDER BY i.billing_date DESC""",
        (status,),
    ).fetchall()


def update_invoice(conn: sqlite3.Connection, invoice_id: int,
                   amount_cents: int, description: str, due_date: str,
                   status: str) -> None:
    """Update invoice. Commits: yes (autocommit via isolation_level=None)."""
    conn.execute(
        """UPDATE invoices
           SET amount_cents = ?, description = ?, due_date = ?, status = ?,
               updated_at = datetime('now')
           WHERE id = ?""",
        (amount_cents, description, due_date, status, invoice_id),
    )


def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Delete invoice. Commits: yes (autocommit via isolation_level=None).

    Raises sqlite3.IntegrityError if payments exist for this invoice
    (FK RESTRICT on payments table).
    """
    conn.execute(
        "DELETE FROM invoices WHERE id = ?",
        (invoice_id,),
    )
