import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = "audit_log.db"
SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"


def _normalize_ts(dt=None):
    """Return current UTC time as 'YYYY-MM-DD HH:MM:SS'."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def get_db(path=None, immediate=False):
    db_path = path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path=None):
    db_path = path or DB_PATH
    schema = SCHEMA_PATH.read_text()
    with get_db(path=db_path) as conn:
        conn.executescript(schema)


def append_event(entity_id, entity_type, event_type, payload_dict, actor=None, db_path=None):
    """Append an event and upsert the projection atomically.

    payload_dict is shallow-merged onto the existing projection state (patch semantics).
    Callers must pass partial-update payloads — this service does NOT support full-snapshot
    replacement. Each key in payload_dict overwrites the same key in the stored state.
    Returns the newly inserted event as a dict.
    """
    now = _normalize_ts()
    payload_json = json.dumps(payload_dict)

    with get_db(path=db_path, immediate=True) as conn:
        cursor = conn.execute(
            """
            INSERT INTO events (entity_id, entity_type, event_type, payload, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entity_id, entity_type, event_type, payload_json, actor, now),
        )
        event_id = cursor.lastrowid

        row = conn.execute(
            "SELECT state, version FROM projections WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()

        if row:
            current_state = json.loads(row["state"])
            new_version = row["version"] + 1
        else:
            current_state = {}
            new_version = 1

        # Shallow merge: new payload keys overwrite existing keys (patch semantics)
        current_state.update(payload_dict)
        new_state_json = json.dumps(current_state)

        conn.execute(
            """
            INSERT INTO projections (entity_id, entity_type, state, version, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entity_id) DO UPDATE SET
                entity_type = excluded.entity_type,
                state       = excluded.state,
                version     = excluded.version,
                updated_at  = excluded.updated_at
            """,
            (entity_id, entity_type, new_state_json, new_version, now),
        )

        event_row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        return dict(event_row)


def get_projection(entity_id, db_path=None):
    """Return the materialized projection for an entity, or None if not found."""
    with get_db(path=db_path) as conn:
        row = conn.execute(
            "SELECT * FROM projections WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["state"] = json.loads(result["state"])
        return result


def get_events(
    entity_id=None,
    entity_type=None,
    event_type=None,
    after_id=None,
    before=None,
    since=None,
    limit=50,
    db_path=None,
):
    """Query events with optional filters and cursor pagination.

    Returns (list_of_event_dicts, next_cursor_or_None).
    Timestamps (since/before) must be 'YYYY-MM-DD HH:MM:SS'.
    """
    limit = max(1, min(int(limit), 200))
    clauses = []
    params = []

    if entity_id is not None:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    if entity_type is not None:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if event_type is not None:
        clauses.append("event_type = ?")
        params.append(event_type)
    if after_id is not None:
        clauses.append("id > ?")
        params.append(int(after_id))
    if since is not None:
        clauses.append("created_at >= ?")
        params.append(since)
    if before is not None:
        clauses.append("created_at <= ?")
        params.append(before)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    # Fetch limit+1 to detect if there are more results
    sql = f"SELECT * FROM events {where} ORDER BY id ASC LIMIT ?"
    params.append(limit + 1)

    with get_db(path=db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    events = [dict(r) for r in rows]
    for e in events:
        e["payload"] = json.loads(e["payload"])

    if len(events) > limit:
        # events[limit-1] is the last row of the current page — use its id as cursor
        # Next call uses id > cursor, which correctly starts at events[limit]
        next_cursor = events[limit - 1]["id"]
        events = events[:limit]
    else:
        next_cursor = None

    return events, next_cursor
