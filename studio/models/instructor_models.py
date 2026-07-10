"""Instructor model — CRUD over the `instructors` table.

Contract (see docs/plans/2026-07-09-feat-lesson-studio-scale-validation-plan.md):
  - Single-row getter returns `dict | None`; lister returns `list[dict]`;
    creator returns the new `int` id; mutators return `None` (FC2).
  - Every writer here is a class-(A) writer: it commits internally and NEVER
    opens an explicit `transaction()` (FC29).
  - Money is integer cents (`hourly_rate_cents`), never float (FC4).
"""

from studio.database import get_db, query

# Fields a client may set via update_instructor. `active` is toggled ONLY through
# set_instrument_active-style `set_instructor_active`; `id`/`user_id`/`created_at`
# are never client-editable.
_UPDATABLE_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "phone",
    "bio",
    "hourly_rate_cents",
)


def list_instructors(active_only=False):
    """Return all instructors as a list[dict], newest last (by id).

    When `active_only` is truthy, restrict to rows with active = 1.
    """
    if active_only:
        return query(
            "SELECT * FROM instructors WHERE active = 1 ORDER BY id",
        )
    return query("SELECT * FROM instructors ORDER BY id")


def get_instructor(iid):
    """Return the instructor row as a dict, or None if it does not exist."""
    return query(
        "SELECT * FROM instructors WHERE id = ?",
        (iid,),
        one=True,
    )


def create_instructor(
    first_name,
    last_name,
    email=None,
    phone=None,
    bio=None,
    hourly_rate_cents=0,
    user_id=None,
):
    """Insert a new instructor and return its new int id. Commits internally."""
    db = get_db()
    cur = db.execute(
        """
        INSERT INTO instructors
            (user_id, first_name, last_name, email, phone, bio, hourly_rate_cents)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, first_name, last_name, email, phone, bio, hourly_rate_cents),
    )
    db.commit()
    return cur.lastrowid


def update_instructor(iid, **fields):
    """Update whitelisted editable fields on an instructor. Commits internally.

    Only fields in `_UPDATABLE_FIELDS` are applied; unknown keys are ignored.
    A no-op (no recognized fields) makes no DB write.
    """
    updates = {k: v for k, v in fields.items() if k in _UPDATABLE_FIELDS}
    if not updates:
        return
    columns = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values())
    params.append(iid)
    db = get_db()
    db.execute(f"UPDATE instructors SET {columns} WHERE id = ?", params)
    db.commit()


def set_instructor_active(iid, active):
    """Soft (de)activate an instructor by setting active = 0/1. Commits internally."""
    db = get_db()
    db.execute(
        "UPDATE instructors SET active = ? WHERE id = ?",
        (1 if active else 0, iid),
    )
    db.commit()
