"""Room model — CRUD over the `rooms` table.

Rooms are a facilities record consumed by lesson scheduling (FK seam) and
managed through the scaffold-hosted /rooms routes. All writers here are
Transaction-Contract class (A): they commit internally and never open an
explicit `transaction()` (per §5 of the shared spec).

Return conventions (FC2):
- listers  -> list[dict]
- getters  -> dict | None
- creators -> int (new row id)
- mutators -> None
"""

from studio.database import get_db, query


def list_rooms(active_only=False):
    """Return all rooms as a list of dicts, ordered by name.

    When `active_only` is True, only rooms with active == 1 are returned.
    """
    if active_only:
        return query(
            "SELECT * FROM rooms WHERE active = 1 ORDER BY name",
        )
    return query("SELECT * FROM rooms ORDER BY name")


def get_room(rid):
    """Return the room with id == rid as a dict, or None if absent."""
    return query("SELECT * FROM rooms WHERE id = ?", (rid,), one=True)


def create_room(name, capacity=1, location=None):
    """Insert a new room and return its integer id. Commits internally."""
    db = get_db()
    cur = db.execute(
        "INSERT INTO rooms (name, capacity, location) VALUES (?, ?, ?)",
        (name, capacity, location),
    )
    db.commit()
    return cur.lastrowid


def update_room(rid, **fields):
    """Update whitelisted editable fields on a room. Commits internally.

    Whitelist: name, capacity, location. Unknown fields are ignored.
    No-op (no fields) returns without touching the DB.
    """
    allowed = ("name", "capacity", "location")
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    columns = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values())
    params.append(rid)
    db = get_db()
    db.execute(f"UPDATE rooms SET {columns} WHERE id = ?", params)
    db.commit()


def set_room_active(rid, active):
    """Soft-toggle a room's active flag (1/0). Commits internally."""
    db = get_db()
    db.execute(
        "UPDATE rooms SET active = ? WHERE id = ?",
        (1 if active else 0, rid),
    )
    db.commit()
