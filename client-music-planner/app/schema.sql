CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS song (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    artist TEXT NOT NULL DEFAULT '',
    genre TEXT NOT NULL DEFAULT 'other',
    musical_key TEXT NOT NULL DEFAULT '',
    tempo INTEGER,
    energy INTEGER NOT NULL DEFAULT 3 CHECK (energy BETWEEN 1 AND 5),
    duration_seconds INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'wedding',
    venue TEXT NOT NULL DEFAULT '',
    client_name TEXT NOT NULL,
    client_email TEXT NOT NULL DEFAULT '',
    portal_token TEXT UNIQUE NOT NULL,
    client_approved INTEGER NOT NULL DEFAULT 0,
    approved_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    is_archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS playlist_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    song_id INTEGER NOT NULL REFERENCES song(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    is_must_play INTEGER NOT NULL DEFAULT 0,
    is_do_not_play INTEGER NOT NULL DEFAULT 0,
    client_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(event_id, song_id)
);

CREATE TABLE IF NOT EXISTS song_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    artist TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_song_user ON song(user_id);
CREATE INDEX IF NOT EXISTS idx_song_genre ON song(user_id, genre);
CREATE INDEX IF NOT EXISTS idx_song_energy ON song(user_id, energy);
CREATE INDEX IF NOT EXISTS idx_event_user ON event(user_id);
CREATE INDEX IF NOT EXISTS idx_event_token ON event(portal_token);
CREATE INDEX IF NOT EXISTS idx_playlist_event ON playlist_item(event_id);
CREATE INDEX IF NOT EXISTS idx_playlist_position ON playlist_item(event_id, position);
CREATE INDEX IF NOT EXISTS idx_song_request_event ON song_request(event_id);
