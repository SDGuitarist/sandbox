import sqlite3
from flask import g, current_app


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    conn = get_db()
    conn.execute('PRAGMA journal_mode=WAL')
    schema_path = current_app.root_path + '/../schema.sql'
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
