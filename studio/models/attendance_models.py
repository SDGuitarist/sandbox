"""Attendance model functions (attendance model agent).

Attendance is SINGLE-STUDENT per lesson: `lessons.student_id` is NOT NULL, so each
lesson has exactly ONE student. `mark_attendance` derives that student_id from the
lesson and UPSERTs a single row on UNIQUE(lesson_id, student_id) — `student_id` is
NEVER a client-supplied parameter.

Transaction class-A: every writer commits internally; this module never opens a
`transaction()`. Auditing is done by the ROUTE post-commit, never here.
"""

from studio.database import get_db, query


def list_attendance(lesson_id=None, student_id=None):
    """List attendance rows, optionally filtered by lesson and/or student.

    Returns list[dict].
    """
    clauses = []
    params = []
    if lesson_id is not None:
        clauses.append("lesson_id = ?")
        params.append(lesson_id)
    if student_id is not None:
        clauses.append("student_id = ?")
        params.append(student_id)

    sql = "SELECT * FROM attendance"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY marked_at DESC, id DESC"
    return query(sql, tuple(params))


def mark_attendance(lesson_id, present, marked_by):
    """Mark the attendance for a lesson's single student.

    Looks up `lessons.student_id` (raises ValueError if the lesson does not exist),
    then UPSERTs one row on UNIQUE(lesson_id, student_id). Commits internally (class-A).
    Does NOT audit — the route records the audit entry post-commit. Returns None.
    """
    db = get_db()
    lesson = db.execute(
        "SELECT student_id FROM lessons WHERE id = ?", (lesson_id,)
    ).fetchone()
    if lesson is None:
        raise ValueError("lesson does not exist")

    student_id = lesson["student_id"]
    present_val = 1 if present else 0

    db.execute(
        """
        INSERT INTO attendance (lesson_id, student_id, present, marked_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(lesson_id, student_id) DO UPDATE SET
            present = excluded.present,
            marked_by = excluded.marked_by,
            marked_at = datetime('now')
        """,
        (lesson_id, student_id, present_val, marked_by),
    )
    db.commit()


def attendance_rate(student_id):
    """Fraction of a student's attendance rows marked present.

    present count / total rows; returns 0.0 when the student has no rows
    (never divides by zero). Returns float.
    """
    row = query(
        """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(present), 0) AS present_count
        FROM attendance
        WHERE student_id = ?
        """,
        (student_id,),
        one=True,
    )
    total = row["total"] if row else 0
    if not total:
        return 0.0
    return row["present_count"] / total
