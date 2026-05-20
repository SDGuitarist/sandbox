import sqlite3
from flask import g, current_app
import click


def get_db():
    """Returns the request-scoped database connection.
    Usage:
        conn = get_db()
        venues = get_all_venues(conn)
    For atomic writes, start a transaction:
        conn = get_db()
        conn.execute('BEGIN IMMEDIATE')
        # ... operations ...
        conn.commit()
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database from schema.sql."""
    conn = get_db()
    with current_app.open_resource('schema.sql') as f:
        conn.executescript(f.read().decode('utf8'))


@click.command('init-db')
def init_db_command():
    init_db()
    click.echo('Database initialized.')
