"""Student model — CRUD + ownership-scoped getters for the students table.

Owning agent: student model agent.

Contract (see docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md):
- Single-row getters return ``dict | None`` (plain dict, never sqlite3.Row).
- Listers return ``list[dict]``.
- Creators return the new ``int`` id.
- Mutators return ``None``.
- Every writer here is a class-A writer: it commits internally via its own single
  write and NEVER opens a ``transaction()`` (§5 Transaction Contracts).
- ``get_student_for`` enforces ownership as a SQL WHERE predicate in the query itself,
  never a fetch-then-compare in Python (Ownership-Scoped Getter Contract; run-080 IDOR).
"""

from studio.database import get_db, query

# Fields a client may set via update_student (§ student_models.py — update_student).
_UPDATABLE_FIELDS = ("first_name", "last_name", "email", "phone", "skill_level", "notes")


def list_students(active_only=False, q=None):
    """Return students as a list of dicts.

    ``active_only`` filters to active=1; ``q`` LIKE-matches first/last name or email.
    """
    sql = "SELECT * FROM students"
    clauses = []
    params = []
    if active_only:
        clauses.append("active = 1")
    if q:
        clauses.append(
            "(first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)"
        )
        like = "%" + q + "%"
        params.extend([like, like, like])
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY last_name, first_name"
    return query(sql, tuple(params))


def get_student(sid):
    """Return one student dict (unscoped — staff-only callers), or None."""
    return query("SELECT * FROM students WHERE id = ?", (sid,), one=True)


def get_student_for(sid, actor):
    """Ownership-scoped getter (Ownership-Scoped Getter Contract).

    The students table is the ownership root, so the predicate specializes to:
        WHERE students.id = :sid AND (:staff OR students.user_id = :actor_id)
    where staff = actor role in ('admin', 'instructor'). A non-owner gets 0 rows
    -> None (the route turns that into abort(404); no 403, no existence leak).
    """
    staff = 1 if actor and actor.get("role") in ("admin", "instructor") else 0
    actor_id = actor.get("id") if actor else None
    return query(
        "SELECT * FROM students "
        "WHERE students.id = ? AND (? OR students.user_id = ?)",
        (sid, staff, actor_id),
        one=True,
    )


def create_student(
    first_name,
    last_name,
    email=None,
    phone=None,
    skill_level="beginner",
    user_id=None,
):
    """Insert a student. Commits internally. Returns the new int id."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO students (user_id, first_name, last_name, email, phone, skill_level) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, first_name, last_name, email, phone, skill_level),
    )
    db.commit()
    return cur.lastrowid


def update_student(sid, **fields):
    """Update whitelisted fields on a student. Commits internally. Returns None.

    Whitelist EXACTLY: first_name, last_name, email, phone, skill_level, notes.
    Any other key is ignored.
    """
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE_FIELDS}
    if not updates:
        return None
    columns = list(updates.keys())
    set_clause = ", ".join(col + " = ?" for col in columns)
    params = [updates[col] for col in columns]
    params.append(sid)
    db = get_db()
    db.execute("UPDATE students SET " + set_clause + " WHERE id = ?", tuple(params))
    db.commit()
    return None


def set_student_active(sid, active):
    """Soft (de)activate a student. Commits internally. Returns None."""
    db = get_db()
    db.execute(
        "UPDATE students SET active = ? WHERE id = ?",
        (1 if active else 0, sid),
    )
    db.commit()
    return None
