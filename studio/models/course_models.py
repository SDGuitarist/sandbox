"""Course model functions (course model agent).

Curriculum CRUD plus the enroll-time capacity helper. Per the shared spec:

- All writers here are Transaction class-(A): they commit internally and NEVER
  open an explicit ``transaction()`` (a class-B writer never nests another writer).
- ``get_course`` and ``count_enrolled`` are READ helpers. They are also called by
  ``enrollment_models.enroll`` INSIDE its BEGIN IMMEDIATE transaction on the same
  per-request ``g``-cached connection, so they use the plain shared ``get_db()`` /
  ``query()`` connection (which automatically sees the transaction's own
  uncommitted writes). They never open a new connection and never commit.
- Every function returns plain dicts / ints — never a raw ``sqlite3.Row`` (FC2).
"""

from studio.database import get_db, query

# Whitelist of columns update_course may set (spec Model Functions + pitfall #4).
_UPDATE_FIELDS = (
    "name",
    "description",
    "instructor_id",
    "level",
    "capacity",
    "price_cents",
)


def list_courses(active_only=False, instructor_id=None):
    """Return courses (each a dict) joined with the instructor's display name.

    ``active_only`` restricts to ``active = 1``; ``instructor_id`` restricts to a
    single instructor. Returns ``list[dict]``.
    """
    sql = (
        "SELECT c.*, "
        "(i.first_name || ' ' || i.last_name) AS instructor_name "
        "FROM courses c "
        "LEFT JOIN instructors i ON i.id = c.instructor_id"
    )
    clauses = []
    params = []
    if active_only:
        clauses.append("c.active = 1")
    if instructor_id is not None:
        clauses.append("c.instructor_id = ?")
        params.append(instructor_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY c.name"
    return query(sql, tuple(params))


def get_course(cid):
    """Return the course row as a dict, or ``None`` if absent.

    Reads on the shared request connection so an in-transaction caller (enroll)
    sees uncommitted state. Never commits.
    """
    return query("SELECT * FROM courses WHERE id = ?", (cid,), one=True)


def create_course(
    name,
    description=None,
    instructor_id=None,
    level="beginner",
    capacity=10,
    price_cents=0,
):
    """Insert a course and return its new integer id. Commits internally."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO courses "
        "(name, description, instructor_id, level, capacity, price_cents) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (name, description, instructor_id, level, capacity, price_cents),
    )
    db.commit()
    return cur.lastrowid


def update_course(cid, **fields):
    """Update whitelisted columns on a course. Commits internally.

    Only the columns in ``_UPDATE_FIELDS`` are honored; any other key is ignored.
    """
    updates = {k: v for k, v in fields.items() if k in _UPDATE_FIELDS}
    if not updates:
        return
    assignments = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values())
    params.append(cid)
    db = get_db()
    db.execute(f"UPDATE courses SET {assignments} WHERE id = ?", params)
    db.commit()


def set_course_active(cid, active):
    """Soft (de)activate a course. Commits internally."""
    db = get_db()
    db.execute(
        "UPDATE courses SET active = ? WHERE id = ?",
        (1 if active else 0, cid),
    )
    db.commit()


def count_enrolled(cid):
    """Return the count of ``active`` enrollments for a course as an ``int``.

    Capacity-check helper. Reads on the shared request connection so an
    in-transaction caller (enroll) sees its own uncommitted inserts. Never commits.
    """
    row = query(
        "SELECT COUNT(*) AS n FROM enrollments "
        "WHERE course_id = ? AND status = 'active'",
        (cid,),
        one=True,
    )
    return row["n"] if row else 0
