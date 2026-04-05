-- Distributed Task Scheduler Schema
-- schedules: recurring job definitions with cron expressions
CREATE TABLE IF NOT EXISTS schedules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    cron_expr   TEXT NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',  -- JSON
    status      TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'paused', 'deleted')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    next_run_at TEXT NOT NULL
);

-- Index for efficient scheduler polling: find active schedules due to run
CREATE INDEX IF NOT EXISTS idx_schedules_status_next_run
    ON schedules(status, next_run_at);

-- job_runs: individual executions spawned from schedules
CREATE TABLE IF NOT EXISTS job_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id  INTEGER NOT NULL REFERENCES schedules(id),
    status       TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    payload      TEXT NOT NULL DEFAULT '{}',  -- JSON, copied from schedule at spawn time
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at   TEXT,       -- set when a worker picks up the job
    completed_at TEXT,       -- set when job finishes (success or failure)
    result       TEXT        -- JSON result or error message
);

-- Index for dashboard queries: recent completed runs, pending runs per schedule
CREATE INDEX IF NOT EXISTS idx_job_runs_schedule_status
    ON job_runs(schedule_id, status);

CREATE INDEX IF NOT EXISTS idx_job_runs_completed_at
    ON job_runs(completed_at DESC);
