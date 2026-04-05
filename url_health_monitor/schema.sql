-- URL Health Monitor Schema

-- monitored_urls: registered URLs to check
CREATE TABLE IF NOT EXISTS monitored_urls (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    url                     TEXT NOT NULL,
    name                    TEXT NOT NULL,
    check_interval_seconds  INTEGER NOT NULL DEFAULT 300,
    failure_threshold       INTEGER NOT NULL DEFAULT 1,
    timeout_seconds         INTEGER NOT NULL DEFAULT 10,
    current_status          TEXT NOT NULL DEFAULT 'unknown'
                                CHECK(current_status IN ('healthy', 'degraded', 'unknown', 'deleted')),
    last_checked_at         TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

-- check_jobs: individual health check tasks dispatched by the scheduler
CREATE TABLE IF NOT EXISTS check_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id       INTEGER NOT NULL REFERENCES monitored_urls(id),
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at   TEXT,
    worker_id    TEXT,
    completed_at TEXT
);

-- Efficient claim query: pending jobs ordered by creation time
CREATE INDEX IF NOT EXISTS idx_check_jobs_status_created
    ON check_jobs(status, created_at);

-- check_results: outcomes of each health check
CREATE TABLE IF NOT EXISTS check_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id           INTEGER NOT NULL REFERENCES check_jobs(id),
    url_id           INTEGER NOT NULL REFERENCES monitored_urls(id),
    http_status_code INTEGER,           -- NULL if connection error
    response_time_ms INTEGER,           -- NULL if connection error
    error_message    TEXT,              -- NULL on success
    checked_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Efficient recent-results query for status update
CREATE INDEX IF NOT EXISTS idx_check_results_url_checked
    ON check_results(url_id, checked_at);
