"""Lesson model — the 4-way FK seam (instructor + student + room + course).

Owns the `lessons` table. Provides:
  - unscoped staff getters/listers (list_lessons, get_lesson) with joined names,
  - ownership-scoped getters (list_lessons_for, get_lesson_for) following the
    UNIFORM Ownership-Scoped Getter Contract, extended for the instructor role
    (a lesson has BOTH a student and an instructor owner),
  - CRUD (create_lesson, update_lesson, set_lesson_status),
  - scheduling conflict detection (check_conflicts).

All getters/listers return plain dicts (never sqlite3.Row — FC2). All writers
commit internally (class-A — FC29); none open an explicit transaction().
The ownership check is always a SQL WHERE predicate, never fetch-then-compare.
"""

from studio.database import get_db, query

# Columns a client may update on a lesson (update_lesson whitelist).
# SPEC_ISSUES note: spec §5 update_lesson has no explicit whitelist; taking the
# editable non-id columns of the lessons table per pitfall #5.
_UPDATABLE_FIELDS = (
    "instructor_id",
    "student_id",
    "room_id",
    "course_id",
    "starts_at",
    "ends_at",
    "status",
    "notes",
)

# Shared SELECT that joins the four related names onto each lesson row.
_LESSON_SELECT = """
    SELECT
        lessons.id,
        lessons.course_id,
        lessons.instructor_id,
        lessons.student_id,
        lessons.room_id,
        lessons.starts_at,
        lessons.ends_at,
        lessons.status,
        lessons.notes,
        instructors.first_name || ' ' || instructors.last_name AS instructor_name,
        students.first_name   || ' ' || students.last_name      AS student_name,
        rooms.name    AS room_name,
        courses.name  AS course_name
    FROM lessons
    JOIN instructors ON instructors.id = lessons.instructor_id
    JOIN students    ON students.id    = lessons.student_id
    LEFT JOIN rooms   ON rooms.id   = lessons.room_id
    LEFT JOIN courses ON courses.id = lessons.course_id
"""


def _build_filters(student_id=None, instructor_id=None, room_id=None,
                   date_from=None, date_to=None, status=None):
    """Build the WHERE fragments + params list shared by the lister paths."""
    clauses = []
    params = []
    if student_id is not None:
        clauses.append("lessons.student_id = ?")
        params.append(student_id)
    if instructor_id is not None:
        clauses.append("lessons.instructor_id = ?")
        params.append(instructor_id)
    if room_id is not None:
        clauses.append("lessons.room_id = ?")
        params.append(room_id)
    if date_from is not None:
        clauses.append("lessons.starts_at >= ?")
        params.append(date_from)
    if date_to is not None:
        clauses.append("lessons.starts_at <= ?")
        params.append(date_to)
    if status is not None:
        clauses.append("lessons.status = ?")
        params.append(status)
    return clauses, params


def list_lessons(student_id=None, instructor_id=None, room_id=None,
                 date_from=None, date_to=None, status=None):
    """List lessons (unscoped; staff callers), joining instructor/student/room/course names."""
    clauses, params = _build_filters(
        student_id, instructor_id, room_id, date_from, date_to, status
    )
    sql = _LESSON_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY lessons.starts_at"
    return query(sql, tuple(params))


def list_lessons_for(actor, **filters):
    """Ownership-scoped list (Ownership-Scoped Getter Contract, instructor-extended).

    admin       -> all rows (honoring filters);
    student     -> rows where student_id = (SELECT id FROM students WHERE user_id = actor.id);
    instructor  -> rows where instructor_id = (SELECT id FROM instructors WHERE user_id = actor.id)
                   (an instructor sees ONLY their own lessons — the single asymmetry).
    Predicate is applied IN SQL. Non-owner therefore gets [] naturally.
    """
    clauses, params = _build_filters(
        filters.get("student_id"),
        filters.get("instructor_id"),
        filters.get("room_id"),
        filters.get("date_from"),
        filters.get("date_to"),
        filters.get("status"),
    )

    role = actor.get("role")
    if role == "admin":
        pass  # no ownership restriction
    elif role == "instructor":
        clauses.append(
            "lessons.instructor_id = (SELECT id FROM instructors WHERE user_id = ?)"
        )
        params.append(actor.get("id"))
    else:  # student (or any non-staff role) — scope to own student rows
        clauses.append(
            "lessons.student_id = (SELECT id FROM students WHERE user_id = ?)"
        )
        params.append(actor.get("id"))

    sql = _LESSON_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY lessons.starts_at"
    return query(sql, tuple(params))


def get_lesson(lid):
    """Fetch one lesson with joined names (unscoped; staff callers). None if absent."""
    return query(_LESSON_SELECT + " WHERE lessons.id = ?", (lid,), one=True)


def get_lesson_for(lid, actor):
    """Ownership-scoped single-lesson getter (student OR instructor owner).

    WHERE lessons.id = :lid AND (admin OR student-owned OR instructor-owned),
    the ownership check expressed entirely in SQL. Non-owner -> None.
    """
    role = actor.get("role")
    if role == "admin":
        return query(_LESSON_SELECT + " WHERE lessons.id = ?", (lid,), one=True)

    sql = _LESSON_SELECT + """
        WHERE lessons.id = ?
          AND (
                lessons.student_id    = (SELECT id FROM students    WHERE user_id = ?)
             OR lessons.instructor_id = (SELECT id FROM instructors WHERE user_id = ?)
          )
    """
    return query(sql, (lid, actor.get("id"), actor.get("id")), one=True)


def create_lesson(instructor_id, student_id, starts_at, ends_at,
                  course_id=None, room_id=None, notes=None):
    """Create a lesson. Validates FKs exist + ends_at > starts_at. Commits. Returns new id.

    Raises ValueError on any FK miss or on ends_at <= starts_at.
    """
    if not (ends_at > starts_at):
        raise ValueError("ends_at must be after starts_at")

    db = get_db()

    if db.execute(
        "SELECT 1 FROM instructors WHERE id = ?", (instructor_id,)
    ).fetchone() is None:
        raise ValueError("instructor does not exist")
    if db.execute(
        "SELECT 1 FROM students WHERE id = ?", (student_id,)
    ).fetchone() is None:
        raise ValueError("student does not exist")
    if room_id is not None and db.execute(
        "SELECT 1 FROM rooms WHERE id = ?", (room_id,)
    ).fetchone() is None:
        raise ValueError("room does not exist")
    if course_id is not None and db.execute(
        "SELECT 1 FROM courses WHERE id = ?", (course_id,)
    ).fetchone() is None:
        raise ValueError("course does not exist")

    cur = db.execute(
        """
        INSERT INTO lessons
            (course_id, instructor_id, student_id, room_id, starts_at, ends_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (course_id, instructor_id, student_id, room_id, starts_at, ends_at, notes),
    )
    db.commit()
    return cur.lastrowid


def update_lesson(lid, **fields):
    """Update whitelisted lesson fields. Commits. No-op if no valid fields given."""
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE_FIELDS}
    if not updates:
        return

    assignments = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values())
    params.append(lid)

    db = get_db()
    db.execute(f"UPDATE lessons SET {assignments} WHERE id = ?", tuple(params))
    db.commit()


def set_lesson_status(lid, status):
    """Set a lesson's status. Commits."""
    db = get_db()
    db.execute("UPDATE lessons SET status = ? WHERE id = ?", (status, lid))
    db.commit()


def check_conflicts(instructor_id, room_id, starts_at, ends_at, exclude_lesson_id=None):
    """Return scheduled lessons that overlap [starts_at, ends_at) for this instructor OR room.

    Time-range overlap test: existing.starts_at < ends_at AND existing.ends_at > starts_at.
    Only status='scheduled' lessons count as conflicts. Read-only; returns list[dict].
    room_id is optional (None -> room is not considered a conflict source).
    """
    clauses = [
        "lessons.status = 'scheduled'",
        "lessons.starts_at < ?",
        "lessons.ends_at > ?",
    ]
    params = [ends_at, starts_at]

    if room_id is not None:
        clauses.append("(lessons.instructor_id = ? OR lessons.room_id = ?)")
        params.extend([instructor_id, room_id])
    else:
        clauses.append("lessons.instructor_id = ?")
        params.append(instructor_id)

    if exclude_lesson_id is not None:
        clauses.append("lessons.id != ?")
        params.append(exclude_lesson_id)

    sql = _LESSON_SELECT + " WHERE " + " AND ".join(clauses) + " ORDER BY lessons.starts_at"
    return query(sql, tuple(params))
