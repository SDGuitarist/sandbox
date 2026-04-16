PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    bio         TEXT,
    location    TEXT,
    email       TEXT,
    profile_url TEXT NOT NULL,
    activity    TEXT,
    source      TEXT NOT NULL,
    scraped_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now')),
    UNIQUE(source, profile_url)
);
