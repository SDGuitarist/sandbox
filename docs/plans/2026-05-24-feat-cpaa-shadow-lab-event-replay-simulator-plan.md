---
title: "feat: CPAA Shadow Lab Phase 0 — Event Replay Simulator"
type: feat
status: active
date: 2026-05-24
origin: docs/brainstorms/2026-05-24-cpaa-shadow-lab-brainstorm.md
feed_forward:
  risk: "Phase 0 is logical-time only — it proves state derivation from complete history but does NOT test arrival-order bugs, burst handling, or real-time edge conditions. Those are explicitly Phase 1 scope."
  verify_first: true
---

# feat: CPAA Shadow Lab Phase 0 — Event Replay Simulator

## Enhancement Summary

**Deepened on:** 2026-05-24
**Sections enhanced:** 7
**Research agents used:** event-sourcing-best-practices, flask-polling-patterns, timeline-ui-patterns, python-reviewer, performance-oracle, security-sentinel, simplicity-reviewer

### Key Improvements
1. Fixed 2 P0 crash bugs in code examples (sqlite3.Row immutability, replay_state type mixing)
2. Added critical `isolation_level=None` requirement (without it, BEGIN IMMEDIATE fails)
3. Added forward-advance concurrency protection pattern (prevents double-projection)
4. Added security hardening section (debug=False, input validation, vendored Bootstrap)
5. Identified 6 YAGNI removals to simplify Phase 0 scope

### Critical Fixes (from Python + Performance review)
- `get_derived_state()` must convert sqlite3.Row to dicts before mutation — Row objects are read-only
- `replay_state` requires `threading.Lock` OR explicit `threaded=False` in Flask dev server
- `db.py` must set `isolation_level=None` for explicit transaction management
- Forward projection advance needs `BEGIN IMMEDIATE` to prevent concurrent double-projection
- Replace `.fetchall()` with cursor iteration in `rebuild_projections_to()`

### YAGNI Removals (from Simplicity review)
- Remove `chain_id` column — no Phase 0 code uses it. (Note: brainstorm MVP mentions causal chain ID; this is an intentional Phase 0 narrowing, not accidental drift. Re-add in Phase 1 when AI agents need causal tracing.)
- Remove `system.network_status` event type — contradicts the "detect silence" test design
- Remove `resolved_by_event_id` column — causal tracing deferred to Phase 1
- Remove `idx_events_type` and `idx_events_source` indexes — no queries use these patterns
- Remove `VENUE_PROFILE` config dict — inline venue name as string constant
- Remove `/api/scenario/info` endpoint — inline metadata into template via Jinja2

## Overview

Build a replay-only event simulator — a digital twin that replays a scripted 4-hour charity gala from synthetic telemetry data. An append-only event log stores all telemetry, a projection engine derives current state, and a Flask dashboard lets an operator watch the event unfold with replay controls (play, pause, speed up, jump to timestamp). Failure injections (dropped heartbeats, event gaps, temperature breaches) are built into the synthetic data to test silence detection and state model resilience.

This is Phase 0 of the CPAA architecture (see brainstorm: `docs/brainstorms/2026-05-24-cpaa-shadow-lab-brainstorm.md`). It proves the event state model before any AI, MCP servers, or hardware are added.

## Problem Statement

The full CPAA architecture requires a reliable event log and derived state layer that handles async events, stale state, temporal gaps, and failure scenarios. Two Codex reviews identified that the biggest risk is distributed systems thinking — not AI prompting or MCP syntax. Phase 0 isolates that learning by building the state model in a controlled replay environment with known data. (Arrival-order ambiguity and real-time edge conditions are deferred to Phase 1.)

**Success criterion:** You can replay the entire event, inspect any point in time, and explain why the current derived state is what it is from the event history alone.

## Proposed Solution

A single Flask application with four components:

1. **Event log** — SQLite `events` table (append-only) + projection tables for derived state
2. **Replay engine** — Server-side replay clock with client-side polling
3. **Operator dashboard** — Bootstrap 5 layout with state panels, event timeline, and replay controls
4. **Synthetic data generator** — Python script that creates a full 4-hour gala scenario with failure injections

## Technical Approach

### Project Structure

```
cpaa-shadow-lab/
├── app/
│   ├── __init__.py              # Flask factory (create_app)
│   ├── db.py                    # SQLite connection, WAL, init_db
│   ├── models/
│   │   └── events.py            # append_event, get_derived_state, rebuild_projections
│   ├── blueprints/
│   │   └── dashboard/
│   │       └── routes.py        # Dashboard page + API endpoints
│   └── templates/
│       ├── base.html            # Bootstrap 5 base template
│       └── dashboard/
│           └── index.html       # Main dashboard with timeline + replay
├── static/
│   ├── css/
│   │   └── dashboard.css        # Custom dashboard styles
│   └── js/
│       └── replay.js            # Replay engine (controls, polling, timeline)
├── schema.sql                   # Event log + projection tables
├── config.py                    # Event config, replay config, thresholds
├── generate_scenario.py         # Synthetic telemetry generator (run once)
├── run.py                       # Entry point
└── requirements.txt             # Flask + dependencies
```

Follows the intake-dashboard pattern: factory in `__init__.py`, blueprints, pure model functions taking `sqlite3.Connection`, schema in `schema.sql`.

### Event Log Schema

```sql
-- schema.sql

-- Core event log (append-only, never update or delete)
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,           -- YYYY-MM-DD HH:MM:SS (event's logical time)
    source TEXT NOT NULL,               -- e.g. 'station_1', 'pos', 'weather_station'
    event_type TEXT NOT NULL,           -- e.g. 'telemetry.culinary.weight'
    payload TEXT NOT NULL,              -- JSON
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE INDEX idx_events_time ON events(event_time);

-- Projection: per-station current state
CREATE TABLE station_state (
    station_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    current_weight_kg REAL,
    current_temp_c REAL,
    temp_status TEXT NOT NULL DEFAULT 'normal',   -- normal, warning, critical
    last_heartbeat TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',        -- healthy, warning, critical, unknown
    updated_at TEXT NOT NULL
);

-- Projection: financial totals (singleton row)
CREATE TABLE financial_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    total_revenue_cents INTEGER NOT NULL DEFAULT 0,
    transaction_count INTEGER NOT NULL DEFAULT 0,
    total_bids INTEGER NOT NULL DEFAULT 0,
    highest_bid_cents INTEGER NOT NULL DEFAULT 0,
    active_lots INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- Projection: environment readings (singleton row)
CREATE TABLE environment_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    temperature_c REAL,
    humidity_pct REAL,
    wind_speed_kmh REAL,
    updated_at TEXT NOT NULL
);

-- Projection: event-triggered alerts (temp_breach only in Phase 0)
CREATE TABLE active_alerts (
    alert_key TEXT PRIMARY KEY,        -- stable key: '{alert_type}:{source}' (survives rebuilds)
    event_id INTEGER NOT NULL REFERENCES events(id),
    alert_type TEXT NOT NULL,          -- temp_breach (event-triggered alerts only)
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,            -- warning, critical
    raised_at TEXT NOT NULL,
    resolved_at TEXT                   -- NULL if still active
);

-- Projection cursor: single source of truth for projection progress
CREATE TABLE replay_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_projected_time TEXT           -- NULL = projections empty, needs full rebuild
);
```

**Key design rules (from prior learnings):**
- Timestamps: `YYYY-MM-DD HH:MM:SS` format, never ISO8601 with T-separator (SQLite `datetime()` rejects T)
- Money: integer cents, never floats (from CoWorkFlow P1)
- Foreign keys: no CASCADE on event references (from service-mesh-dashboard — CASCADE would delete the audit trail)
- Projections: synchronous upsert, not async workers (from event-sourced audit log lesson)

### Event Type Taxonomy

```
telemetry.culinary.weight        -- { station_id, weight_kg }
telemetry.culinary.temperature   -- { station_id, temp_c }
telemetry.financial.transaction  -- { amount_cents, item, station_id }
telemetry.financial.bid          -- { lot_id, amount_cents, bid_number }
telemetry.environmental.weather  -- { temperature_c, humidity_pct, wind_speed_kmh }
system.heartbeat                 -- { sensor_id, station_id }
system.alert.raised              -- { alert_type, source, message, severity }
system.alert.resolved            -- { alert_key, reason }  # matches active_alerts PK
system.operator_note             -- { note }
```

### Derived State Projection Engine

**How projections work:**

Each event type has a projection handler that upserts the corresponding projection table. Projection handlers are pure functions: `(connection, event) -> None`.

```python
# Conceptual — models/events.py
import json
import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)

PROJECTION_HANDLERS: dict[str, callable] = {
    'telemetry.culinary.weight': project_station_weight,
    'telemetry.culinary.temperature': project_station_temperature,
    'telemetry.financial.transaction': project_financial_transaction,
    'telemetry.financial.bid': project_financial_bid,
    'telemetry.environmental.weather': project_environment,
    'system.heartbeat': project_heartbeat,
    'system.alert.raised': project_alert_raised,
    'system.alert.resolved': project_alert_resolved,
}

def append_event(
    db: sqlite3.Connection,
    event_time: str,
    source: str,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    """Append event and update projections. Commits internally.
    
    REQUIRES: db must have isolation_level=None (explicit transaction mgmt).
    Returns the new event ID.
    """
    db.execute("BEGIN IMMEDIATE")
    try:
        cursor = db.execute(
            "INSERT INTO events (event_time, source, event_type, payload) "
            "VALUES (?, ?, ?, ?)",
            (event_time, source, event_type, json.dumps(payload))
        )
        event_id = cursor.lastrowid
        handler = PROJECTION_HANDLERS.get(event_type)
        if handler:
            handler(db, event_id, event_time, source, payload)
        else:
            logger.warning("No projection handler for event type: %s (event_id=%d)", event_type, event_id)
        db.execute("COMMIT")
        return event_id
    except Exception:
        db.execute("ROLLBACK")
        raise
```

**Critical db.py requirement (from Python review P0):** The connection MUST be created with `isolation_level=None` for explicit transaction management:

```python
# In app/db.py
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            isolation_level=None,  # CRITICAL: enables explicit BEGIN/COMMIT/ROLLBACK
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA busy_timeout=5000")
    return g.db
```

Without `isolation_level=None`, Python's sqlite3 module manages transactions implicitly, and `BEGIN IMMEDIATE` raises `OperationalError: cannot start a transaction within a transaction`.

**Transaction behavior:** `append_event` commits internally (BEGIN IMMEDIATE + COMMIT/ROLLBACK). All other model functions are read-only.

**Replay rebuild:** When the operator jumps backward in time, projections must be rebuilt:

```python
def rebuild_projections_to(db: sqlite3.Connection, target_time: str) -> None:
    """Clear all projections, replay events to target_time, update cursor atomically.
    Commits internally. Uses cursor iteration (O(1) memory).
    
    Called on: backward jump, reset (with target_time=None to clear all).
    """
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("DELETE FROM station_state")
        db.execute("DELETE FROM financial_state")
        db.execute("DELETE FROM environment_state")
        db.execute("DELETE FROM active_alerts")
        if target_time is None:
            # Reset: clear projections and cursor
            db.execute("INSERT OR REPLACE INTO replay_meta (id, last_projected_time) VALUES (1, NULL)")
        else:
            cursor = db.execute(
                "SELECT id, event_time, source, event_type, payload FROM events "
                "WHERE event_time <= ? ORDER BY event_time, id",
                (target_time,)
            )
            for event in cursor:
                handler = PROJECTION_HANDLERS.get(event['event_type'])
                if handler:
                    payload = json.loads(event['payload'])
                    handler(db, event['id'], event['event_time'], event['source'], payload)
            # Atomically update cursor in same transaction
            db.execute(
                "INSERT OR REPLACE INTO replay_meta (id, last_projected_time) VALUES (1, ?)",
                (target_time,)
            )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
```

**Projection cursor contract:**
- `replay_meta.last_projected_time` is the single source of truth.
- `advance_projections(db, t)` reads the cursor, projects events since cursor up to t, updates cursor — all in one `BEGIN IMMEDIATE` transaction.
- `rebuild_projections_to(db, t)` clears all projections, replays from scratch to t, sets cursor to t — all atomic.
- `rebuild_projections_to(db, None)` clears all projections and sets cursor to NULL (used by reset).
- `/api/replay/reset` calls `rebuild_projections_to(db, None)` to clear state.

**Performance note (from Performance review):** At ~1000 events, full rebuild takes ~20-30ms. Cursor iteration keeps memory at O(1) regardless of dataset size. Snapshot optimization is unnecessary until events exceed ~5000.

**Stale heartbeat detection:** A background check (or query-time check) marks stations as `unknown` if their last heartbeat is older than the configured TTL (e.g., 60 seconds in event time). Implemented as a query in `get_derived_state()`:

```python
from datetime import datetime

def parse_time(time_str: str) -> datetime:
    """Parse YYYY-MM-DD HH:MM:SS string to datetime."""
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")

def get_derived_state(
    db: sqlite3.Connection,
    current_time: str,
    heartbeat_ttl_seconds: int = 60,
) -> dict[str, Any]:
    """Return full derived state dict. Read-only, does NOT commit.
    
    IMPORTANT: sqlite3.Row objects are READ-ONLY. Must convert to dicts
    before any mutation (Python review P0 finding).
    """
    # Convert to dicts — sqlite3.Row does not support item assignment
    stations = [dict(row) for row in db.execute("SELECT * FROM station_state").fetchall()]
    
    # Mark stations with stale heartbeats
    current_dt = parse_time(current_time)
    for station in stations:
        if station['last_heartbeat']:
            elapsed = current_dt - parse_time(station['last_heartbeat'])
            if elapsed.total_seconds() > heartbeat_ttl_seconds:
                station['status'] = 'unknown'
    
    financial = db.execute("SELECT * FROM financial_state WHERE id = 1").fetchone()
    environment = db.execute("SELECT * FROM environment_state WHERE id = 1").fetchone()
    
    # Merge event-triggered + absence-derived alerts (see Alert Model section)
    alerts = compute_all_alerts(db, stations, current_time, heartbeat_ttl_seconds)
    
    return {
        'stations': stations,
        'financials': dict(financial) if financial else {},
        'environment': dict(environment) if environment else {},
        'alerts': alerts,
    }
```

### Initial State (at scenario start, before any events)

When the dashboard loads and no replay has started, all panels show baseline values:

- **Stations:** All stations listed with initial weights from config, temp = `n/a` (no readings yet), status = `unknown` (no heartbeats received yet)
- **Financials:** Revenue $0, 0 transactions, 0 bids, all lots at opening bid
- **Environment:** `n/a` for all readings (no weather events yet)
- **Alerts:** Empty
- **Timeline:** Empty, "Press Play to start replay" prompt

The first heartbeat events (at scenario start) transition stations from `unknown` to `healthy`.

### Replay State Machine

```
[Stopped] --play--> [Playing]     (set current_event_time to scenario_start, start clock)
[Stopped] --jump--> [Paused]      (rebuild projections to target, set current_event_time)
[Stopped] --reset--> [Stopped]    (no-op)
[Stopped] --pause--> [Stopped]    (no-op)

[Playing] --pause--> [Paused]     (freeze current_event_time)
[Playing] --play--> [Playing]     (no-op, already playing)
[Playing] --end-of-data--> [Paused]  (auto-pause at scenario_end, status stays 'paused')
[Playing] --jump--> [Paused]      (auto-pause first, then rebuild to target)
[Playing] --reset--> [Stopped]    (clear projections + cursor via rebuild_projections_to(None))
[Playing] --speed--> [Playing]    (update speed, takes effect next poll cycle)

[Paused] --play--> [Playing]      (resume from current_event_time)
[Paused] --jump--> [Paused]       (rebuild projections to target, stay paused)
[Paused] --pause--> [Paused]      (no-op)
[Paused] --reset--> [Stopped]     (clear projections + cursor)
[Paused] --speed--> [Paused]      (update speed for next play)
```

**Design decisions:**
- **No "Complete" state.** End-of-data is just auto-pause. The operator sees the final state and can jump backward or reset. There is no special UI for "complete" — the progress slider is at 100% and the Play button resumes (but immediately re-pauses since there are no more events). This eliminates one state and its transitions.
- **Stopped → jump is allowed.** The operator can jump to any point without pressing Play first. This rebuilds projections and enters Paused.
- **Idempotent actions.** Playing while playing, pausing while paused, resetting while stopped — all no-ops. No error, no state change.
- **Jump during playback auto-pauses first.** Prevents race conditions between the old playback position and the new jump target.
- **Speed persists across pause/resume.** Speed changes take effect on the next poll cycle.
- **At 10x speed**, the polling interval stays at 500ms — the server batches all events in the elapsed window into a single response.

### Replay Engine

**Server-side replay clock** stored as module-level state with threading lock:

```python
import threading
from datetime import datetime, timedelta

_replay_lock = threading.Lock()
_replay_state = {
    'status': 'stopped',           # stopped, playing, paused (no 'complete' — end-of-data is just auto-pause)
    'speed': 1,                    # 1, 2, 5, 10
    'current_event_time': None,    # datetime | None
    'wall_time_at_play': None,     # float (time.time()) | None
    'event_time_at_play': None,    # datetime | None
    'scenario_start': datetime(2026, 6, 15, 18, 0, 0),
    'scenario_end': datetime(2026, 6, 15, 22, 0, 0),
}
# NOTE: Projection progress is tracked in DB (replay_meta.last_projected_time),
# NOT in _replay_state. This is the single source of truth for "how far have
# projections been built." All functions that modify projections update it atomically.
```

**Critical notes (from Python review P0):**
- Flask's dev server defaults to `threaded=True` since Flask 1.0. Concurrent `/api/state` GET and `/api/replay/play` POST will race on `_replay_state` without the lock.
- All mutations must acquire `_replay_lock`. Reads of simple values (status, speed) are safe without lock due to Python's GIL, but read-modify-write (advancing clock) requires it.
- `scenario_start` and `scenario_end` are parsed once as `datetime` objects — never compare `min(datetime, str)` which raises TypeError.
- Run with `app.run(host='127.0.0.1', debug=False, threaded=True)` or use `threaded=False` to avoid lock complexity entirely (acceptable for Phase 0 single-user).

**Current event time calculation:**

```python
import time

def get_current_event_time() -> datetime | None:
    """Calculate current position in event time. Thread-safe."""
    with _replay_lock:
        if _replay_state['status'] != 'playing':
            return _replay_state['current_event_time']
        elapsed_wall = time.time() - _replay_state['wall_time_at_play']
        elapsed_event = elapsed_wall * _replay_state['speed']
        current = _replay_state['event_time_at_play'] + timedelta(seconds=elapsed_event)
        return min(current, _replay_state['scenario_end'])
```

**Projection advance:** On each `/api/state` poll, the route calls `advance_projections(db, current_time_str)` which reads `replay_meta.last_projected_time`, projects new events since that cursor, and atomically updates the cursor — all in one `BEGIN IMMEDIATE` transaction. On backward jump or reset, the route calls `rebuild_projections_to(db, target_time)` or `rebuild_projections_to(db, None)` which clears and rebuilds atomically.

**API endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Render dashboard page (scenario metadata inlined via Jinja2) |
| `/api/state` | GET | Return current derived state + replay position + recent events (batched) |
| `/api/replay/play` | POST | Start/resume replay |
| `/api/replay/pause` | POST | Pause replay |
| `/api/replay/speed` | POST | Set speed (1, 2, 5, 10) |
| `/api/replay/jump` | POST | Jump to specific event time |
| `/api/replay/reset` | POST | Reset to stopped state, clear all projections |

**No separate `/api/timeline` endpoint.** The `/api/state` response includes a `recent_events` array (last 50 events up to current replay time) alongside the derived state. One poll = one request = all dashboard data. Client-side JS filters the timeline by event type locally.

### Alert Model (Two Categories)

Alerts split into two categories with different detection paths:

#### Category 1: Event-Triggered Alerts (materialized)

These are raised and resolved by explicit events in the log (`system.alert.raised`, `system.alert.resolved`). The generator inserts these events at known scenario times.

- **Example:** Temperature breach — the generator emits `system.alert.raised` when temp exceeds threshold, and `system.alert.resolved` when it drops back.
- **Storage:** Materialized in `active_alerts` table by projection handlers for `system.alert.raised` and `system.alert.resolved`.
- **Alert key:** `'{alert_type}:{source}'` (e.g., `'temp_breach:station_1'`). This is the PRIMARY KEY, stable across rebuilds (unlike an AUTOINCREMENT id which changes on every rebuild).
- **Resolution:** The `system.alert.resolved` handler sets `resolved_at` on the matching alert key.

#### Category 2: Absence-Derived Alerts (query-time computed)

These are detected by the *absence* of expected events. They are NOT stored in `active_alerts` — they are computed fresh on every call to `get_derived_state()`.

- **Heartbeat loss:** Station's `last_heartbeat` is older than `heartbeat_ttl_seconds` relative to `current_time`. Derived from `station_state.last_heartbeat`.
- **Network outage:** ALL stations have stale heartbeats simultaneously. Derived from the same staleness check.
- **Auction stall:** No `telemetry.financial.bid` events in the last `auction_stall_minutes`. Derived from a query: `SELECT MAX(event_time) FROM events WHERE event_type = 'telemetry.financial.bid' AND event_time <= ?`.

**Why query-time, not materialized:**
- Absence conditions have no explicit "raise" event — they emerge from silence.
- Materializing them would require a background detector that runs on every poll, writing alert rows and then deleting them on rebuild. This adds write-contention and makes the alert table's contents dependent on polling frequency.
- Query-time derivation is simpler, deterministic, and survives projection rebuilds without special handling.

**`get_derived_state()` returns both types merged:**

```python
def get_derived_state(db, current_time, heartbeat_ttl_seconds=60, auction_stall_minutes=15):
    # ... (existing station/financial/environment reads)
    
    # Event-triggered alerts (from active_alerts table)
    event_alerts = [dict(a) for a in db.execute(
        "SELECT * FROM active_alerts WHERE resolved_at IS NULL"
    ).fetchall()]
    
    # Absence-derived alerts (computed at query time)
    derived_alerts = []
    for station in stations:
        if station['last_heartbeat']:
            elapsed = (parse_time(current_time) - parse_time(station['last_heartbeat'])).total_seconds()
            if elapsed > heartbeat_ttl_seconds:
                derived_alerts.append({
                    'alert_key': f"heartbeat_lost:{station['station_id']}",
                    'alert_type': 'heartbeat_lost',
                    'source': station['station_id'],
                    'message': f"{station['name']} heartbeat lost ({int(elapsed)}s ago)",
                    'severity': 'warning',
                })
    
    # Auction stall check
    last_bid = db.execute(
        "SELECT MAX(event_time) as t FROM events "
        "WHERE event_type = 'telemetry.financial.bid' AND event_time <= ?",
        (current_time,)
    ).fetchone()
    if last_bid and last_bid['t']:
        stall_seconds = (parse_time(current_time) - parse_time(last_bid['t'])).total_seconds()
        if stall_seconds > auction_stall_minutes * 60:
            derived_alerts.append({
                'alert_key': 'auction_stall:global',
                'alert_type': 'auction_stall',
                'source': 'auction',
                'message': f"No bids for {int(stall_seconds // 60)} minutes",
                'severity': 'warning',
            })
    
    all_alerts = event_alerts + derived_alerts
    all_alerts.sort(key=lambda a: (0 if a.get('severity') == 'critical' else 1))
    return { 'stations': stations, ..., 'alerts': all_alerts }
```

**No operator interaction:** Alerts cannot be dismissed in Phase 0. Event-triggered alerts resolve when the generator emits a `system.alert.resolved` event. Absence-derived alerts resolve automatically when the condition clears (heartbeat resumes, bid arrives).

### Replay Semantics: Logical-Time Only (Phase 0 Scope)

**Phase 0 is a logical-time replay.** All events are pre-loaded and queried by `event_time`. The replay engine asks: "given the complete event history up to time T, what is the correct derived state?" It does NOT simulate real-time arrival-order behavior.

**What this means for failure injections:**

| Injection | What Phase 0 actually tests | What it does NOT test |
|-----------|----------------------------|---------------------|
| Dropped heartbeat | Absence detection: state correctly shows UNKNOWN when heartbeat gap exceeds TTL | Real sensor going offline mid-stream |
| Temp breach | Event-triggered alert raised/resolved correctly by projection handlers | Real sensor threshold crossing |
| Network outage (event gap) | Absence detection: all stations go UNKNOWN during gap, state recovers after gap ends | Buffered burst arrival, network reconnect handling |
| Auction stall | Absence detection: query correctly identifies bid gap exceeding threshold | Real auction platform failure |
| ~~Delayed event~~ | **Removed from Phase 0** | Arrival-order bugs require real-time event insertion (Phase 1+) |

**Key design decision:** The "delayed event" injection (originally: event with `event_time = 21:00` but `created_at = 21:00:45`) is **removed from Phase 0**. In a pre-loaded logical-time replay, all events are sorted by `event_time` regardless of `created_at`. There is no moment where the system "doesn't know" about the event yet — it's already in the table. Testing arrival-order bugs requires a real-time insertion model (background thread or external producer), which is Phase 1+ scope.

**The `created_at` column is retained** in the schema for future use (Phase 1 will add arrival-time semantics), but Phase 0 ignores it for projection ordering.

**What Phase 0 proves:** The state model correctly handles temporal gaps (silence detection) and event-triggered state changes. It does NOT prove that the system handles arrival-order ambiguity, which is deferred to Phase 1 when real-time event insertion is introduced.

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  CPAA Shadow Lab                                    Phase 0     │
├─────────────────────────────────────────────────────────────────┤
│  Replay: 19:45:23 / 22:00:00    Speed: [1x] [2x] [5x] [10x]  │
│  [Play] [Pause] [Reset]                                        │
│  ══════════════════●══════════════════════════════              │
│  18:00            19:45                          22:00          │
├───────────────────────┬─────────────────────────────────────────┤
│  STATIONS             │  EVENT TIMELINE                         │
│  ┌─────────────────┐  │  19:45:23 [ALERT] Station 2 temp high  │
│  │ Ceviche Bar     │  │  19:44:50 [SALE]  POS txn #47 $45.00  │
│  │ Wt: 4.2kg       │  │  19:44:12 [BEAT]  Station 1 OK        │
│  │ Tmp: 3.1C       │  │  19:43:30 [BID]   Lot #5 $2,500       │
│  │ ● Healthy       │  │  19:42:15 [ENV]   Wind 18 km/h        │
│  └─────────────────┘  │  19:41:00 [BEAT]  Station 2 OK        │
│  ┌─────────────────┐  │  ...                                   │
│  │ Taco Station    │  │                                        │
│  │ Wt: 1.1kg       │  │  Filter: [All] [Alerts] [Financial]   │
│  │ Tmp: n/a        │  │                                        │
│  │ ● Healthy       │  │                                        │
│  └─────────────────┘  │                                        │
├───────────────────────┤                                        │
│  ENVIRONMENT          │                                        │
│  Temp: 21.3C          │                                        │
│  Humidity: 68%        │                                        │
│  Wind: 18 km/h        │                                        │
├───────────────────────┤                                        │
│  FINANCIALS           │                                        │
│  Revenue: $12,450     │                                        │
│  Txns: 47             │                                        │
│  Bids: 23             │                                        │
│  Top Bid: $2,500      │                                        │
├───────────────────────┤                                        │
│  ACTIVE ALERTS        │                                        │
│  ! Station 2 temp     │                                        │
│    high (8.2C)        │                                        │
└───────────────────────┴─────────────────────────────────────────┘
```

- **Left column (col-md-4):** Current state panels — stations, environment, financials, active alerts
- **Right column (col-md-8):** Event timeline (scrollable, filterable by type)
- **Top bar:** Replay controls + progress slider
- Bootstrap 5.3.3 vendored in `static/vendor/` (no CDN — see Security Hardening)
- Station status colors: green (healthy), yellow (warning), red (critical), gray (unknown)

### Client-Side Replay Engine (replay.js)

```javascript
// Conceptual — static/js/replay.js

const POLL_INTERVAL_MS = 500;
let pollTimer = null;

async function pollState() {
    const res = await fetch('/api/state');
    const data = await res.json();
    updateStatePanel(data.stations, data.financials, data.environment, data.alerts);
    updateReplayPosition(data.replay);
    updateTimeline(data.recent_events);
}

function play() { fetch('/api/replay/play', { method: 'POST' }); startPolling(); }
function pause() { fetch('/api/replay/pause', { method: 'POST' }); stopPolling(); }
function setSpeed(s) { fetch('/api/replay/speed', { method: 'POST', body: JSON.stringify({speed: s}) }); }
function jumpTo(t) { fetch('/api/replay/jump', { method: 'POST', body: JSON.stringify({time: t}) }); }

function startPolling() { pollTimer = setInterval(pollState, POLL_INTERVAL_MS); }
function stopPolling() { clearInterval(pollTimer); pollTimer = null; }
```

**Timeline source:** The `data.recent_events` array from `/api/state` contains the last 50 events up to the current replay position. Client-side filtering by type category (All, Alerts, Financial, Telemetry, System) — no server round-trip needed.

**Progress slider:** HTML range input bound to scenario start/end times. On change, sends `/api/replay/jump` request.

### Synthetic Data Generator

`generate_scenario.py` creates a complete 4-hour gala scenario and populates the SQLite database.

**Scenario structure:**

```python
SCENARIO = {
    'venue': 'WILDCOAST Baja Bash (simulated)',
    'start': '2026-06-15 18:00:00',
    'end': '2026-06-15 22:00:00',
    'stations': [
        {'id': 'station_1', 'name': 'Ceviche Bar', 'initial_weight_kg': 8.0, 'has_temp_sensor': True},
        {'id': 'station_2', 'name': 'Taco Station', 'initial_weight_kg': 10.0, 'has_temp_sensor': False},
        {'id': 'station_3', 'name': 'Dessert Table', 'initial_weight_kg': 6.0, 'has_temp_sensor': False},
    ],
    'auction_lots': [
        {'id': 'lot_1', 'name': 'Surf Trip Package', 'opening_bid_cents': 50000},
        {'id': 'lot_2', 'name': 'Private Chef Dinner', 'opening_bid_cents': 30000},
        {'id': 'lot_3', 'name': 'Art Print Collection', 'opening_bid_cents': 20000},
    ],
    'heartbeat_interval_seconds': 30,
}
```

**Event generation pattern:**
- Station weights: gradual decline every 5-10 minutes, with occasional replenishment bumps
- Temperature: Ceviche Bar starts at 2C, drifts toward ambient over 4 hours
- POS transactions: random interval (1-5 min), amounts $15-$200
- Auction bids: clustered (flurry then stall pattern), increasing amounts per lot
- Environment: gradual temperature drop (marine layer), humidity rise, wind variation
- Heartbeats: every 30 seconds per station/sensor
- Operator notes: 2-3 manual entries at key moments

**Failure injections (hardcoded into the scenario timeline):**

| Time | Injection | What It Tests | Expected Behavior |
|------|-----------|---------------|-------------------|
| 19:15-19:18 | Station 2 heartbeat drops for 3 min | Absence detection (single station) | Status → UNKNOWN after 60s TTL, resolves when heartbeats resume |
| 19:45 | Ceviche Bar temp spikes to 8.2C | Event-triggered alert | `system.alert.raised` event fires, alert_key `temp_breach:station_1` materialized |
| 20:00-20:15 | No events from any source for 15 min | Absence detection (all stations) | All stations → UNKNOWN within 60s of last heartbeat each |
| 20:30-20:50 | No bid events for 20 min | Absence detection (auction stall) | Query-time alert when gap exceeds `auction_stall_minutes` |

**Removed:** "Delayed event / out-of-order arrival" — requires real-time insertion semantics (Phase 1+). See "Replay Semantics" section.

**Generator output:** Populates the SQLite database directly. Run once before starting the Flask app: `python generate_scenario.py`

### Configuration

```python
# config.py — immutable config (tuples, not lists — from prior learning commit 464b8a6)

EVENT_CONFIG = {
    'scenario_start': '2026-06-15 18:00:00',
    'scenario_end': '2026-06-15 22:00:00',
    'heartbeat_ttl_seconds': 60,
    'temp_warning_c': 5.0,
    'temp_critical_c': 7.0,
    'auction_stall_minutes': 15,
}

REPLAY_CONFIG = {
    'default_speed': 1,
    'allowed_speeds': (1, 2, 5, 10),  # tuple — immutable
    'poll_interval_ms': 500,
}
```

Venue name is inlined as a constant in `base.html` template ("CPAA Shadow Lab — WILDCOAST Baja Bash"). No `VENUE_PROFILE` dict needed (YAGNI — from simplicity review).

These are the "explicit seams" from the brainstorm — configuration data separated from control logic. In Phase 0, they are simple Python dicts with immutable sequences. Not a full config framework (see brainstorm: "design awareness, not premature abstraction").

### Implementation Phases

#### Phase A: Schema + Models (~50-80 lines)

- Write `schema.sql` with events table and projection tables
- Write `app/db.py` following intake-dashboard pattern (WAL, busy_timeout=5000)
- Write `app/models/events.py` with `append_event()`, projection handlers, `rebuild_projections_to()`, `get_derived_state()`
- Write basic tests for append + projection

**Deliverable:** Can insert events and query derived state from Python REPL.

#### Phase B: Synthetic Data Generator (~80-100 lines)

- Write `config.py` with event config and replay config
- Write `generate_scenario.py` that creates the full 4-hour scenario
- Include all 4 failure injections at specified times
- Verify: run generator, inspect event count and timeline coverage

**Deliverable:** SQLite database populated with ~500-1000 events covering 18:00-22:00.

#### Phase C: Flask App + API (~60-80 lines)

- Write `app/__init__.py` factory
- Write `app/blueprints/dashboard/routes.py` with all API endpoints
- Implement server-side replay clock
- Wire replay controls to projection engine (advance forward, rebuild on jump-back)

**Deliverable:** API returns correct state at any replay position via curl.

#### Phase D: Dashboard UI (~100-120 lines)

- Write `app/templates/base.html` (Bootstrap 5 base)
- Write `app/templates/dashboard/index.html` (layout with panels)
- Write `static/js/replay.js` (polling, controls, timeline updates)
- Write `static/css/dashboard.css` (status colors, timeline styling)

**Deliverable:** Full working dashboard with replay controls in browser.

#### Phase E: Failure Injection Verification (~30 lines)

- Replay through each failure injection point
- Verify correct state transitions (UNKNOWN status, event-triggered alerts, absence-derived alerts)
- Fix any projection bugs discovered during verification

**Deliverable:** All 4 failure scenarios produce correct derived state.

## Alternative Approaches Considered

1. **Client-side replay (all events loaded in browser, JS renders state)** — Rejected because it doesn't exercise the append-only log or projection patterns that later phases depend on. The whole point of Phase 0 is to validate the server-side state model.

2. **Real-time event insertion (background thread inserts events as replay progresses)** — Rejected for Phase 0. Adds threading complexity without teaching a different lesson. The pre-loaded approach still tests projection patterns via `rebuild_projections_to()`.

3. **Postgres instead of SQLite** — Rejected for sandbox track. SQLite is the repo standard, simpler to set up, and sufficient for single-writer replay. Postgres is deferred to the production track (Phase 3+).

(See brainstorm for full architecture alternatives: general-purpose AI actuation, full CRM access, software-only kill switch — all rejected with rationale.)

## System-Wide Impact

### Interaction Graph

Minimal — Phase 0 is a standalone prototype with no external integrations.

- `generate_scenario.py` writes to SQLite → Flask reads from SQLite
- Dashboard JS polls `/api/state` → route calls `get_derived_state()` → reads projection tables
- Replay control JS posts to `/api/replay/*` → route updates in-memory replay state → next poll reflects new position

### Error Propagation

- Generator failure: script exits, no partial data (runs in a single transaction)
- Projection handler failure: ROLLBACK in `append_event()`, event not persisted
- API endpoint failure: Flask returns 500, client retries on next poll interval
- Replay jump-backward failure: ROLLBACK in `rebuild_projections_to()`, projections unchanged

### State Lifecycle Risks

- **Jump-backward rebuild:** Deletes all projection rows and replays from scratch. If this fails mid-rebuild, projections are empty. Mitigated by wrapping in BEGIN IMMEDIATE + ROLLBACK on error.
- **Projection cursor vs event log:** In Phase 0 (logical-time replay), all events are pre-loaded and ordered by `event_time`. There are no arrival-order surprises. The only scenario where projections might lag is during forward advance if a poll races with another poll — mitigated by `BEGIN IMMEDIATE` serialization in `advance_projections()`.
- **Replay clock drift:** In-memory replay state is lost on server restart. Acceptable for Phase 0 (single-user prototype).

### API Surface Parity

No other interfaces expose equivalent functionality. Phase 0 is self-contained.

### Integration Test Scenarios

1. Generate scenario → start Flask → play replay → verify state at 19:00, 20:00, 21:00 matches expected values
2. Jump to 19:45 (temp breach) → verify `temp_breach:station_1` alert in active_alerts → jump to 18:00 → verify alert gone after rebuild (cursor correctly reset)
3. Play through network outage (20:00-20:15) → verify all stations go UNKNOWN via query-time absence detection → advance past 20:15 → verify states recover
4. Play at 10x speed from start to end → verify final state matches full scenario totals → verify replay_meta.last_projected_time = scenario_end
5. Pause → jump backward → resume → verify replay_meta cursor matches jump target, no stale projections from pre-jump position

## Acceptance Tests

### Happy Path
- WHEN the operator loads the dashboard THE SYSTEM SHALL display the stopped state with all stations status UNKNOWN (no heartbeats yet), zero revenue, and empty timeline
- WHEN the operator presses Play THE SYSTEM SHALL advance the replay clock at the selected speed and update state panels every 500ms
- WHEN the operator changes speed to 10x THE SYSTEM SHALL advance event time at 10x wall clock speed
- WHEN the operator pauses replay THE SYSTEM SHALL freeze the current event time and stop state updates
- WHEN the operator drags the progress slider to 20:30 THE SYSTEM SHALL rebuild projections to that time and display the correct derived state

### Failure Injection Scenarios
- WHEN Station 2 heartbeat is missing for more than 60 seconds THE SYSTEM SHALL display station status as UNKNOWN (gray) and return a query-time heartbeat_lost alert in the alerts array
- WHEN Ceviche Bar temperature exceeds 7.0C THE SYSTEM SHALL display station temp_status as critical (red) and materialize a temp_breach alert in active_alerts with key 'temp_breach:station_1'
- WHEN no events arrive for 15 minutes (network outage at 20:00) THE SYSTEM SHALL mark all stations as UNKNOWN within 60 seconds of their respective last heartbeats
- WHEN the replay advances past 20:15 (events resume) THE SYSTEM SHALL process the resumed events and restore station states to healthy as heartbeats arrive
- WHEN no bid events arrive for more than 15 minutes THE SYSTEM SHALL return a query-time auction_stall alert in the alerts array

### Edge Cases
- WHEN the replay clock reaches scenario_end (22:00:00) THE SYSTEM SHALL auto-pause (status → paused) and display final derived state
- WHEN the operator jumps backward from 21:00 to 19:00 THE SYSTEM SHALL call rebuild_projections_to('2026-06-15 19:00:00'), atomically updating the cursor, and display correct state at 19:00
- WHEN the operator resets replay THE SYSTEM SHALL call rebuild_projections_to(None), clearing all projections and the cursor, and return to stopped state
- WHEN the operator jumps from stopped state THE SYSTEM SHALL rebuild projections to the target time and enter paused state
- WHEN the operator presses Play while already playing THE SYSTEM SHALL do nothing (idempotent)
- WHEN the operator presses Pause while in stopped state THE SYSTEM SHALL do nothing (idempotent)

### Verification Commands

```bash
# Generate scenario data
python generate_scenario.py

# Start the app
python run.py

# Verify event count
sqlite3 instance/shadow_lab.db "SELECT COUNT(*) FROM events;"
# Expected: 500-1000

# Verify scenario time range
sqlite3 instance/shadow_lab.db "SELECT MIN(event_time), MAX(event_time) FROM events;"
# Expected: 2026-06-15 18:00:00 | 2026-06-15 22:00:00

# Verify projections after full replay
sqlite3 instance/shadow_lab.db "SELECT * FROM financial_state;"
# Expected: total_revenue_cents > 0, transaction_count > 0

# API smoke test (state at scenario start)
curl -s http://127.0.0.1:5000/api/state | python -m json.tool
# Expected: JSON with stations, financials, environment, alerts, replay position

# Replay control test
curl -s -X POST http://127.0.0.1:5000/api/replay/jump -H 'Content-Type: application/json' -d '{"time":"2026-06-15 19:45:00"}'
curl -s http://127.0.0.1:5000/api/state | python -m json.tool
# Expected: state at 19:45 with temp_breach alert active
```

## What Must NOT Change

- No modifications to any existing sandbox projects (intake-dashboard, notes-api, etc.)
- No external API calls (Phase 0 is fully offline)
- No AI/LLM integration (that's Phase 1)
- No authentication (single-user prototype)
- No real PII or donor data (synthetic only)

## Dependencies & Prerequisites

- Python 3.10+, Flask, SQLite3 (all available)
- No external packages beyond Flask ecosystem
- No vendor API credentials needed
- No hardware needed

## Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Jump-backward rebuild too slow for large event logs | Medium | Low (Phase 0 has ~1000 events) | Acceptable for Phase 0. If slow, add incremental rebuild in Phase 1. |
| Absence-detection query cost at high speed | Medium | Low | Each poll runs 1 extra query (auction stall check). At ~1000 events with idx_events_time index, <1ms. Monitor in Phase 1 if dataset grows. |
| Replay clock drift between server and client | Low | Low | Client polls frequently (500ms). Drift is bounded by poll interval. |
| In-memory replay state lost on server restart | Certain | Low | Acceptable for Phase 0. Add persistence in Phase 1 if needed. |
| Bootstrap timeline UI inadequate for event volume | Medium | Low | Phase 0 has ~1000 events. Paginate timeline, show only recent N events near current position. |

## Plan Quality Gate

1. **What exactly is changing?** Adding a new project `cpaa-shadow-lab/` with a Flask app that replays synthetic event data through an append-only log with projections and a Bootstrap dashboard.
2. **What must not change?** All existing sandbox projects. No external API calls, no AI integration, no real data.
3. **How will we know it worked?** Verification commands above pass. All 4 failure injection scenarios produce correct state transitions. Operator can replay, pause, jump, and explain derived state from the event history.
4. **What is the most likely way this plan is wrong?** The absence-derived alert model (query-time heartbeat/stall detection) may have subtle timing bugs: during a `rebuild_projections_to()` call, if a concurrent poll reads empty projections mid-rebuild and derives false alerts. Mitigated by `BEGIN IMMEDIATE` serialization (the poll's `advance_projections()` will block until rebuild commits), but untested at this point.

## Feed-Forward

- **Hardest decision:** Scoping Phase 0 as logical-time-only replay and explicitly deferring arrival-order testing to Phase 1. The original plan claimed to test "buffered burst" and "late arrival" scenarios, but pre-loaded events sorted by `event_time` cannot actually exercise those code paths. Codex caught this — honesty about what Phase 0 does and doesn't prove is more valuable than false confidence.
- **Rejected alternatives:** Client-side replay (skips server-side state model validation), background-thread insertion (would enable arrival-order testing but adds threading complexity disproportionate to Phase 0's learning goals).
- **Least confident:** Whether absence-detection via query-time computation (heartbeat staleness, auction stall) will perform acceptably when the dashboard is polling every 500ms at 10x speed. Each poll runs 2 extra queries against the events table. At ~1000 events this is fast, but the pattern doesn't scale to Phase 1's larger datasets without caching or event-count optimization.

## Security Hardening (Phase 0 — minimal effort, prevents bad patterns)

**From Security review — fix these in implementation, not later:**

1. **`debug=False` explicitly** — Flask debug mode enables Werkzeug interactive debugger with arbitrary code execution. Even on localhost, DNS rebinding attacks can reach it.
   ```python
   # run.py
   app = create_app()
   app.run(host='127.0.0.1', debug=False)
   ```

2. **Input validation on POST endpoints** — Unvalidated speed/time values cause crashes:
   ```python
   @bp.route('/api/replay/speed', methods=['POST'])
   def set_speed():
       data = request.get_json(silent=True)
       if data is None:
           return jsonify({"error": "Request body must be valid JSON"}), 400
       speed = data.get('speed')
       if speed not in REPLAY_CONFIG['allowed_speeds']:
           return jsonify({"error": f"speed must be one of {REPLAY_CONFIG['allowed_speeds']}"}), 400
       # proceed
   ```

3. **Content-Type enforcement** — Reject non-JSON requests on POST endpoints:
   ```python
   if not request.is_json:
       return jsonify({"error": "Content-Type must be application/json"}), 415
   ```

4. **Vendor Bootstrap files** — Download `bootstrap.min.css` and `bootstrap.bundle.min.js` into `static/vendor/`. Eliminates CDN supply chain risk (polyfill.io incident 2024). Simplifies CSP to `default-src 'self'`.

5. **Add security headers:**
   ```python
   @app.after_request
   def set_security_headers(response):
       response.headers['Content-Security-Policy'] = "default-src 'self'"
       response.headers['X-Content-Type-Options'] = 'nosniff'
       response.headers['X-Frame-Options'] = 'DENY'
       return response
   ```

## Research Insights (from parallel research agents)

### Event Sourcing with SQLite
- At 1000 events, full rebuild takes ~20-30ms. Snapshot optimization unnecessary until >5000 events.
- `orjson` is 2-4x faster than stdlib `json` for payload parsing — consider if rebuild latency matters.
- Never use `json_extract()` in SQL hot paths — parse JSON in Python instead.
- `synchronous=NORMAL` (WAL default) risks losing last committed txns on OS crash (not process crash). Acceptable for Phase 0.

### Flask Polling Patterns
- Module-level dict + `threading.Lock` is the correct pattern for shared mutable state in Flask.
- One batched `/api/state` endpoint is simpler than multiple parallel fetches.
- Adaptive polling: at 1x speed, poll every 2000ms; at 10x, keep 500ms. Reduces server load 75%.
- Exponential backoff on poll errors (500ms → 1s → 2s → 4s, capped at 10s).

### Timeline UI Patterns
- **Vertical scrollable list** with Bootstrap `list-group` — simpler than horizontal timeline, works for 50-200 events.
- **Auto-scroll:** Track `userIsScrolling` boolean. Only auto-scroll to latest event when user hasn't scrolled up manually.
- **Progress slider:** Guard with `isDragging` flag — don't programmatically update `slider.value` while user is dragging.
- **Speed controls:** Discrete buttons in `btn-group`, not a continuous slider. Highlight active speed with `.active`.
- **Status colors:** Use Bootstrap contextual classes directly — `text-bg-success`, `text-bg-warning`, `text-bg-danger`, `text-bg-secondary`.
- **Client-side filtering:** Store event type on each `list-group-item` as `data-event-type`. Toggle `display: none` on filter button click.

### Forward Projection Advance

`advance_projections()` is the function called on each poll to project new events. It reads the cursor from `replay_meta`, projects events since cursor up to the current replay time, and atomically updates the cursor. See `rebuild_projections_to()` in the main Projection Engine section for the full cursor contract. Both functions use `BEGIN IMMEDIATE` and update `replay_meta.last_projected_time` in the same transaction.

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-05-24-cpaa-shadow-lab-brainstorm.md](docs/brainstorms/2026-05-24-cpaa-shadow-lab-brainstorm.md) — Key decisions carried forward: AI as bounded advisor (not controller), append-only event log (not mutable state dict), Phase 0 is replay-only (no AI/MCP/hardware).

### Internal References

- Flask factory pattern: `intake-dashboard/app/__init__.py`
- SQLite WAL + db.py pattern: `intake-dashboard/app/db.py:5-26`
- Bootstrap base template: `intake-dashboard/app/templates/base.html`
- Event-sourced audit log lesson: `docs/solutions/2026-04-05-event-sourced-audit-log.md` — synchronous projection, cursor pagination, timestamp format
- Service mesh dashboard lesson: `docs/solutions/2026-04-05-service-mesh-dashboard.md` — ON DELETE SET NULL for audit logs, TOCTOU in auth
- Client intake dashboard lesson: `docs/solutions/2026-05-23-client-intake-dashboard-15-agent-swarm-build.md` — CSRF parentheses, cross-file flow bugs, BEGIN IMMEDIATE pattern
- CoWorkFlow lesson: `docs/solutions/2026-05-22-coworkflow-22-agent-swarm-build.md` — integer cents for money, CSRF in Jinja2

### Codex Review History

- Original architecture review: `docs/handoffs/2026-05-23-cpaa-codex-pre-brainstorm.md` — 3 P0s, 8 P1s, 1 Insight
- Revised architecture: `docs/handoffs/2026-05-24-cpaa-revised-architecture.md` — all P0s resolved
- Verification pass: all P0s RESOLVED, 6 new carry-forwards → addressed in brainstorm
