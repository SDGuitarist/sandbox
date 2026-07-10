"""Instrument checkout model — inventory transactions.

Owns the `instrument_checkouts` table. Two class-B writers
(`checkout_instrument`, `return_instrument`) each own exactly ONE
`transaction()` (BEGIN IMMEDIATE) and thread that SAME connection into
`instrument_models.set_instrument_status`, committing as one atomic unit.

Per the Transaction Contracts, these writers NEVER call `audit_models.record`
and NEVER call `conn.commit()` — `transaction()` commits on clean exit and
rolls back on any exception.
"""

from datetime import datetime, timezone

from studio.database import get_db, query, transaction
from studio.models.instrument_models import set_instrument_status


def list_checkouts(student_id=None, status=None):
    """Return checkout rows joined with instrument + student, newest first.

    Optional filters: `student_id`, `status` ('out'|'returned'|'overdue').
    """
    sql = """
        SELECT c.id            AS id,
               c.instrument_id  AS instrument_id,
               c.student_id     AS student_id,
               c.checked_out_at AS checked_out_at,
               c.due_at         AS due_at,
               c.returned_at    AS returned_at,
               c.status         AS status,
               i.name           AS instrument_name,
               i.category       AS instrument_category,
               s.first_name     AS student_first_name,
               s.last_name      AS student_last_name
          FROM instrument_checkouts c
          JOIN instruments i ON i.id = c.instrument_id
          JOIN students    s ON s.id = c.student_id
    """
    clauses = []
    params = []
    if student_id is not None:
        clauses.append("c.student_id = ?")
        params.append(student_id)
    if status is not None:
        clauses.append("c.status = ?")
        params.append(status)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY c.checked_out_at DESC, c.id DESC"
    return query(sql, tuple(params))


def get_checkout(cid):
    """Return one checkout row (joined with instrument + student) or None."""
    sql = """
        SELECT c.id            AS id,
               c.instrument_id  AS instrument_id,
               c.student_id     AS student_id,
               c.checked_out_at AS checked_out_at,
               c.due_at         AS due_at,
               c.returned_at    AS returned_at,
               c.status         AS status,
               i.name           AS instrument_name,
               i.category       AS instrument_category,
               s.first_name     AS student_first_name,
               s.last_name      AS student_last_name
          FROM instrument_checkouts c
          JOIN instruments i ON i.id = c.instrument_id
          JOIN students    s ON s.id = c.student_id
         WHERE c.id = ?
    """
    return query(sql, (cid,), one=True)


def checkout_instrument(instrument_id, student_id, due_at):
    """Atomically check out an available instrument to a student.

    Owns ONE `with transaction() as conn` (BEGIN IMMEDIATE). Inside it, and on
    the SAME connection (TOCTOU-safe):
      1. read the instrument and require `status == 'available'` (else ValueError);
      2. INSERT the checkout row (status 'out');
      3. flip the instrument to 'checked_out' via `set_instrument_status`.
    Any exception rolls back the whole unit. Returns the new checkout id.
    """
    with transaction() as conn:
        instrument = conn.execute(
            "SELECT status FROM instruments WHERE id = ?",
            (instrument_id,),
        ).fetchone()
        if instrument is None or instrument["status"] != "available":
            raise ValueError("instrument unavailable")

        cur = conn.execute(
            """
            INSERT INTO instrument_checkouts (instrument_id, student_id, due_at, status)
            VALUES (?, ?, ?, 'out')
            """,
            (instrument_id, student_id, due_at),
        )
        checkout_id = cur.lastrowid

        set_instrument_status(conn, instrument_id, "checked_out")

        return checkout_id


def return_instrument(checkout_id):
    """Atomically return a checked-out instrument.

    Owns ONE `with transaction() as conn` (BEGIN IMMEDIATE). Requires the
    checkout exists with status 'out' (else ValueError); sets `returned_at`
    (ISO now) + status='returned', and flips the instrument back to 'available'
    via `set_instrument_status` on the SAME connection. One atomic unit.
    """
    with transaction() as conn:
        checkout = conn.execute(
            "SELECT instrument_id, status FROM instrument_checkouts WHERE id = ?",
            (checkout_id,),
        ).fetchone()
        if checkout is None or checkout["status"] != "out":
            raise ValueError("checkout not open")

        returned_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            UPDATE instrument_checkouts
               SET returned_at = ?, status = 'returned'
             WHERE id = ?
            """,
            (returned_at, checkout_id),
        )

        set_instrument_status(conn, checkout["instrument_id"], "available")
