"""Cross-entity search model (search agent).

Covers ONLY students, instructors, and courses. It deliberately does NOT search
lessons, attendance, invoices, or practice logs -- those are per-student private
records whose cross-student exposure a keyword search could leak (Codex scope
boundary). Accordingly this module imports ONLY studio.database and never any
lesson/attendance/invoice/practice model.

Role filtering (Authorization Matrix / §6, /search):
  - staff (admin, instructor) see all matches across the three entities;
  - a student sees only THEMSELVES in student results (matched on their own
    students.id) plus the public active-course catalog. Instructor results are
    empty for a student (a student sees "only self + the public course catalog").
"""

from studio.database import query


def _like(term):
    """Build an escaped LIKE pattern.

    Escapes the LIKE metacharacters (%, _, and the escape char itself) so a user
    query is always treated as a literal substring -- never interpolated into SQL
    (the term is still passed as a bound parameter; only wildcards are neutralized).
    The paired SQL uses ESCAPE '\\'.
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def search_all(q, role, actor_student_id=None):
    """Cross-entity keyword search over students, instructors, and courses.

    Args:
        q: raw search string (may be empty).
        role: the actor's role ('admin' | 'instructor' | 'student').
        actor_student_id: the students.id of a student actor (None for staff).

    Returns:
        dict with three lists of plain dicts:
        {'students': [...], 'instructors': [...], 'courses': [...]}.
        Empty query -> all three lists empty (no error).
    """
    result = {"students": [], "instructors": [], "courses": []}

    if q is None:
        return result
    term = q.strip()
    if not term:
        return result

    pattern = _like(term)
    is_staff = role in ("admin", "instructor")

    # ---- students ----
    if is_staff:
        result["students"] = query(
            "SELECT id, first_name, last_name, email, skill_level, active "
            "FROM students "
            "WHERE (first_name LIKE ? ESCAPE '\\' "
            "   OR last_name LIKE ? ESCAPE '\\' "
            "   OR email LIKE ? ESCAPE '\\') "
            "ORDER BY last_name, first_name",
            (pattern, pattern, pattern),
        )
    elif actor_student_id is not None:
        # A student sees only THEMSELVES, and only when they match the query.
        result["students"] = query(
            "SELECT id, first_name, last_name, email, skill_level, active "
            "FROM students "
            "WHERE id = ? "
            "  AND (first_name LIKE ? ESCAPE '\\' "
            "    OR last_name LIKE ? ESCAPE '\\' "
            "    OR email LIKE ? ESCAPE '\\') "
            "ORDER BY last_name, first_name",
            (actor_student_id, pattern, pattern, pattern),
        )

    # ---- instructors ----
    # Staff only. A student sees only self + the public course catalog, so a
    # student's instructor results are empty (simplest faithful reading of §6;
    # see SPEC_ISSUES).
    if is_staff:
        result["instructors"] = query(
            "SELECT id, first_name, last_name, email, active "
            "FROM instructors "
            "WHERE (first_name LIKE ? ESCAPE '\\' "
            "   OR last_name LIKE ? ESCAPE '\\' "
            "   OR email LIKE ? ESCAPE '\\') "
            "ORDER BY last_name, first_name",
            (pattern, pattern, pattern),
        )

    # ---- courses ----
    # The course catalog is public. Staff see every matching course; a student
    # sees the public catalog scoped to active courses only.
    if is_staff:
        result["courses"] = query(
            "SELECT id, name, description, level, price_cents, active "
            "FROM courses "
            "WHERE (name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\') "
            "ORDER BY name",
            (pattern, pattern),
        )
    else:
        result["courses"] = query(
            "SELECT id, name, description, level, price_cents, active "
            "FROM courses "
            "WHERE active = 1 "
            "  AND (name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\') "
            "ORDER BY name",
            (pattern, pattern),
        )

    return result
