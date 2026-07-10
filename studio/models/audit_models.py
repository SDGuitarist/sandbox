"""Cross-cutting audit log model (write-only lib + admin read).

Imported by EVERY mutating route. Two functions only (FC1):

- ``record`` — inserts one ``audit_log`` row and commits (class-A writer). Always
  called by a ROUTE post-commit, never inside a ``transaction()`` block and never by
  a model writer (see spec §5 "Audit is NOT a writer class here").
- ``list_audit`` — admin audit view (routes/dashboard.py ``/audit``); newest first,
  optional ``entity_type`` filter, parameterized LIMIT.

Imports per spec §2 (Cross-Boundary Wiring): ``from studio.database import get_db, query``.
"""

from studio.database import get_db, query


def record(user_id, action, entity_type, entity_id=None, detail=None):
    """Insert one audit_log row and commit.

    Class-A writer: self-contained single write that commits internally. Called by
    every mutating route exactly once, AFTER the model mutation has returned and
    committed — so this insert is always a separate post-commit statement, never
    nested inside a checkout/return/enroll transaction.

    Insert errors are NOT swallowed (FC10): any sqlite3 error propagates to the caller.
    """
    db = get_db()
    db.execute(
        "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, action, entity_type, entity_id, detail),
    )
    db.commit()


def list_audit(entity_type=None, limit=200):
    """Return audit_log rows newest first, optionally filtered by ``entity_type``.

    ``limit`` is bound as a parameter (never string-interpolated). Returns a list of
    plain dicts (FC2 — the ``query`` helper already converts sqlite3.Row → dict).
    """
    sql = "SELECT * FROM audit_log"
    params = []
    if entity_type is not None:
        sql += " WHERE entity_type = ?"
        params.append(entity_type)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    return query(sql, tuple(params))
