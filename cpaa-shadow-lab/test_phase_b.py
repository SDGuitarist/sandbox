"""Phase B smoke test — verify generated scenario and derived state."""

import sqlite3
import os

from app.models.events import (
    rebuild_projections_to, advance_projections, get_derived_state,
)

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'instance', 'shadow_lab.db'
)


def open_db():
    db = sqlite3.connect(DB_PATH, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def test_event_count_and_range():
    db = open_db()
    count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count > 500, f"Too few events: {count}"
    min_t = db.execute("SELECT MIN(event_time) FROM events").fetchone()[0]
    max_t = db.execute("SELECT MAX(event_time) FROM events").fetchone()[0]
    assert min_t == '2026-06-15 18:00:00', f"Bad start: {min_t}"
    assert max_t == '2026-06-15 22:00:00', f"Bad end: {max_t}"
    print(f"  event count ({count}) and range: OK")
    db.close()


def test_station_prepopulation():
    db = open_db()
    stations = db.execute("SELECT * FROM station_state ORDER BY station_id").fetchall()
    assert len(stations) == 3
    assert stations[0]['name'] == 'Ceviche Bar'
    assert stations[0]['current_weight_kg'] == 8.0
    assert stations[0]['status'] == 'unknown'
    print("  station pre-population: OK")
    db.close()


def test_heartbeat_drop_station_2():
    """Station 2 should have no heartbeats between 19:15 and 19:18."""
    db = open_db()
    gap_hbs = db.execute(
        "SELECT COUNT(*) FROM events WHERE source = 'station_2' "
        "AND event_type = 'system.heartbeat' "
        "AND event_time >= '2026-06-15 19:15:00' "
        "AND event_time < '2026-06-15 19:18:00'"
    ).fetchone()[0]
    assert gap_hbs == 0, f"Station 2 has {gap_hbs} heartbeats during drop"

    # But heartbeats exist before and after the gap
    before = db.execute(
        "SELECT MAX(event_time) FROM events WHERE source = 'station_2' "
        "AND event_type = 'system.heartbeat' AND event_time < '2026-06-15 19:15:00'"
    ).fetchone()[0]
    after = db.execute(
        "SELECT MIN(event_time) FROM events WHERE source = 'station_2' "
        "AND event_type = 'system.heartbeat' AND event_time >= '2026-06-15 19:18:00'"
    ).fetchone()[0]
    assert before is not None, "No heartbeats before gap"
    assert after is not None, "No heartbeats after gap"
    print(f"  heartbeat drop station_2 (gap {before} to {after}): OK")
    db.close()


def test_network_outage():
    """No events of any kind between 20:00 and 20:15."""
    db = open_db()
    outage_events = db.execute(
        "SELECT COUNT(*) FROM events "
        "WHERE event_time >= '2026-06-15 20:00:00' "
        "AND event_time < '2026-06-15 20:15:00'"
    ).fetchone()[0]
    assert outage_events == 0, f"{outage_events} events during outage"
    print("  network outage (20:00-20:15 empty): OK")
    db.close()


def test_temp_spike_alert():
    """Temp breach alert raised at 19:45, resolved at 19:55."""
    db = open_db()
    raised = db.execute(
        "SELECT * FROM events WHERE event_type = 'system.alert.raised' "
        "AND event_time = '2026-06-15 19:45:00'"
    ).fetchone()
    assert raised is not None, "No alert raised at 19:45"

    resolved = db.execute(
        "SELECT * FROM events WHERE event_type = 'system.alert.resolved' "
        "AND event_time = '2026-06-15 19:55:00'"
    ).fetchone()
    assert resolved is not None, "No alert resolved at 19:55"
    print("  temp spike alert raised/resolved: OK")
    db.close()


def test_auction_stall():
    """No bid events between 20:30 and 20:50."""
    db = open_db()
    stall_bids = db.execute(
        "SELECT COUNT(*) FROM events "
        "WHERE event_type = 'telemetry.financial.bid' "
        "AND event_time >= '2026-06-15 20:30:00' "
        "AND event_time < '2026-06-15 20:50:00'"
    ).fetchone()[0]
    assert stall_bids == 0, f"{stall_bids} bids during stall"
    print("  auction stall (20:30-20:50 no bids): OK")
    db.close()


def test_derived_state_at_key_times():
    """Rebuild projections to key times and verify derived state shape."""
    db = open_db()

    # At 19:00 — normal operation
    rebuild_projections_to(db, "2026-06-15 19:00:00")
    state = get_derived_state(db, "2026-06-15 19:00:00")
    assert len(state['stations']) == 3
    assert state['financials']['total_revenue_cents'] > 0
    assert state['financials']['transaction_count'] > 0
    assert state['environment']['temperature_c'] is not None

    # All stations should be healthy at 19:00
    for s in state['stations']:
        assert s['status'] == 'healthy', (
            f"{s['station_id']} is {s['status']} at 19:00"
        )

    # At 19:16 — station_2 heartbeat dropped at 19:15, TTL=60s
    rebuild_projections_to(db, "2026-06-15 19:16:30")
    state = get_derived_state(db, "2026-06-15 19:16:30")
    s2 = next(s for s in state['stations'] if s['station_id'] == 'station_2')
    assert s2['status'] == 'unknown', (
        f"station_2 should be unknown at 19:16:30, got {s2['status']}"
    )
    # station_1 and station_3 should still be healthy
    s1 = next(s for s in state['stations'] if s['station_id'] == 'station_1')
    assert s1['status'] == 'healthy', f"station_1 should be healthy, got {s1['status']}"

    # At 19:45 — temp breach alert should be active
    rebuild_projections_to(db, "2026-06-15 19:45:00")
    state = get_derived_state(db, "2026-06-15 19:45:00")
    alert_keys = {a['alert_key'] for a in state['alerts']}
    assert 'temp_breach:station_1' in alert_keys, (
        f"Missing temp_breach alert. Got: {alert_keys}"
    )

    # At 19:56 — temp breach should be resolved
    rebuild_projections_to(db, "2026-06-15 19:56:00")
    state = get_derived_state(db, "2026-06-15 19:56:00")
    event_alert_keys = {
        a['alert_key'] for a in state['alerts']
        if a['alert_type'] == 'temp_breach'
    }
    assert 'temp_breach:station_1' not in event_alert_keys, (
        "temp_breach should be resolved at 19:56"
    )

    # At 20:05 — during outage, all stations should go unknown
    rebuild_projections_to(db, "2026-06-15 20:05:00")
    state = get_derived_state(db, "2026-06-15 20:05:00")
    for s in state['stations']:
        assert s['status'] == 'unknown', (
            f"{s['station_id']} should be unknown during outage, got {s['status']}"
        )

    # At 22:00 — final state
    rebuild_projections_to(db, "2026-06-15 22:00:00")
    state = get_derived_state(db, "2026-06-15 22:00:00")
    assert 'stations' in state
    assert 'financials' in state
    assert 'environment' in state
    assert 'alerts' in state
    assert state['financials']['transaction_count'] > 0
    assert state['financials']['total_bids'] > 0

    print("  derived state at key times: OK")

    # Clean up: reset projections and restore pre-populated stations
    rebuild_projections_to(db, None)
    db.close()


if __name__ == '__main__':
    print("Phase B smoke tests:")
    test_event_count_and_range()
    test_station_prepopulation()
    test_heartbeat_drop_station_2()
    test_network_outage()
    test_temp_spike_alert()
    test_auction_stall()
    test_derived_state_at_key_times()
    print("\nAll Phase B tests passed!")
