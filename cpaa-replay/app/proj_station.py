import json
import sqlite3

from app.payload import parse_patch
from app.anomaly_models import record_anomaly

_HEARTBEAT_ALLOWED = ("station_id", "sensor_id")
_WEIGHT_ALLOWED = ("station_id", "weight_kg")
_TEMPERATURE_ALLOWED = ("station_id", "temp_c")
_TRANSACTION_ALLOWED = ("station_id", "amount_cents", "item")


def reset_station(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM station_state")


def _flag_unknown_keys(conn: sqlite3.Connection, payload: dict, allowed: tuple) -> None:
    for key in payload:
        if key not in allowed:
            record_anomaly(conn, None, "unknown_key", None, f"station_state: {key}")


def apply_station(conn: sqlite3.Connection, row: sqlite3.Row) -> None:
    event_type = row["event_type"]
    payload = json.loads(row["payload"])

    if event_type == "system.heartbeat":
        _flag_unknown_keys(conn, payload, _HEARTBEAT_ALLOWED)
        station_id = payload["station_id"]
        conn.execute(
            "INSERT INTO station_state(station_id, status, last_heartbeat) "
            "VALUES(:station_id, 'online', :last_heartbeat) "
            "ON CONFLICT(station_id) DO UPDATE SET "
            "status=excluded.status, last_heartbeat=excluded.last_heartbeat",
            {"station_id": station_id, "last_heartbeat": row["logical_ts"]},
        )

    elif event_type == "telemetry.culinary.weight":
        _flag_unknown_keys(conn, payload, _WEIGHT_ALLOWED)
        station_id = payload["station_id"]
        patch = parse_patch(payload, _WEIGHT_ALLOWED)
        if "weight_kg" in patch:
            conn.execute(
                "INSERT INTO station_state(station_id, weight_kg) "
                "VALUES(:station_id, :weight_kg) "
                "ON CONFLICT(station_id) DO UPDATE SET weight_kg=excluded.weight_kg",
                {"station_id": station_id, "weight_kg": patch["weight_kg"]},
            )

    elif event_type == "telemetry.culinary.temperature":
        _flag_unknown_keys(conn, payload, _TEMPERATURE_ALLOWED)
        station_id = payload["station_id"]
        patch = parse_patch(payload, _TEMPERATURE_ALLOWED)
        if "temp_c" in patch:
            conn.execute(
                "INSERT INTO station_state(station_id, temp_c) "
                "VALUES(:station_id, :temp_c) "
                "ON CONFLICT(station_id) DO UPDATE SET temp_c=excluded.temp_c",
                {"station_id": station_id, "temp_c": patch["temp_c"]},
            )

    elif event_type == "telemetry.financial.transaction":
        _flag_unknown_keys(conn, payload, _TRANSACTION_ALLOWED)
        station_id = payload["station_id"]
        patch = parse_patch(payload, _TRANSACTION_ALLOWED)
        amount = patch.get("amount_cents")
        if amount is not None:
            conn.execute(
                "INSERT INTO station_state(station_id, sales_total_cents) "
                "VALUES(:station_id, :amount) "
                "ON CONFLICT(station_id) DO UPDATE SET "
                "sales_total_cents=station_state.sales_total_cents + excluded.sales_total_cents",
                {"station_id": station_id, "amount": amount},
            )
