"""Dedup + classification tests (frozen #1, §8.9).

Covers: monotonic event_id assignment, dedup_counters increments
(dup_exact / dup_conflict), the dup_conflict anomaly row, and
canonical-payload order-insensitivity (same logical payload, different key
order -> dup_exact, never dup_conflict).
"""
from app.event_models import append_event


_TS = "2026-06-15 19:00:00"


def _counter(conn, kind: str) -> int:
    row = conn.execute(
        "SELECT count FROM dedup_counters WHERE kind = ?", (kind,)
    ).fetchone()
    return 0 if row is None else row["count"]


def _anomalies(conn, kind: str) -> list:
    return conn.execute(
        "SELECT * FROM anomalies WHERE kind = ?", (kind,)
    ).fetchall()


def test_unique_events_get_monotonic_event_id(shadow_conn):
    eid1 = append_event(
        shadow_conn, "k1", _TS, "system.heartbeat", '{"station_id":"S1"}', "gen"
    )
    eid2 = append_event(
        shadow_conn, "k2", _TS, "system.heartbeat", '{"station_id":"S2"}', "gen"
    )
    eid3 = append_event(
        shadow_conn, "k3", _TS, "system.heartbeat", '{"station_id":"S3"}', "gen"
    )
    assert eid1 < eid2 < eid3, "event_id must be strictly monotonic"
    rows = shadow_conn.execute(
        "SELECT event_id FROM events ORDER BY event_id"
    ).fetchall()
    ids = [r["event_id"] for r in rows]
    assert ids == sorted(ids)
    assert len(ids) == 3, "only the unique events should be appended"


def test_duplicate_exact_payload_increments_dup_exact_no_anomaly(shadow_conn):
    eid = append_event(
        shadow_conn, "dup-k", _TS, "system.heartbeat", '{"station_id":"S1"}', "gen"
    )
    again = append_event(
        shadow_conn, "dup-k", _TS, "system.heartbeat", '{"station_id":"S1"}', "gen"
    )
    # returns the existing event_id in all paths
    assert again == eid
    # only one physical row exists
    cnt = shadow_conn.execute(
        "SELECT COUNT(*) AS c FROM events WHERE idempotency_key = ?", ("dup-k",)
    ).fetchone()["c"]
    assert cnt == 1
    assert _counter(shadow_conn, "dup_exact") == 1
    assert _counter(shadow_conn, "dup_conflict") == 0
    assert _anomalies(shadow_conn, "dup_conflict") == []


def test_duplicate_conflict_payload_increments_counter_and_records_anomaly(shadow_conn):
    eid = append_event(
        shadow_conn, "c-k", _TS, "system.heartbeat", '{"station_id":"S1"}', "gen"
    )
    again = append_event(
        shadow_conn, "c-k", _TS, "system.heartbeat", '{"station_id":"DIFFERENT"}', "gen"
    )
    assert again == eid, "existing event_id returned, never overwritten"
    # original payload preserved (first-write-wins)
    stored = shadow_conn.execute(
        "SELECT payload FROM events WHERE idempotency_key = ?", ("c-k",)
    ).fetchone()["payload"]
    assert "S1" in stored and "DIFFERENT" not in stored
    assert _counter(shadow_conn, "dup_conflict") == 1
    assert _counter(shadow_conn, "dup_exact") == 0
    conflicts = _anomalies(shadow_conn, "dup_conflict")
    assert len(conflicts) == 1
    assert conflicts[0]["idempotency_key"] == "c-k"


def test_canonical_payload_comparison_is_order_insensitive(shadow_conn):
    # Same logical payload, different JSON key order -> canonicalization makes
    # them equal, so this is a dup_exact, NOT a dup_conflict.
    eid = append_event(
        shadow_conn,
        "order-k",
        _TS,
        "system.heartbeat",
        '{"station_id":"S1","sensor_id":"X"}',
        "gen",
    )
    again = append_event(
        shadow_conn,
        "order-k",
        _TS,
        "system.heartbeat",
        '{"sensor_id":"X","station_id":"S1"}',
        "gen",
    )
    assert again == eid
    assert _counter(shadow_conn, "dup_exact") == 1
    assert _counter(shadow_conn, "dup_conflict") == 0
    assert _anomalies(shadow_conn, "dup_conflict") == []
