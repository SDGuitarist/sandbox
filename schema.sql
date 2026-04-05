PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id   TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL,
    actor       TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_entity
    ON events(entity_id, created_at);

CREATE INDEX IF NOT EXISTS idx_events_type_time
    ON events(entity_type, event_type, created_at);

CREATE TABLE IF NOT EXISTS projections (
    entity_id   TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    state       TEXT NOT NULL,
    version     INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);
