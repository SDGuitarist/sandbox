"""Practice-log model — ownership-scoped getters + student self-service writers.

Ownership-Scoped Getter Contract (UNIFORM across student/lesson/invoice/practice):
the ownership check is a SQL WHERE predicate in the query itself, never a
fetch-then-compare in Python. A non-owner therefore gets 0 rows -> None/[] and the
route does `row = get_practice_log_for(...) or abort(404)`.

Actor roles for practice logs (student-owned entity):
  - admin / instructor -> staff, no ownership restriction (may scope by target_student_id)
  - student            -> restricted to their own rows; target_student_id is IGNORED
"""

from studio.database import get_db, query


def _is_staff(actor):
    """True when the actor is admin or instructor (both are staff over practice logs)."""
    return actor is not None and actor.get("role") in ("admin", "instructor")


def list_practice_logs_for(actor, target_student_id=None):
    """Ownership-scoped list of practice logs (newest first).

    student -> only their own logs; target_student_id is IGNORED (can never widen scope).
    staff   -> all logs, or scoped to target_student_id when supplied.
    """
    if _is_staff(actor):
        if target_student_id is not None:
            return query(
                "SELECT * FROM practice_logs WHERE student_id = :sid "
                "ORDER BY logged_at DESC, id DESC",
                {"sid": target_student_id},
            )
        return query(
            "SELECT * FROM practice_logs ORDER BY logged_at DESC, id DESC"
        )

    # student (or anyone non-staff): scoped to their own student row via SQL predicate.
    return query(
        "SELECT * FROM practice_logs "
        "WHERE student_id = (SELECT id FROM students WHERE user_id = :actor_id) "
        "ORDER BY logged_at DESC, id DESC",
        {"actor_id": (actor or {}).get("id")},
    )


def get_practice_log_for(log_id, actor):
    """Ownership-scoped single-row getter -> dict | None.

    WHERE practice_logs.id = :log_id AND (:staff OR student_id = <actor's student>).
    Non-owner -> None (route aborts 404 before deleting).
    """
    return query(
        "SELECT * FROM practice_logs "
        "WHERE id = :log_id AND (:staff OR "
        "student_id = (SELECT id FROM students WHERE user_id = :actor_id))",
        {
            "log_id": log_id,
            "staff": 1 if _is_staff(actor) else 0,
            "actor_id": (actor or {}).get("id"),
        },
        one=True,
    )


def create_practice_log(student_id, minutes, notes=None):
    """Insert a practice log; commits. Returns the new int id.

    minutes CHECK (> 0) is schema-enforced — an invalid value raises IntegrityError,
    which we let propagate.
    """
    db = get_db()
    cur = db.execute(
        "INSERT INTO practice_logs (student_id, minutes, notes) "
        "VALUES (:student_id, :minutes, :notes)",
        {"student_id": student_id, "minutes": minutes, "notes": notes},
    )
    db.commit()
    return cur.lastrowid


def delete_practice_log(log_id):
    """Delete a practice log by id; commits. Returns None.

    The route guards ownership via get_practice_log_for() BEFORE calling this.
    """
    db = get_db()
    db.execute("DELETE FROM practice_logs WHERE id = :log_id", {"log_id": log_id})
    db.commit()


def total_minutes(student_id, since=None):
    """SUM of practice minutes for a student (0 when none), optionally since a timestamp.

    since -> filter logged_at >= since (e.g. start-of-week for the dashboard aggregate).
    """
    if since is not None:
        row = query(
            "SELECT COALESCE(SUM(minutes), 0) AS total FROM practice_logs "
            "WHERE student_id = :sid AND logged_at >= :since",
            {"sid": student_id, "since": since},
            one=True,
        )
    else:
        row = query(
            "SELECT COALESCE(SUM(minutes), 0) AS total FROM practice_logs "
            "WHERE student_id = :sid",
            {"sid": student_id},
            one=True,
        )
    return row["total"] if row else 0
