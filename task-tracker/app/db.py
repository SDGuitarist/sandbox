import os
import sqlite3
from contextlib import contextmanager

from flask import current_app

@contextmanager
def get_db(immediate=False):
    db_path = current_app.config['DB_PATH']
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        if immediate:
            conn.execute('BEGIN IMMEDIATE')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(app):
    db_path = app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
    conn.close()
