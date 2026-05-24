import sqlite3

from flask import current_app, g


def init_db(app):
    """Initialize the database. Called once at startup."""
    conn = sqlite3.connect(app.config['DATABASE'], timeout=10)
    conn.execute("PRAGMA journal_mode = WAL")
    with app.open_resource('schema.sql', mode='r') as f:
        conn.executescript(f.read())
    conn.close()


def get_db():
    """Get a request-scoped database connection."""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Close the database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()
