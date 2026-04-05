CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL,
    checksum    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS migrations_lock (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    locked_at   TEXT NOT NULL,
    locked_by   TEXT NOT NULL
);
