import json
import sqlite3

from app.anomaly_models import record_anomaly
from app.payload import parse_patch

_ALLOWED: dict[str, tuple[str, ...]] = {
    "system.operator_note": ("note",),
    "system.alert.raised": ("alert_type", "source", "message", "severity"),
    "system.alert.resolved": ("alert_key", "reason"),
}


def _upsert(conn: sqlite3.Connection, k: str, v: str) -> None:
    conn.execute(
        "INSERT INTO system_state(k, v) VALUES(?, ?) "
        "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (k, v),
    )


def apply_system(conn: sqlite3.Connection, row: sqlite3.Row) -> None:
    event_type = row["event_type"]
    allowed = _ALLOWED.get(event_type)
    if allowed is None:
        return

    payload = json.loads(row["payload"])

    for key in payload:
        if key not in allowed:
            record_anomaly(
                conn,
                None,
                "unknown_key",
                row["idempotency_key"],
                f"{event_type}: {key}",
            )

    patch = parse_patch(payload, allowed)

    if event_type == "system.operator_note":
        note = patch.get("note")
        if note is None:
            return
        _upsert(conn, "note:" + str(row["event_id"]), str(note))
    elif event_type == "system.alert.raised":
        alert_type = patch.get("alert_type")
        source = patch.get("source")
        if alert_type is None or source is None:
            return
        _upsert(conn, str(alert_type) + ":" + str(source), "raised")
    elif event_type == "system.alert.resolved":
        alert_key = patch.get("alert_key")
        if alert_key is None:
            return
        _upsert(conn, str(alert_key), "resolved")


def reset_system(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM system_state")
