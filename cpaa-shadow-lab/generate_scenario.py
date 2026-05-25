#!/usr/bin/env python3
"""Generate a complete 4-hour charity gala scenario for CPAA Shadow Lab.

Creates synthetic events covering 18:00-22:00 with 4 failure injections.
Run once before starting the Flask app.

Usage: python3 generate_scenario.py
"""

import json
import os
import random
import sqlite3
from datetime import datetime, timedelta

from config import EVENT_CONFIG, STATIONS, AUCTION_LOTS

random.seed(42)

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
DB_PATH = os.path.join(DB_DIR, 'shadow_lab.db')
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')

START = datetime(2026, 6, 15, 18, 0, 0)
END = datetime(2026, 6, 15, 22, 0, 0)

# Failure injection windows
HB_DROP = (datetime(2026, 6, 15, 19, 15, 0), datetime(2026, 6, 15, 19, 18, 0))
OUTAGE = (datetime(2026, 6, 15, 20, 0, 0), datetime(2026, 6, 15, 20, 15, 0))
BID_STALL = (datetime(2026, 6, 15, 20, 30, 0), datetime(2026, 6, 15, 20, 50, 0))
TEMP_SPIKE = datetime(2026, 6, 15, 19, 45, 0)
TEMP_RESOLVE = datetime(2026, 6, 15, 19, 55, 0)


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def in_outage(t):
    return OUTAGE[0] <= t < OUTAGE[1]


def gen_heartbeats():
    """Every 30s per station. Station 2 drops 19:15-19:18. All drop 20:00-20:15."""
    events = []
    interval = EVENT_CONFIG['heartbeat_interval_seconds']
    t = START
    while t <= END:
        if not in_outage(t):
            for s in STATIONS:
                sid = s['id']
                if sid == 'station_2' and HB_DROP[0] <= t < HB_DROP[1]:
                    continue
                events.append((
                    fmt(t), sid, 'system.heartbeat',
                    {'sensor_id': f"sensor_{sid}", 'station_id': sid},
                ))
        t += timedelta(seconds=interval)
    return events


def gen_weights():
    """Gradual decline every 5-10 min with occasional replenishment."""
    events = []
    for s in STATIONS:
        weight = s['initial_weight_kg']
        t = START + timedelta(minutes=random.randint(3, 7))
        replenished_early = False
        replenished_late = False
        while t <= END:
            if not in_outage(t):
                weight -= random.uniform(0.1, 0.4)
                mins = (t - START).total_seconds() / 60
                if not replenished_early and 85 < mins < 95:
                    weight += random.uniform(3.0, 5.0)
                    replenished_early = True
                elif not replenished_late and 175 < mins < 185:
                    weight += random.uniform(3.0, 5.0)
                    replenished_late = True
                weight = max(weight, 0.3)
                events.append((
                    fmt(t), s['id'], 'telemetry.culinary.weight',
                    {'station_id': s['id'], 'weight_kg': round(weight, 1)},
                ))
            t += timedelta(minutes=random.randint(5, 10))
    return events


def gen_temperatures():
    """Ceviche Bar only. Drifts from 2C toward ambient, spikes at 19:45."""
    events = []
    temp = STATIONS[0].get('initial_temp_c', 2.0)
    t = START + timedelta(minutes=5)
    spike_done = False
    resolve_done = False
    while t <= END:
        if not in_outage(t):
            if not spike_done and t >= TEMP_SPIKE:
                temp = 8.2
                spike_done = True
            elif not resolve_done and t >= TEMP_RESOLVE:
                temp = 4.0
                resolve_done = True
            else:
                temp += random.uniform(0.02, 0.12)
                temp = min(temp, 6.0)
            events.append((
                fmt(t), 'station_1', 'telemetry.culinary.temperature',
                {'station_id': 'station_1', 'temp_c': round(temp, 1)},
            ))
        t += timedelta(minutes=5)
    return events


def gen_transactions():
    """POS transactions at random 1-5 min intervals, $15-$200."""
    events = []
    items = ('tacos', 'ceviche', 'drinks', 'dessert', 'cocktail')
    t = START + timedelta(minutes=random.randint(10, 20))
    while t <= END:
        if not in_outage(t):
            events.append((
                fmt(t), 'pos', 'telemetry.financial.transaction',
                {
                    'amount_cents': random.randint(1500, 20000),
                    'item': random.choice(items),
                    'station_id': random.choice(STATIONS)['id'],
                },
            ))
        t += timedelta(minutes=random.randint(1, 5))
    return events


def gen_bids():
    """Clustered bids per lot. No bids during 20:30-20:50 stall window."""
    events = []
    bid_windows = [
        (AUCTION_LOTS[0], START + timedelta(minutes=30),
         START + timedelta(minutes=90)),
        (AUCTION_LOTS[1], START + timedelta(minutes=90),
         START + timedelta(minutes=145)),
        (AUCTION_LOTS[2], START + timedelta(minutes=175),
         START + timedelta(minutes=210)),
    ]
    for lot, win_start, win_end in bid_windows:
        amount = lot['opening_bid_cents']
        num_bids = random.randint(5, 8)
        for i in range(num_bids):
            frac = i / max(num_bids - 1, 1)
            t = win_start + (win_end - win_start) * frac
            t += timedelta(seconds=random.randint(-60, 60))
            t = max(win_start, min(t, win_end))
            if in_outage(t) or BID_STALL[0] <= t < BID_STALL[1]:
                continue
            amount += random.randint(2000, 10000)
            events.append((
                fmt(t), 'auction', 'telemetry.financial.bid',
                {
                    'lot_id': lot['id'],
                    'amount_cents': amount,
                    'bid_number': i + 1,
                },
            ))
    return events


def gen_weather():
    """Gradual marine layer cooling, humidity rise, variable wind."""
    events = []
    temp, humidity, wind = 24.0, 60.0, 12.0
    t = START + timedelta(minutes=10)
    while t <= END:
        if not in_outage(t):
            temp = max(17.0, temp - random.uniform(0.3, 0.8))
            humidity = min(85.0, humidity + random.uniform(0.5, 1.5))
            wind = max(5.0, min(25.0, wind + random.uniform(-2.0, 2.0)))
            events.append((
                fmt(t), 'weather_station',
                'telemetry.environmental.weather',
                {
                    'temperature_c': round(temp, 1),
                    'humidity_pct': round(humidity, 1),
                    'wind_speed_kmh': round(wind, 1),
                },
            ))
        t += timedelta(minutes=random.randint(8, 15))
    return events


def gen_alerts():
    """Event-triggered alert for Ceviche Bar temp breach."""
    return [
        (fmt(TEMP_SPIKE), 'system', 'system.alert.raised', {
            'alert_type': 'temp_breach', 'source': 'station_1',
            'message': 'Ceviche Bar temperature 8.2C exceeds critical threshold',
            'severity': 'critical',
        }),
        (fmt(TEMP_RESOLVE), 'system', 'system.alert.resolved', {
            'alert_key': 'temp_breach:station_1',
            'reason': 'Temperature returned to normal',
        }),
    ]


def gen_operator_notes():
    return [
        (fmt(START), 'operator', 'system.operator_note',
         {'note': 'Gala setup complete, doors opening'}),
        (fmt(START + timedelta(minutes=30)), 'operator', 'system.operator_note',
         {'note': 'Silent auction is now live'}),
        (fmt(END - timedelta(minutes=15)), 'operator', 'system.operator_note',
         {'note': 'Closing remarks beginning, thank donors'}),
    ]


def main():
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    db = sqlite3.connect(DB_PATH, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")

    with open(SCHEMA_PATH) as f:
        db.executescript(f.read())

    # Pre-populate station_state with initial values (dashboard shows these
    # before replay starts — projections update them during advance)
    db.execute("BEGIN")
    for s in STATIONS:
        db.execute(
            "INSERT INTO station_state "
            "(station_id, name, current_weight_kg, current_temp_c, "
            "temp_status, status, updated_at) "
            "VALUES (?, ?, ?, ?, 'normal', 'unknown', ?)",
            (s['id'], s['name'], s['initial_weight_kg'],
             s.get('initial_temp_c'), fmt(START)),
        )
    db.execute("COMMIT")

    # Generate all events
    all_events = []
    all_events.extend(gen_heartbeats())
    all_events.extend(gen_weights())
    all_events.extend(gen_temperatures())
    all_events.extend(gen_transactions())
    all_events.extend(gen_bids())
    all_events.extend(gen_weather())
    all_events.extend(gen_alerts())
    all_events.extend(gen_operator_notes())

    # Sort chronologically (by time, then source for determinism)
    all_events.sort(key=lambda e: (e[0], e[1]))

    # Insert events (raw SQL — projections built during replay, not here)
    db.execute("BEGIN")
    for event_time, source, event_type, payload in all_events:
        db.execute(
            "INSERT INTO events (event_time, source, event_type, payload) "
            "VALUES (?, ?, ?, ?)",
            (event_time, source, event_type, json.dumps(payload)),
        )
    db.execute("COMMIT")

    # Print summary
    count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    min_t = db.execute("SELECT MIN(event_time) FROM events").fetchone()[0]
    max_t = db.execute("SELECT MAX(event_time) FROM events").fetchone()[0]
    print(f"Generated {count} events")
    print(f"Time range: {min_t} to {max_t}")
    print()

    rows = db.execute(
        "SELECT event_type, COUNT(*) as n FROM events "
        "GROUP BY event_type ORDER BY n DESC"
    ).fetchall()
    for r in rows:
        print(f"  {r[0]}: {r[1]}")

    db.close()
    print(f"\nDatabase: {DB_PATH}")


if __name__ == '__main__':
    main()
