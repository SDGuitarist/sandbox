"""Event log and projection engine for CPAA Shadow Lab.

All public functions take a sqlite3.Connection with isolation_level=None.
Write functions (append_event, rebuild_projections_to, advance_projections)
commit internally via BEGIN IMMEDIATE. Read functions do NOT commit.
"""

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Temperature thresholds (matches config.py EVENT_CONFIG)
TEMP_WARNING_C = 5.0
TEMP_CRITICAL_C = 7.0


def parse_time(time_str: str) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM:SS' to datetime."""
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Projection handlers — each is (db, event_id, event_time, source, payload)
# ---------------------------------------------------------------------------

def _ensure_station(db: sqlite3.Connection, station_id: str, event_time: str):
    """Insert station with defaults if it doesn't exist yet."""
    db.execute(
        "INSERT OR IGNORE INTO station_state "
        "(station_id, name, status, temp_status, updated_at) "
        "VALUES (?, ?, 'unknown', 'normal', ?)",
        (station_id, station_id, event_time),
    )


def _project_station_weight(db, event_id, event_time, source, payload):
    station_id = payload['station_id']
    _ensure_station(db, station_id, event_time)
    db.execute(
        "UPDATE station_state SET current_weight_kg = ?, updated_at = ? "
        "WHERE station_id = ?",
        (payload['weight_kg'], event_time, station_id),
    )


def _project_station_temperature(db, event_id, event_time, source, payload):
    station_id = payload['station_id']
    temp = payload['temp_c']
    if temp >= TEMP_CRITICAL_C:
        temp_status = 'critical'
    elif temp >= TEMP_WARNING_C:
        temp_status = 'warning'
    else:
        temp_status = 'normal'
    _ensure_station(db, station_id, event_time)
    db.execute(
        "UPDATE station_state SET current_temp_c = ?, temp_status = ?, "
        "updated_at = ? WHERE station_id = ?",
        (temp, temp_status, event_time, station_id),
    )


def _project_financial_transaction(db, event_id, event_time, source, payload):
    db.execute(
        "INSERT INTO financial_state "
        "(id, total_revenue_cents, transaction_count, total_bids, "
        "highest_bid_cents, active_lots, updated_at) "
        "VALUES (1, ?, 1, 0, 0, 0, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "total_revenue_cents = financial_state.total_revenue_cents "
        "+ excluded.total_revenue_cents, "
        "transaction_count = financial_state.transaction_count + 1, "
        "updated_at = excluded.updated_at",
        (payload['amount_cents'], event_time),
    )


def _project_financial_bid(db, event_id, event_time, source, payload):
    amount = payload['amount_cents']
    db.execute(
        "INSERT INTO financial_state "
        "(id, total_revenue_cents, transaction_count, total_bids, "
        "highest_bid_cents, active_lots, updated_at) "
        "VALUES (1, 0, 0, 1, ?, 0, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "total_bids = financial_state.total_bids + 1, "
        "highest_bid_cents = MAX(financial_state.highest_bid_cents, "
        "excluded.highest_bid_cents), "
        "updated_at = excluded.updated_at",
        (amount, event_time),
    )


def _project_environment(db, event_id, event_time, source, payload):
    db.execute(
        "INSERT INTO environment_state "
        "(id, temperature_c, humidity_pct, wind_speed_kmh, updated_at) "
        "VALUES (1, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "temperature_c = excluded.temperature_c, "
        "humidity_pct = excluded.humidity_pct, "
        "wind_speed_kmh = excluded.wind_speed_kmh, "
        "updated_at = excluded.updated_at",
        (payload['temperature_c'], payload['humidity_pct'],
         payload['wind_speed_kmh'], event_time),
    )


def _project_heartbeat(db, event_id, event_time, source, payload):
    station_id = payload['station_id']
    _ensure_station(db, station_id, event_time)
    db.execute(
        "UPDATE station_state SET last_heartbeat = ?, status = 'healthy', "
        "updated_at = ? WHERE station_id = ?",
        (event_time, event_time, station_id),
    )


def _project_alert_raised(db, event_id, event_time, source, payload):
    alert_key = f"{payload['alert_type']}:{payload['source']}"
    db.execute(
        "INSERT OR REPLACE INTO active_alerts "
        "(alert_key, event_id, alert_type, source, message, severity, "
        "raised_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
        (alert_key, event_id, payload['alert_type'], payload['source'],
         payload['message'], payload['severity'], event_time),
    )


def _project_alert_resolved(db, event_id, event_time, source, payload):
    db.execute(
        "UPDATE active_alerts SET resolved_at = ? WHERE alert_key = ?",
        (event_time, payload['alert_key']),
    )


PROJECTION_HANDLERS = {
    'telemetry.culinary.weight': _project_station_weight,
    'telemetry.culinary.temperature': _project_station_temperature,
    'telemetry.financial.transaction': _project_financial_transaction,
    'telemetry.financial.bid': _project_financial_bid,
    'telemetry.environmental.weather': _project_environment,
    'system.heartbeat': _project_heartbeat,
    'system.alert.raised': _project_alert_raised,
    'system.alert.resolved': _project_alert_resolved,
}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def append_event(
    db: sqlite3.Connection,
    event_time: str,
    source: str,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    """Append event and update projections atomically. Commits internally.

    Returns the new event ID.
    """
    db.execute("BEGIN IMMEDIATE")
    try:
        cursor = db.execute(
            "INSERT INTO events (event_time, source, event_type, payload) "
            "VALUES (?, ?, ?, ?)",
            (event_time, source, event_type, json.dumps(payload)),
        )
        event_id = cursor.lastrowid
        handler = PROJECTION_HANDLERS.get(event_type)
        if handler:
            handler(db, event_id, event_time, source, payload)
        else:
            logger.warning(
                "No projection handler for event type: %s (event_id=%d)",
                event_type, event_id,
            )
        db.execute("COMMIT")
        return event_id
    except Exception:
        db.execute("ROLLBACK")
        raise


def rebuild_projections_to(
    db: sqlite3.Connection, target_time: str | None,
) -> None:
    """Clear all projections and replay events up to target_time.

    Commits internally. Pass target_time=None to clear everything (reset).
    Uses cursor iteration for O(1) memory.
    """
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("DELETE FROM station_state")
        db.execute("DELETE FROM financial_state")
        db.execute("DELETE FROM environment_state")
        db.execute("DELETE FROM active_alerts")

        if target_time is None:
            db.execute(
                "INSERT OR REPLACE INTO replay_meta "
                "(id, last_projected_time) VALUES (1, NULL)"
            )
        else:
            cursor = db.execute(
                "SELECT id, event_time, source, event_type, payload "
                "FROM events WHERE event_time <= ? ORDER BY event_time, id",
                (target_time,),
            )
            for event in cursor:
                handler = PROJECTION_HANDLERS.get(event['event_type'])
                if handler:
                    payload = json.loads(event['payload'])
                    handler(
                        db, event['id'], event['event_time'],
                        event['source'], payload,
                    )
            db.execute(
                "INSERT OR REPLACE INTO replay_meta "
                "(id, last_projected_time) VALUES (1, ?)",
                (target_time,),
            )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise


def advance_projections(
    db: sqlite3.Connection, target_time: str,
) -> None:
    """Project events from cursor to target_time. Commits internally.

    No-op if target_time <= cursor (prevents double-projection).
    """
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute(
            "SELECT last_projected_time FROM replay_meta WHERE id = 1"
        ).fetchone()
        cursor_time = row['last_projected_time'] if row else None

        if cursor_time and target_time <= cursor_time:
            db.execute("COMMIT")
            return

        if cursor_time:
            events = db.execute(
                "SELECT id, event_time, source, event_type, payload "
                "FROM events WHERE event_time > ? AND event_time <= ? "
                "ORDER BY event_time, id",
                (cursor_time, target_time),
            )
        else:
            events = db.execute(
                "SELECT id, event_time, source, event_type, payload "
                "FROM events WHERE event_time <= ? ORDER BY event_time, id",
                (target_time,),
            )

        for event in events:
            handler = PROJECTION_HANDLERS.get(event['event_type'])
            if handler:
                payload = json.loads(event['payload'])
                handler(
                    db, event['id'], event['event_time'],
                    event['source'], payload,
                )

        db.execute(
            "INSERT OR REPLACE INTO replay_meta "
            "(id, last_projected_time) VALUES (1, ?)",
            (target_time,),
        )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise


def get_derived_state(
    db: sqlite3.Connection,
    current_time: str,
    heartbeat_ttl_seconds: int = 60,
    auction_stall_minutes: int = 15,
) -> dict[str, Any]:
    """Return full derived state dict. Read-only, does NOT commit.

    sqlite3.Row objects are read-only — convert to dicts before mutation.
    """
    # Stations — convert to dicts for mutability
    stations = [
        dict(row)
        for row in db.execute("SELECT * FROM station_state").fetchall()
    ]

    # Mark stations with stale heartbeats
    current_dt = parse_time(current_time)
    for station in stations:
        if station['last_heartbeat']:
            elapsed = (
                current_dt - parse_time(station['last_heartbeat'])
            ).total_seconds()
            if elapsed > heartbeat_ttl_seconds:
                station['status'] = 'unknown'

    financial = db.execute(
        "SELECT * FROM financial_state WHERE id = 1"
    ).fetchone()
    environment = db.execute(
        "SELECT * FROM environment_state WHERE id = 1"
    ).fetchone()

    alerts = _compute_all_alerts(
        db, stations, current_time, heartbeat_ttl_seconds,
        auction_stall_minutes,
    )

    return {
        'stations': stations,
        'financials': dict(financial) if financial else {},
        'environment': dict(environment) if environment else {},
        'alerts': alerts,
    }


def _compute_all_alerts(
    db: sqlite3.Connection,
    stations: list[dict],
    current_time: str,
    heartbeat_ttl_seconds: int,
    auction_stall_minutes: int,
) -> list[dict]:
    """Merge event-triggered + absence-derived alerts."""
    # Event-triggered (materialized in active_alerts)
    event_alerts = [
        dict(a) for a in db.execute(
            "SELECT * FROM active_alerts WHERE resolved_at IS NULL"
        ).fetchall()
    ]

    # Absence-derived (computed at query time)
    derived_alerts = []
    current_dt = parse_time(current_time)

    for station in stations:
        if station['last_heartbeat']:
            elapsed = (
                current_dt - parse_time(station['last_heartbeat'])
            ).total_seconds()
            if elapsed > heartbeat_ttl_seconds:
                derived_alerts.append({
                    'alert_key': f"heartbeat_lost:{station['station_id']}",
                    'alert_type': 'heartbeat_lost',
                    'source': station['station_id'],
                    'message': (
                        f"{station['name']} heartbeat lost "
                        f"({int(elapsed)}s ago)"
                    ),
                    'severity': 'warning',
                })

    # Auction stall check
    last_bid = db.execute(
        "SELECT MAX(event_time) as t FROM events "
        "WHERE event_type = 'telemetry.financial.bid' "
        "AND event_time <= ?",
        (current_time,),
    ).fetchone()
    if last_bid and last_bid['t']:
        stall_seconds = (
            current_dt - parse_time(last_bid['t'])
        ).total_seconds()
        if stall_seconds > auction_stall_minutes * 60:
            derived_alerts.append({
                'alert_key': 'auction_stall:global',
                'alert_type': 'auction_stall',
                'source': 'auction',
                'message': f"No bids for {int(stall_seconds // 60)} minutes",
                'severity': 'warning',
            })

    all_alerts = event_alerts + derived_alerts
    all_alerts.sort(
        key=lambda a: (0 if a.get('severity') == 'critical' else 1)
    )
    return all_alerts
