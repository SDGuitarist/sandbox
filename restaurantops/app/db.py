import os
import sqlite3
from flask import g, current_app

def get_db():
    """Get database connection for current request.

    Uses isolation_level=None to disable Python's implicit transaction
    management. This is REQUIRED for BEGIN IMMEDIATE to work correctly.
    All write routes must call conn.commit() explicitly.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            isolation_level=None
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA busy_timeout=5000")
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
