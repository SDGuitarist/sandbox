import sqlite3
import os
from flask import g

DATABASE = os.environ.get('DATABASE_PATH', 'gymflow.db')


def get_db():
    """Get database connection. Returns a plain connection (NOT a context manager).

    Usage:
        conn = get_db()
        members = get_all_members(conn)
    """
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database from schema.sql."""
    conn = get_db()
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
