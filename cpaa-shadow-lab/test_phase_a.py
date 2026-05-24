"""Phase A smoke test — verify append_event + projections + get_derived_state."""

import sqlite3
import os

from app.models.events import (
    append_event, rebuild_projections_to, advance_projections,
    get_derived_state,
)

DB_PATH = "/tmp/cpaa_shadow_lab_test.db"
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def make_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db = sqlite3.connect(DB_PATH, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    with open(SCHEMA_PATH) as f:
        db.executescript(f.read())
    return db


def test_append_and_projections():
    db = make_db()
    t = "2026-06-15 18:00:00"

    # Heartbeat sets station to healthy
    eid = append_event(db, t, "station_1", "system.heartbeat",
                       {"sensor_id": "s1", "station_id": "station_1"})
    assert eid == 1, f"Expected event id 1, got {eid}"

    # Weight update
    append_event(db, "2026-06-15 18:01:00", "station_1",
                 "telemetry.culinary.weight",
                 {"station_id": "station_1", "weight_kg": 7.5})

    # Temperature (below warning)
    append_event(db, "2026-06-15 18:02:00", "station_1",
                 "telemetry.culinary.temperature",
                 {"station_id": "station_1", "temp_c": 2.0})

    # POS transaction
    append_event(db, "2026-06-15 18:03:00", "pos",
                 "telemetry.financial.transaction",
                 {"amount_cents": 4500, "item": "tacos", "station_id": "station_1"})

    # Bid
    append_event(db, "2026-06-15 18:04:00", "auction",
                 "telemetry.financial.bid",
                 {"lot_id": "lot_1", "amount_cents": 55000, "bid_number": 1})

    # Weather
    append_event(db, "2026-06-15 18:05:00", "weather_station",
                 "telemetry.environmental.weather",
                 {"temperature_c": 22.0, "humidity_pct": 65.0,
                  "wind_speed_kmh": 12.0})

    # Alert raised
    append_event(db, "2026-06-15 19:45:00", "system",
                 "system.alert.raised",
                 {"alert_type": "temp_breach", "source": "station_1",
                  "message": "Ceviche Bar temp 8.2C", "severity": "critical"})

    state = get_derived_state(db, "2026-06-15 19:45:00")

    # Verify shape
    assert 'stations' in state, "Missing 'stations' key"
    assert 'financials' in state, "Missing 'financials' key"
    assert 'environment' in state, "Missing 'environment' key"
    assert 'alerts' in state, "Missing 'alerts' key"

    # Verify station data
    assert len(state['stations']) == 1
    s = state['stations'][0]
    assert s['station_id'] == 'station_1'
    assert s['current_weight_kg'] == 7.5
    assert s['current_temp_c'] == 2.0
    assert s['temp_status'] == 'normal'
    # Heartbeat was at 18:00, current time is 19:45 — 105 min > 60s TTL
    assert s['status'] == 'unknown', f"Expected unknown, got {s['status']}"

    # Verify financials
    f = state['financials']
    assert f['total_revenue_cents'] == 4500
    assert f['transaction_count'] == 1
    assert f['total_bids'] == 1
    assert f['highest_bid_cents'] == 55000

    # Verify environment
    e = state['environment']
    assert e['temperature_c'] == 22.0
    assert e['humidity_pct'] == 65.0

    # Verify alerts — should have temp_breach (event) + heartbeat_lost (derived)
    assert len(state['alerts']) >= 2
    alert_keys = {a['alert_key'] for a in state['alerts']}
    assert 'temp_breach:station_1' in alert_keys
    assert 'heartbeat_lost:station_1' in alert_keys
    # Critical sorts first
    assert state['alerts'][0]['severity'] == 'critical'

    print("  append + projection + get_derived_state: OK")
    db.close()


def test_rebuild_projections():
    db = make_db()

    # Insert events across time
    append_event(db, "2026-06-15 18:00:00", "station_1", "system.heartbeat",
                 {"sensor_id": "s1", "station_id": "station_1"})
    append_event(db, "2026-06-15 19:00:00", "pos",
                 "telemetry.financial.transaction",
                 {"amount_cents": 3000, "item": "drinks", "station_id": "s1"})
    append_event(db, "2026-06-15 20:00:00", "pos",
                 "telemetry.financial.transaction",
                 {"amount_cents": 5000, "item": "dinner", "station_id": "s1"})

    # Rebuild to 19:00 — should only see first transaction
    rebuild_projections_to(db, "2026-06-15 19:00:00")
    state = get_derived_state(db, "2026-06-15 19:00:00")
    assert state['financials']['total_revenue_cents'] == 3000
    assert state['financials']['transaction_count'] == 1

    # Rebuild to None (reset) — projections empty
    rebuild_projections_to(db, None)
    state = get_derived_state(db, "2026-06-15 18:00:00")
    assert state['financials'] == {}
    assert state['stations'] == []

    print("  rebuild_projections_to: OK")
    db.close()


def test_advance_projections():
    db = make_db()

    append_event(db, "2026-06-15 18:00:00", "station_1", "system.heartbeat",
                 {"sensor_id": "s1", "station_id": "station_1"})
    append_event(db, "2026-06-15 19:00:00", "pos",
                 "telemetry.financial.transaction",
                 {"amount_cents": 3000, "item": "drinks", "station_id": "s1"})
    append_event(db, "2026-06-15 20:00:00", "pos",
                 "telemetry.financial.transaction",
                 {"amount_cents": 5000, "item": "dinner", "station_id": "s1"})

    # Clear projections (matches real app flow: generator pre-loads, app resets)
    rebuild_projections_to(db, None)

    # Advance to 19:00
    advance_projections(db, "2026-06-15 19:00:00")
    state = get_derived_state(db, "2026-06-15 19:00:00")
    assert state['financials']['total_revenue_cents'] == 3000

    # Advance to 20:00 — should add second transaction
    advance_projections(db, "2026-06-15 20:00:00")
    state = get_derived_state(db, "2026-06-15 20:00:00")
    assert state['financials']['total_revenue_cents'] == 8000
    assert state['financials']['transaction_count'] == 2

    # Advance to 19:00 again — no-op (cursor already past)
    advance_projections(db, "2026-06-15 19:00:00")
    state = get_derived_state(db, "2026-06-15 20:00:00")
    assert state['financials']['total_revenue_cents'] == 8000

    print("  advance_projections: OK")
    db.close()


def test_alert_resolve():
    db = make_db()

    append_event(db, "2026-06-15 19:45:00", "system",
                 "system.alert.raised",
                 {"alert_type": "temp_breach", "source": "station_1",
                  "message": "Temp high", "severity": "critical"})

    state = get_derived_state(db, "2026-06-15 19:45:00")
    assert any(a['alert_key'] == 'temp_breach:station_1'
               for a in state['alerts'])

    append_event(db, "2026-06-15 19:50:00", "system",
                 "system.alert.resolved",
                 {"alert_key": "temp_breach:station_1", "reason": "temp normal"})

    state = get_derived_state(db, "2026-06-15 19:50:00")
    assert not any(a['alert_key'] == 'temp_breach:station_1'
                   for a in state['alerts'])

    print("  alert raise/resolve: OK")
    db.close()


if __name__ == "__main__":
    print("Phase A smoke tests:")
    test_append_and_projections()
    test_rebuild_projections()
    test_advance_projections()
    test_alert_resolve()
    print("\nAll Phase A tests passed!")
    os.remove(DB_PATH)
