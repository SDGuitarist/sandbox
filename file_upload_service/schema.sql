-- File Upload Service Schema

-- files: metadata for each uploaded file
CREATE TABLE IF NOT EXISTS files (
    id               TEXT PRIMARY KEY,          -- UUID v4
    original_filename TEXT NOT NULL,            -- sanitized display name only
    content_type     TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes       INTEGER NOT NULL,
    upload_dir_path  TEXT NOT NULL,             -- absolute path to upload_dir/<id>/
    status           TEXT NOT NULL DEFAULT 'uploaded'
                         CHECK(status IN ('uploaded', 'processing', 'done', 'failed')),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- processing_jobs: one row per processor type per file
CREATE TABLE IF NOT EXISTS processing_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id      TEXT NOT NULL REFERENCES files(id),
    job_type     TEXT NOT NULL CHECK(job_type IN ('thumbnail', 'metadata')),
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts  INTEGER NOT NULL DEFAULT 3,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    claimed_at   TEXT,
    worker_id    TEXT,
    completed_at TEXT,
    error_message TEXT
);

-- Index for efficient worker claim queries
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status_created
    ON processing_jobs(status, created_at);

CREATE INDEX IF NOT EXISTS idx_processing_jobs_file_id
    ON processing_jobs(file_id);

-- file_results: output of each processing job
CREATE TABLE IF NOT EXISTS file_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     TEXT NOT NULL REFERENCES files(id),
    result_type TEXT NOT NULL CHECK(result_type IN ('thumbnail', 'metadata')),
    result_path TEXT,    -- filesystem path (for thumbnail)
    result_json TEXT,    -- JSON string (for metadata)
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_file_results_file_type
    ON file_results(file_id, result_type);
