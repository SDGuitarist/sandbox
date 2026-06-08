"""Ingest source events from the read-only live.db into shadow.db.

Reads ``source_events`` from ``live.db`` via ``open_live_ro`` (READ-ONLY),
performs ingest-time structural validation on each event (§7), and dedup-appends
valid events into ``shadow.db`` via ``append_event``. Malformed events and events
with an unmapped ``event_type`` are recorded as anomalies and SKIPPED.

The caller (ingest_routes) owns the transaction: it opens the shadow connection
with ``get_db(immediate=True)`` (BEGIN IMMEDIATE) and commits. This module never
opens the shadow connection and never commits (§8 rule 2, FC5/FC29).
"""

import json

from app.db import open_live_ro
from app.event_models import append_event
from app.anomaly_models import record_anomaly
from app.payload import parse_json
from app.constants import DISPATCH

# Maximum source-payload size accepted at ingest time (§7).
MAX_PAYLOAD_BYTES = 64 * 1024
# Maximum event_type length accepted at ingest time (§7).
MAX_EVENT_TYPE_LEN = 128

# Required keys per event_type (§4.4 "Required" column). An event whose payload
# is missing any of these keys is malformed and SKIPPED. Event types not listed
# have no required keys (only weather has none).
REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "system.heartbeat": ("station_id",),
    "telemetry.culinary.weight": ("station_id",),
    "telemetry.culinary.temperature": ("station_id",),
    "telemetry.financial.transaction": ("station_id",),
    "telemetry.financial.bid": ("lot_id",),
    "telemetry.environmental.weather": (),
    "system.operator_note": ("note",),
    "system.alert.raised": ("alert_type", "source"),
    "system.alert.resolved": ("alert_key",),
}


def ingest_source(conn, live_db_path: str) -> dict[str, int]:
    """Ingest all source_events from live.db into shadow.db's events log.

    Args:
        conn: an already-open shadow ``sqlite3.Connection`` inside the caller's
            BEGIN IMMEDIATE transaction. This function NEVER commits.
        live_db_path: filesystem path to the read-only live.db.

    Returns:
        A counts dict: ``{"read", "appended", "malformed", "unknown"}``.
    """
    counts = {"read": 0, "appended": 0, "malformed": 0, "unknown": 0}

    ro_conn = open_live_ro(live_db_path)
    try:
        rows = ro_conn.execute(
            "SELECT idempotency_key, logical_ts, event_type, payload, source "
            "FROM source_events ORDER BY seq"
        ).fetchall()
    finally:
        ro_conn.close()

    for row in rows:
        counts["read"] += 1
        idempotency_key = row["idempotency_key"]
        logical_ts = row["logical_ts"]
        event_type = row["event_type"]
        raw_payload = row["payload"]
        source = row["source"]

        # Size cap on the raw payload text (§7).
        if not isinstance(raw_payload, str) or len(
            raw_payload.encode("utf-8")
        ) > MAX_PAYLOAD_BYTES:
            record_anomaly(
                conn,
                None,
                "malformed_payload",
                idempotency_key,
                "payload oversize or non-text",
            )
            counts["malformed"] += 1
            continue

        # event_type must be a non-empty str <= 128 chars (§7).
        if (
            not isinstance(event_type, str)
            or not event_type
            or len(event_type) > MAX_EVENT_TYPE_LEN
        ):
            record_anomaly(
                conn,
                None,
                "malformed_payload",
                idempotency_key,
                "invalid event_type",
            )
            counts["malformed"] += 1
            continue

        # event_type must be mapped in DISPATCH; otherwise unknown (§4.4, §7).
        if event_type not in DISPATCH:
            record_anomaly(
                conn,
                None,
                "unknown_key",
                idempotency_key,
                "unmapped event_type",
            )
            counts["unknown"] += 1
            continue

        # Payload must be valid JSON AND a JSON object (§7).
        parsed = parse_json(raw_payload)
        if parsed is None or not isinstance(parsed, dict):
            record_anomaly(
                conn,
                None,
                "malformed_payload",
                idempotency_key,
                "payload not a JSON object",
            )
            counts["malformed"] += 1
            continue

        # Required PK key(s) for this event_type must be present (§4.4, §7).
        required = REQUIRED_KEYS.get(event_type, ())
        if any(key not in parsed for key in required):
            record_anomaly(
                conn,
                None,
                "malformed_payload",
                idempotency_key,
                "missing required key",
            )
            counts["malformed"] += 1
            continue

        # Canonicalize the payload before storage so dedup comparison is
        # order-insensitive (§8 rule 8/9). append_event re-canonicalizes too,
        # but passing a stable form keeps the stored bytes consistent.
        payload_canonical = json.dumps(
            parsed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

        # Dedup-append inside the caller's BEGIN IMMEDIATE. append_event owns the
        # INSERT OR IGNORE + dedup classification; we never commit.
        append_event(
            conn,
            idempotency_key,
            logical_ts,
            event_type,
            payload_canonical,
            source,
        )
        counts["appended"] += 1

    return counts
