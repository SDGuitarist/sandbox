import os
import sqlite3
from contextlib import contextmanager

DB_NAME = 'task_tracker_categories.db'


@contextmanager
def get_db(immediate=False):
    from flask import current_app
    conn = sqlite3.connect(current_app.config['DB_PATH'], timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if immediate:
        conn.execute("BEGIN IMMEDIATE")
    try:
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
