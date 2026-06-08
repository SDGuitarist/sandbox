import json

from app.anomaly_models import record_anomaly


def _canonicalize(payload: str) -> str:
    """Re-serialise a JSON payload with sorted keys and compact separators.

    Idempotent: already-canonical payloads round-trip unchanged. Called in the
    dedup comparison path so the order-insensitivity guarantee holds even if the
    caller has not pre-canonicalized (§8.9 spec requirement).
    """
    try:
        return json.dumps(
            json.loads(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (ValueError, TypeError):
        return payload


def append_event(conn, idempotency_key, logical_ts, event_type, payload_canonical, source):
    cur = conn.execute(
        "INSERT OR IGNORE INTO events "
        "(idempotency_key, logical_ts, event_type, payload, source) "
        "VALUES (:idempotency_key, :logical_ts, :event_type, :payload, :source)",
        {
            "idempotency_key": idempotency_key,
            "logical_ts": logical_ts,
            "event_type": event_type,
            "payload": payload_canonical,
            "source": source,
        },
    )
    if cur.rowcount == 1:
        return cur.lastrowid

    existing = conn.execute(
        "SELECT event_id, payload FROM events WHERE idempotency_key = :idempotency_key",
        {"idempotency_key": idempotency_key},
    ).fetchone()

    if _canonicalize(existing["payload"]) == _canonicalize(payload_canonical):
        conn.execute(
            "INSERT INTO dedup_counters (kind, count) VALUES ('dup_exact', 1) "
            "ON CONFLICT(kind) DO UPDATE SET count = count + 1"
        )
    else:
        conn.execute(
            "INSERT INTO dedup_counters (kind, count) VALUES ('dup_conflict', 1) "
            "ON CONFLICT(kind) DO UPDATE SET count = count + 1"
        )
        record_anomaly(conn, None, "dup_conflict", idempotency_key, "duplicate key with differing payload")

    return existing["event_id"]


def get_events(conn):
    return conn.execute(
        "SELECT event_id, idempotency_key, logical_ts, event_type, payload, source, appended_at "
        "FROM events ORDER BY event_id"
    ).fetchall()


def events_at_time(conn, t):
    return conn.execute(
        "SELECT event_id, idempotency_key, logical_ts, event_type, payload, source, appended_at "
        "FROM events WHERE logical_ts <= :t ORDER BY event_id",
        {"t": t},
    ).fetchall()
