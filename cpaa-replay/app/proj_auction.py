import sqlite3

from app.payload import parse_json, parse_patch
from app.anomaly_models import record_anomaly

_ALLOWED = ("amount_cents", "bid_number")


def apply_auction(conn: sqlite3.Connection, row: sqlite3.Row) -> None:
    payload = parse_json(row["payload"])
    if not isinstance(payload, dict):
        record_anomaly(conn, None, "malformed_payload", None, "auction payload not an object")
        return

    lot_id = payload.get("lot_id")
    if not isinstance(lot_id, str) or not lot_id:
        record_anomaly(conn, None, "malformed_payload", None, "missing lot_id")
        return

    for key in payload:
        if key != "lot_id" and key not in _ALLOWED:
            record_anomaly(conn, None, "unknown_key", None, key)

    patch = parse_patch(payload, _ALLOWED)

    if "amount_cents" not in patch:
        return
    amount = patch["amount_cents"]
    if amount is None:
        return

    conn.execute(
        "INSERT INTO auction_state(lot_id, bid_high_cents, bid_count) "
        "VALUES(:lot_id, :amount, 1) "
        "ON CONFLICT(lot_id) DO UPDATE SET "
        "bid_high_cents = MAX(bid_high_cents, excluded.bid_high_cents), "
        "bid_count = bid_count + 1",
        {"lot_id": lot_id, "amount": amount},
    )


def reset_auction(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM auction_state")
