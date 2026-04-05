import json

from .db import _now


def append_event(conn, event_type: str, service_id: str = None, payload: dict = None) -> dict:
    """Append an event to the timeline."""
    payload_json = json.dumps(payload or {})
    conn.execute(
        "INSERT INTO events (event_type, service_id, payload, created_at) VALUES (?, ?, ?, ?)",
        (event_type, service_id, payload_json, _now()),
    )
    row = conn.execute(
        "SELECT * FROM events WHERE id = last_insert_rowid()"
    ).fetchone()
    d = dict(row)
    d["payload"] = json.loads(d["payload"])
    return d


def list_events(conn, after_id: int = None, limit: int = 20, service_id: str = None) -> dict:
    """Return paginated events ordered by id ascending.

    Cursor pagination: use id > after_id. next_cursor = events[limit-1]["id"].
    """
    limit = max(1, min(int(limit), 200))

    params = []
    where_clauses = []

    if after_id is not None:
        where_clauses.append("id > ?")
        params.append(after_id)
    if service_id is not None:
        where_clauses.append("service_id = ?")
        params.append(service_id)

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    params.append(limit + 1)  # fetch one extra to detect next page

    rows = conn.execute(
        f"SELECT * FROM events {where} ORDER BY id ASC LIMIT ?",
        params,
    ).fetchall()

    has_more = len(rows) > limit
    page = rows[:limit]

    events = []
    for r in page:
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        events.append(d)

    next_cursor = events[-1]["id"] if has_more and events else None

    return {"events": events, "next_cursor": next_cursor}
