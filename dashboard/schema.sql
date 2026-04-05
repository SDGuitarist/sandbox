CREATE TABLE IF NOT EXISTS services (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    url             TEXT,
    health_check_url TEXT NOT NULL,
    description     TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id          TEXT PRIMARY KEY,
    prefix      TEXT NOT NULL,
    key_hash    TEXT NOT NULL,
    salt        TEXT NOT NULL,
    label       TEXT NOT NULL,
    service_id  TEXT REFERENCES services(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    last_used_at TEXT,
    revoked     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(prefix);

CREATE TABLE IF NOT EXISTS health_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id      TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    checked_at      TEXT NOT NULL,
    status          TEXT NOT NULL,
    status_code     INTEGER,
    response_time_ms INTEGER,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_health_results_service ON health_results(service_id, id DESC);

CREATE TABLE IF NOT EXISTS health_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id      TEXT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending',
    scheduled_at    TEXT NOT NULL,
    claimed_at      TEXT,
    worker_id       TEXT,
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_health_jobs_pending ON health_jobs(status, scheduled_at);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    -- SET NULL preserves the audit record when a service is deleted;
    -- CASCADE would delete the service.deleted event itself.
    service_id  TEXT REFERENCES services(id) ON DELETE SET NULL,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_id ON events(id);
CREATE INDEX IF NOT EXISTS idx_events_service ON events(service_id, id);
