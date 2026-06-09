"""Live-guard: content-based hash of live.db read through SQL.

`live_content_hash` proves live.db is unchanged across a replay by hashing the
*content* of `source_events` via a SQL query (deterministic ORDER BY seq),
NEVER the file bytes. A read-only connection from `open_live_ro` is passed in.
"""

import hashlib
import sqlite3


def live_content_hash(ro_conn: sqlite3.Connection) -> str:
    """Return the 64-char lowercase hex SHA-256 of live.db content.

    Reads every `source_events` row in `seq` (primary key) order and folds the
    column values into a SHA-256 digest. Computed from queried content, not from
    the database file bytes, so it is stable across WAL/checkpoint differences.
    """
    digest = hashlib.sha256()
    cur = ro_conn.execute(
        "SELECT seq, idempotency_key, logical_ts, event_type, payload, source "
        "FROM source_events ORDER BY seq ASC"
    )
    for row in cur:
        for value in (
            row["seq"],
            row["idempotency_key"],
            row["logical_ts"],
            row["event_type"],
            row["payload"],
            row["source"],
        ):
            digest.update(repr(value).encode("utf-8"))
            digest.update(b"\x1f")
        digest.update(b"\x1e")
    return digest.hexdigest()
