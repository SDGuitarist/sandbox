CREATE TABLE IF NOT EXISTS source_events (
  seq INTEGER PRIMARY KEY,
  idempotency_key TEXT NOT NULL,
  logical_ts TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  source TEXT NOT NULL
);
