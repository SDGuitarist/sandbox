import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workshop.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schema.sql")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(schema)
