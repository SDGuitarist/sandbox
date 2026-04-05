import sqlite3
from flask import g

DATABASE = 'webhooks.db'

SCHEMA = """
CREATE TABLE IF NOT EXISTS webhooks (
    id           TEXT PRIMARY KEY,
    url          TEXT NOT NULL,
    secret       TEXT NOT NULL,
    events       TEXT NOT NULL,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deliveries (
    id              TEXT PRIMARY KEY,
    webhook_id      TEXT NOT NULL REFERENCES webhooks(id),
    event_type      TEXT NOT NULL,
    payload         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    attempt_count   INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_error      TEXT,
    worker_id       TEXT,
    claimed_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_deliveries_status_next ON deliveries(status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_webhook ON deliveries(webhook_id, created_at);
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
