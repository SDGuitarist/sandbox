"""Role-scoped announcement model functions.

Class-A writers (commit internally, never open a transaction() — FC29).
Rows are converted to plain dicts before crossing the boundary (FC2).
Audit is written by the route post-commit, never here.
"""

from studio.database import get_db, query

# audience buckets visible to each role, in addition to 'all'.
_ROLE_AUDIENCE = {
    "student": ("all", "students"),
    "instructor": ("all", "instructors"),
}


def list_for_role(role):
    """Return announcements visible to `role`, newest first.

    student    -> audience IN ('all', 'students')
    instructor -> audience IN ('all', 'instructors')
    admin      -> every row, regardless of audience
    """
    audiences = _ROLE_AUDIENCE.get(role)
    if audiences is None:
        # admin (or any non-scoped role) sees all rows.
        return query(
            "SELECT * FROM announcements ORDER BY created_at DESC, id DESC"
        )
    placeholders = ",".join("?" for _ in audiences)
    return query(
        "SELECT * FROM announcements "
        f"WHERE audience IN ({placeholders}) "
        "ORDER BY created_at DESC, id DESC",
        tuple(audiences),
    )


def get_announcement(aid):
    """Return the announcement dict for `aid`, or None."""
    return query(
        "SELECT * FROM announcements WHERE id = ?",
        (aid,),
        one=True,
    )


def create_announcement(author_id, title, body, audience="all"):
    """Insert an announcement and return its new int id. Commits internally."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO announcements (author_id, title, body, audience) "
        "VALUES (?, ?, ?, ?)",
        (author_id, title, body, audience),
    )
    conn.commit()
    return cur.lastrowid


def delete_announcement(aid):
    """Delete the announcement with `aid`. Commits internally. Returns None."""
    conn = get_db()
    conn.execute("DELETE FROM announcements WHERE id = ?", (aid,))
    conn.commit()
