CREATE TABLE IF NOT EXISTS events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  idempotency_key TEXT NOT NULL UNIQUE,
  logical_ts TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  source TEXT NOT NULL,
  appended_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(logical_ts, event_id);

CREATE TABLE IF NOT EXISTS replay_runs (
  run_id TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('PENDING','RUNNING','COMPLETE_PASS','ABORTED')),
  events_applied INTEGER NOT NULL DEFAULT 0,
  projection_hash TEXT,
  live_hash_pre TEXT,
  live_hash_post TEXT,
  reset_done INTEGER NOT NULL DEFAULT 0,
  started_at TEXT,
  finished_at TEXT,
  CHECK (status != 'COMPLETE_PASS' OR projection_hash IS NOT NULL),
  CHECK (status != 'RUNNING' OR started_at IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON replay_runs(status);

CREATE TABLE IF NOT EXISTS station_state (
  station_id TEXT PRIMARY KEY,
  weight_kg REAL,
  temp_c REAL,
  status TEXT,
  last_heartbeat TEXT,
  sales_total_cents INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS auction_state (
  lot_id TEXT PRIMARY KEY,
  bid_high_cents INTEGER NOT NULL DEFAULT 0,
  bid_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS environmental_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  temperature_c REAL,
  humidity_pct REAL,
  wind_speed_kmh REAL
);
CREATE TABLE IF NOT EXISTS system_state (
  k TEXT PRIMARY KEY,
  v TEXT
);

CREATE TABLE IF NOT EXISTS projection_snapshots (
  run_id TEXT NOT NULL,
  table_name TEXT NOT NULL,
  pk TEXT NOT NULL,
  row_json TEXT NOT NULL,
  PRIMARY KEY (run_id, table_name, pk),
  FOREIGN KEY (run_id) REFERENCES replay_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dedup_counters (
  kind TEXT PRIMARY KEY CHECK (kind IN ('dup_exact','dup_conflict')),
  count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS anomalies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT,
  kind TEXT NOT NULL CHECK (kind IN ('dup_conflict','unknown_key','malformed_payload')),
  idempotency_key TEXT,
  detail TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (run_id) REFERENCES replay_runs(run_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS determinism_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_a TEXT NOT NULL,
  run_b TEXT NOT NULL,
  match INTEGER NOT NULL CHECK (match IN (0,1)),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS determinism_diffs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  result_id INTEGER NOT NULL REFERENCES determinism_results(id) ON DELETE CASCADE,
  table_name TEXT,
  pk TEXT,
  key TEXT,
  value_a TEXT,
  value_b TEXT
);
