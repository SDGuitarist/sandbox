CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_name TEXT NOT NULL,
    email TEXT NOT NULL,
    business_name TEXT NOT NULL,
    business_type TEXT NOT NULL,
    team_size TEXT NOT NULL,
    current_workflows TEXT NOT NULL,
    pain_points TEXT NOT NULL,
    tools_used TEXT NOT NULL,
    goals TEXT NOT NULL,
    urgency TEXT NOT NULL,
    submitter_notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'reviewed', 'assessment-ready',
               'audit-scheduled', 'completed', 'declined', 'archived')),
    is_audit_fit INTEGER NOT NULL DEFAULT 0
        CHECK (is_audit_fit IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_submissions_status
    ON submissions(status);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL UNIQUE,
    summary TEXT NOT NULL DEFAULT '',
    bottlenecks TEXT NOT NULL DEFAULT '',
    root_causes TEXT NOT NULL DEFAULT '',
    next_steps TEXT NOT NULL DEFAULT '',
    audit_fit_recommendation TEXT NOT NULL DEFAULT '',
    admin_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_assessments_submission_id
    ON assessments(submission_id);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notes_submission_id
    ON notes(submission_id);
