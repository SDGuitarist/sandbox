-- CPAA Shadow Lab Phase 0 — Event Replay Simulator
-- Append-only event log + projection tables for derived state

-- Core event log (append-only, never update or delete)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_events_time ON events(event_time);

-- Projection: per-station current state
CREATE TABLE IF NOT EXISTS station_state (
    station_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    current_weight_kg REAL,
    current_temp_c REAL,
    temp_status TEXT NOT NULL DEFAULT 'normal',
    last_heartbeat TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    updated_at TEXT NOT NULL
);

-- Projection: financial totals (singleton row)
CREATE TABLE IF NOT EXISTS financial_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    total_revenue_cents INTEGER NOT NULL DEFAULT 0,
    transaction_count INTEGER NOT NULL DEFAULT 0,
    total_bids INTEGER NOT NULL DEFAULT 0,
    highest_bid_cents INTEGER NOT NULL DEFAULT 0,
    active_lots INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- Projection: environment readings (singleton row)
CREATE TABLE IF NOT EXISTS environment_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    temperature_c REAL,
    humidity_pct REAL,
    wind_speed_kmh REAL,
    updated_at TEXT NOT NULL
);

-- Projection: event-triggered alerts
CREATE TABLE IF NOT EXISTS active_alerts (
    alert_key TEXT PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    alert_type TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    raised_at TEXT NOT NULL,
    resolved_at TEXT
);

-- Projection cursor: single source of truth for projection progress
CREATE TABLE IF NOT EXISTS replay_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_projected_time TEXT
);
