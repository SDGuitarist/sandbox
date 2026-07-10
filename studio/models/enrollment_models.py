"""Enrollment model — CRUD plus the atomic enroll→invoice transaction (class-B).

`enroll` is one of the two hardest seams in the build: it owns a single
`transaction()` (BEGIN IMMEDIATE) and threads that same connection through the
invoice in-tx helpers so an enrollment and its billing item commit — or roll
back — as one unit. All guards run INSIDE the transaction to be TOCTOU-safe.

Imports per spec §2 only:
- `from studio.database import get_db, query, transaction`
- `from studio.models.course_models import get_course, count_enrolled`
- `from studio.models.invoice_models import add_item_in_tx, get_or_create_draft_invoice_in_tx`
"""

import sqlite3

from studio.database import get_db, query, transaction
from studio.models.course_models import get_course, count_enrolled
from studio.models.invoice_models import (
    add_item_in_tx,
    get_or_create_draft_invoice_in_tx,
)


def list_enrollments(student_id=None, course_id=None, status=None):
    """List enrollments joined with student + course names (list[dict])."""
    sql = """
        SELECT e.id,
               e.student_id,
               e.course_id,
               e.status,
               e.enrolled_at,
               s.first_name || ' ' || s.last_name AS student_name,
               c.name                             AS course_name
        FROM enrollments e
        JOIN students s ON s.id = e.student_id
        JOIN courses  c ON c.id = e.course_id
        WHERE 1 = 1
    """
    params = []
    if student_id is not None:
        sql += " AND e.student_id = ?"
        params.append(student_id)
    if course_id is not None:
        sql += " AND e.course_id = ?"
        params.append(course_id)
    if status is not None:
        sql += " AND e.status = ?"
        params.append(status)
    sql += " ORDER BY e.enrolled_at DESC, e.id DESC"
    return query(sql, tuple(params))


def get_enrollment(eid):
    """Single enrollment joined with student + course names (dict | None)."""
    sql = """
        SELECT e.id,
               e.student_id,
               e.course_id,
               e.status,
               e.enrolled_at,
               s.first_name || ' ' || s.last_name AS student_name,
               c.name                             AS course_name
        FROM enrollments e
        JOIN students s ON s.id = e.student_id
        JOIN courses  c ON c.id = e.course_id
        WHERE e.id = ?
    """
    return query(sql, (eid,), one=True)


def enroll(student_id, course_id, created_by):
    """Atomically enroll a student in a course (class-B transaction owner).

    Owns exactly ONE `transaction()` (BEGIN IMMEDIATE). All guards run inside it
    so concurrent class-B writers serialize and re-read current state:
      1. re-read the course on `conn`; require it exists AND active == 1
         (else ValueError('course inactive'));
      2. capacity: count_enrolled(course_id) < course['capacity']
         (else ValueError('course full'));
      3. INSERT the enrollment, relying on UNIQUE(student_id, course_id);
         an IntegrityError → ValueError('already enrolled').
    If the course is priced (price_cents > 0), reuse/create the student's single
    draft invoice and add a matching item — threading the SAME conn. Any
    exception propagates and `transaction()` rolls back the whole unit.

    Returns the new enrollment id (int). Does NOT audit (the route audits
    post-commit). Does NOT call conn.commit() (transaction() commits on clean
    exit).
    """
    with transaction() as conn:
        # (1) in-tx active/existence guard — a concurrent deactivation can't slip through.
        course = get_course(course_id)
        if course is None or course["active"] != 1:
            raise ValueError("course inactive")

        # (2) in-tx capacity guard — count_enrolled reads the same conn.
        if count_enrolled(course_id) >= course["capacity"]:
            raise ValueError("course full")

        # (3) insert; the DB UNIQUE(student_id, course_id) is the authoritative
        # already-enrolled guard.
        try:
            cur = conn.execute(
                "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
                (student_id, course_id),
            )
        except sqlite3.IntegrityError:
            raise ValueError("already enrolled")
        enrollment_id = cur.lastrowid

        # Priced course → accrete an item onto the student's single draft invoice.
        if course["price_cents"] > 0:
            invoice_id = get_or_create_draft_invoice_in_tx(conn, student_id, created_by)
            add_item_in_tx(
                conn,
                invoice_id,
                description=course["name"],
                amount_cents=course["price_cents"],
                source_type="enrollment",
                source_id=enrollment_id,
            )

        return enrollment_id


def set_enrollment_status(eid, status):
    """Set an enrollment's status (class-A; commits internally). Returns None."""
    if status not in ("active", "completed", "withdrawn"):
        raise ValueError("invalid status")
    db = get_db()
    db.execute("UPDATE enrollments SET status = ? WHERE id = ?", (status, eid))
    db.commit()
