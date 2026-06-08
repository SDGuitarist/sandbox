import json

from app.payload import parse_patch
from app.anomaly_models import record_anomaly

_ALLOWED = ("temperature_c", "humidity_pct", "wind_speed_kmh")


def apply_environmental(conn, row) -> None:
    payload = json.loads(row["payload"])
    patch = parse_patch(payload, _ALLOWED)
    for key in payload:
        if key not in _ALLOWED:
            record_anomaly(
                conn,
                None,
                "unknown_key",
                row["idempotency_key"],
                f"environmental_state: unknown key {key}",
            )
    if not patch:
        conn.execute(
            "INSERT INTO environmental_state(id) VALUES(1) "
            "ON CONFLICT(id) DO NOTHING"
        )
        return
    columns = sorted(patch)
    insert_cols = ", ".join(["id", *columns])
    insert_placeholders = ", ".join(["1", *["?" for _ in columns]])
    set_clause = ", ".join(f"{col}=excluded.{col}" for col in columns)
    sql = (
        f"INSERT INTO environmental_state({insert_cols}) "
        f"VALUES({insert_placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {set_clause}"
    )
    conn.execute(sql, tuple(patch[col] for col in columns))


def reset_environmental(conn) -> None:
    conn.execute("DELETE FROM environmental_state")
