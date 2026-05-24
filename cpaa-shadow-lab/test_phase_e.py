#!/usr/bin/env python3
"""Phase E — Failure injection verification.

Tests all 4 failure scenarios produce correct state transitions,
plus a full replay consistency check.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.events import (
    advance_projections, get_derived_state, rebuild_projections_to,
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


def station_by_id(stations, sid):
    return next(s for s in stations if s['station_id'] == sid)


def alert_keys(alerts):
    return {a['alert_key'] for a in alerts}


def alert_types(alerts):
    return {a['alert_type'] for a in alerts}


# ── Injection 1: Station 2 heartbeat drop (19:15-19:18) ──────────────

def test_heartbeat_drop():
    db = open_db()

    # Before the gap: all stations healthy
    rebuild_projections_to(db, "2026-06-15 19:14:00")
    state = get_derived_state(db, "2026-06-15 19:14:00")
    for s in state['stations']:
        assert s['status'] == 'healthy', (
            f"{s['station_id']} should be healthy at 19:14, got {s['status']}"
        )

    # During the gap: station_2 unknown (last HB ~19:14:30, now 19:16:30 = 120s > 60s TTL)
    rebuild_projections_to(db, "2026-06-15 19:16:30")
    state = get_derived_state(db, "2026-06-15 19:16:30")
    s2 = station_by_id(state['stations'], 'station_2')
    assert s2['status'] == 'unknown', (
        f"station_2 should be unknown at 19:16:30, got {s2['status']}"
    )
    assert 'heartbeat_lost:station_2' in alert_keys(state['alerts']), (
        "Missing heartbeat_lost alert for station_2"
    )
    # station_1 and station_3 should still be healthy
    s1 = station_by_id(state['stations'], 'station_1')
    s3 = station_by_id(state['stations'], 'station_3')
    assert s1['status'] == 'healthy', f"station_1 should be healthy, got {s1['status']}"
    assert s3['status'] == 'healthy', f"station_3 should be healthy, got {s3['status']}"

    # After the gap: station_2 recovers
    rebuild_projections_to(db, "2026-06-15 19:19:00")
    state = get_derived_state(db, "2026-06-15 19:19:00")
    s2 = station_by_id(state['stations'], 'station_2')
    assert s2['status'] == 'healthy', (
        f"station_2 should recover by 19:19, got {s2['status']}"
    )
    assert 'heartbeat_lost:station_2' not in alert_keys(state['alerts']), (
        "heartbeat_lost for station_2 should resolve after gap"
    )

    print("  Injection 1 (heartbeat drop): PASS")
    db.close()


# ── Injection 2: Ceviche Bar temp breach (19:45) ─────────────────────

def test_temp_breach():
    db = open_db()

    # At 19:45: temp breach alert active
    rebuild_projections_to(db, "2026-06-15 19:45:00")
    state = get_derived_state(db, "2026-06-15 19:45:00")
    assert 'temp_breach:station_1' in alert_keys(state['alerts']), (
        "Missing temp_breach alert at 19:45"
    )
    breach = next(a for a in state['alerts'] if a['alert_key'] == 'temp_breach:station_1')
    assert breach['severity'] == 'critical', f"Expected critical, got {breach['severity']}"

    # Station temp_status should be critical
    s1 = station_by_id(state['stations'], 'station_1')
    assert s1['temp_status'] == 'critical', (
        f"station_1 temp_status should be critical, got {s1['temp_status']}"
    )
    assert s1['current_temp_c'] == 8.2, f"Expected 8.2C, got {s1['current_temp_c']}"

    # At 19:56: alert should be resolved
    rebuild_projections_to(db, "2026-06-15 19:56:00")
    state = get_derived_state(db, "2026-06-15 19:56:00")
    event_breach_alerts = [
        a for a in state['alerts'] if a.get('alert_key') == 'temp_breach:station_1'
    ]
    assert len(event_breach_alerts) == 0, "temp_breach should be resolved at 19:56"

    # Station temp should have dropped back
    s1 = station_by_id(state['stations'], 'station_1')
    assert s1['current_temp_c'] < 5.0, (
        f"station_1 temp should be <5C after resolve, got {s1['current_temp_c']}"
    )

    print("  Injection 2 (temp breach): PASS")
    db.close()


# ── Injection 3: Network outage (20:00-20:15) ────────────────────────

def test_network_outage():
    db = open_db()

    # Just before outage: all healthy
    rebuild_projections_to(db, "2026-06-15 19:59:30")
    state = get_derived_state(db, "2026-06-15 19:59:30")
    for s in state['stations']:
        assert s['status'] == 'healthy', (
            f"{s['station_id']} should be healthy at 19:59:30, got {s['status']}"
        )

    # During outage: all stations unknown (60s after last heartbeat each)
    rebuild_projections_to(db, "2026-06-15 20:02:00")
    state = get_derived_state(db, "2026-06-15 20:02:00")
    unknown_count = sum(1 for s in state['stations'] if s['status'] == 'unknown')
    assert unknown_count == 3, (
        f"All 3 stations should be unknown at 20:02, got {unknown_count}"
    )
    hb_alerts = [a for a in state['alerts'] if a['alert_type'] == 'heartbeat_lost']
    assert len(hb_alerts) == 3, f"Expected 3 heartbeat_lost alerts, got {len(hb_alerts)}"

    # After outage: stations recover
    rebuild_projections_to(db, "2026-06-15 20:16:00")
    state = get_derived_state(db, "2026-06-15 20:16:00")
    healthy_count = sum(1 for s in state['stations'] if s['status'] == 'healthy')
    assert healthy_count == 3, (
        f"All 3 should recover by 20:16, got {healthy_count} healthy"
    )

    print("  Injection 3 (network outage): PASS")
    db.close()


# ── Injection 4: Auction stall (20:30-20:50) ─────────────────────────

def test_auction_stall():
    db = open_db()

    # At 20:45: last bid was ~20:25 = 20 min ago > 15 min threshold
    rebuild_projections_to(db, "2026-06-15 20:45:00")
    state = get_derived_state(db, "2026-06-15 20:45:00")
    assert 'auction_stall:global' in alert_keys(state['alerts']), (
        "Missing auction_stall alert at 20:45"
    )
    stall = next(a for a in state['alerts'] if a['alert_key'] == 'auction_stall:global')
    assert stall['severity'] == 'warning', f"Expected warning, got {stall['severity']}"

    # After lot_3 bids start (~20:55+): stall should resolve
    rebuild_projections_to(db, "2026-06-15 21:00:00")
    state = get_derived_state(db, "2026-06-15 21:00:00")
    assert 'auction_stall:global' not in alert_keys(state['alerts']), (
        "auction_stall should resolve after new bids arrive"
    )

    print("  Injection 4 (auction stall): PASS")
    db.close()


# ── Full replay consistency ───────────────────────────────────────────

def test_full_replay():
    db = open_db()

    # Advance from start to end
    rebuild_projections_to(db, None)
    advance_projections(db, "2026-06-15 22:00:00")
    state = get_derived_state(db, "2026-06-15 22:00:00")

    # All stations should exist with names
    assert len(state['stations']) == 3
    names = {s['name'] for s in state['stations']}
    assert names == {'Ceviche Bar', 'Taco Station', 'Dessert Table'}, (
        f"Expected 3 named stations, got {names}"
    )

    # Financials should match generator totals
    f = state['financials']
    assert f['transaction_count'] == 69, f"Expected 69 txns, got {f['transaction_count']}"
    assert f['total_bids'] == 20, f"Expected 20 bids, got {f['total_bids']}"
    assert f['total_revenue_cents'] > 0, "Revenue should be positive"
    assert f['highest_bid_cents'] > 0, "Highest bid should be positive"

    # Environment should have final readings
    e = state['environment']
    assert e['temperature_c'] is not None
    assert e['humidity_pct'] is not None

    # Rebuild back to start: projections should be clean
    rebuild_projections_to(db, "2026-06-15 18:00:30")
    state = get_derived_state(db, "2026-06-15 18:00:30")
    assert state['financials'].get('total_revenue_cents', 0) == 0, (
        "Revenue should be 0 at scenario start"
    )
    # Stations should exist (from heartbeats) and be healthy
    assert len(state['stations']) == 3
    for s in state['stations']:
        assert s['status'] == 'healthy', (
            f"{s['station_id']} should be healthy at start, got {s['status']}"
        )

    # Reset: projections empty
    rebuild_projections_to(db, None)
    cursor = db.execute(
        "SELECT last_projected_time FROM replay_meta WHERE id = 1"
    ).fetchone()
    assert cursor['last_projected_time'] is None, "Cursor should be NULL after reset"

    print("  Full replay consistency: PASS")
    db.close()


if __name__ == '__main__':
    print("Phase E — Failure injection verification:")
    test_heartbeat_drop()
    test_temp_breach()
    test_network_outage()
    test_auction_stall()
    test_full_replay()
    print("\nAll Phase E tests passed!")
