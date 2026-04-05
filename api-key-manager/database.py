import sqlite3
from flask import g

DATABASE = 'apikeys.db'

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id              TEXT PRIMARY KEY,
    key_hash        TEXT NOT NULL,
    key_salt        TEXT NOT NULL,
    prefix          TEXT NOT NULL,
    name            TEXT NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    rate_limit_rpm  INTEGER NOT NULL DEFAULT 60,
    window_count    INTEGER NOT NULL DEFAULT 0,
    window_start    TIMESTAMP,
    total_requests  INTEGER NOT NULL DEFAULT 0,
    last_used_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(prefix);
"""


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, timeout=10)
        result = g.db.execute('PRAGMA journal_mode=WAL').fetchone()
        if result[0] != 'wal':
            raise RuntimeError(f"SQLite WAL mode could not be enabled (got: {result[0]})")
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        db.commit()
