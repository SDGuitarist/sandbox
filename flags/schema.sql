CREATE TABLE IF NOT EXISTS flags (
    key             TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    default_enabled INTEGER NOT NULL DEFAULT 0,
    environments    TEXT,
    allowlist       TEXT,
    percentage      INTEGER,
    eval_count      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flag_dependencies (
    flag_key       TEXT NOT NULL REFERENCES flags(key) ON DELETE CASCADE,
    depends_on_key TEXT NOT NULL REFERENCES flags(key) ON DELETE CASCADE,
    PRIMARY KEY (flag_key, depends_on_key)
);
