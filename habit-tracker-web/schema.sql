CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (date('now')),
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    completed_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(habit_id, completed_date)
);

CREATE INDEX IF NOT EXISTS idx_completions_habit_id ON completions(habit_id);
CREATE INDEX IF NOT EXISTS idx_completions_date ON completions(completed_date);
