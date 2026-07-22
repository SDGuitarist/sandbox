"""Cross-cutting audit log — WRITE-ONLY lib + admin read (shared-services).

``record`` is imported by every mutating route and is the sole writer of
``audit_logs``. ``list_audit`` backs the scaffold-hosted admin ``GET /audit``
view.

Transaction discipline (spec §4 / §5):
- ``record`` is a **class-A** writer: its single ``INSERT`` executes directly on
  the request connection which is opened ``isolation_level=None`` (SQLite
  AUTOCOMMIT), so the row persists **immediately**. It does NOT call
  ``conn.commit()`` (nothing is pending) and NEVER opens ``transaction()``.
- ``record`` is called **post-commit, route-level only** — NEVER inside a
  class-B ``transaction()`` and never by a model writer. This guarantees the
  audit insert can never commit-nest inside the ``create_order`` /
  ``process_return`` atomic units.
"""

from swarmlimit.database import get_db, query


def record(actor_id, action, entity_type, entity_id=None, detail=None) -> None:
    """Insert exactly one ``audit_logs`` row; persists immediately via SQLite
    autocommit (no ``conn.commit()``, no ``transaction()``).

    Class-A. Called post-commit at the route layer only.
    """
    get_db().execute(
        "INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (actor_id, action, entity_type, entity_id, detail),
    )


def list_audit(entity_type=None, limit=200) -> list[dict]:
    """Return audit rows (most recent first) as plain ``dict``s (FC63 — never
    leak ``sqlite3.Row`` across the boundary).

    Optionally filtered by ``entity_type``; capped at ``limit`` rows. Backs the
    scaffold-hosted admin ``GET /audit`` view.
    """
    if entity_type is None:
        rows = query(
            "SELECT id, actor_id, action, entity_type, entity_id, detail, created_at "
            "FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    else:
        rows = query(
            "SELECT id, actor_id, action, entity_type, entity_id, detail, created_at "
            "FROM audit_logs WHERE entity_type = ? ORDER BY id DESC LIMIT ?",
            (entity_type, limit),
        )
    return [dict(row) for row in rows]
