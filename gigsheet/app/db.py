import sqlite3
from flask import g, current_app
import click


def get_db():
    """Returns the request-scoped database connection.
    Usage:
        conn = get_db()
        leads = get_leads_by_workspace(conn, workspace_id)
    For atomic writes, start a transaction:
        conn = get_db()
        conn.execute('BEGIN IMMEDIATE')
        # ... operations ...
        conn.commit()
    NOTE: get_db() is NOT a context manager. Do NOT use `with`.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
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
    conn = get_db()
    with current_app.open_resource('schema.sql') as f:
        conn.executescript(f.read().decode('utf8'))


@click.command('init-db')
def init_db_command():
    init_db()
    click.echo('Initialized the database.')
